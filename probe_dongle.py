#!/usr/bin/env python3
"""
Sifteo V1 Dongle Probe Script v5 - Interactive Event & Graphics Test.

Built from reverse engineering of SiftRunner binary + decompiled Python SDK.

COMPLETE PROTOCOL REFERENCE:

Outgoing opcodes (host -> cube/dongle):
  1  SIFT_IDS         - Query connected cube list
  3  DONGLE_VERSION   - Query dongle firmware version
  5  ADD_WHITELIST     - Add 12-byte HW ID to whitelist
  6  REMOVE_WHITELIST  - Remove from whitelist (all-0xFF = clear)
  7  ENABLE_WHITELIST  - 0=disable, 1=enable whitelist filtering
  8  REQUEST_PAIRED    - Query paired/connected cubes
  33 TILT_REQUEST      - Request tilt events (starts stream, returns 128)
  36 NEIGHBOR_REQUEST  - Request neighbor events (returns 137)
  37 DEVICE_ID_REQUEST - Request hardware ID (returns 135)
  38 BUTTON_REQUEST    - Request button events (starts stream, returns 136)
  46 GAME_START_STOP   - 0=idle screen, 1=game mode
  63 CUBE_FW_VERSION   - Query cube firmware version
  81 GFX_DRAW          - Repaint display (rotation param)
  82 GFX_DRAW_RECT     - Draw rectangle: x, y, color, w, h
  83 GFX_FILL          - Fill screen with RGB332 color
  84 GFX_IMAGE         - Draw image from flash

Incoming opcodes (cube/dongle -> host):
   9 PAIRED_SIFT       - Cube paired and responding
  10 UNPAIRED_SIFT     - Cube was paired but disconnected
  11 NONPAIRED_DETECT  - Cube in range but not whitelisted
  16 WL_ENTRY_INFO     - Whitelist entry data
  17 WL_ENTRY_COUNT    - Number of whitelist entries
 128 TILT              - Tilt data: x, y, z
 133 NEIGHBOR          - Neighbor event: side, neighborID, neighborSide
 135 DEVICE_ID         - Hardware ID bytes
 136 BUTTON            - Button state: 0=released, 1=pressed
 137 NEIGHBOR_FULL     - Full neighbor report: 8 bytes (2 per side)
 140 BATTERY_LOW       - Battery level low warning
 141 FW_VERSION        - Firmware version report
 143 DOCK_STATE        - Dock state change
 145 SHAKE             - Shake: type(1=start,0=stop), duration_ms LE

USB format: [radio_msg_length, usb_msg_id, address, opcode, payload...]
  Address 0xFF = dongle, 0-15 = cube addresses
  Side indices: 0=up, 1=left, 2=down, 3=right

Usage: sudo python3.9 probe_dongle.py
"""

import sys
import time
import struct
import usb.core
import usb.util
import queue
import threading
import select

SIFTEO_VID = 0x22FA
SIFTEO_PID = 0x0101
EP_IN_SIZE = 33
EP_OUT_SIZE = 34
DONGLE_ADDRESS = 0xFF

# === OUTGOING OPCODES ===
OP_SIFT_IDS = 1
OP_DONGLE_VERSION = 3
OP_ADD_WHITELIST = 5
OP_REMOVE_WHITELIST = 6
OP_ENABLE_WHITELIST = 7
OP_REQUEST_PAIRED_SIFTS = 8
OP_DONGLE_BOOTLOADER = 12
OP_RF_SCAN_REPORT = 22
OP_RF_SCAN_REQUEST = 23
OP_TILT_REQUEST = 33
OP_NEIGHBOR_REQUEST = 36
OP_DEVICE_ID_REQUEST = 37
OP_BUTTON_REQUEST = 38
OP_GAME_START_STOP = 46
OP_ASSET_UPLOAD = 56
OP_REMOVE_APP = 58
OP_APP_DELETE_ASSET = 59
OP_APP_INFO_REQUEST = 60
OP_ASSET_INVENTORY_REQ = 61
OP_AVAILABLE_STORAGE = 62
OP_CUBE_FW_VERSION = 63
OP_ASSET_UPLOAD_HEADER = 68
OP_APP_LIST_REQUEST = 70
OP_GFX_DRAW = 81
OP_GFX_DRAW_RECT = 82
OP_GFX_FILL = 83
OP_GFX_IMAGE = 84
OP_GFX_PUT_PIXEL = 85
OP_GFX_SET_ROTATION = 86
OP_ASSET_VERIFY_CRC = 153
OP_FB_DUMP_REQUEST = 157
OP_ASSET_DUMP_REQUEST = 160

# === INCOMING OPCODES ===
OP_PAIRED_SIFT = 9
OP_UNPAIRED_SIFT = 10
OP_NONPAIRED_DETECTED = 11
OP_WHITELIST_ENTRY_INFO = 16
OP_WHITELIST_ENTRY_COUNT = 17
OP_FW_UPLOAD_COMPLETE = 45
OP_APP_LIST_RESP_HEADER = 71
OP_APP_LIST_RESP_ITEM = 72
OP_ASSET_UPLOAD_RESULT = 73
OP_ASSET_DELETE_COMPLETE = 74
OP_TILT = 128
OP_NEIGHBOR = 133
OP_DEVICE_ID = 135
OP_BUTTON = 136
OP_NEIGHBOR_FULL = 137
OP_ASSET_INV_RESPONSE = 138
OP_APP_INFO_RESPONSE = 139
OP_BATTERY_LOW = 140
OP_FW_VERSION = 141
OP_DOCK_STATE = 143
OP_DOCK_LOCATION = 144
OP_SHAKE = 145
OP_ASSET_VERIFY_CRC_RESP = 154
OP_FB_DL_HEADER = 158
OP_FB_DL_DATA = 159
OP_ASSET_DL_HEADER = 161
OP_ASSET_DL_DATA = 162
OP_REPAINT_BEGIN = 165

OP_NAMES = {
    1: "SIFT_IDS", 3: "DONGLE_VERSION",
    5: "ADD_WHITELIST", 6: "REMOVE_WHITELIST",
    7: "ENABLE_WHITELIST", 8: "REQUEST_PAIRED",
    9: "PAIRED_SIFT", 10: "UNPAIRED_SIFT",
    11: "NONPAIRED_DETECT", 12: "BOOTLOADER",
    16: "WL_ENTRY_INFO", 17: "WL_ENTRY_COUNT",
    22: "RF_SCAN_REPORT", 23: "RF_SCAN_REQUEST",
    33: "TILT_REQ", 36: "NEIGHBOR_REQ", 37: "DEVICE_ID_REQ",
    38: "BUTTON_REQ", 46: "GAME_START_STOP",
    56: "ASSET_UPLOAD", 58: "REMOVE_APP", 59: "DELETE_ASSET",
    60: "APP_INFO_REQ", 61: "ASSET_INV_REQ", 62: "AVAIL_STORAGE",
    63: "CUBE_FW_VERSION", 68: "ASSET_UPLOAD_HDR",
    70: "APP_LIST_REQ", 71: "APP_LIST_HDR", 72: "APP_LIST_ITEM",
    73: "ASSET_UPLOAD_RESULT", 74: "ASSET_DEL_COMPLETE",
    81: "GFX_DRAW", 82: "GFX_DRAW_RECT", 83: "GFX_FILL",
    84: "GFX_IMAGE", 85: "GFX_PUT_PIXEL", 86: "GFX_SET_ROTATION",
    128: "TILT", 133: "NEIGHBOR", 135: "DEVICE_ID",
    136: "BUTTON", 137: "NEIGHBOR_FULL",
    138: "ASSET_INV_RESP", 139: "APP_INFO_RESP",
    140: "BATTERY_LOW", 141: "FW_VERSION",
    143: "DOCK_STATE", 144: "DOCK_LOCATION",
    145: "SHAKE", 154: "CRC_VERIFY_RESP",
    157: "FB_DUMP_REQ", 158: "FB_DL_HDR", 159: "FB_DL_DATA",
    160: "ASSET_DUMP_REQ", 161: "ASSET_DL_HDR", 162: "ASSET_DL_DATA",
    165: "REPAINT_BEGIN",
}

SIDE_NAMES = ['up', 'left', 'down', 'right']
NULL_SIFTABLE_ID = 254

# RGB332 color helpers
def rgb332(r, g, b):
    """Convert 0-255 RGB to RGB332 byte."""
    return ((r >> 5) << 5) | ((g >> 5) << 2) | (b >> 6)

# Named colors in RGB332
COLOR_BLACK = 0x00
COLOR_WHITE = 0xFF
COLOR_RED = 0xE0
COLOR_GREEN = 0x1C
COLOR_BLUE = 0x03
COLOR_YELLOW = 0xFC
COLOR_CYAN = 0x1F
COLOR_MAGENTA = 0xE3
COLOR_ORANGE = 0xF0


def op_name(code):
    return OP_NAMES.get(code, f"UNKNOWN_0x{code:02X}")


def hex_dump(data, max_bytes=24):
    return ' '.join(f'{b:02X}' for b in data[:max_bytes])


class DongleProbe:
    def __init__(self):
        self.dev = None
        self.ep_in = None
        self.ep_out = None
        self.response_queue = queue.Queue(5000)
        self.event_queue = queue.Queue(5000)
        self._running = False
        self._rx_thread = None
        self._msg_id = 0

    def open(self):
        dev = usb.core.find(idVendor=SIFTEO_VID, idProduct=SIFTEO_PID)
        if dev is None:
            print("ERROR: No Sifteo dongle found")
            return False

        try:
            if dev.is_kernel_driver_active(0):
                dev.detach_kernel_driver(0)
        except (usb.core.USBError, NotImplementedError):
            pass

        usb.util.claim_interface(dev, 0)
        cfg = dev.get_active_configuration()
        intf = cfg[(0, 0)]

        self.ep_in = usb.util.find_descriptor(
            intf, custom_match=lambda e:
            usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_IN
        )
        self.ep_out = usb.util.find_descriptor(
            intf, custom_match=lambda e:
            usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_OUT
        )
        self.dev = dev
        print(f"Dongle opened: {dev.product} (bus {dev.bus}, addr {dev.address})")
        print(f"  EP IN:  0x{self.ep_in.bEndpointAddress:02X} ({self.ep_in.wMaxPacketSize} bytes)")
        print(f"  EP OUT: 0x{self.ep_out.bEndpointAddress:02X} ({self.ep_out.wMaxPacketSize} bytes)")
        self._start_rx()
        return True

    def close(self):
        self._running = False
        if self._rx_thread:
            self._rx_thread.join(timeout=2.0)
        if self.dev:
            try:
                usb.util.release_interface(self.dev, 0)
            except Exception:
                pass

    def _start_rx(self):
        self._running = True
        self._rx_thread = threading.Thread(target=self._rx_loop, daemon=True)
        self._rx_thread.start()

    def _rx_loop(self):
        while self._running:
            try:
                data = self.ep_in.read(EP_IN_SIZE, timeout=100)
                if data and len(data) >= 2:
                    if data[1] == DONGLE_ADDRESS:
                        self.response_queue.put(bytes(data))
                    else:
                        self.event_queue.put(bytes(data))
            except usb.core.USBTimeoutError:
                pass
            except usb.core.USBError:
                if self._running:
                    time.sleep(0.01)

    def write_raw(self, data):
        padded = bytearray(EP_OUT_SIZE)
        n = min(len(data), EP_OUT_SIZE)
        padded[:n] = data[:n]
        self.ep_out.write(bytes(padded), timeout=1000)

    def send(self, address, opcode, *payload):
        """Send: [radio_msg_len, msg_id, addr, opcode, payload...]"""
        inner_len = 2 + len(payload)
        msg = bytearray(33)
        msg[0] = inner_len & 0xFF
        msg[1] = self._msg_id & 0xFF
        msg[2] = address & 0xFF
        msg[3] = opcode & 0xFF
        for i, b in enumerate(payload):
            if 4 + i < 33:
                msg[4 + i] = b & 0xFF
        self._msg_id = (self._msg_id + 1) & 0xFF
        self.write_raw(bytes(msg))

    def send_and_recv(self, address, opcode, *payload, timeout=2.0):
        while not self.response_queue.empty():
            try:
                self.response_queue.get_nowait()
            except queue.Empty:
                break
        self.send(address, opcode, *payload)
        return self.get_response(timeout=timeout)

    def get_response(self, timeout=2.0):
        try:
            return self.response_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def get_event(self, timeout=0.1):
        try:
            return self.event_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def drain_all(self, duration=0.5):
        responses = []
        events = []
        end = time.time() + duration
        while time.time() < end:
            try:
                r = self.response_queue.get_nowait()
                responses.append(r)
            except queue.Empty:
                pass
            try:
                e = self.event_queue.get_nowait()
                events.append(e)
            except queue.Empty:
                pass
            time.sleep(0.005)
        return responses, events


def decode_event(data):
    """Decode a cube event into human-readable info."""
    if not data or len(data) < 3:
        return None

    addr = data[1]
    opcode = data[2]
    payload = data[3:] if len(data) > 3 else b''

    if addr == DONGLE_ADDRESS:
        # Dongle response
        if opcode == OP_PAIRED_SIFT and len(payload) >= 1:
            cube_addr = payload[0]
            hw_id = payload[1:13] if len(payload) >= 13 else payload[1:]
            hw_str = ' '.join(f'{b:02X}' for b in hw_id)
            return f"PAIRED_SIFT: cube={cube_addr} hw_id=[{hw_str}]"
        elif opcode == OP_UNPAIRED_SIFT and len(payload) >= 1:
            cube_addr = payload[0]
            return f"UNPAIRED_SIFT: cube={cube_addr}"
        elif opcode == OP_NONPAIRED_DETECTED:
            hw_id = payload[:12]
            hw_str = ' '.join(f'{b:02X}' for b in hw_id)
            return f"NONPAIRED_DETECTED: hw_id=[{hw_str}]"
        elif opcode == OP_WHITELIST_ENTRY_COUNT and len(payload) >= 1:
            return f"WHITELIST_COUNT: {payload[0]}"
        elif opcode == OP_SIFT_IDS and len(payload) >= 1:
            count = payload[0]
            ids = list(payload[1:1+count]) if count > 0 else []
            return f"SIFT_IDS: count={count} ids={ids}"
        elif opcode == OP_DONGLE_VERSION and len(payload) >= 3:
            return f"DONGLE_FW: {payload[0]}.{payload[1]}.{payload[2]}"
        else:
            return f"DONGLE_RESP: op={op_name(opcode)}"
    else:
        # Cube event
        if opcode == OP_TILT and len(payload) >= 3:
            x, y, z = payload[0], payload[1], payload[2]
            face = "DOWN" if z < 1 else ("UP" if z > 1 else "SIDE")
            return f"TILT: cube={addr} x={x} y={y} z={z} ({face})"
        elif opcode == OP_BUTTON and len(payload) >= 1:
            state = "PRESSED" if payload[0] else "RELEASED"
            return f"BUTTON: cube={addr} {state}"
        elif opcode == OP_NEIGHBOR and len(payload) >= 3:
            side, nid, nside = payload[0], payload[1], payload[2]
            side_name = SIDE_NAMES[side] if side < 4 else f"side{side}"
            if nid == NULL_SIFTABLE_ID:
                return f"NEIGHBOR: cube={addr} {side_name} -> NONE"
            else:
                nside_name = SIDE_NAMES[nside] if nside < 4 else f"side{nside}"
                return f"NEIGHBOR: cube={addr} {side_name} -> cube={nid} {nside_name}"
        elif opcode == OP_NEIGHBOR_FULL and len(payload) >= 8:
            sides = []
            # Order: down(2), right(3), up(0), left(1)
            order = [(2, 'down'), (3, 'right'), (0, 'up'), (1, 'left')]
            for i, (side_idx, side_name) in enumerate(order):
                nid = payload[i*2]
                nside = payload[i*2+1]
                if nid != NULL_SIFTABLE_ID:
                    nside_name = SIDE_NAMES[nside] if nside < 4 else f"s{nside}"
                    sides.append(f"{side_name}->c{nid}.{nside_name}")
            return f"NEIGHBOR_FULL: cube={addr} [{', '.join(sides) or 'none'}]"
        elif opcode == OP_SHAKE and len(payload) >= 1:
            if payload[0] == 1:
                return f"SHAKE: cube={addr} START"
            else:
                dur = 0
                if len(payload) >= 3:
                    dur = (payload[2] << 8) | payload[1]
                return f"SHAKE: cube={addr} STOP duration={dur}ms"
        elif opcode == OP_BATTERY_LOW:
            return f"BATTERY_LOW: cube={addr}"
        elif opcode == OP_FW_VERSION and len(payload) >= 3:
            return f"FW_VERSION: cube={addr} {payload[0]}.{payload[1]}.{payload[2]}"
        elif opcode == OP_DOCK_STATE and len(payload) >= 1:
            return f"DOCK_STATE: cube={addr} state={payload[0]}"
        elif opcode == OP_DEVICE_ID:
            hw_str = ' '.join(f'{b:02X}' for b in payload[:12])
            return f"DEVICE_ID: cube={addr} [{hw_str}]"
        else:
            return f"CUBE_EVENT: cube={addr} op={op_name(opcode)} payload={hex_dump(payload, 12)}"


def discover_cubes(probe, max_attempts=5):
    """Run the full discovery sequence with retries. Returns set of cube IDs.

    The dongle sometimes needs multiple attempts to respond after first being
    opened. This mirrors SiftRunner's behavior of retrying on startup.
    """
    cubes = set()

    print("=" * 64)
    print("DISCOVERY: Finding cubes")
    print("=" * 64)

    # Drain any stale data from previous sessions
    probe.drain_all(1.0)

    for attempt in range(1, max_attempts + 1):
        print(f"\n  Attempt {attempt}/{max_attempts}...")

        # Step 1: Disable whitelist to accept ALL cubes
        probe.send(DONGLE_ADDRESS, OP_ENABLE_WHITELIST, 0)
        time.sleep(0.3)

        # Step 2: Verify dongle is responsive with a version query
        probe.send(DONGLE_ADDRESS, OP_DONGLE_VERSION)
        time.sleep(0.2)
        version_resp = probe.get_response(timeout=1.0)
        if version_resp and len(version_resp) > 5:
            print(f"    Dongle firmware: {version_resp[3]}.{version_resp[4]}.{version_resp[5]}")
        else:
            print("    Dongle not responding yet, retrying...")
            probe.drain_all(0.5)
            time.sleep(1.0)
            continue

        # Step 3: Request paired sifts
        probe.send(DONGLE_ADDRESS, OP_REQUEST_PAIRED_SIFTS)
        time.sleep(0.5)

        # Step 4: Collect pairing responses for several seconds
        # Cubes take time to respond after the dongle starts scanning
        listen_duration = 3.0 if attempt == 1 else 5.0
        start = time.time()
        while time.time() - start < listen_duration:
            resp = probe.get_response(timeout=0.2)
            if resp and len(resp) > 2:
                decoded = decode_event(resp)
                if decoded:
                    print(f"    {decoded}")
                if resp[2] == OP_PAIRED_SIFT and len(resp) > 3:
                    cubes.add(resp[3])

            evt = probe.get_event(timeout=0.05)
            if evt:
                decoded = decode_event(evt)
                if decoded:
                    print(f"    {decoded}")

            # If we found cubes, keep listening briefly for more
            if cubes and time.time() - start > 2.0:
                break

        # Step 5: Also query SIFT_IDS to catch any we missed
        probe.send(DONGLE_ADDRESS, OP_SIFT_IDS)
        time.sleep(0.3)
        resp = probe.get_response(timeout=1.0)
        if resp and len(resp) > 3 and resp[2] == OP_SIFT_IDS:
            count = resp[3]
            if 0 < count < 20:
                ids = list(resp[4:4+count])
                cubes.update(ids)
                print(f"    SIFT_IDS: {count} cubes: {ids}")

        if cubes:
            break

        # No cubes yet — send another REQUEST_PAIRED_SIFTS and wait longer
        print("    No cubes found yet, re-scanning...")
        probe.send(DONGLE_ADDRESS, OP_REQUEST_PAIRED_SIFTS)
        probe.drain_all(1.5)

    # Drain remaining
    probe.drain_all(0.5)

    if cubes:
        print(f"\n  Found {len(cubes)} cube(s): {sorted(cubes)}")
    else:
        print(f"\n  No cubes found after {max_attempts} attempts!")
        print("  Make sure cubes are powered on and near the dongle.")

    return cubes


def initialize_cube(probe, cube_id):
    """Send initialization requests to a cube to start event streams.

    This reproduces Siftable.initialize_state() from the SDK:
      - ACCELEROMETER_TILT_REQUEST (33) -> starts tilt events
      - BUTTON_REPORT_REQUEST (38) -> starts button events
      - NEIGHBOR_REPORT_REQUEST (36) -> starts neighbor events
    """
    print(f"  Initializing cube {cube_id}...")

    # Put cube in game mode
    probe.send(cube_id, OP_GAME_START_STOP, 1)
    time.sleep(0.05)

    # Request initial state (this enables event streaming)
    probe.send(cube_id, OP_TILT_REQUEST)
    time.sleep(0.05)
    probe.send(cube_id, OP_BUTTON_REQUEST)
    time.sleep(0.05)
    probe.send(cube_id, OP_NEIGHBOR_REQUEST)
    time.sleep(0.05)

    print(f"    Cube {cube_id} initialized (tilt/button/neighbor events enabled)")


def event_monitor(probe, cubes, duration=30.0):
    """Monitor cube events in real time."""
    print()
    print("=" * 64)
    print(f"EVENT MONITOR ({duration:.0f}s)")
    print("  Watching for: tilt, button, shake, neighbor events")
    print("  Tilt/shake your cubes, press buttons, put them together!")
    print("=" * 64)

    start = time.time()
    event_count = 0
    last_tilt = {}

    while time.time() - start < duration:
        elapsed = time.time() - start

        # Check for cube events
        evt = probe.get_event(timeout=0.05)
        if evt and len(evt) >= 3:
            addr = evt[1]
            opcode = evt[2]
            decoded = decode_event(evt)

            # Suppress repeated tilt events (only show changes)
            if opcode == OP_TILT and len(evt) >= 6:
                tilt_key = (addr, evt[3], evt[4], evt[5])
                if last_tilt.get(addr) == tilt_key:
                    continue
                last_tilt[addr] = tilt_key

            if decoded:
                event_count += 1
                print(f"  [{elapsed:6.1f}s] {decoded}")

        # Check for dongle responses too
        resp = probe.get_response(timeout=0.01)
        if resp and len(resp) >= 3:
            decoded = decode_event(resp)
            if decoded:
                # Skip noisy SIFT_IDS responses
                if resp[2] != OP_SIFT_IDS:
                    print(f"  [{time.time()-start:6.1f}s] {decoded}")

    print(f"\n  Event monitor ended. {event_count} events received.")


def graphics_demo(probe, cubes):
    """Demo graphics commands on all cubes."""
    print()
    print("=" * 64)
    print("GRAPHICS DEMO")
    print("=" * 64)

    cube_list = sorted(cubes)

    # Cycle through colors
    colors = [
        ("RED", COLOR_RED),
        ("GREEN", COLOR_GREEN),
        ("BLUE", COLOR_BLUE),
        ("YELLOW", COLOR_YELLOW),
        ("CYAN", COLOR_CYAN),
        ("MAGENTA", COLOR_MAGENTA),
        ("WHITE", COLOR_WHITE),
    ]

    for name, color in colors:
        print(f"  Filling all cubes with {name} (0x{color:02X})...")
        for cid in cube_list:
            probe.send(cid, OP_GFX_FILL, color)
            time.sleep(0.02)
            probe.send(cid, OP_GFX_DRAW, 0)  # repaint
            time.sleep(0.02)
        time.sleep(0.8)
        # Drain responses
        probe.drain_all(0.1)

    # Draw rectangles
    print("\n  Drawing rectangles...")
    for i, cid in enumerate(cube_list):
        # Draw a colored rectangle on each cube
        x, y, w, h = 20, 20, 88, 88
        probe.send(cid, OP_GFX_FILL, COLOR_BLACK)
        time.sleep(0.02)
        color = colors[i % len(colors)][1]
        probe.send(cid, OP_GFX_DRAW_RECT, x, y, color, w, h)
        time.sleep(0.02)
        probe.send(cid, OP_GFX_DRAW, 0)
        time.sleep(0.02)
    time.sleep(1.0)
    probe.drain_all(0.2)

    # Pattern: each cube a different color
    print("\n  Assigning unique colors to each cube...")
    for i, cid in enumerate(cube_list):
        color = colors[i % len(colors)][1]
        name = colors[i % len(colors)][0]
        probe.send(cid, OP_GFX_FILL, color)
        time.sleep(0.02)
        probe.send(cid, OP_GFX_DRAW, 0)
        time.sleep(0.02)
        print(f"    Cube {cid}: {name}")
    time.sleep(1.0)
    probe.drain_all(0.2)

    print("  Graphics demo complete!")


HEARTBEAT_INTERVAL = 5.0  # seconds between SIFT_IDS polls in interactive mode


def interactive_mode(probe, cubes):
    """Interactive command mode."""
    print()
    print("=" * 64)
    print("INTERACTIVE MODE")
    print("  Commands:")
    print("    fill <color>     - Fill all cubes (red/green/blue/yellow/cyan/magenta/white/black)")
    print("    fill <cube> <c>  - Fill specific cube")
    print("    rect <cube> <x> <y> <w> <h> <color>  - Draw rectangle")
    print("    idle             - Put all cubes in idle mode")
    print("    game             - Put all cubes in game mode")
    print("    monitor [secs]   - Monitor events (default 30s)")
    print("    demo             - Run graphics demo")
    print("    scan             - RF spectrum scan")
    print("    status           - Query cube status")
    print("    rescan           - Full re-discovery of cubes")
    print("    wake             - Re-initialize all known cubes")
    print("    raw <addr> <op> [payload...]  - Send raw command")
    print("    quit             - Exit")
    print("=" * 64)

    color_map = {
        'red': COLOR_RED, 'green': COLOR_GREEN, 'blue': COLOR_BLUE,
        'yellow': COLOR_YELLOW, 'cyan': COLOR_CYAN, 'magenta': COLOR_MAGENTA,
        'white': COLOR_WHITE, 'black': COLOR_BLACK, 'orange': COLOR_ORANGE,
    }

    cube_list = sorted(cubes)

    def _bg_prompt():
        """Reprint prompt after background output."""
        try:
            sys.stdout.write("> ")
            sys.stdout.flush()
        except Exception:
            pass

    # Start a background event + heartbeat thread
    evt_running = [True]
    last_heartbeat = [time.time()]

    def bg_events():
        while evt_running[0]:
            # Check cube events
            evt = probe.get_event(timeout=0.1)
            if evt and len(evt) >= 3:
                decoded = decode_event(evt)
                if decoded:
                    print(f"\r  [EVENT] {decoded}")
                    _bg_prompt()

            # Check dongle responses for PAIRED/UNPAIRED notifications
            resp = probe.get_response(timeout=0.01)
            if resp and len(resp) >= 3:
                opcode = resp[2]
                if opcode == OP_PAIRED_SIFT and len(resp) >= 4:
                    cube_addr = resp[3]
                    if cube_addr not in cubes:
                        print(f"\r  [RECONNECT] Cube {cube_addr} paired! Initializing...")
                        initialize_cube(probe, cube_addr)
                        cubes.add(cube_addr)
                        cube_list.clear()
                        cube_list.extend(sorted(cubes))
                        _bg_prompt()
                    # else: already known, just a re-announce
                elif opcode == OP_UNPAIRED_SIFT and len(resp) >= 4:
                    cube_addr = resp[3]
                    if cube_addr in cubes:
                        print(f"\r  [DISCONNECT] Cube {cube_addr} went offline")
                        cubes.discard(cube_addr)
                        cube_list.clear()
                        cube_list.extend(sorted(cubes))
                        _bg_prompt()

            # Periodic heartbeat: poll SIFT_IDS to detect cube changes
            now = time.time()
            if now - last_heartbeat[0] >= HEARTBEAT_INTERVAL:
                last_heartbeat[0] = now
                try:
                    probe.send(DONGLE_ADDRESS, OP_SIFT_IDS)
                    time.sleep(0.2)
                    hb_resp = probe.get_response(timeout=0.5)
                    if hb_resp and len(hb_resp) > 3 and hb_resp[2] == OP_SIFT_IDS:
                        count = hb_resp[3]
                        active_ids = set(hb_resp[4:4 + count]) if 0 < count < 20 else set()

                        # Detect new/returning cubes
                        new_cubes = active_ids - cubes
                        for cid in new_cubes:
                            print(f"\r  [RECONNECT] Cube {cid} detected! Initializing...")
                            initialize_cube(probe, cid)
                            cubes.add(cid)
                            _bg_prompt()

                        # Detect gone cubes
                        gone_cubes = cubes - active_ids
                        for cid in gone_cubes:
                            print(f"\r  [SLEEP] Cube {cid} no longer responding")
                            cubes.discard(cid)
                            _bg_prompt()

                        if new_cubes or gone_cubes:
                            cube_list.clear()
                            cube_list.extend(sorted(cubes))
                except Exception:
                    pass  # heartbeat is best-effort

    evt_thread = threading.Thread(target=bg_events, daemon=True)
    evt_thread.start()

    try:
        while True:
            try:
                line = input("> ").strip()
            except EOFError:
                break
            if not line:
                continue

            parts = line.split()
            cmd = parts[0].lower()

            if cmd == 'quit' or cmd == 'q' or cmd == 'exit':
                break

            elif cmd == 'fill':
                if len(parts) == 2:
                    # fill <color> - all cubes
                    c = color_map.get(parts[1].lower())
                    if c is None:
                        try:
                            c = int(parts[1], 0)
                        except ValueError:
                            print(f"  Unknown color: {parts[1]}")
                            continue
                    for cid in cube_list:
                        probe.send(cid, OP_GFX_FILL, c)
                        time.sleep(0.02)
                        probe.send(cid, OP_GFX_DRAW, 0)
                        time.sleep(0.02)
                    print(f"  Filled all cubes with 0x{c:02X}")
                elif len(parts) == 3:
                    # fill <cube> <color>
                    try:
                        cid = int(parts[1])
                    except ValueError:
                        print(f"  Invalid cube ID: {parts[1]}")
                        continue
                    c = color_map.get(parts[2].lower())
                    if c is None:
                        try:
                            c = int(parts[2], 0)
                        except ValueError:
                            print(f"  Unknown color: {parts[2]}")
                            continue
                    probe.send(cid, OP_GFX_FILL, c)
                    time.sleep(0.02)
                    probe.send(cid, OP_GFX_DRAW, 0)
                    print(f"  Filled cube {cid} with 0x{c:02X}")
                probe.drain_all(0.1)

            elif cmd == 'rect':
                if len(parts) >= 7:
                    try:
                        cid = int(parts[1])
                        x, y, w, h = int(parts[2]), int(parts[3]), int(parts[4]), int(parts[5])
                        c = color_map.get(parts[6].lower())
                        if c is None:
                            c = int(parts[6], 0)
                        probe.send(cid, OP_GFX_DRAW_RECT, x, y, c, w, h)
                        time.sleep(0.02)
                        probe.send(cid, OP_GFX_DRAW, 0)
                        print(f"  Drew rect on cube {cid}: ({x},{y}) {w}x{h} color=0x{c:02X}")
                    except (ValueError, IndexError) as e:
                        print(f"  Error: {e}")
                else:
                    print("  Usage: rect <cube> <x> <y> <w> <h> <color>")
                probe.drain_all(0.1)

            elif cmd == 'idle':
                for cid in cube_list:
                    probe.send(cid, OP_GAME_START_STOP, 0)
                    time.sleep(0.02)
                print("  All cubes set to idle mode")
                probe.drain_all(0.1)

            elif cmd == 'game':
                for cid in cube_list:
                    probe.send(cid, OP_GAME_START_STOP, 1)
                    time.sleep(0.02)
                print("  All cubes set to game mode")
                probe.drain_all(0.1)

            elif cmd == 'monitor':
                dur = 30.0
                if len(parts) > 1:
                    try:
                        dur = float(parts[1])
                    except ValueError:
                        pass
                # Temporarily stop bg events
                evt_running[0] = False
                evt_thread.join(timeout=1)
                event_monitor(probe, cubes, dur)
                # Restart bg events
                evt_running[0] = True
                new_thread = threading.Thread(target=bg_events, daemon=True)
                new_thread.start()

            elif cmd == 'demo':
                evt_running[0] = False
                evt_thread.join(timeout=1)
                graphics_demo(probe, cubes)
                evt_running[0] = True
                new_thread = threading.Thread(target=bg_events, daemon=True)
                new_thread.start()

            elif cmd == 'scan':
                print("  Running RF spectrum scan...")
                scans = 50
                scan_bytes = [
                    (scans >> 24) & 0xFF, (scans >> 16) & 0xFF,
                    (scans >> 8) & 0xFF, scans & 0xFF,
                ]
                probe.send(DONGLE_ADDRESS, OP_RF_SCAN_REQUEST, *scan_bytes)
                scan_results = []
                scan_start = time.time()
                while time.time() - scan_start < 15.0:
                    resp = probe.get_response(timeout=0.5)
                    if resp and len(resp) > 7:
                        chan = resp[3]
                        total = (resp[4] << 8) | resp[5]
                        noisy = (resp[6] << 8) | resp[7]
                        scan_results.append((chan, total, noisy))
                    elif not resp:
                        break
                if scan_results:
                    noisy = [(c, t, n) for c, t, n in scan_results if n > 0]
                    clean = [(c, t, n) for c, t, n in scan_results if n == 0]
                    print(f"  {len(scan_results)} channels: {len(clean)} clean, {len(noisy)} noisy")
                    for c, t, n in noisy[:10]:
                        print(f"    CH{c}: {n}/{t} noisy samples")
                else:
                    print("  No scan results!")

            elif cmd == 'rescan':
                # Full re-discovery
                evt_running[0] = False
                evt_thread.join(timeout=1)
                print("  Running full cube re-discovery...")
                new_cubes = discover_cubes(probe)
                cubes.clear()
                cubes.update(new_cubes)
                cube_list.clear()
                cube_list.extend(sorted(cubes))
                # Re-initialize all
                for cid in cube_list:
                    initialize_cube(probe, cid)
                # Restart bg thread
                evt_running[0] = True
                last_heartbeat[0] = time.time()
                evt_thread = threading.Thread(target=bg_events, daemon=True)
                evt_thread.start()

            elif cmd == 'wake':
                # Re-initialize all known cubes (useful after sleep)
                if not cube_list:
                    print("  No cubes known. Use 'rescan' to discover cubes.")
                else:
                    print(f"  Re-initializing {len(cube_list)} cube(s)...")
                    for cid in cube_list:
                        initialize_cube(probe, cid)
                    probe.drain_all(0.5)
                    print("  Done! Cubes should be active again.")

            elif cmd == 'status':
                # Query dongle version
                resp = probe.send_and_recv(DONGLE_ADDRESS, OP_DONGLE_VERSION)
                if resp and len(resp) > 5:
                    print(f"  Dongle FW: {resp[3]}.{resp[4]}.{resp[5]}")

                # Query SIFT_IDS
                resp = probe.send_and_recv(DONGLE_ADDRESS, OP_SIFT_IDS)
                if resp and len(resp) > 3:
                    count = resp[3]
                    ids = list(resp[4:4+count]) if count > 0 else []
                    print(f"  Connected cubes: {count} -> {ids}")
                    # Update cubes set with current state
                    if ids:
                        new_ids = set(ids) - cubes
                        gone_ids = cubes - set(ids)
                        if new_ids:
                            print(f"  New cubes: {sorted(new_ids)}")
                            for cid in new_ids:
                                cubes.add(cid)
                                initialize_cube(probe, cid)
                            cube_list.clear()
                            cube_list.extend(sorted(cubes))
                        if gone_ids:
                            print(f"  Gone cubes: {sorted(gone_ids)}")

                # Query each cube's firmware
                for cid in cube_list:
                    probe.send(cid, OP_CUBE_FW_VERSION)
                    time.sleep(0.1)
                time.sleep(0.5)
                while True:
                    evt = probe.get_event(timeout=0.2)
                    if not evt:
                        break
                    decoded = decode_event(evt)
                    if decoded:
                        print(f"    {decoded}")

            elif cmd == 'raw':
                if len(parts) >= 3:
                    try:
                        addr = int(parts[1], 0)
                        op = int(parts[2], 0)
                        payload = [int(p, 0) for p in parts[3:]]
                        probe.send(addr, op, *payload)
                        print(f"  Sent: addr=0x{addr:02X} op=0x{op:02X} payload={payload}")
                        time.sleep(0.3)
                        # Show any responses
                        for _ in range(5):
                            resp = probe.get_response(timeout=0.2)
                            if resp:
                                decoded = decode_event(resp)
                                print(f"    RESP: {hex_dump(resp)} -> {decoded}")
                            else:
                                break
                    except ValueError as e:
                        print(f"  Error parsing: {e}")
                else:
                    print("  Usage: raw <addr> <opcode> [payload bytes...]")

            else:
                print(f"  Unknown command: {cmd}")

    finally:
        evt_running[0] = False


def main():
    probe = DongleProbe()
    if not probe.open():
        return

    cubes = set()
    try:
        # Phase 1: Discover cubes
        cubes = discover_cubes(probe)

        if not cubes:
            print("\nNo cubes found. Exiting.")
            return

        # Phase 2: Initialize all cubes (start event streams)
        print()
        print("=" * 64)
        print("INITIALIZING CUBES")
        print("  Sending tilt/button/neighbor requests to start event streams")
        print("  (from Siftable.initialize_state())")
        print("=" * 64)
        for cid in sorted(cubes):
            initialize_cube(probe, cid)
        time.sleep(0.5)

        # Drain initial responses
        print("\n  Initial state responses:")
        start = time.time()
        while time.time() - start < 2.0:
            evt = probe.get_event(timeout=0.1)
            if evt:
                decoded = decode_event(evt)
                if decoded:
                    print(f"    {decoded}")
            resp = probe.get_response(timeout=0.05)
            if resp:
                decoded = decode_event(resp)
                if decoded and "SIFT_IDS" not in decoded:
                    print(f"    {decoded}")

        # Phase 3: Quick event test
        print()
        print("=" * 64)
        print("EVENT TEST (10 seconds)")
        print("  Tilt cubes, press buttons, put them near each other!")
        print("=" * 64)
        event_monitor(probe, cubes, duration=10.0)

        # Phase 4: Graphics demo
        graphics_demo(probe, cubes)

        # Phase 5: Interactive mode
        interactive_mode(probe, cubes)

    except KeyboardInterrupt:
        print("\nInterrupted.")
    finally:
        print("\nCleaning up...")
        # Set cubes to idle mode
        for cid in cubes:
            try:
                probe.send(cid, OP_GAME_START_STOP, 0)
            except Exception:
                pass
        # Re-enable whitelist
        try:
            probe.send(DONGLE_ADDRESS, OP_ENABLE_WHITELIST, 1)
        except Exception:
            pass
        time.sleep(0.2)
        probe.close()
        print("Done.")


if __name__ == "__main__":
    main()
