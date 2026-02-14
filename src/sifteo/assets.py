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

Legacy `.siftapp` binaries are also supported as opaque payload installs.
"""

from __future__ import annotations

import logging
import os
import io
import json
import struct
import subprocess
import tempfile
import time
import zlib
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Callable, Union, Literal

logger = logging.getLogger(__name__)

from .dongle import SifteoDongle
from .protocol import (
    USB_OUT_MSG_LEN,
    Op, Message, DONGLE_ADDRESS,
    ASSET_TYPE_IMAGE, ASSET_TYPE_SOUND,
    UPLOAD_OK, UPLOAD_CRC_FAIL, UPLOAD_DISK_FULL, UPLOAD_MISALIGNMENT,
    UPLOAD_RESULT_STATUS_IDX,
    UPLOAD_RESULT_ORIG_CRC_IDX, UPLOAD_RESULT_CALC_CRC_IDX,
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
    cmd_request_app_list, cmd_game_start,
    rgb_to_rgb332,
    unpack_u8, unpack_u16, unpack_u32, op_name,
)

# Max data bytes in a single ASSET_UPLOAD chunk.
#
# In this transport implementation, `Message.to_bytes()` can carry at most
# `USB_OUT_MSG_LEN - 4` payload bytes (len/msg_id/address/opcode envelope).
# Upload chunk payload adds 2 bytes of overhead (`byte_count` + `seq_id`),
# so the safe data budget is:
#   MAX_CHUNK_DATA = (USB_OUT_MSG_LEN - 4) - 2 = USB_OUT_MSG_LEN - 6
#
# With USB_OUT_MSG_LEN=34 this yields 28 bytes, matching legacy helpers.
MAX_CHUNK_DATA = USB_OUT_MSG_LEN - 6

# Time to wait after sending the upload header (cube flash is slow).
HEADER_PROCESS_DELAY = 3.0

# Legacy .siftapp package markers (from preserved Siftrunner bundles).
SIFTAPP_HEADER_SIZE = 16
SIFTAPP_MAGIC_PREFIX = b"\x5D\xB9\x5E\xCC\x86\x2B\x75\x0E"
SIFTAPP_MAGIC_SUFFIX = b"\x44\xAE\x26\xFC"
SIFTAPP_TOKEN_OFFSET = 8
SIFTAPP_INTERNAL_ID_OFFSET = 10

# Legacy SiftRunner AppPackager AES key/IV words.
# Decryption expects 32-bit word byte-swapping on input/output.
_APPPACKAGER_KEY_WORDS = (
    0x2BF0510B,
    0x559C91B1,
    0x9DCC27F9,
    0xD727C08A,
)
_APPPACKAGER_IV_WORDS = (
    0x00010203,
    0x04050607,
    0x08090A0B,
    0x0C0D0E0F,
)


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


@dataclass
class UploadResult:
    """Result of an asset upload attempt, including CRC details from firmware."""
    status: int
    status_idx: int
    original_crc: Optional[int] = None
    calculated_crc: Optional[int] = None

    @property
    def ok(self) -> bool:
        return self.status == UPLOAD_OK

    @property
    def crc_fail(self) -> bool:
        return self.status == UPLOAD_CRC_FAIL


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


@dataclass
class SiftAppHeader:
    """Best-effort parsed metadata from a legacy `.siftapp` header."""

    valid: bool
    token: Optional[int] = None
    internal_id: Optional[int] = None


@dataclass
class SiftAppInstallResult:
    """Result metadata for a `.siftapp` install operation."""

    app_id: int
    asset_id: int
    bytes_uploaded: int
    app_id_source: Literal["explicit", "header", "manifest_dev_app_id", "filename_crc32"]
    payload_shape: Literal["container", "body"]
    install_mode: Literal["opaque", "bundle"]
    asset_count: int
    header: SiftAppHeader


@dataclass
class SiftBundleAsset:
    """Single image asset extracted from a .sftbndl container."""

    name: str
    asset_id: int
    marker: Literal["C", "R"]
    width: int
    height: int
    payload: bytes


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


def read_siftapp(file_path: Union[str, Path]) -> bytes:
    """Read a legacy `.siftapp` bundle file as raw bytes."""
    with open(file_path, "rb") as f:
        return f.read()


def _has_valid_trailing_crc(data: bytes) -> bool:
    """Return True if data ends with CRC32(data[:-4]) in little-endian."""
    if len(data) < CRC_SIZE:
        return False
    expected = struct.unpack_from("<I", data, len(data) - CRC_SIZE)[0]
    actual = zlib.crc32(data[:-CRC_SIZE]) & 0xFFFFFFFF
    return expected == actual


def ensure_trailing_crc(data: bytes) -> bytes:
    """Ensure payload has a valid trailing CRC expected by cube assets."""
    if _has_valid_trailing_crc(data):
        return data
    crc = zlib.crc32(data) & 0xFFFFFFFF
    return data + struct.pack("<I", crc)


def align4(data: bytes) -> bytes:
    """Pad payload with zero bytes to a 4-byte boundary."""
    pad = (-len(data)) % 4
    if pad == 0:
        return data
    return data + (b"\x00" * pad)


def parse_siftapp_header(data: bytes) -> SiftAppHeader:
    """Parse the fixed 16-byte legacy `.siftapp` header if present.

    Notes:
        - This is a best-effort parser for preserved Sifteo bundle files.
        - `internal_id` is an inferred app identifier byte used by old bundles.
    """
    if len(data) < SIFTAPP_HEADER_SIZE:
        return SiftAppHeader(valid=False)

    if not data.startswith(SIFTAPP_MAGIC_PREFIX):
        return SiftAppHeader(valid=False)

    if data[12:16] != SIFTAPP_MAGIC_SUFFIX:
        return SiftAppHeader(valid=False)

    token = struct.unpack_from("<I", data, SIFTAPP_TOKEN_OFFSET)[0]
    internal_id = data[SIFTAPP_INTERNAL_ID_OFFSET]
    return SiftAppHeader(valid=True, token=token, internal_id=internal_id)


def extract_siftapp_payload(
    data: bytes,
    payload_shape: Literal["container", "body"] = "container",
) -> bytes:
    """Extract upload payload bytes from a `.siftapp` container.

    Shapes:
        - container: upload full file bytes.
        - body: strip the 16-byte legacy container header.
    """
    if payload_shape == "container":
        return data
    if payload_shape != "body":
        raise ValueError(
            "payload_shape must be 'container' or 'body', got "
            f"{payload_shape!r}"
        )
    header = parse_siftapp_header(data)
    if not header.valid:
        raise ValueError(
            "payload_shape='body' requires a valid .siftapp header"
        )
    if len(data) <= SIFTAPP_HEADER_SIZE:
        raise ValueError("Invalid .siftapp: no body payload after header")
    return data[SIFTAPP_HEADER_SIZE:]


def _swap_u32_words(data: bytes) -> bytes:
    """Swap byte order within each 32-bit word."""
    if len(data) % 4 != 0:
        raise ValueError("Data length must be a multiple of 4 for word-swap")
    out = bytearray(len(data))
    for i in range(0, len(data), 4):
        out[i:i + 4] = data[i:i + 4][::-1]
    return bytes(out)


def _strip_pkcs7_padding(data: bytes) -> bytes:
    """Strip PKCS7 padding when present; otherwise return unchanged."""
    if not data:
        return data
    pad = data[-1]
    if 1 <= pad <= 16 and data.endswith(bytes([pad]) * pad):
        return data[:-pad]
    return data


def decrypt_legacy_siftapp(data: bytes) -> bytes:
    """Decrypt a legacy `.siftapp` payload to its ZIP bytes."""
    key = b"".join(struct.pack(">I", w) for w in _APPPACKAGER_KEY_WORDS)
    iv = b"".join(struct.pack(">I", w) for w in _APPPACKAGER_IV_WORDS)
    swapped_in = _swap_u32_words(data)

    with tempfile.TemporaryDirectory(prefix="sifteo_siftapp_") as td:
        in_path = Path(td) / "cipher.bin"
        out_path = Path(td) / "plain.bin"
        in_path.write_bytes(swapped_in)
        try:
            subprocess.run(
                [
                    "openssl",
                    "enc",
                    "-aes-128-cfb",
                    "-d",
                    "-nopad",
                    "-K",
                    key.hex(),
                    "-iv",
                    iv.hex(),
                    "-in",
                    str(in_path),
                    "-out",
                    str(out_path),
                ],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except FileNotFoundError as exc:
            raise ValueError(
                "openssl is required to decrypt legacy .siftapp files"
            ) from exc
        except subprocess.CalledProcessError as exc:
            raise ValueError(
                "Failed to decrypt .siftapp with legacy AppPackager cipher"
            ) from exc
        plain = out_path.read_bytes()

    swapped_out = _swap_u32_words(plain)
    return _strip_pkcs7_padding(swapped_out)


def _parse_manifest_dev_app_id(raw: object) -> Optional[int]:
    """Parse manifest devAppID values that may be int or string."""
    if isinstance(raw, int):
        return raw & 0xFFFFFFFF
    if isinstance(raw, str):
        s = raw.strip()
        if s.isdigit():
            return int(s, 10) & 0xFFFFFFFF
    return None


def parse_siftbndl(data: bytes, names: list[str]) -> list[SiftBundleAsset]:
    """Parse a legacy `.sftbndl` image container."""
    if len(data) < 3 or data[0] != ord("N"):
        raise ValueError("Invalid .sftbndl header (missing magic 'N')")

    count = struct.unpack_from("<H", data, 1)[0]
    if count <= 0:
        raise ValueError("Invalid .sftbndl: asset count is zero")
    if len(names) != count:
        raise ValueError(
            "Index entry count does not match .sftbndl count "
            f"({len(names)} != {count})"
        )

    header_bytes = 3 + (count * 4)
    if len(data) < header_bytes:
        raise ValueError("Invalid .sftbndl: offset table truncated")

    offsets = [struct.unpack_from("<I", data, 3 + i * 4)[0] for i in range(count)]
    assets: list[SiftBundleAsset] = []
    for i, start in enumerate(offsets):
        end = offsets[i + 1] if (i + 1) < len(offsets) else len(data)
        if start < header_bytes or start >= len(data):
            raise ValueError(
                f"Invalid .sftbndl: offset {start} out of range for asset {i}"
            )
        if end <= start or end > len(data):
            raise ValueError(
                f"Invalid .sftbndl: bad asset bounds {start}:{end} for asset {i}"
            )
        chunk = data[start:end]
        if len(chunk) < 5:
            raise ValueError(f"Invalid .sftbndl: asset {i} chunk too short")

        marker_byte = chunk[0]
        if marker_byte == ord("C"):
            marker: Literal["C", "R"] = "C"
        elif marker_byte == ord("R"):
            marker = "R"
        else:
            raise ValueError(
                f"Invalid .sftbndl: unknown asset marker 0x{marker_byte:02X}"
            )

        width = struct.unpack_from("<H", chunk, 1)[0]
        height = struct.unpack_from("<H", chunk, 3)[0]
        assets.append(
            SiftBundleAsset(
                name=names[i],
                asset_id=i,
                marker=marker,
                width=width,
                height=height,
                payload=chunk,
            )
        )
    return assets


def extract_siftapp_bundle_assets(
    container_bytes: bytes,
) -> tuple[Optional[str], Optional[int], list[SiftBundleAsset]]:
    """Extract installable image assets from a legacy `.siftapp` container."""
    decrypted = decrypt_legacy_siftapp(container_bytes)
    if not zipfile.is_zipfile(io.BytesIO(decrypted)):
        raise ValueError("Decrypted .siftapp payload is not a valid ZIP archive")

    with zipfile.ZipFile(io.BytesIO(decrypted)) as zf:
        manifest_candidates = [n for n in zf.namelist() if n.endswith("manifest.json")]
        if not manifest_candidates:
            raise ValueError("No manifest.json found in decrypted .siftapp bundle")
        manifest_path = manifest_candidates[0]

        manifest_data = json.loads(
            zf.read(manifest_path).decode("utf-8", errors="replace")
        )
        app_meta = manifest_data.get("app", {}) if isinstance(manifest_data, dict) else {}
        title = app_meta.get("title") if isinstance(app_meta, dict) else None
        dev_app_id = (
            _parse_manifest_dev_app_id(app_meta.get("devAppID"))
            if isinstance(app_meta, dict)
            else None
        )
        images_path = (
            str(app_meta.get("imagesPath"))
            if isinstance(app_meta, dict) and app_meta.get("imagesPath")
            else "assets/images"
        ).strip().strip("/")

        root_dir = manifest_path.rsplit("/", 1)[0] if "/" in manifest_path else ""
        expected_prefix = f"{root_dir}/{images_path}/".lower() if root_dir else f"{images_path}/".lower()

        def _is_in_images_dir(path: str) -> bool:
            return path.lower().startswith(expected_prefix)

        index_candidates = [
            n for n in zf.namelist()
            if n.endswith("_siftbndl_index.txt") and _is_in_images_dir(n)
        ]
        bundle_candidates = [
            n for n in zf.namelist()
            if n.endswith(".sftbndl") and _is_in_images_dir(n)
        ]
        # Fallback for odd manifests with non-matching imagesPath casing.
        if not index_candidates:
            index_candidates = [n for n in zf.namelist() if n.endswith("_siftbndl_index.txt")]
        if not bundle_candidates:
            bundle_candidates = [n for n in zf.namelist() if n.endswith(".sftbndl")]

        if not index_candidates or not bundle_candidates:
            raise ValueError("No image bundle/index files found in decrypted .siftapp")

        index_path = index_candidates[0]
        bundle_path = bundle_candidates[0]

        index_lines = [
            ln.strip()
            for ln in zf.read(index_path).decode("utf-8", errors="replace").splitlines()
            if ln.strip()
        ]
        bundle_data = zf.read(bundle_path)
        assets = parse_siftbndl(bundle_data, index_lines)
        if not assets:
            raise ValueError("No assets parsed from .sftbndl bundle")
        return title if isinstance(title, str) else None, dev_app_id, assets


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

    @staticmethod
    def _decode_upload_status(payload: bytes) -> tuple[int, int]:
        """Decode upload status from firmware-variant payload layouts.

        The authoritative offset is UPLOAD_RESULT_STATUS_IDX (payload[6]),
        derived from the original SiftRunner C HID library format where
        getUInt8AtOffet(rply, 6, header=2) reads rply[8] = our payload[6].

        Some firmware or queue-path variants shift the status byte; we
        fall back to nearby offsets when the primary doesn't hold a valid
        status code.

        Returns (status, payload_index).
        """
        valid = {UPLOAD_OK, UPLOAD_CRC_FAIL, UPLOAD_DISK_FULL, UPLOAD_MISALIGNMENT}
        candidate_indices = (
            UPLOAD_RESULT_STATUS_IDX,  # payload[6]: authoritative original offset
            7,                         # observed event-queue variant
            5,                         # adjacent offset (off-by-one guard)
            4,
            0,
        )
        for idx in candidate_indices:
            if idx < len(payload):
                status = payload[idx]
                if status in valid:
                    if idx != UPLOAD_RESULT_STATUS_IDX:
                        logger.warning(
                            "Upload status found at payload[%d] instead of "
                            "expected payload[%d] — firmware variant?",
                            idx, UPLOAD_RESULT_STATUS_IDX,
                        )
                    return status, idx
        raise UploadError(
            "Unknown upload status layout: "
            f"payload[{len(payload)}]={payload[:16].hex()}"
        )

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

    def _drain_response_queue(self, limit: int = 2048) -> int:
        """Drop stale dongle-response packets and return count removed.

        Upload writes now use per-packet ACKs from the response queue. Any
        stale packets left by prior operations can be mistaken as ACKs, so we
        clear pending responses before starting a new upload transaction.
        """
        drained = 0
        while drained < limit:
            raw = self._dongle.get_response_raw(timeout=None)
            if raw is None:
                break
            drained += 1
        return drained

    def _drain_event_queue(self, limit: int = 2048) -> int:
        """Drop stale event packets and return count removed."""
        drained = 0
        while drained < limit:
            msg = self._dongle.get_event(timeout=None)
            if msg is None:
                break
            drained += 1
        return drained

    def _drain_all_queues(self) -> tuple[int, int]:
        """Drop stale packets from both response and event queues."""
        return self._drain_response_queue(), self._drain_event_queue()

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

    def _upload_raw(self, cube_id: int, app_id: int, asset_id: int,
                    data: bytes, asset_type: int = ASSET_TYPE_IMAGE,
                    progress: Optional[Callable[[int, int], None]] = None,
                    ) -> UploadResult:
        """Low-level upload that returns the full UploadResult.

        Handles the protocol steps (game_start, header, chunks, result)
        and returns the parsed result including CRC values from firmware.
        """
        size = len(data)

        # Put cube into game/feedback mode before asset transfer.
        self._dongle.send(cmd_game_start(cube_id), wait_for_ack=True)
        time.sleep(0.05)

        # Drop stale responses so write ACK parsing starts clean.
        self._drain_response_queue()

        # Step 1: Send upload header.
        self._dongle.send(
            cmd_asset_upload_header(cube_id, size, app_id, asset_id, asset_type),
            wait_for_ack=True,
        )

        # Step 2: Wait for cube to process header (flash is slow).
        time.sleep(HEADER_PROCESS_DELAY)

        # Step 3: Send data in chunks.
        offset = 0
        seq_id = 0
        while offset < size:
            chunk_size = min(MAX_CHUNK_DATA, size - offset)
            chunk = data[offset:offset + chunk_size]
            self._dongle.send(
                cmd_asset_upload_chunk(cube_id, chunk, seq_id),
                wait_for_ack=True,
            )
            seq_id = (seq_id + 1) & 0xFF
            offset += chunk_size
            if progress:
                progress(offset, size)

        # Step 4: Wait for upload result (may arrive on either queue).
        result = self._wait_for_either(cube_id, Op.ASSET_UPLOAD_RESULT, timeout=15.0)
        if result is None:
            raise UploadError("No upload result received (timed out)")

        raw, _from_response = result
        logger.debug(
            "ASSET_UPLOAD_RESULT raw[%d]: %s (queue=%s)",
            len(raw), raw[:20].hex(),
            "response" if _from_response else "event",
        )
        payload = raw[3:] if len(raw) > 3 else b""
        if not payload:
            raise UploadError(
                f"Upload result too short ({len(raw)} bytes, "
                f"payload={payload.hex()})"
            )

        status, status_idx = self._decode_upload_status(payload)

        # Extract CRC values from the upload result payload.
        #
        # The CRC fields follow immediately after the status byte:
        #   status_idx + 1 : u32 original CRC (what the cube found in the data)
        #   status_idx + 5 : u32 calculated CRC (what the cube computed)
        #
        # Previously we used fixed offsets (payload[7] and payload[11]),
        # which only worked when status landed at the expected payload[6].
        # When the status shifts to payload[7] (event-queue variant), the
        # fixed offsets read garbage that includes the status byte itself
        # (e.g. orig=0x02XXXXXX where 0x02 is the CRC_FAIL status code).
        original_crc = None
        calculated_crc = None
        orig_crc_idx = status_idx + 1
        calc_crc_idx = status_idx + 5
        if len(payload) >= calc_crc_idx + 4:
            original_crc = unpack_u32(payload, orig_crc_idx)
            calculated_crc = unpack_u32(payload, calc_crc_idx)
            logger.debug(
                "Upload result CRCs: original=0x%08X calculated=0x%08X "
                "(at payload[%d] and payload[%d], status at payload[%d])",
                original_crc, calculated_crc,
                orig_crc_idx, calc_crc_idx, status_idx,
            )

        return UploadResult(
            status=status,
            status_idx=status_idx,
            original_crc=original_crc,
            calculated_crc=calculated_crc,
        )

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
        result = self._upload_raw(
            cube_id, app_id, asset_id, data,
            asset_type=asset_type, progress=progress,
        )
        if result.ok:
            return True

        status_details = f"status={result.status} at payload[{result.status_idx}]"
        if result.original_crc is not None:
            status_details += (
                f", orig_crc=0x{result.original_crc:08X}"
                f", calc_crc=0x{result.calculated_crc:08X}"
            )

        if result.crc_fail:
            raise UploadError(f"CRC verification failed on cube ({status_details})")
        elif result.status == UPLOAD_DISK_FULL:
            raise UploadError(f"Cube flash storage is full ({status_details})")
        elif result.status == UPLOAD_MISALIGNMENT:
            raise UploadError(f"Flash alignment error on cube ({status_details})")
        else:
            raise UploadError(f"Unknown upload status ({status_details})")

    def upload_bytes_learn_crc(
        self, cube_id: int, app_id: int, asset_id: int,
        data: bytes, asset_type: int = ASSET_TYPE_IMAGE,
        progress: Optional[Callable[[int, int], None]] = None,
    ) -> bool:
        """Upload asset data using a two-pass CRC-learning strategy.

        The cube firmware uses a proprietary CRC algorithm.  When the data
        does not already carry valid trailing CRC bytes, this method:

        1. **Probe pass**: uploads ``data`` padded with 4 zero bytes as a
           dummy CRC.  The cube stores the data but reports CRC_FAIL.
        2. **Learn**: queries the cube via ``verify_crc`` to read back the
           cube's computed CRC for the stored data.
        3. **Delete** the failed probe asset.
        4. **Final pass**: re-uploads ``data`` with the correct CRC appended.

        If the first upload already succeeds (data already has valid CRC),
        the subsequent steps are skipped.

        Returns True on success.
        Raises UploadError if the CRC cannot be learned or the re-upload
        still fails.
        """
        # Ensure data is 4-byte aligned before appending CRC probe.
        aligned_data = align4(data)

        # Probe pass: append 4 zero bytes as dummy CRC.
        probe_data = aligned_data + b"\x00\x00\x00\x00"
        probe_result = self._upload_raw(
            cube_id, app_id, asset_id, probe_data,
            asset_type=asset_type, progress=progress,
        )

        if probe_result.ok:
            return True

        if not probe_result.crc_fail:
            raise UploadError(
                f"Probe upload failed with non-CRC error "
                f"(status={probe_result.status})"
            )

        # Drain both queues to clear stale responses before verify_crc.
        self._drain_all_queues()

        # Learn the CRC via verify_crc.  The cube stores the data even on
        # CRC_FAIL, so verify_crc returns the CRC the cube computed over the
        # body and the dummy CRC we appended.
        learned_crc = None
        time.sleep(0.5)  # short settle time after failed upload
        crc_check = self.verify_crc(cube_id, app_id, asset_id,
                                     asset_type, timeout=10.0)
        if crc_check is not None:
            learned_crc = crc_check.calculated_crc
            logger.info(
                "verify_crc learned CRC 0x%08X for asset %d "
                "(stored_crc=0x%08X, valid=%s)",
                learned_crc, asset_id,
                crc_check.original_crc, crc_check.valid,
            )
            print(
                f"    CRC learned via verify: 0x{learned_crc:08X} "
                f"(stored=0x{crc_check.original_crc:08X})"
            )

        if learned_crc is None:
            raise UploadError(
                "CRC-learning failed: verify_crc returned no data after "
                "probe upload (cube may not store assets on CRC_FAIL)"
            )

        # Delete the failed probe asset so the re-upload slot is clean.
        self.delete_asset(cube_id, app_id, asset_id, asset_type, timeout=10.0)
        time.sleep(0.5)

        # Drain all queues again before the re-upload.
        self._drain_all_queues()

        # Final pass: append the learned CRC.
        final_data = aligned_data + struct.pack("<I", learned_crc)
        final_result = self._upload_raw(
            cube_id, app_id, asset_id, final_data,
            asset_type=asset_type, progress=progress,
        )

        if final_result.ok:
            print(f"    CRC re-upload: OK")
            return True

        raise UploadError(
            f"CRC-learning re-upload failed "
            f"(status={final_result.status}, "
            f"learned_crc=0x{learned_crc:08X})"
        )

    def install_siftapp(self, cube_id: int,
                        siftapp_path: Union[str, Path],
                        app_id: Optional[int] = None,
                        prefer_header_app_id: bool = False,
                        install_mode: Literal["auto", "bundle", "opaque"] = "auto",
                        payload_shape: Literal["container", "body"] = "container",
                        payload_crc_mode: Literal["append", "none", "learn"] = "none",
                        asset_id: int = 0,
                        asset_type: int = ASSET_TYPE_IMAGE,
                        progress: Optional[Callable[[int, int], None]] = None
                        ) -> SiftAppInstallResult:
        """Install a legacy `.siftapp` on a cube.

        Modes:
            - bundle: decrypt+unpack `.siftapp`, extract `.sftbndl` image assets,
                      and upload each image as a separate cube asset.
            - opaque: upload container bytes directly as one asset (legacy fallback).
            - auto: try bundle mode first, then fall back to opaque on parse/decrypt
                    failures.
        """
        path = Path(siftapp_path)
        if not path.exists():
            raise FileNotFoundError(f".siftapp file not found: {path}")

        container_bytes = read_siftapp(path)
        header = parse_siftapp_header(container_bytes)

        if payload_crc_mode not in {"append", "none", "learn"}:
            raise ValueError(
                "payload_crc_mode must be 'append', 'none', or 'learn', got "
                f"{payload_crc_mode!r}"
            )
        if install_mode not in {"auto", "bundle", "opaque"}:
            raise ValueError(
                "install_mode must be 'auto', 'bundle', or 'opaque', got "
                f"{install_mode!r}"
            )

        def _resolve_app_id(
            manifest_dev_app_id: Optional[int] = None,
        ) -> tuple[int, Literal["explicit", "header", "manifest_dev_app_id", "filename_crc32"]]:
            if app_id is not None:
                return app_id & 0xFFFFFFFF, "explicit"
            if prefer_header_app_id and header.valid and header.internal_id is not None:
                return header.internal_id & 0xFFFFFFFF, "header"
            if manifest_dev_app_id is not None:
                return manifest_dev_app_id & 0xFFFFFFFF, "manifest_dev_app_id"
            return zlib.crc32(path.stem.encode("utf-8")) & 0xFFFFFFFF, "filename_crc32"

        extracted_assets: Optional[list[SiftBundleAsset]] = None
        manifest_dev_app_id: Optional[int] = None
        if install_mode in {"auto", "bundle"}:
            try:
                _title, manifest_dev_app_id, extracted_assets = extract_siftapp_bundle_assets(
                    container_bytes
                )
            except ValueError:
                if install_mode == "bundle":
                    raise
                extracted_assets = None

            if extracted_assets is not None:
                if not extracted_assets:
                    raise ValueError("No installable assets extracted from .siftapp")

                resolved_app_id, source = _resolve_app_id(
                    manifest_dev_app_id=manifest_dev_app_id
                )

                use_learn = payload_crc_mode == "learn"
                prepared: list[tuple[int, bytes]] = []
                for entry in extracted_assets:
                    # Cube flash writes require 4-byte aligned payload lengths.
                    # Legacy image records from .sftbndl may not be aligned yet.
                    payload = align4(entry.payload)
                    if payload_crc_mode == "append":
                        payload = ensure_trailing_crc(payload)
                    prepared.append((asset_id + entry.asset_id, payload))

                total_bytes = sum(len(payload) for _, payload in prepared)
                sent_bytes = 0
                for aid, payload in prepared:
                    if progress is None:
                        cb = None
                    else:
                        base = sent_bytes

                        def cb(done: int, _size: int, base_offset: int = base) -> None:
                            progress(base_offset + done, total_bytes)

                    if use_learn:
                        self.upload_bytes_learn_crc(
                            cube_id=cube_id,
                            app_id=resolved_app_id,
                            asset_id=aid & 0xFFFF,
                            data=payload,
                            asset_type=ASSET_TYPE_IMAGE,
                            progress=cb,
                        )
                    else:
                        self.upload_bytes(
                            cube_id=cube_id,
                            app_id=resolved_app_id,
                            asset_id=aid & 0xFFFF,
                            data=payload,
                            asset_type=ASSET_TYPE_IMAGE,
                            progress=cb,
                        )
                    sent_bytes += len(payload)

                return SiftAppInstallResult(
                    app_id=resolved_app_id,
                    asset_id=asset_id,
                    bytes_uploaded=sent_bytes,
                    app_id_source=source,
                    payload_shape="container",
                    install_mode="bundle",
                    asset_count=len(prepared),
                    header=header,
                )

        data = extract_siftapp_payload(container_bytes, payload_shape=payload_shape)
        if payload_crc_mode == "append":
            data = ensure_trailing_crc(data)

        resolved_app_id, source = _resolve_app_id()
        if payload_crc_mode == "learn":
            self.upload_bytes_learn_crc(
                cube_id, resolved_app_id, asset_id, data,
                asset_type=asset_type, progress=progress,
            )
        else:
            self.upload_bytes(
                cube_id, resolved_app_id, asset_id, data,
                asset_type=asset_type, progress=progress,
            )
        return SiftAppInstallResult(
            app_id=resolved_app_id,
            asset_id=asset_id,
            bytes_uploaded=len(data),
            app_id_source=source,
            payload_shape=payload_shape,
            install_mode="opaque",
            asset_count=1,
            header=header,
        )

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
