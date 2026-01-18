"""Perlin noise flame effect for LED matrix.

Inspired by: https://www.instructables.com/LED-Flame-Controlled-by-Noise/
"""

import argparse
import asyncio
import colorsys
import math
import os
import sys
from dataclasses import replace
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from bk_light.config import load_config
from bk_light.panel_manager import PanelManager


# Permutation table for Perlin noise
PERM = [
    151, 160, 137, 91, 90, 15, 131, 13, 201, 95, 96, 53, 194, 233, 7, 225,
    140, 36, 103, 30, 69, 142, 8, 99, 37, 240, 21, 10, 23, 190, 6, 148,
    247, 120, 234, 75, 0, 26, 197, 62, 94, 252, 219, 203, 117, 35, 11, 32,
    57, 177, 33, 88, 237, 149, 56, 87, 174, 20, 125, 136, 171, 168, 68, 175,
    74, 165, 71, 134, 139, 48, 27, 166, 77, 146, 158, 231, 83, 111, 229, 122,
    60, 211, 133, 230, 220, 105, 92, 41, 55, 46, 245, 40, 244, 102, 143, 54,
    65, 25, 63, 161, 1, 216, 80, 73, 209, 76, 132, 187, 208, 89, 18, 169,
    200, 196, 135, 130, 116, 188, 159, 86, 164, 100, 109, 198, 173, 186, 3, 64,
    52, 217, 226, 250, 124, 123, 5, 202, 38, 147, 118, 126, 255, 82, 85, 212,
    207, 206, 59, 227, 47, 16, 58, 17, 182, 189, 28, 42, 223, 183, 170, 213,
    119, 248, 152, 2, 44, 154, 163, 70, 221, 153, 101, 155, 167, 43, 172, 9,
    129, 22, 39, 253, 19, 98, 108, 110, 79, 113, 224, 232, 178, 185, 112, 104,
    218, 246, 97, 228, 251, 34, 242, 193, 238, 210, 144, 12, 191, 179, 162, 241,
    81, 51, 145, 235, 249, 14, 239, 107, 49, 192, 214, 31, 181, 199, 106, 157,
    184, 84, 204, 176, 115, 121, 50, 45, 127, 4, 150, 254, 138, 236, 205, 93,
    222, 114, 67, 29, 24, 72, 243, 141, 128, 195, 78, 66, 215, 61, 156, 180,
]
PERM = PERM + PERM  # Double for overflow


def fade(t: float) -> float:
    """Fade function for smooth interpolation."""
    return t * t * t * (t * (t * 6 - 15) + 10)


def lerp(a: float, b: float, t: float) -> float:
    """Linear interpolation."""
    return a + t * (b - a)


def grad(h: int, x: float, y: float, z: float) -> float:
    """Gradient function."""
    h = h & 15
    u = x if h < 8 else y
    v = y if h < 4 else (x if h == 12 or h == 14 else z)
    return (u if (h & 1) == 0 else -u) + (v if (h & 2) == 0 else -v)


def perlin(x: float, y: float, z: float) -> float:
    """3D Perlin noise returning value in range [-1, 1]."""
    # Find unit cube
    X = int(math.floor(x)) & 255
    Y = int(math.floor(y)) & 255
    Z = int(math.floor(z)) & 255

    # Relative position in cube
    x -= math.floor(x)
    y -= math.floor(y)
    z -= math.floor(z)

    # Fade curves
    u = fade(x)
    v = fade(y)
    w = fade(z)

    # Hash coordinates
    A = PERM[X] + Y
    AA = PERM[A] + Z
    AB = PERM[A + 1] + Z
    B = PERM[X + 1] + Y
    BA = PERM[B] + Z
    BB = PERM[B + 1] + Z

    # Blend results
    return lerp(
        lerp(
            lerp(grad(PERM[AA], x, y, z), grad(PERM[BA], x - 1, y, z), u),
            lerp(grad(PERM[AB], x, y - 1, z), grad(PERM[BB], x - 1, y - 1, z), u),
            v,
        ),
        lerp(
            lerp(grad(PERM[AA + 1], x, y, z - 1), grad(PERM[BA + 1], x - 1, y, z - 1), u),
            lerp(grad(PERM[AB + 1], x, y - 1, z - 1), grad(PERM[BB + 1], x - 1, y - 1, z - 1), u),
            v,
        ),
        w,
    )


def perlin_normalized(x: float, y: float, z: float) -> float:
    """Perlin noise normalized to [0, 1]."""
    return (perlin(x, y, z) + 1) / 2


def octave_noise(x: float, y: float, z: float, octaves: int = 4, persistence: float = 0.5) -> float:
    """Fractal Brownian motion - layered Perlin noise."""
    total = 0.0
    frequency = 1.0
    amplitude = 1.0
    max_value = 0.0

    for _ in range(octaves):
        total += perlin_normalized(x * frequency, y * frequency, z * frequency) * amplitude
        max_value += amplitude
        amplitude *= persistence
        frequency *= 2

    return total / max_value


# Color presets - high contrast for LED visibility
COLOR_PRESETS = {
    'fire': {
        'hue_center': 20,      # Orange-red
        'hue_range': 60,       # Yellow to deep red
        'saturation': 1.0,
        'brightness_min': 0.0,
        'brightness_max': 1.0,
    },
    'ocean': {
        'hue_center': 200,     # Cyan-blue
        'hue_range': 80,
        'saturation': 1.0,
        'brightness_min': 0.0,
        'brightness_max': 1.0,
    },
    'forest': {
        'hue_center': 100,     # Green-yellow
        'hue_range': 80,
        'saturation': 1.0,
        'brightness_min': 0.0,
        'brightness_max': 1.0,
    },
    'plasma': {
        'hue_center': 280,     # Purple-magenta
        'hue_range': 120,
        'saturation': 1.0,
        'brightness_min': 0.2,
        'brightness_max': 1.0,
    },
    'lava': {
        'hue_center': 10,      # Deep red-orange
        'hue_range': 40,
        'saturation': 1.0,
        'brightness_min': 0.0,
        'brightness_max': 1.0,
    },
    'aurora': {
        'hue_center': 160,     # Cyan-green
        'hue_range': 160,
        'saturation': 1.0,
        'brightness_min': 0.1,
        'brightness_max': 1.0,
    },
    'sunset': {
        'hue_center': 25,      # Orange-red
        'hue_range': 80,
        'saturation': 1.0,
        'brightness_min': 0.0,
        'brightness_max': 1.0,
    },
    'ice': {
        'hue_center': 200,     # Blue-cyan
        'hue_range': 60,
        'saturation': 0.8,
        'brightness_min': 0.3,
        'brightness_max': 1.0,
    },
    'rainbow': {
        'hue_center': 180,
        'hue_range': 360,      # Full spectrum
        'saturation': 1.0,
        'brightness_min': 0.5,
        'brightness_max': 1.0,
    },
    'matrix': {
        'hue_center': 120,     # Green
        'hue_range': 30,
        'saturation': 1.0,
        'brightness_min': 0.0,
        'brightness_max': 1.0,
    },
}


def generate_frame(
    width: int,
    height: int,
    t: float,
    scale: float = 0.05,
    preset: dict = None,
    octaves: int = 2,
    vertical_bias: float = 0.5,
    contrast: float = 2.5,
) -> Image.Image:
    """Generate a single frame of Perlin noise.

    Args:
        width: Frame width
        height: Frame height
        t: Time parameter for animation
        scale: Noise scale (smaller = larger blobs)
        preset: Color preset dict
        octaves: Number of noise octaves
        vertical_bias: Add vertical gradient for flame effect (0-1)

    Returns:
        PIL Image
    """
    if preset is None:
        preset = COLOR_PRESETS['fire']

    image = Image.new('RGB', (width, height), (0, 0, 0))
    pixels = image.load()

    hue_center = preset['hue_center']
    hue_range = preset['hue_range']
    saturation = preset['saturation']
    brightness_min = preset['brightness_min']
    brightness_max = preset['brightness_max']

    for y in range(height):
        for x in range(width):
            # Generate noise values
            nx = x * scale
            ny = y * scale

            # Main noise for hue
            noise_hue = octave_noise(nx, ny, t, octaves)
            # Apply contrast to hue
            noise_hue = (noise_hue - 0.5) * contrast + 0.5
            noise_hue = max(0, min(1, noise_hue))

            # Separate noise for brightness (offset coordinates)
            noise_bright = octave_noise(nx + 100, ny + 100, t * 1.5, octaves)
            # Apply contrast to brightness
            noise_bright = (noise_bright - 0.5) * contrast + 0.5
            noise_bright = max(0, min(1, noise_bright))

            # Apply vertical bias for flame effect (brighter at bottom)
            if vertical_bias > 0:
                v_factor = 1 - (y / height)  # 1 at top, 0 at bottom
                v_factor = v_factor ** (1 + vertical_bias)
                noise_bright = noise_bright * (1 - v_factor * 0.7)

            # Map to hue (cyclical)
            hue = ((noise_hue * hue_range) - (hue_range / 2) + hue_center) % 360
            hue_normalized = hue / 360.0

            # Map to brightness
            brightness = brightness_min + noise_bright * (brightness_max - brightness_min)
            brightness = max(0, min(1, brightness))

            # Convert HSV to RGB
            r, g, b = colorsys.hsv_to_rgb(hue_normalized, saturation, brightness)

            pixels[x, y] = (int(r * 255), int(g * 255), int(b * 255))

    return image


def print_console_preview(image: Image.Image, title: str = "") -> None:
    """Print a dot-matrix preview to console."""
    os.system('cls' if os.name == 'nt' else 'clear')
    if title:
        print(title + "\n")

    width, height = image.size
    pixels = image.load()
    RESET = "\033[0m"

    for y in range(height):
        line = ""
        for x in range(width):
            r, g, b = pixels[x, y]
            brightness = (0.299 * r + 0.587 * g + 0.114 * b) / 255.0

            if brightness < 0.1:
                dot = " "
            elif brightness < 0.4:
                dot = "•"
            else:
                dot = "●"

            # 256-color terminal
            r_term = int(r / 255 * 5)
            g_term = int(g / 255 * 5)
            b_term = int(b / 255 * 5)
            color_code = 16 + 36 * r_term + 6 * g_term + b_term
            line += f"\033[38;5;{color_code}m{dot} "

        print(line + RESET)
    print()


async def run_perlin_flame(
    config,
    preset_name: str = 'plasma',
    scale: float = 0.05,
    speed: float = 0.15,
    octaves: int = 2,
    vertical_bias: float = 0.5,
    contrast: float = 2.5,
    no_device: bool = False,
    fps: float = 2,
    debug: bool = False,
) -> None:
    """Run the Perlin noise flame animation."""
    preset = COLOR_PRESETS.get(preset_name, COLOR_PRESETS['fire'])

    if no_device:
        width, height = 32, 32
        manager = None
    else:
        manager = PanelManager(config)
        await manager.__aenter__()
        width, height = manager.canvas_size

    print(f"\033[?25l", end="")  # Hide cursor

    t = 0.0
    frame_interval = 1.0 / fps
    frame_count = 0
    start_time = asyncio.get_event_loop().time()

    try:
        while True:
            frame_start = asyncio.get_event_loop().time()

            frame = generate_frame(
                width, height, t,
                scale=scale,
                preset=preset,
                octaves=octaves,
                vertical_bias=vertical_bias,
                contrast=contrast,
            )

            # Draw frame number in center when debug mode
            if debug:
                draw = ImageDraw.Draw(frame)
                text = str(frame_count)
                # Try to load a font, fallback to default
                try:
                    font = ImageFont.truetype("arial.ttf", 16)
                except OSError:
                    font = ImageFont.load_default()
                # Get text bounding box
                bbox = draw.textbbox((0, 0), text, font=font)
                text_width = bbox[2] - bbox[0]
                text_height = bbox[3] - bbox[1]
                x = (width - text_width) // 2
                y = (height - text_height) // 2
                # Draw with black outline for visibility
                for dx in [-1, 0, 1]:
                    for dy in [-1, 0, 1]:
                        if dx != 0 or dy != 0:
                            draw.text((x + dx, y + dy), text, fill=(0, 0, 0), font=font)
                draw.text((x, y), text, fill=(255, 255, 255), font=font)

            # Build title with debug info
            if debug:
                actual_fps = frame_count / max(0.001, frame_start - start_time) if frame_count > 0 else 0
                title = f"Perlin [{preset_name}] Frame:{frame_count} FPS:{actual_fps:.1f} t:{t:.2f}"
            else:
                title = f"Perlin Flame [{preset_name}] - {width}x{height} - Ctrl+C to exit"

            print_console_preview(frame, title)

            if manager:
                send_start = asyncio.get_event_loop().time()
                await manager.send_image(frame, delay=0.01)
                send_time = asyncio.get_event_loop().time() - send_start
                if debug:
                    print(f"Frame {frame_count} sent in {send_time*1000:.0f}ms")

            frame_count += 1
            t += speed

            # Compensate for frame generation and send time
            elapsed = asyncio.get_event_loop().time() - frame_start
            sleep_time = max(0, frame_interval - elapsed)
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)

    except asyncio.CancelledError:
        pass
    finally:
        print(f"\033[?25h", end="")  # Show cursor
        if debug:
            total_time = asyncio.get_event_loop().time() - start_time
            print(f"\nTotal: {frame_count} frames in {total_time:.1f}s ({frame_count/total_time:.1f} FPS)")
        if manager:
            await manager.__aexit__(None, None, None)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Perlin noise flame effect for LED matrix"
    )
    parser.add_argument("--config", type=Path, help="Path to config file")
    parser.add_argument("--address", help="Override device address")
    parser.add_argument(
        "--preset", "-p", type=str, default="plasma",
        choices=list(COLOR_PRESETS.keys()),
        help="Color preset (default: plasma)"
    )
    parser.add_argument(
        "--scale", "-s", type=float, default=0.05,
        help="Noise scale - smaller=larger blobs (default: 0.05)"
    )
    parser.add_argument(
        "--contrast", type=float, default=2.5,
        help="Contrast multiplier 1.0-3.0 (default: 2.5)"
    )
    parser.add_argument(
        "--speed", type=float, default=0.15,
        help="Animation speed per frame (default: 0.15)"
    )
    parser.add_argument(
        "--octaves", "-o", type=int, default=2,
        help="Noise octaves - more=more detail (default: 2)"
    )
    parser.add_argument(
        "--vertical-bias", "-v", type=float, default=0.5,
        help="Vertical gradient for flame effect 0-2 (default: 0.5)"
    )
    parser.add_argument(
        "--fps", type=float, default=2,
        help="Target FPS (default: 2, BLE limited)"
    )
    parser.add_argument(
        "--no-device", action="store_true",
        help="Preview only, don't connect to LED device"
    )
    parser.add_argument(
        "--list", "-l", action="store_true",
        help="List available color presets"
    )
    parser.add_argument(
        "--debug", action="store_true",
        help="Show debug info (frame count, send time, actual FPS)"
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    if args.list:
        print("Available color presets:\n")
        for name, preset in COLOR_PRESETS.items():
            print(f"  {name}:")
            print(f"    Hue center: {preset['hue_center']}° (range: ±{preset['hue_range']//2}°)")
            print(f"    Saturation: {preset['saturation']:.0%}")
            print(f"    Brightness: {preset['brightness_min']:.0%} - {preset['brightness_max']:.0%}")
            print()
        sys.exit(0)

    config = None
    if not args.no_device:
        config = load_config(args.config)
        if args.address:
            config = replace(config, device=replace(config.device, address=args.address))

    try:
        asyncio.run(run_perlin_flame(
            config,
            preset_name=args.preset,
            scale=args.scale,
            speed=args.speed,
            octaves=args.octaves,
            vertical_bias=args.vertical_bias,
            contrast=args.contrast,
            no_device=args.no_device,
            fps=args.fps,
            debug=args.debug,
        ))
    except KeyboardInterrupt:
        print("\033[?25h", end="")  # Show cursor
        print("\nDone.")
