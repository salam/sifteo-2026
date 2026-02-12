"""
Sifteo V1 Application Base Class.

Provides the BaseApp class that developers subclass to create games
and interactive experiences for Sifteo V1 cubes.

Usage:
    from sifteo import BaseApp, Cube

    class MyGame(BaseApp):
        def setup(self):
            for cube in self.cubes:
                cube.fill(0, 0, 255)

        def tick(self, dt):
            pass

        def on_button(self, cube, pressed):
            if pressed:
                cube.fill(255, 0, 0)

    if __name__ == "__main__":
        MyGame().run()
"""

from __future__ import annotations

from typing import Optional
from .runner import SifteoRunner
from .cube import (
    Cube, CubeEvent, TiltEvent, ButtonEvent,
    NeighborEvent, ShakeEvent, BatteryLowEvent,
)
from .assets import AssetManager


class BaseApp:
    """Base class for Sifteo V1 applications.

    Subclass this and override event handlers and tick() to build a game.

    Lifecycle:
        1. __init__() -> creates runner
        2. run() -> connects dongle, calls setup(), enters event loop
        3. setup() -> called once after connection, before first tick
        4. tick(dt) -> called every frame with delta time in seconds
        5. Event handlers called as events arrive from cubes

    Properties:
        cubes: list of all connected Cube objects
        runner: the underlying SifteoRunner instance

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

    def __init__(self, target_fps: float = 30.0):
        self.runner = SifteoRunner()
        self._target_fps = target_fps
        self._prev_tilt: dict[int, tuple] = {}
        self._prev_face_down: dict[int, bool] = {}

    @property
    def cubes(self) -> list[Cube]:
        """All currently connected cubes."""
        return list(self.runner.cubes.values())

    @property
    def assets(self) -> Optional[AssetManager]:
        """Asset manager for uploading/downloading assets to cubes."""
        return self.runner.assets

    def run(self, cube_ids: Optional[list[int]] = None) -> None:
        """Connect to dongle and start the game loop.

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

        self.setup()
        self.runner.run(target_fps=self._target_fps)

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

    # -- Internal --

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
