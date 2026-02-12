#!/usr/bin/env python3
"""Raw dongle communication test using pyusb/libusb (interrupt transfers)."""

import usb.core
import usb.util
import time

VID = 0x22FA
PID = 0x0101
MSG_LEN = 33


def hex_dump(data, n=20):
    if not data:
        return "(empty)"
    return ' '.join(f'{b:02X}' for b in data[:n])


def main():
    print("=== Raw Dongle Test (pyusb/libusb) ===\n")

    dev = usb.core.find(idVendor=VID, idProduct=PID)
    if dev is None:
        print("No Sifteo dongle found!")
        return

    print(f"Found: {dev.manufacturer} - {dev.product}")
    print(f"  VID:PID: 0x{dev.idVendor:04X}:0x{dev.idProduct:04X}")
    print(f"  Bus: {dev.bus}  Address: {dev.address}")
    print()

    # Print configuration details
    cfg = dev.get_active_configuration()
    print(f"Configuration: {cfg.bConfigurationValue}")
    for intf in cfg:
        print(f"  Interface {intf.bInterfaceNumber}:")
        print(f"    Class: {intf.bInterfaceClass} SubClass: {intf.bInterfaceSubClass}")
        for ep in intf:
            direction = "IN" if usb.util.endpoint_direction(ep.bEndpointAddress) == usb.util.ENDPOINT_IN else "OUT"
            ep_type = {0: "CTRL", 1: "ISOC", 2: "BULK", 3: "INTR"}[usb.util.endpoint_type(ep.bmAttributes)]
            print(f"    EP 0x{ep.bEndpointAddress:02X} ({direction}, {ep_type}) "
                  f"MaxPacketSize={ep.wMaxPacketSize}")
    print()

    # Detach kernel driver if needed (macOS HID)
    try:
        if dev.is_kernel_driver_active(0):
            print("Detaching kernel driver...")
            dev.detach_kernel_driver(0)
            print("  Done")
    except usb.core.USBError as e:
        print(f"  Could not detach kernel driver: {e}")
        print("  Try running with sudo, or the test may still work...")

    # Claim interface
    usb.util.claim_interface(dev, 0)
    print("Interface 0 claimed\n")

    # Find endpoints
    cfg = dev.get_active_configuration()
    intf = cfg[(0, 0)]
    ep_in = usb.util.find_descriptor(intf, custom_match=lambda e:
        usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_IN)
    ep_out = usb.util.find_descriptor(intf, custom_match=lambda e:
        usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_OUT)

    print(f"EP IN:  0x{ep_in.bEndpointAddress:02X} (size {ep_in.wMaxPacketSize})")
    print(f"EP OUT: 0x{ep_out.bEndpointAddress:02X} (size {ep_out.wMaxPacketSize})")
    print()

    # Test 1: Passive read (check if dongle sends anything)
    print("[1] Passive read (2 sec)...")
    count = 0
    start = time.time()
    while time.time() - start < 2.0:
        try:
            data = ep_in.read(ep_in.wMaxPacketSize, timeout=100)
            if data:
                count += 1
                print(f"  [{count}] {hex_dump(data)}")
        except usb.core.USBTimeoutError:
            pass
    print(f"  Got {count} packets\n")

    # Test 2: Write + read (Format A: [opcode, address, msg_id, ...])
    print("[2] Interrupt write (Format A: [opcode, addr, 0, ...])")
    test_packets = [
        ("GAME_START_STOP cube 0", [46, 0, 0, 0]),
        ("GAME_START_STOP cube 1", [46, 1, 0, 1]),
        ("TILT_REQUEST cube 1",    [33, 1, 0]),
        ("BUTTON_REQUEST cube 1",  [38, 1, 0]),
        ("APP_LIST_REQUEST cube 1",[70, 1, 0]),
        ("GRAPHICS_FILL cube 1",   [83, 1, 0, 0xE0]),  # red
    ]

    for desc, pkt_data in test_packets:
        pkt = bytearray(MSG_LEN)
        for i, b in enumerate(pkt_data):
            pkt[i] = b

        try:
            written = ep_out.write(bytes(pkt), timeout=1000)
            status = f"wrote {written}"
        except usb.core.USBTimeoutError:
            status = "TIMEOUT"
        except usb.core.USBError as e:
            status = f"ERROR: {e}"

        # Read response
        resp_str = ""
        try:
            resp = ep_in.read(ep_in.wMaxPacketSize, timeout=500)
            if resp:
                resp_str = hex_dump(resp)
                addr = resp[1] if len(resp) > 1 else -1
                label = "DONGLE" if addr == 0xFF else f"CUBE_{addr}"
                resp_str = f"[{label}] {resp_str}"
        except usb.core.USBTimeoutError:
            resp_str = "no response"

        print(f"  {desc}: {status} -> {resp_str}")
        time.sleep(0.05)
    print()

    # Test 3: Write + read (Format B: [addr, opcode, ...])
    print("[3] Interrupt write (Format B: [addr, opcode, ...])")
    for desc, pkt_data in [
        ("GAME_START_STOP cube 0", [0, 46, 0]),
        ("GAME_START_STOP cube 1", [1, 46, 1]),
    ]:
        pkt = bytearray(MSG_LEN)
        for i, b in enumerate(pkt_data):
            pkt[i] = b

        try:
            written = ep_out.write(bytes(pkt), timeout=1000)
            status = f"wrote {written}"
        except usb.core.USBTimeoutError:
            status = "TIMEOUT"
        except usb.core.USBError as e:
            status = f"ERROR: {e}"

        try:
            resp = ep_in.read(ep_in.wMaxPacketSize, timeout=500)
            resp_str = hex_dump(resp) if resp else "no response"
        except usb.core.USBTimeoutError:
            resp_str = "no response"

        print(f"  {desc}: {status} -> {resp_str}")
        time.sleep(0.05)
    print()

    # Test 4: Listen for cube events after sending game_start
    print("[4] Listen after GAME_START (5 sec)...")
    pkt = bytearray(MSG_LEN)
    pkt[0] = 46  # GAME_START_STOP
    pkt[1] = 1   # cube 1
    pkt[3] = 1   # mode = 1 (game active)
    try:
        ep_out.write(bytes(pkt), timeout=1000)
        print("  Sent GAME_START to cube 1")
    except Exception as e:
        print(f"  Write error: {e}")

    count = 0
    start = time.time()
    while time.time() - start < 5.0:
        try:
            data = ep_in.read(ep_in.wMaxPacketSize, timeout=200)
            if data:
                count += 1
                addr = data[1] if len(data) > 1 else -1
                op = data[0] if len(data) > 0 else -1
                label = "DONGLE" if addr == 0xFF else f"CUBE_{addr}"
                print(f"  [{count}] {label} op={op}: {hex_dump(data)}")
        except usb.core.USBTimeoutError:
            pass
    print(f"  Got {count} packets\n")

    # Cleanup
    usb.util.release_interface(dev, 0)
    print("Done.")


if __name__ == "__main__":
    main()
