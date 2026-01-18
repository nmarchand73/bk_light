"""Radar clock animation for LED matrix.

Classic radar effect with rotating sweep, fading trail, and time display.
"""

import argparse
import asyncio
import math
import os
import sys
from dataclasses import replace
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
import urllib.request
import xml.etree.ElementTree as ET
import threading
import time as time_module

project_root = Path(__file__).resolve().parents[1]


# =============================================================================
# PIXEL FONT - 5x7 bitmap digits optimized for 32x32 LED displays
# =============================================================================

# Each digit is 5 pixels wide x 7 pixels tall
# 1 = pixel on, 0 = pixel off
PIXEL_FONT = {
    '0': [
        [0, 1, 1, 1, 0],
        [1, 0, 0, 0, 1],
        [1, 0, 0, 1, 1],
        [1, 0, 1, 0, 1],
        [1, 1, 0, 0, 1],
        [1, 0, 0, 0, 1],
        [0, 1, 1, 1, 0],
    ],
    '1': [
        [0, 0, 1, 0, 0],
        [0, 1, 1, 0, 0],
        [0, 0, 1, 0, 0],
        [0, 0, 1, 0, 0],
        [0, 0, 1, 0, 0],
        [0, 0, 1, 0, 0],
        [0, 1, 1, 1, 0],
    ],
    '2': [
        [0, 1, 1, 1, 0],
        [1, 0, 0, 0, 1],
        [0, 0, 0, 0, 1],
        [0, 0, 1, 1, 0],
        [0, 1, 0, 0, 0],
        [1, 0, 0, 0, 0],
        [1, 1, 1, 1, 1],
    ],
    '3': [
        [0, 1, 1, 1, 0],
        [1, 0, 0, 0, 1],
        [0, 0, 0, 0, 1],
        [0, 0, 1, 1, 0],
        [0, 0, 0, 0, 1],
        [1, 0, 0, 0, 1],
        [0, 1, 1, 1, 0],
    ],
    '4': [
        [0, 0, 0, 1, 0],
        [0, 0, 1, 1, 0],
        [0, 1, 0, 1, 0],
        [1, 0, 0, 1, 0],
        [1, 1, 1, 1, 1],
        [0, 0, 0, 1, 0],
        [0, 0, 0, 1, 0],
    ],
    '5': [
        [1, 1, 1, 1, 1],
        [1, 0, 0, 0, 0],
        [1, 1, 1, 1, 0],
        [0, 0, 0, 0, 1],
        [0, 0, 0, 0, 1],
        [1, 0, 0, 0, 1],
        [0, 1, 1, 1, 0],
    ],
    '6': [
        [0, 0, 1, 1, 0],
        [0, 1, 0, 0, 0],
        [1, 0, 0, 0, 0],
        [1, 1, 1, 1, 0],
        [1, 0, 0, 0, 1],
        [1, 0, 0, 0, 1],
        [0, 1, 1, 1, 0],
    ],
    '7': [
        [1, 1, 1, 1, 1],
        [0, 0, 0, 0, 1],
        [0, 0, 0, 1, 0],
        [0, 0, 1, 0, 0],
        [0, 1, 0, 0, 0],
        [0, 1, 0, 0, 0],
        [0, 1, 0, 0, 0],
    ],
    '8': [
        [0, 1, 1, 1, 0],
        [1, 0, 0, 0, 1],
        [1, 0, 0, 0, 1],
        [0, 1, 1, 1, 0],
        [1, 0, 0, 0, 1],
        [1, 0, 0, 0, 1],
        [0, 1, 1, 1, 0],
    ],
    '9': [
        [0, 1, 1, 1, 0],
        [1, 0, 0, 0, 1],
        [1, 0, 0, 0, 1],
        [0, 1, 1, 1, 1],
        [0, 0, 0, 0, 1],
        [0, 0, 0, 1, 0],
        [0, 1, 1, 0, 0],
    ],
    ':': [
        [0],
        [1],
        [0],
        [0],
        [0],
        [1],
        [0],
    ],
    ' ': [
        [0],
        [0],
        [0],
        [0],
        [0],
        [0],
        [0],
    ],
}

CHAR_WIDTH = 5
CHAR_HEIGHT = 7
CHAR_SPACING = 1
COLON_WIDTH = 1


# =============================================================================
# MINI PIXEL FONT - 3x5 bitmap for scrolling banner
# =============================================================================

MINI_FONT = {
    '0': [[1,1,1],[1,0,1],[1,0,1],[1,0,1],[1,1,1]],
    '1': [[0,1,0],[1,1,0],[0,1,0],[0,1,0],[1,1,1]],
    '2': [[1,1,1],[0,0,1],[1,1,1],[1,0,0],[1,1,1]],
    '3': [[1,1,1],[0,0,1],[1,1,1],[0,0,1],[1,1,1]],
    '4': [[1,0,1],[1,0,1],[1,1,1],[0,0,1],[0,0,1]],
    '5': [[1,1,1],[1,0,0],[1,1,1],[0,0,1],[1,1,1]],
    '6': [[1,1,1],[1,0,0],[1,1,1],[1,0,1],[1,1,1]],
    '7': [[1,1,1],[0,0,1],[0,0,1],[0,1,0],[0,1,0]],
    '8': [[1,1,1],[1,0,1],[1,1,1],[1,0,1],[1,1,1]],
    '9': [[1,1,1],[1,0,1],[1,1,1],[0,0,1],[1,1,1]],
    'A': [[0,1,0],[1,0,1],[1,1,1],[1,0,1],[1,0,1]],
    'B': [[1,1,0],[1,0,1],[1,1,0],[1,0,1],[1,1,0]],
    'C': [[0,1,1],[1,0,0],[1,0,0],[1,0,0],[0,1,1]],
    'D': [[1,1,0],[1,0,1],[1,0,1],[1,0,1],[1,1,0]],
    'E': [[1,1,1],[1,0,0],[1,1,0],[1,0,0],[1,1,1]],
    'F': [[1,1,1],[1,0,0],[1,1,0],[1,0,0],[1,0,0]],
    'G': [[0,1,1],[1,0,0],[1,0,1],[1,0,1],[0,1,1]],
    'H': [[1,0,1],[1,0,1],[1,1,1],[1,0,1],[1,0,1]],
    'I': [[1,1,1],[0,1,0],[0,1,0],[0,1,0],[1,1,1]],
    'J': [[0,0,1],[0,0,1],[0,0,1],[1,0,1],[0,1,0]],
    'K': [[1,0,1],[1,0,1],[1,1,0],[1,0,1],[1,0,1]],
    'L': [[1,0,0],[1,0,0],[1,0,0],[1,0,0],[1,1,1]],
    'M': [[1,0,1],[1,1,1],[1,0,1],[1,0,1],[1,0,1]],
    'N': [[1,0,1],[1,1,1],[1,1,1],[1,0,1],[1,0,1]],
    'O': [[0,1,0],[1,0,1],[1,0,1],[1,0,1],[0,1,0]],
    'P': [[1,1,0],[1,0,1],[1,1,0],[1,0,0],[1,0,0]],
    'Q': [[0,1,0],[1,0,1],[1,0,1],[1,1,1],[0,1,1]],
    'R': [[1,1,0],[1,0,1],[1,1,0],[1,0,1],[1,0,1]],
    'S': [[0,1,1],[1,0,0],[0,1,0],[0,0,1],[1,1,0]],
    'T': [[1,1,1],[0,1,0],[0,1,0],[0,1,0],[0,1,0]],
    'U': [[1,0,1],[1,0,1],[1,0,1],[1,0,1],[0,1,0]],
    'V': [[1,0,1],[1,0,1],[1,0,1],[0,1,0],[0,1,0]],
    'W': [[1,0,1],[1,0,1],[1,0,1],[1,1,1],[1,0,1]],
    'X': [[1,0,1],[1,0,1],[0,1,0],[1,0,1],[1,0,1]],
    'Y': [[1,0,1],[1,0,1],[0,1,0],[0,1,0],[0,1,0]],
    'Z': [[1,1,1],[0,0,1],[0,1,0],[1,0,0],[1,1,1]],
    '%': [[1,0,1],[0,0,1],[0,1,0],[1,0,0],[1,0,1]],
    ':': [[0],[1],[0],[1],[0]],
    '.': [[0],[0],[0],[0],[1]],
    ',': [[0],[0],[0],[1],[1]],
    '!': [[1],[1],[1],[0],[1]],
    '?': [[1,1,0],[0,0,1],[0,1,0],[0,0,0],[0,1,0]],
    '-': [[0,0,0],[0,0,0],[1,1,1],[0,0,0],[0,0,0]],
    '/': [[0,0,1],[0,0,1],[0,1,0],[1,0,0],[1,0,0]],
    "'": [[1],[1],[0],[0],[0]],
    '"': [[1,0,1],[1,0,1],[0,0,0],[0,0,0],[0,0,0]],
    ' ': [[0,0],[0,0],[0,0],[0,0],[0,0]],
}

MINI_CHAR_HEIGHT = 5
MINI_CHAR_SPACING = 1


def draw_mini_text(image: Image.Image, text: str, x: int, y: int, color: tuple = None, fade_edges: bool = False, rainbow: bool = False) -> None:
    """Draw text using the mini 3x5 pixel font.

    Args:
        fade_edges: Apply fade in/out effect at screen edges
        rainbow: Use rainbow colors, cycling on each "//" separator
    """
    pixels = image.load()
    cursor_x = x
    width = image.width
    fade_zone = 4  # Pixels for fade effect

    # Rainbow mode: track color index and separator detection
    color_index = 0
    current_color = RAINBOW_COLORS[0] if rainbow else color
    text_upper = text.upper()
    i = 0

    while i < len(text_upper):
        # Check for separator "//" to change color
        if rainbow and i < len(text_upper) - 1 and text_upper[i:i+2] == "//":
            color_index = (color_index + 1) % len(RAINBOW_COLORS)
            current_color = RAINBOW_COLORS[color_index]

        char = text_upper[i]
        i += 1

        if char not in MINI_FONT:
            cursor_x += 2  # Skip unknown chars
            continue

        glyph = MINI_FONT[char]
        glyph_width = len(glyph[0])

        for row_idx, row in enumerate(glyph):
            for col_idx, pixel in enumerate(row):
                if pixel:
                    px = cursor_x + col_idx
                    py = y + row_idx
                    if 0 <= px < width and 0 <= py < image.height:
                        # Apply fade effect at edges
                        if fade_edges:
                            if px < fade_zone:
                                fade = px / fade_zone
                            elif px > width - fade_zone:
                                fade = (width - px) / fade_zone
                            else:
                                fade = 1.0
                            faded_color = (
                                int(current_color[0] * fade),
                                int(current_color[1] * fade),
                                int(current_color[2] * fade)
                            )
                            pixels[px, py] = faded_color
                        else:
                            pixels[px, py] = current_color

        cursor_x += glyph_width + MINI_CHAR_SPACING


def get_mini_text_width(text: str) -> int:
    """Calculate width of text in mini font."""
    width = 0
    for i, char in enumerate(text.upper()):
        if char not in MINI_FONT:
            width += 2
        else:
            width += len(MINI_FONT[char][0])
        if i < len(text) - 1:
            width += MINI_CHAR_SPACING
    return width


def get_visible_color_index(text: str, scroll_offset: int, screen_width: int) -> int:
    """Determine which rainbow color index is visible on screen."""
    # Count separators in the text
    separator_count = text.count("//")
    if separator_count == 0:
        return 0

    # Calculate how far we've scrolled as a fraction
    text_width = get_mini_text_width(text)
    total_width = text_width + screen_width
    scroll_pos = scroll_offset % total_width

    # Map scroll position to color index based on text structure
    progress = scroll_pos / total_width  # 0.0 to 1.0
    color_index = int(progress * (separator_count + 1)) % len(RAINBOW_COLORS)

    return color_index


def draw_pixel_text(image: Image.Image, text: str, x: int, y: int, color: tuple) -> None:
    """Draw text using the pixel font bitmap.

    Args:
        image: PIL Image to draw on
        text: String to render (digits and colon only)
        x: Starting X position
        y: Starting Y position
        color: RGB tuple for text color
    """
    pixels = image.load()
    cursor_x = x

    for char in text:
        if char not in PIXEL_FONT:
            continue

        glyph = PIXEL_FONT[char]
        glyph_width = len(glyph[0])

        for row_idx, row in enumerate(glyph):
            for col_idx, pixel in enumerate(row):
                if pixel:
                    px = cursor_x + col_idx
                    py = y + row_idx
                    if 0 <= px < image.width and 0 <= py < image.height:
                        pixels[px, py] = color

        cursor_x += glyph_width + CHAR_SPACING


def get_pixel_text_width(text: str) -> int:
    """Calculate the width of text rendered with pixel font."""
    width = 0
    for i, char in enumerate(text):
        if char not in PIXEL_FONT:
            continue
        glyph = PIXEL_FONT[char]
        width += len(glyph[0])
        if i < len(text) - 1:
            width += CHAR_SPACING
    return width


if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from bk_light.config import load_config
from bk_light.panel_manager import PanelManager


# =============================================================================
# CONFIGURATION
# =============================================================================

SCRIPT_NAME = "Radar Clock"
DEFAULT_FPS = 2  # BLE device limit

# 5 seconds per rotation at 2 FPS = 10 frames/tour
# speed = 2π / 10 ≈ 0.628 rad/frame
DEFAULT_SPEED = 2 * math.pi / 10

# Brightness (0.0 - 1.0)
BRIGHTNESS = 0.5

# Colors (will be scaled by BRIGHTNESS)
COLOR_BG = (0, 0, int(20 * BRIGHTNESS))
COLOR_GRID = (0, int(40 * BRIGHTNESS), int(80 * BRIGHTNESS))
COLOR_SWEEP = (0, int(100 * BRIGHTNESS), int(255 * BRIGHTNESS))
COLOR_TIME = (int(255 * BRIGHTNESS), 0, 0)

# Rainbow colors for news (scaled by brightness) - no blue to contrast with radar
RAINBOW_COLORS = [
    (int(255 * BRIGHTNESS), int(255 * BRIGHTNESS), int(255 * BRIGHTNESS)),  # White
    (int(255 * BRIGHTNESS), int(127 * BRIGHTNESS), int(0 * BRIGHTNESS)),    # Orange
    (int(255 * BRIGHTNESS), int(255 * BRIGHTNESS), int(0 * BRIGHTNESS)),    # Yellow
    (int(0 * BRIGHTNESS), int(255 * BRIGHTNESS), int(0 * BRIGHTNESS)),      # Green
    (int(0 * BRIGHTNESS), int(255 * BRIGHTNESS), int(255 * BRIGHTNESS)),    # Cyan
    (int(127 * BRIGHTNESS), int(0 * BRIGHTNESS), int(255 * BRIGHTNESS)),    # Purple
    (int(255 * BRIGHTNESS), int(0 * BRIGHTNESS), int(127 * BRIGHTNESS)),    # Pink
]

# Banner settings
BANNER_HEIGHT = 5               # Mini font height
BANNER_Y = 27                   # Y position (32 - 5 = 27)

# News settings
NEWS_RSS_URL = "https://www.franceinfo.fr/titres.rss"
NEWS_UPDATE_INTERVAL = 300      # Update news every 5 minutes
NEWS_SEPARATOR = "  //  "       # Separator between headlines


# =============================================================================
# NEWS FETCHER
# =============================================================================

class NewsFetcher:
    """Background thread that fetches news headlines from RSS feed."""

    def __init__(self, url: str = NEWS_RSS_URL, update_interval: float = NEWS_UPDATE_INTERVAL):
        self.url = url
        self.update_interval = update_interval
        self.headlines: list[str] = ["CHARGEMENT NEWS..."]
        self.combined_text = "CHARGEMENT NEWS..."
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread = None

    def start(self):
        """Start the background fetching thread."""
        self._thread = threading.Thread(target=self._fetch_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop the background thread."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2)

    def get_text(self) -> str:
        """Get the combined headline text for scrolling."""
        with self._lock:
            return self.combined_text

    def _fetch_loop(self):
        """Main fetch loop running in background."""
        while not self._stop_event.is_set():
            try:
                self._fetch_news()
            except Exception as e:
                with self._lock:
                    self.combined_text = f"ERREUR: {str(e)[:30]}"

            # Wait for next update or stop
            self._stop_event.wait(self.update_interval)

    def _fetch_news(self):
        """Fetch and parse RSS feed."""
        req = urllib.request.Request(
            self.url,
            headers={'User-Agent': 'Mozilla/5.0 (compatible; LEDDisplay/1.0)'}
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            data = response.read()

        root = ET.fromstring(data)
        headlines = []

        # Parse RSS items
        for item in root.findall('.//item'):
            title = item.find('title')
            pub_date = item.find('pubDate')
            if title is not None and title.text:
                # Extract time from pubDate (format: "Sun, 19 Jan 2025 14:30:00 GMT")
                time_prefix = ""
                if pub_date is not None and pub_date.text:
                    try:
                        # Parse RSS date format
                        from email.utils import parsedate_tz
                        parsed = parsedate_tz(pub_date.text)
                        if parsed:
                            hour = parsed[3]
                            minute = parsed[4]
                            time_prefix = f"{hour:02d}:{minute:02d} "
                    except Exception:
                        pass

                # Clean up the title - remove accents for LED display
                text = self._simplify_text(title.text.strip())
                if text:
                    headlines.append(time_prefix + text)

        with self._lock:
            if headlines:
                # Show all news in original order (chronological from RSS)
                self.headlines = headlines
                self.combined_text = NEWS_SEPARATOR.join(self.headlines)
            else:
                self.combined_text = "PAS DE NEWS"

    def _simplify_text(self, text: str) -> str:
        """Simplify text for LED display (remove accents, uppercase)."""
        # Accent replacements
        replacements = {
            'é': 'E', 'è': 'E', 'ê': 'E', 'ë': 'E', 'É': 'E', 'È': 'E', 'Ê': 'E',
            'à': 'A', 'â': 'A', 'ä': 'A', 'À': 'A', 'Â': 'A',
            'ù': 'U', 'û': 'U', 'ü': 'U', 'Ù': 'U', 'Û': 'U',
            'î': 'I', 'ï': 'I', 'Î': 'I', 'Ï': 'I',
            'ô': 'O', 'ö': 'O', 'Ô': 'O', 'Ö': 'O',
            'ç': 'C', 'Ç': 'C',
            'œ': 'OE', 'Œ': 'OE',
            'æ': 'AE', 'Æ': 'AE',
            '«': '"', '»': '"',
            ''': "'", ''': "'",
            '"': '"', '"': '"',
            '–': '-', '—': '-',
            '…': '...',
        }
        for old, new in replacements.items():
            text = text.replace(old, new)

        return text.upper()


# =============================================================================
# ANIMATION
# =============================================================================

def generate_frame(
    width: int,
    height: int,
    t: float,
    num_circles: int = 3,
    trail_length: float = 0.4,
    show_time: bool = True,
    show_news: bool = True,
    news_text: str = "",
    scroll_offset: int = 0,
    **kwargs,
) -> Image.Image:
    """Generate a single radar frame with clock.

    Args:
        width: Frame width in pixels
        height: Frame height in pixels
        t: Time parameter (sweep angle)
        num_circles: Number of concentric grid circles
        trail_length: Length of fade trail (0-1, fraction of circle)
        show_time: Display current time in center
        show_news: Display scrolling news banner at bottom
        news_text: News headline text to scroll
        scroll_offset: Horizontal scroll position for banner

    Returns:
        PIL Image (RGB mode)
    """
    image = Image.new('RGB', (width, height), COLOR_BG)
    pixels = image.load()

    # Radar is always blue
    radar_color = COLOR_SWEEP

    cx = width / 2 - 0.5
    cy = height / 2 - 0.5
    max_radius = min(width, height) / 2 - 1

    # Current sweep angle (start from top, go clockwise)
    sweep_angle = (-t + math.pi / 2) % (2 * math.pi)

    # Draw pixel by pixel
    for y in range(height):
        for x in range(width):
            dx = x - cx
            dy = y - cy
            dist = math.sqrt(dx * dx + dy * dy)

            # Skip if outside radar circle
            if dist > max_radius:
                continue

            # Pixel angle
            pixel_angle = math.atan2(dy, dx)
            if pixel_angle < 0:
                pixel_angle += 2 * math.pi

            # Calculate angle difference from sweep (how far behind the sweep)
            angle_diff = sweep_angle - pixel_angle
            if angle_diff < 0:
                angle_diff += 2 * math.pi

            # Trail intensity (1.0 at sweep line, fading to 0)
            trail_angle = trail_length * 2 * math.pi
            if angle_diff < trail_angle:
                # In the trail - calculate fade
                trail_intensity = 1.0 - (angle_diff / trail_angle)
                # Apply exponential fade for more realistic look
                trail_intensity = trail_intensity ** 1.5
            else:
                trail_intensity = 0

            # Grid circles (always visible, dim)
            grid_intensity = 0
            for i in range(1, num_circles + 1):
                ring_radius = (i / num_circles) * max_radius
                ring_dist = abs(dist - ring_radius)
                if ring_dist < 1.0:
                    grid_intensity = 0.15 * (1 - ring_dist)

            # Cross-hairs (center lines)
            if abs(dx) < 0.8 or abs(dy) < 0.8:
                grid_intensity = max(grid_intensity, 0.1)

            # Combine trail and grid
            total_intensity = max(trail_intensity, grid_intensity)

            # Apply color (use dynamic radar_color)
            r = int(radar_color[0] * total_intensity)
            g = int(radar_color[1] * total_intensity)
            b = int(radar_color[2] * total_intensity)

            # Add slight background tint
            r = max(r, COLOR_BG[0])
            g = max(g, COLOR_BG[1])
            b = max(b, COLOR_BG[2])

            pixels[x, y] = (r, g, b)

    # Draw time in center using pixel font
    if show_time:
        now = datetime.now()
        hours = now.strftime("%H")
        minutes = now.strftime("%M")

        # Blink colon: visible for first 500ms of each second, hidden for last 500ms
        show_colon = now.microsecond < 500000
        colon = ":" if show_colon else " "
        time_str = f"{hours}{colon}{minutes}"

        # Calculate centered position for pixel font
        text_width = get_pixel_text_width(time_str)
        text_height = CHAR_HEIGHT

        x = (width - text_width) // 2
        y = (height - text_height) // 2

        # Draw time using pixel font
        draw_pixel_text(image, time_str, x, y, COLOR_TIME)

    # Draw scrolling news banner at bottom
    if show_news and news_text:
        text_width = get_mini_text_width(news_text)

        # Scroll position (wraps around for seamless loop)
        total_width = text_width + width
        x_pos = width - (scroll_offset % total_width)

        # Draw the text with rainbow colors
        draw_mini_text(image, news_text, x_pos, BANNER_Y, fade_edges=False, rainbow=True)

    return image


def add_custom_args(parser: argparse.ArgumentParser) -> None:
    """Add custom command line arguments for this animation."""
    parser.add_argument(
        "--circles", "-c", type=int, default=3,
        help="Number of concentric grid circles (default: 3)"
    )
    parser.add_argument(
        "--trail", "-t", type=float, default=0.4,
        help="Trail length as fraction of circle 0-1 (default: 0.4)"
    )
    parser.add_argument(
        "--no-time", action="store_true",
        help="Hide time display"
    )
    parser.add_argument(
        "--no-news", action="store_true",
        help="Hide news scrolling banner"
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
    speed: float = DEFAULT_SPEED,
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

    # News fetcher
    news_fetcher = None
    if kwargs.get('show_news', True):
        news_fetcher = NewsFetcher()
        news_fetcher.start()

    # Scroll state
    scroll_offset = 0

    try:
        while True:
            frame_start = asyncio.get_event_loop().time()

            # Get current news text
            news_text = news_fetcher.get_text() if news_fetcher else ""

            # Increment scroll offset (8 pixels per frame at 2 FPS = 16 pixels/sec)
            scroll_offset += 8

            # Generate frame
            frame = generate_frame(
                width, height, t,
                news_text=news_text,
                scroll_offset=scroll_offset,
                **kwargs
            )

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
        if news_fetcher:
            news_fetcher.stop()
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
        "--speed", type=float, default=DEFAULT_SPEED,
        help=f"Sweep rotation speed per frame (default: {DEFAULT_SPEED:.3f}, 5s/tour at 2FPS)"
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
    no_device = args.no_device

    if not no_device:
        try:
            config = load_config(args.config)
            if args.address:
                config = replace(config, device=replace(config.device, address=args.address))
        except (FileNotFoundError, ValueError) as e:
            print(f"Config error: {e}")
            print("Running in preview mode (--no-device). Use --address to specify a BLE device.")
            no_device = True

    # Extract custom kwargs
    custom_kwargs = {
        'num_circles': args.circles,
        'trail_length': args.trail,
        'show_time': not args.no_time,
        'show_news': not args.no_news,
    }

    try:
        asyncio.run(run_animation(
            config,
            speed=args.speed,
            no_device=no_device,
            fps=args.fps,
            debug=args.debug,
            **custom_kwargs,
        ))
    except KeyboardInterrupt:
        print("\033[?25h", end="")  # Show cursor
        print("\nDone.")
