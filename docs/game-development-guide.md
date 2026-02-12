# Sifteo V1 Game Development Guide

A tutorial for creating games and interactive experiences for Sifteo V1 cubes using the Python `BaseApp` API.

## Prerequisites

- macOS with Python 3.9+
- `libusb` installed (`brew install libusb`)
- `pyusb` and `hidapi` installed (`pip install pyusb hidapi`)
- A Sifteo V1 USB dongle and one or more V1 cubes
- Optional: `Pillow` for image assets (`pip install Pillow`)

## Your First Game

Every Sifteo game is a Python class that subclasses `BaseApp`. Here's the simplest possible game:

```python
from sifteo import BaseApp, Cube

class MyGame(BaseApp):
    def setup(self):
        for cube in self.cubes:
            cube.fill(0, 0, 255)  # Fill every cube with blue

if __name__ == "__main__":
    MyGame().run()
```

Run it with:

```bash
sudo python3 my_game.py
```

Root access is required on macOS because the USB dongle's kernel HID driver must be detached for raw access.

## App Lifecycle

When you call `MyGame().run()`, the following happens in order:

1. **Connect** -- the dongle is opened and cubes are discovered
2. **Asset sync** -- if your class declares `IMAGES` or `SOUNDS`, they are uploaded to all cubes (only missing assets are transferred)
3. **`setup()`** -- called once; initialize your game state and draw the initial screen
4. **Event loop** -- runs at ~30 FPS (configurable). Each frame:
   - All pending cube events are processed and dispatched to your handlers
   - `tick(dt)` is called with the time elapsed since the last frame (in seconds)
   - All cubes with pending draw operations are repainted
5. **Shutdown** -- Ctrl+C stops the loop, cubes return to idle, dongle is closed

```python
class MyGame(BaseApp):
    def setup(self):
        """Called once after connection. Initialize state, draw first frame."""
        self.counter = 0
        for cube in self.cubes:
            cube.fill(0, 0, 0)

    def tick(self, dt):
        """Called every frame. dt = seconds since last frame (~0.033 at 30 FPS)."""
        self.counter += dt
```

You can set a custom frame rate in the constructor:

```python
class MyGame(BaseApp):
    def __init__(self):
        super().__init__(target_fps=60.0)
```

## Display

Each cube has a 128x128 pixel LCD display. Colors use 8-bit RGB332 encoding internally, but the API accepts standard 0-255 RGB values.

### Fill the Screen

```python
cube.fill(255, 0, 0)    # Solid red
cube.fill(0, 255, 0)    # Solid green
cube.fill(0, 0, 0)      # Black
```

### Draw Rectangles

```python
cube.rect(x, y, width, height, r, g, b)

# Examples:
cube.rect(10, 10, 50, 30, 255, 255, 0)   # Yellow rectangle at (10,10), 50x30 pixels
cube.rect(0, 0, 128, 64, 0, 0, 128)      # Dark blue top half
```

### Draw Individual Pixels

```python
cube.put_pixel(64, 64, 255, 255, 255)  # White pixel at center
```

### Display Images from Flash

Images must be uploaded to cube flash first (see [Assets](#assets) below):

```python
cube.image(app_id, asset_id)                      # Full screen, default position
cube.image(app_id, asset_id, x=10, y=10)          # Position at (10, 10)
cube.image(app_id, asset_id, w=64, h=64)          # Partial size
cube.image(app_id, asset_id, scale=2)              # 2x scale
cube.image(app_id, asset_id, rotation=1)           # Rotated (0-3)
cube.image(app_id, asset_id, src_x=0, src_y=0)    # Source region offset
```

### Repainting

Drawing operations write to the cube's framebuffer but don't update the display immediately. The framework automatically calls `repaint()` on every cube at the end of each frame. You can also call it manually if needed:

```python
cube.fill(255, 0, 0)
cube.repaint()       # Force immediate display update
```

### Display Orientation

```python
cube.orientation = 0  # Normal (default)
cube.orientation = 1  # Rotated 90 degrees
cube.orientation = 2  # Rotated 180 degrees
cube.orientation = 3  # Rotated 270 degrees
```

## Input: Event Handlers

Override these methods in your `BaseApp` subclass to respond to cube interactions.

### Button Press

Each cube has one clickable button (the screen itself).

```python
def on_button(self, cube, pressed):
    if pressed:
        print(f"Cube {cube.id} pressed!")
    else:
        print(f"Cube {cube.id} released!")
```

### Tilt (Accelerometer)

Cubes report tilt as discrete levels, not continuous angles:

- `x`: 0 = tilted left, 1 = level, 2 = tilted right
- `y`: 0 = tilted up, 1 = level, 2 = tilted down
- `z`: 0 = face down, 2 = face up

```python
def on_tilt(self, cube, x, y, z):
    if x == 0:
        print("Tilted left")
    elif x == 2:
        print("Tilted right")

    if z == 0:
        print("Face down!")
```

### Flip Detection

Triggered when a cube is turned face-down or face-up (derived from z-axis tilt changes):

```python
def on_flip(self, cube, face_down):
    if face_down:
        cube.fill(0, 0, 0)  # Screen off when face down
    else:
        cube.fill(0, 255, 0)  # Green when face up
```

### Shake

Triggered when a cube detects a shake gesture:

```python
def on_shake(self, cube):
    print(f"Cube {cube.id} was shaken!")
```

### Neighbor Detection

Cubes detect when they are placed next to each other. Each cube has 4 sides: **0 = top, 1 = left, 2 = bottom, 3 = right**.

```python
def on_neighbor_add(self, cube, side, neighbor, neighbor_side):
    """Two cubes were placed next to each other."""
    print(f"Cube {cube.id} side {side} <-> Cube {neighbor.id} side {neighbor_side}")
    # Example: sync colors
    neighbor.fill(255, 0, 0)

def on_neighbor_remove(self, cube, side):
    """A neighbor was removed from this side."""
    print(f"Cube {cube.id} lost neighbor on side {side}")
```

Neighbor state is also tracked on each cube object:

```python
# cube.neighbors is a list of 4 elements (one per side)
# Each is None (no neighbor) or (neighbor_id, neighbor_side)
for side, neighbor_info in enumerate(cube.neighbors):
    if neighbor_info:
        neighbor_id, neighbor_side = neighbor_info
        print(f"Side {side} -> Cube {neighbor_id}")
```

### Cube Connect / Disconnect

```python
def on_new_cube(self, cube):
    """A cube just connected (powered on or came back from sleep)."""
    print(f"Welcome cube {cube.id}!")
    cube.fill(0, 255, 0)

def on_lost_cube(self, cube):
    """A cube disconnected (powered off or went to sleep)."""
    print(f"Lost cube {cube.id}")
```

### Other Events

```python
def on_battery_low(self, cube):
    """Cube reports low battery."""
    print(f"Cube {cube.id}: battery low!")

def on_dock(self, cube, docked):
    """Cube placed in or removed from charging dock."""
    print(f"Cube {cube.id}: {'docked' if docked else 'undocked'}")

def on_firmware_version(self, cube, version):
    """Cube reports its firmware version string."""
    print(f"Cube {cube.id}: firmware {version}")
```

## Cube State

Each `Cube` object tracks its current state:

```python
cube.id                  # Integer cube address (0-15)
cube.tilt                # Tuple (x, y, z) -- current tilt
cube.button_pressed      # bool
cube.face_down           # bool (derived from tilt z-axis)
cube.neighbors           # List of 4: None or (neighbor_id, side)
cube.online              # bool
cube.firmware_version    # str or None
cube.battery_low         # bool
cube.docked              # bool
```

Access all connected cubes via `self.cubes`:

```python
def tick(self, dt):
    for cube in self.cubes:
        if cube.button_pressed:
            cube.fill(255, 0, 0)
```

## Assets

Assets (images and sounds) can be declared as class attributes for automatic management.

### Declaring Assets

```python
class MyGame(BaseApp):
    APP_NAME = "my_game"                         # Auto-generates app_id via CRC32
    IMAGES = {
        "logo": "assets/logo.png",               # PNG, BMP, JPEG supported
        "sprite": "assets/sprite.bmp",
    }
    SOUNDS = {
        "beep": "assets/beep.wav",               # WAV files only
        "music": "assets/background_music.wav",
    }
```

File paths are resolved **relative to the Python file** defining the subclass.

### How App IDs Work

Every app needs a 32-bit identifier to scope its assets on cube flash:

- **`APP_NAME = "my_game"`** -- the string is hashed with CRC32 to produce the ID automatically
- **`APP_ID = 12345`** -- set an explicit integer ID (overrides `APP_NAME`)
- If neither is set, defaults to `0`

```python
# These are equivalent:
class Game1(BaseApp):
    APP_NAME = "my_game"  # app_id = zlib.crc32(b"my_game") & 0xFFFFFFFF

class Game2(BaseApp):
    APP_ID = 0xA1B2C3D4   # Explicit ID
```

### Asset IDs

Integer IDs are assigned automatically in sorted order: images first (sorted by name), then sounds (sorted by name), starting from 0.

```python
# With IMAGES = {"bg": ..., "avatar": ...} and SOUNDS = {"click": ...}
# Assigned IDs:
#   "avatar" -> 0  (images sorted: avatar before bg)
#   "bg"     -> 1
#   "click"  -> 2  (sounds come after images)
```

Use `self.asset_id("name")` to look up the assigned ID:

```python
def setup(self):
    for cube in self.cubes:
        cube.image(self.app_id, self.asset_id("logo"))
```

### Smart Sync

When `run()` is called, assets are synced to all connected cubes before `setup()`. The sync is smart -- it queries each cube's inventory and only uploads assets that are missing. If all assets are already present, no uploads happen.

```
Syncing 3 asset(s) for app my_game...
  Cube 1: uploading 2/3 asset(s)
    avatar (avatar.png)...
    [##############################] 100% (16388/16388 bytes)
    beep (beep.wav)...
    [##############################] 100% (44104/44104 bytes)
  Cube 2: all 3 asset(s) present
Asset sync complete.
```

### Late-Joining Cubes

If a cube connects after the game has started, you can sync assets to it:

```python
def on_new_cube(self, cube):
    self.sync_assets_to_cube(cube)
    cube.image(self.app_id, self.asset_id("logo"))
```

### Image Format Details

- Images are converted to **RGB332** format (1 byte per pixel)
- Default size is **128x128** (full screen = 16384 bytes + 4 byte CRC)
- Larger images are resized with Lanczos resampling
- Requires `Pillow` (`pip install Pillow`)

### Sound Playback

Sound assets uploaded to cube flash are for storage only -- the V1 cubes have no speakers. Sound playback happens on the **host machine**. The `SoundMixer` class is available as `self.sound`:

```python
class MyGame(BaseApp):
    def setup(self):
        self.beep_handle = None

    def on_button(self, cube, pressed):
        if pressed:
            self.beep_handle = self.sound.play("assets/beep.wav")

    def on_shake(self, cube):
        self.sound.stop_all()
```

`SoundMixer` methods:

| Method                      | Description                          |
|-----------------------------|--------------------------------------|
| `play(path, volume=1.0)`   | Play a sound file, returns a handle  |
| `stop(handle)`              | Stop a specific sound                |
| `stop_all()`                | Stop all playing sounds              |
| `pause_all()`               | Pause all sounds                     |
| `resume_all()`              | Resume paused sounds                 |
| `is_playing(handle)`        | Check if a sound is still playing    |
| `active_count`              | Number of currently playing sounds   |

Volume is 0.0 to 1.0. On macOS, playback uses `afplay`.

## Complete Example: A Game with Assets

```python
from sifteo import BaseApp, Cube

class PictureViewer(BaseApp):
    APP_NAME = "viewer"
    IMAGES = {
        "photo1": "assets/photo1.png",
        "photo2": "assets/photo2.png",
        "photo3": "assets/photo3.png",
    }

    def setup(self):
        self.current = {}
        photos = sorted(self.IMAGES.keys())
        for i, cube in enumerate(self.cubes):
            name = photos[i % len(photos)]
            self.current[cube.id] = name
            self._show(cube, name)

    def _show(self, cube, name):
        cube.image(self.app_id, self.asset_id(name))

    def on_button(self, cube, pressed):
        if not pressed:
            return
        photos = sorted(self.IMAGES.keys())
        cur = self.current.get(cube.id, photos[0])
        idx = (photos.index(cur) + 1) % len(photos)
        self.current[cube.id] = photos[idx]
        self._show(cube, photos[idx])

    def on_neighbor_add(self, cube, side, neighbor, neighbor_side):
        # Show the same image on both cubes
        name = self.current.get(cube.id)
        if name:
            self.current[neighbor.id] = name
            self._show(neighbor, name)

if __name__ == "__main__":
    PictureViewer().run()
```

## Game Design Patterns

### Tracking Per-Cube State

Use a dictionary keyed by `cube.id`:

```python
def setup(self):
    self.scores = {cube.id: 0 for cube in self.cubes}
    self.colors = {cube.id: (0, 0, 0) for cube in self.cubes}
```

### Animation with `tick()`

The `tick(dt)` method is called every frame. Use `dt` for smooth, frame-rate-independent animation:

```python
def setup(self):
    self.timer = 0.0
    self.flash_on = False

def tick(self, dt):
    self.timer += dt
    if self.timer >= 0.5:  # Toggle every 0.5 seconds
        self.timer = 0.0
        self.flash_on = not self.flash_on
        for cube in self.cubes:
            if self.flash_on:
                cube.fill(255, 255, 255)
            else:
                cube.fill(0, 0, 0)
```

### Color Blending

Smoothly transition between colors:

```python
def lerp_color(a, b, t):
    """Blend two (r, g, b) tuples. t=0 gives a, t=1 gives b."""
    return (
        int(a[0] + (b[0] - a[0]) * t),
        int(a[1] + (b[1] - a[1]) * t),
        int(a[2] + (b[2] - a[2]) * t),
    )
```

### Neighbor-Based Mechanics

The neighbor system is what makes Sifteo games unique. Use it for:

- **Passing objects** between cubes (touch to transfer)
- **Building patterns** (arrange cubes in a specific layout)
- **Combining effects** (two cubes side-by-side create something new)

```python
def on_neighbor_add(self, cube, side, neighbor, neighbor_side):
    # Transfer an item from cube to neighbor
    if self.has_item[cube.id]:
        self.has_item[cube.id] = False
        self.has_item[neighbor.id] = True
        self._repaint(cube)
        self._repaint(neighbor)
```

## API Reference Summary

### BaseApp Class Attributes

| Attribute   | Type            | Description                        |
|-------------|-----------------|------------------------------------|
| `APP_NAME`  | `str` or `None` | App name (auto-generates app_id)  |
| `APP_ID`    | `int` or `None` | Explicit 32-bit app ID            |
| `IMAGES`    | `dict`          | `{name: path}` image assets       |
| `SOUNDS`    | `dict`          | `{name: path}` sound assets       |

### BaseApp Properties

| Property  | Type                   | Description                  |
|-----------|------------------------|------------------------------|
| `cubes`   | `list[Cube]`           | All connected cubes          |
| `assets`  | `AssetManager` or None | Asset manager instance       |
| `app_id`  | `int` or None          | Computed 32-bit app ID       |
| `sound`   | `SoundMixer`           | Host-side sound player       |

### BaseApp Methods

| Method                     | Description                              |
|----------------------------|------------------------------------------|
| `run(cube_ids=None)`       | Connect and start the game loop          |
| `asset_id(name)`           | Look up integer asset ID by name         |
| `sync_assets_to_cube(cube)`| Upload assets to a specific cube         |

### Cube Display Methods

| Method                                              | Description            |
|-----------------------------------------------------|------------------------|
| `fill(r, g, b)`                                    | Fill screen with color |
| `rect(x, y, w, h, r, g, b)`                        | Draw filled rectangle  |
| `put_pixel(x, y, r, g, b)`                         | Draw single pixel      |
| `image(app_id, asset_id, x, y, w, h, scale, rotation)` | Blit image from flash |
| `repaint()`                                         | Force display update   |

### Event Handlers

| Handler                                             | Trigger                    |
|-----------------------------------------------------|----------------------------|
| `setup()`                                           | Once, after connection     |
| `tick(dt)`                                          | Every frame                |
| `on_new_cube(cube)`                                 | Cube connected             |
| `on_lost_cube(cube)`                                | Cube disconnected          |
| `on_button(cube, pressed)`                          | Button press/release       |
| `on_tilt(cube, x, y, z)`                            | Accelerometer change       |
| `on_shake(cube)`                                    | Shake gesture              |
| `on_flip(cube, face_down)`                          | Cube flipped over          |
| `on_neighbor_add(cube, side, neighbor, neighbor_side)` | Cubes placed together   |
| `on_neighbor_remove(cube, side)`                    | Neighbor removed           |
| `on_battery_low(cube)`                              | Low battery warning        |
| `on_dock(cube, docked)`                             | Dock state change          |
| `on_firmware_version(cube, version)`                | Firmware version reported  |
