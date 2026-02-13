#!/usr/bin/env python3
"""
Upload known legacy .siftimg fixtures and verify cube-side CRC results.

This script is intended to prove that the ASSET_UPLOAD transport path works
with known-good legacy image assets before debugging .siftapp containers.

Example:
  SIFTEO_WRITE_MIN_GAP=0.001 SIFTEO_WRITE_MAX_RETRIES=5 \
  PYTHONPATH=src sudo /opt/homebrew/bin/python3.9 \
  examples/verify_fixture_upload.py --cube-id 0 --quick
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Iterable


REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sifteo.assets import AssetManager, read_siftimg  # noqa: E402
from sifteo.dongle import (  # noqa: E402
    SifteoDongle,
    DongleNotFoundError,
    DongleConnectionError,
    DongleWriteError,
)
from sifteo.protocol import ASSET_TYPE_IMAGE  # noqa: E402


DEFAULT_FIXTURE_DIR = (
    REPO_ROOT
    / "extracted/siftrunner/Siftrunner.app/Contents/Resources/runner/connector/usb/tests/fixtures"
)
DEFAULT_QUICK_FIXTURES = ["small.siftimg", "sifteo-logo-cc.siftimg", "walk.siftimg"]


def _progress_bar(sent: int, total: int) -> None:
    pct = (sent * 100 // total) if total else 100
    bar = "#" * (pct // 2) + "-" * (50 - (pct // 2))
    print(f"\r    [{bar}] {pct}% ({sent}/{total} bytes)", end="", flush=True)
    if sent >= total:
        print()


def _resolve_fixture_list(
    fixture_dir: Path, fixture_args: list[str], quick: bool
) -> list[Path]:
    if fixture_args:
        paths: list[Path] = []
        for raw in fixture_args:
            candidate = Path(raw)
            if not candidate.is_absolute():
                candidate = fixture_dir / raw
            if not candidate.exists():
                raise FileNotFoundError(f"Fixture not found: {raw}")
            paths.append(candidate.resolve())
        return paths

    if quick:
        return [fixture_dir / name for name in DEFAULT_QUICK_FIXTURES]

    return sorted(fixture_dir.glob("*.siftimg"))


def _target_cubes(discovered: list[int], cube_ids: list[int], all_cubes: bool) -> list[int]:
    if all_cubes:
        return discovered
    if cube_ids:
        return [cid for cid in cube_ids if cid in discovered]
    if 0 in discovered:
        return [0]
    return discovered[:1]


def _run_for_cube(
    assets: AssetManager,
    cube_id: int,
    app_id: int,
    start_asset_id: int,
    fixture_paths: Iterable[Path],
    delete_first: bool,
    roundtrip: bool,
) -> tuple[int, int]:
    print(f"\nCube {cube_id}:")
    if delete_first:
        print(f"  Deleting existing assets for app_id={app_id}...")
        assets.delete_all_assets(cube_id, app_id)

    passed = 0
    total = 0
    for idx, path in enumerate(fixture_paths):
        total += 1
        asset_id = start_asset_id + idx
        data = read_siftimg(path)
        print(f"  Uploading {path.name} -> asset_id={asset_id} ({len(data)} bytes)")
        try:
            assets.upload_bytes(
                cube_id=cube_id,
                app_id=app_id,
                asset_id=asset_id,
                data=data,
                asset_type=ASSET_TYPE_IMAGE,
                progress=_progress_bar,
            )
            crc = assets.verify_crc(cube_id, app_id, asset_id, ASSET_TYPE_IMAGE)
            fixture_ok = False
            if crc and crc.valid:
                fixture_ok = True
                print("    CRC: VALID")
            elif crc:
                print(
                    "    CRC: MISMATCH "
                    f"(orig=0x{crc.original_crc:08X}, calc=0x{crc.calculated_crc:08X})"
                )
            else:
                print("    CRC: TIMEOUT")

            if fixture_ok and roundtrip:
                downloaded = assets.download_asset(
                    cube_id, app_id, asset_id, ASSET_TYPE_IMAGE, timeout=30.0
                )
                if downloaded is None:
                    fixture_ok = False
                    print("    Roundtrip: DOWNLOAD TIMEOUT")
                elif downloaded != data:
                    fixture_ok = False
                    print(
                        "    Roundtrip: BYTE MISMATCH "
                        f"(uploaded={len(data)}, downloaded={len(downloaded)})"
                    )
                else:
                    print("    Roundtrip: BYTE MATCH")

            if fixture_ok:
                passed += 1
        except (DongleWriteError, DongleConnectionError, Exception) as exc:
            print(f"    Upload failed: {exc}")

    print(f"  Result: {passed}/{total} fixture uploads verified")
    return passed, total


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Upload known legacy .siftimg fixtures and verify cube CRC responses."
    )
    parser.add_argument(
        "--fixture-dir",
        default=str(DEFAULT_FIXTURE_DIR),
        help="Directory containing legacy .siftimg fixtures.",
    )
    parser.add_argument(
        "--fixture",
        action="append",
        default=[],
        help="Fixture filename or path (repeatable). If omitted, uses all *.siftimg files.",
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Use a small representative subset of fixtures.",
    )
    parser.add_argument(
        "--cube-id",
        type=int,
        action="append",
        default=[],
        help="Target cube ID (repeatable). Default targets cube 0 if available.",
    )
    parser.add_argument(
        "--all-cubes",
        action="store_true",
        help="Run verification on all discovered cubes.",
    )
    parser.add_argument(
        "--app-id",
        type=lambda s: int(s, 0),
        default=0x53465446,
        help="App ID used for fixture uploads (default: 0x53465446).",
    )
    parser.add_argument(
        "--start-asset-id",
        type=int,
        default=100,
        help="Starting asset ID for fixture uploads (default: 100).",
    )
    parser.add_argument(
        "--delete-first",
        action="store_true",
        help="Delete all assets for --app-id on target cube(s) before uploading.",
    )
    parser.add_argument(
        "--roundtrip",
        action="store_true",
        help="After CRC check, download each asset and compare bytes exactly.",
    )
    args = parser.parse_args()

    fixture_dir = Path(args.fixture_dir).resolve()
    if not fixture_dir.exists():
        print(f"Fixture directory not found: {fixture_dir}", file=sys.stderr)
        sys.exit(1)

    try:
        fixture_paths = _resolve_fixture_list(fixture_dir, args.fixture, args.quick)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
    if not fixture_paths:
        print(f"No .siftimg fixtures found in {fixture_dir}", file=sys.stderr)
        sys.exit(1)

    print("Sifteo V1 fixture upload verification")
    print(f"Fixture dir: {fixture_dir}")
    print(f"Fixtures: {', '.join(p.name for p in fixture_paths)}")
    print(f"App ID: 0x{args.app_id:08X}")

    dongle = SifteoDongle()
    try:
        try:
            dongle.open()
        except (DongleNotFoundError, DongleConnectionError) as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            sys.exit(1)

        discovered = sorted(dongle.discover_cubes())
        if not discovered:
            print("No cubes found.")
            sys.exit(1)

        targets = _target_cubes(discovered, args.cube_id, args.all_cubes)
        if not targets:
            print("No selected cubes are connected.")
            sys.exit(1)

        print(f"Targets: {targets}")
        assets = AssetManager(dongle)
        total_ok = 0
        total_checks = 0
        for cube_id in targets:
            ok, checks = _run_for_cube(
                assets=assets,
                cube_id=cube_id,
                app_id=args.app_id,
                start_asset_id=args.start_asset_id,
                fixture_paths=fixture_paths,
                delete_first=args.delete_first,
                roundtrip=args.roundtrip,
            )
            total_ok += ok
            total_checks += checks

        print(
            "\nSummary: "
            f"{total_ok}/{total_checks} fixture uploads passed verification "
            f"across {len(targets)} cube(s)"
        )
        if total_ok != total_checks:
            sys.exit(1)
    finally:
        dongle.close()


if __name__ == "__main__":
    main()
