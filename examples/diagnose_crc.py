#!/usr/bin/env python3
"""Diagnostic script to understand ASSET_UPLOAD_RESULT layout and CRC learning.

Uploads a known .siftimg fixture in multiple ways to understand:
1. What the ASSET_UPLOAD_RESULT payload looks like on success vs CRC failure
2. Whether the cube stores data on CRC_FAIL (so verify_crc can read it)
3. Whether verify_crc-based CRC learning works

Usage:
    sudo python3.9 examples/diagnose_crc.py [cube_id]
"""

import os
import struct
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from sifteo.dongle import SifteoDongle
from sifteo.assets import AssetManager, align4
from sifteo.protocol import (
    Op, ASSET_TYPE_IMAGE,
    UPLOAD_OK, UPLOAD_CRC_FAIL, UPLOAD_DISK_FULL, UPLOAD_MISALIGNMENT,
)

FIXTURE_PATH = os.path.join(
    os.path.dirname(__file__), "..",
    "extracted/siftrunner/Siftrunner.app/Contents/Resources/"
    "runner/connector/usb/tests/fixtures/small.siftimg",
)

APP_ID = 0xDEAD0001
ASSET_ID = 0


def status_name(s):
    return {UPLOAD_OK: "OK", UPLOAD_CRC_FAIL: "CRC_FAIL",
            UPLOAD_DISK_FULL: "DISK_FULL", UPLOAD_MISALIGNMENT: "MISALIGN"}.get(s, f"?{s}")


def dump_upload_result(label, result, raw_payload):
    print(f"\n--- {label} ---")
    print(f"  status={status_name(result.status)} ({result.status}) at payload[{result.status_idx}]")
    if result.original_crc is not None:
        print(f"  original_crc  = 0x{result.original_crc:08X}  (at payload[{result.status_idx+1}:{result.status_idx+5}])")
        print(f"  calculated_crc= 0x{result.calculated_crc:08X}  (at payload[{result.status_idx+5}:{result.status_idx+9}])")
    else:
        print(f"  (no CRC values available, payload too short)")
    print(f"  raw payload[{len(raw_payload)}]: {raw_payload.hex()}")
    # Also show all u32 values from the payload for analysis
    print(f"  All u32 LE values in payload:")
    for i in range(0, len(raw_payload) - 3):
        val = struct.unpack_from("<I", raw_payload, i)[0]
        print(f"    [{i:2d}:{i+4:2d}] = 0x{val:08X}", end="")
        if i == result.status_idx + 1:
            print("  <-- orig_crc (relative)", end="")
        if i == result.status_idx + 5:
            print("  <-- calc_crc (relative)", end="")
        print()


def drain_all(dongle, limit=500):
    """Drain both response and event queues."""
    drained = 0
    while drained < limit:
        raw = dongle.get_response_raw(timeout=None)
        if raw is None:
            break
        drained += 1
    edrained = 0
    while edrained < limit:
        msg = dongle.get_event(timeout=None)
        if msg is None:
            break
        edrained += 1
    return drained, edrained


def main():
    cube_id = int(sys.argv[1]) if len(sys.argv) > 1 else 0

    if not os.path.exists(FIXTURE_PATH):
        print(f"Fixture not found: {FIXTURE_PATH}")
        sys.exit(1)

    with open(FIXTURE_PATH, "rb") as f:
        siftimg_data = f.read()

    print(f"Fixture: {FIXTURE_PATH}")
    print(f"  Size: {len(siftimg_data)} bytes")
    print(f"  Marker: {chr(siftimg_data[0])}")
    width = struct.unpack_from("<H", siftimg_data, 1)[0]
    height = struct.unpack_from("<H", siftimg_data, 3)[0]
    print(f"  Dimensions: {width}x{height}")
    trailing_crc = struct.unpack_from("<I", siftimg_data, len(siftimg_data) - 4)[0]
    print(f"  Trailing CRC: 0x{trailing_crc:08X}")
    body_no_crc = siftimg_data[:-4]
    print(f"  Body (no CRC): {len(body_no_crc)} bytes")

    dongle = SifteoDongle()
    dongle.open()
    print(f"\nDongle opened. Target cube: {cube_id}")

    # Discover cubes
    cubes = dongle.discover_cubes()
    if cube_id not in cubes:
        print(f"Cube {cube_id} not found! Available: {sorted(cubes)}")
        dongle.close()
        sys.exit(1)

    manager = AssetManager(dongle)

    # Clean slate
    print("\n=== Cleaning up ===")
    drain_all(dongle)
    manager.delete_all_assets(cube_id, APP_ID)
    time.sleep(1)
    drain_all(dongle)

    # We need _upload_raw to also return the raw payload bytes.
    # Monkey-patch _wait_for_either to capture raw bytes.
    _orig_wait = manager._wait_for_either
    _last_raw = [None]

    def _capturing_wait(*a, **k):
        result = _orig_wait(*a, **k)
        if result:
            _last_raw[0] = result[0]
        else:
            _last_raw[0] = None
        return result

    manager._wait_for_either = _capturing_wait

    # ============================================================
    # TEST 1: Upload full .siftimg (with valid CRC) — should succeed
    # ============================================================
    print("\n=== TEST 1: Upload full .siftimg (with valid CRC) ===")
    drain_all(dongle)
    result1 = manager._upload_raw(cube_id, APP_ID, ASSET_ID, siftimg_data)
    raw1 = _last_raw[0]
    payload1 = raw1[3:] if raw1 and len(raw1) > 3 else b""
    dump_upload_result("Full .siftimg (valid CRC)", result1, payload1)

    # Verify CRC after successful upload
    crc_result1 = manager.verify_crc(cube_id, APP_ID, ASSET_ID)
    if crc_result1:
        print(f"\n  verify_crc: orig=0x{crc_result1.original_crc:08X} "
              f"calc=0x{crc_result1.calculated_crc:08X} "
              f"valid={crc_result1.valid}")
    else:
        print(f"\n  verify_crc: TIMEOUT (no response)")

    # ============================================================
    # TEST 2: Delete, then upload body WITHOUT CRC + dummy zeros
    # ============================================================
    print("\n=== TEST 2: Upload body + dummy CRC (0x00000000) ===")
    manager.delete_all_assets(cube_id, APP_ID)
    time.sleep(1)
    drain_all(dongle)

    probe_data = align4(body_no_crc) + b"\x00\x00\x00\x00"
    print(f"  Probe data size: {len(probe_data)} bytes")
    print(f"  Last 8 bytes: {probe_data[-8:].hex()}")
    result2 = manager._upload_raw(cube_id, APP_ID, ASSET_ID, probe_data)
    raw2 = _last_raw[0]
    payload2 = raw2[3:] if raw2 and len(raw2) > 3 else b""
    dump_upload_result("Body + dummy CRC (0x00000000)", result2, payload2)

    # Try verify_crc AFTER failed upload to see if data was stored
    print("\n  Trying verify_crc after CRC_FAIL upload...")
    crc_result2 = manager.verify_crc(cube_id, APP_ID, ASSET_ID)
    if crc_result2:
        print(f"  verify_crc: orig=0x{crc_result2.original_crc:08X} "
              f"calc=0x{crc_result2.calculated_crc:08X} "
              f"valid={crc_result2.valid}")
        if not crc_result2.valid:
            print(f"  >> LEARNED CRC from verify_crc: 0x{crc_result2.calculated_crc:08X}")
    else:
        print(f"  verify_crc: TIMEOUT — data likely NOT stored on CRC_FAIL")

    # ============================================================
    # TEST 3: Delete, drain, upload body + fixture's known CRC
    # ============================================================
    print(f"\n=== TEST 3: Upload body + known CRC (0x{trailing_crc:08X}) ===")
    manager.delete_all_assets(cube_id, APP_ID)
    time.sleep(1)
    drain_all(dongle)

    known_crc_data = align4(body_no_crc) + struct.pack("<I", trailing_crc)
    print(f"  Data size: {len(known_crc_data)} bytes")
    print(f"  Last 8 bytes: {known_crc_data[-8:].hex()}")
    result3 = manager._upload_raw(cube_id, APP_ID, ASSET_ID, known_crc_data)
    raw3 = _last_raw[0]
    payload3 = raw3[3:] if raw3 and len(raw3) > 3 else b""
    dump_upload_result("Body + known CRC", result3, payload3)

    # ============================================================
    # TEST 4: If verify_crc learned a CRC, try uploading with it
    # ============================================================
    if crc_result2 and not crc_result2.valid:
        learned = crc_result2.calculated_crc
        print(f"\n=== TEST 4: Upload body + verify_crc-learned CRC (0x{learned:08X}) ===")
        manager.delete_all_assets(cube_id, APP_ID)
        time.sleep(1)
        drain_all(dongle)

        learned_data = align4(body_no_crc) + struct.pack("<I", learned)
        print(f"  Data size: {len(learned_data)} bytes")
        print(f"  Last 8 bytes: {learned_data[-8:].hex()}")
        result4 = manager._upload_raw(cube_id, APP_ID, ASSET_ID, learned_data)
        raw4 = _last_raw[0]
        payload4 = raw4[3:] if raw4 and len(raw4) > 3 else b""
        dump_upload_result("Body + verify-learned CRC", result4, payload4)

        if result4.ok:
            print("\n  >>> SUCCESS! verify_crc CRC learning works! <<<")
        else:
            print("\n  >>> FAILED: verify_crc CRC did not match <<<")

    # ============================================================
    # TEST 5: Upload body WITHOUT any CRC (raw .sftbndl record size)
    # ============================================================
    print(f"\n=== TEST 5: Upload raw body (no CRC appended, as-is) ===")
    manager.delete_all_assets(cube_id, APP_ID)
    time.sleep(1)
    drain_all(dongle)

    raw_body = align4(body_no_crc)
    print(f"  Data size: {len(raw_body)} bytes")
    result5 = manager._upload_raw(cube_id, APP_ID, ASSET_ID, raw_body)
    raw5 = _last_raw[0]
    payload5 = raw5[3:] if raw5 and len(raw5) > 3 else b""
    dump_upload_result("Raw body (no CRC)", result5, payload5)

    # Try verify_crc
    print("\n  Trying verify_crc after raw body upload...")
    crc_result5 = manager.verify_crc(cube_id, APP_ID, ASSET_ID)
    if crc_result5:
        print(f"  verify_crc: orig=0x{crc_result5.original_crc:08X} "
              f"calc=0x{crc_result5.calculated_crc:08X} "
              f"valid={crc_result5.valid}")
    else:
        print(f"  verify_crc: TIMEOUT")

    # Cleanup
    print("\n=== Cleanup ===")
    manager.delete_all_assets(cube_id, APP_ID)
    dongle.close()
    print("Done.")


if __name__ == "__main__":
    main()
