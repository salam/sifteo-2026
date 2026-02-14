"""
Sifteo V1 Dongle Packet Protocol.

Defines opcodes, message formats, and packet construction/parsing
for communication with V1 cubes via the nRF24LU1+ USB dongle.

Wire format (OUT, host -> dongle, 34 bytes):
    [radio_msg_len, msg_id, address, opcode, payload..., 0-padding]
    radio_msg_len = 2 + len(payload)  (covers address + opcode + payload)
    msg_id = incrementing counter 0-255 for host<->dongle tracking

Wire format (IN, dongle -> host, 33 bytes):
    [radio_msg_len, address, opcode, payload..., 0-padding]
    address = 0xFF for dongle responses, 0-15 for cube events

Reverse-engineered from decrypted Sifteo source code (.epy files)
and confirmed by USB packet capture with probe_dongle.py.
"""

import struct
from enum import IntEnum


# -- Addressing --

DONGLE_ADDRESS = 0xFF
NULL_SIFTABLE_ID = 254
USB_IN_MSG_LEN = 33
USB_OUT_MSG_LEN = 34
# Backward-compatible alias used by RX-side code and tests.
USB_MSG_LEN = USB_IN_MSG_LEN


# -- Opcodes --

class Op(IntEnum):
    """Sifteo V1 protocol opcodes."""

    # === Incoming: dongle reporting cube presence ===

    SIFT_IDS = 1

    # === Dongle Management (host <-> dongle, address 0xFF) ===

    DONGLE_VERSION = 3
    ADD_WHITELIST = 5
    REMOVE_WHITELIST = 6
    ENABLE_WHITELIST = 7
    REQUEST_PAIRED_SIFTS = 8
    PAIRED_SIFT = 9
    UNPAIRED_SIFT = 10
    NONPAIRED_DETECTED = 11
    DONGLE_BOOTLOADER = 12
    WHITELIST_ENTRY_INFO = 16
    WHITELIST_ENTRY_COUNT = 17
    DONGLE_RF_SCAN_REPORT = 22
    DONGLE_RF_SCAN_REQUEST = 23

    # === Outgoing: Host -> Cube (Commands) ===

    # Sensor queries
    ACCELEROMETER_TILT_REQUEST = 33
    NEIGHBOR_REPORT_REQUEST = 36
    DEVICE_ID_REQUEST = 37
    BUTTON_REPORT_REQUEST = 38

    # Game/firmware control
    FIRMWARE_UPLOAD_COMPLETE = 45
    GAME_START_STOP = 46  # 0=idle, 1=game active

    # Asset management
    ASSET_UPLOAD = 56
    APP_DELETE_ALL_ASSETS = 58
    APP_DELETE_ASSET = 59
    APP_INFO_REQUEST = 60
    ASSET_INVENTORY_REQUEST = 61
    AVAILABLE_STORAGE = 62
    CUBE_FW_VERSION = 63
    ASSET_UPLOAD_HEADER = 68
    APP_LIST_REQUEST = 70

    # Graphics
    GRAPHICS_DRAW = 81          # repaint display
    GRAPHICS_DRAW_RECT = 82     # draw filled rectangle
    GRAPHICS_FILL = 83          # fill screen with color
    GRAPHICS_IMAGE = 84         # blit image to framebuffer
    GRAPHICS_PUT_PIXEL = 85     # draw single pixel
    GRAPHICS_SET_ROTATION = 86  # set display rotation

    # Asset verification/download
    ASSET_VERIFY_CRC_REQUEST = 153
    FRAME_BUFFER_DUMP_REQUEST = 157
    ASSET_DUMP_REQUEST = 160

    # === Incoming: Cube -> Host (Events) ===

    TILT = 128
    NEIGHBOR = 133
    DEVICE_ID = 135
    BUTTON = 136
    NEIGHBOR_FULL_REPORT = 137
    ASSET_INVENTORY_RESPONSE = 138
    APP_INFO_RESPONSE = 139
    BATTERY_LOW = 140
    FIRMWARE_VERSION = 141
    DOCK_STATE = 143
    DOCK_LOCATION = 144
    SHAKE = 145
    ASSET_VERIFY_CRC_RESPONSE = 154
    FRAME_BUFFER_DOWNLOAD_HEADER = 158
    FRAME_BUFFER_DOWNLOAD = 159
    ASSET_DOWNLOAD_HEADER = 161
    ASSET_DOWNLOAD = 162
    REPAINT_BEGIN = 165

    # === Dongle response codes ===

    APP_LIST_RESPONSE_HEADER = 71
    APP_LIST_RESPONSE_ITEM = 72
    ASSET_UPLOAD_RESULT = 73
    ASSET_DELETE_COMPLETE = 74


# Opcode name lookup
_OP_NAMES = {op.value: op.name for op in Op}


def op_name(code: int) -> str:
    """Get a human-readable name for an opcode."""
    return _OP_NAMES.get(code, f"UNKNOWN_{code}")


# -- Message Construction --

class Message:
    """A Sifteo protocol message.

    OUT format (host -> dongle): [radio_msg_len, msg_id, address, opcode, payload...]
    IN format  (dongle -> host): [radio_msg_len, address, opcode, payload...]

    OUT size: USB_OUT_MSG_LEN (34 bytes), zero-padded.
    IN  size: USB_IN_MSG_LEN (33 bytes).
    """

    def __init__(self, opcode: int, address: int, payload: bytes = b"", msg_id: int = 0):
        self.opcode = opcode
        self.address = address
        self.msg_id = msg_id
        self.payload = payload

    def to_bytes(self) -> bytes:
        """Serialize to 34-byte USB OUT message.

        Format: [radio_msg_len, msg_id, address, opcode, payload..., 0-padding]
        """
        buf = bytearray(USB_OUT_MSG_LEN)
        payload_len = min(len(self.payload), USB_OUT_MSG_LEN - 4)
        buf[0] = (2 + payload_len) & 0xFF   # radio_msg_len = address + opcode + payload
        buf[1] = self.msg_id & 0xFF
        buf[2] = self.address & 0xFF
        buf[3] = self.opcode & 0xFF
        buf[4:4 + payload_len] = self.payload[:payload_len]
        return bytes(buf)

    @classmethod
    def from_bytes(cls, data: bytes) -> "Message":
        """Parse a received 33-byte USB IN message.

        Format: [radio_msg_len, address, opcode, payload...]
        """
        if len(data) < 3:
            raise ValueError(f"Message too short: {len(data)} bytes")
        address = data[1]
        opcode = data[2]
        payload = bytes(data[3:])
        return cls(opcode, address, payload, msg_id=0)

    @property
    def is_dongle_response(self) -> bool:
        return self.address == DONGLE_ADDRESS

    def __repr__(self):
        name = op_name(self.opcode)
        payload_hex = self.payload[:10].hex()
        if len(self.payload) > 10:
            payload_hex += "..."
        return f"Message({name}, addr={self.address}, payload={payload_hex})"


# -- Payload Helpers (little-endian, matching original protocol) --

def pack_u8(val: int) -> bytes:
    return struct.pack("<B", val & 0xFF)

def pack_u16(val: int) -> bytes:
    return struct.pack("<H", val & 0xFFFF)

def pack_u32(val: int) -> bytes:
    return struct.pack("<I", val & 0xFFFFFFFF)

def unpack_u8(data: bytes, offset: int = 0) -> int:
    return data[offset]

def unpack_u16(data: bytes, offset: int = 0) -> int:
    return struct.unpack_from("<H", data, offset)[0]

def unpack_u32(data: bytes, offset: int = 0) -> int:
    return struct.unpack_from("<I", data, offset)[0]


# -- Dongle Command Builders --

def cmd_dongle_version() -> Message:
    """Request dongle firmware version."""
    return Message(Op.DONGLE_VERSION, DONGLE_ADDRESS)

def cmd_disable_whitelist() -> Message:
    """Disable cube whitelist filtering (required for discovery)."""
    return Message(Op.ENABLE_WHITELIST, DONGLE_ADDRESS, pack_u8(0))

def cmd_enable_whitelist() -> Message:
    """Enable cube whitelist filtering."""
    return Message(Op.ENABLE_WHITELIST, DONGLE_ADDRESS, pack_u8(1))

def cmd_request_paired_sifts() -> Message:
    """Request list of paired/known cubes from dongle."""
    return Message(Op.REQUEST_PAIRED_SIFTS, DONGLE_ADDRESS)

def cmd_request_sift_ids() -> Message:
    """Request current connected cube IDs."""
    return Message(Op.SIFT_IDS, DONGLE_ADDRESS)


# -- Cube Command Builders --

def cmd_request_tilt(cube_id: int) -> Message:
    """Request current tilt state from a cube."""
    return Message(Op.ACCELEROMETER_TILT_REQUEST, cube_id)

def cmd_request_button(cube_id: int) -> Message:
    """Request current button state from a cube."""
    return Message(Op.BUTTON_REPORT_REQUEST, cube_id)

def cmd_request_neighbors(cube_id: int) -> Message:
    """Request full neighbor report from a cube."""
    return Message(Op.NEIGHBOR_REPORT_REQUEST, cube_id)

def cmd_request_device_id(cube_id: int) -> Message:
    """Request hardware device ID from a cube."""
    return Message(Op.DEVICE_ID_REQUEST, cube_id)

def cmd_game_start(cube_id: int) -> Message:
    """Tell cube a game is starting (exit idle screen)."""
    return Message(Op.GAME_START_STOP, cube_id, pack_u8(1))

def cmd_game_stop(cube_id: int) -> Message:
    """Tell cube to return to idle screen."""
    return Message(Op.GAME_START_STOP, cube_id, pack_u8(0))

def cmd_fill_screen(cube_id: int, color_rgb8: int) -> Message:
    """Fill the cube's entire screen with an 8-bit RGB332 color."""
    return Message(Op.GRAPHICS_FILL, cube_id, pack_u8(color_rgb8))

def cmd_draw_rect(cube_id: int, x: int, y: int, w: int, h: int, color_rgb8: int) -> Message:
    """Draw a filled rectangle on the cube's screen."""
    payload = struct.pack("<BBBBB", x, y, color_rgb8, w, h)
    return Message(Op.GRAPHICS_DRAW_RECT, cube_id, payload)

def cmd_repaint(cube_id: int, rotation: int = 0) -> Message:
    """Repaint the cube's display. Call after drawing operations."""
    return Message(Op.GRAPHICS_DRAW, cube_id, pack_u8(rotation))

def cmd_blit_image(cube_id: int, app_id: int, asset_id: int,
                   x: int = 0, y: int = 0, src_x: int = 0, src_y: int = 0,
                   w: int = 128, h: int = 128, scale: int = 1, rotation: int = 0) -> Message:
    """Blit an image asset from cube flash to the framebuffer."""
    rot_scale = ((rotation & 0x3) << 6) | (scale & 0x3F)
    payload = (pack_u32(app_id) + pack_u16(asset_id) +
               struct.pack("<BB", x, y) +
               pack_u16(src_x) + pack_u16(src_y) +
               struct.pack("<BBB", w, h, rot_scale))
    return Message(Op.GRAPHICS_IMAGE, cube_id, payload)

def cmd_put_pixel(cube_id: int, x: int, y: int, color_rgb8: int) -> Message:
    """Draw a single pixel on the cube's screen."""
    payload = struct.pack("<BBB", x, y, color_rgb8)
    return Message(Op.GRAPHICS_PUT_PIXEL, cube_id, payload)


def cmd_set_rotation(cube_id: int, rotation: int) -> Message:
    """Set the cube's display rotation (0-3)."""
    return Message(Op.GRAPHICS_SET_ROTATION, cube_id, pack_u8(rotation))


def cmd_request_app_list(cube_id: int) -> Message:
    """Request list of installed apps on a cube."""
    return Message(Op.APP_LIST_REQUEST, cube_id)


def cmd_request_cube_fw_version(cube_id: int) -> Message:
    """Request firmware version from a cube."""
    return Message(Op.CUBE_FW_VERSION, cube_id)


# -- Asset Management Command Builders --

ASSET_TYPE_IMAGE = 0
ASSET_TYPE_SOUND = 1

# Upload result status codes
UPLOAD_OK = 1
UPLOAD_CRC_FAIL = 2
UPLOAD_DISK_FULL = 3
UPLOAD_MISALIGNMENT = 4

# Payload offsets for response parsing
UPLOAD_RESULT_STATUS_IDX = 6   # status byte in ASSET_UPLOAD_RESULT payload
                               # Original code: getUInt8AtOffet(rply, 6, header=2) = rply[8].
                               # C HID library strips radio_msg_len, so rply[8] = 7th data byte.
                               # Our raw format keeps radio_msg_len: payload = raw[3:], so
                               # payload[6] = raw[9] = original rply[8].
APP_INFO_IMAGES_IDX = 4        # u16 image count in APP_INFO_RESPONSE payload
APP_INFO_SOUNDS_IDX = 6        # u16 sound count in APP_INFO_RESPONSE payload
APP_INFO_BYTES_IDX = 8         # u32 byte count in APP_INFO_RESPONSE payload
ASSET_INV_ASSET_ID_IDX = 4    # u16 asset_id in ASSET_INVENTORY_RESPONSE payload
ASSET_INV_ASSET_TYPE_IDX = 6  # u8 type in ASSET_INVENTORY_RESPONSE payload
CRC_ORIG_IDX = 7              # u32 original CRC in ASSET_VERIFY_CRC_RESPONSE payload
CRC_CALC_IDX = 11             # u32 calculated CRC in ASSET_VERIFY_CRC_RESPONSE payload
# These same offsets appear in ASSET_UPLOAD_RESULT when the firmware
# includes CRC details (observed on V1 hardware).
UPLOAD_RESULT_ORIG_CRC_IDX = 7   # u32 original CRC in ASSET_UPLOAD_RESULT payload
UPLOAD_RESULT_CALC_CRC_IDX = 11  # u32 calculated CRC in ASSET_UPLOAD_RESULT payload
APP_LIST_APP_ID_IDX = 0       # u32 app_id in APP_LIST_RESPONSE_ITEM payload
FB_WIDTH_IDX = 0              # u8 width in FRAME_BUFFER_DOWNLOAD_HEADER payload
FB_HEIGHT_IDX = 1             # u8 height in FRAME_BUFFER_DOWNLOAD_HEADER payload
FB_BPP_IDX = 2                # u8 bytes-per-pixel in FRAME_BUFFER_DOWNLOAD_HEADER payload
ASSET_DL_SIZE_IDX = 0         # u32 size in ASSET_DOWNLOAD_HEADER payload
ASSET_DL_CRC_IDX = 4          # u32 CRC in ASSET_DOWNLOAD_HEADER payload


def cmd_asset_upload_header(cube_id: int, size: int, app_id: int,
                            asset_id: int, asset_type: int = ASSET_TYPE_IMAGE) -> Message:
    """Send asset upload header to initiate a transfer.

    After sending, wait ~3 seconds before sending data chunks.
    """
    payload = pack_u32(size) + pack_u32(app_id) + pack_u16(asset_id) + pack_u8(asset_type)
    return Message(Op.ASSET_UPLOAD_HEADER, cube_id, payload)


def cmd_asset_upload_chunk(cube_id: int, data: bytes, seq_id: int) -> Message:
    """Send one chunk of asset data.

    Max 28 data bytes per chunk. Format: [byte_count, data..., seq_id]
    """
    byte_count = len(data) + 1  # data bytes + seq_id byte
    payload = pack_u8(byte_count) + data + pack_u8(seq_id)
    return Message(Op.ASSET_UPLOAD, cube_id, payload)


def cmd_app_info_request(cube_id: int, app_id: int) -> Message:
    """Query asset counts (images, sounds, bytes) for an app."""
    return Message(Op.APP_INFO_REQUEST, cube_id, pack_u32(app_id))


def cmd_asset_inventory_request(cube_id: int, app_id: int, expected_count: int) -> Message:
    """Query asset inventory for an app. Returns ASSET_INVENTORY_RESPONSE per asset."""
    payload = pack_u32(app_id) + pack_u16(expected_count)
    return Message(Op.ASSET_INVENTORY_REQUEST, cube_id, payload)


def cmd_available_storage(cube_id: int) -> Message:
    """Query available storage on a cube."""
    return Message(Op.AVAILABLE_STORAGE, cube_id)


def cmd_delete_all_assets(cube_id: int, app_id: int) -> Message:
    """Delete all assets belonging to an app."""
    return Message(Op.APP_DELETE_ALL_ASSETS, cube_id, pack_u32(app_id))


def cmd_delete_asset(cube_id: int, app_id: int, asset_id: int,
                     asset_type: int = ASSET_TYPE_IMAGE) -> Message:
    """Delete a specific asset."""
    payload = pack_u32(app_id) + pack_u16(asset_id) + pack_u8(asset_type)
    return Message(Op.APP_DELETE_ASSET, cube_id, payload)


def cmd_verify_crc(cube_id: int, app_id: int, asset_id: int,
                   asset_type: int = ASSET_TYPE_IMAGE) -> Message:
    """Request CRC verification for an asset on the cube."""
    payload = pack_u32(app_id) + pack_u16(asset_id) + pack_u8(asset_type)
    return Message(Op.ASSET_VERIFY_CRC_REQUEST, cube_id, payload)


def cmd_frame_buffer_dump(cube_id: int) -> Message:
    """Request framebuffer download from a cube."""
    return Message(Op.FRAME_BUFFER_DUMP_REQUEST, cube_id)


def cmd_asset_dump_request(cube_id: int, app_id: int, asset_id: int,
                           asset_type: int = ASSET_TYPE_IMAGE) -> Message:
    """Request asset data download from a cube."""
    payload = pack_u32(app_id) + pack_u16(asset_id) + pack_u8(asset_type)
    return Message(Op.ASSET_DUMP_REQUEST, cube_id, payload)


# -- Color Utilities --

def rgb_to_rgb332(r: int, g: int, b: int) -> int:
    """Convert 24-bit RGB to 8-bit RGB332 color."""
    return ((r >> 5) << 5) | ((g >> 5) << 2) | (b >> 6)

def rgb332_to_rgb(c: int) -> tuple:
    """Convert 8-bit RGB332 to approximate 24-bit RGB tuple."""
    r = ((c >> 5) & 0x7) * 36
    g = ((c >> 2) & 0x7) * 36
    b = (c & 0x3) * 85
    return (r, g, b)
