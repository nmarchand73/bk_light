"""2D Animated Text Display - Rainbow scrolling with wave effect."""

import asyncio
import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from bk_light.config import load_config
from bk_light.panel_manager import PanelManager


def get_rainbow_color(t: float) -> tuple[int, int, int]:
    """Get rainbow color from position t (0-1)."""
    hue = t * 360
    h = hue / 60
    i = int(h) % 6
    f = h - int(h)

    if i == 0:
        return (255, int(255 * f), 0)
    elif i == 1:
        return (int(255 * (1 - f)), 255, 0)
    elif i == 2:
        return (0, 255, int(255 * f))
    elif i == 3:
        return (0, int(255 * (1 - f)), 255)
    elif i == 4:
        return (int(255 * f), 0, 255)
    else:
        return (255, 0, int(255 * (1 - f)))


def render_text_frame(
    text: str,
    size: tuple[int, int],
    offset_x: float,
    time_t: float,
    font: ImageFont.FreeTypeFont,
    wave_amplitude: float = 3.0,
    wave_frequency: float = 0.3,
) -> Image.Image:
    """Render a single frame with rainbow text and wave effect."""
    img = Image.new("RGB", size, (0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Get text dimensions
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]

    # Center vertically
    base_y = (size[1] - text_height) // 2

    # Draw each character with individual color and wave offset
    x = offset_x
    for i, char in enumerate(text):
        # Rainbow color based on character position and time
        color_t = (i / max(len(text), 1) + time_t) % 1.0
        color = get_rainbow_color(color_t)

        # Wave effect - vertical offset based on position and time
        wave_offset = wave_amplitude * math.sin(2 * math.pi * (i * wave_frequency + time_t * 2))
        y = base_y + wave_offset

        # Draw character
        char_bbox = draw.textbbox((0, 0), char, font=font)
        char_width = char_bbox[2] - char_bbox[0]

        if -char_width < x < size[0]:
            draw.text((x, y), char, fill=color, font=font)

        x += char_width + 1  # spacing

    return img


def render_typewriter_frame(
    text: str,
    size: tuple[int, int],
    visible_chars: int,
    time_t: float,
    font: ImageFont.FreeTypeFont,
) -> Image.Image:
    """Render typewriter effect - letters appear one by one."""
    img = Image.new("RGB", size, (0, 0, 0))
    draw = ImageDraw.Draw(img)

    visible_text = text[:visible_chars]
    if not visible_text:
        return img

    # Get text dimensions
    bbox = draw.textbbox((0, 0), visible_text, font=font)
    text_height = bbox[3] - bbox[1]
    base_y = (size[1] - text_height) // 2

    # Start from left edge with small margin
    x = 2
    for i, char in enumerate(visible_text):
        color_t = (i / max(len(text), 1) + time_t) % 1.0
        color = get_rainbow_color(color_t)

        char_bbox = draw.textbbox((0, 0), char, font=font)
        char_width = char_bbox[2] - char_bbox[0]

        if x < size[0]:
            draw.text((x, base_y), char, fill=color, font=font)
        x += char_width + 1

    # Blinking cursor at end
    if int(time_t * 8) % 2 == 0 and x < size[0]:
        cursor_color = get_rainbow_color(time_t)
        draw.rectangle([x, base_y, x + 2, base_y + text_height], fill=cursor_color)

    return img


def render_reveal_frame(
    text: str,
    size: tuple[int, int],
    reveal_progress: float,
    time_t: float,
    font: ImageFont.FreeTypeFont,
) -> Image.Image:
    """Render reveal effect - text revealed from left with sparkle."""
    img = Image.new("RGB", size, (0, 0, 0))
    draw = ImageDraw.Draw(img)

    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]

    # Center or left-align based on text width
    if text_width < size[0]:
        start_x = (size[0] - text_width) // 2
    else:
        start_x = 2

    base_y = (size[1] - text_height) // 2
    reveal_x = start_x + reveal_progress * (text_width + 10)

    x = start_x
    for i, char in enumerate(text):
        char_bbox = draw.textbbox((0, 0), char, font=font)
        char_width = char_bbox[2] - char_bbox[0]
        char_center = x + char_width // 2

        if char_center < reveal_x:
            # Revealed - full color
            color_t = (i / max(len(text), 1) + time_t * 0.5) % 1.0
            color = get_rainbow_color(color_t)
            if 0 <= x < size[0]:
                draw.text((x, base_y), char, fill=color, font=font)
        elif char_center < reveal_x + 5:
            # At reveal edge - bright white sparkle
            if 0 <= x < size[0]:
                draw.text((x, base_y), char, fill=(255, 255, 255), font=font)

        x += char_width + 1

    return img


def render_vertical_scroll_frame(
    text: str,
    size: tuple[int, int],
    offset_y: float,
    time_t: float,
    font: ImageFont.FreeTypeFont,
) -> Image.Image:
    """Render vertical scrolling for long text split into lines."""
    img = Image.new("RGB", size, (0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Split text to fit width
    words = list(text)  # Split into characters for long text
    char_bbox = draw.textbbox((0, 0), "W", font=font)
    char_width = char_bbox[2] - char_bbox[0] + 1
    char_height = char_bbox[3] - char_bbox[1]
    chars_per_line = max(1, (size[0] - 4) // char_width)

    # Create lines
    lines = []
    for i in range(0, len(text), chars_per_line):
        lines.append(text[i:i + chars_per_line])

    # Draw lines with vertical offset
    line_height = char_height + 2
    y = offset_y

    for line_idx, line in enumerate(lines):
        if -line_height < y < size[1]:
            x = 2
            for char_idx, char in enumerate(line):
                global_idx = line_idx * chars_per_line + char_idx
                color_t = (global_idx / max(len(text), 1) + time_t * 0.3) % 1.0
                color = get_rainbow_color(color_t)
                draw.text((x, y), char, fill=color, font=font)
                x += char_width
        y += line_height

    return img


def render_wave_scroll_frame(
    text: str,
    size: tuple[int, int],
    offset_x: float,
    time_t: float,
    font: ImageFont.FreeTypeFont,
) -> Image.Image:
    """Scrolling text with wave motion - best for long text."""
    img = Image.new("RGB", size, (0, 0, 0))
    draw = ImageDraw.Draw(img)

    bbox = draw.textbbox((0, 0), text, font=font)
    text_height = bbox[3] - bbox[1]
    base_y = (size[1] - text_height) // 2

    x = offset_x
    for i, char in enumerate(text):
        color_t = (i / max(len(text), 1) + time_t) % 1.0
        color = get_rainbow_color(color_t)

        # Wave based on absolute position for smooth scrolling wave
        wave_offset = 3 * math.sin(2 * math.pi * (x / 20 + time_t * 2))
        y = base_y + wave_offset

        char_bbox = draw.textbbox((0, 0), char, font=font)
        char_width = char_bbox[2] - char_bbox[0]

        if -char_width < x < size[0]:
            draw.text((x, y), char, fill=color, font=font)

        x += char_width + 1

    return img


def render_big_letter_frame(
    text: str,
    size: tuple[int, int],
    char_index: int,
    time_t: float,
    font: ImageFont.FreeTypeFont,
) -> Image.Image:
    """Show one big letter at a time, centered."""
    img = Image.new("RGB", size, (0, 0, 0))
    draw = ImageDraw.Draw(img)

    if char_index >= len(text):
        return img

    char = text[char_index]

    # Get character size
    bbox = draw.textbbox((0, 0), char, font=font)
    char_width = bbox[2] - bbox[0]
    char_height = bbox[3] - bbox[1]

    # Center the character
    x = (size[0] - char_width) // 2
    y = (size[1] - char_height) // 2

    # Rainbow color cycling
    color_t = (char_index / max(len(text), 1) + time_t * 0.5) % 1.0
    color = get_rainbow_color(color_t)

    draw.text((x, y), char, fill=color, font=font)

    return img


def generate_animation_frames(
    text: str,
    size: tuple[int, int],
    num_frames: int = 60,
    mode: str = "scroll"
) -> list[Image.Image]:
    """Generate animation frames."""
    # Load font
    font_path = project_root / "assets" / "fonts" / "PixelOperator.ttf"
    font_size = min(size[1] - 4, 24)

    try:
        font = ImageFont.truetype(str(font_path), font_size)
    except:
        font = ImageFont.load_default()

    # Get text width
    temp_img = Image.new("RGB", (1, 1))
    temp_draw = ImageDraw.Draw(temp_img)
    bbox = temp_draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]

    frames = []
    is_long_text = text_width > size[0]

    if mode == "wave_scroll":
        # Scrolling with wave motion - great for long text
        total_scroll = size[0] + text_width + 20
        for i in range(num_frames):
            t = i / num_frames
            offset_x = size[0] - (t * total_scroll)
            frame = render_wave_scroll_frame(text, size, offset_x, t, font)
            frames.append(frame)

    elif mode == "typewriter":
        # Typewriter effect - letters appear one by one
        chars_to_show = len(text)
        for i in range(num_frames):
            t = i / num_frames
            visible = int(t * (chars_to_show + 5))  # +5 for pause at end
            visible = min(visible, chars_to_show)
            frame = render_typewriter_frame(text, size, visible, t, font)
            frames.append(frame)

    elif mode == "reveal":
        # Sparkle reveal from left to right
        for i in range(num_frames):
            t = i / num_frames
            frame = render_reveal_frame(text, size, t, t, font)
            frames.append(frame)

    elif mode == "vertical":
        # Vertical scrolling for very long text
        char_height = text_height + 2
        chars_per_line = max(1, (size[0] - 4) // ((text_width // len(text)) + 1))
        num_lines = (len(text) + chars_per_line - 1) // chars_per_line
        total_height = num_lines * char_height

        total_scroll = size[1] + total_height
        for i in range(num_frames):
            t = i / num_frames
            offset_y = size[1] - (t * total_scroll)
            frame = render_vertical_scroll_frame(text, size, offset_y, t, font)
            frames.append(frame)

    elif mode == "scroll":
        # Classic horizontal scroll with rainbow
        total_scroll = size[0] + text_width + 20
        for i in range(num_frames):
            t = i / num_frames
            offset_x = size[0] - (t * total_scroll)
            frame = render_text_frame(text, size, offset_x, t, font)
            frames.append(frame)

    elif mode == "big_letter":
        # Show each letter one at a time, big and centered
        # Use larger font for big letters
        big_font_size = min(size[1] - 2, size[0] - 2, 28)
        try:
            big_font = ImageFont.truetype(str(font_path), big_font_size)
        except:
            big_font = font

        frames_per_char = max(4, num_frames // len(text))
        for i in range(num_frames):
            t = i / num_frames
            char_idx = min(int(i / frames_per_char), len(text) - 1)
            frame = render_big_letter_frame(text, size, char_idx, t, big_font)
            frames.append(frame)

    else:  # wave, pulse, bounce - only for short text
        if is_long_text:
            # Fallback to wave_scroll for long text
            return generate_animation_frames(text, size, num_frames, "wave_scroll")

        if mode == "wave":
            offset_x = (size[0] - text_width) // 2
            for i in range(num_frames):
                t = i / num_frames
                frame = render_text_frame(text, size, offset_x, t, font, wave_amplitude=4)
                frames.append(frame)

        elif mode == "pulse":
            offset_x = (size[0] - text_width) // 2
            for i in range(num_frames):
                t = i / num_frames
                frame = render_text_frame(text, size, offset_x, t * 3, font, wave_amplitude=0)
                frames.append(frame)

        elif mode == "bounce":
            for i in range(num_frames):
                t = i / num_frames
                bounce_x = (size[0] - text_width) // 2 + math.sin(t * 2 * math.pi) * (size[0] - text_width) // 3
                frame = render_text_frame(text, size, bounce_x, t, font, wave_amplitude=2)
                frames.append(frame)

    return frames


async def play_animation(config, text: str, cycle_interval: float = 30.0) -> None:
    """Play animated text cycling through different modes."""
    async with PanelManager(config) as manager:
        size = manager.canvas_size
        print(f"Canvas: {size[0]}x{size[1]}")
        print(f"Text: '{text}'")

        # Check if text is long
        temp_img = Image.new("RGB", (1, 1))
        temp_draw = ImageDraw.Draw(temp_img)
        font_path = project_root / "assets" / "fonts" / "PixelOperator.ttf"
        try:
            font = ImageFont.truetype(str(font_path), min(size[1] - 4, 24))
        except:
            font = ImageFont.load_default()
        bbox = temp_draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        is_long = text_width > size[0]

        # Choose modes based on text length
        # 32x32 display = only ~4-5 chars fit, so scrolling is best for long text
        if is_long:
            modes = ["wave_scroll", "big_letter", "scroll"]  # Scrolling + big letter for long
        else:
            modes = ["wave", "pulse", "wave_scroll"]  # Short text can use centered modes

        mode_index = 0
        import time

        try:
            while True:
                current_mode = modes[mode_index % len(modes)]
                print(f"\n>> Mode: {current_mode}")

                # Generate frames for current mode
                frames = generate_animation_frames(text, size, num_frames=48, mode=current_mode)
                prebuffered = manager.prebuffer_images(frames)
                print(f"Playing {len(prebuffered)} frames")

                # Play for cycle_interval seconds
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
    text = sys.argv[1] if len(sys.argv) > 1 else "HELLO"

    config = load_config()

    try:
        asyncio.run(play_animation(config, text, cycle_interval=30.0))
    except KeyboardInterrupt:
        print("\nStopped.")
