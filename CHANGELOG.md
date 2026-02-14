<!-- markdownlint-disable MD024 -->
# Changelog

All notable changes to the Sifteo 2026 project are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased] - 2026-02-14

### Added

- **Sifteo Cube Manager GUI** (`python3 -m sifteo gui`): pywebview-based desktop app for browsing and installing the 23 bundled legacy games without the command line.
  - Dark-themed single-page app with landing screen (dongle detection, sudo escalation) and connected dashboard (game card grid, inline install progress).
  - Python<->JS bridge with status polling, connect/disconnect, game catalog, and install-with-progress.
  - Hand-curated metadata for all 23 `.siftapp` games (display names, categories, descriptions).
  - Automatic dongle detection (no root), macOS sudo relaunch via osascript, per-cube install targeting.
  - Toggleable console log panel at the bottom showing timestamped status, connection, install, and error messages from both JS frontend and Python bridge.
  - Settings panel (gear icon in topbar) with upload speed slider (logarithmic, 25 ms to 1 µs write gap) and write retries control, applied live to the dongle.
  - Cover art images for all 23 games extracted from original Sifteo Sync app resources and displayed on game cards in the dashboard.
  - Category filter dropdown (All, Installed, Action, Puzzle, Word, etc.) and sort buttons (A--Z, Size) in the game dashboard toolbar.
  - Custom macOS dock icon (original SifteoSync.icns) set via AppKit at launch.
  - **Observer tab** in dashboard for real-time cube visualization: cubes rendered as rounded squares with directional arrow, tilt-based 3D rotation, button press indicator, battery low warning, shake pulse animation (3 concentric rings), BFS neighbor-aware layout engine, and docking station grid (2x3 slot layout).
  - `pywebview>=5.0` as optional `[gui]` dependency (`pip install 'sifteo[gui]'`).
- Legacy `.siftapp` install support in `AssetManager` via `install_siftapp()`, including header parsing (`parse_siftapp_header`) and deterministic app ID inference.
- New `.siftapp` install result/header metadata types: `SiftAppInstallResult` and `SiftAppHeader`.
- New CLI command `python3 -m sifteo install-siftapp ...` for direct bundle installation to connected cubes.
- New helper launcher `examples/install_app.py` to install bundled apps by short name (`./examples/install_app.py <name> <cube_id>`).
- New fixture verification tool `examples/verify_fixture_upload.py` to upload known legacy `.siftimg` assets and validate cube-side CRC responses.
- `examples/verify_fixture_upload.py` now supports optional download roundtrip checks (`--roundtrip`) for byte-for-byte transport verification after CRC validation.
- New reverse-engineering helper `examples/analyze_siftapp.py` to inspect `.siftapp` headers, entropy/alignment characteristics, token/internal-id collisions, and optional crypto candidate scans.
- **CRC-learning upload** (`upload_bytes_learn_crc`): two-pass strategy that probes the cube's proprietary CRC algorithm by uploading with a dummy CRC, extracting the firmware-computed CRC from the `ASSET_UPLOAD_RESULT` response, then re-uploading with the correct CRC appended.  Exposed as `--payload-crc learn` in the CLI and used by default in `--payload-crc auto` for bundle-mode installs.
- `UploadResult` dataclass exposing per-upload status, status offset, and firmware-reported `original_crc`/`calculated_crc` values.
- Legacy `.siftapp` bundle extraction pipeline: AppPackager-compatible decrypt, ZIP unpack, `.sftbndl`/index parsing, and per-image asset install support.
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

- **Refactored dongle.py with backend abstraction** (`_DongleBackend`, `_PyUSBBackend`, `_HidapiBackend`). Investigated hidapi/IOHIDManager as a root-free alternative on macOS; confirmed that `IOHIDDeviceSetReport` does not work for this device's interrupt OUT endpoint (times out after ~5s). Root/sudo is still required on macOS. The backend abstraction is retained for future alternative approaches (privileged helper, Linux hidraw, etc.).
- `examples/install_app.py` now treats only cube target `all` as broadcast; numeric IDs (including `0`) target a specific cube.
- `examples/asset_upload.py` now accepts `.siftapp` files directly (auto/forced mode) and uses inferred app IDs when `--app-id` is omitted.
- Asset upload flow now accepts upload-result and delete-complete responses from either response or event queues for firmware compatibility.
- Asset uploads now perform legacy-style per-packet dongle ACK synchronization (header + data chunks) instead of fire-and-forget writes.
- Dongle write path now rate-limits and retries transient USB timeout writes.
- Dongle write pacing/retries can now be tuned via env vars: `SIFTEO_WRITE_MIN_GAP`, `SIFTEO_WRITE_MAX_RETRIES`, and `SIFTEO_WRITE_ACK_TIMEOUT`.
- `examples/install_app.py` now forwards `SIFTEO_WRITE_MIN_GAP`/`SIFTEO_WRITE_MAX_RETRIES`/`SIFTEO_WRITE_ACK_TIMEOUT` through `sudo` so upload tuning applies to helper-based installs.
- `examples/install_app.py` now forwards `PYTHONPATH` through `sudo` to guarantee it runs the workspace `src/sifteo` code instead of a stale globally installed module.
- `install-siftapp` now uses direct dongle + asset operations instead of full runner cube initialization, reducing extra radio traffic during installs.
- `.siftapp` installs now default app-ID inference to `crc32(filename_stem)`; header-ID inference is opt-in (`--prefer-header-app-id`) to avoid collisions across legacy bundles.
- `install-siftapp` now auto-tries compatibility variants (`crc/header` app-id and `asset-type` 0/1) when no explicit app-id/type is provided.
- `install-siftapp` `--payload-crc auto` now defaults to `learn` for bundle mode and tries `learn`/`none`/`append` for opaque mode, replacing the previous `none`/`append` order.
- `install-siftapp` `--payload-crc` now accepts `learn` in addition to `auto`, `append`, and `none`.
- Asset upload internals refactored: `upload_bytes()` delegates to `_upload_raw()` which returns a rich `UploadResult` with CRC details, enabling the CRC-learning two-pass strategy.
- `install-siftapp` now auto-tries `.siftapp` payload extraction shapes (`--payload-shape auto`): full container bytes and 16-byte-header-stripped body bytes. New `--payload-shape` flag allows forcing `container` or `body`.
- `install-siftapp` now defaults to `--install-mode auto`: tries bundle extraction/install first, then uses opaque upload only as fallback for non-extractable containers.
- Runner cube initialization now adds an inter-cube delay to reduce radio relay contention.
- `examples/asset_upload.py` now auto-detects image vs sound uploads by extension and supports WAV encoding directly.
- README expanded with event support examples and updated acknowledgements.
- `TODO.md` updated to mark completed asset pipeline, runtime improvements, tests, and docs work.

### Fixed

- Fixed `UPLOAD_RESULT_STATUS_IDX` from 4 to 6 to match the original SiftRunner C HID library offset (rply[8] after 2-byte header strip = our payload[6]), reducing false upload status misclassification.
- Increased dongle write ACK timeout from 5 s to 20 s to match the original SiftRunner's `write_msg(sync=20)` tolerance, preventing premature `DongleWriteError` on slow transfers.
- Added `logging.debug` output for raw `ASSET_UPLOAD_RESULT` packets and a `logging.warning` when the status byte is found at a non-authoritative fallback offset, aiding hardware-level protocol debugging.
- Fixed a long-upload transport stall where full RX queues could block the USB receive thread and trigger `DongleWriteError: Write timed out after 3 attempts` during large `.siftapp` installs.
- `python3 -m sifteo install-siftapp ...` now reports dongle write/connection failures per-cube as regular install failures instead of aborting with a traceback.
- Fixed `NameError: UPLOAD_RESULT_STATUS_IDX` in asset upload result parsing after full-data transfer completion.
- Fixed upload-result status decoding for firmware variants where `ASSET_UPLOAD_RESULT` reports status at an alternate payload offset (avoids false `Unknown upload status: 0` failures).
- Fixed upload-result status decoding priority to match legacy offset (`payload[6]`) before variant offsets, avoiding false misclassification of cube errors.
- Fixed a reliability gap where stale response packets and unsynchronized chunk writes could lead to `Flash alignment error on cube` during `.siftapp` installs.
- Improved upload failure messages to include decoded status index and raw payload bytes for protocol-level debugging.
- Fixed upload chunk sizing to respect the message payload budget (`USB_MSG_LEN - 4`) so full chunks are not truncated in transit (prevents false cube-side flash alignment failures).
- Fixed USB OUT framing to use a 34-byte transmit frame budget (`USB_OUT_MSG_LEN`) while keeping 33-byte IN parsing, restoring full legacy upload chunk payload capacity and preventing systematic CRC failures on known-good `.siftimg` fixtures.
- Asset uploads now explicitly send `GAME_START` to the target cube before transfer to avoid writing while cubes remain in idle/launcher state (which can manifest as consistent upload status 2 failures).
- Changed default `payload_crc_mode` from `"append"` to `"none"` for `.siftapp` installs. Analysis of original `.siftimg` fixture files confirmed the cube firmware uses a non-standard CRC algorithm (not zlib CRC32). Appending CRC32 bytes that the cube cannot validate caused systematic `CRC verification failed on cube (status=2)` failures during bundle-mode installs.
- Fixed `install-siftapp --install-mode auto` fallback behavior so upload failures in bundle mode are reported directly instead of being silently retried as opaque uploads.
- Fixed bundle-mode asset staging to 4-byte align extracted `.sftbndl` records before CRC append, preventing immediate `Flash alignment error on cube` on first chunk upload.
- Fixed GUI crash on launch (`EXC_BREAKPOINT` in `__CFCheckCFInfoPACSignature`) caused by calling `hid.enumerate()` from a background thread on macOS. GUI bridge now uses `enumerate_dongles_pyusb()` which is thread-safe.
- Fixed dongle connection failure ("The device has no langid") when USB string descriptors are unavailable. `dev.product`/`dev.manufacturer` reads are now wrapped in a try/except so the connection proceeds with fallback names.
- Fixed Observer tab neighbor layout: reverted to authoritative side numbering `0=top,1=left,2=bottom,3=right` (confirmed from decompiled Sifteo SDK `Cube.Side` enum and `SIDE_NAMES`). Added `NEIGHBOR_FULL_REPORT` (op 137) handler so neighbor state is populated on initial cube connection, not only on live add/remove events. Added neighbor debug logging to the console panel.

### Tests

- Added unit tests for `.siftapp` header parsing and install app-ID inference/upload wiring.
- Added dongle RX queue overflow unit tests to ensure latest packets are retained without blocking.
- Added dongle write-tuning unit tests for environment-based pacing/retry overrides.
- Added dongle ACK handshake tests and upload tests asserting ACK-synchronized writes.
- Added tests for default filename-based `.siftapp` app-ID inference and explicit opt-in header-ID behavior.
- Added `.siftapp` install tests for payload CRC mode handling (`append` vs raw/no-append) and input validation.
- Added `.sftbndl` parser tests, bundle extraction tests (manifest + bundle index), and install-mode tests for manifest app-ID usage and no-fallback-on-upload-error behavior.
- Added tests for bundle payload alignment/CRC staging and `align4()` helper behavior.
- Added `UploadResult` dataclass tests (`ok`, `crc_fail`, `disk_full` status variants).
- Added CRC-learning upload tests: probe-OK shortcut, probe-then-reupload with learned CRC, non-CRC probe failure, missing `calculated_crc`, and re-upload failure.
- Added `install_siftapp` tests for `payload_crc_mode="learn"` in both bundle and opaque modes.

## [0.1.0] - 2026-02-11

### Added

- Initial open-source baseline: USB dongle communication, protocol/message layer, cube abstraction, runner loop, and base app framework.
- Initial reverse-engineering references under `decompiled/` and `decrypted_py/`.
- Initial project docs and examples (`README.md`, `PROTOCOL.md`, `examples/hello_world.py`, `examples/asset_upload.py`).
