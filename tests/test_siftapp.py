"""Tests for legacy .siftapp helpers and install flow."""

import io
import json
import os
import struct
import sys
import tempfile
import zlib
import zipfile
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from sifteo.protocol import (
    UPLOAD_OK, UPLOAD_CRC_FAIL, UPLOAD_DISK_FULL,
    USB_OUT_MSG_LEN, Op,
)
from sifteo.assets import (
    AssetManager,
    CRCResult,
    SiftBundleAsset,
    UploadError,
    UploadResult,
    SIFTAPP_MAGIC_PREFIX,
    SIFTAPP_MAGIC_SUFFIX,
    align4,
    ensure_trailing_crc,
    extract_siftapp_bundle_assets,
    extract_siftapp_payload,
    parse_siftbndl,
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

    def get_event(self, timeout=None):
        return None


def _valid_siftapp_bytes(internal_id: int = 0x2A) -> bytes:
    token = bytes([0x1F, 0x53, internal_id & 0xFF, 0x20])
    return SIFTAPP_MAGIC_PREFIX + token + SIFTAPP_MAGIC_SUFFIX + b"\xAA\xBB\xCC"


def _build_sftbndl(entries):
    chunks = []
    for marker, width, height, payload in entries:
        chunks.append(bytes([ord(marker)]) + struct.pack("<HH", width, height) + payload)
    header_size = 3 + (len(chunks) * 4)
    offsets = []
    cursor = header_size
    for chunk in chunks:
        offsets.append(cursor)
        cursor += len(chunk)
    data = bytearray()
    data.extend(b"N")
    data.extend(struct.pack("<H", len(chunks)))
    for off in offsets:
        data.extend(struct.pack("<I", off))
    for chunk in chunks:
        data.extend(chunk)
    return bytes(data)


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

    def test_align4_pads_to_4_byte_boundary(self):
        assert align4(b"") == b""
        assert align4(b"\x01\x02\x03\x04") == b"\x01\x02\x03\x04"
        assert align4(b"\x01") == b"\x01\x00\x00\x00"
        assert align4(b"\x01\x02\x03") == b"\x01\x02\x03\x00"


class TestSiftBundleParsing:
    def test_parse_siftbndl_parses_marker_bounds_and_names(self):
        bundle = _build_sftbndl(
            [
                ("C", 10, 11, b"\x01\x02\x03"),
                ("R", 4, 5, b"\xAA"),
            ]
        )
        assets = parse_siftbndl(bundle, ["alpha", "beta"])

        assert len(assets) == 2
        assert assets[0].name == "alpha"
        assert assets[0].marker == "C"
        assert assets[0].width == 10
        assert assets[0].height == 11
        assert assets[0].payload == b"C" + struct.pack("<HH", 10, 11) + b"\x01\x02\x03"
        assert assets[1].name == "beta"
        assert assets[1].marker == "R"
        assert assets[1].width == 4
        assert assets[1].height == 5

    def test_parse_siftbndl_rejects_name_count_mismatch(self):
        bundle = _build_sftbndl([("C", 1, 1, b"\x00"), ("C", 2, 2, b"\x00")])
        try:
            parse_siftbndl(bundle, ["only-one-name"])
            assert False, "Expected ValueError for mismatched index count"
        except ValueError as exc:
            assert "Index entry count does not match" in str(exc)


class TestSiftAppBundleExtraction:
    def test_extract_siftapp_bundle_assets_from_manifest_and_bundle(self):
        bundle_names = ["arms", "start"]
        bundle_bytes = _build_sftbndl(
            [
                ("C", 20, 58, b"\x10\x11"),
                ("R", 128, 124, b"\x01\x02\x03"),
            ]
        )

        manifest = {
            "app": {
                "title": "Monster Greeting",
                "devAppID": "1009997",
                "imagesPath": "assets/images",
            }
        }
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("game/manifest.json", json.dumps(manifest))
            zf.writestr("game/assets/images/images_siftbndl_index.txt", "\n".join(bundle_names))
            zf.writestr("game/assets/images/images.sftbndl", bundle_bytes)

        with patch("sifteo.assets.decrypt_legacy_siftapp", return_value=buf.getvalue()):
            title, dev_app_id, assets = extract_siftapp_bundle_assets(b"ciphertext")

        assert title == "Monster Greeting"
        assert dev_app_id == 1009997
        assert [a.name for a in assets] == bundle_names
        assert [a.marker for a in assets] == ["C", "R"]


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
        assert captured["size"] == len(raw)  # default payload_crc_mode is "none"
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

    def test_install_bundle_uses_manifest_app_id_and_uploads_all_assets(self):
        manager = AssetManager(_DummyDongle())
        uploads = []

        def _fake_upload(cube_id, app_id, asset_id, data, asset_type=0, progress=None):
            uploads.append((cube_id, app_id, asset_id, asset_type, len(data)))
            return True

        manager.upload_bytes = _fake_upload  # type: ignore[method-assign]
        extracted = [
            SiftBundleAsset("a", 0, "C", 1, 1, b"C\x01\x00\x01\x00\xAA"),
            SiftBundleAsset("b", 1, "R", 2, 2, b"R\x02\x00\x02\x00\xBB"),
        ]

        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "bundle.siftapp")
            with open(path, "wb") as f:
                f.write(_valid_siftapp_bytes())

            with patch(
                "sifteo.assets.extract_siftapp_bundle_assets",
                return_value=("Bundle", 0x12345678, extracted),
            ):
                result = manager.install_siftapp(
                    cube_id=7,
                    siftapp_path=path,
                    install_mode="bundle",
                    asset_id=50,
                    payload_crc_mode="none",
                )

        assert result.install_mode == "bundle"
        assert result.asset_count == 2
        assert result.app_id == 0x12345678
        assert result.app_id_source == "manifest_dev_app_id"
        assert [u[2] for u in uploads] == [50, 51]
        assert all(u[1] == 0x12345678 for u in uploads)

    def test_install_auto_does_not_fallback_on_bundle_upload_error(self):
        manager = AssetManager(_DummyDongle())
        calls = {"count": 0}

        def _fake_upload(*args, **kwargs):
            calls["count"] += 1
            raise UploadError("bundle upload failed")

        manager.upload_bytes = _fake_upload  # type: ignore[method-assign]

        extracted = [SiftBundleAsset("a", 0, "C", 1, 1, b"C\x01\x00\x01\x00\xAA")]
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "bundle_auto.siftapp")
            with open(path, "wb") as f:
                f.write(_valid_siftapp_bytes())

            with patch(
                "sifteo.assets.extract_siftapp_bundle_assets",
                return_value=("Bundle", 0x1234, extracted),
            ):
                try:
                    manager.install_siftapp(
                        cube_id=1,
                        siftapp_path=path,
                        install_mode="auto",
                    )
                    assert False, "Expected UploadError from bundle upload"
                except UploadError as exc:
                    assert "bundle upload failed" in str(exc)

        assert calls["count"] == 1

    def test_install_bundle_aligns_payload_before_crc_append(self):
        manager = AssetManager(_DummyDongle())
        uploaded = []

        def _fake_upload(cube_id, app_id, asset_id, data, asset_type=0, progress=None):
            uploaded.append(data)
            return True

        manager.upload_bytes = _fake_upload  # type: ignore[method-assign]
        extracted = [SiftBundleAsset("a", 0, "C", 1, 1, b"C\x01\x00\x01\x00\xAA")]

        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "bundle_align.siftapp")
            with open(path, "wb") as f:
                f.write(_valid_siftapp_bytes())

            with patch(
                "sifteo.assets.extract_siftapp_bundle_assets",
                return_value=("Bundle", 0x1234, extracted),
            ):
                manager.install_siftapp(
                    cube_id=1,
                    siftapp_path=path,
                    install_mode="bundle",
                    payload_crc_mode="append",
                )

        assert len(uploaded) == 1
        # 6-byte payload => padded to 8, then +4-byte CRC => 12.
        assert len(uploaded[0]) == 12
        assert (len(uploaded[0]) - 4) % 4 == 0


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

        max_payload = USB_OUT_MSG_LEN - 4
        for msg, _kwargs in manager._dongle.sent:
            if msg.opcode != Op.ASSET_UPLOAD:
                continue
            # Payload format: [byte_count, data..., seq_id]
            assert len(msg.payload) <= max_payload
            assert msg.payload[0] == len(msg.payload) - 1


class TestUploadResult:
    def test_upload_result_ok(self):
        r = UploadResult(status=UPLOAD_OK, status_idx=6)
        assert r.ok is True
        assert r.crc_fail is False

    def test_upload_result_crc_fail(self):
        r = UploadResult(
            status=UPLOAD_CRC_FAIL, status_idx=6,
            original_crc=0xAABBCCDD, calculated_crc=0x11223344,
        )
        assert r.ok is False
        assert r.crc_fail is True
        assert r.original_crc == 0xAABBCCDD
        assert r.calculated_crc == 0x11223344

    def test_upload_result_disk_full(self):
        r = UploadResult(status=UPLOAD_DISK_FULL, status_idx=6)
        assert r.ok is False
        assert r.crc_fail is False


class TestCRCLearningUpload:
    def _make_manager_with_results(self, results, verify_crc_result=None):
        """Create an AssetManager that returns pre-set UploadResults.

        Args:
            results: list of UploadResult to return from successive _upload_raw calls.
            verify_crc_result: CRCResult or None to return from verify_crc.
        """
        manager = AssetManager(_DummyDongle())
        call_idx = {"i": 0}

        def _fake_upload_raw(cube_id, app_id, asset_id, data,
                             asset_type=0, progress=None):
            i = call_idx["i"]
            call_idx["i"] += 1
            return results[i]

        manager._upload_raw = _fake_upload_raw  # type: ignore[method-assign]
        manager.delete_asset = lambda *a, **k: True  # type: ignore[method-assign]
        manager.verify_crc = lambda *a, **k: verify_crc_result  # type: ignore[method-assign]
        return manager

    def test_learn_crc_succeeds_on_probe_ok(self):
        """If probe upload already succeeds, no re-upload is needed."""
        manager = self._make_manager_with_results([
            UploadResult(status=UPLOAD_OK, status_idx=6),
        ])
        ok = manager.upload_bytes_learn_crc(
            cube_id=1, app_id=0x1234, asset_id=0, data=b"test-data",
        )
        assert ok is True

    def test_learn_crc_probes_then_reuploads(self):
        """Probe fails with CRC_FAIL, learns CRC via verify_crc, re-uploads."""
        verify_result = CRCResult(original_crc=0x00000000, calculated_crc=0xDEADBEEF)
        manager = self._make_manager_with_results(
            [
                UploadResult(status=UPLOAD_CRC_FAIL, status_idx=6),
                UploadResult(status=UPLOAD_OK, status_idx=6),
            ],
            verify_crc_result=verify_result,
        )
        uploads = []
        orig_upload_raw = manager._upload_raw

        def _tracking_upload_raw(cube_id, app_id, asset_id, data,
                                 asset_type=0, progress=None):
            uploads.append(data)
            return orig_upload_raw(cube_id, app_id, asset_id, data,
                                   asset_type=asset_type, progress=progress)

        manager._upload_raw = _tracking_upload_raw  # type: ignore[method-assign]

        ok = manager.upload_bytes_learn_crc(
            cube_id=1, app_id=0x1234, asset_id=0, data=b"test",
        )
        assert ok is True
        assert len(uploads) == 2
        # Probe: data padded to 4 bytes + 4 zero bytes
        assert uploads[0].endswith(b"\x00\x00\x00\x00")
        # Final: data padded to 4 bytes + learned CRC from verify_crc
        assert uploads[1].endswith(struct.pack("<I", 0xDEADBEEF))

    def test_learn_crc_raises_on_non_crc_probe_failure(self):
        """Probe fails with DISK_FULL — should raise, not retry."""
        manager = self._make_manager_with_results([
            UploadResult(status=UPLOAD_DISK_FULL, status_idx=6),
        ])
        try:
            manager.upload_bytes_learn_crc(
                cube_id=1, app_id=0x1234, asset_id=0, data=b"test",
            )
            assert False, "Expected UploadError"
        except UploadError as exc:
            assert "non-CRC error" in str(exc)

    def test_learn_crc_raises_when_verify_crc_returns_none(self):
        """Probe CRC_FAIL but verify_crc returns nothing — data not stored."""
        manager = self._make_manager_with_results(
            [UploadResult(status=UPLOAD_CRC_FAIL, status_idx=6)],
            verify_crc_result=None,
        )
        try:
            manager.upload_bytes_learn_crc(
                cube_id=1, app_id=0x1234, asset_id=0, data=b"test",
            )
            assert False, "Expected UploadError"
        except UploadError as exc:
            assert "verify_crc returned no data" in str(exc)

    def test_learn_crc_raises_when_reupload_fails(self):
        """Learns CRC from verify_crc, but re-upload still fails."""
        verify_result = CRCResult(original_crc=0, calculated_crc=0xCAFEBABE)
        manager = self._make_manager_with_results(
            [
                UploadResult(status=UPLOAD_CRC_FAIL, status_idx=6),
                UploadResult(status=UPLOAD_CRC_FAIL, status_idx=6),
            ],
            verify_crc_result=verify_result,
        )
        try:
            manager.upload_bytes_learn_crc(
                cube_id=1, app_id=0x1234, asset_id=0, data=b"test",
            )
            assert False, "Expected UploadError"
        except UploadError as exc:
            assert "re-upload failed" in str(exc)


class TestInstallSiftAppLearnCRC:
    def test_install_bundle_with_learn_crc_mode(self):
        """Bundle install with payload_crc_mode='learn' calls learn method."""
        manager = AssetManager(_DummyDongle())
        learn_calls = []

        def _fake_learn(cube_id, app_id, asset_id, data,
                        asset_type=0, progress=None):
            learn_calls.append((cube_id, app_id, asset_id, len(data)))
            return True

        manager.upload_bytes_learn_crc = _fake_learn  # type: ignore[method-assign]

        extracted = [
            SiftBundleAsset("img0", 0, "C", 1, 1, b"C\x01\x00\x01\x00\xAA"),
            SiftBundleAsset("img1", 1, "R", 2, 2, b"R\x02\x00\x02\x00\xBB"),
        ]

        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "learn.siftapp")
            with open(path, "wb") as f:
                f.write(_valid_siftapp_bytes())

            with patch(
                "sifteo.assets.extract_siftapp_bundle_assets",
                return_value=("Learn Test", 0xABCD, extracted),
            ):
                result = manager.install_siftapp(
                    cube_id=5,
                    siftapp_path=path,
                    install_mode="bundle",
                    payload_crc_mode="learn",
                )

        assert result.install_mode == "bundle"
        assert result.asset_count == 2
        assert len(learn_calls) == 2
        assert learn_calls[0][0] == 5  # cube_id
        assert learn_calls[0][1] == 0xABCD  # app_id

    def test_install_opaque_with_learn_crc_mode(self):
        """Opaque install with payload_crc_mode='learn' calls learn method."""
        manager = AssetManager(_DummyDongle())
        learn_calls = []

        def _fake_learn(cube_id, app_id, asset_id, data,
                        asset_type=0, progress=None):
            learn_calls.append((cube_id, app_id, asset_id, len(data)))
            return True

        manager.upload_bytes_learn_crc = _fake_learn  # type: ignore[method-assign]

        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "opaque_learn.siftapp")
            raw = _valid_siftapp_bytes()
            with open(path, "wb") as f:
                f.write(raw)

            result = manager.install_siftapp(
                cube_id=2,
                siftapp_path=path,
                install_mode="opaque",
                payload_crc_mode="learn",
            )

        assert result.install_mode == "opaque"
        assert len(learn_calls) == 1
        assert learn_calls[0][2] == 0  # asset_id
