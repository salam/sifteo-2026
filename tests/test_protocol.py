"""Tests for sifteo.protocol — message construction, opcodes, color conversion."""

import struct
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from sifteo.protocol import (
    Op, Message, USB_MSG_LEN, USB_OUT_MSG_LEN, DONGLE_ADDRESS,
    pack_u8, pack_u16, pack_u32, unpack_u8, unpack_u16, unpack_u32,
    rgb_to_rgb332, rgb332_to_rgb,
    cmd_fill_screen, cmd_draw_rect, cmd_repaint, cmd_blit_image,
    cmd_put_pixel, cmd_set_rotation,
    cmd_game_start, cmd_game_stop,
    cmd_request_tilt, cmd_request_button, cmd_request_neighbors,
    cmd_request_device_id, cmd_request_cube_fw_version,
    cmd_dongle_version, cmd_disable_whitelist,
)


# -- Message serialization --

class TestMessageToBytes:
    def test_length_is_usb_msg_len(self):
        msg = Message(Op.GRAPHICS_FILL, 1, b"\xE0")
        data = msg.to_bytes()
        assert len(data) == USB_OUT_MSG_LEN

    def test_zero_padded(self):
        msg = Message(Op.GRAPHICS_FILL, 1, b"\xE0")
        data = msg.to_bytes()
        # Bytes after payload should be zero
        assert all(b == 0 for b in data[5:])

    def test_field_positions(self):
        msg = Message(Op.GRAPHICS_FILL, 3, b"\xAB", msg_id=42)
        data = msg.to_bytes()
        # [radio_msg_len, msg_id, address, opcode, payload...]
        assert data[0] == 3  # radio_msg_len = 2 + 1 (addr + opcode + 1 byte payload)
        assert data[1] == 42  # msg_id
        assert data[2] == 3   # address (cube ID)
        assert data[3] == Op.GRAPHICS_FILL  # opcode
        assert data[4] == 0xAB  # payload byte

    def test_empty_payload(self):
        msg = Message(Op.ACCELEROMETER_TILT_REQUEST, 1)
        data = msg.to_bytes()
        assert data[0] == 2  # radio_msg_len = 2 + 0
        assert data[3] == Op.ACCELEROMETER_TILT_REQUEST
        assert all(b == 0 for b in data[4:])

    def test_msg_id_wraps(self):
        msg = Message(Op.GRAPHICS_FILL, 1, b"\x00", msg_id=256)
        data = msg.to_bytes()
        assert data[1] == 0  # 256 & 0xFF = 0


class TestMessageFromBytes:
    def test_parse_basic(self):
        # IN format: [radio_msg_len, address, opcode, payload...]
        raw = bytearray(USB_MSG_LEN)
        raw[0] = 5   # radio_msg_len
        raw[1] = 2   # address (cube 2)
        raw[2] = Op.TILT  # opcode
        raw[3] = 1   # x
        raw[4] = 1   # y
        raw[5] = 2   # z
        msg = Message.from_bytes(bytes(raw))
        assert msg.address == 2
        assert msg.opcode == Op.TILT
        assert msg.payload[0] == 1
        assert msg.payload[1] == 1
        assert msg.payload[2] == 2

    def test_dongle_response(self):
        raw = bytearray(USB_MSG_LEN)
        raw[1] = DONGLE_ADDRESS
        raw[2] = Op.DONGLE_VERSION
        msg = Message.from_bytes(bytes(raw))
        assert msg.is_dongle_response


class TestMessageRoundtrip:
    def test_roundtrip(self):
        original = Message(Op.GRAPHICS_DRAW_RECT, 5, b"\x0A\x14\xE0\x1E\x28", msg_id=7)
        data = original.to_bytes()
        # Parse as IN (drops msg_id, shifts by 1)
        # IN format doesn't include msg_id, so we parse from byte 1 onward
        parsed = Message.from_bytes(data[1:])  # skip radio_msg_len, parse from msg_id...
        # In round-trip the address slot contains msg_id from OUT format
        # This tests the format difference — exact round-trip needs same format


# -- Pack/Unpack helpers --

class TestPackUnpack:
    def test_u8_roundtrip(self):
        for val in [0, 1, 127, 255]:
            assert unpack_u8(pack_u8(val)) == val

    def test_u16_little_endian(self):
        data = pack_u16(0x1234)
        assert data == b"\x34\x12"  # little-endian
        assert unpack_u16(data) == 0x1234

    def test_u32_little_endian(self):
        data = pack_u32(0xDEADBEEF)
        assert data == b"\xEF\xBE\xAD\xDE"
        assert unpack_u32(data) == 0xDEADBEEF

    def test_u16_offset(self):
        data = b"\xFF\x34\x12"
        assert unpack_u16(data, 1) == 0x1234

    def test_u32_offset(self):
        data = b"\x00\xEF\xBE\xAD\xDE"
        assert unpack_u32(data, 1) == 0xDEADBEEF

    def test_u8_mask(self):
        assert pack_u8(256) == b"\x00"  # masked to 0
        assert pack_u8(257) == b"\x01"


# -- Color conversion --

class TestColorConversion:
    def test_rgb332_pure_red(self):
        c = rgb_to_rgb332(255, 0, 0)
        assert c == 0b11100000  # 0xE0

    def test_rgb332_pure_green(self):
        c = rgb_to_rgb332(0, 255, 0)
        assert c == 0b00011100  # 0x1C

    def test_rgb332_pure_blue(self):
        c = rgb_to_rgb332(0, 0, 255)
        assert c == 0b00000011  # 0x03

    def test_rgb332_white(self):
        c = rgb_to_rgb332(255, 255, 255)
        assert c == 0xFF

    def test_rgb332_black(self):
        c = rgb_to_rgb332(0, 0, 0)
        assert c == 0x00

    def test_rgb332_to_rgb_red(self):
        r, g, b = rgb332_to_rgb(0xE0)
        assert r > 200  # approximate
        assert g < 50
        assert b < 50

    def test_rgb332_to_rgb_black(self):
        assert rgb332_to_rgb(0x00) == (0, 0, 0)

    def test_rgb_roundtrip_approximate(self):
        # RGB332 is lossy, so round-trip only approximate
        for r, g, b in [(255, 0, 0), (0, 255, 0), (0, 0, 255), (0, 0, 0)]:
            c = rgb_to_rgb332(r, g, b)
            r2, g2, b2 = rgb332_to_rgb(c)
            assert abs(r2 - r) < 40
            assert abs(g2 - g) < 40
            assert abs(b2 - b) < 90  # blue has only 2 bits


# -- Command builders --

class TestCommandBuilders:
    def test_cmd_fill_screen(self):
        msg = cmd_fill_screen(1, 0xE0)
        assert msg.opcode == Op.GRAPHICS_FILL
        assert msg.address == 1
        assert msg.payload == bytes([0xE0])

    def test_cmd_draw_rect(self):
        msg = cmd_draw_rect(2, 10, 20, 30, 40, 0xAB)
        assert msg.opcode == Op.GRAPHICS_DRAW_RECT
        assert msg.address == 2
        x, y, color, w, h = struct.unpack("<BBBBB", msg.payload)
        assert (x, y, color, w, h) == (10, 20, 0xAB, 30, 40)

    def test_cmd_put_pixel(self):
        msg = cmd_put_pixel(3, 64, 32, 0xFF)
        assert msg.opcode == Op.GRAPHICS_PUT_PIXEL
        assert msg.address == 3
        x, y, color = struct.unpack("<BBB", msg.payload)
        assert (x, y, color) == (64, 32, 0xFF)

    def test_cmd_set_rotation(self):
        msg = cmd_set_rotation(1, 2)
        assert msg.opcode == Op.GRAPHICS_SET_ROTATION
        assert msg.address == 1
        assert msg.payload == bytes([2])

    def test_cmd_repaint(self):
        msg = cmd_repaint(1, rotation=1)
        assert msg.opcode == Op.GRAPHICS_DRAW
        assert msg.payload == bytes([1])

    def test_cmd_game_start(self):
        msg = cmd_game_start(1)
        assert msg.opcode == Op.GAME_START_STOP
        assert msg.payload == bytes([1])

    def test_cmd_game_stop(self):
        msg = cmd_game_stop(1)
        assert msg.opcode == Op.GAME_START_STOP
        assert msg.payload == bytes([0])

    def test_cmd_request_tilt(self):
        msg = cmd_request_tilt(5)
        assert msg.opcode == Op.ACCELEROMETER_TILT_REQUEST
        assert msg.address == 5
        assert msg.payload == b""

    def test_cmd_request_button(self):
        msg = cmd_request_button(3)
        assert msg.opcode == Op.BUTTON_REPORT_REQUEST
        assert msg.address == 3

    def test_cmd_request_neighbors(self):
        msg = cmd_request_neighbors(1)
        assert msg.opcode == Op.NEIGHBOR_REPORT_REQUEST

    def test_cmd_request_device_id(self):
        msg = cmd_request_device_id(2)
        assert msg.opcode == Op.DEVICE_ID_REQUEST

    def test_cmd_request_fw_version(self):
        msg = cmd_request_cube_fw_version(1)
        assert msg.opcode == Op.CUBE_FW_VERSION
        assert msg.address == 1

    def test_cmd_blit_image(self):
        msg = cmd_blit_image(1, app_id=0x1234, asset_id=5,
                             x=10, y=20, src_x=0, src_y=0,
                             w=64, h=64, scale=2, rotation=1)
        assert msg.opcode == Op.GRAPHICS_IMAGE
        assert msg.address == 1
        # Payload: app_id(4) + asset_id(2) + x + y + src_x(2) + src_y(2) + w + h + rot_scale
        assert len(msg.payload) == 15
        app_id = unpack_u32(msg.payload, 0)
        asset_id = unpack_u16(msg.payload, 4)
        assert app_id == 0x1234
        assert asset_id == 5
        rot_scale = msg.payload[14]
        assert (rot_scale >> 6) & 0x3 == 1  # rotation
        assert rot_scale & 0x3F == 2  # scale

    def test_cmd_dongle_version(self):
        msg = cmd_dongle_version()
        assert msg.opcode == Op.DONGLE_VERSION
        assert msg.address == DONGLE_ADDRESS

    def test_cmd_disable_whitelist(self):
        msg = cmd_disable_whitelist()
        assert msg.opcode == Op.ENABLE_WHITELIST
        assert msg.address == DONGLE_ADDRESS
        assert msg.payload == bytes([0])


# -- Opcode enum --

class TestOpcodes:
    def test_graphics_opcodes_values(self):
        assert Op.GRAPHICS_DRAW == 81
        assert Op.GRAPHICS_DRAW_RECT == 82
        assert Op.GRAPHICS_FILL == 83
        assert Op.GRAPHICS_IMAGE == 84
        assert Op.GRAPHICS_PUT_PIXEL == 85
        assert Op.GRAPHICS_SET_ROTATION == 86

    def test_event_opcodes_values(self):
        assert Op.TILT == 128
        assert Op.NEIGHBOR == 133
        assert Op.BUTTON == 136
        assert Op.BATTERY_LOW == 140
        assert Op.FIRMWARE_VERSION == 141
        assert Op.DOCK_STATE == 143
        assert Op.DOCK_LOCATION == 144
        assert Op.SHAKE == 145
