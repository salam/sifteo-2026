"""
Sifteo V1 Cube Abstraction.

Represents a physical Sifteo cube and provides high-level APIs
for display, sensors, and neighbor detection.
"""

import time
from typing import Optional, Callable
from .protocol import (
    Op, Message, DONGLE_ADDRESS, NULL_SIFTABLE_ID,
    cmd_request_tilt, cmd_request_button, cmd_request_neighbors,
    cmd_request_device_id, cmd_game_start, cmd_game_stop,
    cmd_fill_screen, cmd_draw_rect, cmd_repaint, cmd_blit_image,
    cmd_put_pixel, cmd_set_rotation, cmd_request_cube_fw_version,
    rgb_to_rgb332, unpack_u8, unpack_u16, unpack_u32, op_name,
)

SCREEN_WIDTH = 128
SCREEN_HEIGHT = 128
NUM_SIDES = 4
START_TILT = (1, 1, 2)


class CubeEvent:
    """Base class for cube events."""
    def __init__(self, cube_id: int):
        self.cube_id = cube_id

class TiltEvent(CubeEvent):
    def __init__(self, cube_id: int, x: int, y: int, z: int):
        super().__init__(cube_id)
        self.x = x
        self.y = y
        self.z = z
    def __repr__(self):
        return f"TiltEvent(cube={self.cube_id}, x={self.x}, y={self.y}, z={self.z})"

class ButtonEvent(CubeEvent):
    def __init__(self, cube_id: int, pressed: bool):
        super().__init__(cube_id)
        self.pressed = pressed
    def __repr__(self):
        return f"ButtonEvent(cube={self.cube_id}, pressed={self.pressed})"

class NeighborEvent(CubeEvent):
    def __init__(self, cube_id: int, my_side: int, neighbor_id: int, neighbor_side: int):
        super().__init__(cube_id)
        self.my_side = my_side
        self.neighbor_id = neighbor_id
        self.neighbor_side = neighbor_side
    @property
    def is_removal(self):
        return self.neighbor_id == NULL_SIFTABLE_ID
    def __repr__(self):
        action = "removed" if self.is_removal else f"neighbor={self.neighbor_id}"
        return f"NeighborEvent(cube={self.cube_id}, side={self.my_side}, {action})"

class ShakeEvent(CubeEvent):
    def __init__(self, cube_id: int):
        super().__init__(cube_id)
    def __repr__(self):
        return f"ShakeEvent(cube={self.cube_id})"

class BatteryLowEvent(CubeEvent):
    def __repr__(self):
        return f"BatteryLowEvent(cube={self.cube_id})"

class FirmwareVersionEvent(CubeEvent):
    def __init__(self, cube_id: int, version: str):
        super().__init__(cube_id)
        self.version = version
    def __repr__(self):
        return f"FirmwareVersionEvent(cube={self.cube_id}, version={self.version!r})"

class DockStateEvent(CubeEvent):
    def __init__(self, cube_id: int, docked: bool):
        super().__init__(cube_id)
        self.docked = docked
    def __repr__(self):
        return f"DockStateEvent(cube={self.cube_id}, docked={self.docked})"

class DockLocationEvent(CubeEvent):
    def __init__(self, cube_id: int, location: int):
        super().__init__(cube_id)
        self.location = location
    def __repr__(self):
        return f"DockLocationEvent(cube={self.cube_id}, location={self.location})"


class Cube:
    """Represents a physical Sifteo V1 cube.

    Provides a high-level interface for:
    - Display: fill, rect, image, repaint
    - Sensors: tilt, button, shake, neighbors
    - State: connection, battery, firmware
    """

    def __init__(self, cube_id: int, send_fn: Callable[[Message], None]):
        self.id = cube_id
        self._send = send_fn
        self.tilt = START_TILT
        self.button_pressed = False
        self.neighbors = [None, None, None, None]  # 4 sides
        self.device_id: Optional[str] = None
        self.firmware_version: Optional[str] = None
        self.battery_low: bool = False
        self.docked: bool = False
        self.dock_location: Optional[int] = None
        self.online = True
        self.last_seen = time.time()
        self._draw_count = 0
        self._orientation = 0

    # -- Display --

    def fill(self, r: int, g: int, b: int):
        """Fill screen with an RGB color (0-255 each)."""
        color = rgb_to_rgb332(r, g, b)
        self._send(cmd_fill_screen(self.id, color))
        self._draw_count += 1

    def fill_color(self, color_rgb8: int):
        """Fill screen with a raw RGB332 color byte."""
        self._send(cmd_fill_screen(self.id, color_rgb8))
        self._draw_count += 1

    def rect(self, x: int, y: int, w: int, h: int, r: int, g: int, b: int):
        """Draw a filled rectangle."""
        color = rgb_to_rgb332(r, g, b)
        self._send(cmd_draw_rect(self.id, x, y, w, h, color))
        self._draw_count += 1

    def image(self, app_id: int, asset_id: int, x: int = 0, y: int = 0,
              w: int = SCREEN_WIDTH, h: int = SCREEN_HEIGHT,
              src_x: int = 0, src_y: int = 0, scale: int = 1, rotation: int = 0):
        """Blit an image from cube flash to the display."""
        self._send(cmd_blit_image(self.id, app_id, asset_id,
                                  x, y, src_x, src_y, w, h, scale, rotation))
        self._draw_count += 1

    def put_pixel(self, x: int, y: int, r: int, g: int, b: int):
        """Draw a single pixel at (x, y) with an RGB color (0-255 each)."""
        color = rgb_to_rgb332(r, g, b)
        self._send(cmd_put_pixel(self.id, x, y, color))
        self._draw_count += 1

    def put_pixel_color(self, x: int, y: int, color_rgb8: int):
        """Draw a single pixel at (x, y) with a raw RGB332 color byte."""
        self._send(cmd_put_pixel(self.id, x, y, color_rgb8))
        self._draw_count += 1

    def repaint(self):
        """Repaint the display. Call after drawing operations."""
        if self._draw_count > 0:
            rotation_map = [0, 3, 2, 1]
            self._send(cmd_repaint(self.id, rotation_map[self._orientation]))
            self._draw_count = 0

    @property
    def orientation(self) -> int:
        return self._orientation

    @orientation.setter
    def orientation(self, value: int):
        self._orientation = value % 4
        self._send(cmd_set_rotation(self.id, self._orientation))

    # -- Sensor Queries --

    def request_tilt(self):
        """Request current tilt data (async, result via event)."""
        self._send(cmd_request_tilt(self.id))

    def request_button(self):
        """Request current button state (async, result via event)."""
        self._send(cmd_request_button(self.id))

    def request_neighbors(self):
        """Request full neighbor report (async, result via event)."""
        self._send(cmd_request_neighbors(self.id))

    def request_device_id(self):
        """Request hardware device ID (async, result via event)."""
        self._send(cmd_request_device_id(self.id))

    def request_firmware_version(self):
        """Request firmware version from the cube (async, result via event)."""
        self._send(cmd_request_cube_fw_version(self.id))

    def initialize_state(self):
        """Query all sensor states (tilt, button, neighbors, firmware)."""
        self.request_tilt()
        self.request_button()
        self.request_neighbors()
        self.request_firmware_version()

    # -- Game Control --

    def game_start(self):
        """Tell cube a game is starting (exit idle screen)."""
        self._send(cmd_game_start(self.id))

    def game_stop(self):
        """Tell cube to return to idle/pairing screen."""
        self._send(cmd_game_stop(self.id))

    # -- Event Handling --

    def handle_event(self, msg: Message) -> Optional[CubeEvent]:
        """Process an incoming event message. Returns a CubeEvent or None."""
        self.last_seen = time.time()
        op = msg.opcode
        payload = msg.payload

        if op == Op.TILT:
            if len(payload) >= 3:
                x, y, z = payload[0], payload[1], payload[2]
                self.tilt = (x, y, z)
                return TiltEvent(self.id, x, y, z)

        elif op == Op.BUTTON:
            if len(payload) >= 1:
                pressed = payload[0] != 0
                self.button_pressed = pressed
                return ButtonEvent(self.id, pressed)

        elif op == Op.NEIGHBOR:
            if len(payload) >= 3:
                my_side = payload[0]
                neighbor_id = payload[1]
                neighbor_side = payload[2]
                if neighbor_id == NULL_SIFTABLE_ID:
                    if 0 <= my_side < NUM_SIDES:
                        self.neighbors[my_side] = None
                else:
                    if 0 <= my_side < NUM_SIDES:
                        self.neighbors[my_side] = (neighbor_id, neighbor_side)
                return NeighborEvent(self.id, my_side, neighbor_id, neighbor_side)

        elif op == Op.SHAKE:
            return ShakeEvent(self.id)

        elif op == Op.BATTERY_LOW:
            self.battery_low = True
            return BatteryLowEvent(self.id)

        elif op == Op.FIRMWARE_VERSION:
            if len(payload) >= 3:
                major, minor, patch = payload[0], payload[1], payload[2]
                self.firmware_version = f"{major}.{minor}.{patch}"
            elif len(payload) >= 1:
                self.firmware_version = payload.hex()
            else:
                self.firmware_version = "unknown"
            return FirmwareVersionEvent(self.id, self.firmware_version)

        elif op == Op.DOCK_STATE:
            docked = payload[0] != 0 if len(payload) >= 1 else False
            self.docked = docked
            return DockStateEvent(self.id, docked)

        elif op == Op.DOCK_LOCATION:
            location = payload[0] if len(payload) >= 1 else 0
            self.dock_location = location
            return DockLocationEvent(self.id, location)

        elif op == Op.DEVICE_ID:
            self.device_id = payload.hex()
            return None

        return None

    @property
    def face_down(self) -> bool:
        """True if the cube is flipped face-down."""
        return self.tilt[2] == 0

    def __repr__(self):
        status = "online" if self.online else "offline"
        return f"Cube(id={self.id}, {status}, tilt={self.tilt})"
