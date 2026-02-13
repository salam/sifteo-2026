"""Allow running sifteo module directly: python3 -m sifteo [command]"""

import argparse
import sys


def main():
    args = sys.argv[1:]

    if not args or args[0] == "detect":
        from .detect import detect_dongle
        detect_dongle()
    elif args[0] == "gui":
        from .gui import launch_gui
        launch_gui()
    elif args[0] == "run":
        from .runner import SifteoRunner
        runner = SifteoRunner()
        if not runner.connect():
            sys.exit(1)
        # Add cubes by ID if specified: python3 -m sifteo run 1 2 3
        for cube_id_str in args[1:]:
            try:
                runner.add_cube(int(cube_id_str))
            except ValueError:
                print(f"Invalid cube ID: {cube_id_str}")
        runner.run()
    elif args[0] == "demo":
        _run_demo()
    elif args[0] == "install-siftapp":
        _install_siftapp(args[1:])
    else:
        print("Usage: python3 -m sifteo [detect|gui|run|demo|install-siftapp]")
        print()
        print("Commands:")
        print("  detect       Detect and probe the USB dongle (default)")
        print("  gui          Open the graphical Cube Manager (requires pywebview)")
        print("  run [ids]    Start the runner with optional cube IDs")
        print("  demo         Run the color demo on connected cubes")
        print("  install-siftapp PATH")
        print("               Upload a legacy .siftapp bundle to connected cube(s)")
        sys.exit(1)


def _run_demo():
    """Simple color-cycling demo to verify cube communication."""
    from .runner import SifteoRunner
    from .protocol import rgb_to_rgb332

    runner = SifteoRunner()
    if not runner.connect():
        sys.exit(1)

    hue = 0

    def tick(dt):
        nonlocal hue
        hue = (hue + 1) % 256
        for cube in runner.cubes.values():
            # Cycle through colors
            r = max(0, 255 - abs(hue - 0) * 3 - abs(hue - 255) * 3)
            g = max(0, 255 - abs(hue - 85) * 3)
            b = max(0, 255 - abs(hue - 170) * 3)
            cube.fill(r, g, b)

    def on_event(event):
        print(f"  {event}")

    runner.on_tick(tick)
    runner.on_event(on_event)

    print("Running color demo. Press Ctrl+C to stop.")
    print("Turn on cubes near the dongle to see them light up.")
    runner.run(target_fps=15)


def _install_siftapp(argv: list[str]) -> None:
    """CLI helper to upload legacy .siftapp files as opaque app payloads."""
    parser = argparse.ArgumentParser(
        prog="python3 -m sifteo install-siftapp",
        description="Upload a legacy .siftapp bundle to cube flash.",
    )
    parser.add_argument("path", help="Path to .siftapp file")
    parser.add_argument("--cube-id", type=int, action="append",
                        help="Target cube ID (repeatable). Defaults to all connected cubes.")
    parser.add_argument("--app-id", type=int, default=None,
                        help="Override app ID.")
    parser.add_argument("--prefer-header-app-id", action="store_true",
                        help="Use .siftapp header internal ID when app-id is not set "
                             "(default uses crc32(filename) to avoid collisions).")
    parser.add_argument("--asset-id", type=int, default=0,
                        help="Asset ID slot to store the bundle (default: 0).")
    parser.add_argument("--asset-type", type=int, choices=[0, 1], default=None,
                        help="Asset type tag to store (0=image, 1=sound). "
                             "Default: auto-try compatibility variants.")
    parser.add_argument(
        "--payload-crc",
        choices=["auto", "append", "none"],
        default="auto",
        help=(
            "How to treat trailing payload CRC for .siftapp bytes: "
            "'append' adds/keeps a zlib CRC32 footer, "
            "'none' uploads bytes as-is, "
            "'auto' tries both."
        ),
    )
    parser.add_argument(
        "--payload-shape",
        choices=["auto", "container", "body"],
        default="auto",
        help=(
            "Which bytes from .siftapp to upload: "
            "'container' uploads full file, "
            "'body' strips the 16-byte header, "
            "'auto' tries both."
        ),
    )
    parser.add_argument("--no-verify", action="store_true",
                        help="Skip post-upload CRC verification.")
    opts = parser.parse_args(argv)

    from .assets import UploadError, AssetManager
    from .dongle import DongleWriteError, DongleConnectionError
    from .dongle import SifteoDongle, DongleNotFoundError

    dongle = SifteoDongle()
    try:
        try:
            dongle.open()
        except (DongleNotFoundError, DongleConnectionError) as exc:
            print(f"ERROR: {exc}")
            sys.exit(1)

        assets = AssetManager(dongle)
        discovered = sorted(dongle.discover_cubes())
        if not discovered:
            print("No cubes found. Make sure cubes are powered on and nearby.")
            sys.exit(1)

        if opts.cube_id:
            targets = [cid for cid in opts.cube_id if cid in discovered]
            missing = [cid for cid in opts.cube_id if cid not in discovered]
            for cid in missing:
                print(f"Skipping unknown cube ID {cid} (not connected)")
        else:
            targets = discovered

        if not targets:
            print("No target cubes selected.")
            sys.exit(1)

        any_failed = False
        for cube_id in targets:
            print(f"Installing on cube {cube_id}: {opts.path}")
            if opts.payload_crc == "auto":
                crc_modes = ["none", "append"]
            else:
                crc_modes = [opts.payload_crc]
            if opts.payload_shape == "auto":
                payload_shapes = ["container", "body"]
            else:
                payload_shapes = [opts.payload_shape]

            if opts.app_id is None and not opts.prefer_header_app_id and opts.asset_type is None:
                base_attempts = [
                    {"app_id": None, "prefer_header_app_id": False, "asset_type": 0,
                     "label": "crc32/type0"},
                    {"app_id": None, "prefer_header_app_id": False, "asset_type": 1,
                     "label": "crc32/type1"},
                    {"app_id": None, "prefer_header_app_id": True, "asset_type": 0,
                     "label": "header/type0"},
                    {"app_id": None, "prefer_header_app_id": True, "asset_type": 1,
                     "label": "header/type1"},
                ]
            else:
                base_attempts = [{
                    "app_id": opts.app_id,
                    "prefer_header_app_id": opts.prefer_header_app_id,
                    "asset_type": 0 if opts.asset_type is None else opts.asset_type,
                    "label": "explicit",
                }]

            attempts = []
            for base in base_attempts:
                for shape in payload_shapes:
                    for crc_mode in crc_modes:
                        label = base["label"]
                        if len(payload_shapes) > 1:
                            label += "/body" if shape == "body" else "/container"
                        if len(crc_modes) > 1:
                            label += "/raw" if crc_mode == "none" else "/crc"
                        attempt = dict(base)
                        attempt["payload_shape"] = shape
                        attempt["payload_crc_mode"] = crc_mode
                        attempt["label"] = label
                        attempts.append(attempt)

            result = None
            last_exc = None
            attempt_errors = []
            for idx, attempt in enumerate(attempts, start=1):
                if len(attempts) > 1:
                    print(
                        f"  Attempt {idx}/{len(attempts)} "
                        f"({attempt['label']})..."
                    )
                try:
                    result = assets.install_siftapp(
                        cube_id=cube_id,
                        siftapp_path=opts.path,
                        app_id=attempt["app_id"],
                        prefer_header_app_id=attempt["prefer_header_app_id"],
                        payload_shape=attempt["payload_shape"],
                        payload_crc_mode=attempt["payload_crc_mode"],
                        asset_id=opts.asset_id,
                        asset_type=attempt["asset_type"],
                        progress=assets.print_progress,
                    )
                    break
                except (
                    FileNotFoundError, UploadError, ValueError,
                    DongleWriteError, DongleConnectionError,
                ) as exc:
                    last_exc = exc
                    attempt_errors.append(exc)
                    if len(attempts) > 1:
                        print(f"    failed: {exc}")
                    continue

            if result is None:
                any_failed = True
                print(f"  FAILED: {last_exc}")
                if (
                    attempt_errors
                    and all(
                        isinstance(e, UploadError)
                        and "CRC verification failed on cube" in str(e)
                        for e in attempt_errors
                    )
                ):
                    print(
                        "  NOTE: all compatibility variants failed with cube CRC rejection.\n"
                        "        This strongly suggests the .siftapp container bytes are not\n"
                        "        directly valid cube asset payloads for ASSET_UPLOAD."
                    )
                continue

            print(f"  Stored as app_id={result.app_id} asset_id={result.asset_id}")
            print(f"  Uploaded {result.bytes_uploaded} bytes (source: {result.app_id_source})")

            if not opts.no_verify:
                crc = assets.verify_crc(
                    cube_id, result.app_id, result.asset_id
                )
                if crc and crc.valid:
                    print("  CRC verification: VALID")
                elif crc:
                    any_failed = True
                    print(
                        "  CRC verification: MISMATCH "
                        f"(orig=0x{crc.original_crc:08X}, calc=0x{crc.calculated_crc:08X})"
                    )
                else:
                    any_failed = True
                    print("  CRC verification: TIMEOUT")

        if any_failed:
            sys.exit(1)
    finally:
        dongle.close()


main()
