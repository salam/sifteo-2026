"""Tests for legacy .siftapp helpers and install flow."""

import os
import sys
import tempfile
import zlib

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from sifteo.protocol import UPLOAD_OK, USB_MSG_LEN, Op
from sifteo.assets import (
    AssetManager,
    UploadError,
    SIFTAPP_MAGIC_PREFIX,
    SIFTAPP_MAGIC_SUFFIX,
    ensure_trailing_crc,
    extract_siftapp_payload,
    parse_siftapp_header,
)


class _DummyDongle:
    """No-op dongle for AssetManager unit tests."""

    def __init__(self):
        self.sent = []

    def send(self, msg, **kwargs):
        self.sent.append((msg, kwargs))

    def get_response_raw(self, timeout=None):
        return None


def _valid_siftapp_bytes(internal_id: int = 0x2A) -> bytes:
    token = bytes([0x1F, 0x53, internal_id & 0xFF, 0x20])
    return SIFTAPP_MAGIC_PREFIX + token + SIFTAPP_MAGIC_SUFFIX + b"\xAA\xBB\xCC"


class TestSiftAppHeader:
    def test_parse_valid_header(self):
        data = _valid_siftapp_bytes(internal_id=0x2A)
        header = parse_siftapp_header(data)
        assert header.valid is True
        assert header.internal_id == 0x2A
        assert header.token == 0x202A531F

    def test_parse_invalid_prefix(self):
        header = parse_siftapp_header(b"not-a-siftapp")
        assert header.valid is False
        assert header.internal_id is None
        assert header.token is None

    def test_parse_too_short(self):
        header = parse_siftapp_header(b"\x00" * 8)
        assert header.valid is False

    def test_ensure_trailing_crc_appends_when_missing(self):
        data = b"abc123"
        wrapped = ensure_trailing_crc(data)
        assert len(wrapped) == len(data) + 4
        assert wrapped.startswith(data)

    def test_ensure_trailing_crc_keeps_existing(self):
        data = ensure_trailing_crc(b"abc123")
        wrapped = ensure_trailing_crc(data)
        assert wrapped == data

    def test_extract_body_payload_from_valid_header(self):
        data = _valid_siftapp_bytes(internal_id=0x44) + b"\x01\x02\x03"
        body = extract_siftapp_payload(data, payload_shape="body")
        assert body == data[16:]

    def test_extract_body_payload_rejects_invalid_header(self):
        try:
            extract_siftapp_payload(b"not-a-valid-header", payload_shape="body")
            assert False, "Expected ValueError for invalid header"
        except ValueError as exc:
            assert "valid .siftapp header" in str(exc)


class TestInstallSiftApp:
    def test_install_uses_explicit_app_id(self):
        manager = AssetManager(_DummyDongle())
        captured = {}

        def _fake_upload(cube_id, app_id, asset_id, data, asset_type=0, progress=None):
            captured["cube_id"] = cube_id
            captured["app_id"] = app_id
            captured["asset_id"] = asset_id
            captured["size"] = len(data)
            return True

        manager.upload_bytes = _fake_upload  # type: ignore[method-assign]

        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "game.siftapp")
            raw = _valid_siftapp_bytes(internal_id=0x11)
            with open(path, "wb") as f:
                f.write(raw)

            result = manager.install_siftapp(
                cube_id=3, siftapp_path=path, app_id=1234, asset_id=9
            )

        assert captured["cube_id"] == 3
        assert captured["app_id"] == 1234
        assert captured["asset_id"] == 9
        assert captured["size"] == len(raw) + 4
        assert captured["size"] == result.bytes_uploaded
        assert result.app_id == 1234
        assert result.app_id_source == "explicit"

    def test_install_can_upload_siftapp_without_appended_crc(self):
        manager = AssetManager(_DummyDongle())
        captured = {}

        def _fake_upload(cube_id, app_id, asset_id, data, asset_type=0, progress=None):
            captured["size"] = len(data)
            return True

        manager.upload_bytes = _fake_upload  # type: ignore[method-assign]

        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "game.siftapp")
            raw = _valid_siftapp_bytes(internal_id=0x22)
            with open(path, "wb") as f:
                f.write(raw)

            result = manager.install_siftapp(
                cube_id=1,
                siftapp_path=path,
                payload_crc_mode="none",
            )

        assert captured["size"] == len(raw)
        assert result.bytes_uploaded == len(raw)
        assert result.payload_shape == "container"

    def test_install_can_upload_body_payload_shape(self):
        manager = AssetManager(_DummyDongle())
        captured = {}

        def _fake_upload(cube_id, app_id, asset_id, data, asset_type=0, progress=None):
            captured["data"] = data
            return True

        manager.upload_bytes = _fake_upload  # type: ignore[method-assign]

        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "game.siftapp")
            raw = _valid_siftapp_bytes(internal_id=0x22) + b"\x10\x11\x12\x13"
            with open(path, "wb") as f:
                f.write(raw)

            result = manager.install_siftapp(
                cube_id=1,
                siftapp_path=path,
                payload_shape="body",
                payload_crc_mode="none",
            )

        assert captured["data"] == raw[16:]
        assert result.bytes_uploaded == len(raw) - 16
        assert result.payload_shape == "body"

    def test_install_defaults_to_filename_crc32(self):
        manager = AssetManager(_DummyDongle())
        captured = {}

        def _fake_upload(cube_id, app_id, asset_id, data, asset_type=0, progress=None):
            captured["app_id"] = app_id
            return True

        manager.upload_bytes = _fake_upload  # type: ignore[method-assign]

        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "header_id.siftapp")
            with open(path, "wb") as f:
                f.write(_valid_siftapp_bytes(internal_id=0x35))

            result = manager.install_siftapp(cube_id=1, siftapp_path=path)

        expected = zlib.crc32(b"header_id") & 0xFFFFFFFF
        assert captured["app_id"] == expected
        assert result.app_id == expected
        assert result.app_id_source == "filename_crc32"
        assert result.header.valid is True

    def test_install_can_prefer_header_app_id(self):
        manager = AssetManager(_DummyDongle())
        captured = {}

        def _fake_upload(cube_id, app_id, asset_id, data, asset_type=0, progress=None):
            captured["app_id"] = app_id
            return True

        manager.upload_bytes = _fake_upload  # type: ignore[method-assign]

        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "header_id.siftapp")
            with open(path, "wb") as f:
                f.write(_valid_siftapp_bytes(internal_id=0x35))

            result = manager.install_siftapp(
                cube_id=1,
                siftapp_path=path,
                prefer_header_app_id=True,
            )

        assert captured["app_id"] == 0x35
        assert result.app_id == 0x35
        assert result.app_id_source == "header"
        assert result.header.valid is True

    def test_install_falls_back_to_filename_crc32(self):
        manager = AssetManager(_DummyDongle())
        captured = {}

        def _fake_upload(cube_id, app_id, asset_id, data, asset_type=0, progress=None):
            captured["app_id"] = app_id
            return True

        manager.upload_bytes = _fake_upload  # type: ignore[method-assign]

        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "my_legacy_game.siftapp")
            with open(path, "wb") as f:
                f.write(b"plain-bytes-without-valid-header")

            result = manager.install_siftapp(cube_id=1, siftapp_path=path)

        expected = zlib.crc32(b"my_legacy_game") & 0xFFFFFFFF
        assert captured["app_id"] == expected
        assert result.app_id == expected
        assert result.app_id_source == "filename_crc32"
        assert result.header.valid is False

    def test_install_rejects_unknown_payload_crc_mode(self):
        manager = AssetManager(_DummyDongle())

        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "bad_mode.siftapp")
            with open(path, "wb") as f:
                f.write(_valid_siftapp_bytes())

            try:
                manager.install_siftapp(
                    cube_id=1,
                    siftapp_path=path,
                    payload_crc_mode="weird",  # type: ignore[arg-type]
                )
                assert False, "Expected ValueError for invalid payload_crc_mode"
            except ValueError as exc:
                assert "payload_crc_mode" in str(exc)

    def test_install_rejects_body_payload_shape_for_invalid_header(self):
        manager = AssetManager(_DummyDongle())

        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "invalid.siftapp")
            with open(path, "wb") as f:
                f.write(b"not-a-valid-siftapp-header")

            try:
                manager.install_siftapp(
                    cube_id=1,
                    siftapp_path=path,
                    payload_shape="body",
                )
                assert False, "Expected ValueError for invalid body extraction"
            except ValueError as exc:
                assert "valid .siftapp header" in str(exc)


class TestUploadBytesResultParsing:
    def test_upload_bytes_reads_upload_result_status_without_nameerror(self):
        manager = AssetManager(_DummyDongle())

        # payload[4] is upload status, matching legacy response layout.
        upload_result_raw = bytes([0, 0, 0, 0, 0, 0, 0, UPLOAD_OK])
        manager._wait_for_either = lambda *a, **k: (upload_result_raw, True)  # type: ignore[method-assign]

        ok = manager.upload_bytes(
            cube_id=1,
            app_id=0x1234,
            asset_id=7,
            data=b"abc",
        )

        assert ok is True
        assert len(manager._dongle.sent) >= 2

    def test_upload_bytes_parses_event_layout_status_offset_6(self):
        manager = AssetManager(_DummyDongle())

        # Real-world event-queue shape where payload[7] carries status.
        upload_result_raw = bytes.fromhex(
            "00004918000000000006043752024375f2bbf676"
        ) + b"\x00" * 13
        manager._wait_for_either = lambda *a, **k: (upload_result_raw, False)  # type: ignore[method-assign]

        try:
            manager.upload_bytes(
                cube_id=0,
                app_id=0x1234,
                asset_id=0,
                data=b"abc",
            )
            assert False, "Expected UploadError for misalignment status"
        except UploadError as exc:
            assert "Flash alignment error on cube" in str(exc)

    def test_upload_bytes_uses_ack_synced_writes(self):
        manager = AssetManager(_DummyDongle())
        manager._wait_for_either = lambda *a, **k: (bytes([0, 0, 0, 0, 0, 0, 0, UPLOAD_OK]), True)  # type: ignore[method-assign]

        ok = manager.upload_bytes(
            cube_id=0,
            app_id=0x1234,
            asset_id=0,
            data=b"abcdef",
        )

        assert ok is True
        assert len(manager._dongle.sent) >= 2
        for _msg, kwargs in manager._dongle.sent:
            assert kwargs.get("wait_for_ack") is True

    def test_upload_chunk_payload_never_exceeds_message_budget(self):
        manager = AssetManager(_DummyDongle())
        manager._wait_for_either = lambda *a, **k: (bytes([0, 0, 0, 0, 0, 0, 0, UPLOAD_OK]), True)  # type: ignore[method-assign]

        manager.upload_bytes(
            cube_id=0,
            app_id=0x1234,
            asset_id=0,
            data=b"x" * 512,
        )

        max_payload = USB_MSG_LEN - 4
        for msg, _kwargs in manager._dongle.sent:
            if msg.opcode != Op.ASSET_UPLOAD:
                continue
            # Payload format: [byte_count, data..., seq_id]
            assert len(msg.payload) <= max_payload
            assert msg.payload[0] == len(msg.payload) - 1
