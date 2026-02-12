"""Sifteo V1 Cubes - Open Source Host Software for Apple Silicon macOS."""

__version__ = "0.1.0"

from .protocol import (
    Op, Message, DONGLE_ADDRESS, rgb_to_rgb332, rgb332_to_rgb,
    ASSET_TYPE_IMAGE, ASSET_TYPE_SOUND,
)
from .dongle import SifteoDongle, DongleNotFoundError, DongleConnectionError
from .cube import Cube, CubeEvent, TiltEvent, ButtonEvent, NeighborEvent, ShakeEvent
from .runner import SifteoRunner
from .app import BaseApp
from .assets import (
    AssetManager, AppInfo, AssetInfo, CRCResult, FrameBuffer, UploadError,
    encode_image, encode_image_rgba, encode_image_rgb,
    read_siftimg, read_siftimg_crc,
)

__all__ = [
    "Op", "Message", "DONGLE_ADDRESS",
    "SifteoDongle", "DongleNotFoundError", "DongleConnectionError",
    "Cube", "CubeEvent", "TiltEvent", "ButtonEvent", "NeighborEvent", "ShakeEvent",
    "SifteoRunner", "BaseApp",
    "AssetManager", "AppInfo", "AssetInfo", "CRCResult", "FrameBuffer", "UploadError",
    "encode_image", "encode_image_rgba", "encode_image_rgb",
    "read_siftimg", "read_siftimg_crc",
    "rgb_to_rgb332", "rgb332_to_rgb",
    "ASSET_TYPE_IMAGE", "ASSET_TYPE_SOUND",
]
