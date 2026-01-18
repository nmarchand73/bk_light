# BLE LED Display Toolkit

A Python utility suite for driving BK-Light ACT1026 (32×32) and ACT1025 (64×16) RGB LED matrices over Bluetooth Low Energy. Provides both a modular library for programmatic control and CLI scripts for various display modes including clocks, animations, and visual effects.

Everything is now configurable through `config.yaml`, so you can define presets, multi-panel layouts, and runtime modes without touching code.

## Requirements

- Python 3.10+
- `pip install -r requirements.txt`
- Bluetooth adapter with BLE support enabled
- Hardware capabilities:
  - BLE 4.0 or newer with GATT/ATT support
  - Central role / GATT client mode
  - LE 1M PHY
  - Long ATT write support (Prepare/Execute or Write-with-response handling for fragmented payloads)
  - MTU negotiation and L2CAP fragmentation

The tools assume the screen advertises as `LED_BLE_*` (BK-Light firmware). Update the MAC address in `config.yaml` (or via `BK_LIGHT_ADDRESS`) if your unit differs.

## Project Structure

```
bk_light/                    # Core library
├── config.py               # YAML configuration loading, validation, preset composition
├── display_session.py      # BLE transport layer (GATT client, ACK protocol, reconnect)
├── panel_manager.py        # Multi-panel orchestration, image slicing for tiled layouts
├── text.py                 # Text-to-PNG rendering with font profiles
└── fonts.py                # Font resolution and per-font rendering hints

scripts/                    # CLI entry points
├── production.py           # Unified entry point routing to display modes
├── setup_device.py         # BLE device scanner and config updater
├── clock_display.py        # HH:MM clock with colon flashing, timezone support
├── display_text.py         # Static or scrolling text display
├── send_image.py           # Image upload with scaling/rotation
├── increment_counter.py    # Animated numeric counter
├── identify_panels.py      # Multi-panel identification utility
├── play_gif.py             # Animated GIF player
│
│   # Visual effects & animations
├── galaxy_animation.py     # Rotating galaxy with twinkling stars
├── fft_vu_meter.py         # Audio-reactive FFT frequency visualizer
├── radar_animation.py      # Radar clock with RSS news ticker
├── perlin_flame.py         # Perlin noise flame effect
├── particle_sea.py         # Matrix/cyber style particle animation
├── retro_scroller.py       # Amiga/Atari ST demoscene effects
├── wheels_animation.py     # Concentric rotating rings
├── text_3d_rotation.py     # 3D rotating text with depth coloring
├── text_2d_animation.py    # 2D text animation effects
├── ascii_art_display.py    # ASCII art renderer
└── animation_template.py   # Template for creating new animations

native/server.py            # WebSocket server for remote frame injection
config.yaml                 # Main configuration file
```

## Quick Start

1. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

2. First-time setup - scan for devices and update config:

   ```bash
   python scripts/setup_device.py
   ```

3. Edit `config.yaml`.

   If you don’t know your panel’s BLE MAC on macOS, discover it first:

   ```bash
   python scripts/scan_macos.py
   ```

   The scanner lists devices advertising as `LED_BLE_*`; copy the address into `config.yaml` (or set `BK_LIGHT_ADDRESS`).

   macOS note: CoreBluetooth/bleak cannot initiate a connection by MAC address. Use macOS only to discover the address, then run the actual connection/production scripts from Linux or Windows where MAC-based connects are supported.

   - Single panel:

     ```yaml
     device:
       address: "F0:27:3C:1A:8B:C3"
     panels:
       list: ["F0:27:3C:1A:8B:C3"]
     display:
       antialias_text: true # set to false for crisp bitmap text
     ```

   - Fonts:

     Place `.ttf` / `.otf` files under `assets/fonts/` and reference them by name (extension optional):

     ```yaml
     presets:
       clock:
         default:
           font: "Aldo PC" # resolves to assets/fonts/Aldo PC.ttf
           size: 22
     ```

   - Multi-panel:

     ```yaml
     panels:
       tile_width: 32
       tile_height: 32
       layout:
         columns: 2
         rows: 1
       list:
         - name: left
           address: "F0:27:3C:1A:8B:C3"
           grid_x: 0
           grid_y: 0
         - name: right
           address: "F0:27:3C:1A:8B:C4"
           grid_x: 1
           grid_y: 0
     ```

     (A bare MAC string is accepted; defaults are inferred.)

4. Pick the runtime mode and preset:

   ```yaml
   runtime:
     mode: clock
     preset: default
     options:
       timezone: "Europe/Paris"
   ```

   Other examples:

   ```yaml
   runtime:
     mode: text
     preset: marquee_left
     options:
       text: "WELCOME"
       color: "#00FFAA"
       background: "#000000"

   runtime:
     mode: image
     preset: signage
     options:
       image: "assets/promo.png"

   runtime:
     mode: counter
     preset: default
     options:
       start: 100
       count: 50
       delay: 0.5
   ```

5. Launch the production entrypoint:

   ```bash
   python scripts/production.py
   ```

   Override anything ad hoc:

   ```bash
   python scripts/production.py --mode text --text "HELLO" --option color=#00FFAA
   ```

6. Need to identify MAC ↔ panel placement or force a clean BLE reset? Run:

   ```bash
   python scripts/identify_panels.py
   ```

   (Each panel displays its index and then disconnects cleanly.)

## Toolkit Scripts

### Core Display Scripts

- `scripts/clock_display.py` – async HH:MM clock (supports 12/24h, dot flashing, themes). Exit with `Ctrl+C` so the BLE session closes cleanly and you can relaunch immediately.
- `scripts/display_text.py` – renders text using presets (colour/background/font/spacing) or marquee scrolls.

  Example scroll preset in `config.yaml`:

  ```yaml
  text:
    marquee_left:
      mode: scroll
      direction: left
      speed: 30.0
      step: 3 # pixels moved per frame
      gap: 32
      size: 18
      spacing: 2
      offset_y: 0
      interval: 0.04
  ```

  Launch:

  ```bash
  python scripts/display_text.py "HELLO" --preset marquee_left
  ```

- `scripts/send_image.py` – uploads any image with fit/cover/scale + rotate/mirror/invert.
- `scripts/play_gif.py` – play animated GIFs on the display.
- `scripts/increment_counter.py` – numeric animation for diagnostics.
- `scripts/identify_panels.py` – flashes digits on each configured panel.

### Animation Scripts

- `scripts/galaxy_animation.py` – rotating galaxy with twinkling stars effect.
- `scripts/fft_vu_meter.py` – audio-reactive FFT frequency visualizer (requires `numpy`, `sounddevice`).
- `scripts/radar_animation.py` – radar clock with sweeping beam, trail effect, and France Info RSS news ticker.
- `scripts/perlin_flame.py` – realistic flame effect using Perlin noise.
- `scripts/particle_sea.py` – Matrix/cyber style particle animation with Perlin noise.
- `scripts/retro_scroller.py` – Amiga/Atari ST demoscene effects (sine scroller, copper bars, starfield).
- `scripts/wheels_animation.py` – concentric rotating rings animation.
- `scripts/text_3d_rotation.py` – 3D rotating text with depth-based coloring (blue=far, red=near).
- `scripts/text_2d_animation.py` – 2D text animation effects.
- `scripts/ascii_art_display.py` – ASCII art renderer for LED display.
- `scripts/animation_template.py` – template for creating new animations.

### Utility Scripts

- `scripts/setup_device.py` – BLE device scanner that updates config.yaml with discovered devices.
- `scripts/list_fonts.py` – prints available fonts from `assets/fonts/`. Bundled fonts:
  - `Aldo PC`
  - `Dolce Vita Light`
  - `Kenyan Coffee Rg`
  - `Kimberley Bl`

  ```bash
  python scripts/list_fonts.py [--config config.yaml]
  ```

- `scripts/scan_macos.py` – macOS helper that scans for BLE devices named `LED_BLE_*` and prints their MAC addresses so you can populate `config.yaml` or `BK_LIGHT_ADDRESS`. macOS cannot connect by MAC (CoreBluetooth limitation), so use the discovered address from Linux/Windows when running the other scripts.

### WebSocket Server

- `native/server.py` – WebSocket server for remote frame injection, allowing external applications to send frames to the display.

  ```bash
  python native/server.py
  ```

Each script honours `--config`, `--address`, and preset overrides so you can reuse the same YAML in development or production.

## Building New Effects

Use Pillow to draw onto a canvas sized to `columns × rows` tiles, then:

```python
async with PanelManager(load_config()) as manager:
    await manager.send_image(image)
```

`PanelManager` slices the image per tile and `BleDisplaySession` handles BLE writes/ACKs for each panel automatically. Sessions will auto-reconnect if a panel restarts (tunable via `reconnect_delay` / `max_retries` / `scan_timeout`).

## Attribution & License

- Created by Puparia — GitHub: [Pupariaa](https://github.com/Pupariaa).
- Code is open-source and contributions are welcome; open a pull request with improvements or new effects.
- If you reuse this toolkit (or derivatives) in your own projects, credit “Puparia / <https://github.com/Pupariaa>” and link back to the original repository.
- Licensed under the [MIT License](./LICENSE).
