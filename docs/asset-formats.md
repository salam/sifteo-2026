# Sifteo V1 Asset Formats

Binary format reference for image and sound assets stored on Sifteo V1 cube flash. Derived from the decrypted original Python sources and confirmed via USB packet capture.

## Overview

Assets are stored on each cube's flash memory, scoped to a 32-bit **app ID**. Each asset has a 16-bit **asset ID** and a **type** (image or sound). All multi-byte values are **little-endian**.

| Property     | Value                       |
|--------------|-----------------------------|
| Byte order   | Little-endian               |
| App ID       | 32-bit unsigned integer     |
| Asset ID     | 16-bit unsigned integer     |
| Asset type   | `0` = Image, `1` = Sound   |
| CRC          | CRC32 (zlib), 4 bytes, appended to payload |

---

## Image Format

Images use the **RGB332** color encoding: 1 byte per pixel, with 3 bits red, 3 bits green, and 2 bits blue. The cube's display is 128x128 pixels.

### RGB332 Encoding

Each 24-bit RGB pixel is packed into a single byte:

```
Bit layout: RRRGGGBB

R = (r >> 5) << 5    (top 3 bits of red,   placed at bits 7-5)
G = (g >> 5) << 2    (top 3 bits of green, placed at bits 4-2)
B = (b >> 6)         (top 2 bits of blue,  placed at bits 1-0)

RGB332 = R | G | B
```

This gives 8 levels for red and green (0, 36, 72, 109, 145, 182, 218, 255 approximate) and 4 levels for blue (0, 85, 170, 255 approximate).

### Binary Layout

A full-screen image asset (128x128) is laid out as:

```
Offset  Size     Description
------  -------  -----------
0x0000  16384    Pixel data: 128 * 128 bytes, row-major, RGB332
0x4000  4        CRC32 of pixel data (little-endian uint32)
------  -------  -----------
Total:  16388 bytes
```

For non-full-screen images (width x height):

```
Offset  Size            Description
------  --------------  -----------
0x0000  width * height  Pixel data, row-major, RGB332
  ...   4               CRC32 of pixel data (little-endian uint32)
------  --------------  -----------
Total:  (width * height) + 4 bytes
```

Pixels are stored in **row-major** order: the first `width` bytes are the top row (left to right), the next `width` bytes are the second row, and so on.

### Encoding from Common Formats

The `encode_image()` function converts PNG, BMP, or JPEG files:

1. Open the image with Pillow and convert to RGB mode
2. Resize to the target dimensions (default 128x128) using Lanczos resampling
3. Convert each pixel from 24-bit RGB to 8-bit RGB332
4. Compute CRC32 of the pixel data
5. Append the CRC as a 4-byte little-endian unsigned integer

There are also raw-data variants:

- `encode_image_rgb(pixel_data, width, height)` -- input is packed RGB bytes (3 bytes/pixel)
- `encode_image_rgba(pixel_data, width, height)` -- input is packed RGBA bytes (4 bytes/pixel, alpha is ignored)

### Pre-compiled `.siftimg` Files

The original Sifteo SDK produced `.siftimg` files that are already in the cube's native format. These can be uploaded directly via `read_siftimg()` without re-encoding. The CRC is in the last 4 bytes.

---

## Sound Format

Sound assets are stored as **IEEE 754 32-bit float** samples at **22050 Hz, mono**.

### Sample Format

| Property       | Value                           |
|----------------|---------------------------------|
| Sample rate    | 22050 Hz                        |
| Channels       | 1 (mono)                        |
| Sample type    | IEEE 754 float32 (4 bytes each) |
| Sample range   | -1.0 to +1.0                    |
| Byte order     | Little-endian                   |

### Binary Layout

```
Offset  Size              Description
------  ----------------  -----------
0x0000  N * 4             Float32 samples (little-endian IEEE 754)
  ...   4                 CRC32 of sample data (little-endian uint32)
------  ----------------  -----------
Total:  (N * 4) + 4 bytes
```

Where `N` is the total number of samples. For example, a 1-second sound at 22050 Hz is 22050 samples = 88200 bytes of sample data + 4 bytes CRC = 88204 bytes total.

### Encoding from WAV Files

The `encode_sound()` function handles WAV conversion:

1. Parse the RIFF/WAV header (`fmt ` and `data` chunks)
2. Decode PCM or IEEE float samples to float32:
   - **PCM 8-bit**: unsigned (0-255, center at 128), normalized to [-1.0, 1.0]
   - **PCM 16-bit**: signed int16, divided by 32768
   - **PCM 24-bit**: signed 24-bit packed (3 bytes), divided by 8388608
   - **PCM 32-bit**: signed int32, divided by 2147483648
   - **IEEE float 32-bit**: used directly
   - **IEEE float 64-bit**: downcast from float64 to float32
3. Mix stereo/multi-channel to mono by averaging all channels per sample
4. Resample to 22050 Hz via linear interpolation if the source rate differs
5. Pack as little-endian float32 array
6. Compute CRC32 and append as 4-byte little-endian uint32

### Supported WAV Format Codes

| Format code | Description                        |
|-------------|------------------------------------|
| `1`         | PCM (8, 16, 24, or 32-bit)        |
| `3`         | IEEE floating-point (32 or 64-bit) |

---

## Upload Protocol

Assets are uploaded to cube flash via the USB dongle using a chunked transfer protocol.

### Upload Sequence

```
Host                           Dongle/Cube
  |                                 |
  |-- ASSET_UPLOAD_HEADER (68) ---->|   Step 1: Send header
  |                                 |
  |        ~3 second pause          |   Step 2: Wait for flash prep
  |                                 |
  |-- ASSET_UPLOAD (56) chunk 0 --->|   Step 3: Send data chunks
  |-- ASSET_UPLOAD (56) chunk 1 --->|     (max 28 data bytes each)
  |-- ASSET_UPLOAD (56) chunk 2 --->|     (seq_id increments 0-255)
  |         ...                     |
  |-- ASSET_UPLOAD (56) chunk N --->|
  |                                 |
  |<-- ASSET_UPLOAD_RESULT (73) ----|   Step 4: Receive result
  |                                 |
```

### Upload Header (Opcode 68)

```
Offset  Size  Type    Description
------  ----  ------  -----------
0       4     uint32  Total asset size in bytes
4       4     uint32  App ID
8       2     uint16  Asset ID
10      1     uint8   Asset type (0=image, 1=sound)
```

After sending the header, the host must wait approximately **3 seconds** for the cube to prepare its flash memory.

### Upload Data Chunk (Opcode 56)

Each chunk carries up to 28 bytes of data:

```
Offset  Size      Type    Description
------  --------  ------  -----------
0       1         uint8   Byte count (data_len + 1, includes seq_id)
1       1-28      bytes   Asset data (max 28 bytes per chunk)
...     1         uint8   Sequence ID (0-255, wrapping)
```

The sequence ID increments by 1 for each chunk and wraps at 255.

### Upload Result (Opcode 73)

The cube responds with a status code:

| Status | Meaning             |
|--------|---------------------|
| `1`    | OK -- upload succeeded |
| `2`    | CRC verification failed |
| `3`    | Disk full (no flash space) |
| `4`    | Flash alignment error |

### CRC Verification (Opcode 153 / 154)

After uploading, the host can request the cube to verify the asset's CRC:

**Request (Opcode 153):**

```
Offset  Size  Type    Description
------  ----  ------  -----------
0       4     uint32  App ID
4       2     uint16  Asset ID
6       1     uint8   Asset type
```

**Response (Opcode 154):**

```
Offset  Size  Type    Description
------  ----  ------  -----------
7       4     uint32  Original CRC (stored at upload time)
11      4     uint32  Calculated CRC (recomputed from flash)
```

The asset is valid if original CRC == calculated CRC.

---

## Asset Management Commands

### Query App Info (Opcode 60 / 139)

Returns asset counts and total storage used by an app.

**Request payload:** 4-byte app_id

**Response payload offsets:**

| Offset | Size | Type   | Description            |
|--------|------|--------|------------------------|
| 4      | 2    | uint16 | Image count            |
| 6      | 2    | uint16 | Sound count            |
| 8      | 4    | uint32 | Total bytes on flash   |

### Query Asset Inventory (Opcode 61 / 138)

Returns one response per asset in the app.

**Request payload:**

| Offset | Size | Type   | Description        |
|--------|------|--------|--------------------|
| 0      | 4    | uint32 | App ID             |
| 4      | 2    | uint16 | Expected asset count |

**Each response payload:**

| Offset | Size | Type   | Description     |
|--------|------|--------|-----------------|
| 4      | 2    | uint16 | Asset ID        |
| 6      | 1    | uint8  | Asset type      |

### Delete All Assets (Opcode 58)

**Request payload:** 4-byte app_id. Response: `ASSET_DELETE_COMPLETE` (74).

### Delete Single Asset (Opcode 59)

**Request payload:**

| Offset | Size | Type   | Description |
|--------|------|--------|-------------|
| 0      | 4    | uint32 | App ID      |
| 4      | 2    | uint16 | Asset ID    |
| 6      | 1    | uint8  | Asset type  |

### Query Available Storage (Opcode 62)

No payload. Response contains a 4-byte uint32 with available bytes.

### List Installed Apps (Opcode 70 / 72)

Returns one `APP_LIST_RESPONSE_ITEM` (72) per installed app, each containing a 4-byte app_id.

---

## Framebuffer Download (Opcode 157 / 158 / 159)

Downloads the cube's current framebuffer for debugging.

**Request:** Opcode 157, no payload.

**Header response (Opcode 158):**

| Offset | Size | Type  | Description       |
|--------|------|-------|-------------------|
| 0      | 1    | uint8 | Width (pixels)    |
| 1      | 1    | uint8 | Height (pixels)   |
| 2      | 1    | uint8 | Bytes per pixel   |

**Data chunks (Opcode 159):**

| Offset | Size        | Type  | Description                |
|--------|-------------|-------|----------------------------|
| 0      | 1           | uint8 | Chunk data length          |
| 1      | chunk_len   | bytes | Framebuffer pixel data     |

Collect chunks until `width * height * bpp` bytes are received.

---

## Asset Download (Opcode 160 / 161 / 162)

Downloads an asset's raw data from cube flash.

**Request (Opcode 160):**

| Offset | Size | Type   | Description |
|--------|------|--------|-------------|
| 0      | 4    | uint32 | App ID      |
| 4      | 2    | uint16 | Asset ID    |
| 6      | 1    | uint8  | Asset type  |

**Header response (Opcode 161):**

| Offset | Size | Type   | Description |
|--------|------|--------|-------------|
| 0      | 4    | uint32 | Total size  |
| 4      | 4    | uint32 | CRC32       |

**Data chunks (Opcode 162):** Same format as framebuffer download chunks.
