"""3D Rotating Text Animation - Creates depth effect like 3d_sphere.gif.

Text rotates in 3D space with depth-based coloring:
- Blue for far/back points
- Red for near/front points
"""

import asyncio
import math
import sys
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from bk_light.config import load_config
from bk_light.panel_manager import PanelManager


@dataclass
class Point3D:
    x: float
    y: float
    z: float


def text_to_3d_points(text: str, radius: float = 10.0, font_size: int = 20) -> list[Point3D]:
    """Convert text to 3D points arranged on a cylinder surface."""
    # Render text to get pixel positions
    font_path = project_root / "assets" / "fonts" / "PixelOperator.ttf"
    try:
        font = ImageFont.truetype(str(font_path), font_size)
    except:
        font = ImageFont.load_default()

    # Get text dimensions
    temp_img = Image.new("L", (200, 50))
    temp_draw = ImageDraw.Draw(temp_img)
    bbox = temp_draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]

    # Render text
    img = Image.new("L", (text_width + 4, text_height + 4), 0)
    draw = ImageDraw.Draw(img)
    draw.text((2, 2), text, fill=255, font=font)

    # Extract points from rendered text
    points = []
    pixels = img.load()
    width, height = img.size

    for y in range(height):
        for x in range(width):
            if pixels[x, y] > 128:
                # Map x to angle around cylinder (full 360°)
                angle = (x / width) * 2 * math.pi
                # Map y to height
                cy = (y / height - 0.5) * radius * 0.8

                # Place point on cylinder surface
                cx = radius * math.cos(angle)
                cz = radius * math.sin(angle)

                points.append(Point3D(cx, cy, cz))

    return points


def create_sphere_points(radius: float = 12.0, density: int = 200) -> list[Point3D]:
    """Create points on a sphere surface (like the original effect)."""
    points = []
    phi = math.pi * (3.0 - math.sqrt(5.0))  # Golden angle

    for i in range(density):
        y = 1 - (i / float(density - 1)) * 2
        r = math.sqrt(1 - y * y)
        theta = phi * i

        x = math.cos(theta) * r * radius
        z = math.sin(theta) * r * radius
        y = y * radius

        points.append(Point3D(x, y, z))

    return points


def text_to_sphere_points(text: str, radius: float = 12.0, font_size: int = 16) -> list[Point3D]:
    """Map text pixels onto a sphere surface."""
    font_path = project_root / "assets" / "fonts" / "PixelOperator.ttf"
    try:
        font = ImageFont.truetype(str(font_path), font_size)
    except:
        font = ImageFont.load_default()

    # Get text dimensions
    temp_img = Image.new("L", (200, 50))
    temp_draw = ImageDraw.Draw(temp_img)
    bbox = temp_draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]

    # Render text
    img = Image.new("L", (text_width + 4, text_height + 4), 0)
    draw = ImageDraw.Draw(img)
    draw.text((2, 2), text, fill=255, font=font)

    points = []
    pixels = img.load()
    width, height = img.size

    for y in range(height):
        for x in range(width):
            if pixels[x, y] > 128:
                # Map to spherical coordinates
                # theta: longitude (0 to 2*pi around)
                # phi: latitude (-pi/2 to pi/2)
                theta = (x / width) * 2 * math.pi
                phi = (y / height - 0.5) * math.pi * 0.8  # Limit to avoid poles

                # Convert to cartesian
                px = radius * math.cos(phi) * math.cos(theta)
                py = radius * math.sin(phi)
                pz = radius * math.cos(phi) * math.sin(theta)

                points.append(Point3D(px, py, pz))

    return points


def rotate_y(points: list[Point3D], angle: float) -> list[Point3D]:
    """Rotate points around Y axis."""
    cos_a = math.cos(angle)
    sin_a = math.sin(angle)
    rotated = []
    for p in points:
        rx = p.x * cos_a - p.z * sin_a
        rz = p.x * sin_a + p.z * cos_a
        rotated.append(Point3D(rx, p.y, rz))
    return rotated


def rotate_x(points: list[Point3D], angle: float) -> list[Point3D]:
    """Rotate points around X axis."""
    cos_a = math.cos(angle)
    sin_a = math.sin(angle)
    rotated = []
    for p in points:
        ry = p.y * cos_a - p.z * sin_a
        rz = p.y * sin_a + p.z * cos_a
        rotated.append(Point3D(p.x, ry, rz))
    return rotated


def depth_to_color(z: float, z_min: float, z_max: float) -> tuple[int, int, int]:
    """Convert Z depth to color using full rainbow gradient.

    Smooth transition: blue (far) → cyan → green → yellow → orange → red (near)
    Uses HSV color space for perceptually smooth gradient.
    """
    if z_max == z_min:
        t = 0.5
    else:
        t = (z - z_min) / (z_max - z_min)  # 0 = far, 1 = near

    # Map t to hue: 240° (blue) down to 0° (red)
    # HSV with full saturation and value for vibrant colors
    hue = (1.0 - t) * 240.0  # 240=blue, 180=cyan, 120=green, 60=yellow, 0=red

    # Convert HSV to RGB (S=1, V=1)
    h = hue / 60.0
    i = int(h)
    f = h - i

    # Since S=1 and V=1: p=0, q=1-f, t=f
    if i == 0:
        r, g, b = 255, int(255 * f), 0
    elif i == 1:
        r, g, b = int(255 * (1 - f)), 255, 0
    elif i == 2:
        r, g, b = 0, 255, int(255 * f)
    elif i == 3:
        r, g, b = 0, int(255 * (1 - f)), 255
    elif i == 4:
        r, g, b = int(255 * f), 0, 255
    else:
        r, g, b = 255, 0, int(255 * (1 - f))

    return (r, g, b)


def depth_to_size(z: float, z_min: float, z_max: float, min_size: int = 1, max_size: int = 3) -> int:
    """Convert Z depth to dot size: far = small, near = large."""
    if z_max == z_min:
        return (min_size + max_size) // 2
    t = (z - z_min) / (z_max - z_min)
    return int(min_size + t * (max_size - min_size))


def render_frame(
    points: list[Point3D],
    size: tuple[int, int],
    scale: float = 1.0,
    min_dot_size: int = 1,
    max_dot_size: int = 3
) -> Image.Image:
    """Render 3D points to 2D image with depth coloring and size variation.

    Points closer to camera (higher Z) are rendered:
    - With warmer colors (red)
    - Larger dot size
    Points further from camera (lower Z) are rendered:
    - With cooler colors (blue)
    - Smaller dot size
    """
    img = Image.new("RGB", size, (0, 0, 0))
    draw = ImageDraw.Draw(img)

    if not points:
        return img

    # Find Z range for color/size mapping
    z_values = [p.z for p in points]
    z_min, z_max = min(z_values), max(z_values)

    # Sort by Z (back to front) for proper overlap - far points drawn first
    sorted_points = sorted(points, key=lambda p: p.z)

    cx, cy = size[0] // 2, size[1] // 2

    for p in sorted_points:
        # Simple orthographic projection
        screen_x = int(cx + p.x * scale)
        screen_y = int(cy - p.y * scale)  # Flip Y

        color = depth_to_color(p.z, z_min, z_max)
        dot_size = depth_to_size(p.z, z_min, z_max, min_dot_size, max_dot_size)

        # Draw dot as circle with depth-based size
        if dot_size <= 1:
            # Single pixel for smallest dots
            if 0 <= screen_x < size[0] and 0 <= screen_y < size[1]:
                draw.point((screen_x, screen_y), fill=color)
        else:
            # Draw ellipse for larger dots
            half = dot_size // 2
            x0, y0 = screen_x - half, screen_y - half
            x1, y1 = screen_x + half, screen_y + half
            # Check bounds with margin
            if -dot_size < screen_x < size[0] + dot_size and -dot_size < screen_y < size[1] + dot_size:
                draw.ellipse([x0, y0, x1, y1], fill=color)

    return img


def generate_frames(
    text: str,
    size: tuple[int, int],
    num_frames: int = 48,
    mode: str = "cylinder"
) -> list[Image.Image]:
    """Generate all animation frames."""
    # Adjust parameters based on text length for readability
    text_len = len(text)

    # Scale radius based on text length - longer text needs larger radius
    base_radius = min(size) * 0.4
    if text_len <= 3:
        radius = base_radius
        font_size = max(16, min(size) // 2)
    elif text_len <= 6:
        radius = base_radius * 1.2
        font_size = max(14, min(size) // 2 - 2)
    else:
        # Long text: larger radius, smaller font, sample points
        radius = base_radius * 1.5
        font_size = max(12, min(size) // 3)

    if mode == "sphere":
        points = text_to_sphere_points(text, radius=radius, font_size=font_size)
    else:  # cylinder
        points = text_to_3d_points(text, radius=radius, font_size=font_size)

    if not points:
        print(f"Warning: No points generated from text '{text}'")
        points = create_sphere_points(radius=radius, density=150)

    # For long text, sample points to avoid overcrowding
    if text_len > 6 and len(points) > 150:
        step = max(1, len(points) // 150)
        points = points[::step]

    print(f"Generated {len(points)} 3D points for '{text}'")

    # Add slight X tilt for better 3D effect
    points = rotate_x(points, math.radians(15))

    frames = []
    scale = min(size) / (radius * 2.5)

    # Larger dots for small displays, smaller for large displays
    min_dot = max(1, min(size) // 16)  # 2 for 32x32
    max_dot = max(2, min(size) // 8)   # 4 for 32x32

    for i in range(num_frames):
        angle = (i / num_frames) * 2 * math.pi
        rotated = rotate_y(points, angle)
        frame = render_frame(rotated, size, scale, min_dot, max_dot)
        frames.append(frame)

    return frames


async def play_animation(
    config,
    text: str,
    speed: float = 1.0,
    mode: str = "cylinder",
    num_frames: int = 48,
    save_gif: str = None,
    cycle_modes: bool = False,
    cycle_interval: float = 30.0,
) -> None:
    """Play the 3D text animation."""
    async with PanelManager(config) as manager:
        size = manager.canvas_size
        print(f"Canvas: {size[0]}x{size[1]}")
        print(f"Text: '{text}'")

        if cycle_modes:
            await play_with_cycling(manager, text, size, num_frames, speed, cycle_interval)
        else:
            await play_single_mode(manager, text, size, num_frames, mode, speed, save_gif)


async def play_single_mode(manager, text, size, num_frames, mode, speed, save_gif):
    """Play animation in a single mode."""
    print(f"Mode: {mode}")
    print("Generating frames...")
    frames = generate_frames(text, size, num_frames, mode)
    print(f"Generated {len(frames)} frames")

    # Save as GIF if requested
    if save_gif:
        print(f"Saving to {save_gif}...")
        frames[0].save(
            save_gif,
            save_all=True,
            append_images=frames[1:],
            duration=int(50 / speed),
            loop=0
        )
        print("Saved!")

    # Prebuffer
    print("Pre-buffering...")
    prebuffered = manager.prebuffer_images(frames)
    print(f"Pre-buffered {len(prebuffered)} frames")

    print("Playing... Press Ctrl+C to stop")

    frame_delay = max(0, (1.0 - speed) * 0.05) if speed < 1.0 else 0

    try:
        while True:
            for frame_data in prebuffered:
                await manager.send_prebuffered_streaming(frame_data)
                if frame_delay > 0:
                    await asyncio.sleep(frame_delay)
    except asyncio.CancelledError:
        raise


async def play_with_cycling(manager, text, size, num_frames, speed, cycle_interval):
    """Play animation cycling through different 3D modes every cycle_interval seconds."""
    import time

    modes = ["sphere", "cylinder", "sphere_tilt", "cylinder_reverse"]
    mode_index = 0

    print(f"Cycling modes every {cycle_interval}s: {modes}")
    frame_delay = max(0, (1.0 - speed) * 0.05) if speed < 1.0 else 0

    try:
        while True:
            current_mode = modes[mode_index % len(modes)]
            print(f"\n>> Switching to: {current_mode}")

            # Generate frames for current mode
            if current_mode == "sphere_tilt":
                frames = generate_frames_with_tilt(text, size, num_frames, "sphere", tilt_x=30, tilt_y=15)
            elif current_mode == "cylinder_reverse":
                frames = generate_frames(text, size, num_frames, "cylinder")
                frames = frames[::-1]  # Reverse rotation direction
            else:
                frames = generate_frames(text, size, num_frames, current_mode)

            prebuffered = manager.prebuffer_images(frames)
            print(f"Playing {current_mode} ({len(prebuffered)} frames)")

            # Play for cycle_interval seconds
            start_time = time.time()
            while time.time() - start_time < cycle_interval:
                for frame_data in prebuffered:
                    await manager.send_prebuffered_streaming(frame_data)
                    if frame_delay > 0:
                        await asyncio.sleep(frame_delay)
                    if time.time() - start_time >= cycle_interval:
                        break

            mode_index += 1

    except asyncio.CancelledError:
        raise


def generate_frames_with_tilt(
    text: str,
    size: tuple[int, int],
    num_frames: int = 48,
    mode: str = "sphere",
    tilt_x: float = 30,
    tilt_y: float = 15
) -> list[Image.Image]:
    """Generate frames with custom tilt angles."""
    # Adjust parameters based on text length
    text_len = len(text)
    base_radius = min(size) * 0.4

    if text_len <= 3:
        radius = base_radius
        font_size = max(16, min(size) // 2)
    elif text_len <= 6:
        radius = base_radius * 1.2
        font_size = max(14, min(size) // 2 - 2)
    else:
        radius = base_radius * 1.5
        font_size = max(12, min(size) // 3)

    if mode == "sphere":
        points = text_to_sphere_points(text, radius=radius, font_size=font_size)
    else:
        points = text_to_3d_points(text, radius=radius, font_size=font_size)

    if not points:
        points = create_sphere_points(radius=radius, density=150)

    # Sample points for long text
    if text_len > 6 and len(points) > 150:
        step = max(1, len(points) // 150)
        points = points[::step]

    # Apply custom tilt
    points = rotate_x(points, math.radians(tilt_x))
    points = rotate_y(points, math.radians(tilt_y))

    frames = []
    scale = min(size) / (radius * 2.5)
    min_dot = max(1, min(size) // 16)
    max_dot = max(2, min(size) // 8)

    for i in range(num_frames):
        angle = (i / num_frames) * 2 * math.pi
        rotated = rotate_y(points, angle)
        frame = render_frame(rotated, size, scale, min_dot, max_dot)
        frames.append(frame)

    return frames


if __name__ == "__main__":
    # Simple usage: python text_3d_rotation.py "YOUR TEXT"
    text = sys.argv[1] if len(sys.argv) > 1 else "HELLO"

    config = load_config()

    try:
        asyncio.run(play_animation(
            config,
            text,
            speed=1.0,
            mode="sphere",
            num_frames=24,
            cycle_modes=True,
            cycle_interval=30.0,
        ))
    except KeyboardInterrupt:
        print("\nStopped.")
