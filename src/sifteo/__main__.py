"""Allow running sifteo module directly: python3 -m sifteo [command]"""

import sys


def main():
    args = sys.argv[1:]

    if not args or args[0] == "detect":
        from .detect import detect_dongle
        detect_dongle()
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
    else:
        print("Usage: python3 -m sifteo [detect|run|demo]")
        print()
        print("Commands:")
        print("  detect       Detect and probe the USB dongle (default)")
        print("  run [ids]    Start the runner with optional cube IDs")
        print("  demo         Run the color demo on connected cubes")
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


main()
