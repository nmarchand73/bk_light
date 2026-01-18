# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

BLE LED Display Toolkit - A Python utility suite for driving BK-Light ACT1026 (32×32) and ACT1025 (64×16) RGB LED matrices over Bluetooth Low Energy. Provides both a modular library for programmatic control and CLI scripts for various display modes.

## Running the Application

```bash
# Install dependencies
pip install -r requirements.txt

# First-time setup: scan for devices and update config
python scripts/setup_device.py

# Main entry point (uses config.yaml defaults)
python scripts/production.py

# Override mode via CLI
python scripts/production.py --mode clock --preset default
python scripts/production.py --mode text --text "HELLO" --preset marquee_left
python scripts/production.py --mode image --image path/to/image.png
python scripts/production.py --mode counter --start 0 --count 100

# Standalone scripts
python scripts/clock_display.py --preset default
python scripts/display_text.py "Hello World" --preset marquee_left
python scripts/send_image.py image.png --mode fit
python scripts/identify_panels.py  # Show panel indices on multi-panel setups
python scripts/galaxy_animation.py  # Animated rotating galaxy effect
python scripts/fft_vu_meter.py      # Audio-reactive frequency visualizer
python scripts/play_gif.py anim.gif # Play animated GIF on display

# WebSocket server for remote control
python native/server.py
```

Device address can be set via `BK_LIGHT_ADDRESS` environment variable or `--address` flag.

## Architecture

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
├── galaxy_animation.py     # Rotating galaxy with twinkling stars
├── fft_vu_meter.py         # Audio-reactive FFT frequency visualizer
└── play_gif.py             # Animated GIF player

native/server.py            # WebSocket server for remote frame injection
config.yaml                 # Main configuration file
```

### Key Design Patterns

1. **Configuration Layer** (`config.py`): Dataclass-based immutable config with preset composition. Mode options merge runtime overrides with YAML presets via `clock_options()`, `text_options()`, etc.

2. **BLE Protocol** (`display_session.py`): 3-stage ACK handshake with `AckWatcher` async notification handler. Frames wrapped with length prefix and CRC32. Auto-reconnect with exponential backoff.

3. **Multi-Panel** (`panel_manager.py`): `PanelManager` context manager handles multiple `BleDisplaySession` instances. Images automatically sliced and distributed in parallel via `asyncio.gather()`.

4. **Font Profiles** (`fonts.py`): Per-font rendering hints (size adjustments, baseline offsets) in `get_font_profile()` registry. Four bundled fonts in `assets/fonts/`.

### BLE Protocol Details

- Write characteristic: `0000fa02`, Notify: `0000fa03`
- Handshake sequence: HANDSHAKE_FIRST → ACK_STAGE_ONE → HANDSHAKE_SECOND → ACK_STAGE_TWO → Frame → ACK_STAGE_THREE
- ACT1025 (64x16) uses alternate ACK patterns defined in `display_session.py`

## Configuration

All settings in `config.yaml`. Key sections:

- `device`: BLE address, MTU, brightness, rotation, reconnect params
- `panels`: Multi-panel grid layout (columns, rows, panel list with grid positions)
- `display`: Frame interval, retries, logging
- `runtime`: Active mode and preset selection
- `presets`: Per-mode configurations (clock, text, image, counter)

## Dependencies

- `bleak`: BLE client
- `Pillow`: Image processing
- `PyYAML`: Configuration
- `websockets`: Optional, for native/server.py
- `numpy`, `sounddevice`: Optional, for fft_vu_meter.py
