import argparse
import asyncio
import sys
from dataclasses import replace
from pathlib import Path
from typing import Dict, Optional

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from bk_light.config import AppConfig, load_config


def parse_cli_value(value: str):
    lowered = value.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        pass
    return value


def parse_option_pairs(pairs: list[str]) -> Dict[str, object]:
    result: Dict[str, object] = {}
    for pair in pairs:
        if "=" not in pair:
            continue
        key, value = pair.split("=", 1)
        result[key.strip()] = parse_cli_value(value.strip())
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path)
    parser.add_argument("--address")
    parser.add_argument("--mode")
    parser.add_argument("--preset")
    parser.add_argument("--text")
    parser.add_argument("--image", type=Path)
    parser.add_argument("--start", type=int)
    parser.add_argument("--count", type=int)
    parser.add_argument("--delay", type=float)
    parser.add_argument("--timezone")
    parser.add_argument("--option", action="append", default=[], help="Override option as key=value")
    return parser.parse_args()


def merge_options(config: AppConfig, args: argparse.Namespace) -> Dict[str, object]:
    merged: Dict[str, object] = {}
    runtime_options = config.runtime.options or {}
    for key, value in runtime_options.items():
        merged[key] = value
    cli_pairs = parse_option_pairs(args.option)
    merged.update(cli_pairs)
    if args.timezone:
        merged["timezone"] = args.timezone
    if args.text:
        merged["text"] = args.text
    if args.image:
        merged["image"] = str(args.image)
    if args.start is not None:
        merged["start"] = args.start
    if args.count is not None:
        merged["count"] = args.count
    if args.delay is not None:
        merged["delay"] = args.delay
    return merged


async def run_mode(config: AppConfig, mode: str, preset_name: str, options: Dict[str, str]) -> None:
    mode = mode.lower()
    if mode == "clock":
        from scripts.clock_display import run_clock
        await run_clock(config, preset_name, options)
    elif mode == "text":
        from scripts.display_text import display_text
        message = options.get("text")
        if not message:
            raise ValueError("Text mode requires a message. Provide runtime.options.text or --text.")
        overrides = {k: v for k, v in options.items() if k != "text"}
        await display_text(config, message, preset_name, overrides)
    elif mode == "image":
        from scripts.send_image import send_image
        image_path = options.get("image")
        if not image_path:
            raise ValueError("Image mode requires an image path. Provide runtime.options.image or --image.")
        overrides = {k: v for k, v in options.items() if k != "image"}
        await send_image(config, Path(image_path), preset_name, overrides)
    elif mode == "counter":
        from scripts.increment_counter import run_counter
        await run_counter(config, preset_name, options)
    else:
        raise ValueError(f"Unsupported mode '{mode}'")


if __name__ == "__main__":
    args = parse_args()
    config = load_config(args.config)
    if args.address:
        config.device = replace(config.device, address=args.address)
    mode = args.mode or config.runtime.mode or "clock"
    preset_name = args.preset or config.runtime.preset or "default"
    options = merge_options(config, args)
    asyncio.run(run_mode(config, mode, preset_name, options))

