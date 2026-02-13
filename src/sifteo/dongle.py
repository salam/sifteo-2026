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
    The macOS HID driver claims this device automatically. IOHIDDeviceSetReport
    does NOT work for this dongle's interrupt OUT endpoint (times out after ~5s).
    We use pyusb/libusb for raw interrupt transfers instead, which requires
    detaching the kernel driver (needs root).

    Run with: sudo python3 -m sifteo

Communication backends:
    - _PyUSBBackend: Uses pyusb/libusb for raw interrupt transfers. Requires
      detaching the kernel HID driver on macOS (needs root). Primary backend.
    - _HidapiBackend: Uses hidapi (IOHIDManager). Does NOT work on macOS for
      this device (write times out). Kept for potential Linux hidraw use.
"""

from __future__ import annotations

import abc
import os
import sys
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


def _read_env_float(name: str, default: float, minimum: float = 0.0) -> float:
    """Parse a non-negative float from environment, with fallback."""
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = float(raw)
    except ValueError:
        print(f"WARNING: ignoring invalid {name}={raw!r}; using {default}")
        return default
    if value < minimum:
        print(f"WARNING: ignoring {name}={raw!r}; must be >= {minimum}")
        return default
    return value


def _read_env_int(name: str, default: int, minimum: int = 0) -> int:
    """Parse a non-negative integer from environment, with fallback."""
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        print(f"WARNING: ignoring invalid {name}={raw!r}; using {default}")
        return default
    if value < minimum:
        print(f"WARNING: ignoring {name}={raw!r}; must be >= {minimum}")
        return default
    return value


# ---------------------------------------------------------------------------
# Communication backends
# ---------------------------------------------------------------------------

class _DongleBackend(abc.ABC):
    """Abstract interface for USB communication with the dongle."""

    @abc.abstractmethod
    def open(self) -> None: ...

    @abc.abstractmethod
    def close(self) -> None: ...

    @abc.abstractmethod
    def write(self, data: bytes) -> int:
        """Write a 33-byte protocol message. Returns bytes written."""
        ...

    @abc.abstractmethod
    def read(self, size: int, timeout_ms: int) -> Optional[bytes]:
        """Read up to *size* bytes. Returns None on timeout."""
        ...

    @property
    @abc.abstractmethod
    def is_open(self) -> bool: ...

    @property
    def name(self) -> str:
        return type(self).__name__


class _HidapiBackend(_DongleBackend):
    """hidapi/IOHIDManager backend (macOS, no root required).

    hidapi on macOS uses IOHIDManager under the hood. hid_write() calls
    IOHIDDeviceSetReport(kIOHIDReportTypeOutput) which goes through the
    kernel HID driver without needing to detach it.

    Buffer convention: hid_write() interprets buf[0] as report ID.
    With report ID 0x00, hidapi strips it and sends the remaining bytes.
    So we pass [0x00] + 33-byte message = 34 bytes total.
    """

    def __init__(self):
        self._dev = None  # hid.device instance

    def open(self) -> None:
        import hid
        self._dev = hid.device()
        self._dev.open(SIFTEO_VID, SIFTEO_PID)
        info = (self._dev.get_manufacturer_string() or "Sifteo")
        product = (self._dev.get_product_string() or "Wireless Link")
        print(f"Sifteo dongle opened (hidapi): {info} - {product}")

    def close(self) -> None:
        if self._dev is not None:
            self._dev.close()
            self._dev = None

    def write(self, data: bytes) -> int:
        # Prepend report ID 0x00; hidapi strips it before sending.
        buf = b'\x00' + bytes(data)
        return self._dev.write(buf)

    def read(self, size: int, timeout_ms: int) -> Optional[bytes]:
        data = self._dev.read(size, timeout_ms)
        if data:
            return bytes(data)
        return None

    @property
    def is_open(self) -> bool:
        return self._dev is not None


class _PyUSBBackend(_DongleBackend):
    """pyusb/libusb backend (requires root on macOS for kernel driver detach)."""

    def __init__(self):
        self._dev = None
        self._ep_in = None
        self._ep_out = None

    def open(self) -> None:
        import usb.core
        import usb.util

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
                "On macOS, try running with sudo if the hidapi backend is unavailable."
            ) from e

        try:
            usb.util.claim_interface(dev, 0)
        except usb.core.USBError as e:
            raise DongleConnectionError(
                f"Cannot claim USB interface: {e}"
            ) from e

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
        print(f"Sifteo dongle opened (pyusb): {dev.product}")
        print(f"  Manufacturer: {dev.manufacturer}")
        print(f"  EP IN:  0x{self._ep_in.bEndpointAddress:02X} ({self._ep_in.wMaxPacketSize} bytes)")
        print(f"  EP OUT: 0x{self._ep_out.bEndpointAddress:02X} ({self._ep_out.wMaxPacketSize} bytes)")

    def close(self) -> None:
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

    def write(self, data: bytes) -> int:
        # Zero-pad to EP_OUT_SIZE (34 bytes) for raw USB interrupt transfer
        padded = bytearray(EP_OUT_SIZE)
        n = min(len(data), EP_OUT_SIZE)
        padded[:n] = data[:n]
        return self._ep_out.write(bytes(padded), timeout=1000)

    def read(self, size: int, timeout_ms: int) -> Optional[bytes]:
        import usb.core
        try:
            data = self._ep_in.read(size, timeout=timeout_ms)
            if data:
                return bytes(data)
        except usb.core.USBTimeoutError:
            pass
        return None

    @property
    def is_open(self) -> bool:
        return self._dev is not None


def enumerate_dongles() -> list[dict]:
    """List connected Sifteo dongles using hidapi (no root needed).

    WARNING: On macOS, hidapi uses IOKit HID Manager which requires a
    CFRunLoop and must only be called from the main thread. Use
    enumerate_dongles_pyusb() for background threads.
    """
    try:
        import hid
        return hid.enumerate(SIFTEO_VID, SIFTEO_PID)
    except ImportError:
        pass

    # Fallback: pyusb
    return enumerate_dongles_pyusb()


def enumerate_dongles_pyusb() -> list[dict]:
    """List connected Sifteo dongles using pyusb only (thread-safe).

    Unlike enumerate_dongles(), this never calls hidapi and is safe to
    call from any thread on macOS.
    """
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
    macOS HID driver that doesn't support writes to this device.

    Incoming packets are sorted into two queues based on the address byte:
    - address == 0xFF: dongle responses (to commands we sent)
    - address != 0xFF: cube events (asynchronous sensor/state data)
    """

    # Minimum gap between consecutive USB writes (seconds).
    # The nRF24LU1+ has a small buffer and needs time to relay each
    # command over radio to the cubes.
    WRITE_MIN_GAP = 0.025     # 25 ms
    WRITE_MAX_RETRIES = 2     # retry on timeout before giving up
    WRITE_ACK_TIMEOUT = 5.0   # seconds waiting for dongle ACK
    ENV_WRITE_MIN_GAP = "SIFTEO_WRITE_MIN_GAP"
    ENV_WRITE_MAX_RETRIES = "SIFTEO_WRITE_MAX_RETRIES"
    ENV_WRITE_ACK_TIMEOUT = "SIFTEO_WRITE_ACK_TIMEOUT"

    def __init__(self):
        self._backend: Optional[_DongleBackend] = None
        self._rx_thread: Optional[threading.Thread] = None
        self._running = False
        self._response_queue: queue.Queue = queue.Queue(5000)
        self._event_queue: queue.Queue = queue.Queue(5000)
        self._msg_id = 0
        self._last_write_time = 0.0
        self._write_min_gap = _read_env_float(
            self.ENV_WRITE_MIN_GAP, self.WRITE_MIN_GAP, minimum=0.0
        )
        self._write_max_retries = _read_env_int(
            self.ENV_WRITE_MAX_RETRIES, self.WRITE_MAX_RETRIES, minimum=0
        )
        self._write_ack_timeout = _read_env_float(
            self.ENV_WRITE_ACK_TIMEOUT, self.WRITE_ACK_TIMEOUT, minimum=0.0
        )

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
        if self._backend is not None:
            self.close()

        # Note: hidapi (IOHIDManager) does NOT work on macOS for this device --
        # IOHIDDeviceSetReport times out on the interrupt OUT endpoint.
        # pyusb with kernel driver detach (root) is required.
        backend = _PyUSBBackend()
        backend.open()
        self._backend = backend
        self._start_rx()

    def close(self) -> None:
        """Close the dongle connection."""
        self._stop_rx()
        if self._backend is not None:
            self._backend.close()
            self._backend = None
            print("Sifteo dongle closed.")

    @property
    def is_open(self) -> bool:
        return self._backend is not None and self._backend.is_open

    # -- Sending --

    def send(self, msg: Message, *,
             wait_for_ack: bool = False,
             ack_timeout: Optional[float] = None) -> Optional[bytes]:
        """Send a protocol Message. Assigns msg_id automatically.

        When wait_for_ack is enabled, blocks for the dongle's write ACK and
        raises DongleWriteError if the ACK is missing or reports non-zero
        status. Returns the raw ACK packet when wait_for_ack is True.
        """
        if not self.is_open:
            raise DongleConnectionError("Dongle not connected")
        msg.msg_id = self._next_msg_id()
        self._usb_write(msg.to_bytes())
        if not wait_for_ack:
            return None

        timeout = self._write_ack_timeout if ack_timeout is None else max(0.0, ack_timeout)
        raw = self.get_response_raw(timeout=timeout if timeout > 0 else None)
        if raw is None:
            raise DongleWriteError(
                f"Timed out waiting for dongle ACK after write ({timeout:.3f}s)"
            )
        if len(raw) < 3:
            raise DongleWriteError(f"Dongle ACK packet too short: {raw.hex()}")

        status = raw[2]
        if status != 0:
            raise DongleWriteError(
                f"Dongle rejected write (status={status}, raw={raw[:12].hex()})"
            )
        return raw

    def _usb_write(self, data: bytes) -> None:
        """Write a 33-byte protocol message via the active backend.

        Rate-limits writes so the dongle's nRF24LU1+ chip can keep up,
        and retries on transient timeouts.
        """
        # Rate-limit: wait if we sent a write too recently
        now = time.time()
        gap = now - self._last_write_time
        if gap < self._write_min_gap:
            time.sleep(self._write_min_gap - gap)

        last_err = None
        for attempt in range(1 + self._write_max_retries):
            try:
                self._backend.write(data)
                self._last_write_time = time.time()
                return
            except Exception as e:
                last_err = e
                # Back off before retrying
                time.sleep(self._write_min_gap * (attempt + 1))

        raise DongleWriteError(
            f"Write failed after {1 + self._write_max_retries} attempts: {last_err}"
        )

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
        while self._running:
            if not self.is_open:
                time.sleep(0.01)
                continue
            try:
                data = self._backend.read(EP_IN_SIZE, timeout_ms=100)
                if data and len(data) >= 3:
                    # Sort by address byte (index 1):
                    # 0xFF = dongle response, else = cube event
                    if data[1] == DONGLE_ADDRESS:
                        self._enqueue_rx_packet(self._response_queue, bytes(data))
                    else:
                        self._enqueue_rx_packet(self._event_queue, bytes(data))
            except Exception:
                if self._running:
                    time.sleep(0.01)

    @staticmethod
    def _enqueue_rx_packet(target_queue: queue.Queue, packet: bytes) -> None:
        """Enqueue an RX packet without ever blocking the RX thread.

        During large asset uploads the dongle can emit a high volume of
        response/ACK packets. If a bounded queue fills up and `put()` blocks,
        the RX thread stops draining USB IN, which can eventually cause OUT
        writes to time out. To keep transport healthy, drop the oldest queued
        packet on overflow and keep the newest traffic.
        """
        try:
            target_queue.put_nowait(packet)
            return
        except queue.Full:
            pass

        try:
            target_queue.get_nowait()
        except queue.Empty:
            return

        try:
            target_queue.put_nowait(packet)
        except queue.Full:
            # Another producer/consumer race can refill the queue in between.
            # It's safe to drop this packet and continue receiving.
            return

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
