# TODO - Road to Uploading Games to Sifteo Cubes

## Asset Upload Pipeline

- [ ] **Implement image asset encoding** - Convert PNG/BMP images to the cube's native format (compressed tiles, RGB332 palette). The original SDK used a custom asset pipeline in SiftRunner; the opcode (`ASSET_UPLOAD_HEADER` 68, `ASSET_UPLOAD` 56) and response (`ASSET_UPLOAD_RESULT` 73) are documented but the exact compression format needs to be verified against the decompiled `asset_helper.py`.

- [ ] **Implement image upload** - Send encoded image data to cube flash via the chunked upload protocol (28 bytes per packet + sequence ID). Handle upload result responses (OK / CRC fail / disk full / misalignment).

- [ ] **Implement sound asset encoding and upload** - Same upload protocol but for sound assets (type=1). Determine the audio format the cubes expect (sample rate, bit depth, compression).

- [ ] **Implement `blit_image` in the Cube API** - Wire up `GRAPHICS_IMAGE_TO_FRAMEBUFFER` (opcode 84) with proper app_id and asset_id parameters so uploaded images can be drawn to the screen.

- [ ] **Asset inventory and management** - Implement `APP_INFO_REQUEST` (60), `ASSET_INVENTORY_REQUEST` (61), `AVAILABLE_STORAGE` (62), and `APP_DELETE_ALL_ASSETS` (58) to query and manage assets stored on cube flash.

- [ ] **CRC verification** - Implement `ASSET_VERIFY_CRC_REQUEST` (153) to verify uploaded assets weren't corrupted.

## Game Upload (Full .siftapp Support)

- [ ] **Understand the .siftapp format** - The original SDK compiled games as .NET DLLs that communicated with SiftRunner via JSON-RPC over TCP (localhost:7000). Determine if we want to support this format or define a new Python-native game format.

- [ ] **App registration on cubes** - When uploading assets, each app has a 32-bit app ID. Implement app registration so cubes know which assets belong to which game.

- [ ] **Framebuffer download** - Implement `FRAME_BUFFER_DUMP_REQUEST` (157) and the download response handlers (158, 159) to read back what's currently on a cube's screen, useful for debugging asset rendering.

## Platform & Runtime

- [ ] **Standalone command-line tool (no Python runtime)** - Build a self-contained binary that doesn't require a Python installation. Options:
  - PyInstaller or Nuitka to compile the Python package into a standalone macOS executable
  - Rewrite the core protocol layer in Rust or Go with `libusb` bindings for a truly native tool
  - Ship as a Homebrew formula with bundled Python

- [ ] **Linux support** - The `pyusb`/`libusb` stack should work on Linux with udev rules for non-root USB access. Needs testing and a udev rule file.

- [ ] **Windows support** - Requires a WinUSB or libusb-win32 driver for the dongle. The original SiftRunner included `sifthid.dll` for Windows; we'd need the equivalent via `pyusb`.

- [ ] **Remove root requirement on macOS** - Investigate using IOKit `IOHIDManager` with a codeless kext or DriverKit user-space driver to avoid needing `sudo`. Alternatively, a privileged helper tool installed once.

## Library Improvements

- [ ] **Sound playback** - The protocol supports sound commands (`sound.play`, `sound.stop`, etc. via JSON-RPC) and the cube has audio output. Implement the sound API.

- [ ] **Firmware version checking** - Query and display cube firmware versions on startup; warn if incompatible with dongle firmware.

- [ ] **Battery level monitoring** - Handle `BATTERY_LOW` (140) events and expose battery state in the Cube API.

- [ ] **Dock state detection** - Handle `DOCK_STATE` (143) and `DOCK_LOCATION` (144) events for charging dock awareness.

- [ ] **Pixel-level drawing** - Expose `GRAPHICS_PUT_PIXEL` (85) in the Cube API for per-pixel drawing.

- [ ] **Display rotation** - Expose `GRAPHICS_SET_ROTATION` (86) so games can rotate the display orientation.

- [ ] **Unit tests** - Add tests for protocol encoding/decoding, message construction, color conversion, and event parsing (can run without hardware using mock data).

## Documentation

- [ ] **Asset format documentation** - Document the exact binary format for image and sound assets as found in the decrypted sources.

- [ ] **Game development guide** - Write a tutorial for creating games with the `BaseApp` API, covering display, input, neighbors, and lifecycle.
