"""Particle sea animation with Perlin noise - Matrix/Cyber style."""

import argparse
import asyncio
import math
import os
import sys
from dataclasses import replace
from pathlib import Path

from PIL import Image

project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from bk_light.config import load_config
from bk_light.panel_manager import PanelManager


# Perlin noise implementation (no external dependency needed)
class PerlinNoise:
    """Simple 2D Perlin noise generator."""

    def __init__(self, seed: int = 0):
        import random
        rng = random.Random(seed)
        self.perm = list(range(256))
        rng.shuffle(self.perm)
        self.perm += self.perm  # Duplicate for overflow

        # Gradient vectors
        self.gradients = [
            (1, 1), (-1, 1), (1, -1), (-1, -1),
            (1, 0), (-1, 0), (0, 1), (0, -1),
        ]

    def _fade(self, t: float) -> float:
        """Smoothstep fade function."""
        return t * t * t * (t * (t * 6 - 15) + 10)

    def _lerp(self, a: float, b: float, t: float) -> float:
        """Linear interpolation."""
        return a + t * (b - a)

    def _grad(self, hash_val: int, x: float, y: float) -> float:
        """Compute gradient dot product."""
        g = self.gradients[hash_val % 8]
        return g[0] * x + g[1] * y

    def noise(self, x: float, y: float) -> float:
        """Generate noise value at (x, y). Returns value in [-1, 1]."""
        # Grid cell coordinates
        xi = int(math.floor(x)) & 255
        yi = int(math.floor(y)) & 255

        # Relative position in cell
        xf = x - math.floor(x)
        yf = y - math.floor(y)

        # Fade curves
        u = self._fade(xf)
        v = self._fade(yf)

        # Hash corners
        aa = self.perm[self.perm[xi] + yi]
        ab = self.perm[self.perm[xi] + yi + 1]
        ba = self.perm[self.perm[xi + 1] + yi]
        bb = self.perm[self.perm[xi + 1] + yi + 1]

        # Blend
        x1 = self._lerp(self._grad(aa, xf, yf), self._grad(ba, xf - 1, yf), u)
        x2 = self._lerp(self._grad(ab, xf, yf - 1), self._grad(bb, xf - 1, yf - 1), u)

        return self._lerp(x1, x2, v)

    def octave_noise(self, x: float, y: float, octaves: int = 4, persistence: float = 0.5) -> float:
        """Multi-octave noise for more natural looking results."""
        total = 0.0
        frequency = 1.0
        amplitude = 1.0
        max_value = 0.0

        for _ in range(octaves):
            total += self.noise(x * frequency, y * frequency) * amplitude
            max_value += amplitude
            amplitude *= persistence
            frequency *= 2.0

        return total / max_value


def create_cyber_gradient(height: float) -> tuple[int, int, int]:
    """Map height value to matrix/cyber colors (filled mode).

    height: normalized value from 0.0 (low) to 1.0 (high)
    Returns: (r, g, b) tuple
    """
    # Apply contrast curve - push values toward extremes
    height = height ** 0.7
    height = (height - 0.5) * 1.8 + 0.5
    height = max(0, min(1, height))

    if height < 0.2:
        t = height / 0.2
        r, g, b = 0, int(15 * t), int(5 + 25 * t)
    elif height < 0.4:
        t = (height - 0.2) / 0.2
        r, g, b = 0, int(15 + 45 * t), int(30 + 40 * t)
    elif height < 0.6:
        t = (height - 0.4) / 0.2
        r, g, b = int(10 * t), int(60 + 120 * t), int(70 + 10 * t)
    elif height < 0.8:
        t = (height - 0.6) / 0.2
        r, g, b = int(10 + 90 * t), int(180 + 75 * t), int(80 + 120 * t)
    else:
        t = (height - 0.8) / 0.2
        r, g, b = int(100 + 120 * t), 255, int(200 + 55 * t)

    return (r, g, b)


def is_contour(height: float, contour_levels: int = 8, thickness: float = 0.025) -> tuple[bool, float]:
    """Check if height value is on a contour line.

    Returns: (is_on_contour, contour_level_normalized)
    """
    # Create evenly spaced contour levels (thinner lines for topo map look)
    for i in range(contour_levels + 1):
        level = i / contour_levels
        if abs(height - level) < thickness:
            return True, level
    return False, 0.0


def create_contour_color(level: float, brightness_boost: float = 0.0) -> tuple[int, int, int]:
    """Create green contour color based on height level.

    level: 0.0 (low) to 1.0 (high)
    Returns: (r, g, b) - shades of green
    """
    # Lower contours: darker green
    # Higher contours: brighter green/cyan

    base_brightness = 0.3 + level * 0.7  # 0.3 to 1.0
    base_brightness = min(1.0, base_brightness + brightness_boost)

    if level < 0.5:
        # Lower half: pure green shades
        r = int(0)
        g = int(80 + 175 * base_brightness)
        b = int(20 * base_brightness)
    else:
        # Upper half: green to cyan
        t = (level - 0.5) * 2  # 0 to 1
        r = int(40 * t * base_brightness)
        g = int(255 * base_brightness)
        b = int((20 + 180 * t) * base_brightness)

    return (r, g, b)


def render_particle_sea_frame(
    width: int,
    height: int,
    noise: PerlinNoise,
    time: float,
    scale: float = 0.1,
    speed: float = 1.0,
    octaves: int = 4,
    contour_mode: bool = True,
    contour_levels: int = 10,
) -> Image.Image:
    """Render a single frame of the topographic terrain."""
    image = Image.new("RGB", (width, height), (0, 0, 0))
    pixels = image.load()

    # Terrain flows diagonally like looking at a moving landscape
    t_offset = time * speed

    # Store height values for contour detection
    heights = [[0.0] * width for _ in range(height)]

    # First pass: calculate terrain heights using layered noise
    for y in range(height):
        for x in range(width):
            # Primary terrain - flows diagonally
            nx = x * scale + t_offset * 0.15
            ny = y * scale + t_offset * 0.1

            # Multi-octave noise for natural terrain look
            terrain = noise.octave_noise(nx, ny, octaves=octaves, persistence=0.5)

            # Add subtle large-scale undulation
            large_wave = noise.noise(x * scale * 0.3 + t_offset * 0.05,
                                     y * scale * 0.3 + t_offset * 0.03) * 0.3

            # Combine and normalize to [0, 1]
            height_val = (terrain + large_wave + 1.2) / 2.4
            height_val = max(0, min(1, height_val))

            heights[y][x] = height_val

    # Second pass: render contour lines
    for y in range(height):
        for x in range(width):
            height_val = heights[y][x]

            if contour_mode:
                # Thin contour lines for topographic map look
                on_contour, level = is_contour(height_val, contour_levels, thickness=0.03)

                if on_contour:
                    color = create_contour_color(level)
                    pixels[x, y] = color

            else:
                # Filled gradient mode
                color = create_cyber_gradient(height_val)
                pixels[x, y] = color

    return image


# Dot characters for LED simulation
DOT_BRIGHT = "●"  # Full dot for bright pixels
DOT_DIM = "•"     # Small dot for dim pixels
DOT_OFF = " "     # Space for off pixels


def render_ascii_frame(image: Image.Image, use_color: bool = True) -> str:
    """Convert image to dot-matrix ASCII art.

    Args:
        image: PIL Image to convert
        use_color: If True, use ANSI color codes

    Returns:
        Dot-matrix string ready to print
    """
    width, height = image.size
    pixels = image.load()

    lines = []
    RESET = "\033[0m"

    for y in range(height):
        line = ""
        for x in range(width):
            r, g, b = pixels[x, y]
            brightness = (0.299 * r + 0.587 * g + 0.114 * b) / 255.0

            # Choose dot based on brightness
            if brightness < 0.08:
                dot = DOT_OFF
            elif brightness < 0.4:
                dot = DOT_DIM
            else:
                dot = DOT_BRIGHT

            if use_color and brightness >= 0.08:
                # Map RGB to 256-color terminal palette
                r_term = int(r / 255 * 5)
                g_term = int(g / 255 * 5)
                b_term = int(b / 255 * 5)
                color_code = 16 + 36 * r_term + 6 * g_term + b_term
                line += f"\033[38;5;{color_code}m{dot} "
            else:
                line += f"{dot} "  # Dot + space between pixels

        lines.append(line + RESET if use_color else line)

    return "\n".join(lines)


def clear_screen():
    """Clear terminal screen and move cursor to top."""
    # Move cursor to top-left corner (works better than full clear for animation)
    print("\033[H", end="")


def hide_cursor():
    """Hide terminal cursor."""
    print("\033[?25l", end="")


def show_cursor():
    """Show terminal cursor."""
    print("\033[?25h", end="")


async def animate_particle_sea(
    config,
    scale: float = 0.12,
    speed: float = 0.5,
    interval: float = 0.06,
    seed: int = 42,
    contour_mode: bool = True,
    contour_levels: int = 10,
    ascii_preview: bool = True,
    no_device: bool = False,
    use_color: bool = True,
) -> None:
    """Run the particle sea animation loop."""
    # Determine canvas size
    if no_device:
        width, height = 32, 32  # Default size when no device
        manager = None
    else:
        manager = PanelManager(config)
        await manager.__aenter__()
        width, height = manager.canvas_size

    mode_str = "Contour" if contour_mode else "Filled"

    if ascii_preview:
        # Clear screen and hide cursor for clean animation
        os.system('cls' if os.name == 'nt' else 'clear')
        hide_cursor()
        print(f"Particle Sea ({mode_str}) - {width}x{height} - Ctrl+C to stop\n")
    else:
        print(f"Particle Sea ({mode_str} mode) on {width}x{height} canvas")
        if contour_mode:
            print(f"Contour levels: {contour_levels}")
        print("Press Ctrl+C to stop")

    noise = PerlinNoise(seed)
    loop = asyncio.get_running_loop()
    start_time = loop.time()

    try:
        while True:
            elapsed = loop.time() - start_time

            frame = render_particle_sea_frame(
                width, height, noise, elapsed, scale, speed,
                contour_mode=contour_mode, contour_levels=contour_levels
            )

            # Send to device if connected
            if manager:
                await manager.send_image(frame, delay=0.1)

            # Show ASCII preview
            if ascii_preview:
                clear_screen()
                print(f"Particle Sea ({mode_str}) - {width}x{height} - Ctrl+C to stop\n")
                print(render_ascii_frame(frame, use_color=use_color))

            await asyncio.sleep(interval)

    except asyncio.CancelledError:
        raise
    finally:
        if ascii_preview:
            show_cursor()
        if manager:
            await manager.__aexit__(None, None, None)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Particle sea animation with Perlin noise - Matrix/Cyber style"
    )
    parser.add_argument("--config", type=Path, help="Path to config file")
    parser.add_argument("--address", help="Override device address")
    parser.add_argument(
        "--scale", type=float, default=0.12,
        help="Terrain scale - lower = larger features (default: 0.12)"
    )
    parser.add_argument(
        "--speed", type=float, default=0.5,
        help="Flow speed (default: 0.5)"
    )
    parser.add_argument(
        "--interval", type=float, default=0.06,
        help="Frame interval in seconds (default: 0.06)"
    )
    parser.add_argument(
        "--seed", type=int, default=42,
        help="Random seed for terrain generation (default: 42)"
    )
    parser.add_argument(
        "--filled", action="store_true",
        help="Use filled gradient mode instead of contour lines"
    )
    parser.add_argument(
        "--levels", type=int, default=10,
        help="Number of contour levels (default: 10)"
    )
    parser.add_argument(
        "--no-ascii", action="store_true",
        help="Disable ASCII preview in terminal"
    )
    parser.add_argument(
        "--no-device", action="store_true",
        help="Run without connecting to LED device (preview only)"
    )
    parser.add_argument(
        "--no-color", action="store_true",
        help="Disable colors in ASCII preview"
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    config = None
    if not args.no_device:
        config = load_config(args.config)
        if args.address:
            config = replace(config, device=replace(config.device, address=args.address))

    try:
        asyncio.run(animate_particle_sea(
            config,
            scale=args.scale,
            speed=args.speed,
            interval=args.interval,
            seed=args.seed,
            contour_mode=not args.filled,
            contour_levels=args.levels,
            ascii_preview=not args.no_ascii,
            no_device=args.no_device,
            use_color=not args.no_color,
        ))
    except KeyboardInterrupt:
        show_cursor()  # Ensure cursor is restored
        print("\nStopped.")
