import argparse
import asyncio
import sys
from dataclasses import replace
from pathlib import Path
from typing import Optional
from PIL import Image, ImageDraw, ImageFont

project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from bk_light.config import AppConfig, load_config, text_options
from bk_light.fonts import resolve_font
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


def build_text_bitmap(
    text: str,
    font_path: Optional[Path],
    size: int,
    spacing: int,
    color: tuple[int, int, int],
    antialias: bool,
) -> Image.Image:
    font = load_font(font_path, size)
    formatted = text.replace("\\n", "\n")
    dummy_mode = "L" if antialias else "1"
    dummy = Image.new(dummy_mode, (1, 1), 0)
    draw_dummy = ImageDraw.Draw(dummy)
    bbox = draw_dummy.multiline_textbbox((0, 0), formatted, font=font, spacing=spacing, align="left")
    width = max(1, bbox[2] - bbox[0])
    height = max(1, bbox[3] - bbox[1])
    mask_mode = "L" if antialias else "1"
    mask = Image.new(mask_mode, (width, height), 0)
    draw_mask = ImageDraw.Draw(mask)
    draw_mask.multiline_text((-bbox[0], -bbox[1]), formatted, fill=255, font=font, spacing=spacing, align="left")
    if not antialias:
        mask = mask.convert("L")
    bitmap = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    fill = Image.new("RGBA", (width, height), (*color, 255))
    bitmap = Image.composite(fill, bitmap, mask)
    return bitmap


def render_static_frame(
    canvas: tuple[int, int],
    text_bitmap: Image.Image,
    background: tuple[int, int, int],
    offset_x: int,
    offset_y: int,
) -> Image.Image:
    frame = Image.new("RGBA", canvas, tuple(background) + (255,))
    x = (canvas[0] - text_bitmap.width) // 2 + offset_x
    y = (canvas[1] - text_bitmap.height) // 2 + offset_y
    frame.paste(text_bitmap, (x, y), text_bitmap)
    return frame.convert("RGB")


def render_scroll_frame(
    canvas: tuple[int, int],
    text_bitmap: Image.Image,
    background: tuple[int, int, int],
    direction: str,
    gap: int,
    offset_x: int,
    offset_y: int,
    position: int,
) -> Image.Image:
    strip_width = max(1, text_bitmap.width + gap)
    strip = Image.new("RGBA", (strip_width, canvas[1]), tuple(background) + (255,))
    y = (canvas[1] - text_bitmap.height) // 2 + offset_y
    strip.paste(text_bitmap, (0, y), text_bitmap)
    shift = position % strip_width
    start = offset_x - shift if direction == "left" else offset_x + shift
    while start > -strip_width:
        start -= strip_width
    frame = Image.new("RGBA", canvas, tuple(background) + (255,))
    x = start
    while x < canvas[0]:
        frame.paste(strip, (int(x), 0), strip)
        x += strip_width
    return frame.convert("RGB")


async def display_text(config: AppConfig, message: str, preset_name: str, overrides: dict[str, Optional[str]]) -> None:
    preset = text_options(config, preset_name, overrides)
    color = parse_color(overrides.get("color")) or parse_color(preset.color)
    background = parse_color(overrides.get("background")) or parse_color(preset.background)
    font_ref = overrides.get("font") or preset.font
    font_path = resolve_font(font_ref)
    text_bitmap = build_text_bitmap(
        message,
        font_path,
        preset.size,
        preset.spacing,
        color,
        config.display.antialias_text,
    )
    try:
        async with PanelManager(config) as manager:
            canvas = manager.canvas_size
            if preset.mode == "scroll":
                strip_width = max(1, text_bitmap.width + preset.gap)
                step = max(1, int(preset.step))
                position = 0
                while True:
                    frame = render_scroll_frame(
                        canvas,
                        text_bitmap,
                        background,
                        preset.direction,
                        preset.gap,
                        preset.offset_x,
                        preset.offset_y,
                        position,
                    )
                    await manager.send_image(frame, delay=0.1)
                    await asyncio.sleep(preset.interval)
                    position = (position + step) % strip_width
            else:
                frame = render_static_frame(
                    canvas,
                    text_bitmap,
                    background,
                    preset.offset_x,
                    preset.offset_y,
                )
                await manager.send_image(frame, delay=0.15)
                await asyncio.sleep(0.2)
    except asyncio.CancelledError:
        raise
    except Exception as error:
        print("ERROR", str(error))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("text")
    parser.add_argument("--config", type=Path)
    parser.add_argument("--address")
    parser.add_argument("--preset")
    parser.add_argument("--color")
    parser.add_argument("--background")
    parser.add_argument("--font", type=Path)
    parser.add_argument("--size", type=int)
    parser.add_argument("--spacing", type=int)
    parser.add_argument("--mode", choices=("static", "scroll"))
    parser.add_argument("--direction", choices=("left", "right"))
    parser.add_argument("--speed", type=float)
    parser.add_argument("--gap", type=int)
    parser.add_argument("--step", type=int)
    parser.add_argument("--offset-x", type=int)
    parser.add_argument("--offset-y", type=int)
    parser.add_argument("--interval", type=float)
    return parser.parse_args()


def build_override_map(args: argparse.Namespace) -> dict[str, Optional[str]]:
    return {
        "color": args.color,
        "background": args.background,
        "font": str(args.font) if args.font else None,
        "size": args.size,
        "spacing": args.spacing,
        "mode": args.mode,
        "direction": args.direction,
        "speed": args.speed,
        "gap": args.gap,
        "step": args.step,
        "offset_x": args.offset_x,
        "offset_y": args.offset_y,
        "interval": args.interval,
    }


if __name__ == "__main__":
    args = parse_args()
    config = load_config(args.config)
    if args.address:
        config.device = replace(config.device, address=args.address)
    preset_name = args.preset or config.runtime.preset or "default"
    overrides = build_override_map(args)
    try:
        asyncio.run(display_text(config, args.text, preset_name, overrides))
    except KeyboardInterrupt:
        pass

