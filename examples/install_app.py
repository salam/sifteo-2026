#!/usr/bin/env python3
"""
Install a bundled .siftapp onto a cube by short app name.

Usage:
    ./examples/install_app.py <name> <cube_id|all>

Examples:
    ./examples/install_app.py siftsays 0      # cube 0 only
    ./examples/install_app.py siftsays all    # all detected cubes
    ./examples/install_app.py siftsays 2      # cube 2 only
    ./examples/install_app.py siftsays.siftapp 2
"""

from __future__ import annotations

import argparse
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SIFTAPP_DIR = PROJECT_ROOT / "sifteo-gen1-redux" / "payload" / "Siftapps"


def discover_siftapps() -> list[Path]:
    return sorted(SIFTAPP_DIR.glob("*.siftapp"), key=lambda p: p.name.lower())


def available_names(apps: list[Path]) -> list[str]:
    return [p.name for p in apps]


def resolve_siftapp(name: str, apps: list[Path]) -> Path | None:
    query = name.strip()
    if not query:
        return None

    query_with_ext = query if query.lower().endswith(".siftapp") else f"{query}.siftapp"
    by_filename = {p.name: p for p in apps}
    by_stem = {p.stem: p for p in apps}
    by_filename_lower = {p.name.lower(): p for p in apps}
    by_stem_lower = {p.stem.lower(): p for p in apps}

    if query_with_ext in by_filename:
        return by_filename[query_with_ext]
    if query in by_stem:
        return by_stem[query]
    if query_with_ext.lower() in by_filename_lower:
        return by_filename_lower[query_with_ext.lower()]
    if query.lower() in by_stem_lower:
        return by_stem_lower[query.lower()]

    return None


def parse_cube_target(raw_value: str) -> int | None:
    value = raw_value.strip().lower()
    if value == "all":
        return None
    try:
        cube_id = int(value)
    except ValueError:
        raise ValueError("cube target must be an integer or 'all'") from None
    if cube_id < 0:
        raise ValueError("cube target must be >= 0")
    return cube_id


def build_command(siftapp_path: Path, cube_id: int | None) -> tuple[list[str], dict[str, str]]:
    python39 = shutil.which("python3.9") or "python3.9"
    py_path = str((PROJECT_ROOT / "src").resolve())
    sudo_env = []
    # sudo typically strips PYTHONPATH, so pass it explicitly to guarantee
    # the workspace module is used rather than a globally installed version.
    sudo_env.append(f"PYTHONPATH={py_path}")
    for key in (
        "SIFTEO_WRITE_MIN_GAP",
        "SIFTEO_WRITE_MAX_RETRIES",
        "SIFTEO_WRITE_ACK_TIMEOUT",
    ):
        value = os.environ.get(key)
        if value:
            # Preserve write tuning across sudo's default env reset.
            sudo_env.append(f"{key}={value}")
    cmd = [
        "sudo",
        *sudo_env,
        python39,
        "-m",
        "sifteo",
        "install-siftapp",
        str(siftapp_path),
    ]
    if cube_id is not None:
        cmd.extend(["--cube-id", str(cube_id)])
    env = os.environ.copy()
    env["PYTHONPATH"] = py_path
    return cmd, env


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Install a bundled .siftapp by name onto a target cube ID."
    )
    parser.add_argument("name", help="App name or filename (with or without .siftapp)")
    parser.add_argument("cube_target", help="Cube ID, or 'all' for all detected cubes")
    parser.add_argument("--dry-run", action="store_true", help="Print command and exit")
    args = parser.parse_args()

    apps = discover_siftapps()
    if not apps:
        print(f"No .siftapp files found in {SIFTAPP_DIR}", file=sys.stderr)
        return 1

    siftapp = resolve_siftapp(args.name, apps)
    if siftapp is None:
        print(f"Unknown app '{args.name}'. Available .siftapp files:", file=sys.stderr)
        for entry in available_names(apps):
            print(f"  - {entry}", file=sys.stderr)
        return 2

    try:
        cube_id = parse_cube_target(args.cube_target)
    except ValueError as exc:
        print(f"Invalid cube target '{args.cube_target}': {exc}", file=sys.stderr)
        return 2

    cmd, env = build_command(siftapp, cube_id)
    pretty = " ".join(shlex.quote(part) for part in cmd)
    print(f"Installing: {siftapp.name}")
    if cube_id is None:
        print("Target cubes: all detected cubes")
    else:
        print(f"Target cube: {cube_id}")
    print(f"Running: {pretty}")

    if args.dry_run:
        return 0

    completed = subprocess.run(cmd, cwd=PROJECT_ROOT, env=env, check=False)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
