"""
Sifteo V1 Application Base Class.

Provides the BaseApp class that developers subclass to create games
and interactive experiences for Sifteo V1 cubes.

Basic usage (no assets):

    from sifteo import BaseApp, Cube

    class MyGame(BaseApp):
        def setup(self):
            for cube in self.cubes:
                cube.fill(0, 0, 255)

        def on_button(self, cube, pressed):
            if pressed:
                cube.fill(255, 0, 0)

    if __name__ == "__main__":
        MyGame().run()

With declarative assets (auto-uploaded before setup):

    class MyGame(BaseApp):
        APP_NAME = "my_game"        # auto-generates 32-bit app_id
        IMAGES = {"logo": "assets/logo.png"}
        SOUNDS = {"beep": "assets/beep.wav"}

        def setup(self):
            for cube in self.cubes:
                cube.image(self.app_id, self.asset_id("logo"))
                cube.repaint()

    if __name__ == "__main__":
        MyGame().run()
"""

from __future__ import annotations

import inspect
import os
import zlib
from typing import Optional

from .runner import SifteoRunner
from .cube import (
    Cube, CubeEvent, TiltEvent, ButtonEvent,
    NeighborEvent, ShakeEvent, BatteryLowEvent,
    FirmwareVersionEvent, DockStateEvent, DockLocationEvent,
)
from .assets import (
    AssetManager, AssetManifest, AssetDeclaration, sync_app_assets,
    ASSET_TYPE_IMAGE, ASSET_TYPE_SOUND,
)
from .sound import SoundMixer


class BaseApp:
    """Base class for Sifteo V1 applications.

    Subclass this and override event handlers and tick() to build a game.

    Lifecycle:
        1. __init__() -> creates runner
        2. run() -> connects dongle, syncs assets (if declared), calls setup(),
           enters event loop
        3. setup() -> called once after connection, before first tick
        4. tick(dt) -> called every frame with delta time in seconds
        5. Event handlers called as events arrive from cubes

    Asset declarations (optional class attributes):
        APP_NAME: str            - auto-generates app_id via CRC32
        APP_ID: int              - explicit 32-bit app_id (overrides APP_NAME)
        IMAGES: dict[str, str]   - name -> relative file path
        SOUNDS: dict[str, str]   - name -> relative file path

    Properties:
        cubes: list of all connected Cube objects
        runner: the underlying SifteoRunner instance
        app_id: the 32-bit app ID (from APP_ID, APP_NAME hash, or None)

    Methods:
        asset_id(name): look up the integer asset_id for a named asset

    Event handlers (override to handle):
        on_new_cube(cube)        - cube connected
        on_lost_cube(cube)       - cube disconnected
        on_tilt(cube, x, y, z)   - accelerometer tilt change
        on_button(cube, pressed) - button press/release
        on_shake(cube)           - shake detected
        on_neighbor_add(cube, side, neighbor, neighbor_side)
        on_neighbor_remove(cube, side)
        on_flip(cube, face_down) - cube flipped over
    """

    # -- Asset Declaration (override in subclass) --

    APP_NAME: Optional[str] = None
    APP_ID: Optional[int] = None
    IMAGES: dict = {}
    SOUNDS: dict = {}

    def __init__(self, target_fps: float = 30.0):
        self.runner = SifteoRunner()
        self.sound = SoundMixer()
        self._target_fps = target_fps
        self._prev_tilt: dict[int, tuple] = {}
        self._prev_face_down: dict[int, bool] = {}
        self._manifest: Optional[AssetManifest] = None

    @property
    def cubes(self) -> list[Cube]:
        """All currently connected cubes."""
        return list(self.runner.cubes.values())

    @property
    def assets(self) -> Optional[AssetManager]:
        """Asset manager for uploading/downloading assets to cubes."""
        return self.runner.assets

    @property
    def app_id(self) -> Optional[int]:
        """The 32-bit app ID, or None if no APP_NAME/APP_ID is set."""
        cls = type(self)
        explicit_id = getattr(cls, 'APP_ID', None)
        if explicit_id is not None:
            return explicit_id & 0xFFFFFFFF
        app_name = getattr(cls, 'APP_NAME', None)
        if app_name:
            return zlib.crc32(app_name.encode('utf-8')) & 0xFFFFFFFF
        return None

    def asset_id(self, name: str) -> int:
        """Look up the integer asset_id for a named asset.

        Args:
            name: The asset name as declared in IMAGES or SOUNDS.

        Returns:
            The integer asset_id assigned to this asset.

        Raises:
            RuntimeError: If no assets are declared.
            KeyError: If the name is not found.
        """
        if self._manifest is None:
            raise RuntimeError("No assets declared (set IMAGES/SOUNDS class attributes)")
        if name not in self._manifest.assets:
            raise KeyError(f"Unknown asset name: {name!r}")
        return self._manifest.assets[name].asset_id

    def run(self, cube_ids: Optional[list[int]] = None) -> None:
        """Connect to dongle and start the game loop.

        If IMAGES or SOUNDS are declared, assets are synced to all
        cubes before setup() is called.

        Args:
            cube_ids: Optional list of cube IDs to pre-register.
                     If None, cubes are discovered automatically.
        """
        if not self.runner.connect():
            return

        if cube_ids:
            for cid in cube_ids:
                self.runner.add_cube(cid)

        self.runner.on_tick(self._internal_tick)
        self.runner.on_event(self._dispatch_event)
        self.runner.on_cube_connect(self._on_cube_connect)
        self.runner.on_cube_disconnect(self._on_cube_disconnect)

        self._manifest = self._build_manifest()
        if self._manifest:
            self._sync_assets()

        self.setup()
        self.runner.run(target_fps=self._target_fps)

    def sync_assets_to_cube(self, cube: Cube) -> None:
        """Upload declared assets to a specific cube.

        Useful for syncing assets to a cube that connects mid-game.
        """
        if self._manifest is None or self.assets is None:
            return
        sync_app_assets(self.assets, cube.id, self._manifest)

    # -- Lifecycle (override these) --

    def setup(self):
        """Called once after the dongle is connected, before the first tick.

        Override this to initialize your game state and draw the initial
        screen on each cube.
        """
        pass

    def tick(self, dt: float):
        """Called every frame.

        Args:
            dt: Time elapsed since last tick, in seconds.
        """
        pass

    # -- Event Handlers (override these) --

    def on_new_cube(self, cube: Cube):
        """Called when a new cube connects."""
        pass

    def on_lost_cube(self, cube: Cube):
        """Called when a cube disconnects."""
        pass

    def on_tilt(self, cube: Cube, x: int, y: int, z: int):
        """Called when a cube's tilt changes.

        x, y: 0=tilt left/up, 1=level, 2=tilt right/down
        z: 0=face down, 2=face up
        """
        pass

    def on_button(self, cube: Cube, pressed: bool):
        """Called when a cube's button is pressed or released."""
        pass

    def on_shake(self, cube: Cube):
        """Called when a cube is shaken."""
        pass

    def on_neighbor_add(self, cube: Cube, side: int,
                        neighbor: Cube, neighbor_side: int):
        """Called when two cubes are placed next to each other.

        Sides: 0=top, 1=left, 2=bottom, 3=right
        """
        pass

    def on_neighbor_remove(self, cube: Cube, side: int):
        """Called when a neighbor is removed from a cube's side."""
        pass

    def on_flip(self, cube: Cube, face_down: bool):
        """Called when a cube is flipped face-down or face-up."""
        pass

    def on_battery_low(self, cube: Cube):
        """Called when a cube reports low battery."""
        pass

    def on_dock(self, cube: Cube, docked: bool):
        """Called when a cube's dock state changes."""
        pass

    def on_firmware_version(self, cube: Cube, version: str):
        """Called when a cube reports its firmware version."""
        pass

    # -- Internal --

    def _build_manifest(self) -> Optional[AssetManifest]:
        """Compute asset manifest from class attributes.

        Returns None if no IMAGES or SOUNDS are declared.
        """
        cls = type(self)
        images = getattr(cls, 'IMAGES', {}) or {}
        sounds = getattr(cls, 'SOUNDS', {}) or {}

        if not images and not sounds:
            return None

        # Determine app_id
        aid = self.app_id
        if aid is None:
            aid = 0  # Default if neither APP_NAME nor APP_ID is set

        # Resolve paths relative to the file defining the subclass
        try:
            base_dir = os.path.dirname(os.path.abspath(inspect.getfile(cls)))
        except (TypeError, OSError):
            base_dir = os.getcwd()

        assets: dict[str, AssetDeclaration] = {}
        next_id = 0

        for name in sorted(images.keys()):
            rel_path = images[name]
            abs_path = os.path.join(base_dir, rel_path)
            assets[name] = AssetDeclaration(
                name=name, path=abs_path,
                asset_type=ASSET_TYPE_IMAGE, asset_id=next_id,
            )
            next_id += 1

        for name in sorted(sounds.keys()):
            rel_path = sounds[name]
            abs_path = os.path.join(base_dir, rel_path)
            assets[name] = AssetDeclaration(
                name=name, path=abs_path,
                asset_type=ASSET_TYPE_SOUND, asset_id=next_id,
            )
            next_id += 1

        app_name = getattr(cls, 'APP_NAME', None)
        return AssetManifest(app_id=aid, app_name=app_name, assets=assets)

    def _sync_assets(self) -> None:
        """Upload declared assets to all connected cubes."""
        if self._manifest is None or self.assets is None:
            return
        label = self._manifest.app_name or str(self._manifest.app_id)
        count = len(self._manifest.assets)
        print(f"Syncing {count} asset(s) for app {label}...")
        for cube in self.cubes:
            sync_app_assets(self.assets, cube.id, self._manifest)
        print("Asset sync complete.")

    def _internal_tick(self, dt: float):
        self.tick(dt)

    def _on_cube_connect(self, cube: Cube):
        self._prev_tilt[cube.id] = cube.tilt
        self._prev_face_down[cube.id] = cube.face_down
        self.on_new_cube(cube)

    def _on_cube_disconnect(self, cube: Cube):
        self._prev_tilt.pop(cube.id, None)
        self._prev_face_down.pop(cube.id, None)
        self.on_lost_cube(cube)

    def _dispatch_event(self, event: CubeEvent):
        cube = self.runner.get_cube(event.cube_id)
        if cube is None:
            return

        if isinstance(event, TiltEvent):
            self.on_tilt(cube, event.x, event.y, event.z)
            # Check for flip
            prev_fd = self._prev_face_down.get(cube.id)
            curr_fd = cube.face_down
            if prev_fd is not None and prev_fd != curr_fd:
                self.on_flip(cube, curr_fd)
            self._prev_face_down[cube.id] = curr_fd

        elif isinstance(event, ButtonEvent):
            self.on_button(cube, event.pressed)

        elif isinstance(event, ShakeEvent):
            self.on_shake(cube)

        elif isinstance(event, NeighborEvent):
            if event.is_removal:
                self.on_neighbor_remove(cube, event.my_side)
            else:
                neighbor = self.runner.get_cube(event.neighbor_id)
                if neighbor:
                    self.on_neighbor_add(
                        cube, event.my_side,
                        neighbor, event.neighbor_side
                    )

        elif isinstance(event, BatteryLowEvent):
            self.on_battery_low(cube)

        elif isinstance(event, DockStateEvent):
            self.on_dock(cube, event.docked)

        elif isinstance(event, FirmwareVersionEvent):
            self.on_firmware_version(cube, event.version)
