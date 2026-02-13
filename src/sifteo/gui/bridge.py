"""Python<->JS bridge: backend logic exposed to the pywebview frontend."""

from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
import zlib
from pathlib import Path
from typing import Optional

from ..dongle import enumerate_dongles_pyusb, DongleConnectionError, DongleWriteError
from ..runner import SifteoRunner
from ..cube import (
    TiltEvent, ButtonEvent, ShakeEvent, NeighborEvent,
    BatteryLowEvent, DockStateEvent, DockLocationEvent,
)
from ..assets import UploadError, parse_siftapp_header
from .catalog import discover_games

# Where the 23 bundled .siftapp games live.
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_SIFTAPP_DIR = _PROJECT_ROOT / "sifteo-gen1-redux" / "payload" / "Siftapps"


class Bridge:
    """JS-callable API object passed as pywebview's js_api.

    Every public method is callable from JS as:
        const result = await pywebview.api.method_name(args);

    pywebview runs each call in a worker thread, so USB I/O is safe here.
    """

    def __init__(self):
        self._runner: Optional[SifteoRunner] = None
        self._lock = threading.Lock()
        self._window = None  # webview.Window, set after window loads
        self._poll_thread: Optional[threading.Thread] = None
        self._poll_running = False
        self._games: Optional[list[dict]] = None
        self._installing: set[str] = set()  # game names currently installing
        self._last_events: dict[int, dict] = {}  # cube_id -> {type, detail, time}

    def set_window(self, window) -> None:
        self._window = window
        self._start_polling()

    # ── Status ──────────────────────────────────────────────────────

    def get_status(self) -> dict:
        """Return current connection state (called by JS on load + poll).

        Uses pyusb-only detection (thread-safe) since this is called from
        pywebview worker threads and the background polling thread.
        macOS IOKit hidapi crashes when called off the main thread.
        """
        dongles = enumerate_dongles_pyusb()
        connected = self._runner is not None and self._runner.dongle.is_open
        cubes = []
        if connected and self._runner:
            for cid, cube in sorted(self._runner.cubes.items()):
                cubes.append({
                    "id": cid,
                    "online": cube.online,
                    "firmware_version": cube.firmware_version or "unknown",
                    "battery_low": cube.battery_low,
                    "device_id": cube.device_id,
                    "docked": cube.docked,
                    "dock_location": cube.dock_location,
                    "button_pressed": cube.button_pressed,
                    "tilt": list(cube.tilt),
                    "neighbors": [
                        {"cube": n[0], "side": n[1]} if n else None
                        for n in cube.neighbors
                    ],
                    "last_seen": cube.last_seen,
                    "last_event": self._last_events.get(cid),
                })
        return {
            "dongle_plugged_in": len(dongles) > 0,
            "is_root": os.geteuid() == 0,
            "connected": connected,
            "cubes": cubes,
        }

    # ── Connect / Disconnect ────────────────────────────────────────

    def connect(self) -> dict:
        """Open the dongle and discover cubes. Requires root."""
        with self._lock:
            if self._runner and self._runner.dongle.is_open:
                return {"ok": True, "cubes": self.get_status()["cubes"]}

            if os.geteuid() != 0:
                self._log("error", "Root access required")
                return {"ok": False, "error": "Root access required. Relaunch with sudo."}

            self._log("info", "Opening dongle and discovering cubes...")
            runner = SifteoRunner()
            try:
                if not runner.connect():
                    self._log("warn", "No cubes found nearby")
                    return {"ok": False, "error": "No cubes found. Power on cubes near the dongle."}
            except (DongleConnectionError, Exception) as exc:
                self._log("error", f"Connection failed: {exc}")
                return {"ok": False, "error": str(exc)}

            self._runner = runner
            cubes = self.get_status()["cubes"]
            self._log("ok", f"Dongle open, {len(cubes)} cube(s) discovered")
            return {"ok": True, "cubes": cubes}

    def disconnect(self) -> dict:
        """Close dongle connection."""
        with self._lock:
            if self._runner:
                try:
                    self._runner.disconnect()
                except Exception:
                    pass
                self._runner = None
            return {"ok": True}

    # ── Relaunch with sudo (macOS) ──────────────────────────────────

    def relaunch_as_root(self) -> dict:
        """Relaunch the GUI with root privileges via macOS osascript."""
        import shlex
        python = shlex.quote(sys.executable)
        # Double-escape for AppleScript string embedding
        shell_cmd = f"{python} -m sifteo gui".replace("\\", "\\\\").replace('"', '\\"')
        cmd = (
            f'do shell script "{shell_cmd}" '
            f'with administrator privileges'
        )
        try:
            subprocess.Popen(["osascript", "-e", cmd])
            # Give the new process a moment, then quit this one
            if self._window:
                self._window.destroy()
            return {"ok": True}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    # ── Game Catalog ────────────────────────────────────────────────

    def get_games(self) -> list[dict]:
        """Return metadata for all available games."""
        if self._games is None:
            if _SIFTAPP_DIR.is_dir():
                self._games = discover_games(_SIFTAPP_DIR)
            else:
                self._games = []
        # Return without 'path' (JS doesn't need filesystem paths)
        return [
            {k: v for k, v in g.items() if k != "path"}
            for g in self._games
        ]

    # ── Installed App Scan ──────────────────────────────────────────

    def scan_installed_apps(self) -> dict:
        """Scan cubes for installed apps. Returns {game_name: [cube_ids]}."""
        with self._lock:
            if not self._runner or not self._runner.dongle.is_open:
                return {}
            if self._runner.assets is None:
                return {}

        # Build app_id -> game_name mapping from .siftapp headers
        all_games = self._games or discover_games(_SIFTAPP_DIR)
        app_id_to_game: dict[int, str] = {}
        for game in all_games:
            path = Path(game.get("path", ""))
            if not path.exists():
                continue
            try:
                with open(path, "rb") as f:
                    header_data = f.read(16)
                header = parse_siftapp_header(header_data)
                if header.valid and header.internal_id is not None:
                    app_id = header.internal_id
                else:
                    app_id = zlib.crc32(path.stem.encode("utf-8")) & 0xFFFFFFFF
                app_id_to_game[app_id] = game["name"]
            except Exception:
                continue

        # Query each cube for its installed app list
        installed: dict[str, list[int]] = {}
        with self._lock:
            if not self._runner or self._runner.assets is None:
                return {}
            cube_ids = sorted(self._runner.cubes.keys())
            for cube_id in cube_ids:
                try:
                    self._log("info", f"Scanning cube {cube_id} for installed apps...")
                    app_ids = self._runner.assets.query_app_list(
                        cube_id, timeout=5.0,
                    )
                    for aid in app_ids:
                        game_name = app_id_to_game.get(aid)
                        if game_name:
                            installed.setdefault(game_name, []).append(cube_id)
                except Exception as exc:
                    self._log("warn", f"Could not scan cube {cube_id}: {exc}")

        count = sum(len(v) for v in installed.values())
        self._log("info", f"Scan complete: {count} app(s) found across {len(cube_ids)} cube(s)")
        return installed

    # ── Install ─────────────────────────────────────────────────────

    def install_game(self, name: str, cube_ids: list[int] | None = None) -> dict:
        """Install a .siftapp on one or more cubes. Pushes progress events."""
        if name in self._installing:
            return {"ok": False, "error": f"{name} is already installing."}

        with self._lock:
            if not self._runner or not self._runner.dongle.is_open:
                return {"ok": False, "error": "Not connected."}
            if self._runner.assets is None:
                return {"ok": False, "error": "Asset manager unavailable."}

            # Resolve the game path
            all_games = self._games or discover_games(_SIFTAPP_DIR)
            game = next((g for g in all_games if g["name"] == name), None)
            if game is None:
                return {"ok": False, "error": f"Unknown game: {name}"}
            siftapp_path = game["path"]

            # Target cubes
            if cube_ids:
                targets = [cid for cid in cube_ids if cid in self._runner.cubes]
            else:
                targets = sorted(self._runner.cubes.keys())

            if not targets:
                return {"ok": False, "error": "No target cubes available."}

        self._installing.add(name)
        any_failed = False
        self._log("info", f"Starting install: {name} -> cube(s) {targets}")

        for cube_id in targets:
            try:
                last_push = [0.0]

                def progress_cb(sent: int, total: int, _cid=cube_id) -> None:
                    now = time.time()
                    # Throttle to ~10 updates/sec
                    if now - last_push[0] < 0.1 and sent < total:
                        return
                    last_push[0] = now
                    pct = int(sent * 100 / total) if total else 0
                    self._push_event("install_progress", {
                        "game": name, "cube_id": _cid, "percent": pct,
                    })

                self._log("info", f"Uploading {name} to cube {cube_id}...")
                with self._lock:
                    result = self._runner.assets.install_siftapp(
                        cube_id=cube_id,
                        siftapp_path=siftapp_path,
                        progress=progress_cb,
                    )

                self._log("info", f"Upload complete, verifying CRC for cube {cube_id}...")
                # CRC verify
                with self._lock:
                    crc = self._runner.assets.verify_crc(
                        cube_id, result.app_id, result.asset_id,
                    )

                ok = crc is not None and crc.valid
                if not ok:
                    any_failed = True
                    self._log("error", f"CRC mismatch on cube {cube_id}")
                else:
                    self._log("ok", f"CRC verified on cube {cube_id}")

                self._push_event("install_done", {
                    "game": name, "cube_id": cube_id, "ok": ok,
                    "error": None if ok else "CRC mismatch",
                })

            except (FileNotFoundError, UploadError, ValueError,
                    DongleWriteError, DongleConnectionError) as exc:
                any_failed = True
                self._log("error", f"Install failed on cube {cube_id}: {exc}")
                self._push_event("install_done", {
                    "game": name, "cube_id": cube_id, "ok": False,
                    "error": str(exc),
                })

        self._installing.discard(name)
        return {"ok": not any_failed}

    # ── Settings ──────────────────────────────────────────────────────

    def get_settings(self) -> dict:
        """Return current dongle write-tuning settings."""
        from ..dongle import SifteoDongle
        if self._runner and self._runner.dongle:
            dongle = self._runner.dongle
            return {
                "write_min_gap": dongle._write_min_gap,
                "write_max_retries": dongle._write_max_retries,
            }
        # Return defaults when not connected
        return {
            "write_min_gap": SifteoDongle.WRITE_MIN_GAP,
            "write_max_retries": SifteoDongle.WRITE_MAX_RETRIES,
        }

    def set_write_speed(self, gap: float) -> dict:
        """Set the minimum gap between USB writes (seconds)."""
        gap = max(0.0, float(gap))
        if self._runner and self._runner.dongle:
            self._runner.dongle._write_min_gap = gap
            self._log("ok", f"Write gap set to {gap:.6f}s")
        return {"ok": True, "write_min_gap": gap}

    def set_write_retries(self, retries: int) -> dict:
        """Set the number of USB write retry attempts."""
        retries = max(0, int(retries))
        if self._runner and self._runner.dongle:
            self._runner.dongle._write_max_retries = retries
            self._log("ok", f"Write retries set to {retries}")
        return {"ok": True, "write_max_retries": retries}

    # ── Background polling ──────────────────────────────────────────

    def _start_polling(self) -> None:
        if self._poll_running:
            return
        self._poll_running = True
        self._poll_thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._poll_thread.start()

    def stop_polling(self) -> None:
        self._poll_running = False

    def _poll_loop(self) -> None:
        """Background loop: detect dongle, process cube events, push status."""
        last_status: dict = {}
        self._log("info", "Background polling started")
        while self._poll_running:
            try:
                # Process events FIRST so status reflects latest cube state
                if self._runner and self._runner.dongle.is_open:
                    with self._lock:
                        try:
                            events = self._runner.process_events()
                            self._runner._heartbeat()
                        except Exception:
                            events = []
                    for ev in events:
                        self._record_event(ev)

                status = self.get_status()

                # Push status change to JS
                if status != last_status:
                    # Log meaningful transitions
                    if last_status:
                        old_d = last_status.get("dongle_plugged_in")
                        new_d = status["dongle_plugged_in"]
                        if new_d and not old_d:
                            self._log("info", "Dongle plugged in")
                        elif not new_d and old_d:
                            self._log("warn", "Dongle unplugged")

                    self._push_event("status_update", status)
                    last_status = status

                if self._runner and self._runner.dongle.is_open:
                    time.sleep(0.5)
                else:
                    time.sleep(2.0)

            except Exception as exc:
                self._log("error", f"Poll error: {exc}")
                time.sleep(2.0)

    _SIDE_NAMES = ["top", "left", "bottom", "right"]

    def _record_event(self, event) -> None:
        """Store the most recent event per cube for the popup display."""
        now = time.time()
        if isinstance(event, TiltEvent):
            self._last_events[event.cube_id] = {
                "type": "tilt",
                "detail": f"({event.x}, {event.y}, {event.z})",
                "time": now,
            }
        elif isinstance(event, ButtonEvent):
            self._last_events[event.cube_id] = {
                "type": "click",
                "detail": "pressed" if event.pressed else "released",
                "time": now,
            }
        elif isinstance(event, ShakeEvent):
            self._last_events[event.cube_id] = {
                "type": "shake",
                "detail": "",
                "time": now,
            }
        elif isinstance(event, NeighborEvent):
            side = self._SIDE_NAMES[event.my_side] if event.my_side < 4 else str(event.my_side)
            if event.is_removal:
                detail = f"{side} removed"
            else:
                detail = f"cube {event.neighbor_id} on {side}"
            self._last_events[event.cube_id] = {
                "type": "neighbor",
                "detail": detail,
                "time": now,
            }
        elif isinstance(event, DockStateEvent):
            self._last_events[event.cube_id] = {
                "type": "dock",
                "detail": "docked" if event.docked else "undocked",
                "time": now,
            }
        elif isinstance(event, DockLocationEvent):
            self._last_events[event.cube_id] = {
                "type": "dock",
                "detail": f"slot {event.location}",
                "time": now,
            }
        elif isinstance(event, BatteryLowEvent):
            self._last_events[event.cube_id] = {
                "type": "battery",
                "detail": "low",
                "time": now,
            }

    def _log(self, level: str, message: str) -> None:
        """Push a log message to the JS console panel."""
        self._push_event("log", {"level": level, "message": message})

    def _push_event(self, event_type: str, data: dict) -> None:
        """Push an event from Python to JS via evaluate_js."""
        if self._window is None:
            return
        import json
        payload = json.dumps({"type": event_type, "data": data})
        try:
            self._window.evaluate_js(f"window.onSifteoEvent({payload})")
        except Exception:
            pass  # Window may be closing

    # ── Cleanup ─────────────────────────────────────────────────────

    def cleanup(self) -> None:
        """Graceful shutdown: stop polling, disconnect dongle."""
        self.stop_polling()
        if self._runner:
            try:
                self._runner.disconnect()
            except Exception:
                pass
            self._runner = None
