#!/usr/bin/env python3
"""
Minimal upload test to isolate CRC failure cause.

Tests upload variants to determine what CRC/format the cube firmware expects:
  1. Raw .siftimg fixture (no CRC append) — matches original SiftRunner
  2. Raw .siftimg fixture with appended CRC32 — tests if cube accepts our CRC
  3. Tiny synthetic payload (32 bytes, no CRC) — baseline transport test
  4. Tiny synthetic payload + CRC32 (36 bytes)
  5. Extracted .sftbndl record from calculator.siftapp (no CRC) — tests bundle mode
  6. Extracted .sftbndl record + CRC32 — for comparison

Usage:
  sudo PYTHONPATH=src python3.9 examples/test_minimal_upload.py --cube-id 0
"""
from __future__ import annotations

import logging
import struct
import sys
import zlib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sifteo.assets import (
    AssetManager, UploadError, ensure_trailing_crc, align4,
    extract_siftapp_bundle_assets, read_siftapp,
)
from sifteo.dongle import (
    SifteoDongle,
    DongleNotFoundError,
    DongleConnectionError,
    DongleWriteError,
)

FIXTURE_DIR = (
    REPO_ROOT
    / "extracted/siftrunner/Siftrunner.app/Contents/Resources"
    / "runner/connector/usb/tests/fixtures"
)

SIFTAPP_DIR = REPO_ROOT / "extracted/payload/Siftapps"

logging.basicConfig(
    level=logging.DEBUG,
    format="%(name)s %(levelname)s: %(message)s",
)


def _progress(sent: int, total: int) -> None:
    pct = (sent * 100 // total) if total else 100
    print(f"\r    [{pct:3d}%] {sent}/{total}", end="", flush=True)
    if sent >= total:
        print()


def _try_upload(mgr: AssetManager, cube_id: int, app_id: int,
                asset_id: int, data: bytes, label: str) -> bool:
    print(f"\n  Test {asset_id}: {label}")
    print(f"    Size: {len(data)} bytes, first8: {data[:8].hex()}, last4: {data[-4:].hex()}")
    try:
        ok = mgr.upload_bytes(
            cube_id=cube_id,
            app_id=app_id,
            asset_id=asset_id,
            data=data,
            progress=_progress,
        )
        print(f"    Result: OK ({ok})")
        # Try CRC verify
        crc = mgr.verify_crc(cube_id, app_id, asset_id)
        if crc and crc.valid:
            print(f"    CRC verify: VALID (0x{crc.original_crc:08X})")
        elif crc:
            print(f"    CRC verify: MISMATCH (orig=0x{crc.original_crc:08X} calc=0x{crc.calculated_crc:08X})")
        else:
            print(f"    CRC verify: TIMEOUT")
        return True
    except (UploadError, DongleWriteError) as e:
        print(f"    FAILED: {e}")
        return False


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(
        description="Upload test variants to isolate CRC failure cause."
    )
    parser.add_argument("--cube-id", type=int, default=0)
    parser.add_argument("--app-id", type=lambda s: int(s, 0), default=0xDEAD0001)
    parser.add_argument("--skip-fixture", action="store_true",
                        help="Skip .siftimg fixture tests")
    parser.add_argument("--skip-bundle", action="store_true",
                        help="Skip .sftbndl extracted record tests")
    args = parser.parse_args()

    dongle = SifteoDongle()
    try:
        dongle.open()
        cubes = dongle.discover_cubes()
        if args.cube_id not in cubes:
            print(f"Cube {args.cube_id} not found (available: {sorted(cubes)})")
            sys.exit(1)

        mgr = AssetManager(dongle)
        results = []
        aid = 0

        # ── .siftimg fixture tests ──
        if not args.skip_fixture:
            fixture_path = FIXTURE_DIR / "small.siftimg"
            if fixture_path.exists():
                raw = fixture_path.read_bytes()
                print(f"\nFixture: {fixture_path.name} ({len(raw)} bytes)")
                print(f"  First 8: {raw[:8].hex()}")
                print(f"  Last  4: {raw[-4:].hex()}")
                stored = struct.unpack_from("<I", raw, len(raw) - 4)[0]
                computed = zlib.crc32(raw[:-4]) & 0xFFFFFFFF
                print(f"  Trailing CRC32 valid: {stored == computed}")

                ok = _try_upload(mgr, args.cube_id, args.app_id, aid,
                                 raw, "Raw .siftimg (as-is, matches SiftRunner)")
                results.append(("fixture raw", ok))
                aid += 1

                with_crc = ensure_trailing_crc(raw)
                ok = _try_upload(mgr, args.cube_id, args.app_id, aid,
                                 with_crc, "Raw .siftimg + appended CRC32")
                results.append(("fixture +crc", ok))
                aid += 1
            else:
                print(f"\nFixture not found: {fixture_path} (skipping)")

        # ── Synthetic payload tests ──
        tiny = b"\xAA" * 32
        ok = _try_upload(mgr, args.cube_id, args.app_id, aid,
                         tiny, "Synthetic 32-byte (no CRC)")
        results.append(("synthetic raw", ok))
        aid += 1

        tiny_crc = ensure_trailing_crc(tiny)
        ok = _try_upload(mgr, args.cube_id, args.app_id, aid,
                         tiny_crc, "Synthetic 32-byte + CRC32 (36 bytes)")
        results.append(("synthetic +crc", ok))
        aid += 1

        # ── Extracted .sftbndl record tests ──
        if not args.skip_bundle:
            siftapp_path = SIFTAPP_DIR / "calculator.siftapp"
            if siftapp_path.exists():
                container = read_siftapp(siftapp_path)
                try:
                    _title, _dev_id, assets = extract_siftapp_bundle_assets(container)
                    # Use the smallest asset for faster testing
                    smallest = min(assets, key=lambda a: len(a.payload))
                    print(f"\n.sftbndl record: {smallest.name} "
                          f"({smallest.marker} {smallest.width}x{smallest.height}, "
                          f"{len(smallest.payload)} bytes)")

                    # Test: raw record (no CRC, no alignment)
                    ok = _try_upload(mgr, args.cube_id, args.app_id, aid,
                                     smallest.payload,
                                     f"sftbndl '{smallest.name}' raw (no CRC)")
                    results.append(("bundle raw", ok))
                    aid += 1

                    # Test: aligned, no CRC
                    aligned = align4(smallest.payload)
                    ok = _try_upload(mgr, args.cube_id, args.app_id, aid,
                                     aligned,
                                     f"sftbndl '{smallest.name}' align4 (no CRC)")
                    results.append(("bundle aligned", ok))
                    aid += 1

                    # Test: aligned + CRC32
                    with_crc = ensure_trailing_crc(aligned)
                    ok = _try_upload(mgr, args.cube_id, args.app_id, aid,
                                     with_crc,
                                     f"sftbndl '{smallest.name}' align4 + CRC32")
                    results.append(("bundle +crc", ok))
                    aid += 1

                except ValueError as e:
                    print(f"\nCould not extract .sftbndl from calculator.siftapp: {e}")
            else:
                print(f"\ncalculator.siftapp not found: {siftapp_path} (skipping)")

        # ── Summary ──
        print("\n" + "=" * 50)
        print("RESULTS:")
        for label, ok in results:
            status = "OK" if ok else "FAIL"
            print(f"  {status:4s}  {label}")
        print("=" * 50)

    finally:
        dongle.close()


if __name__ == "__main__":
    main()
