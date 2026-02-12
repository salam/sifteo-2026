#!/usr/bin/env python3
"""
Sifteo V1 Dongle Detection and Diagnostic Tool.

Detects the USB dongle, probes communication, and listens for cube events.

Usage:
    python3 -m sifteo detect           # Detection only (no root needed)
    sudo python3 -m sifteo detect      # Full probe with communication test
"""

import os
import sys
import time

from .dongle import (
    SIFTEO_VID, SIFTEO_PID, SifteoDongle,
    DongleNotFoundError, DongleConnectionError, enumerate_dongles,
)
from .protocol import Op, Message, DONGLE_ADDRESS, op_name


def detect_dongle():
    """Detect and probe a connected Sifteo V1 dongle."""
    print("=" * 60)
    print("Sifteo V1 Dongle Detection Tool")
    print("=" * 60)
    print()

    is_root = os.geteuid() == 0

    # Step 1: Enumerate (no root needed)
    print(f"[1/4] Looking for Sifteo dongle (VID=0x{SIFTEO_VID:04X}, PID=0x{SIFTEO_PID:04X})...")
    devices = enumerate_dongles()

    if not devices:
        print("  NOT FOUND!")
        print()
        print("  Troubleshooting:")
        print("  1. Make sure the Sifteo USB dongle is plugged in")
        print("  2. Try a different USB port")
        print("  3. Check System Information > USB for the device")
        print("  4. The dongle should show as 'Sifteo Wireless Link'")
        return False

    print(f"  Found {len(devices)} Sifteo dongle(s)!")
    for i, dev in enumerate(devices):
        print(f"\n  Dongle #{i+1}:")
        print(f"    Product:      {dev.get('product_string', 'N/A')}")
        print(f"    Manufacturer: {dev.get('manufacturer_string', 'N/A')}")
        vid = dev.get('vendor_id', 0)
        pid = dev.get('product_id', 0)
        print(f"    VID:PID:      0x{vid:04X}:0x{pid:04X}")
        if 'usage_page' in dev:
            print(f"    Usage Page:   0x{dev['usage_page']:04X}")
            print(f"    Usage:        0x{dev['usage']:04X}")
        if 'interface_number' in dev:
            print(f"    Interface:    {dev['interface_number']}")
    print()

    # Step 2: USB descriptor details (pyusb, no root needed)
    print("[2/4] USB endpoint details...")
    try:
        import usb.core
        import usb.util
        udev = usb.core.find(idVendor=SIFTEO_VID, idProduct=SIFTEO_PID)
        if udev:
            cfg = udev.get_active_configuration()
            for intf in cfg:
                for ep in intf:
                    direction = "IN" if usb.util.endpoint_direction(ep.bEndpointAddress) == usb.util.ENDPOINT_IN else "OUT"
                    ep_type = {0: "CTRL", 1: "ISOC", 2: "BULK", 3: "INTR"}[usb.util.endpoint_type(ep.bmAttributes)]
                    print(f"  EP 0x{ep.bEndpointAddress:02X} ({direction}, {ep_type}) MaxPacketSize={ep.wMaxPacketSize}")
        else:
            print("  (pyusb could not find device)")
    except ImportError:
        print("  (pyusb not installed, skipping)")
    except Exception as e:
        print(f"  Error: {e}")
    print()

    # Step 3 & 4: Communication test (requires root)
    if not is_root:
        print("[3/4] Communication test... SKIPPED (not root)")
        print("  Run with sudo for full communication testing:")
        print(f"  sudo {sys.executable} -m sifteo detect")
        print()
        print("[4/4] Cube event listening... SKIPPED (not root)")
        print()
        print("=" * 60)
        print("Detection complete! Dongle found but not tested.")
        print(f"Run with sudo for full test: sudo {sys.executable} -m sifteo detect")
        print("=" * 60)
        return True

    # Step 3: Open and write (requires root)
    print("[3/4] Opening dongle (with kernel driver detach)...")
    dongle = SifteoDongle()
    try:
        dongle.open()
        print("  SUCCESS!")
    except DongleNotFoundError:
        print("  FAILED - Dongle not found")
        return False
    except DongleConnectionError as e:
        print(f"  FAILED - {e}")
        return False

    print()
    print("  Running cube discovery...")
    cube_ids = dongle.discover_cubes(max_attempts=3)
    if cube_ids:
        print(f"  Discovered cubes: {sorted(cube_ids)}")
    else:
        print("  No cubes found (normal if no cubes are powered on)")
    print()

    # Step 4: Listen for events
    print("[4/4] Listening for cube events (10 seconds)...")
    print("  Turn on Sifteo cubes near the dongle to see events.")
    print()

    event_count = 0
    start = time.time()
    while time.time() - start < 10.0:
        msg = dongle.get_event(timeout=0.2)
        if msg:
            event_count += 1
            name = op_name(msg.opcode)
            payload_hex = ' '.join(f'{b:02X}' for b in msg.payload[:8])
            print(f"  [{event_count:3d}] cube={msg.address} op={name} payload={payload_hex}")

    if event_count == 0:
        print("  No events received (normal if no cubes are powered on)")
    else:
        print(f"\n  Received {event_count} events in 10 seconds")

    dongle.close()
    print()
    print("=" * 60)
    print("Detection complete!")
    print("=" * 60)
    return True


if __name__ == "__main__":
    detect_dongle()
