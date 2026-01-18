"""Wheels animation - Concentric rotating rings.

Inspired by: https://imaginary-institute.com/previews/preview-wheels.html
"""

import argparse
import asyncio
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


# =============================================================================
# CONFIGURATION
# =============================================================================

SCRIPT_NAME = "Wheels Animation"
DEFAULT_FPS = 2  # BLE device limit

# Colors - Match original algorithm
COLOR_ORANGE = (255, 135, 20)   # color(180, 95, 10) in RGB approx
COLOR_BLUE = (0, 80, 110)       # color(0, 80, 110)


# =============================================================================
# ANIMATION - Following original algorithm exactly
# =============================================================================

def generate_frame(
    width: int,
    height: int,
    t: float,
    ring_thickness: float = 4,
    angle_bump: float = 0.3,
    **kwargs,
) -> Image.Image:
    """Generate a single animation frame.

    Original algorithm:
      - Draw orange disk
      - Draw blue half-disk (arc) on top
      - Decrease diameter, increase angle
      - Repeat

    Args:
        width: Frame width in pixels
        height: Frame height in pixels
        t: Time parameter (AngleStart)
        ring_thickness: Thickness of each ring
        angle_bump: Rotation increment per ring

    Returns:
        PIL Image (RGB mode)
    """
    image = Image.new('RGB', (width, height), COLOR_BLUE)
    draw = ImageDraw.Draw(image)

    cx = width / 2
    cy = height / 2

    diam = min(width, height)
    angle = t  # AngleStart

    while diam > 0:
        # Bounding box for this circle
        x0 = cx - diam / 2
        y0 = cy - diam / 2
        x1 = cx + diam / 2
        y1 = cy + diam / 2
        bbox = [x0, y0, x1, y1]

        # Draw orange disk
        draw.ellipse(bbox, fill=COLOR_ORANGE)

        # Draw blue half-disk on top (arc from angle to angle+180°)
        start_deg = math.degrees(angle)
        end_deg = start_deg + 180
        draw.pieslice(bbox, start=start_deg, end=end_deg, fill=COLOR_BLUE)

        # Next ring: smaller diameter, more rotation
        diam -= ring_thickness
        angle += angle_bump

    return image


def add_custom_args(parser: argparse.ArgumentParser) -> None:
    """Add custom command line arguments for this animation."""
    parser.add_argument(
        "--thickness", "-t", type=float, default=4,
        help="Ring thickness in pixels (default: 4)"
    )
    parser.add_argument(
        "--bump", "-b", type=float, default=0.3,
        help="Angle bump per ring in radians (default: 0.3)"
    )


# =============================================================================
# CONSOLE PREVIEW - DO NOT MODIFY
# =============================================================================

def print_console_preview(image: Image.Image, title: str = "") -> None:
    """Print a dot-matrix preview to console with colors."""
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


def draw_debug_overlay(image: Image.Image, frame_count: int) -> None:
    """Draw frame number in center of image."""
    width, height = image.size
    draw = ImageDraw.Draw(image)
    text = str(frame_count)

    try:
        font = ImageFont.truetype("arial.ttf", 16)
    except OSError:
        font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    x = (width - text_width) // 2
    y = (height - text_height) // 2

    # Black outline
    for dx in [-1, 0, 1]:
        for dy in [-1, 0, 1]:
            if dx != 0 or dy != 0:
                draw.text((x + dx, y + dy), text, fill=(0, 0, 0), font=font)
    # White text
    draw.text((x, y), text, fill=(255, 255, 255), font=font)


# =============================================================================
# MAIN LOOP - DO NOT MODIFY
# =============================================================================

async def run_animation(
    config,
    speed: float = 0.3,
    no_device: bool = False,
    fps: float = DEFAULT_FPS,
    debug: bool = False,
    **kwargs,
) -> None:
    """Main animation loop."""
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

            # Generate frame
            frame = generate_frame(width, height, t, **kwargs)

            # Debug overlay
            if debug:
                draw_debug_overlay(frame, frame_count)
                actual_fps = frame_count / max(0.001, frame_start - start_time) if frame_count > 0 else 0
                title = f"{SCRIPT_NAME} | Frame:{frame_count} FPS:{actual_fps:.1f} t:{t:.2f}"
            else:
                title = f"{SCRIPT_NAME} - {width}x{height} - Ctrl+C to exit"

            # Console preview
            print_console_preview(frame, title)

            # Send to device
            if manager:
                send_start = asyncio.get_event_loop().time()
                await manager.send_image(frame, delay=0.01)
                if debug:
                    send_time = asyncio.get_event_loop().time() - send_start
                    print(f"Frame {frame_count} sent in {send_time*1000:.0f}ms")

            frame_count += 1
            t += speed

            # Maintain target FPS
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


# =============================================================================
# ARGUMENT PARSING
# =============================================================================

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=SCRIPT_NAME)

    # Standard arguments
    parser.add_argument("--config", type=Path, help="Path to config file")
    parser.add_argument("--address", help="Override device address")
    parser.add_argument(
        "--speed", type=float, default=0.3,
        help="Animation speed per frame (default: 0.3)"
    )
    parser.add_argument(
        "--fps", type=float, default=DEFAULT_FPS,
        help=f"Target FPS (default: {DEFAULT_FPS}, BLE limited)"
    )
    parser.add_argument(
        "--no-device", action="store_true",
        help="Preview only, don't connect to LED device"
    )
    parser.add_argument(
        "--debug", action="store_true",
        help="Show debug info (frame count, send time, actual FPS)"
    )

    # Custom arguments for this animation
    add_custom_args(parser)

    return parser.parse_args()


# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    args = parse_args()

    config = None
    if not args.no_device:
        config = load_config(args.config)
        if args.address:
            config = replace(config, device=replace(config.device, address=args.address))

    # Extract custom kwargs
    custom_kwargs = {
        'ring_thickness': args.thickness,
        'angle_bump': args.bump,
    }

    try:
        asyncio.run(run_animation(
            config,
            speed=args.speed,
            no_device=args.no_device,
            fps=args.fps,
            debug=args.debug,
            **custom_kwargs,
        ))
    except KeyboardInterrupt:
        print("\033[?25h", end="")  # Show cursor
        print("\nDone.")
