"""Galaxy animation effect for BK-Light LED panels."""

import argparse
import asyncio
import math
import random
import sys
from dataclasses import replace
from pathlib import Path

from PIL import Image

project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from bk_light.config import load_config
from bk_light.panel_manager import PanelManager


def create_star_field(width: int, height: int, count: int, seed: int = 42) -> list[tuple[int, int, float]]:
    """Generate random star positions with brightness values."""
    rng = random.Random(seed)
    stars = []
    for _ in range(count):
        x = rng.randint(0, width - 1)
        y = rng.randint(0, height - 1)
        brightness = rng.uniform(0.3, 1.0)
        stars.append((x, y, brightness))
    return stars


def spiral_density(x: float, y: float, cx: float, cy: float, angle: float, arms: int = 2) -> float:
    """Calculate spiral arm density at a point."""
    dx = x - cx
    dy = y - cy
    distance = math.sqrt(dx * dx + dy * dy)
    if distance < 0.5:
        return 1.0

    theta = math.atan2(dy, dx) + angle
    arm_angle = (theta * arms) - (distance * 0.4)
    arm_density = (math.cos(arm_angle) + 1) / 2
    falloff = math.exp(-distance * 0.15)
    return arm_density * falloff


def render_galaxy_frame(
    width: int,
    height: int,
    angle: float,
    stars: list[tuple[int, int, float]],
    twinkle_phase: float,
    core_color: tuple[int, int, int] = (255, 220, 180),
    arm_color: tuple[int, int, int] = (100, 120, 200),
    star_color: tuple[int, int, int] = (200, 200, 255),
) -> Image.Image:
    """Render a single frame of the galaxy animation."""
    image = Image.new("RGB", (width, height), (0, 0, 0))
    pixels = image.load()

    cx, cy = width / 2, height / 2
    max_radius = max(width, height) / 2

    # Draw spiral arms and core
    for y in range(height):
        for x in range(width):
            dx = x - cx
            dy = y - cy
            distance = math.sqrt(dx * dx + dy * dy)

            # Core glow
            core_intensity = max(0, 1 - (distance / (max_radius * 0.3)))
            core_intensity = core_intensity ** 2

            # Spiral arms
            arm_intensity = spiral_density(x, y, cx, cy, angle, arms=2)

            # Combine
            total = min(1.0, core_intensity * 1.5 + arm_intensity * 0.6)

            if total > 0.05:
                # Blend core and arm colors based on distance
                blend = min(1.0, distance / (max_radius * 0.5))
                r = int(core_color[0] * (1 - blend) + arm_color[0] * blend)
                g = int(core_color[1] * (1 - blend) + arm_color[1] * blend)
                b = int(core_color[2] * (1 - blend) + arm_color[2] * blend)
                r = int(r * total)
                g = int(g * total)
                b = int(b * total)
                pixels[x, y] = (r, g, b)

    # Draw twinkling stars
    for sx, sy, base_brightness in stars:
        # Twinkle effect using sine wave with phase offset
        twinkle = 0.5 + 0.5 * math.sin(twinkle_phase + base_brightness * 10)
        brightness = base_brightness * twinkle

        # Don't draw stars over bright galaxy core
        current = pixels[sx, sy]
        if sum(current) < 100:
            intensity = int(255 * brightness)
            r = min(255, int(star_color[0] * brightness))
            g = min(255, int(star_color[1] * brightness))
            b = min(255, int(star_color[2] * brightness))
            pixels[sx, sy] = (r, g, b)

    return image


async def animate_galaxy(
    config,
    speed: float = 0.5,
    interval: float = 0.05,
    star_count: int = 30,
) -> None:
    """Run the galaxy animation loop."""
    async with PanelManager(config) as manager:
        width, height = manager.canvas_size
        print(f"Galaxy animation on {width}x{height} canvas")
        print("Press Ctrl+C to stop")

        stars = create_star_field(width, height, star_count)
        loop = asyncio.get_running_loop()
        start_time = loop.time()

        try:
            while True:
                elapsed = loop.time() - start_time
                angle = elapsed * speed
                twinkle_phase = elapsed * 3

                frame = render_galaxy_frame(
                    width, height, angle, stars, twinkle_phase
                )
                await manager.send_image(frame, delay=0.1)
                await asyncio.sleep(interval)

        except asyncio.CancelledError:
            raise


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Galaxy animation for BK-Light LED panels")
    parser.add_argument("--config", type=Path, help="Path to config file")
    parser.add_argument("--address", help="Override device address")
    parser.add_argument("--speed", type=float, default=0.5, help="Rotation speed (default: 0.5)")
    parser.add_argument("--interval", type=float, default=0.05, help="Frame interval in seconds (default: 0.05)")
    parser.add_argument("--stars", type=int, default=30, help="Number of background stars (default: 30)")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    config = load_config(args.config)
    if args.address:
        config = replace(config, device=replace(config.device, address=args.address))

    try:
        asyncio.run(animate_galaxy(config, args.speed, args.interval, args.stars))
    except KeyboardInterrupt:
        print("\nStopped.")
