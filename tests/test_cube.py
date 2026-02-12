"""Tests for sifteo.cube — event parsing, state updates, display methods."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from sifteo.protocol import (
    Op, Message, NULL_SIFTABLE_ID, rgb_to_rgb332,
)
from sifteo.cube import (
    Cube, CubeEvent,
    TiltEvent, ButtonEvent, NeighborEvent, ShakeEvent,
    BatteryLowEvent, FirmwareVersionEvent, DockStateEvent, DockLocationEvent,
    SCREEN_WIDTH, SCREEN_HEIGHT, START_TILT,
)


def make_cube():
    """Create a Cube with a mock send function that records messages."""
    sent = []
    cube = Cube(1, sent.append)
    return cube, sent


def make_event_msg(opcode, cube_id=1, payload=b""):
    """Create a Message as if received from a cube."""
    return Message(opcode, cube_id, payload)


# -- Event Parsing --

class TestTiltEvent:
    def test_parse(self):
        cube, _ = make_cube()
        msg = make_event_msg(Op.TILT, payload=bytes([0, 2, 1]))
        event = cube.handle_event(msg)
        assert isinstance(event, TiltEvent)
        assert event.cube_id == 1
        assert event.x == 0
        assert event.y == 2
        assert event.z == 1

    def test_updates_state(self):
        cube, _ = make_cube()
        assert cube.tilt == START_TILT
        cube.handle_event(make_event_msg(Op.TILT, payload=bytes([2, 0, 2])))
        assert cube.tilt == (2, 0, 2)

    def test_short_payload_returns_none(self):
        cube, _ = make_cube()
        event = cube.handle_event(make_event_msg(Op.TILT, payload=bytes([1, 2])))
        assert event is None


class TestButtonEvent:
    def test_pressed(self):
        cube, _ = make_cube()
        event = cube.handle_event(make_event_msg(Op.BUTTON, payload=bytes([1])))
        assert isinstance(event, ButtonEvent)
        assert event.pressed is True
        assert cube.button_pressed is True

    def test_released(self):
        cube, _ = make_cube()
        cube.button_pressed = True
        event = cube.handle_event(make_event_msg(Op.BUTTON, payload=bytes([0])))
        assert isinstance(event, ButtonEvent)
        assert event.pressed is False
        assert cube.button_pressed is False


class TestNeighborEvent:
    def test_add(self):
        cube, _ = make_cube()
        # Neighbor cube 2 on our side 0 (top), their side 2 (bottom)
        event = cube.handle_event(make_event_msg(Op.NEIGHBOR, payload=bytes([0, 2, 2])))
        assert isinstance(event, NeighborEvent)
        assert not event.is_removal
        assert event.my_side == 0
        assert event.neighbor_id == 2
        assert event.neighbor_side == 2
        assert cube.neighbors[0] == (2, 2)

    def test_removal(self):
        cube, _ = make_cube()
        cube.neighbors[1] = (3, 0)
        event = cube.handle_event(
            make_event_msg(Op.NEIGHBOR, payload=bytes([1, NULL_SIFTABLE_ID, 0]))
        )
        assert isinstance(event, NeighborEvent)
        assert event.is_removal
        assert cube.neighbors[1] is None


class TestShakeEvent:
    def test_parse(self):
        cube, _ = make_cube()
        event = cube.handle_event(make_event_msg(Op.SHAKE))
        assert isinstance(event, ShakeEvent)
        assert event.cube_id == 1


class TestBatteryLowEvent:
    def test_parse(self):
        cube, _ = make_cube()
        assert cube.battery_low is False
        event = cube.handle_event(make_event_msg(Op.BATTERY_LOW))
        assert isinstance(event, BatteryLowEvent)
        assert cube.battery_low is True


class TestFirmwareVersionEvent:
    def test_parse_3_bytes(self):
        cube, _ = make_cube()
        event = cube.handle_event(
            make_event_msg(Op.FIRMWARE_VERSION, payload=bytes([1, 1, 4]))
        )
        assert isinstance(event, FirmwareVersionEvent)
        assert event.version == "1.1.4"
        assert cube.firmware_version == "1.1.4"

    def test_parse_hex_fallback(self):
        cube, _ = make_cube()
        event = cube.handle_event(
            make_event_msg(Op.FIRMWARE_VERSION, payload=bytes([0xAB]))
        )
        assert isinstance(event, FirmwareVersionEvent)
        assert cube.firmware_version == "ab"

    def test_parse_empty_payload(self):
        cube, _ = make_cube()
        event = cube.handle_event(
            make_event_msg(Op.FIRMWARE_VERSION, payload=b"")
        )
        assert isinstance(event, FirmwareVersionEvent)
        assert cube.firmware_version == "unknown"


class TestDockStateEvent:
    def test_docked(self):
        cube, _ = make_cube()
        event = cube.handle_event(
            make_event_msg(Op.DOCK_STATE, payload=bytes([1]))
        )
        assert isinstance(event, DockStateEvent)
        assert event.docked is True
        assert cube.docked is True

    def test_undocked(self):
        cube, _ = make_cube()
        cube.docked = True
        event = cube.handle_event(
            make_event_msg(Op.DOCK_STATE, payload=bytes([0]))
        )
        assert isinstance(event, DockStateEvent)
        assert event.docked is False
        assert cube.docked is False


class TestDockLocationEvent:
    def test_parse(self):
        cube, _ = make_cube()
        event = cube.handle_event(
            make_event_msg(Op.DOCK_LOCATION, payload=bytes([5]))
        )
        assert isinstance(event, DockLocationEvent)
        assert event.location == 5
        assert cube.dock_location == 5


class TestUnknownOpcode:
    def test_returns_none(self):
        cube, _ = make_cube()
        # Use an opcode value that isn't handled
        event = cube.handle_event(make_event_msg(165))  # REPAINT_BEGIN
        assert event is None


class TestDeviceId:
    def test_stores_hex(self):
        cube, _ = make_cube()
        event = cube.handle_event(
            make_event_msg(Op.DEVICE_ID, payload=bytes([0xDE, 0xAD, 0xBE, 0xEF]))
        )
        assert event is None  # DEVICE_ID doesn't return an event
        assert cube.device_id == "deadbeef"


# -- Display Methods --

class TestDisplayMethods:
    def test_fill_sends_correct_msg(self):
        cube, sent = make_cube()
        cube.fill(255, 0, 0)
        assert len(sent) == 1
        msg = sent[0]
        assert msg.opcode == Op.GRAPHICS_FILL
        assert msg.address == 1
        assert msg.payload == bytes([rgb_to_rgb332(255, 0, 0)])

    def test_fill_color_sends_raw(self):
        cube, sent = make_cube()
        cube.fill_color(0xAB)
        assert sent[0].payload == bytes([0xAB])

    def test_rect_sends_correct_msg(self):
        cube, sent = make_cube()
        cube.rect(10, 20, 30, 40, 0, 255, 0)
        msg = sent[0]
        assert msg.opcode == Op.GRAPHICS_DRAW_RECT
        # Payload: x, y, color, w, h
        assert msg.payload[0] == 10  # x
        assert msg.payload[1] == 20  # y
        assert msg.payload[3] == 30  # w
        assert msg.payload[4] == 40  # h

    def test_put_pixel_sends_correct_msg(self):
        cube, sent = make_cube()
        cube.put_pixel(64, 32, 255, 255, 255)
        msg = sent[0]
        assert msg.opcode == Op.GRAPHICS_PUT_PIXEL
        assert msg.payload[0] == 64  # x
        assert msg.payload[1] == 32  # y
        assert msg.payload[2] == rgb_to_rgb332(255, 255, 255)  # color

    def test_put_pixel_color_sends_raw(self):
        cube, sent = make_cube()
        cube.put_pixel_color(10, 20, 0xE0)
        msg = sent[0]
        assert msg.opcode == Op.GRAPHICS_PUT_PIXEL
        assert msg.payload[2] == 0xE0

    def test_repaint_only_if_dirty(self):
        cube, sent = make_cube()
        cube.repaint()
        assert len(sent) == 0  # nothing drawn, nothing to repaint

        cube.fill(255, 0, 0)
        sent.clear()
        cube.repaint()
        assert len(sent) == 1
        assert sent[0].opcode == Op.GRAPHICS_DRAW

    def test_repaint_resets_draw_count(self):
        cube, sent = make_cube()
        cube.fill(255, 0, 0)
        cube.fill(0, 255, 0)
        assert cube._draw_count == 2
        cube.repaint()
        assert cube._draw_count == 0


# -- Orientation / Rotation --

class TestOrientation:
    def test_setter_sends_command(self):
        cube, sent = make_cube()
        cube.orientation = 2
        assert cube.orientation == 2
        # Should have sent a SET_ROTATION command
        rotation_msgs = [m for m in sent if m.opcode == Op.GRAPHICS_SET_ROTATION]
        assert len(rotation_msgs) == 1
        assert rotation_msgs[0].payload == bytes([2])

    def test_wraps_at_4(self):
        cube, _ = make_cube()
        cube.orientation = 5
        assert cube.orientation == 1  # 5 % 4

    def test_initial_orientation(self):
        cube, _ = make_cube()
        assert cube.orientation == 0


# -- State Properties --

class TestCubeState:
    def test_face_down(self):
        cube, _ = make_cube()
        # Default tilt is (1, 1, 2) — face up
        assert cube.face_down is False
        cube.tilt = (1, 1, 0)
        assert cube.face_down is True

    def test_initial_state(self):
        cube, _ = make_cube()
        assert cube.id == 1
        assert cube.online is True
        assert cube.battery_low is False
        assert cube.docked is False
        assert cube.dock_location is None
        assert cube.firmware_version is None
        assert cube.device_id is None
        assert cube.neighbors == [None, None, None, None]

    def test_last_seen_updated_on_event(self):
        cube, _ = make_cube()
        import time
        old_time = cube.last_seen
        time.sleep(0.01)
        cube.handle_event(make_event_msg(Op.SHAKE))
        assert cube.last_seen > old_time


# -- Sensor Queries --

class TestSensorQueries:
    def test_request_tilt(self):
        cube, sent = make_cube()
        cube.request_tilt()
        assert sent[0].opcode == Op.ACCELEROMETER_TILT_REQUEST

    def test_request_button(self):
        cube, sent = make_cube()
        cube.request_button()
        assert sent[0].opcode == Op.BUTTON_REPORT_REQUEST

    def test_request_neighbors(self):
        cube, sent = make_cube()
        cube.request_neighbors()
        assert sent[0].opcode == Op.NEIGHBOR_REPORT_REQUEST

    def test_request_device_id(self):
        cube, sent = make_cube()
        cube.request_device_id()
        assert sent[0].opcode == Op.DEVICE_ID_REQUEST

    def test_request_firmware_version(self):
        cube, sent = make_cube()
        cube.request_firmware_version()
        assert sent[0].opcode == Op.CUBE_FW_VERSION

    def test_initialize_state(self):
        cube, sent = make_cube()
        cube.initialize_state()
        opcodes = [m.opcode for m in sent]
        assert Op.ACCELEROMETER_TILT_REQUEST in opcodes
        assert Op.BUTTON_REPORT_REQUEST in opcodes
        assert Op.NEIGHBOR_REPORT_REQUEST in opcodes
        assert Op.CUBE_FW_VERSION in opcodes


# -- Game Control --

class TestGameControl:
    def test_game_start(self):
        cube, sent = make_cube()
        cube.game_start()
        assert sent[0].opcode == Op.GAME_START_STOP
        assert sent[0].payload == bytes([1])

    def test_game_stop(self):
        cube, sent = make_cube()
        cube.game_stop()
        assert sent[0].opcode == Op.GAME_START_STOP
        assert sent[0].payload == bytes([0])


# -- Repr --

class TestRepr:
    def test_cube_repr(self):
        cube, _ = make_cube()
        r = repr(cube)
        assert "Cube" in r
        assert "id=1" in r
        assert "online" in r

    def test_event_reprs(self):
        assert "TiltEvent" in repr(TiltEvent(1, 0, 1, 2))
        assert "ButtonEvent" in repr(ButtonEvent(1, True))
        assert "ShakeEvent" in repr(ShakeEvent(1))
        assert "BatteryLowEvent" in repr(BatteryLowEvent(1))
        assert "FirmwareVersionEvent" in repr(FirmwareVersionEvent(1, "1.1.4"))
        assert "DockStateEvent" in repr(DockStateEvent(1, True))
        assert "DockLocationEvent" in repr(DockLocationEvent(1, 3))
        assert "removed" in repr(NeighborEvent(1, 0, NULL_SIFTABLE_ID, 0))
        assert "neighbor=2" in repr(NeighborEvent(1, 0, 2, 2))
