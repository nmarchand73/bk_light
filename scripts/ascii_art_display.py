"""Display ASCII art on the LED matrix."""

import argparse
import asyncio
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


# Character to brightness mapping (0.0 = off, 1.0 = full bright)
CHAR_BRIGHTNESS = {
    ' ': 0.0,
    '.': 0.15,
    ':': 0.2,
    '-': 0.25,
    '\'': 0.2,
    ',': 0.15,
    '_': 0.2,
    '`': 0.15,
    '^': 0.25,
    '"': 0.25,
    ';': 0.3,
    '!': 0.35,
    '~': 0.3,
    '\\': 0.35,
    '/': 0.35,
    '|': 0.4,
    '(': 0.4,
    ')': 0.4,
    '[': 0.45,
    ']': 0.45,
    '{': 0.45,
    '}': 0.45,
    '<': 0.4,
    '>': 0.4,
    '=': 0.45,
    '+': 0.5,
    '*': 0.55,
    'x': 0.55,
    'o': 0.6,
    'O': 0.7,
    '0': 0.7,
    '#': 0.8,
    '%': 0.85,
    '@': 0.95,
    '&': 0.9,
    '$': 0.85,
    '8': 0.75,
    'X': 0.7,
    'W': 0.8,
    'M': 0.85,
}

# Default brightness for unknown characters
DEFAULT_BRIGHTNESS = 0.5


def char_to_brightness(char: str) -> float:
    """Convert a character to brightness value."""
    return CHAR_BRIGHTNESS.get(char, DEFAULT_BRIGHTNESS)


def parse_color(color_str: str) -> tuple[int, int, int]:
    """Parse color string to RGB tuple.

    Supports:
    - Hex: #00FF00 or 00FF00
    - Named: green, red, blue, cyan, white, etc.
    """
    color_str = color_str.lower().strip()

    # Named colors
    named_colors = {
        'green': (0, 255, 0),
        'red': (255, 0, 0),
        'blue': (0, 0, 255),
        'cyan': (0, 255, 255),
        'magenta': (255, 0, 255),
        'yellow': (255, 255, 0),
        'white': (255, 255, 255),
        'orange': (255, 128, 0),
        'purple': (128, 0, 255),
        'pink': (255, 100, 200),
        'lime': (128, 255, 0),
        'aqua': (0, 255, 200),
    }

    if color_str in named_colors:
        return named_colors[color_str]

    # Hex color
    color_str = color_str.lstrip('#')
    if len(color_str) == 6:
        try:
            r = int(color_str[0:2], 16)
            g = int(color_str[2:4], 16)
            b = int(color_str[4:6], 16)
            return (r, g, b)
        except ValueError:
            pass

    # Default to green
    return (0, 255, 0)


def ascii_to_image(
    ascii_art: str,
    width: int = 32,
    height: int = 32,
    color: tuple[int, int, int] = (0, 255, 0),
    bg_color: tuple[int, int, int] = (0, 0, 0),
) -> Image.Image:
    """Convert ASCII art string to PIL Image.

    Args:
        ascii_art: Multi-line ASCII art string
        width: Output image width
        height: Output image height
        color: RGB color for bright pixels
        bg_color: RGB background color

    Returns:
        PIL Image sized to width x height
    """
    lines = ascii_art.split('\n')

    # Remove empty lines at start/end
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()

    if not lines:
        return Image.new('RGB', (width, height), bg_color)

    # Find bounding box of actual content (non-space characters)
    min_x, max_x = float('inf'), 0
    min_y, max_y = float('inf'), 0

    for y, line in enumerate(lines):
        for x, char in enumerate(line):
            if char != ' ' and char_to_brightness(char) > 0:
                min_x = min(min_x, x)
                max_x = max(max_x, x)
                min_y = min(min_y, y)
                max_y = max(max_y, y)

    # Handle empty art
    if min_x == float('inf'):
        return Image.new('RGB', (width, height), bg_color)

    # Content dimensions
    content_width = max_x - min_x + 1
    content_height = max_y - min_y + 1

    # Create image at content size (cropped to bounding box)
    art_image = Image.new('RGB', (content_width, content_height), bg_color)
    pixels = art_image.load()

    for y, line in enumerate(lines):
        if y < min_y or y > max_y:
            continue
        for x, char in enumerate(line):
            if x < min_x or x > max_x:
                continue
            brightness = char_to_brightness(char)
            if brightness > 0:
                r = int(color[0] * brightness)
                g = int(color[1] * brightness)
                b = int(color[2] * brightness)
                pixels[x - min_x, y - min_y] = (r, g, b)

    # Scale to fit display while maintaining aspect ratio
    scale_x = width / content_width
    scale_y = height / content_height
    scale = min(scale_x, scale_y)

    new_width = max(1, int(content_width * scale))
    new_height = max(1, int(content_height * scale))

    # Use NEAREST for pixel-art look
    art_image = art_image.resize((new_width, new_height), Image.Resampling.NEAREST)

    # Center on final canvas
    final_image = Image.new('RGB', (width, height), bg_color)
    x_offset = (width - new_width) // 2
    y_offset = (height - new_height) // 2
    final_image.paste(art_image, (x_offset, y_offset))

    return final_image


# Dot characters for console preview
DOT_BRIGHT = "●"
DOT_DIM = "•"
DOT_OFF = " "


def render_console_preview(image: Image.Image, use_color: bool = True) -> str:
    """Convert image to dot-matrix console preview.

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
                line += f"{dot} "

        lines.append(line + RESET if use_color else line)

    return "\n".join(lines)


def print_console_preview(image: Image.Image, title: str = "", use_color: bool = True) -> None:
    """Clear screen and print dot-matrix preview."""
    os.system('cls' if os.name == 'nt' else 'clear')
    if title:
        print(title + "\n")
    print(render_console_preview(image, use_color))
    print()


# Story definitions: list of (art_name, duration, caption)
STORIES = {
    'chase': [
        ('pacman', 0.5, None),
        ('ghost', 0.4, None),
        ('pacman', 0.5, None),
        ('ghost', 0.4, None),
        ('ghost', 0.3, None),
        ('explosion', 0.4, None),
        ('skull', 0.8, None),
        ('star', 0.6, None),  # Game over
    ],
    'love': [
        ('smiley', 0.8, None),
        ('heart', 0.6, None),
        ('smiley', 0.6, None),
        ('heart', 0.6, None),
        ('diamond', 0.8, None),  # Engagement
        ('crown', 0.8, None),    # Wedding
        ('heart', 0.6, None),
        ('star', 1.0, None),
    ],
    'invasion': [
        ('moon', 0.6, None),
        ('star', 0.5, None),
        ('rocket', 0.5, None),
        ('alien', 0.4, None),
        ('invader', 0.4, None),
        ('alien', 0.4, None),
        ('robot', 0.5, None),
        ('explosion', 0.4, None),
        ('fire', 0.5, None),
        ('skull', 0.8, None),
    ],
    'halloween': [
        ('moon', 0.6, None),
        ('cat', 0.5, None),
        ('ghost', 0.5, None),
        ('skull', 0.5, None),
        ('fire', 0.4, None),
        ('ghost', 0.5, None),
        ('skull_bones', 0.6, None),
        ('cat', 0.5, None),
        ('moon', 0.8, None),
    ],
    'adventure': [
        ('smiley', 0.5, None),
        ('house', 0.5, None),
        ('door', 0.4, None),
        ('key', 0.5, None),
        ('door', 0.4, None),
        ('sword', 0.5, None),
        ('shield', 0.5, None),
        ('alien', 0.4, None),
        ('explosion', 0.4, None),
        ('coin', 0.5, None),
        ('diamond', 0.5, None),
        ('crown', 0.6, None),
        ('star', 0.8, None),
    ],
    'weather': [
        ('sun', 0.7, None),
        ('cloud', 0.5, None),
        ('rain', 0.6, None),
        ('lightning', 0.3, None),
        ('rain', 0.5, None),
        ('cloud', 0.5, None),
        ('sun', 0.8, None),
        ('bird', 0.6, None),
    ],
    'ocean': [
        ('sun', 0.6, None),
        ('water', 0.5, None),
        ('fish', 0.5, None),
        ('water', 0.4, None),
        ('fish', 0.5, None),
        ('bird', 0.5, None),
        ('sun', 0.6, None),
        ('moon', 0.6, None),
        ('star', 0.8, None),
    ],
    'space': [
        ('star', 0.5, None),
        ('moon', 0.5, None),
        ('rocket', 0.5, None),
        ('star', 0.4, None),
        ('alien', 0.5, None),
        ('robot', 0.5, None),
        ('explosion', 0.4, None),
        ('star', 0.5, None),
        ('sun', 0.8, None),
    ],
    'dungeon': [
        ('door', 0.5, None),
        ('key', 0.4, None),
        ('door', 0.4, None),
        ('skull', 0.5, None),
        ('sword', 0.4, None),
        ('explosion', 0.4, None),
        ('potion', 0.5, None),
        ('heart', 0.5, None),
        ('coin', 0.4, None),
        ('diamond', 0.5, None),
        ('door', 0.4, None),
        ('crown', 0.6, None),
        ('star', 0.8, None),
    ],
    'forest': [
        ('sun', 0.6, None),
        ('tree', 0.5, None),
        ('bird', 0.5, None),
        ('tree', 0.4, None),
        ('cat', 0.5, None),
        ('fish', 0.5, None),
        ('tree', 0.4, None),
        ('moon', 0.6, None),
        ('star', 0.8, None),
    ],
    'battle': [
        ('robot', 0.5, None),
        ('alien', 0.5, None),
        ('sword', 0.4, None),
        ('shield', 0.4, None),
        ('explosion', 0.3, None),
        ('fire', 0.4, None),
        ('explosion', 0.3, None),
        ('skull', 0.5, None),
        ('crown', 0.6, None),
        ('star', 0.8, None),
    ],
    'party': [
        ('smiley', 0.5, None),
        ('music', 0.5, None),
        ('star', 0.4, None),
        ('heart', 0.4, None),
        ('music', 0.4, None),
        ('diamond', 0.4, None),
        ('star', 0.4, None),
        ('crown', 0.5, None),
        ('explosion', 0.4, None),
        ('star', 0.8, None),
    ],
    'nightmare': [
        ('moon', 0.5, None),
        ('ghost', 0.4, None),
        ('skull', 0.4, None),
        ('alien', 0.4, None),
        ('fire', 0.4, None),
        ('skull_bones', 0.5, None),
        ('lightning', 0.3, None),
        ('ghost', 0.4, None),
        ('explosion', 0.4, None),
        ('sun', 0.6, None),  # Wake up
        ('smiley', 0.8, None),
    ],
    'treasure': [
        ('house', 0.5, None),
        ('door', 0.4, None),
        ('key', 0.4, None),
        ('door', 0.4, None),
        ('skull', 0.4, None),
        ('sword', 0.4, None),
        ('coin', 0.4, None),
        ('coin', 0.3, None),
        ('diamond', 0.5, None),
        ('crown', 0.6, None),
        ('heart', 0.5, None),
        ('star', 0.8, None),
    ],
}


# Built-in ASCII art examples - 32x32 detailed versions
ASCII_ART_EXAMPLES = {
    'heart': """
        @@@@@@        @@@@@@
      @@@@@@@@@@    @@@@@@@@@@
    @@@@@@@@@@@@@@@@@@@@@@@@@@@@
   @@@@@@@@@@@@@@@@@@@@@@@@@@@@@
  @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
  @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
  @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
  @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
   @@@@@@@@@@@@@@@@@@@@@@@@@@@@@
   @@@@@@@@@@@@@@@@@@@@@@@@@@@@@
    @@@@@@@@@@@@@@@@@@@@@@@@@@@
     @@@@@@@@@@@@@@@@@@@@@@@@@
      @@@@@@@@@@@@@@@@@@@@@@@
       @@@@@@@@@@@@@@@@@@@@@
        @@@@@@@@@@@@@@@@@@@
         @@@@@@@@@@@@@@@@@
          @@@@@@@@@@@@@@@
           @@@@@@@@@@@@@
            @@@@@@@@@@@
             @@@@@@@@@
              @@@@@@@
               @@@@@
                @@@
                 @
""",
    'skull': """
        @@@@@@@@@@@@@@@@
      @@@@@@@@@@@@@@@@@@@@
    @@@@@@@@@@@@@@@@@@@@@@@@
   @@@@@@@@@@@@@@@@@@@@@@@@@@
  @@@@@@@@@@@@@@@@@@@@@@@@@@@@
  @@@@@@@@@@@@@@@@@@@@@@@@@@@@
  @@@@@@@@@@@@@@@@@@@@@@@@@@@@
  @@@@@  @@@@@@@@@@@@  @@@@@@@
  @@@@    @@@@@@@@@@    @@@@@@
  @@@@    @@@@@@@@@@    @@@@@@
  @@@@@  @@@@@@@@@@@@  @@@@@@@
  @@@@@@@@@@@@@@@@@@@@@@@@@@@@
  @@@@@@@@@@@@@@@@@@@@@@@@@@@@
   @@@@@@@@@@@  @@@@@@@@@@@@@
    @@@@@@@@@    @@@@@@@@@@@
     @@@@@@@@@@@@@@@@@@@@@@
      @@@@  @@@@@@@@  @@@@
       @@    @@@@@@    @@
        @@  @@    @@  @@
         @@@@      @@@@
""",
    'invader': """
        @@              @@
         @@            @@
          @@          @@
           @@@@@@@@@@@@
         @@@@@@@@@@@@@@@@
        @@@@@@@@@@@@@@@@@@
       @@@@@@@@@@@@@@@@@@@@
      @@@@@@@@@@@@@@@@@@@@@@
     @@@@ @@@@@@@@@@@@@@ @@@@
     @@@@@@@@@@@@@@@@@@@@@@@@
     @@@@@@@@@@@@@@@@@@@@@@@@
     @@ @@@@@@@@@@@@@@@@@@ @@
     @@ @@              @@ @@
     @@ @@              @@ @@
        @@@@          @@@@
        @@@@          @@@@
         @@            @@
""",
    'pacman': """
             @@@@@@@@@@@
          @@@@@@@@@@@@@@@@@
        @@@@@@@@@@@@@@@@@@@@@
       @@@@@@@@@@@@@@@@@@@@@@@
      @@@@@@@@@@@@@@@@@
     @@@@@@@@@@@@@@@
    @@@@@@@@@@@@@
    @@@@@@@@@@
    @@@@@@@
    @@@@@@@@@@
    @@@@@@@@@@@@@
     @@@@@@@@@@@@@@@
      @@@@@@@@@@@@@@@@@
       @@@@@@@@@@@@@@@@@@@@@@@
        @@@@@@@@@@@@@@@@@@@@@
          @@@@@@@@@@@@@@@@@
             @@@@@@@@@@@
""",
    'ghost': """
          @@@@@@@@@@@@
        @@@@@@@@@@@@@@@@
       @@@@@@@@@@@@@@@@@@
      @@@@@@@@@@@@@@@@@@@@
     @@@@@@@@@@@@@@@@@@@@@@
     @@@@@@@@@@@@@@@@@@@@@@
     @@@@@  @@@@@@@@  @@@@@
     @@@@    @@@@@@    @@@@
     @@@@    @@@@@@    @@@@
     @@@@@  @@@@@@@@  @@@@@
     @@@@@@@@@@@@@@@@@@@@@@
     @@@@@@@@@@@@@@@@@@@@@@
     @@@@@@@@@@@@@@@@@@@@@@
     @@@@@@@@@@@@@@@@@@@@@@
     @@@@@@@@@@@@@@@@@@@@@@
     @@@@@@@@@@@@@@@@@@@@@@
     @@@  @@@@  @@@@  @@@@@
     @@    @@    @@    @@@@
""",
    'smiley': """
         @@@@@@@@@@@@@@
       @@@@@@@@@@@@@@@@@@
      @@@@@@@@@@@@@@@@@@@@
     @@@@@@@@@@@@@@@@@@@@@@
    @@@@@@@@@@@@@@@@@@@@@@@@
    @@@@@  @@@@@@@@@@  @@@@@
    @@@@    @@@@@@@@    @@@@
    @@@@    @@@@@@@@    @@@@
    @@@@@  @@@@@@@@@@  @@@@@
    @@@@@@@@@@@@@@@@@@@@@@@@
    @@@@@@@@@@@@@@@@@@@@@@@@
    @@@@@@@@@@@@@@@@@@@@@@@@
    @@@  @@@@@@@@@@@@@@  @@@
    @@@@  @@@@@@@@@@@@  @@@@
     @@@@@  @@@@@@@@  @@@@@
      @@@@@@        @@@@@@
       @@@@@@@@@@@@@@@@@@
         @@@@@@@@@@@@@@
""",
    'star': """
              @@@@
              @@@@
              @@@@
              @@@@
             @@@@@@
             @@@@@@
   @@       @@@@@@@@       @@
    @@     @@@@@@@@@@     @@
     @@@  @@@@@@@@@@@@  @@@
      @@@@@@@@@@@@@@@@@@@
  @@@@@@@@@@@@@@@@@@@@@@@@@@@@
  @@@@@@@@@@@@@@@@@@@@@@@@@@@@
      @@@@@@@@@@@@@@@@@@@
       @@@@@@@@@@@@@@@@@
        @@@@@@@@@@@@@@@
         @@@@@@@@@@@@@
          @@@@@@@@@@@
         @@@@@   @@@@@
        @@@@       @@@@
       @@@           @@@
      @@               @@
""",
    'cat': """
    @@                    @@
    @@@                  @@@
    @@@@                @@@@
    @@@@@              @@@@@
    @@@@@@@@@@@@@@@@@@@@@@@@
    @@@@@@@@@@@@@@@@@@@@@@@@
     @@@@@@@@@@@@@@@@@@@@@@
     @@@@@@@@@@@@@@@@@@@@@@
     @@@@@  @@@@@@@@  @@@@@
     @@@@    @@@@@@    @@@@
     @@@@    @@@@@@    @@@@
     @@@@@  @@@@@@@@  @@@@@
     @@@@@@@@@@@@@@@@@@@@@@
     @@@@ @@@@@@@@@@@@ @@@@
     @@@   @@@@@@@@@@   @@@
      @@@@@@@@  @@@@@@@@@@
       @@@@@@    @@@@@@@@
         @@@@@@@@@@@@@@
""",
    'moon': """
            @@@@@@@@@@@@@
          @@@@@@@@@@@@@
        @@@@@@@@@@@@@
       @@@@@@@@@@@@@
      @@@@@@@@@@@@@
     @@@@@@@@@@@@@
     @@@@@@@@@@@@@
    @@@@@@@@@@@@@
    @@@@@@@@@@@@@
    @@@@@@@@@@@@@
    @@@@@@@@@@@@@
     @@@@@@@@@@@@@
     @@@@@@@@@@@@@
      @@@@@@@@@@@@@
       @@@@@@@@@@@@@
        @@@@@@@@@@@@@
          @@@@@@@@@@@@@
            @@@@@@@@@@@@@
""",
    'sun': """
              @@@@
       @@     @@@@     @@
        @@    @@@@    @@
         @@  @@@@@@  @@
    @@    @@@@@@@@@@@@    @@
     @@  @@@@@@@@@@@@@@  @@
      @@@@@@@@@@@@@@@@@@@@
  @@@@@@@@@@@@@@@@@@@@@@@@@@@@
  @@@@@@@@@@@@@@@@@@@@@@@@@@@@
  @@@@@@@@@@@@@@@@@@@@@@@@@@@@
  @@@@@@@@@@@@@@@@@@@@@@@@@@@@
      @@@@@@@@@@@@@@@@@@@@
     @@  @@@@@@@@@@@@@@  @@
    @@    @@@@@@@@@@@@    @@
         @@  @@@@@@  @@
        @@    @@@@    @@
       @@     @@@@     @@
              @@@@
""",
    'cloud': """


        @@@@@@@@@@@@
      @@@@@@@@@@@@@@@@
     @@@@@@@@@@@@@@@@@@@@@@
   @@@@@@@@@@@@@@@@@@@@@@@@@@
  @@@@@@@@@@@@@@@@@@@@@@@@@@@@
 @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
 @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
 @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
  @@@@@@@@@@@@@@@@@@@@@@@@@@@@


""",
    'rain': """
        @@@@@@@@@@@@@@@@
      @@@@@@@@@@@@@@@@@@@@
    @@@@@@@@@@@@@@@@@@@@@@@@
   @@@@@@@@@@@@@@@@@@@@@@@@@@
  @@@@@@@@@@@@@@@@@@@@@@@@@@@@
  @@@@@@@@@@@@@@@@@@@@@@@@@@@@

     @@      @@      @@
      @@      @@      @@
     @@      @@      @@
      @@      @@      @@
     @@      @@      @@
      @@      @@      @@
     @@      @@      @@
      @@      @@      @@
     @@      @@      @@
      @@      @@      @@
""",
    'lightning': """
           @@@@@@@@@
          @@@@@@@@@
         @@@@@@@@@
        @@@@@@@@@
       @@@@@@@@@
      @@@@@@@@@
     @@@@@@@@@
    @@@@@@@@@@@@@@@@@@@
   @@@@@@@@@@@@@@@@@@@
          @@@@@@@@@
         @@@@@@@@@
        @@@@@@@@@
       @@@@@@@@@
      @@@@@@@@@
     @@@@@@@
    @@@@@
   @@@
  @
""",
    'tree': """
              @@@@
             @@@@@@
            @@@@@@@@
           @@@@@@@@@@
          @@@@@@@@@@@@
         @@@@@@@@@@@@@@
        @@@@@@@@@@@@@@@@
       @@@@@@@@@@@@@@@@@@
      @@@@@@@@@@@@@@@@@@@@
     @@@@@@@@@@@@@@@@@@@@@@
    @@@@@@@@@@@@@@@@@@@@@@@@
   @@@@@@@@@@@@@@@@@@@@@@@@@@
            @@@@@@
            @@@@@@
            @@@@@@
            @@@@@@
            @@@@@@
          @@@@@@@@@@
         @@@@@@@@@@@@
""",
    'house': """
              @@@@
             @@@@@@
            @@@@@@@@
           @@@@@@@@@@
          @@@@@@@@@@@@
         @@@@@@@@@@@@@@
        @@@@@@@@@@@@@@@@
       @@@@@@@@@@@@@@@@@@
      @@@@@@@@@@@@@@@@@@@@
     @@@@@@@@@@@@@@@@@@@@@@
    @@@@@@@@@@@@@@@@@@@@@@@@
    @@@@@@@@@@@@@@@@@@@@@@@@
    @@@@    @@@@@@@@    @@@@
    @@@@    @@@@@@@@    @@@@
    @@@@    @@@@@@@@    @@@@
    @@@@    @@@@@@@@    @@@@
    @@@@    @@    @@    @@@@
    @@@@          @@    @@@@
    @@@@@@@@@@@@@@@@@@@@@@@@
""",
    'rocket': """
              @@@@
             @@@@@@
            @@@@@@@@
           @@@@@@@@@@
          @@@@@@@@@@@@
         @@@@@@@@@@@@@@
         @@@@@@@@@@@@@@
        @@@@@@@@@@@@@@@@
        @@@@@@@@@@@@@@@@
        @@@@@@@@@@@@@@@@
        @@@@@@@@@@@@@@@@
        @@@@@@@@@@@@@@@@
       @@@@@@@@@@@@@@@@@@
       @@  @@@@@@@@@@  @@
      @@    @@@@@@@@    @@
     @@      @@@@@@      @@
    @@                    @@
   @@                      @@
""",
    'alien': """
         @@@@@@@@@@@@@@
       @@@@@@@@@@@@@@@@@@
      @@@@@@@@@@@@@@@@@@@@
     @@@@@@@@@@@@@@@@@@@@@@
    @@@@@@@@@@@@@@@@@@@@@@@@
    @@@@@    @@@@@@    @@@@@
    @@@@      @@@@      @@@@
    @@@@      @@@@      @@@@
    @@@@@    @@@@@@    @@@@@
    @@@@@@@@@@@@@@@@@@@@@@@@
     @@@@@@@@@@@@@@@@@@@@@@
      @@@@@  @@@@@@  @@@@@
       @@@@@@@@@@@@@@@@@
      @@@@@@@@@@@@@@@@@@@@
     @@@@              @@@@
    @@@@                @@@@
   @@@@                  @@@@
  @@                        @@
""",
    'robot': """
      @@@@@@@@@@@@@@@@@@@@
     @@@@@@@@@@@@@@@@@@@@@@
     @@                  @@
     @@  @@@@      @@@@  @@
     @@  @@@@      @@@@  @@
     @@                  @@
     @@    @@@@@@@@@@    @@
     @@@@@@@@@@@@@@@@@@@@@@
      @@@@@@@@@@@@@@@@@@@@
           @@@@@@@@
      @@@@@@@@@@@@@@@@@@@@
     @@@@@@@@@@@@@@@@@@@@@@
     @@@@@@@@@@@@@@@@@@@@@@
     @@@@  @@@@@@@@@@  @@@@
     @@@@  @@@@@@@@@@  @@@@
     @@@@  @@@@@@@@@@  @@@@
     @@@@  @@@@  @@@@  @@@@
     @@@@  @@@@  @@@@  @@@@
""",
    'fish': """


              @@
             @@@@
            @@@@@@@@@@@@@@@@@@
          @@@@@@@@@@@@@@@@@@@@@@
        @@@@@ @@@@@@@@@@@@@@@@@@@@
      @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
     @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
    @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
     @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
      @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
        @@@@@@@@@@@@@@@@@@@@@@@@@@
          @@@@@@@@@@@@@@@@@@@@@@
            @@@@@@@@@@@@@@@@@@
             @@@@
              @@

""",
    'bird': """
                  @@
                 @@@@
                @@@@@@
               @@@@@@
    @@@@@@@@@@@@@@@@@@@@@@@@@
   @@@@@@@@@@@@@@@@@@@@@@@@@@@
  @@@@@@@@@@@@@@@@@@@@@@@@@@@@@
 @@@@@@@@@@@@@@@@@@@@@@@@@@@@@
  @@@@@@@@@@@@@@@@@@@@@@@@@
    @@@@@@@@@@@@@@@@@@@@@
      @@@@@@@@@@@@@@@
        @@@@@@@@@@
          @@@@@@
           @@@@
            @@
""",
    'crown': """
   @@                      @@
   @@@                    @@@
   @@@@                  @@@@
   @@@@@                @@@@@
   @@@@@@    @@@@@@    @@@@@@
   @@@@@@@  @@@@@@@@  @@@@@@@
   @@@@@@@@@@@@@@@@@@@@@@@@@@
   @@@@@@@@@@@@@@@@@@@@@@@@@@
   @@@@@@@@@@@@@@@@@@@@@@@@@@
   @@@@@@@@@@@@@@@@@@@@@@@@@@
    @@@@@@@@@@@@@@@@@@@@@@@@
    @@@@@@@@@@@@@@@@@@@@@@@@
    @@@@@@@@@@@@@@@@@@@@@@@@
    @@@@@@@@@@@@@@@@@@@@@@@@


""",
    'diamond': """
              @@@@
             @@@@@@
            @@@@@@@@
           @@@@@@@@@@
          @@@@@@@@@@@@
         @@@@@@@@@@@@@@
        @@@@@@@@@@@@@@@@
       @@@@@@@@@@@@@@@@@@
      @@@@@@@@@@@@@@@@@@@@
       @@@@@@@@@@@@@@@@@@
        @@@@@@@@@@@@@@@@
         @@@@@@@@@@@@@@
          @@@@@@@@@@@@
           @@@@@@@@@@
            @@@@@@@@
             @@@@@@
              @@@@
               @@
""",
    'music': """
           @@@@@@@@@@@@@@
           @@@@@@@@@@@@@@
           @@          @@
           @@          @@
           @@          @@
           @@          @@
           @@          @@
           @@        @@@@
           @@      @@@@@@
           @@    @@@@@@@@
           @@   @@@@@@@@@
       @@@@@@   @@@@@@@@@
      @@@@@@@   @@@@@@@@@
     @@@@@@@@    @@@@@@@@
     @@@@@@@@      @@@@
     @@@@@@@@
      @@@@@@
       @@@@
""",
    'explosion': """
      @@            @@@@
       @@    @@@@    @@
   @@   @@  @@@@@@  @@    @@
    @@   @@@@@@@@@@@@    @@
     @@ @@@@@@@@@@@@@@ @@
       @@@@@@@@@@@@@@@@
  @@ @@@@@@@@@@@@@@@@@@@@ @@
   @@@@@@@@@@@@@@@@@@@@@@@@
  @@@@@@@@@@@@@@@@@@@@@@@@@@
 @@@@@@@@@@@@@@@@@@@@@@@@@@@
 @@@@@@@@@@@@@@@@@@@@@@@@@@@
  @@@@@@@@@@@@@@@@@@@@@@@@@@
   @@@@@@@@@@@@@@@@@@@@@@@@
  @@ @@@@@@@@@@@@@@@@@@@@ @@
       @@@@@@@@@@@@@@@@
     @@ @@@@@@@@@@@@@@ @@
    @@   @@@@@@@@@@@@    @@
   @@   @@  @@@@@@  @@    @@
       @@    @@@@    @@
      @@            @@@@
""",
    'sword': """
              @@@@
              @@@@
              @@@@
              @@@@
              @@@@
              @@@@
              @@@@
              @@@@
              @@@@
              @@@@
              @@@@
              @@@@
              @@@@
              @@@@
              @@@@
        @@@@@@@@@@@@@@@@
        @@@@@@@@@@@@@@@@
              @@@@
              @@@@
             @@@@@@
            @@@@@@@@
""",
    'shield': """
     @@@@@@@@@@@@@@@@@@@@
    @@@@@@@@@@@@@@@@@@@@@@
   @@@@@@@@@@@@@@@@@@@@@@@@
   @@@@@@@@@@@@@@@@@@@@@@@@
   @@@@@@@@@@@@@@@@@@@@@@@@
   @@@@@@@@@@@@@@@@@@@@@@@@
   @@@@@@@@@@@@@@@@@@@@@@@@
   @@@@@@@@@@@@@@@@@@@@@@@@
   @@@@@@@@@@@@@@@@@@@@@@@@
    @@@@@@@@@@@@@@@@@@@@@@
    @@@@@@@@@@@@@@@@@@@@@@
     @@@@@@@@@@@@@@@@@@@@
      @@@@@@@@@@@@@@@@@@
       @@@@@@@@@@@@@@@@
        @@@@@@@@@@@@@@
         @@@@@@@@@@@@
          @@@@@@@@@@
           @@@@@@@@
            @@@@@@
             @@@@
              @@
""",
    'potion': """
           @@@@@@@@
          @@      @@
          @@      @@
           @@@@@@@@
            @@@@@@
           @@@@@@@@
          @@@@@@@@@@
         @@@@@@@@@@@@
        @@@@@@@@@@@@@@
       @@@@@@@@@@@@@@@@
       @@@@@@@@@@@@@@@@
       @@@@@@@@@@@@@@@@
       @@@@@@@@@@@@@@@@
       @@@@@@@@@@@@@@@@
       @@@@@@@@@@@@@@@@
        @@@@@@@@@@@@@@
         @@@@@@@@@@@@
          @@@@@@@@@@
""",
    'coin': """
         @@@@@@@@@@@@
       @@@@@@@@@@@@@@@@
      @@@@@@@@@@@@@@@@@@
     @@@@@@@@@@@@@@@@@@@@
    @@@@@@ @@@@@@@@ @@@@@@
    @@@@@@  @@@@@@  @@@@@@
    @@@@@@  @@@@@@  @@@@@@
    @@@@@@  @@@@@@  @@@@@@
    @@@@@@  @@@@@@  @@@@@@
    @@@@@@  @@@@@@  @@@@@@
    @@@@@@  @@@@@@  @@@@@@
    @@@@@@  @@@@@@  @@@@@@
    @@@@@@ @@@@@@@@ @@@@@@
     @@@@@@@@@@@@@@@@@@@@
      @@@@@@@@@@@@@@@@@@
       @@@@@@@@@@@@@@@@
         @@@@@@@@@@@@
""",
    'key': """
          @@@@@@@@@@
        @@@@@@@@@@@@@@
       @@@@        @@@@
       @@@@        @@@@
       @@@@        @@@@
       @@@@        @@@@
        @@@@@@@@@@@@@@
          @@@@@@@@@@
             @@@@
             @@@@
             @@@@
             @@@@@@@@
             @@@@
             @@@@
             @@@@@@@@
             @@@@
             @@@@
             @@@@@@@@
""",
    'door': """
    @@@@@@@@@@@@@@@@@@@@@@
    @@@@@@@@@@@@@@@@@@@@@@
    @@@@                @@
    @@@@                @@
    @@@@                @@
    @@@@                @@
    @@@@                @@
    @@@@                @@
    @@@@          @@@@  @@
    @@@@          @@@@  @@
    @@@@          @@@@  @@
    @@@@                @@
    @@@@                @@
    @@@@                @@
    @@@@                @@
    @@@@                @@
    @@@@                @@
    @@@@@@@@@@@@@@@@@@@@@@
    @@@@@@@@@@@@@@@@@@@@@@
""",
    'fire': """
              @@
             @@@@
            @@@@@@
           @@@  @@@
          @@@    @@@
         @@@  @@  @@@
        @@@  @@@@  @@@
        @@@ @@@@@@ @@@
       @@@@@@@@@@@@@@@
       @@@@@@@@@@@@@@@
      @@@@@@@@@@@@@@@@@
      @@@@@@@@@@@@@@@@@
     @@@@@@@@@@@@@@@@@@@
     @@@@@@@@@@@@@@@@@@@
    @@@@@@@@@@@@@@@@@@@@@
     @@@@@@@@@@@@@@@@@@@
      @@@@@@@@@@@@@@@@@
        @@@@@@@@@@@@@
""",
    'water': """
             @@@@
            @@@@@@
           @@@@@@@@
          @@@@@@@@@@
           @@@@@@@@
            @@@@@@
           @@@@@@@@
          @@@@@@@@@@
         @@@@@@@@@@@@
        @@@@@@@@@@@@@@
       @@@@@@@@@@@@@@@@
      @@@@@@@@@@@@@@@@@@
     @@@@@@@@@@@@@@@@@@@@
    @@@@@@@@@@@@@@@@@@@@@@
   @@@@@@@@@@@@@@@@@@@@@@@@
  @@@@@@@@@@@@@@@@@@@@@@@@@@
 @@@@@@@@@@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
""",
    'skull_bones': """
        @@@@@@@@@@@@@@@@
      @@@@@@@@@@@@@@@@@@@@
    @@@@@@@@@@@@@@@@@@@@@@@@
   @@@@@@@@@@@@@@@@@@@@@@@@@@
  @@@@@  @@@@@@@@@@@@  @@@@@@@
  @@@@    @@@@@@@@@@    @@@@@@
  @@@@    @@@@@@@@@@    @@@@@@
  @@@@@  @@@@@@@@@@@@  @@@@@@@
  @@@@@@@@@@@@@@@@@@@@@@@@@@@@
   @@@@@@@@@@@  @@@@@@@@@@@@@
    @@@@@@@@@    @@@@@@@@@@@
     @@@@@@@@@@@@@@@@@@@@@@
@@    @@@@  @@@@@@@@  @@@@    @@
 @@    @@    @@@@@@    @@    @@
  @@  @@@@  @@    @@  @@@@  @@
   @@@@  @@@@      @@@@  @@@@
    @@    @@        @@    @@
""",
}


def lerp_images(img1: Image.Image, img2: Image.Image, t: float) -> Image.Image:
    """Linear interpolation between two images.

    Args:
        img1: Starting image
        img2: Ending image
        t: Interpolation factor (0.0 = img1, 1.0 = img2)

    Returns:
        Blended image
    """
    width, height = img1.size
    result = Image.new('RGB', (width, height), (0, 0, 0))

    px1 = img1.load()
    px2 = img2.load()
    px_out = result.load()

    for y in range(height):
        for x in range(width):
            r1, g1, b1 = px1[x, y]
            r2, g2, b2 = px2[x, y]

            r = int(r1 + (r2 - r1) * t)
            g = int(g1 + (g2 - g1) * t)
            b = int(b1 + (b2 - b1) * t)

            px_out[x, y] = (r, g, b)

    return result


def ease_in_out(t: float) -> float:
    """Smooth easing function for nicer transitions."""
    if t < 0.5:
        return 2 * t * t
    else:
        return 1 - pow(-2 * t + 2, 2) / 2


async def display_story(
    config,
    story_name: str,
    color: tuple[int, int, int] = (0, 255, 0),
    speed: float = 1.0,
    loop: bool = True,
    morph: bool = True,
    no_device: bool = False,
    use_color: bool = True,
) -> None:
    """Play a story sequence with morphing transitions."""
    if story_name not in STORIES:
        print(f"Error: Unknown story '{story_name}'")
        print(f"Available: {', '.join(STORIES.keys())}")
        return

    story = STORIES[story_name]

    # Determine canvas size
    if no_device:
        width, height = 32, 32
        manager = None
    else:
        manager = PanelManager(config)
        await manager.__aenter__()
        width, height = manager.canvas_size

    # Pre-render all frames
    art_cache = {}
    for art_name, _, _ in story:
        if art_name not in art_cache and art_name in ASCII_ART_EXAMPLES:
            art_cache[art_name] = ascii_to_image(
                ASCII_ART_EXAMPLES[art_name], width, height, color
            )

    print(f"\033[?25l", end="")  # Hide cursor

    try:
        while True:
            for i, (art_name, duration, caption) in enumerate(story):
                if art_name not in art_cache:
                    continue

                current_img = art_cache[art_name]
                adjusted_duration = duration / speed

                # Show current frame
                title = f"Story: {story_name} - {art_name} - Ctrl+C to exit"
                print_console_preview(current_img, title, use_color)

                if manager:
                    await manager.send_image(current_img, delay=0.05)

                # Morph to next frame if enabled
                if morph and i < len(story) - 1:
                    next_art = story[i + 1][0]
                    if next_art in art_cache:
                        next_img = art_cache[next_art]

                        # Hold then morph
                        await asyncio.sleep(adjusted_duration * 0.6)

                        # Quick morph transition
                        morph_steps = 8
                        for step in range(1, morph_steps + 1):
                            t = ease_in_out(step / morph_steps)
                            frame = lerp_images(current_img, next_img, t)
                            print_console_preview(frame, title, use_color)
                            if manager:
                                await manager.send_image(frame, delay=0.03)
                            await asyncio.sleep(adjusted_duration * 0.4 / morph_steps)
                    else:
                        await asyncio.sleep(adjusted_duration)
                else:
                    await asyncio.sleep(adjusted_duration)

            if not loop:
                break

    except asyncio.CancelledError:
        pass
    finally:
        print(f"\033[?25h", end="")  # Show cursor
        if manager:
            await manager.__aexit__(None, None, None)


async def display_morphing_art(
    config,
    art_names: list[str],
    color: tuple[int, int, int] = (0, 255, 0),
    hold_time: float = 0.8,
    morph_time: float = 0.4,
    morph_steps: int = 10,
    loop: bool = True,
    no_device: bool = False,
    use_color: bool = True,
) -> None:
    """Display morphing animation between multiple ASCII arts."""
    # Determine canvas size
    if no_device:
        width, height = 32, 32
        manager = None
    else:
        manager = PanelManager(config)
        await manager.__aenter__()
        width, height = manager.canvas_size

    # Convert all arts to images
    images = []
    for name in art_names:
        if name in ASCII_ART_EXAMPLES:
            art = ASCII_ART_EXAMPLES[name]
        else:
            print(f"Warning: Unknown art '{name}', skipping")
            continue
        img = ascii_to_image(art, width, height, color)
        images.append((name, img))

    if len(images) < 2:
        print("Error: Need at least 2 arts for morphing")
        return

    print(f"\033[?25l", end="")  # Hide cursor

    try:
        frame_interval = morph_time / morph_steps
        idx = 0

        while True:
            current_name, current_img = images[idx]
            next_idx = (idx + 1) % len(images)
            next_name, next_img = images[next_idx]

            # Hold on current image
            title = f"Morphing: {current_name} - {width}x{height} - Ctrl+C to exit"
            print_console_preview(current_img, title, use_color)
            if manager:
                await manager.send_image(current_img, delay=0.1)
            await asyncio.sleep(hold_time)

            # Morph to next image
            for step in range(morph_steps + 1):
                t = step / morph_steps
                t_eased = ease_in_out(t)

                frame = lerp_images(current_img, next_img, t_eased)

                title = f"Morphing: {current_name} → {next_name} - {width}x{height}"
                print_console_preview(frame, title, use_color)

                if manager:
                    await manager.send_image(frame, delay=0.05)

                await asyncio.sleep(frame_interval)

            idx = next_idx

            if not loop and idx == 0:
                break

    except asyncio.CancelledError:
        pass
    finally:
        print(f"\033[?25h", end="")  # Show cursor
        if manager:
            await manager.__aexit__(None, None, None)


async def display_ascii_art(
    config,
    ascii_art: str,
    color: tuple[int, int, int] = (0, 255, 0),
    duration: float = 0,
    no_device: bool = False,
    use_color: bool = True,
) -> None:
    """Display ASCII art on the LED device and console."""
    # Determine canvas size
    if no_device:
        width, height = 32, 32
        manager = None
    else:
        manager = PanelManager(config)
        await manager.__aenter__()
        width, height = manager.canvas_size

    # Convert ASCII art to image
    image = ascii_to_image(ascii_art, width, height, color)

    # Show console preview
    title = f"ASCII Art Display - {width}x{height} - Ctrl+C to exit"
    print_console_preview(image, title, use_color)

    # Send to device
    if manager:
        await manager.send_image(image, delay=0.1)

    try:
        if duration > 0:
            await asyncio.sleep(duration)
        else:
            while True:
                await asyncio.sleep(1)
    except asyncio.CancelledError:
        pass
    finally:
        if manager:
            await manager.__aexit__(None, None, None)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Display ASCII art on LED matrix"
    )
    parser.add_argument("--config", type=Path, help="Path to config file")
    parser.add_argument("--address", help="Override device address")
    parser.add_argument(
        "--file", "-f", type=Path,
        help="Path to ASCII art text file"
    )
    parser.add_argument(
        "--art", "-a", type=str,
        help="ASCII art string (use \\n for newlines)"
    )
    parser.add_argument(
        "--example", "-e", type=str,
        choices=list(ASCII_ART_EXAMPLES.keys()),
        help="Use built-in example art"
    )
    parser.add_argument(
        "--color", "-c", type=str, default="green",
        help="Color: name (green, red, cyan...) or hex (#00FF00)"
    )
    parser.add_argument(
        "--duration", "-d", type=float, default=0,
        help="Display duration in seconds (0 = forever)"
    )
    parser.add_argument(
        "--list", "-l", action="store_true",
        help="List available example art"
    )
    parser.add_argument(
        "--no-device", action="store_true",
        help="Preview only, don't connect to LED device"
    )
    parser.add_argument(
        "--no-color", action="store_true",
        help="Disable colors in console preview"
    )
    parser.add_argument(
        "--morph", "-m", nargs="+",
        help="Morph between multiple arts (e.g., --morph heart skull ghost)"
    )
    parser.add_argument(
        "--story", "-s", type=str,
        choices=list(STORIES.keys()),
        help="Play a predefined story"
    )
    parser.add_argument(
        "--speed", type=float, default=1.0,
        help="Story playback speed multiplier (default: 1.0)"
    )
    parser.add_argument(
        "--no-morph", action="store_true",
        help="Disable morphing transitions in story mode"
    )
    parser.add_argument(
        "--list-stories", action="store_true",
        help="List available stories"
    )
    parser.add_argument(
        "--hold", type=float, default=0.8,
        help="Hold time on each art in seconds (default: 0.8)"
    )
    parser.add_argument(
        "--morph-time", type=float, default=0.4,
        help="Morph transition time in seconds (default: 0.4)"
    )
    parser.add_argument(
        "--morph-steps", type=int, default=10,
        help="Number of frames for morph transition (default: 10)"
    )
    parser.add_argument(
        "--no-loop", action="store_true",
        help="Don't loop morphing animation"
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    # List examples
    if args.list:
        print("Available ASCII art examples:\n")
        for name, art in ASCII_ART_EXAMPLES.items():
            print(f"  {name}:")
            for line in art.strip().split('\n')[:3]:
                print(f"    {line}")
            print("    ...")
            print()
        sys.exit(0)

    # List stories
    if args.list_stories:
        print("Available stories:\n")
        for name, scenes in STORIES.items():
            arts = [s[0] for s in scenes]
            total_time = sum(s[1] for s in scenes)
            print(f"  {name}:")
            print(f"    Sequence: {' → '.join(arts)}")
            print(f"    Duration: {total_time:.1f}s")
            print()
        sys.exit(0)

    # Parse color
    color = parse_color(args.color)

    # Load config if using device
    config = None
    if not args.no_device:
        config = load_config(args.config)
        if args.address:
            config = replace(config, device=replace(config.device, address=args.address))

    # Story mode
    if args.story:
        try:
            asyncio.run(display_story(
                config,
                story_name=args.story,
                color=color,
                speed=args.speed,
                loop=not args.no_loop,
                morph=not args.no_morph,
                no_device=args.no_device,
                use_color=not args.no_color,
            ))
        except KeyboardInterrupt:
            print("\033[?25h", end="")  # Show cursor
            print("\nDone.")
        sys.exit(0)

    # Morphing mode
    if args.morph:
        try:
            asyncio.run(display_morphing_art(
                config,
                art_names=args.morph,
                color=color,
                hold_time=args.hold,
                morph_time=args.morph_time,
                morph_steps=args.morph_steps,
                loop=not args.no_loop,
                no_device=args.no_device,
                use_color=not args.no_color,
            ))
        except KeyboardInterrupt:
            print("\033[?25h", end="")  # Show cursor
            print("\nDone.")
        sys.exit(0)

    # Single art mode - get ASCII art from source
    ascii_art = None

    if args.example:
        ascii_art = ASCII_ART_EXAMPLES[args.example]
    elif args.file:
        if not args.file.exists():
            print(f"Error: File not found: {args.file}")
            sys.exit(1)
        ascii_art = args.file.read_text()
    elif args.art:
        ascii_art = args.art.replace('\\n', '\n')
    else:
        # Read from stdin
        print("Enter ASCII art (Ctrl+D or Ctrl+Z to finish):")
        try:
            ascii_art = sys.stdin.read()
        except KeyboardInterrupt:
            sys.exit(0)

    if not ascii_art or not ascii_art.strip():
        print("Error: No ASCII art provided")
        print("Use --example, --file, --art, --morph, or pipe input")
        sys.exit(1)

    try:
        asyncio.run(display_ascii_art(
            config,
            ascii_art,
            color,
            args.duration,
            no_device=args.no_device,
            use_color=not args.no_color,
        ))
    except KeyboardInterrupt:
        print("\nDone.")
