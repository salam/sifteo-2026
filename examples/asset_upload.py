#!/usr/bin/env python3
"""
Asset Upload Example - Sifteo V1.

Demonstrates uploading image and sound assets to cube flash,
querying asset inventory, CRC verification, and framebuffer download.

Usage:
    # Upload a PNG/BMP/JPEG image (auto-encodes to RGB332):
    sudo python3 examples/asset_upload.py logo.png

    # Upload a WAV sound (auto-encodes to float32 22050Hz mono):
    sudo python3 examples/asset_upload.py beep.wav

    # Upload a pre-compiled .siftimg file:
    sudo python3 examples/asset_upload.py walk.siftimg

    # With a custom app/asset ID:
    sudo python3 examples/asset_upload.py logo.png --app-id 42 --asset-id 1

    # Just query existing assets on the cube:
    sudo python3 examples/asset_upload.py --list

    # Download the framebuffer to a file:
    sudo python3 examples/asset_upload.py --dump-framebuffer output.bin

    # Delete all assets for an app:
    sudo python3 examples/asset_upload.py --delete-all --app-id 42
"""

import sys
import os
import argparse
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from sifteo import (
    BaseApp, Cube, AssetManager, ASSET_TYPE_IMAGE, ASSET_TYPE_SOUND,
    encode_image, encode_sound, read_siftimg,
)

# Image file extensions that should be encoded to RGB332
IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.bmp', '.gif', '.tiff', '.webp'}

# Sound file extensions that should be encoded to float32
SOUND_EXTENSIONS = {'.wav'}


def progress_bar(sent: int, total: int):
    pct = sent * 100 // total
    bar = "=" * (pct // 2) + " " * (50 - pct // 2)
    print(f"\r  [{bar}] {pct}% ({sent}/{total} bytes)", end="", flush=True)
    if sent >= total:
        print()


class AssetUploadDemo(BaseApp):

    def __init__(self, args):
        super().__init__()
        self.args = args

    def setup(self):
        if not self.cubes:
            print("No cubes found!")
            self.runner.stop()
            return

        cube = self.cubes[0]
        assets = self.assets
        print(f"Using cube {cube.id}")

        if self.args.list:
            self._list_assets(cube, assets)
        elif self.args.dump_framebuffer:
            self._dump_framebuffer(cube, assets)
        elif self.args.delete_all:
            self._delete_all(cube, assets)
        elif self.args.file:
            self._upload_file(cube, assets)
        else:
            print("Nothing to do. Use --help for usage info.")

        self.runner.stop()

    def _list_assets(self, cube: Cube, assets: AssetManager):
        app_id = self.args.app_id

        print(f"\n--- App list for cube {cube.id} ---")
        app_ids = assets.query_app_list(cube.id)
        if app_ids:
            for aid in app_ids:
                print(f"  App ID: {aid}")
        else:
            print("  No apps found.")

        print(f"\n--- Asset info for app {app_id} ---")
        info = assets.query_app_info(cube.id, app_id)
        if info:
            print(f"  Images: {info.image_count}")
            print(f"  Sounds: {info.sound_count}")
            print(f"  Total bytes: {info.total_bytes}")

            inv = assets.query_asset_inventory(cube.id, app_id)
            if inv:
                print(f"\n  Assets:")
                for a in inv:
                    print(f"    #{a.asset_id} ({a.type_name})")
        else:
            print("  No info (app may not exist on cube).")

    def _dump_framebuffer(self, cube: Cube, assets: AssetManager):
        output = self.args.dump_framebuffer
        print(f"Downloading framebuffer from cube {cube.id}...")
        fb = assets.download_framebuffer(cube.id)
        if fb is None:
            print("Failed to download framebuffer.")
            return
        print(f"  Size: {fb.width}x{fb.height}, {fb.bpp} bpp")
        print(f"  Data: {len(fb.data)} bytes")
        with open(output, "wb") as f:
            f.write(fb.data)
        print(f"  Saved to {output}")

    def _delete_all(self, cube: Cube, assets: AssetManager):
        app_id = self.args.app_id
        print(f"Deleting all assets for app {app_id} on cube {cube.id}...")
        if assets.delete_all_assets(cube.id, app_id):
            print("Done.")
        else:
            print("Failed (timeout or error).")

    def _upload_file(self, cube: Cube, assets: AssetManager):
        file_path = self.args.file
        app_id = self.args.app_id
        asset_id = self.args.asset_id
        ext = os.path.splitext(file_path)[1].lower()

        # Auto-detect asset type from extension (--sound flag overrides)
        is_sound = self.args.sound or ext in SOUND_EXTENSIONS
        asset_type = ASSET_TYPE_SOUND if is_sound else ASSET_TYPE_IMAGE

        type_name = "sound" if is_sound else "image"
        print(f"\nUploading {type_name}: {file_path}")
        print(f"  App ID: {app_id}, Asset ID: {asset_id}")
        print(f"  File size: {os.path.getsize(file_path)} bytes")

        if ext in SOUND_EXTENSIONS:
            print(f"  Encoding: {ext} -> float32 22050Hz mono")
            data = encode_sound(file_path)
            print(f"  Encoded size: {len(data)} bytes (including 4-byte CRC)")
        elif ext in IMAGE_EXTENSIONS:
            w = self.args.width
            h = self.args.height
            print(f"  Encoding: {ext} -> RGB332 ({w}x{h})")
            data = encode_image(file_path, w, h)
            print(f"  Encoded size: {len(data)} bytes (including 4-byte CRC)")
        else:
            print(f"  Format: raw ({ext or 'binary'})")
            data = read_siftimg(file_path)

        print()

        try:
            ok = assets.upload_bytes(
                cube.id, app_id, asset_id, data,
                asset_type=asset_type, progress=progress_bar,
            )
            if ok:
                print(f"Upload complete!")
            else:
                print("Upload returned False.")
                return
        except Exception as e:
            print(f"Upload failed: {e}")
            return

        # Verify CRC
        if self.args.verify:
            print("Verifying CRC...")
            crc = assets.verify_crc(cube.id, app_id, asset_id, asset_type)
            if crc:
                status = "VALID" if crc.valid else "MISMATCH"
                print(f"  Original: 0x{crc.original_crc:08X}")
                print(f"  Calculated: 0x{crc.calculated_crc:08X}")
                print(f"  Status: {status}")
            else:
                print("  CRC verification timed out.")

        # Display the image on the cube
        if asset_type == ASSET_TYPE_IMAGE and self.args.display:
            print(f"Displaying asset on cube {cube.id}...")
            cube.image(app_id, asset_id)
            cube.repaint()


def main():
    parser = argparse.ArgumentParser(description="Sifteo V1 Asset Upload Tool")
    parser.add_argument("file", nargs="?", help="Asset file to upload")
    parser.add_argument("--app-id", type=int, default=0,
                        help="Application ID (default: 0)")
    parser.add_argument("--asset-id", type=int, default=0,
                        help="Asset ID (default: 0)")
    parser.add_argument("--width", type=int, default=128,
                        help="Image width for PNG/BMP encoding (default: 128)")
    parser.add_argument("--height", type=int, default=128,
                        help="Image height for PNG/BMP encoding (default: 128)")
    parser.add_argument("--sound", action="store_true",
                        help="Upload as sound asset (default: image)")
    parser.add_argument("--verify", action="store_true", default=True,
                        help="Verify CRC after upload (default: True)")
    parser.add_argument("--no-verify", action="store_false", dest="verify",
                        help="Skip CRC verification")
    parser.add_argument("--display", action="store_true", default=True,
                        help="Display uploaded image on cube (default: True)")
    parser.add_argument("--no-display", action="store_false", dest="display")
    parser.add_argument("--list", action="store_true",
                        help="List assets on cube instead of uploading")
    parser.add_argument("--dump-framebuffer", metavar="OUTPUT",
                        help="Download framebuffer to file")
    parser.add_argument("--delete-all", action="store_true",
                        help="Delete all assets for the given app ID")
    args = parser.parse_args()

    if not args.file and not args.list and not args.dump_framebuffer and not args.delete_all:
        parser.print_help()
        sys.exit(1)

    print("Sifteo V1 - Asset Upload Tool")
    print()
    AssetUploadDemo(args).run()


if __name__ == "__main__":
    main()
