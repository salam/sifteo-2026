<!-- markdownlint-disable MD024 -->
# Changelog

All notable changes to the Sifteo 2026 project are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased] - 2026-02-12

### Added

- Declarative app asset manifests in `BaseApp` with `APP_NAME`/`APP_ID`, `IMAGES`, `SOUNDS`, `app_id`, and `asset_id()` support.
- Smart per-cube asset sync (`sync_app_assets`) with `AssetManifest`, `AssetDeclaration`, and `AssetSyncError`.
- Sound asset encoding (`encode_sound`) from WAV to 22050 Hz mono float32 with CRC, including PCM/float decode and resampling.
- Host-side sound playback API (`SoundMixer`) using `afplay`, exposed as `BaseApp.sound`.
- Cube APIs for `put_pixel`, `put_pixel_color`, firmware version requests, and hardware rotation command wiring.
- New event types and state handling for firmware version, battery low, dock state, and dock location.
- Example game `examples/hot_potato.py`.
- Documentation files `docs/asset-formats.md` and `docs/game-development-guide.md`.
- Unit test suite in `tests/` covering protocol serialization/builders and cube behavior/event parsing.
- Project media/artifacts: `sifteo-v1.jpg`, `power_up.wav`, and a preserved `sifteo-v1-doctormikereddy/Sifteo Sync.app` reference bundle.

### Changed

- Asset upload flow now accepts upload-result and delete-complete responses from either response or event queues for firmware compatibility.
- Dongle write path now rate-limits and retries transient USB timeout writes.
- Runner cube initialization now adds an inter-cube delay to reduce radio relay contention.
- `examples/asset_upload.py` now auto-detects image vs sound uploads by extension and supports WAV encoding directly.
- README expanded with event support examples and updated acknowledgements.
- `TODO.md` updated to mark completed asset pipeline, runtime improvements, tests, and docs work.

### Tests

- `pytest -q tests` passes (`79 passed`).

## [0.1.0] - 2026-02-11

### Added

- Initial open-source baseline: USB dongle communication, protocol/message layer, cube abstraction, runner loop, and base app framework.
- Initial reverse-engineering references under `decompiled/` and `decrypted_py/`.
- Initial project docs and examples (`README.md`, `PROTOCOL.md`, `examples/hello_world.py`, `examples/asset_upload.py`).
