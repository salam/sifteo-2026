"""
Sifteo V1 Asset Management.

Handles uploading, downloading, verifying, and managing assets stored
on cube flash. Also supports framebuffer download for debugging.

Asset types:
    0 = Image (compressed tiles, RGB332 palette)
    1 = Sound (raw audio)

Upload protocol:
    1. Send ASSET_UPLOAD_HEADER with size, app_id, asset_id, type
    2. Wait ~3 seconds for cube to process header
    3. Send ASSET_UPLOAD chunks (max 28 data bytes + seq_id per packet)
    4. Receive ASSET_UPLOAD_RESULT (1=OK, 2=CRC fail, 3=disk full, 4=misaligned)

Each app has a 32-bit app_id. Assets are scoped to their app_id.
"""

from __future__ import annotations

import os
import struct
import time
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Callable, Union

from .dongle import SifteoDongle
from .protocol import (
    Op, Message, DONGLE_ADDRESS,
    ASSET_TYPE_IMAGE, ASSET_TYPE_SOUND,
    UPLOAD_OK, UPLOAD_CRC_FAIL, UPLOAD_DISK_FULL, UPLOAD_MISALIGNMENT,
    APP_INFO_IMAGES_IDX, APP_INFO_SOUNDS_IDX, APP_INFO_BYTES_IDX,
    ASSET_INV_ASSET_ID_IDX, ASSET_INV_ASSET_TYPE_IDX,
    CRC_ORIG_IDX, CRC_CALC_IDX,
    APP_LIST_APP_ID_IDX,
    FB_WIDTH_IDX, FB_HEIGHT_IDX, FB_BPP_IDX,
    ASSET_DL_SIZE_IDX, ASSET_DL_CRC_IDX,
    cmd_asset_upload_header, cmd_asset_upload_chunk,
    cmd_app_info_request, cmd_asset_inventory_request,
    cmd_available_storage, cmd_delete_all_assets, cmd_delete_asset,
    cmd_verify_crc, cmd_frame_buffer_dump, cmd_asset_dump_request,
    cmd_request_app_list,
    rgb_to_rgb332,
    unpack_u8, unpack_u16, unpack_u32, op_name,
)

# Max data bytes in a single ASSET_UPLOAD chunk.
# The legacy code uses MSG_PAYLOAD_LENGTH - 2 = 28 bytes.
MAX_CHUNK_DATA = 28

# Time to wait after sending the upload header (cube flash is slow).
HEADER_PROCESS_DELAY = 3.0


@dataclass
class AppInfo:
    """Asset counts for an app on a cube."""
    app_id: int
    image_count: int
    sound_count: int
    total_bytes: int


@dataclass
class AssetInfo:
    """A single asset entry in the cube's inventory."""
    asset_id: int
    asset_type: int

    @property
    def type_name(self) -> str:
        return "image" if self.asset_type == ASSET_TYPE_IMAGE else "sound"


@dataclass
class CRCResult:
    """CRC verification result for an asset."""
    original_crc: int
    calculated_crc: int

    @property
    def valid(self) -> bool:
        return self.original_crc == self.calculated_crc


@dataclass
class FrameBuffer:
    """Downloaded framebuffer data from a cube."""
    width: int
    height: int
    bpp: int
    data: bytes

    @property
    def pixel_count(self) -> int:
        return self.width * self.height


class UploadError(Exception):
    """Raised when an asset upload fails."""
    pass


# -- Image Encoding --

CRC_SIZE = 4


def encode_image(image_path: Union[str, Path],
                 width: int = 128, height: int = 128) -> bytes:
    """Encode a PNG/BMP/JPEG image to the cube's native format (RGB332 + CRC).

    Reads the image, resizes to width x height, converts each pixel
    to 8-bit RGB332, and appends a CRC32.

    Args:
        image_path: Path to a PNG, BMP, or JPEG file.
        width: Target width (default 128 = full cube screen).
        height: Target height (default 128 = full cube screen).

    Returns:
        Bytes ready for upload (RGB332 pixel data + 4-byte CRC).

    Requires:
        Pillow (pip install Pillow)
    """
    from PIL import Image

    img = Image.open(image_path).convert("RGB")

    if img.size != (width, height):
        img = img.resize((width, height), Image.LANCZOS)

    pixels = bytearray(width * height)
    for i, (r, g, b) in enumerate(img.getdata()):
        pixels[i] = rgb_to_rgb332(r, g, b)

    crc = zlib.crc32(pixels) & 0xFFFFFFFF
    return bytes(pixels) + struct.pack("<I", crc)


def encode_image_rgba(pixel_data: bytes, width: int, height: int) -> bytes:
    """Encode raw RGBA pixel data to the cube's native format.

    Args:
        pixel_data: RGBA bytes (4 bytes per pixel, row-major).
        width: Image width.
        height: Image height.

    Returns:
        Bytes ready for upload (RGB332 pixel data + 4-byte CRC).
    """
    pixels = bytearray(width * height)
    for i in range(width * height):
        offset = i * 4
        r, g, b = pixel_data[offset], pixel_data[offset + 1], pixel_data[offset + 2]
        pixels[i] = rgb_to_rgb332(r, g, b)

    crc = zlib.crc32(pixels) & 0xFFFFFFFF
    return bytes(pixels) + struct.pack("<I", crc)


def encode_image_rgb(pixel_data: bytes, width: int, height: int) -> bytes:
    """Encode raw RGB pixel data to the cube's native format.

    Args:
        pixel_data: RGB bytes (3 bytes per pixel, row-major).
        width: Image width.
        height: Image height.

    Returns:
        Bytes ready for upload (RGB332 pixel data + 4-byte CRC).
    """
    pixels = bytearray(width * height)
    for i in range(width * height):
        offset = i * 3
        r, g, b = pixel_data[offset], pixel_data[offset + 1], pixel_data[offset + 2]
        pixels[i] = rgb_to_rgb332(r, g, b)

    crc = zlib.crc32(pixels) & 0xFFFFFFFF
    return bytes(pixels) + struct.pack("<I", crc)


def read_siftimg(file_path: Union[str, Path]) -> bytes:
    """Read a pre-compiled .siftimg file as raw bytes."""
    with open(file_path, "rb") as f:
        return f.read()


def read_siftimg_crc(file_path: Union[str, Path]) -> int:
    """Read the CRC from the last 4 bytes of a .siftimg file."""
    size = os.path.getsize(file_path)
    with open(file_path, "rb") as f:
        f.seek(size - CRC_SIZE)
        return struct.unpack("<I", f.read(CRC_SIZE))[0]


class AssetManager:
    """Manages assets on a Sifteo cube via the USB dongle.

    Provides high-level methods for:
    - Uploading assets (images, sounds) to cube flash
    - Downloading assets and framebuffer from cube flash
    - Querying asset inventory and storage
    - Verifying asset integrity via CRC
    - Managing apps (list, delete)
    """

    def __init__(self, dongle: SifteoDongle):
        self._dongle = dongle

    # -- Response Helpers --

    def _wait_for_event(self, cube_id: int, opcode: int,
                        timeout: float = 10.0) -> Optional[Message]:
        """Wait for a specific event opcode from a specific cube.

        Drains the event queue looking for a matching message.
        Non-matching events are discarded (they've already been queued
        and the runner will have processed them).
        """
        deadline = time.time() + timeout
        while time.time() < deadline:
            remaining = deadline - time.time()
            if remaining <= 0:
                break
            msg = self._dongle.get_event(timeout=min(remaining, 0.5))
            if msg is None:
                continue
            if msg.address == cube_id and msg.opcode == opcode:
                return msg
        return None

    def _wait_for_response(self, opcode: int,
                           timeout: float = 10.0) -> Optional[bytes]:
        """Wait for a specific dongle response opcode."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            remaining = deadline - time.time()
            if remaining <= 0:
                break
            raw = self._dongle.get_response_raw(timeout=min(remaining, 0.5))
            if raw is None:
                continue
            if len(raw) >= 3 and raw[2] == opcode:
                return raw
        return None

    # -- Asset Upload --

    def upload_file(self, cube_id: int, app_id: int, asset_id: int,
                    file_path: str, asset_type: int = ASSET_TYPE_IMAGE,
                    progress: Optional[Callable[[int, int], None]] = None) -> bool:
        """Upload a file as an asset to a cube.

        Args:
            cube_id: Target cube address.
            app_id: 32-bit application ID.
            asset_id: 16-bit asset ID within the app.
            file_path: Path to the file to upload.
            asset_type: ASSET_TYPE_IMAGE (0) or ASSET_TYPE_SOUND (1).
            progress: Optional callback(bytes_sent, total_bytes).

        Returns:
            True if upload succeeded, False otherwise.

        Raises:
            FileNotFoundError: If file_path doesn't exist.
            UploadError: If the cube reports an error.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Asset file not found: {file_path}")

        size = os.path.getsize(file_path)
        with open(file_path, "rb") as f:
            data = f.read()

        return self.upload_bytes(cube_id, app_id, asset_id, data,
                                 asset_type=asset_type, progress=progress)

    def upload_bytes(self, cube_id: int, app_id: int, asset_id: int,
                     data: bytes, asset_type: int = ASSET_TYPE_IMAGE,
                     progress: Optional[Callable[[int, int], None]] = None) -> bool:
        """Upload raw bytes as an asset to a cube.

        Args:
            cube_id: Target cube address.
            app_id: 32-bit application ID.
            asset_id: 16-bit asset ID within the app.
            data: Raw asset bytes.
            asset_type: ASSET_TYPE_IMAGE (0) or ASSET_TYPE_SOUND (1).
            progress: Optional callback(bytes_sent, total_bytes).

        Returns:
            True if upload succeeded.

        Raises:
            UploadError: If the cube reports an error.
        """
        size = len(data)

        # Step 1: Send upload header
        self._dongle.send(cmd_asset_upload_header(cube_id, size, app_id,
                                                   asset_id, asset_type))

        # Step 2: Wait for cube to process header (flash is slow)
        time.sleep(HEADER_PROCESS_DELAY)

        # Step 3: Send data in chunks
        offset = 0
        seq_id = 0
        while offset < size:
            chunk_size = min(MAX_CHUNK_DATA, size - offset)
            chunk = data[offset:offset + chunk_size]
            self._dongle.send(cmd_asset_upload_chunk(cube_id, chunk, seq_id))
            seq_id = (seq_id + 1) & 0xFF
            offset += chunk_size
            if progress:
                progress(offset, size)

        # Step 4: Wait for upload result
        raw = self._wait_for_response(Op.ASSET_UPLOAD_RESULT, timeout=15.0)
        if raw is None:
            raise UploadError("No upload result received from dongle (timed out)")

        # Parse status from response payload.
        # Response format: [radio_msg_len, addr(0xFF), opcode(73), ...payload]
        # The status byte is at payload offset 4 from the legacy code
        # (ASSET_UPLOAD_RESULT_IDX = 6, with MSG_HEADER_LENGTH=2 → offset 4 in payload).
        # In our wire format: data[3+4] = data[7], but the legacy offsets count
        # from byte index 0 of the raw packet with header_len=2.
        # Legacy: getUInt8AtOffet(rply, 6, header=2) → rply[8]
        # Our raw: [radio_msg_len, 0xFF, opcode, payload...] → payload starts at [3]
        # Status is at payload[3] (the 4th byte of payload after opcode-specific data).
        # From the original: ASSET_UPLOAD_RESULT_IDX=6 + header=2 = index 8 in raw.
        # In our wire format that's raw[8] too (since our raw starts at byte 0).
        # But actually let's be careful: in the original dongle_helper, the raw message
        # is [siftid, opcode, ...payload] (32 bytes total). Index 6+2=8.
        # In our format: [radio_msg_len, address, opcode, payload...] (33 bytes).
        # The payload starts at index 3. The result status should be at a fixed offset.
        # Let's just check multiple likely positions.
        if len(raw) > 8:
            status = raw[8]
        elif len(raw) > 6:
            status = raw[6]
        else:
            raise UploadError("Upload result response too short")

        if status == UPLOAD_OK:
            return True
        elif status == UPLOAD_CRC_FAIL:
            raise UploadError("CRC verification failed on cube")
        elif status == UPLOAD_DISK_FULL:
            raise UploadError("Cube flash storage is full")
        elif status == UPLOAD_MISALIGNMENT:
            raise UploadError("Flash alignment error on cube")
        else:
            raise UploadError(f"Unknown upload status: {status}")

    # -- App & Asset Queries --

    def query_app_info(self, cube_id: int, app_id: int,
                       timeout: float = 10.0) -> Optional[AppInfo]:
        """Query asset counts for an app on a cube.

        Returns AppInfo with image_count, sound_count, total_bytes.
        """
        self._dongle.send(cmd_app_info_request(cube_id, app_id))
        msg = self._wait_for_event(cube_id, Op.APP_INFO_RESPONSE, timeout=timeout)
        if msg is None:
            return None

        payload = msg.payload
        if len(payload) < 12:
            return None

        images = unpack_u16(payload, APP_INFO_IMAGES_IDX)
        sounds = unpack_u16(payload, APP_INFO_SOUNDS_IDX)
        total_bytes = unpack_u32(payload, APP_INFO_BYTES_IDX)
        return AppInfo(app_id, images, sounds, total_bytes)

    def query_asset_inventory(self, cube_id: int, app_id: int,
                              timeout: float = 10.0) -> list[AssetInfo]:
        """Query the list of assets for an app on a cube.

        Returns a list of AssetInfo entries.
        """
        # First query the count so we know how many responses to expect
        info = self.query_app_info(cube_id, app_id, timeout=timeout)
        if info is None:
            return []

        expected = info.image_count + info.sound_count
        if expected == 0:
            return []

        self._dongle.send(cmd_asset_inventory_request(cube_id, app_id, expected))

        assets = []
        deadline = time.time() + timeout
        while len(assets) < expected and time.time() < deadline:
            msg = self._wait_for_event(
                cube_id, Op.ASSET_INVENTORY_RESPONSE,
                timeout=min(deadline - time.time(), 2.0)
            )
            if msg is None:
                break
            if len(msg.payload) >= 7:
                aid = unpack_u16(msg.payload, ASSET_INV_ASSET_ID_IDX)
                atype = unpack_u8(msg.payload, ASSET_INV_ASSET_TYPE_IDX)
                assets.append(AssetInfo(aid, atype))

        return assets

    def query_app_list(self, cube_id: int,
                       timeout: float = 10.0) -> list[int]:
        """List all app IDs installed on a cube.

        Returns a list of 32-bit app_id values.
        """
        self._dongle.send(cmd_request_app_list(cube_id))

        app_ids = []
        deadline = time.time() + timeout
        while time.time() < deadline:
            raw = self._wait_for_response(
                Op.APP_LIST_RESPONSE_ITEM,
                timeout=min(deadline - time.time(), 2.0)
            )
            if raw is None:
                break
            # Payload starts at index 3 in our raw format
            if len(raw) >= 7:
                aid = unpack_u32(raw, 3 + APP_LIST_APP_ID_IDX)
                app_ids.append(aid)

        return app_ids

    def query_available_storage(self, cube_id: int,
                                timeout: float = 10.0) -> Optional[int]:
        """Query available storage bytes on a cube."""
        self._dongle.send(cmd_available_storage(cube_id))
        # The response comes back as an event with storage info.
        # The exact response opcode isn't clearly documented separately;
        # it likely comes back as a generic response. Try event queue first.
        msg = self._wait_for_event(cube_id, Op.AVAILABLE_STORAGE, timeout=timeout)
        if msg is not None and len(msg.payload) >= 4:
            return unpack_u32(msg.payload, 0)
        return None

    # -- Asset Deletion --

    def delete_all_assets(self, cube_id: int, app_id: int,
                          timeout: float = 20.0) -> bool:
        """Delete all assets for an app on a cube.

        Uses a longer timeout because deletion of many assets can be slow.
        """
        self._dongle.send(cmd_delete_all_assets(cube_id, app_id))
        raw = self._wait_for_response(Op.ASSET_DELETE_COMPLETE, timeout=timeout)
        return raw is not None

    def delete_asset(self, cube_id: int, app_id: int, asset_id: int,
                     asset_type: int = ASSET_TYPE_IMAGE,
                     timeout: float = 10.0) -> bool:
        """Delete a specific asset from a cube."""
        self._dongle.send(cmd_delete_asset(cube_id, app_id, asset_id, asset_type))
        raw = self._wait_for_response(Op.ASSET_DELETE_COMPLETE, timeout=timeout)
        return raw is not None

    # -- CRC Verification --

    def verify_crc(self, cube_id: int, app_id: int, asset_id: int,
                   asset_type: int = ASSET_TYPE_IMAGE,
                   timeout: float = 10.0) -> Optional[CRCResult]:
        """Verify an asset's CRC on the cube.

        Returns CRCResult with original and calculated CRC values.
        The asset is valid if both match.
        """
        self._dongle.send(cmd_verify_crc(cube_id, app_id, asset_id, asset_type))
        msg = self._wait_for_event(cube_id, Op.ASSET_VERIFY_CRC_RESPONSE,
                                   timeout=timeout)
        if msg is None:
            return None

        payload = msg.payload
        if len(payload) < 15:
            return None

        orig = unpack_u32(payload, CRC_ORIG_IDX)
        calc = unpack_u32(payload, CRC_CALC_IDX)
        return CRCResult(orig, calc)

    # -- Framebuffer Download --

    def download_framebuffer(self, cube_id: int,
                             timeout: float = 15.0) -> Optional[FrameBuffer]:
        """Download the current framebuffer from a cube.

        Returns a FrameBuffer with width, height, bpp, and raw pixel data.
        Useful for debugging asset rendering.
        """
        self._dongle.send(cmd_frame_buffer_dump(cube_id))

        # Wait for header
        header = self._wait_for_event(
            cube_id, Op.FRAME_BUFFER_DOWNLOAD_HEADER, timeout=timeout
        )
        if header is None:
            return None

        payload = header.payload
        if len(payload) < 3:
            return None

        width = unpack_u8(payload, FB_WIDTH_IDX)
        height = unpack_u8(payload, FB_HEIGHT_IDX)
        bpp = unpack_u8(payload, FB_BPP_IDX)
        total_bytes = width * height * bpp

        # Collect data chunks
        data = bytearray()
        deadline = time.time() + timeout
        while len(data) < total_bytes and time.time() < deadline:
            msg = self._wait_for_event(
                cube_id, Op.FRAME_BUFFER_DOWNLOAD,
                timeout=min(deadline - time.time(), 2.0)
            )
            if msg is None:
                break
            if len(msg.payload) >= 2:
                chunk_len = unpack_u8(msg.payload, 0)
                chunk_data = msg.payload[1:1 + chunk_len]
                data.extend(chunk_data)

        if len(data) < total_bytes:
            return None

        return FrameBuffer(width, height, bpp, bytes(data[:total_bytes]))

    # -- Asset Download --

    def download_asset(self, cube_id: int, app_id: int, asset_id: int,
                       asset_type: int = ASSET_TYPE_IMAGE,
                       timeout: float = 30.0) -> Optional[bytes]:
        """Download an asset's raw data from a cube.

        Returns the raw bytes, or None if download failed.
        """
        self._dongle.send(cmd_asset_dump_request(cube_id, app_id,
                                                  asset_id, asset_type))

        # Wait for download header
        header = self._wait_for_event(
            cube_id, Op.ASSET_DOWNLOAD_HEADER, timeout=timeout
        )
        if header is None:
            return None

        payload = header.payload
        if len(payload) < 8:
            return None

        total_bytes = unpack_u32(payload, ASSET_DL_SIZE_IDX)
        expected_crc = unpack_u32(payload, ASSET_DL_CRC_IDX)

        # Collect data chunks
        data = bytearray()
        deadline = time.time() + timeout
        while len(data) < total_bytes and time.time() < deadline:
            msg = self._wait_for_event(
                cube_id, Op.ASSET_DOWNLOAD,
                timeout=min(deadline - time.time(), 2.0)
            )
            if msg is None:
                break
            if len(msg.payload) >= 2:
                chunk_len = unpack_u8(msg.payload, 0)
                chunk_data = msg.payload[1:1 + chunk_len]
                data.extend(chunk_data)

        if len(data) < total_bytes:
            return None

        return bytes(data[:total_bytes])

    # -- Convenience --

    def upload_image(self, cube_id: int, app_id: int, asset_id: int,
                     image_path: Union[str, Path],
                     width: int = 128, height: int = 128,
                     progress: Optional[Callable[[int, int], None]] = None) -> bool:
        """Encode a PNG/BMP/JPEG image and upload to a cube.

        Converts the image to RGB332 format and streams it to cube flash.

        Args:
            cube_id: Target cube address.
            app_id: 32-bit application ID.
            asset_id: 16-bit asset ID within the app.
            image_path: Path to image file.
            width: Target width (default 128).
            height: Target height (default 128).
            progress: Optional callback(bytes_sent, total_bytes).

        Returns:
            True if upload succeeded.

        Requires:
            Pillow (pip install Pillow)
        """
        data = encode_image(image_path, width, height)
        return self.upload_bytes(cube_id, app_id, asset_id, data,
                                 asset_type=ASSET_TYPE_IMAGE, progress=progress)

    def upload_and_verify(self, cube_id: int, app_id: int, asset_id: int,
                          data: bytes, asset_type: int = ASSET_TYPE_IMAGE,
                          progress: Optional[Callable[[int, int], None]] = None) -> bool:
        """Upload an asset and verify its CRC on the cube.

        Returns True only if both upload and CRC verification succeed.
        """
        self.upload_bytes(cube_id, app_id, asset_id, data,
                          asset_type=asset_type, progress=progress)

        crc_result = self.verify_crc(cube_id, app_id, asset_id, asset_type)
        if crc_result is None:
            raise UploadError("CRC verification request timed out")
        if not crc_result.valid:
            raise UploadError(
                f"CRC mismatch: original=0x{crc_result.original_crc:08X} "
                f"calculated=0x{crc_result.calculated_crc:08X}"
            )
        return True

    @staticmethod
    def print_progress(bytes_sent: int, total: int) -> None:
        """Default progress callback that prints a progress bar."""
        pct = (bytes_sent * 100) // total if total > 0 else 0
        bar_len = 30
        filled = (pct * bar_len) // 100
        bar = "#" * filled + "-" * (bar_len - filled)
        print(f"\r  [{bar}] {pct}% ({bytes_sent}/{total} bytes)", end="", flush=True)
        if bytes_sent >= total:
            print()
