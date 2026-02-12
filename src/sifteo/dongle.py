"""
Sifteo V1 USB Dongle Communication Module.

Communicates with the Sifteo V1 USB dongle (nRF24LU1+) via USB.

Hardware Details:
    - Chip: Nordic nRF24LU1+ (USB 2.0 + 8-bit MCU + nRF24L01+ 2.4GHz radio)
    - VID: 0x22FA (Sifteo Inc.)
    - PID: 0x0101
    - Product: "Sifteo Wireless Link"
    - HID Interface: Vendor-defined usage page 0xFF00
    - EP 0x81 IN (Interrupt): 33 bytes  (dongle -> host)
    - EP 0x01 OUT (Interrupt): 34 bytes  (host -> dongle)

Note on macOS:
    The macOS HID driver claims this device automatically. The IOKit HID
    Manager's IOHIDDeviceSetReport does NOT work for this dongle's interrupt
    OUT endpoint (times out). We use pyusb/libusb for raw interrupt transfers
    instead, which requires detaching the kernel driver (needs root).

    Run with: sudo python3 -m sifteo
"""

from __future__ import annotations

import time
import threading
import queue
from typing import Optional

from .protocol import (
    Message, DONGLE_ADDRESS, USB_MSG_LEN, Op, op_name,
    cmd_dongle_version, cmd_disable_whitelist,
    cmd_request_paired_sifts, cmd_request_sift_ids,
)


# Sifteo V1 dongle USB identifiers
SIFTEO_VID = 0x22FA
SIFTEO_PID = 0x0101

# Endpoint sizes (from USB descriptors)
EP_IN_ADDR = 0x81
EP_OUT_ADDR = 0x01
EP_IN_SIZE = 33    # dongle -> host
EP_OUT_SIZE = 34   # host -> dongle (33 data bytes + 1 zero-pad)


class DongleNotFoundError(Exception):
    """Raised when no Sifteo dongle is detected."""
    pass


class DongleConnectionError(Exception):
    """Raised when communication with the dongle fails."""
    pass


class DongleWriteError(DongleConnectionError):
    """Raised when a write to the dongle fails."""
    pass


def enumerate_dongles() -> list[dict]:
    """List connected Sifteo dongles using hidapi (no root needed)."""
    try:
        import hid
        return hid.enumerate(SIFTEO_VID, SIFTEO_PID)
    except ImportError:
        pass

    # Fallback: pyusb
    try:
        import usb.core
        dev = usb.core.find(idVendor=SIFTEO_VID, idProduct=SIFTEO_PID)
        if dev:
            return [{"vendor_id": SIFTEO_VID, "product_id": SIFTEO_PID,
                      "product_string": "Sifteo Wireless Link"}]
    except ImportError:
        pass

    return []


class SifteoDongle:
    """Interface to the Sifteo V1 USB dongle.

    Uses pyusb/libusb for raw USB interrupt transfers, bypassing the
    macOS HID driver that doesn't properly support writes to this device.

    Incoming packets are sorted into two queues based on the address byte:
    - address == 0xFF: dongle responses (to commands we sent)
    - address != 0xFF: cube events (asynchronous sensor/state data)
    """

    def __init__(self):
        self._dev = None       # usb.core.Device
        self._ep_in = None     # IN endpoint
        self._ep_out = None    # OUT endpoint
        self._rx_thread: Optional[threading.Thread] = None
        self._running = False
        self._response_queue: queue.Queue = queue.Queue(5000)
        self._event_queue: queue.Queue = queue.Queue(5000)
        self._msg_id = 0

    def _next_msg_id(self) -> int:
        """Get next message ID (0-255 incrementing counter)."""
        mid = self._msg_id
        self._msg_id = (self._msg_id + 1) & 0xFF
        return mid

    @staticmethod
    def enumerate() -> list[dict]:
        """List all connected Sifteo dongles."""
        return enumerate_dongles()

    @staticmethod
    def is_connected() -> bool:
        """Check if a Sifteo dongle is plugged in."""
        return len(enumerate_dongles()) > 0

    def open(self) -> None:
        """Open a connection to the Sifteo dongle.

        Requires root on macOS to detach the kernel HID driver.
        Run with: sudo python3 -m sifteo

        Raises:
            DongleNotFoundError: If no dongle is found.
            DongleConnectionError: If the dongle cannot be opened.
        """
        import usb.core
        import usb.util

        if self._dev is not None:
            self.close()

        dev = usb.core.find(idVendor=SIFTEO_VID, idProduct=SIFTEO_PID)
        if dev is None:
            raise DongleNotFoundError(
                "No Sifteo dongle found. Make sure it's plugged in.\n"
                f"Looking for USB device VID=0x{SIFTEO_VID:04X} PID=0x{SIFTEO_PID:04X}"
            )

        # Detach kernel HID driver (requires root on macOS)
        try:
            if dev.is_kernel_driver_active(0):
                dev.detach_kernel_driver(0)
        except usb.core.USBError as e:
            raise DongleConnectionError(
                f"Cannot detach kernel driver: {e}\n"
                "On macOS, run with sudo: sudo python3 -m sifteo"
            ) from e

        # Claim the interface
        try:
            usb.util.claim_interface(dev, 0)
        except usb.core.USBError as e:
            raise DongleConnectionError(
                f"Cannot claim USB interface: {e}\n"
                "On macOS, run with sudo: sudo python3 -m sifteo"
            ) from e

        # Find endpoints
        cfg = dev.get_active_configuration()
        intf = cfg[(0, 0)]
        self._ep_in = usb.util.find_descriptor(
            intf, custom_match=lambda e:
            usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_IN
        )
        self._ep_out = usb.util.find_descriptor(
            intf, custom_match=lambda e:
            usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_OUT
        )

        if not self._ep_in or not self._ep_out:
            raise DongleConnectionError("Could not find IN/OUT endpoints")

        self._dev = dev
        print(f"Sifteo dongle opened: {dev.product}")
        print(f"  Manufacturer: {dev.manufacturer}")
        print(f"  EP IN:  0x{self._ep_in.bEndpointAddress:02X} ({self._ep_in.wMaxPacketSize} bytes)")
        print(f"  EP OUT: 0x{self._ep_out.bEndpointAddress:02X} ({self._ep_out.wMaxPacketSize} bytes)")

        self._start_rx()

    def close(self) -> None:
        """Close the dongle connection."""
        self._stop_rx()
        if self._dev is not None:
            import usb.util
            try:
                usb.util.release_interface(self._dev, 0)
            except Exception:
                pass
            try:
                self._dev.attach_kernel_driver(0)
            except Exception:
                pass
            self._dev = None
            self._ep_in = None
            self._ep_out = None
            print("Sifteo dongle closed.")

    @property
    def is_open(self) -> bool:
        return self._dev is not None

    # -- Sending --

    def send(self, msg: Message) -> None:
        """Send a protocol Message. Assigns msg_id automatically."""
        if self._dev is None:
            raise DongleConnectionError("Dongle not connected")
        msg.msg_id = self._next_msg_id()
        self._usb_write(msg.to_bytes())

    def _usb_write(self, data: bytes) -> None:
        """Write data via USB interrupt OUT transfer.

        Copies the 33-byte message into a 34-byte buffer (zero-padded).
        No HID report ID prefix — pyusb interrupt writes don't need one.
        """
        import usb.core

        padded = bytearray(EP_OUT_SIZE)
        n = min(len(data), EP_OUT_SIZE)
        padded[:n] = data[:n]

        try:
            written = self._ep_out.write(bytes(padded), timeout=1000)
            if written != EP_OUT_SIZE:
                raise DongleWriteError(
                    f"Short write: {written}/{EP_OUT_SIZE} bytes"
                )
        except usb.core.USBTimeoutError:
            raise DongleWriteError("Write timed out")
        except usb.core.USBError as e:
            raise DongleWriteError(f"Write failed: {e}") from e

    # -- Receiving --

    def get_event(self, timeout: Optional[float] = None) -> Optional[Message]:
        """Get the next cube event from the queue.

        Args:
            timeout: Seconds to wait. None = non-blocking.

        Returns:
            A Message from a cube, or None if no event available.
        """
        try:
            if timeout is not None:
                data = self._event_queue.get(block=True, timeout=timeout)
            else:
                data = self._event_queue.get_nowait()
            return Message.from_bytes(data)
        except queue.Empty:
            return None

    def get_response_raw(self, timeout: Optional[float] = None) -> Optional[bytes]:
        """Get the next raw dongle response from the response queue.

        Returns raw bytes (not parsed as Message), or None if empty.
        """
        try:
            if timeout is not None:
                return self._response_queue.get(block=True, timeout=timeout)
            else:
                return self._response_queue.get_nowait()
        except queue.Empty:
            return None

    # -- Synchronous Waiting (for asset operations) --

    def wait_for_event(self, opcode: int, timeout: float = 10.0) -> Optional[Message]:
        """Wait for a cube event with a specific opcode.

        Drains the event queue until a message with the matching opcode
        is found or the timeout expires. Non-matching events are discarded.

        Used for synchronous asset operations (inventory, CRC verify, etc.).
        Should NOT be called while the runner event loop is active.
        """
        deadline = time.time() + timeout
        while time.time() < deadline:
            remaining = deadline - time.time()
            if remaining <= 0:
                break
            msg = self.get_event(timeout=min(remaining, 0.5))
            if msg is not None and msg.opcode == opcode:
                return msg
        return None

    def wait_for_response(self, opcode: int, timeout: float = 10.0) -> Optional[bytes]:
        """Wait for a dongle response with a specific opcode.

        Drains the response queue until a message with the matching opcode
        is found or the timeout expires. Non-matching responses are discarded.

        Used for synchronous asset operations (upload result, delete, etc.).
        Should NOT be called while the runner event loop is active.
        """
        deadline = time.time() + timeout
        while time.time() < deadline:
            remaining = deadline - time.time()
            if remaining <= 0:
                break
            raw = self.get_response_raw(timeout=min(remaining, 0.5))
            if raw is not None and len(raw) >= 3 and raw[2] == opcode:
                return raw
        return None

    def collect_events(self, opcode: int, timeout: float = 4.0) -> list[Message]:
        """Collect all events with a specific opcode until timeout.

        Used for multi-response operations like asset inventory queries
        where multiple response messages are expected.
        """
        results = []
        deadline = time.time() + timeout
        while time.time() < deadline:
            remaining = deadline - time.time()
            if remaining <= 0:
                break
            msg = self.get_event(timeout=min(remaining, 0.5))
            if msg is None:
                if results:
                    break  # got some results and now timed out = done
                continue
            if msg.opcode == opcode:
                results.append(msg)
        return results

    # -- Discovery --

    def discover_cubes(self, max_attempts: int = 5) -> set[int]:
        """Discover connected cubes using the dongle's pairing protocol.

        Disables whitelist filtering, requests paired cubes, and collects
        responses. Retries up to max_attempts times.

        Returns a set of cube address IDs.
        """
        cubes: set[int] = set()

        # Drain stale data
        self._drain(1.0)

        for attempt in range(1, max_attempts + 1):
            # Step 1: Disable whitelist so we can see all cubes
            self.send(cmd_disable_whitelist())
            time.sleep(0.3)

            # Step 2: Verify dongle is responsive with version query
            self.send(cmd_dongle_version())
            resp = self.get_response_raw(timeout=1.0)
            if resp is None:
                print(f"  Attempt {attempt}/{max_attempts}: dongle not responding, retrying...")
                self._drain(0.5)
                time.sleep(1.0)
                continue

            # Step 3: Request paired cubes
            self.send(cmd_request_paired_sifts())

            # Step 4: Collect PAIRED_SIFT responses (3 seconds)
            deadline = time.time() + 3.0
            while time.time() < deadline:
                resp = self.get_response_raw(timeout=0.5)
                if resp is None:
                    continue
                if len(resp) >= 4 and resp[2] == Op.PAIRED_SIFT:
                    cubes.add(resp[3])

            # Step 5: Also try SIFT_IDS query
            self.send(cmd_request_sift_ids())
            deadline = time.time() + 2.0
            while time.time() < deadline:
                # Check response queue (SIFT_IDS with addr 0xFF)
                resp = self.get_response_raw(timeout=0.3)
                if resp is not None and len(resp) >= 4 and resp[2] == Op.SIFT_IDS:
                    count = resp[3]
                    for i in range(count):
                        if 4 + i < len(resp):
                            cubes.add(resp[4 + i])
                    break

                # Check event queue (SIFT_IDS with cube addr)
                evt = self.get_event(timeout=0.2)
                if evt is not None and evt.opcode == Op.SIFT_IDS:
                    if len(evt.payload) >= 1:
                        count = evt.payload[0]
                        for i in range(count):
                            if 1 + i < len(evt.payload):
                                cubes.add(evt.payload[1 + i])
                    break

            if cubes:
                print(f"  Found {len(cubes)} cube(s): {sorted(cubes)}")
                break

            print(f"  Attempt {attempt}/{max_attempts}: no cubes found, retrying...")
            self._drain(0.5)
            time.sleep(1.0)

        return cubes

    def _drain(self, duration: float) -> None:
        """Drain both queues for the given duration."""
        deadline = time.time() + duration
        while time.time() < deadline:
            try:
                self._response_queue.get_nowait()
            except queue.Empty:
                pass
            try:
                self._event_queue.get_nowait()
            except queue.Empty:
                pass
            time.sleep(0.01)

    # -- Background Receive Thread --

    def _start_rx(self) -> None:
        if self._running:
            return
        self._running = True
        self._rx_thread = threading.Thread(target=self._rx_loop, daemon=True)
        self._rx_thread.start()

    def _stop_rx(self) -> None:
        self._running = False
        if self._rx_thread is not None:
            self._rx_thread.join(timeout=2.0)
            self._rx_thread = None

    def _rx_loop(self) -> None:
        """Background receive loop. Sorts packets into response/event queues.

        Incoming format: [radio_msg_len, address, opcode, payload...]
        address == 0xFF goes to response_queue, else to event_queue.
        """
        import usb.core

        while self._running:
            if not self.is_open:
                time.sleep(0.01)
                continue
            try:
                data = self._ep_in.read(EP_IN_SIZE, timeout=100)
                if data and len(data) >= 3:
                    # Sort by address byte (index 1):
                    # 0xFF = dongle response, else = cube event
                    if data[1] == DONGLE_ADDRESS:
                        self._response_queue.put(bytes(data))
                    else:
                        self._event_queue.put(bytes(data))
            except usb.core.USBTimeoutError:
                pass
            except usb.core.USBError:
                if self._running:
                    time.sleep(0.01)

    # -- Context Manager --

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass
