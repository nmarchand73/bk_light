"""Play animated GIF on BK-Light LED panels.

Streams GIF frames over BLE for smooth animation playback.
"""

import argparse
import asyncio
import sys
from dataclasses import replace
from pathlib import Path

from PIL import Image

project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from bk_light.config import load_config
from bk_light.panel_manager import PanelManager


def load_gif_frames(
    gif_path: Path,
    target_size: tuple[int, int],
) -> list[tuple[Image.Image, float]]:
    """Load and resize GIF frames."""
    gif = Image.open(gif_path)
    frames = []
    canvas = None

    try:
        frame_idx = 0
        while True:
            gif.seek(frame_idx)
            duration_ms = gif.info.get("duration", 100)
            if duration_ms <= 0:
                duration_ms = 100

            if canvas is None:
                canvas = Image.new("RGBA", gif.size, (0, 0, 0, 255))

            frame = gif.convert("RGBA")
            canvas = Image.alpha_composite(canvas, frame)

            # Resize to target size
            result = canvas.convert("RGB").copy()
            if result.size != target_size:
                result = result.resize(target_size, Image.Resampling.NEAREST)

            frames.append((result, duration_ms / 1000.0))

            disposal = gif.info.get("disposal", 0)
            if disposal == 2:
                canvas = Image.new("RGBA", gif.size, (0, 0, 0, 255))

            frame_idx += 1
    except EOFError:
        pass

    gif.close()
    return frames


async def play_gif(
    config,
    gif_path: Path,
    speed: float = 1.0,
    brightness: float = 1.0,
    use_timing: bool = False,
) -> None:
    """Stream GIF frames over BLE."""
    config = replace(config, device=replace(config.device, brightness=brightness))

    print(f"Loading GIF: {gif_path.name}")

    async with PanelManager(config) as manager:
        canvas_size = manager.canvas_size
        print(f"Canvas size: {canvas_size[0]}x{canvas_size[1]}")

        frames = load_gif_frames(gif_path, canvas_size)
        print(f"Loaded {len(frames)} frames")

        if not frames:
            print("Error: No frames found in GIF")
            return

        # Pre-buffer all frames to avoid conversion during playback
        print("Pre-buffering frames...")
        frame_images = [img for img, _ in frames]
        durations = [d for _, d in frames]
        prebuffered = manager.prebuffer_images(frame_images)
        print(f"Pre-buffered {len(prebuffered)} frames")

        if use_timing:
            total_duration = sum(durations)
            avg_frame_duration = total_duration / len(frames) if frames else 0
            print(f"Duration: {total_duration:.1f}s per loop ({avg_frame_duration*1000:.0f}ms avg per frame)")
            print(f"Speed: {speed}x")
        else:
            print("Speed: MAX (no delay)")
        print("Playing... Press Ctrl+C to stop")

        try:
            loop_obj = asyncio.get_running_loop()

            if use_timing:
                while True:
                    for frame_data, duration in zip(prebuffered, durations):
                        frame_start = loop_obj.time()
                        await manager.send_prebuffered_streaming(frame_data)

                        # Calculate remaining time for this frame
                        elapsed = loop_obj.time() - frame_start
                        target_duration = duration / speed
                        remaining = target_duration - elapsed

                        if remaining > 0:
                            await asyncio.sleep(remaining)
            else:
                # No delays - play as fast as BLE allows
                while True:
                    for frame_data in prebuffered:
                        await manager.send_prebuffered_streaming(frame_data)

        except asyncio.CancelledError:
            raise


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Play GIF on BK-Light LED panel")
    parser.add_argument("gif", type=Path, help="Path to GIF file")
    parser.add_argument("--config", type=Path, help="Config file")
    parser.add_argument("--address", help="Device BLE address")
    parser.add_argument("--speed", type=float, default=1.0, help="Playback speed multiplier (only with --use-timing)")
    parser.add_argument("--brightness", type=float, default=1.0, help="Brightness (0.0-1.0)")
    parser.add_argument("--use-timing", action="store_true", help="Respect GIF frame timing (default: max speed)")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    if not args.gif.exists():
        print(f"Error: File not found: {args.gif}")
        sys.exit(1)

    config = load_config(args.config)
    if args.address:
        config = replace(config, device=replace(config.device, address=args.address))

    try:
        asyncio.run(play_gif(
            config,
            args.gif,
            speed=args.speed,
            brightness=args.brightness,
            use_timing=args.use_timing,
        ))
    except KeyboardInterrupt:
        print("\nStopped.")
