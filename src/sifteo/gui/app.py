"""Sifteo Cube Manager GUI -- pywebview window setup and lifecycle."""

from __future__ import annotations

import sys
from pathlib import Path

WEB_DIR = Path(__file__).parent / "web"


def launch_gui() -> None:
    """Open the Sifteo Cube Manager window."""
    try:
        import webview
    except ImportError:
        print("ERROR: pywebview is not installed.")
        print("Install it with:  pip install 'sifteo[gui]'")
        sys.exit(1)

    from .bridge import Bridge

    bridge = Bridge()

    window = webview.create_window(
        title="Sifteo Cube Manager",
        url=str(WEB_DIR / "index.html"),
        js_api=bridge,
        width=780,
        height=620,
        min_size=(600, 480),
        background_color="#111114",
    )

    def on_loaded():
        bridge.set_window(window)

    def on_closed():
        bridge.cleanup()

    window.events.loaded += on_loaded
    window.events.closed += on_closed

    webview.start(debug=("--debug" in sys.argv))
