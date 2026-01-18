"""Retro Demoscene Effects - Amiga/Atari ST style scrollers.

Classic 80s/90s demo effects:
- Sine scroller (text waves up/down)
- Copper/raster bars (horizontal animated color bars)
- Parallax starfield
"""

import asyncio
import math
import random
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from bk_light.config import load_config
from bk_light.panel_manager import PanelManager


# ============== COPPER BARS ==============

def render_copper_bars(size: tuple[int, int], time_t: float) -> Image.Image:
    """Render classic Amiga copper/raster bars - subtle version for slow framerate."""
    img = Image.new("RGB", size, (0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Static gradient bars - just color cycling, no movement
    # Classic copper bar look: horizontal gradient bands
    for y in range(size[1]):
        # Color cycles slowly through the spectrum based on Y position and time
        hue = (y / size[1] + time_t * 0.3) % 1.0
        # Vary intensity for banding effect
        band = (y % 8) / 8.0
        intensity = 0.4 + 0.4 * math.sin(band * math.pi)
        r, g, b = hsv_to_rgb(hue, 0.9, intensity)
        draw.line([(0, y), (size[0] - 1, y)], fill=(r, g, b))

    return img


def hsv_to_rgb(h: float, s: float, v: float) -> tuple[int, int, int]:
    """Convert HSV to RGB."""
    if s == 0:
        r = g = b = int(v * 255)
        return (r, g, b)

    i = int(h * 6)
    f = (h * 6) - i
    p = v * (1 - s)
    q = v * (1 - s * f)
    t = v * (1 - s * (1 - f))
    i = i % 6

    if i == 0:
        r, g, b = v, t, p
    elif i == 1:
        r, g, b = q, v, p
    elif i == 2:
        r, g, b = p, v, t
    elif i == 3:
        r, g, b = p, q, v
    elif i == 4:
        r, g, b = t, p, v
    else:
        r, g, b = v, p, q

    return (int(r * 255), int(g * 255), int(b * 255))


# ============== PARALLAX STARFIELD ==============

class Star:
    def __init__(self, size: tuple[int, int]):
        self.reset(size, random.random())

    def reset(self, size: tuple[int, int], initial_x: float = 1.0):
        self.x = size[0] * initial_x
        self.y = random.randint(0, size[1] - 1)
        # Slower speeds for low framerate
        self.speed = random.uniform(0.2, 1.0)
        # Faster stars are brighter (closer)
        self.brightness = 0.4 + (self.speed / 1.0) * 0.6

    def update(self, size: tuple[int, int]):
        self.x -= self.speed
        if self.x < 0:
            self.reset(size)
            self.x = size[0]


def create_starfield(size: tuple[int, int], num_stars: int = 30) -> list[Star]:
    """Create parallax starfield."""
    return [Star(size) for _ in range(num_stars)]


def render_starfield(size: tuple[int, int], stars: list[Star], time_t: float) -> Image.Image:
    """Render parallax starfield."""
    img = Image.new("RGB", size, (0, 0, 0))

    for star in stars:
        star.update(size)
        x, y = int(star.x), star.y
        if 0 <= x < size[0]:
            # Twinkle effect
            twinkle = 0.7 + 0.3 * math.sin(time_t * 10 + star.y)
            brightness = int(star.brightness * twinkle * 255)
            color = (brightness, brightness, brightness)
            img.putpixel((x, y), color)

    return img


# ============== SINE SCROLLER ==============

def render_sine_scroller(
    text: str,
    size: tuple[int, int],
    offset_x: float,
    time_t: float,
    font: ImageFont.FreeTypeFont,
    amplitude: float = 3.0,  # Reduced for slow framerate
    frequency: float = 0.1,   # Gentler wave
    with_copper: bool = True,
    with_stars: bool = False,
    stars: list[Star] = None,
) -> Image.Image:
    """Render classic sine wave scroller with optional copper bars - subtle version."""
    # Start with background effect
    if with_copper:
        img = render_copper_bars(size, time_t)
    elif with_stars and stars:
        img = render_starfield(size, stars, time_t)
    else:
        img = Image.new("RGB", size, (0, 0, 0))

    draw = ImageDraw.Draw(img)

    # Get text height for centering
    bbox = draw.textbbox((0, 0), text, font=font)
    text_height = bbox[3] - bbox[1]
    base_y = (size[1] - text_height) // 2

    x = offset_x
    for i, char in enumerate(text):
        char_bbox = draw.textbbox((0, 0), char, font=font)
        char_width = char_bbox[2] - char_bbox[0]

        if -char_width < x < size[0]:
            # Subtle sine wave - gentle movement
            sine_offset = amplitude * math.sin(2 * math.pi * (x * frequency + time_t * 0.8))
            y = base_y + sine_offset

            # Rainbow color cycling through text (slower)
            hue = (i / max(len(text), 1) + time_t * 0.3) % 1.0
            color = hsv_to_rgb(hue, 1.0, 1.0)

            # Draw character with slight outline for visibility on copper bars
            if with_copper:
                # Black outline
                for ox, oy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                    draw.text((x + ox, y + oy), char, fill=(0, 0, 0), font=font)

            draw.text((x, y), char, fill=color, font=font)

        x += char_width + 1

    return img


# ============== CHROME SCROLLER ==============

def render_chrome_scroller(
    text: str,
    size: tuple[int, int],
    offset_x: float,
    time_t: float,
    font: ImageFont.FreeTypeFont,
) -> Image.Image:
    """Chrome/metallic style scroller - shimmering gradient effect, no movement."""
    img = Image.new("RGB", size, (0, 0, 15))  # Dark blue background
    draw = ImageDraw.Draw(img)

    bbox = draw.textbbox((0, 0), text, font=font)
    text_height = bbox[3] - bbox[1]
    base_y = (size[1] - text_height) // 2

    # No bounce - static position, just color shimmer

    x = offset_x
    for i, char in enumerate(text):
        char_bbox = draw.textbbox((0, 0), char, font=font)
        char_width = char_bbox[2] - char_bbox[0]

        if -char_width < x < size[0]:
            # Chrome shimmer effect - slow color cycling
            shimmer = (time_t * 0.5 + i * 0.15) % 1.0

            # Metallic gradient: silver/cyan/white
            r = int(180 + 75 * math.sin(shimmer * 2 * math.pi))
            g = int(200 + 55 * math.sin(shimmer * 2 * math.pi + 0.5))
            b = 255

            draw.text((x, base_y), char, fill=(r, g, b), font=font)

        x += char_width + 1

    return img


# ============== FRAME GENERATION ==============

def generate_retro_frames(
    text: str,
    size: tuple[int, int],
    num_frames: int = 60,
    mode: str = "sine_copper"
) -> list[Image.Image]:
    """Generate retro demoscene animation frames."""
    # Load font
    font_path = project_root / "assets" / "fonts" / "PixelOperator.ttf"
    font_size = min(size[1] - 6, 20)

    try:
        font = ImageFont.truetype(str(font_path), font_size)
    except:
        font = ImageFont.load_default()

    # Get text width for scrolling
    temp_img = Image.new("RGB", (1, 1))
    temp_draw = ImageDraw.Draw(temp_img)
    bbox = temp_draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]

    total_scroll = size[0] + text_width + 20
    frames = []
    stars = create_starfield(size, 40) if "star" in mode else None

    for i in range(num_frames):
        t = i / num_frames
        offset_x = size[0] - (t * total_scroll)

        if mode == "sine_copper":
            frame = render_sine_scroller(text, size, offset_x, t, font,
                                         with_copper=True, with_stars=False)
        elif mode == "sine_stars":
            frame = render_sine_scroller(text, size, offset_x, t, font,
                                         with_copper=False, with_stars=True, stars=stars)
        elif mode == "chrome":
            frame = render_chrome_scroller(text, size, offset_x, t, font)
        elif mode == "copper_only":
            frame = render_copper_bars(size, t)
        elif mode == "stars_only":
            frame = render_starfield(size, stars, t)
        else:  # sine simple
            frame = render_sine_scroller(text, size, offset_x, t, font,
                                         with_copper=False, with_stars=False)

        frames.append(frame)

    return frames


# ============== MAIN ==============

async def play_retro(config, text: str, cycle_interval: float = 30.0) -> None:
    """Play retro demoscene effects, cycling through modes."""
    async with PanelManager(config) as manager:
        size = manager.canvas_size
        print(f"Canvas: {size[0]}x{size[1]}")
        print(f"Text: '{text}'")
        print("=== RETRO DEMOSCENE MODE ===")

        modes = ["sine_copper", "sine_stars", "chrome"]
        mode_index = 0

        import time

        try:
            while True:
                current_mode = modes[mode_index % len(modes)]
                print(f"\n>> Effect: {current_mode}")

                frames = generate_retro_frames(text, size, num_frames=60, mode=current_mode)
                prebuffered = manager.prebuffer_images(frames)
                print(f"Playing {len(prebuffered)} frames")

                start_time = time.time()
                while time.time() - start_time < cycle_interval:
                    for frame_data in prebuffered:
                        await manager.send_prebuffered_streaming(frame_data)
                        if time.time() - start_time >= cycle_interval:
                            break

                mode_index += 1

        except asyncio.CancelledError:
            raise


if __name__ == "__main__":
    text = sys.argv[1] if len(sys.argv) > 1 else "AMIGA RULES!"

    config = load_config()

    try:
        asyncio.run(play_retro(config, text, cycle_interval=30.0))
    except KeyboardInterrupt:
        print("\nStopped.")
