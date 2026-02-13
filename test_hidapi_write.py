#!/usr/bin/env python3
"""
Diagnostic: Test hidapi write path for Sifteo dongle (no root required).

Validates that hid.device().write() works on macOS without sudo by sending
a DONGLE_VERSION query via IOHIDManager (hidapi) and reading the response.

If this script works without sudo, the root requirement can be eliminated
by switching dongle.py from pyusb to hidapi for communication.

Usage:
    python3 test_hidapi_write.py
"""

import sys
import time

SIFTEO_VID = 0x22FA
SIFTEO_PID = 0x0101


def build_dongle_version_query() -> bytes:
    """Build a 33-byte DONGLE_VERSION query message.

    Wire format: [radio_msg_len, msg_id, address, opcode, ...zero-padding]
    - radio_msg_len = 2 (address + opcode, no payload)
    - msg_id = 0
    - address = 0xFF (dongle)
    - opcode = 3 (DONGLE_VERSION)
    """
    msg = bytearray(33)
    msg[0] = 2       # radio_msg_len
    msg[1] = 0       # msg_id
    msg[2] = 0xFF    # address (dongle)
    msg[3] = 3       # opcode (DONGLE_VERSION)
    return bytes(msg)


def main():
    print("=" * 60)
    print("hidapi Write Diagnostic for Sifteo Dongle")
    print("=" * 60)
    print()

    # Step 1: Import hidapi
    try:
        import hid
    except ImportError:
        print("FAIL: hidapi not installed. Run: pip install hidapi")
        return False

    # Step 2: Enumerate
    print(f"[1/4] Enumerating VID=0x{SIFTEO_VID:04X} PID=0x{SIFTEO_PID:04X}...")
    devices = hid.enumerate(SIFTEO_VID, SIFTEO_PID)
    if not devices:
        print("  NOT FOUND - make sure dongle is plugged in")
        return False
    print(f"  Found {len(devices)} device(s)")
    for i, d in enumerate(devices):
        print(f"  [{i}] {d.get('product_string', '?')} "
              f"path={d.get('path', b'?')}")
    print()

    # Step 3: Open
    print("[2/4] Opening device via hidapi (no root)...")
    dev = hid.device()
    try:
        dev.open(SIFTEO_VID, SIFTEO_PID)
    except OSError as e:
        print(f"  FAIL: {e}")
        return False
    print(f"  Opened: {dev.get_manufacturer_string()} - {dev.get_product_string()}")
    print()

    # Step 4: Write (the critical test)
    print("[3/4] Sending DONGLE_VERSION query via hid_write()...")
    msg_33 = build_dongle_version_query()
    # hidapi on macOS: buf[0] is report ID. 0x00 = "no numbered reports".
    # hidapi strips the 0x00 and sends the remaining 33 bytes via
    # IOHIDDeviceSetReport(kIOHIDReportTypeOutput).
    write_buf = b'\x00' + msg_33  # 34 bytes total
    print(f"  Buffer: {len(write_buf)} bytes (report_id=0x00 + 33 msg bytes)")
    print(f"  First 8 bytes: {' '.join(f'{b:02X}' for b in write_buf[:8])}")

    try:
        t0 = time.time()
        written = dev.write(write_buf)
        dt_write = (time.time() - t0) * 1000
        print(f"  WRITE OK: {written} bytes returned in {dt_write:.1f}ms")
    except OSError as e:
        print(f"  WRITE FAIL: {e}")
        print()
        print("  IOHIDDeviceSetReport does not work for this device.")
        print("  Approach A (hidapi backend) will NOT work.")
        print("  Fall back to Approach C (privileged helper).")
        dev.close()
        return False
    print()

    # Step 5: Read response
    print("[4/4] Reading response (2s timeout)...")
    try:
        t0 = time.time()
        resp = dev.read(33, timeout_ms=2000)
        dt_read = (time.time() - t0) * 1000
    except OSError as e:
        print(f"  READ FAIL: {e}")
        dev.close()
        return False

    if not resp:
        print(f"  READ TIMEOUT after {dt_read:.1f}ms - no response received")
        print()
        print("  The write may have been silently dropped by IOHIDManager.")
        print("  Try also reading without writing (dongle may send unsolicited events).")

        # Bonus: try a second read to catch any cube events
        print()
        print("  Bonus: listening 3s for any unsolicited data...")
        for _ in range(30):
            data = dev.read(33, timeout_ms=100)
            if data:
                hex_str = ' '.join(f'{b:02X}' for b in data[:10])
                print(f"  Got {len(data)} bytes: {hex_str}...")
                break
        else:
            print("  No data received at all (device may not be sending).")

        dev.close()
        return False

    hex_str = ' '.join(f'{b:02X}' for b in resp[:10])
    print(f"  GOT {len(resp)} bytes in {dt_read:.1f}ms: {hex_str}...")

    # Parse: expect address=0xFF, opcode=3 (DONGLE_VERSION)
    if len(resp) >= 3 and resp[1] == 0xFF and resp[2] == 3:
        print()
        print("  SUCCESS! DONGLE_VERSION response received!")
        print(f"  radio_msg_len={resp[0]} address=0x{resp[1]:02X} opcode={resp[2]}")
        if len(resp) >= 7:
            print(f"  Version bytes: {' '.join(f'{b:02X}' for b in resp[3:7])}")
        print()
        print("  hidapi write+read works WITHOUT root on macOS.")
        print("  Approach A (hidapi backend) is VIABLE.")
        dev.close()
        return True
    else:
        print(f"  Got data but unexpected format (addr={resp[1]:02X} op={resp[2]:02X})")
        print("  This might be an unsolicited event, not our response.")
        print("  Trying one more read...")
        resp2 = dev.read(33, timeout_ms=1000)
        if resp2 and len(resp2) >= 3:
            hex2 = ' '.join(f'{b:02X}' for b in resp2[:10])
            print(f"  Second read: {hex2}...")
            if resp2[1] == 0xFF and resp2[2] == 3:
                print("  SUCCESS on second read!")
                dev.close()
                return True
        dev.close()
        return False


if __name__ == "__main__":
    ok = main()
    print()
    print("=" * 60)
    print(f"Result: {'PASS' if ok else 'FAIL'}")
    print("=" * 60)
    sys.exit(0 if ok else 1)
