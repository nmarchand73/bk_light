import argparse
import asyncio
import sys
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from PIL import Image, ImageDraw, ImageFont

project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from bk_light.config import AppConfig, clock_options, load_config
from bk_light.fonts import get_font_profile, resolve_font
from bk_light.panel_manager import PanelManager


def parse_color(value: Optional[str]) -> Optional[tuple[int, int, int]]:
    if value is None:
        return None
    cleaned = value.replace("#", "").replace(" ", "")
    if "," in cleaned:
        parts = cleaned.split(",")
        return tuple(int(part) for part in parts[:3])
    if len(cleaned) == 6:
        return tuple(int(cleaned[i:i + 2], 16) for i in (0, 2, 4))
    raise ValueError("Invalid color")


def load_font(path: Optional[Path], size: int) -> ImageFont.ImageFont:
    if path is None:
        return ImageFont.load_default()
    try:
        return ImageFont.truetype(str(path), size)
    except Exception:
        return ImageFont.load_default()


def resolve_timezone(config: AppConfig, override: Optional[str]) -> timezone:
    tz_name = override or config.device.timezone
    if not tz_name or tz_name == "auto":
        return datetime.now().astimezone().tzinfo or timezone.utc
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(tz_name)
    except Exception:
        return datetime.now().astimezone().tzinfo or timezone.utc


def build_clock_image(
    canvas: tuple[int, int],
    text: str,
    color: tuple[int, int, int],
    accent: tuple[int, int, int],
    background: tuple[int, int, int],
    font_path: Optional[Path],
    size: int,
    colon_visible: bool,
    antialias: bool,
    offset_x: int,
    offset_y: int,
    colon_dx: int,
    colon_top_adjust: int,
    colon_bottom_adjust: int,
) -> Image.Image:
    font = load_font(font_path, size)
    mask_mode = "L" if antialias else "1"
    dummy = Image.new(mask_mode, (1, 1), 0)
    draw_dummy = ImageDraw.Draw(dummy)
    digit_glyphs: dict[str, Image.Image] = {}
    digit_bboxes: dict[str, tuple[int, int, int, int]] = {}
    max_digit_width = 1
    digit_top: Optional[int] = None
    digit_bottom: Optional[int] = None
    for value in range(10):
        char = str(value)
        bbox = draw_dummy.textbbox((0, 0), char, font=font)
        if bbox is None:
            continue
        digit_bboxes[char] = bbox
        width = max(1, bbox[2] - bbox[0])
        height = max(1, bbox[3] - bbox[1])
        max_digit_width = max(max_digit_width, width)
        digit_top = bbox[1] if digit_top is None else min(digit_top, bbox[1])
        digit_bottom = bbox[3] if digit_bottom is None else max(digit_bottom, bbox[3])
        mask = Image.new(mask_mode, (width, height), 0)
        draw_mask = ImageDraw.Draw(mask)
        draw_mask.text((-bbox[0], -bbox[1]), char, fill=255, font=font)
        if not antialias:
            mask = mask.convert("L")
        layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        fill_layer = Image.new("RGBA", (width, height), (*color, 255))
        glyph = Image.composite(fill_layer, layer, mask)
        digit_glyphs[char] = glyph
    if digit_top is None or digit_bottom is None:
        digit_top = 0
        digit_bottom = size
    digit_height = max(1, digit_bottom - digit_top)
    def render_segment(segment: str) -> Image.Image:
        if not segment:
            return Image.new("RGBA", (1, digit_height), (0, 0, 0, 0))
        length = len(segment)
        segment_width = length * max_digit_width
        segment_image = Image.new("RGBA", (segment_width, digit_height), (0, 0, 0, 0))
        position = 0
        for char in segment:
            glyph = digit_glyphs.get(char)
            bbox = digit_bboxes.get(char)
            if glyph is None or bbox is None:
                position += max_digit_width
                continue
            padding = (max_digit_width - glyph.width) // 2
            y_offset = bbox[1] - digit_top
            segment_image.alpha_composite(glyph, (position + padding, y_offset))
            position += max_digit_width
        return segment_image
    parts = text.split(":", 1)
    left_text = parts[0]
    right_text = parts[1] if len(parts) > 1 else ""
    left_segment = render_segment(left_text)
    right_segment = render_segment(right_text)
    extra_gap = 1 if right_text else 0
    colon_width = 1 if right_text else 0
    total_width = left_segment.width + extra_gap + colon_width + right_segment.width
    frame = Image.new("RGBA", canvas, tuple(background) + (255,))
    origin_x = int((canvas[0] - total_width) // 2) + offset_x
    origin_y = int((canvas[1] - digit_height) // 2) + offset_y
    frame.alpha_composite(left_segment, (origin_x, origin_y))
    if right_text:
        right_x = origin_x + left_segment.width + extra_gap + colon_width
        frame.alpha_composite(right_segment, (right_x, origin_y))
    frame_rgb = frame.convert("RGB")
    if right_text:
        baseline = origin_y - digit_top + digit_height / 2
        gap = digit_height * 0.35
        base_top = int(round(baseline - gap))
        base_bottom = int(round(baseline + gap))
        colon_column = origin_x + left_segment.width + colon_dx
        colon_column = max(0, min(canvas[0] - 1, colon_column))
        top = base_top + colon_top_adjust
        bottom = base_bottom + colon_bottom_adjust
        if bottom < top:
            top, bottom = bottom, top
        if bottom == top:
            if bottom < canvas[1] - 1:
                bottom += 1
            elif top > 0:
                top -= 1
        top = max(0, min(canvas[1] - 1, top))
        bottom = max(0, min(canvas[1] - 1, bottom))
        if colon_visible:
            for row in (top, bottom):
                if 0 <= row < canvas[1]:
                    frame_rgb.putpixel((colon_column, row), accent)
        else:
            for row in range(top, bottom + 1):
                if 0 <= row < canvas[1]:
                    frame_rgb.putpixel((colon_column, row), background)
    return frame_rgb


async def run_clock(config: AppConfig, preset_name: str, overrides: dict[str, Optional[str]]) -> None:
    preset = clock_options(config, preset_name, overrides)
    tz = resolve_timezone(config, overrides.get("timezone"))
    color = parse_color(overrides.get("color")) or parse_color(preset.color)
    accent = parse_color(overrides.get("accent")) or parse_color(preset.accent)
    background = parse_color(overrides.get("background")) or parse_color(preset.background)
    font_ref = overrides.get("font") or preset.font
    font_path = resolve_font(font_ref)
    profile = get_font_profile(font_ref, font_path)
    if overrides.get("size") is not None:
        size = int(overrides["size"])
    elif profile.recommended_size is not None:
        size = int(profile.recommended_size)
    else:
        size = preset.size
    size = max(1, int(round(size)))
    interval = preset.interval
    dot_flashing = preset.dot_flashing
    flash_period = preset.dot_flash_period
    last_stamp = ""
    last_colon = True
    loop = asyncio.get_running_loop()
    start_time = loop.time()
    try:
        async with PanelManager(config) as manager:
            canvas = manager.canvas_size
            while True:
                now = datetime.now(tz)
                if preset.format == "12h":
                    stamp = now.strftime("%I:%M")
                    if stamp.startswith("0"):
                        stamp = stamp[1:]
                else:
                    stamp = now.strftime("%H:%M")
                elapsed = loop.time() - start_time
                colon_visible = True
                if dot_flashing:
                    colon_visible = int(elapsed / flash_period) % 2 == 0
                if stamp != last_stamp or colon_visible != last_colon:
                    image = build_clock_image(
                        canvas,
                        stamp,
                        color,
                        accent,
                        background,
                        font_path,
                        size,
                        colon_visible,
                        config.display.antialias_text,
                        profile.offset_x,
                        profile.offset_y,
                        profile.colon_dx,
                        profile.colon_top_adjust,
                        profile.colon_bottom_adjust,
                    )
                    await manager.send_image(image, delay=0.15)
                    last_stamp = stamp
                    last_colon = colon_visible
                await asyncio.sleep(interval)
    except asyncio.CancelledError:
        raise
    except Exception as error:
        print("ERROR", str(error))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path)
    parser.add_argument("--address")
    parser.add_argument("--preset")
    parser.add_argument("--timezone")
    parser.add_argument("--format", choices=("12h", "24h"))
    parser.add_argument("--color")
    parser.add_argument("--accent")
    parser.add_argument("--background")
    parser.add_argument("--font", type=Path)
    parser.add_argument("--size", type=int)
    parser.add_argument("--interval", type=float)
    parser.add_argument("--dot-flashing", choices=("on", "off"))
    parser.add_argument("--dot-flash-period", type=float)
    return parser.parse_args()


def build_override_map(args: argparse.Namespace) -> dict[str, Optional[str]]:
    overrides: dict[str, Optional[str]] = {
        "timezone": args.timezone,
        "format": args.format,
        "color": args.color,
        "accent": args.accent,
        "background": args.background,
        "font": str(args.font) if args.font else None,
        "size": args.size,
        "interval": args.interval,
        "dot_flash_period": args.dot_flash_period,
    }
    if args.dot_flashing == "on":
        overrides["dot_flashing"] = True
    elif args.dot_flashing == "off":
        overrides["dot_flashing"] = False
    return overrides


if __name__ == "__main__":
    args = parse_args()
    config = load_config(args.config)
    if args.address:
        config.device = replace(config.device, address=args.address)
    preset_name = args.preset or config.runtime.preset or "default"
    overrides = build_override_map(args)
    try:
        asyncio.run(run_clock(config, preset_name, overrides))
    except KeyboardInterrupt:
        pass

