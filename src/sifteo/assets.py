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


class AssetSyncError(Exception):
    """Raised when asset sync to a cube fails."""
    pass


@dataclass
class AssetDeclaration:
    """A single declared asset in a game's manifest."""
    name: str
    path: str           # Resolved absolute path
    asset_type: int     # ASSET_TYPE_IMAGE or ASSET_TYPE_SOUND
    asset_id: int       # Assigned integer ID

    @property
    def type_name(self) -> str:
        return "image" if self.asset_type == ASSET_TYPE_IMAGE else "sound"


@dataclass
class AssetManifest:
    """Computed asset manifest for a game, built from BaseApp class attributes."""
    app_id: int
    app_name: Optional[str]
    assets: dict  # name -> AssetDeclaration

    @property
    def image_count(self) -> int:
        return sum(1 for a in self.assets.values() if a.asset_type == ASSET_TYPE_IMAGE)

    @property
    def sound_count(self) -> int:
        return sum(1 for a in self.assets.values() if a.asset_type == ASSET_TYPE_SOUND)


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


# -- Sound Encoding --

# Cube audio format: IEEE 32-bit float, 22050 Hz, mono
SOUND_SAMPLE_RATE = 22050
SOUND_SAMPLE_WIDTH = 4  # 32-bit float = 4 bytes

# WAV format codes
_WAV_PCM = 1
_WAV_IEEE_FLOAT = 3


def encode_sound(sound_path: Union[str, Path],
                 target_rate: int = SOUND_SAMPLE_RATE) -> bytes:
    """Encode a WAV audio file to the cube's native format (float32 samples + CRC).

    Reads a WAV file, converts to mono 22050 Hz IEEE 32-bit float samples,
    and appends a CRC32.

    Supports PCM WAV (8/16/24/32-bit) and IEEE float WAV (32/64-bit).
    Input files at other sample rates are resampled via linear interpolation.

    Args:
        sound_path: Path to a WAV file.
        target_rate: Target sample rate (default 22050 Hz).

    Returns:
        Bytes ready for upload (raw float32 samples + 4-byte CRC).
    """
    sound_path = Path(sound_path)
    ext = sound_path.suffix.lower()

    if ext == ".wav":
        samples = _decode_wav(sound_path, target_rate)
    else:
        raise ValueError(f"Unsupported audio format: {ext} (only .wav is supported)")

    raw = struct.pack(f"<{len(samples)}f", *samples)
    crc = zlib.crc32(raw) & 0xFFFFFFFF
    return raw + struct.pack("<I", crc)


def _decode_wav(wav_path: Path, target_rate: int) -> list[float]:
    """Decode a WAV file to a list of mono float32 samples at target_rate."""
    with open(wav_path, "rb") as f:
        data = f.read()

    if data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        raise ValueError("Not a valid WAV file")

    # Parse chunks
    fmt_data = None
    audio_data = None
    pos = 12
    while pos < len(data) - 8:
        chunk_id = data[pos:pos + 4]
        chunk_size = struct.unpack_from("<I", data, pos + 4)[0]
        chunk_body = data[pos + 8:pos + 8 + chunk_size]
        if chunk_id == b"fmt ":
            fmt_data = chunk_body
        elif chunk_id == b"data":
            audio_data = chunk_body
        pos += 8 + chunk_size
        if pos % 2 == 1:
            pos += 1  # WAV chunks are word-aligned

    if fmt_data is None or audio_data is None:
        raise ValueError("WAV file missing fmt or data chunk")

    audio_fmt = struct.unpack_from("<H", fmt_data, 0)[0]
    channels = struct.unpack_from("<H", fmt_data, 2)[0]
    sample_rate = struct.unpack_from("<I", fmt_data, 4)[0]
    bits_per_sample = struct.unpack_from("<H", fmt_data, 14)[0]

    # Decode samples to float32
    if audio_fmt == _WAV_IEEE_FLOAT:
        if bits_per_sample == 32:
            n_samples = len(audio_data) // 4
            samples = list(struct.unpack(f"<{n_samples}f", audio_data[:n_samples * 4]))
        elif bits_per_sample == 64:
            n_samples = len(audio_data) // 8
            doubles = struct.unpack(f"<{n_samples}d", audio_data[:n_samples * 8])
            samples = [float(d) for d in doubles]
        else:
            raise ValueError(f"Unsupported IEEE float bit depth: {bits_per_sample}")
    elif audio_fmt == _WAV_PCM:
        samples = _pcm_to_float(audio_data, bits_per_sample)
    else:
        raise ValueError(f"Unsupported WAV format code: {audio_fmt}")

    # Mix to mono if stereo/multi-channel
    if channels > 1:
        mono = []
        for i in range(0, len(samples), channels):
            mono.append(sum(samples[i:i + channels]) / channels)
        samples = mono

    # Resample if needed
    if sample_rate != target_rate:
        samples = _resample(samples, sample_rate, target_rate)

    return samples


def _pcm_to_float(data: bytes, bits: int) -> list[float]:
    """Convert PCM audio data to float32 samples in [-1.0, 1.0]."""
    if bits == 8:
        # 8-bit PCM is unsigned (0-255, center at 128)
        return [(b - 128) / 128.0 for b in data]
    elif bits == 16:
        n = len(data) // 2
        raw = struct.unpack(f"<{n}h", data[:n * 2])
        return [s / 32768.0 for s in raw]
    elif bits == 24:
        samples = []
        for i in range(0, len(data) - 2, 3):
            val = data[i] | (data[i + 1] << 8) | (data[i + 2] << 16)
            if val >= 0x800000:
                val -= 0x1000000
            samples.append(val / 8388608.0)
        return samples
    elif bits == 32:
        n = len(data) // 4
        raw = struct.unpack(f"<{n}i", data[:n * 4])
        return [s / 2147483648.0 for s in raw]
    else:
        raise ValueError(f"Unsupported PCM bit depth: {bits}")


def _resample(samples: list[float], src_rate: int, dst_rate: int) -> list[float]:
    """Resample audio via linear interpolation."""
    if src_rate == dst_rate:
        return samples
    ratio = src_rate / dst_rate
    out_len = int(len(samples) * dst_rate / src_rate)
    result = []
    for i in range(out_len):
        src_pos = i * ratio
        idx = int(src_pos)
        frac = src_pos - idx
        if idx + 1 < len(samples):
            result.append(samples[idx] * (1.0 - frac) + samples[idx + 1] * frac)
        else:
            result.append(samples[min(idx, len(samples) - 1)])
    return result


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

    def _wait_for_either(self, cube_id: int, opcode: int,
                         timeout: float = 10.0) -> Optional[tuple[bytes, bool]]:
        """Wait for a message on either the response or event queue.

        Some messages (like ASSET_UPLOAD_RESULT) may arrive on either queue
        depending on firmware version. This checks both.

        Returns:
            (raw_bytes, from_response_queue) or None if timed out.
        """
        deadline = time.time() + timeout
        while time.time() < deadline:
            remaining = deadline - time.time()
            if remaining <= 0:
                break
            # Check response queue (non-blocking)
            raw = self._dongle.get_response_raw(timeout=None)
            if raw is not None and len(raw) >= 3 and raw[2] == opcode:
                return (raw, True)
            # Check event queue (short blocking wait)
            msg = self._dongle.get_event(timeout=min(remaining, 0.25))
            if msg is not None and msg.opcode == opcode:
                # Reconstruct raw bytes: [0, address, opcode, payload...]
                raw = bytes([0, msg.address, msg.opcode]) + bytes(msg.payload)
                return (raw, False)
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

        # Step 4: Wait for upload result (may arrive on either queue)
        result = self._wait_for_either(cube_id, Op.ASSET_UPLOAD_RESULT, timeout=15.0)
        if result is None:
            raise UploadError("No upload result received (timed out)")

        raw, from_response = result
        # Parse status byte. The status is at a fixed offset in the payload.
        # Legacy code: getUInt8AtOffet(rply, 6, header=2) → rply[8]
        # Response queue raw: [radio_msg_len, 0xFF, opcode, payload...] → raw[8]
        # Event queue raw (reconstructed): [0, cube_addr, opcode, payload...] → raw[8]
        # Both formats have payload starting at index 3, status at payload[5] = raw[8].
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
        result = self._wait_for_either(cube_id, Op.ASSET_DELETE_COMPLETE, timeout=timeout)
        return result is not None

    def delete_asset(self, cube_id: int, app_id: int, asset_id: int,
                     asset_type: int = ASSET_TYPE_IMAGE,
                     timeout: float = 10.0) -> bool:
        """Delete a specific asset from a cube."""
        self._dongle.send(cmd_delete_asset(cube_id, app_id, asset_id, asset_type))
        result = self._wait_for_either(cube_id, Op.ASSET_DELETE_COMPLETE, timeout=timeout)
        return result is not None

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

    def upload_sound(self, cube_id: int, app_id: int, asset_id: int,
                     sound_path: Union[str, Path],
                     progress: Optional[Callable[[int, int], None]] = None) -> bool:
        """Encode a WAV file and upload as a sound asset to a cube.

        Converts the audio to 22050 Hz mono float32 and streams to cube flash.

        Args:
            cube_id: Target cube address.
            app_id: 32-bit application ID.
            asset_id: 16-bit asset ID within the app.
            sound_path: Path to WAV file.
            progress: Optional callback(bytes_sent, total_bytes).

        Returns:
            True if upload succeeded.
        """
        data = encode_sound(sound_path)
        return self.upload_bytes(cube_id, app_id, asset_id, data,
                                 asset_type=ASSET_TYPE_SOUND, progress=progress)

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


# -- App Asset Sync --

def sync_app_assets(manager: AssetManager, cube_id: int,
                    manifest: AssetManifest) -> None:
    """Smart-sync declared assets to a cube, uploading only what's missing.

    Queries the cube's asset inventory for the app and skips assets
    that are already present. If the app doesn't exist on the cube
    or the counts don't match expectations, uploads all assets.

    Args:
        manager: AssetManager instance for dongle communication.
        cube_id: Target cube address.
        manifest: The game's asset manifest.

    Raises:
        FileNotFoundError: If a declared asset file doesn't exist.
        AssetSyncError: If an upload fails.
    """
    app_id = manifest.app_id

    # Check what's already on the cube
    existing_ids: set[int] = set()
    info = manager.query_app_info(cube_id, app_id, timeout=5.0)
    if (info
            and info.image_count == manifest.image_count
            and info.sound_count == manifest.sound_count):
        inventory = manager.query_asset_inventory(cube_id, app_id, timeout=5.0)
        existing_ids = {a.asset_id for a in inventory}

    to_upload = [a for a in manifest.assets.values()
                 if a.asset_id not in existing_ids]

    if not to_upload:
        print(f"  Cube {cube_id}: all {len(manifest.assets)} asset(s) present")
        return

    print(f"  Cube {cube_id}: uploading {len(to_upload)}/{len(manifest.assets)} asset(s)")

    for asset in sorted(to_upload, key=lambda a: a.asset_id):
        if not os.path.exists(asset.path):
            raise FileNotFoundError(
                f"Asset file not found: {asset.path} "
                f"(declared as {asset.name!r})"
            )

        print(f"    {asset.name} ({os.path.basename(asset.path)})...")
        try:
            if asset.asset_type == ASSET_TYPE_IMAGE:
                ext = os.path.splitext(asset.path)[1].lower()
                if ext == ".siftimg":
                    data = read_siftimg(asset.path)
                else:
                    data = encode_image(asset.path)
                manager.upload_bytes(cube_id, app_id, asset.asset_id, data,
                                     asset_type=ASSET_TYPE_IMAGE,
                                     progress=AssetManager.print_progress)
            else:
                data = encode_sound(asset.path)
                manager.upload_bytes(cube_id, app_id, asset.asset_id, data,
                                     asset_type=ASSET_TYPE_SOUND,
                                     progress=AssetManager.print_progress)
        except UploadError as e:
            raise AssetSyncError(
                f"Failed to upload {asset.name!r} to cube {cube_id}: {e}"
            ) from e
