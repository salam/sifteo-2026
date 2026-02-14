"""Sifteo Cube Manager GUI -- pywebview window setup and lifecycle."""

from __future__ import annotations

import platform
import sys
from pathlib import Path

GUI_DIR = Path(__file__).parent
WEB_DIR = GUI_DIR / "web"
ICON_PATH = GUI_DIR / "SifteoSync.icns"


def _set_macos_icon() -> None:
    """Set the dock/app icon on macOS via AppKit."""
    if platform.system() != "Darwin" or not ICON_PATH.exists():
        return
    try:
        from AppKit import NSApplication, NSImage  # type: ignore[import-untyped]

        icon = NSImage.alloc().initWithContentsOfFile_(str(ICON_PATH))
        if icon:
            NSApplication.sharedApplication().setApplicationIconImage_(icon)
    except ImportError:
        pass


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
        _set_macos_icon()
        bridge.set_window(window)

    def on_closed():
        bridge.cleanup()

    window.events.loaded += on_loaded
    window.events.closed += on_closed

    webview.start(debug=("--debug" in sys.argv))
