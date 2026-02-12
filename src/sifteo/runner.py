"""
Sifteo V1 Runner - Host Application.

Replacement for the original SiftRunner (C++/Qt/Mono, 32-bit Intel).
Manages the USB dongle, cube connections, event routing, and game lifecycle.

Usage:
    from sifteo.runner import SifteoRunner

    runner = SifteoRunner()
    runner.connect()
    runner.run()  # blocking event loop
"""

from __future__ import annotations

import time
import signal
import sys
from typing import Optional, Callable

from .dongle import SifteoDongle, DongleNotFoundError, DongleConnectionError
from .protocol import (
    Op, Message, DONGLE_ADDRESS, NULL_SIFTABLE_ID, op_name,
    cmd_game_start, cmd_game_stop, cmd_request_sift_ids,
)
from .cube import Cube, CubeEvent, NeighborEvent
from .assets import AssetManager


class SifteoRunner:
    """Main host application for Sifteo V1 cubes.

    Manages:
    - USB dongle connection and cube discovery
    - Cube lifecycle (add/remove)
    - Event routing from dongle to cube objects
    - Neighbor state synchronization across cubes
    - Game tick loop
    """

    HEARTBEAT_INTERVAL = 5.0   # seconds between SIFT_IDS polls
    CUBE_TIMEOUT = 15.0        # seconds without events before marking offline

    def __init__(self):
        self.dongle = SifteoDongle()
        self.cubes: dict[int, Cube] = {}
        self.assets: Optional[AssetManager] = None
        self._running = False
        self._tick_callback: Optional[Callable[[float], None]] = None
        self._event_callback: Optional[Callable[[CubeEvent], None]] = None
        self._on_cube_connect: Optional[Callable[[Cube], None]] = None
        self._on_cube_disconnect: Optional[Callable[[Cube], None]] = None
        self._last_tick = 0.0
        self._last_heartbeat = 0.0

    # -- Connection --

    def connect(self, max_discovery_attempts: int = 5) -> bool:
        """Open the USB dongle and discover connected cubes.

        Returns True if at least one cube was found.
        """
        try:
            self.dongle.open()
        except DongleNotFoundError as e:
            print(f"ERROR: {e}")
            return False
        except DongleConnectionError as e:
            print(f"ERROR: {e}")
            return False

        self.assets = AssetManager(self.dongle)

        # Discover cubes
        cube_ids = self.dongle.discover_cubes(max_attempts=max_discovery_attempts)
        if not cube_ids:
            print("No cubes found. Make sure cubes are powered on and nearby.")
            return False

        for cid in sorted(cube_ids):
            self.add_cube(cid)
            # Small pause between cubes so the dongle can finish
            # relaying initialization commands over radio
            time.sleep(0.15)

        return True

    def disconnect(self) -> None:
        """Stop all cubes and close the dongle."""
        for cube in self.cubes.values():
            try:
                cube.game_stop()
            except Exception:
                pass
        self.cubes.clear()
        self.dongle.close()

    # -- Cube Management --

    def add_cube(self, cube_id: int) -> Cube:
        """Register a cube by ID. Creates a Cube object and initializes it."""
        if cube_id in self.cubes:
            return self.cubes[cube_id]

        cube = Cube(cube_id, self.dongle.send)
        self.cubes[cube_id] = cube
        cube.game_start()
        cube.initialize_state()

        if self._on_cube_connect:
            self._on_cube_connect(cube)

        print(f"Cube {cube_id} added and initialized")
        return cube

    def remove_cube(self, cube_id: int) -> None:
        """Unregister a cube."""
        cube = self.cubes.pop(cube_id, None)
        if cube:
            cube.online = False
            if self._on_cube_disconnect:
                self._on_cube_disconnect(cube)
            print(f"Cube {cube_id} removed")

    def get_cube(self, cube_id: int) -> Optional[Cube]:
        """Get a Cube by ID, or None."""
        return self.cubes.get(cube_id)

    # -- Callbacks --

    def on_tick(self, callback: Callable[[float], None]) -> None:
        """Register a tick callback. Called every frame with delta time (seconds)."""
        self._tick_callback = callback

    def on_event(self, callback: Callable[[CubeEvent], None]) -> None:
        """Register a callback for all cube events."""
        self._event_callback = callback

    def on_cube_connect(self, callback: Callable[[Cube], None]) -> None:
        self._on_cube_connect = callback

    def on_cube_disconnect(self, callback: Callable[[Cube], None]) -> None:
        self._on_cube_disconnect = callback

    # -- Event Processing --

    def process_events(self) -> list[CubeEvent]:
        """Process all pending events from the dongle. Returns list of events."""
        events = []

        # Drain dongle response queue (ACKs, pairing notifications)
        self._process_dongle_responses()

        while True:
            msg = self.dongle.get_event(timeout=None)
            if msg is None:
                break
            event = self._route_message(msg)
            if event:
                events.append(event)
        return events

    def _process_dongle_responses(self) -> None:
        """Drain and process dongle response queue for management messages."""
        while True:
            raw = self.dongle.get_response_raw(timeout=None)
            if raw is None:
                break
            if len(raw) < 3:
                continue
            opcode = raw[2]
            if opcode == Op.PAIRED_SIFT and len(raw) >= 4:
                cube_addr = raw[3]
                if cube_addr != DONGLE_ADDRESS:
                    if cube_addr not in self.cubes:
                        self._reconnect_cube(cube_addr)
                    else:
                        # Cube already known - touch it to reset timeout
                        self.cubes[cube_addr].last_seen = time.time()
            elif opcode == Op.UNPAIRED_SIFT and len(raw) >= 4:
                cube_addr = raw[3]
                if cube_addr in self.cubes:
                    self.remove_cube(cube_addr)
            elif opcode == Op.SIFT_IDS and len(raw) >= 4:
                # Heartbeat response: check for new/returning cubes
                count = raw[3]
                reported_ids = set()
                for i in range(count):
                    if 4 + i < len(raw):
                        reported_ids.add(raw[4 + i])
                for cid in reported_ids:
                    if cid != DONGLE_ADDRESS and cid not in self.cubes:
                        self._reconnect_cube(cid)

    def _route_message(self, msg: Message) -> Optional[CubeEvent]:
        """Route an incoming event message to the appropriate cube."""
        # SIFT_IDS: dongle telling us which cubes are present
        if msg.opcode == Op.SIFT_IDS:
            return self._handle_sift_ids(msg)

        cube = self.cubes.get(msg.address)
        if cube is None:
            # Auto-discover: cube we haven't seen yet
            cube = self.add_cube(msg.address)

        event = cube.handle_event(msg)

        # Neighbor events need cross-cube synchronization
        if isinstance(event, NeighborEvent) and not event.is_removal:
            self._sync_neighbor(event)

        if event and self._event_callback:
            self._event_callback(event)

        return event

    def _handle_sift_ids(self, msg: Message) -> None:
        """Handle SIFT_IDS message: dongle reporting connected cube IDs."""
        if len(msg.payload) < 1:
            return None
        count = msg.payload[0]
        cube_ids = list(msg.payload[1:1 + count])

        # Add new cubes
        for cid in cube_ids:
            if cid != DONGLE_ADDRESS and cid not in self.cubes:
                self.add_cube(cid)

        # Remove cubes that are no longer present
        current_ids = set(self.cubes.keys())
        for cid in current_ids - set(cube_ids):
            self.remove_cube(cid)

        return None

    def _sync_neighbor(self, event: NeighborEvent) -> None:
        """Synchronize neighbor state across both cubes in a neighbor pair."""
        neighbor_cube = self.cubes.get(event.neighbor_id)
        if neighbor_cube and 0 <= event.neighbor_side < 4:
            neighbor_cube.neighbors[event.neighbor_side] = (
                event.cube_id, event.my_side
            )

    # -- Heartbeat & Reconnection --

    def _heartbeat(self) -> None:
        """Periodically poll for cube presence and detect disconnects/reconnects."""
        now = time.time()
        if now - self._last_heartbeat < self.HEARTBEAT_INTERVAL:
            return
        self._last_heartbeat = now

        # Poll dongle for currently connected cubes
        self.dongle.send(cmd_request_sift_ids())

        # Check for cubes that have timed out (no events received)
        for cube_id in list(self.cubes.keys()):
            cube = self.cubes[cube_id]
            if cube.online and now - cube.last_seen > self.CUBE_TIMEOUT:
                print(f"Cube {cube_id} timed out (no events for {self.CUBE_TIMEOUT:.0f}s)")
                self.remove_cube(cube_id)

    def _reconnect_cube(self, cube_id: int) -> Cube:
        """Re-initialize a cube that has come back after sleeping."""
        print(f"Cube {cube_id} reconnected, re-initializing...")
        cube = Cube(cube_id, self.dongle.send)
        self.cubes[cube_id] = cube
        cube.game_start()
        cube.initialize_state()

        if self._on_cube_connect:
            self._on_cube_connect(cube)

        return cube

    # -- Repaint --

    def repaint_all(self) -> None:
        """Repaint all cubes that have pending draw operations."""
        for cube in self.cubes.values():
            cube.repaint()

    # -- Main Loop --

    def run(self, target_fps: float = 30.0) -> None:
        """Run the main event loop.

        Processes events, calls tick callback, and repaints cubes
        at the target frame rate. Blocks until stop() is called
        or Ctrl+C is pressed.
        """
        self._running = True
        self._last_tick = time.time()
        frame_time = 1.0 / target_fps

        # Handle Ctrl+C gracefully
        original_sigint = signal.getsignal(signal.SIGINT)
        def _sigint_handler(sig, frame):
            print("\nShutting down...")
            self._running = False
        signal.signal(signal.SIGINT, _sigint_handler)

        print(f"Runner started ({target_fps:.0f} FPS target, {len(self.cubes)} cubes)")
        print("Press Ctrl+C to stop")

        try:
            while self._running:
                frame_start = time.time()

                # 1. Process all pending events
                self.process_events()

                # 1.5. Heartbeat: poll for cube presence changes
                self._heartbeat()

                # 2. Call tick
                now = time.time()
                dt = now - self._last_tick
                self._last_tick = now
                if self._tick_callback:
                    self._tick_callback(dt)

                # 3. Repaint all cubes
                self.repaint_all()

                # 4. Sleep to maintain target FPS
                elapsed = time.time() - frame_start
                sleep_time = frame_time - elapsed
                if sleep_time > 0:
                    time.sleep(sleep_time)
        finally:
            signal.signal(signal.SIGINT, original_sigint)
            self.disconnect()
            print("Runner stopped.")

    def stop(self) -> None:
        """Signal the main loop to stop."""
        self._running = False

    # -- Convenience --

    def __repr__(self):
        status = "connected" if self.dongle.is_open else "disconnected"
        return f"SifteoRunner({status}, {len(self.cubes)} cubes)"
