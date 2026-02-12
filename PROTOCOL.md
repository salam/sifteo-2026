# Sifteo V1 Protocol Documentation

Reverse-engineered protocol documentation for Sifteo Cubes Series 1.

## Architecture

```
Game (.siftapp DLL)
  |  JSON-RPC over TCP localhost:7000
  v
SiftRunner (C++/Qt + PythonQt)
  |  USB HID (Interrupt transfers)
  v
Dongle (nRF24LU1+ @ 0x22FA:0x0101)
  |  2.4GHz nRF24L01+ Enhanced ShockBurst
  v
Cubes (STM32 ARM Cortex-M3 + nRF24L01+)
```

## USB Layer

### Dongle Hardware
- **Chip**: Nordic nRF24LU1+ (USB 2.0 + 8-bit 8051 MCU + nRF24L01+ 2.4GHz transceiver)
- **VendorID**: 0x22FA (Sifteo Inc.)
- **ProductID**: 0x0101
- **Manufacturer String**: "Sifteo Inc."
- **Product String**: "Sifteo Wireless Link"
- **USB Version**: 2.0

### HID Interface
- **Usage Page**: 0xFF00 (Vendor-Defined)
- **Usage**: 0x01
- **Input Report** (dongle -> host): 33 bytes, Interrupt EP1 IN
- **Output Report** (host -> dongle): 34 bytes, Interrupt EP1 OUT
- **No Report IDs** (single input/output report)

### Firmware Versions
| Version | File | Notes |
|---------|------|-------|
| 0.8.2 | (none) | Pre-release |
| 1.0.0 | dongle-v100.hex | Initial release |
| 1.1.4 | dongle_1_1_4.hex | Compatible with cube FW 1.1.0-1.1.4 |
| 1.1.5 | dongle_1_1_5.hex | Latest, compatible with cube FW 1.1.0-1.1.4 |

## JSON-RPC Protocol (Game <-> SiftRunner)

Games communicate with SiftRunner via JSON-RPC over TCP on localhost:7000.

### Game -> SiftRunner (Outgoing Calls)

| Method | Parameters | Description |
|--------|-----------|-------------|
| `app.init` | (none) | Initialize app, returns cubes/images/sounds/appID |
| `cube.fill` | `[sessionId, colorData]` | Fill entire screen with color |
| `cube.paint` | `[sessionId, rotation]` | Refresh/paint the display |
| `cube.image` | `[sessionId, name, x, y, w, h, srcX, srcY, scale, rotation]` | Draw image |
| `cube.fillRect` | `[sessionId, x, y, w, h, colorData]` | Fill rectangle |
| `sound.play` | `[name, volLeft, volRight, loops]` | Play sound, returns handle |
| `sound.stop` | `[handle]` | Stop sound |
| `sound.pause` | `[handle]` | Pause sound |
| `sound.resume` | `[handle]` | Resume sound |
| `sound.setVolume` | `[handle, volLeft, volRight]` | Set volume |
| `sound.pauseAll` | (none) | Pause all sounds |
| `sound.resumeAll` | (none) | Resume all sounds |
| `sound.stopAll` | (none) | Stop all sounds |

### SiftRunner -> Game (Incoming Events)

| Method | Parameters | Description |
|--------|-----------|-------------|
| `cube.tiltEvent` | `[sessionId, x, y, z]` | Accelerometer tilt data |
| `cube.shakeEvent` | `[sessionId, isShaking, duration]` | Shake detection |
| `cube.buttonEvent` | `[sessionId, isPressed]` | Button press/release |
| `cube.neighborEvent` | `[id1, side1, id2, side2]` | Neighbor add/remove (id2=254 = removed) |
| `cube.connectedEvent` | `[sessionId, hardwareID]` | Cube connected |
| `cube.disconnectedEvent` | `[sessionId]` | Cube disconnected |
| `app.pauseEvent` | (none) | App paused |
| `app.resumeEvent` | (none) | App resumed |
| `sound.startedEvent` | `[soundId]` | Sound started playing |
| `sound.stoppedEvent` | `[soundId]` | Sound stopped |
| `link.emptyEvent` | (none) | No pending data |

### app.init Response

```json
{
  "result": {
    "cubes": [
      {"id": 0, "hardwareID": "...", "buttonState": false, "tiltState": [1, 1, 2]}
    ],
    "images": [
      {"name": "image_name", "width": 128, "height": 128}
    ],
    "sounds": [
      {"name": "sound_name"}
    ],
    "appID": "com.example.game"
  }
}
```

## Cube Hardware

### V1 Cube Specifications
- **MCU**: STM32 ARM Cortex-M3 @ 72MHz
- **Flash**: 8MB
- **Display**: 128x128 pixel full-color LCD
- **Sensors**: 3-axis accelerometer
- **Radio**: nRF24L01+ 2.4GHz
- **Power**: Rechargeable Li-Po battery (~4 hours)
- **Neighbor Detection**: Proprietary near-field sensing (4 sides)

### Cube Sides
```
    TOP (0)
LEFT (1) [CUBE] RIGHT (3)
   BOTTOM (2)
```

### Tilt Data
- X, Y: 0 = tilt left/up, 1 = level, 2 = tilt right/down
- Z: 0 = face down, 2 = face up (upright)

### Constants
- `SCREEN_WIDTH` / `SCREEN_HEIGHT` = 128
- `NEIGHBOR_ID_NONE` = 254
- `NUM_SIDES` = 4

## Dongle Packet Protocol

**Status: FULLY DOCUMENTED** (decrypted from original Sifteo source)

### USB HID Transport

The dongle communicates via HID interrupt transfers:
- Host -> Dongle: 33 bytes per packet (USB_MSG_LEN)
- Dongle -> Host: 33 bytes per packet (USB_MSG_LEN)
- Dongle address: `0xFF`

### Packet Format

```
Byte 0: opcode (command/event type)
Byte 1: address (cube ID, or 0xFF for dongle)
Byte 2: message_id (sequence number, typically 0)
Bytes 3-32: payload (padded with zeros)
```

### Responses

The dongle distinguishes responses by byte 1:
- `data[1] == 0xFF` → dongle response (queued in response queue)
- `data[1] != 0xFF` → cube event (queued in event queue)

### Opcodes

#### Outgoing: Host -> Cube (Commands)

| Code | Name | Payload | Description |
|------|------|---------|-------------|
| 33 | `ACCELEROMETER_TILT_REQUEST` | (none) | Request current tilt state, returns opcode 128 |
| 36 | `NEIGHBOR_REPORT_REQUEST` | (none) | Request neighbor report, returns opcode 137 |
| 37 | `DEVICE_ID_REQUEST` | (none) | Request hardware ID, returns opcode 135 |
| 38 | `BUTTON_REPORT_REQUEST` | (none) | Request button state, returns opcode 136 |
| 46 | `GAME_START_STOP` | `[mode]` | mode=0: idle screen, mode=1: game active |
| 56 | `ASSET_UPLOAD` | `[byte_count, ...data, seq_id]` | Upload asset data chunk (max 28 bytes/packet) |
| 58 | `APP_DELETE_ALL_ASSETS` | `[appid_u32_le]` | Delete all assets for an app |
| 59 | `APP_DELETE_ASSET` | `[appid_u32_le, assetid_u16_le, type_u8]` | Delete specific asset |
| 60 | `APP_INFO_REQUEST` | `[appid_u32_le]` | Query app info, returns opcode 139 |
| 61 | `ASSET_INVENTORY_REQUEST` | `[appid_u32_le, count_u16_le]` | Query asset list, returns 138 |
| 62 | `AVAILABLE_STORAGE` | (none) | Query available storage |
| 68 | `ASSET_UPLOAD_HEADER` | `[size_u32_le, appid_u32_le, assetid_u16_le, type_u8]` | Start asset upload |
| 70 | `APP_LIST_REQUEST` | (none) | List installed apps, returns 72 |
| 81 | `GRAPHICS_DRAW` | `[rotation]` | Repaint display (rotation: 0-3) |
| 82 | `GRAPHICS_DRAW_RECT` | `[x, y, color_u8, w, h]` | Draw filled rectangle |
| 83 | `GRAPHICS_FILL` | `[color_u8]` | Fill screen with 8-bit RGB color |
| 84 | `GRAPHICS_IMAGE_TO_FRAMEBUFFER` | `[appid_u32_le, assetid_u16_le, x, y, srcX_u16_le, srcY_u16_le, w, h, rot_scale]` | Blit image asset to framebuffer |
| 85 | `GRAPHICS_PUT_PIXEL` | `[x, y, color]` | Draw single pixel |
| 86 | `GRAPHICS_SET_ROTATION` | `[rotation]` | Set display rotation |
| 153 | `ASSET_VERIFY_CRC_REQUEST` | `[appid_u32_le, assetid_u16_le, type_u8]` | Verify asset CRC |
| 157 | `FRAME_BUFFER_DUMP_REQUEST` | (none) | Download framebuffer from cube |
| 160 | `ASSET_DUMP_REQUEST` | `[appid_u32_le, assetid_u16_le, type_u8]` | Download asset from cube |

#### Incoming: Cube -> Host (Events)

| Code | Name | Payload | Description |
|------|------|---------|-------------|
| 1 | `SIFT_IDS` | varies | Cube identification |
| 128 | `tilt` | `[x, y, z]` | Accelerometer tilt (0=tilt, 1=level, 2=tilt) |
| 133 | `neighbor` | `[my_side, neighbor_id, neighbor_side]` | Neighbor add/remove event |
| 135 | `device_id` | `[id_bytes...]` | Hardware device ID |
| 136 | `button` | `[state]` | Button state (0=released, 1=pressed) |
| 137 | `neighbor_full_report` | `[side0_id, side0_side, ...]` | Full neighbor report |
| 138 | `ASSET_INVENTORY_RESPONSE` | `[..., assetid_u16, type_u8]` | Asset inventory item |
| 139 | `APP_INFO_RESPONSE` | `[..., images_u16, sounds_u16, bytes_u32]` | App info |
| 140 | `battery_level_low` | varies | Low battery warning |
| 141 | `firmware_version_report` | varies | Firmware version |
| 143 | `dock_state` | varies | Docking state change |
| 144 | `dock_location` | varies | Dock location |
| 145 | `shake` | varies | Shake event |
| 154 | `ASSET_VERIFY_CRC_RESPONSE` | `[..., orig_crc_u32, calc_crc_u32]` | CRC verification result |
| 158 | `FRAME_BUFFER_DOWNLOAD_HEADER` | `[w, h, bpp]` | Framebuffer download header |
| 159 | `FRAME_BUFFER_DOWNLOAD` | `[byte_count, ...data]` | Framebuffer data chunk |
| 161 | `ASSET_DOWNLOAD_HEADER` | `[size_u32_le, crc_u32_le]` | Asset download header |
| 162 | `ASSET_DOWNLOAD` | `[byte_count, ...data]` | Asset data chunk |
| 165 | `repaint_begin_report` | varies | Repaint started |

#### Dongle-Specific Commands (address=0xFF)

| Code | Name | Payload | Description |
|------|------|---------|-------------|
| 22 | `RF_SCAN_REPORT` | `[channel, total_hi, total_lo, noisy_hi, noisy_lo]` | RF scan result |
| 23 | `RF_SCAN_REQUEST` | `[scans_u32_be]` | Request RF channel scan |

### Graphics Protocol

#### Image Blit (opcode 84)
The `rot_scale` byte combines rotation and scale:
```
rot_scale = (rotation << 6) | (scale & 0x3F)
```
Where rotation is 0-3 (90-degree increments) and scale is 0-63.

#### Color Format
Colors are 8-bit RGB (3-3-2 format: RRRGGGBB).

### Asset Types
- `0` = Image
- `1` = Sound

### Asset Upload Protocol
1. Send `ASSET_UPLOAD_HEADER` (opcode 68) with size, app ID, asset ID, type
2. Wait 3 seconds for header processing
3. Send `ASSET_UPLOAD` (opcode 56) chunks with data + sequence ID
4. Each chunk: max 28 data bytes + 1 seq_id byte
5. Wait for `ASSET_UPLOAD_RESULT` (opcode 73): status 1=OK, 2=CRC fail, 3=disk full, 4=misalignment

## .epy File Encryption

The original Sifteo Python source files were encrypted as `.epy` files using:
- **Algorithm**: AES-128-CFB (Cipher Feedback Mode, 128-bit blocks)
- **Key**: `0x2BF0510B 0x559C91B1 0x9DCC27F9 0xD727C08A` (as uint32 array)
- **IV**: `0x00010203 0x04050607 0x08090A0B 0x0C0D0E0F`
- **Byte ordering**: Big-endian within uint32 AES state, but file I/O is little-endian
  (x86), requiring byte-swapping each 4-byte group before/after decryption
- **Padding**: PKCS7-like (last byte of last block = number of padding bytes)

## Source Files (Decompiled/Decrypted)

### Decrypted Python Sources (from .epy files)

| File | Description |
|------|-------------|
| `decrypted_py/runner/connector/usb/dongle.py` | USB HID dongle communication (VID/PID, read/write) |
| `decrypted_py/runner/connector/usb/helpers/dongle_helper.py` | Message construction/parsing helpers |
| `decrypted_py/runner/connector/usb/helpers/graphics_helper.py` | Graphics command helpers |
| `decrypted_py/runner/connector/usb/helpers/asset_helper.py` | Asset upload/download/management |
| `decrypted_py/runner/connector/usb_connector.py` | USB connector abstraction |
| `decrypted_py/runner/connector/message.py` | Message class (opcode, address, payload) |
| `decrypted_py/runner/app.py` | App lifecycle management |
| `decrypted_py/runner/link.py` | Link layer (send to dongle/cube) |
| `decrypted_py/sift/opcodes.py` | Complete opcode definitions |
| `decrypted_py/sift/siftable.py` | Siftable (cube) API: display, sensors, neighbors |
| `decrypted_py/sift/sift_set.py` | SiftSet: cube collection + event routing |
| `decrypted_py/sift/neighbors.py` | Neighbor detection and tracking |
| `decrypted_py/sift/base_app.py` | Base class for Sifteo apps |
| `decrypted_py/sift/image.py` | Image asset handling |
| `decrypted_py/sift/sound.py` | Sound playback API |

### Decompiled .NET Sources

| File | Description |
|------|-------------|
| `decompiled/Sifteo/Sifteo/Cube.cs` | Cube API (display, sensors, neighbors) |
| `decompiled/Sifteo/Sifteo/BaseApp.cs` | Game base class (Setup, Tick, events) |
| `decompiled/Sifteo/Sifteo/CubeSet.cs` | Cube collection management |
| `decompiled/Sifteo/Sifteo/Sound.cs` | Sound API |
| `decompiled/Sifteo/Sifteo/JsonRpcService.cs` | JSON-RPC protocol handler |
| `decompiled/Sifteo/Sifteo/JsonRpcConnector.cs` | TCP connection to SiftRunner |
| `decompiled/Runner/Sifteo.Runner/Runner.cs` | Game DLL loader |

## Native Libraries

| Library | Platform | Functions |
|---------|----------|-----------|
| `sift_dongle_lib.so` | macOS (i386/x86_64/ppc) | `sift_hid_open`, `sift_hid_close`, `sift_hid_send`, `sift_hid_recv`, `output_callback` |
| `sift_dongle_emu_lib.so` | macOS (i386/x86_64/ppc) | Same + `sift_hid_cancel` |
| `sifthid.dll` | Windows (i386) | Same + `sift_hid_rx_packet_size`, `sift_hid_tx_packet_size` |

Source: `hid_MACOSX.c` (macOS), `hid_WINDOWS.c` (Windows)
