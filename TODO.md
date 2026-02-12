# TODO - Road to Uploading Games to Sifteo Cubes

## Asset Upload Pipeline

- [x] **Implement image asset encoding** - `encode_image()` converts PNG/BMP/JPEG to RGB332 + CRC via Pillow. Also `encode_image_rgb()` and `encode_image_rgba()` for raw pixel data. See `src/sifteo/assets.py`.

- [x] **Implement image upload** - `AssetManager.upload_bytes()` and `upload_file()` implement the chunked upload protocol (28 bytes/packet + seq ID). Handles upload result responses (OK / CRC fail / disk full / misalignment). See `src/sifteo/assets.py`.

- [x] **Implement sound asset encoding and upload** - `encode_sound()` converts WAV files (PCM 8/16/24/32-bit and IEEE float 32/64-bit) to 22050 Hz mono float32 samples + CRC. Handles stereo mixdown and sample rate resampling. `AssetManager.upload_sound()` encodes and uploads in one step. See `src/sifteo/assets.py`.

- [x] **Implement `blit_image` in the Cube API** - `Cube.image()` sends `GRAPHICS_IMAGE` (opcode 84) with app_id, asset_id, position, size, scale, and rotation. See `src/sifteo/cube.py`.

- [x] **Asset inventory and management** - `AssetManager` implements `query_app_info()` (60), `query_asset_inventory()` (61), `query_available_storage()` (62), `delete_all_assets()` (58), `delete_asset()` (59), and `query_app_list()` (70). See `src/sifteo/assets.py`.

- [x] **CRC verification** - `AssetManager.verify_crc()` implements `ASSET_VERIFY_CRC_REQUEST` (153) and parses the response with original and calculated CRC values. Also `upload_and_verify()` for combined upload + verify.

## Game Upload (Full .siftapp Support)

- [x] **Understand the .siftapp format** - Investigated: `.siftapp` files are .NET DLLs loaded via `Assembly.LoadFrom()`, communicating over JSON-RPC TCP localhost:7000. The original Python runner used `manifest.json` per app directory. **Decision:** We do NOT support the .NET DLL format. Our Python `BaseApp` subclass is the replacement -- the class itself serves as the manifest with `APP_NAME`, `IMAGES`, and `SOUNDS` class attributes.

- [x] **App registration on cubes** - `BaseApp` now supports declarative asset management: set `APP_NAME` (auto-generates 32-bit app_id via CRC32) or `APP_ID` (explicit), plus `IMAGES` and `SOUNDS` dicts mapping names to file paths. Assets are smart-synced to all cubes before `setup()` is called (only missing assets are uploaded). Use `self.app_id` and `self.asset_id("name")` in game code. See `src/sifteo/app.py` and `src/sifteo/assets.py`.

- [x] **Framebuffer download** - `AssetManager.download_framebuffer()` implements `FRAME_BUFFER_DUMP_REQUEST` (157) and parses the download response (158 header, 159 data chunks). Returns `FrameBuffer` with width, height, bpp, and raw pixel data.

## Platform & Runtime

- [ ] **Standalone command-line tool (no Python runtime)** - Build a self-contained binary that doesn't require a Python installation. Options:
  - PyInstaller or Nuitka to compile the Python package into a standalone macOS executable
  - Rewrite the core protocol layer in Rust or Go with `libusb` bindings for a truly native tool
  - Ship as a Homebrew formula with bundled Python

- [ ] **Linux support** - The `pyusb`/`libusb` stack should work on Linux with udev rules for non-root USB access. Needs testing and a udev rule file.

- [ ] **Windows support** - Requires a WinUSB or libusb-win32 driver for the dongle. The original SiftRunner included `sifthid.dll` for Windows; we'd need the equivalent via `pyusb`.

- [ ] **Remove root requirement on macOS** - Investigate using IOKit `IOHIDManager` with a codeless kext or DriverKit user-space driver to avoid needing `sudo`. Alternatively, a privileged helper tool installed once.

## Library Improvements

- [x] **Sound playback** - `SoundMixer` provides host-side sound playback (cubes have no speakers — the original SDK played sounds on the host via `siftx.sound`). Uses macOS `afplay` as a zero-dependency backend. Integrated into `BaseApp` as `self.sound`. See `src/sifteo/sound.py`.

- [x] **Firmware version checking** - `Cube.request_firmware_version()` sends `CUBE_FW_VERSION` (63); `FIRMWARE_VERSION` (141) response is parsed and stored as `cube.firmware_version`. Called automatically during `initialize_state()`. `FirmwareVersionEvent` dispatched to `BaseApp.on_firmware_version()`. See `src/sifteo/cube.py`.

- [x] **Battery level monitoring** - `BATTERY_LOW` (140) events set `cube.battery_low = True` and dispatch `BatteryLowEvent` to `BaseApp.on_battery_low()`. See `src/sifteo/cube.py`, `src/sifteo/app.py`.

- [x] **Dock state detection** - `DOCK_STATE` (143) and `DOCK_LOCATION` (144) events parsed in `handle_event()`, stored as `cube.docked` and `cube.dock_location`. `DockStateEvent` dispatched to `BaseApp.on_dock()`. See `src/sifteo/cube.py`, `src/sifteo/app.py`.

- [x] **Pixel-level drawing** - `Cube.put_pixel(x, y, r, g, b)` and `put_pixel_color(x, y, color_rgb8)` send `GRAPHICS_PUT_PIXEL` (85). See `src/sifteo/cube.py`, `src/sifteo/protocol.py`.

- [x] **Display rotation** - `Cube.orientation` setter now sends `GRAPHICS_SET_ROTATION` (86) to the cube hardware in addition to tracking state locally. See `src/sifteo/cube.py`, `src/sifteo/protocol.py`.

- [x] **Unit tests** - 79 tests in `tests/test_protocol.py` and `tests/test_cube.py` covering message serialization, pack/unpack helpers, color conversion, all command builders, all event types (tilt, button, neighbor, shake, battery, firmware, dock), display methods, orientation, and state management. All tests run without hardware using mock data.

## Documentation

- [x] **Asset format documentation** - Document the exact binary format for image and sound assets as found in the decrypted sources. See `docs/asset-formats.md`.

- [x] **Game development guide** - Write a tutorial for creating games with the `BaseApp` API, covering display, input, neighbors, and lifecycle. See `docs/game-development-guide.md`.
