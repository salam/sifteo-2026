"""Tests for sifteo.dongle backends and queue behavior."""

import os
import queue
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest

from sifteo.dongle import (
    SifteoDongle, DongleWriteError,
    _HidapiBackend, _PyUSBBackend,
    SIFTEO_VID, SIFTEO_PID, EP_OUT_SIZE,
)
from sifteo.protocol import Message, DONGLE_ADDRESS


# ---------------------------------------------------------------------------
# Helper: create a dongle with a mock backend so send() works
# ---------------------------------------------------------------------------

def _dongle_with_mock_backend():
    """Return a SifteoDongle with a mock backend (is_open=True)."""
    dongle = SifteoDongle()
    backend = MagicMock()
    backend.is_open = True
    dongle._backend = backend
    return dongle


# ---------------------------------------------------------------------------
# Queue overflow tests (unchanged from original)
# ---------------------------------------------------------------------------

def test_enqueue_rx_packet_keeps_latest_when_full():
    q = queue.Queue(maxsize=2)
    SifteoDongle._enqueue_rx_packet(q, b"a")
    SifteoDongle._enqueue_rx_packet(q, b"b")
    SifteoDongle._enqueue_rx_packet(q, b"c")

    assert q.qsize() == 2
    assert q.get_nowait() == b"b"
    assert q.get_nowait() == b"c"


def test_enqueue_rx_packet_adds_when_space_available():
    q = queue.Queue(maxsize=2)
    SifteoDongle._enqueue_rx_packet(q, b"x")
    SifteoDongle._enqueue_rx_packet(q, b"y")

    assert q.qsize() == 2
    assert q.get_nowait() == b"x"
    assert q.get_nowait() == b"y"


# ---------------------------------------------------------------------------
# Write tuning from env vars
# ---------------------------------------------------------------------------

def test_write_tuning_defaults_without_env(monkeypatch):
    monkeypatch.delenv("SIFTEO_WRITE_MIN_GAP", raising=False)
    monkeypatch.delenv("SIFTEO_WRITE_MAX_RETRIES", raising=False)
    dongle = SifteoDongle()
    assert dongle._write_min_gap == dongle.WRITE_MIN_GAP
    assert dongle._write_max_retries == dongle.WRITE_MAX_RETRIES


def test_write_tuning_reads_env(monkeypatch):
    monkeypatch.setenv("SIFTEO_WRITE_MIN_GAP", "0.005")
    monkeypatch.setenv("SIFTEO_WRITE_MAX_RETRIES", "5")
    dongle = SifteoDongle()
    assert dongle._write_min_gap == 0.005
    assert dongle._write_max_retries == 5


# ---------------------------------------------------------------------------
# ACK handshake tests (using mock backend)
# ---------------------------------------------------------------------------

def test_send_wait_for_ack_success():
    dongle = _dongle_with_mock_backend()
    dongle._response_queue.put_nowait(bytes([0, DONGLE_ADDRESS, 0]) + b"\x00" * 30)

    ack = dongle.send(
        Message(opcode=1, address=DONGLE_ADDRESS),
        wait_for_ack=True,
        ack_timeout=0.1,
    )

    assert ack is not None
    assert ack[2] == 0


def test_send_wait_for_ack_timeout_raises():
    dongle = _dongle_with_mock_backend()

    with pytest.raises(DongleWriteError, match="Timed out waiting for dongle ACK"):
        dongle.send(
            Message(opcode=1, address=DONGLE_ADDRESS),
            wait_for_ack=True,
            ack_timeout=0.01,
        )


def test_send_wait_for_ack_error_status_raises():
    dongle = _dongle_with_mock_backend()
    dongle._response_queue.put_nowait(bytes([0, DONGLE_ADDRESS, 3]) + b"\x00" * 30)

    with pytest.raises(DongleWriteError, match="Dongle rejected write"):
        dongle.send(
            Message(opcode=1, address=DONGLE_ADDRESS),
            wait_for_ack=True,
            ack_timeout=0.1,
        )


# ---------------------------------------------------------------------------
# _HidapiBackend tests
# ---------------------------------------------------------------------------

def test_hidapi_backend_write_prepends_report_id():
    """hid_write() expects [report_id, ...data]. We prepend 0x00."""
    backend = _HidapiBackend()
    mock_dev = MagicMock()
    mock_dev.write.return_value = 34
    backend._dev = mock_dev

    msg = bytes(range(33))  # 33-byte protocol message
    backend.write(msg)

    mock_dev.write.assert_called_once()
    written = mock_dev.write.call_args[0][0]
    assert len(written) == 34
    assert written[0:1] == b'\x00'  # report ID
    assert written[1:] == msg


def test_hidapi_backend_read_returns_none_on_empty():
    backend = _HidapiBackend()
    mock_dev = MagicMock()
    mock_dev.read.return_value = []
    backend._dev = mock_dev

    result = backend.read(33, timeout_ms=100)
    assert result is None


def test_hidapi_backend_read_returns_bytes():
    backend = _HidapiBackend()
    mock_dev = MagicMock()
    mock_dev.read.return_value = [0x02, 0xFF, 0x03] + [0] * 30
    backend._dev = mock_dev

    result = backend.read(33, timeout_ms=100)
    assert isinstance(result, bytes)
    assert len(result) == 33
    assert result[0] == 0x02
    assert result[1] == 0xFF


def test_hidapi_backend_is_open():
    backend = _HidapiBackend()
    assert not backend.is_open
    backend._dev = MagicMock()
    assert backend.is_open
    backend.close()
    assert not backend.is_open


# ---------------------------------------------------------------------------
# _PyUSBBackend tests
# ---------------------------------------------------------------------------

def test_pyusb_backend_write_pads_to_ep_out_size():
    """pyusb backend zero-pads 33-byte message to 34 bytes."""
    backend = _PyUSBBackend()
    mock_ep = MagicMock()
    mock_ep.write.return_value = EP_OUT_SIZE
    backend._ep_out = mock_ep
    backend._dev = MagicMock()

    msg = bytes(range(33))
    backend.write(msg)

    mock_ep.write.assert_called_once()
    written = mock_ep.write.call_args[0][0]
    assert len(written) == EP_OUT_SIZE  # 34
    assert written[:33] == msg
    assert written[33] == 0  # zero-pad


def test_pyusb_backend_is_open():
    backend = _PyUSBBackend()
    assert not backend.is_open
    backend._dev = MagicMock()
    assert backend.is_open


# ---------------------------------------------------------------------------
# Backend selection tests
# ---------------------------------------------------------------------------

def test_open_always_uses_pyusb_backend():
    """open() always uses _PyUSBBackend (hidapi does not work for writes)."""
    dongle = SifteoDongle()

    with patch("sifteo.dongle._PyUSBBackend") as MockPyUSB:
        MockPyUSB.return_value.is_open = True
        dongle.open()
        MockPyUSB.return_value.open.assert_called_once()

    dongle._running = False
    dongle._backend = None


def test_open_does_not_try_hidapi():
    """open() should not attempt _HidapiBackend (IOHIDDeviceSetReport fails)."""
    dongle = SifteoDongle()

    with patch("sifteo.dongle._HidapiBackend") as MockHidapi, \
         patch("sifteo.dongle._PyUSBBackend") as MockPyUSB:
        MockPyUSB.return_value.is_open = True
        dongle.open()
        MockHidapi.return_value.open.assert_not_called()

    dongle._running = False
    dongle._backend = None
