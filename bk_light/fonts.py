from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

ASSETS_DIR = Path(__file__).resolve().parents[1] / "assets"
FONTS_DIR = ASSETS_DIR / "fonts"
FONT_EXTENSIONS = {".ttf", ".otf", ".ttc"}


def normalize(name: str) -> str:
    return "".join(ch.lower() for ch in name if ch.isalnum())


@dataclass(frozen=True)
class FontProfile:
    recommended_size: Optional[int] = None
    offset_x: int = 0
    offset_y: int = 0
    colon_dx: int = 0
    colon_top_adjust: int = 7
    colon_bottom_adjust: int = 6


FONT_PROFILES: dict[str, FontProfile] = {
    "aldopc": FontProfile(recommended_size=16, offset_x=1, offset_y=-1, colon_bottom_adjust=8),
    "caviardreams": FontProfile(recommended_size=16),
    "dolcevitalight": FontProfile(recommended_size=14),
    "kenyancoffeerg": FontProfile(recommended_size=15, offset_y=-1, colon_dx=1, colon_top_adjust=8, colon_bottom_adjust=9),
    "kimberleybl": FontProfile(recommended_size=11, offset_y=-1),
}


def resolve_font(reference: Optional[str]) -> Optional[Path]:
    if not reference:
        return None
    candidate = Path(reference)
    if candidate.exists():
        return candidate
    if not reference.lower().endswith(tuple(FONT_EXTENSIONS)) and FONTS_DIR.exists():
        target = normalize(reference)
        for entry in FONTS_DIR.iterdir():
            if entry.suffix.lower() not in FONT_EXTENSIONS:
                continue
            if normalize(entry.stem) == target:
                return entry
    relative_candidate = ASSETS_DIR / reference
    if relative_candidate.exists():
        return relative_candidate
    return candidate


def list_available_fonts() -> list[str]:
    if not FONTS_DIR.exists():
        return []
    names: list[str] = []
    for entry in FONTS_DIR.iterdir():
        if entry.is_file() and entry.suffix.lower() in FONT_EXTENSIONS:
            names.append(entry.stem)
    return sorted(names)


def get_font_profile(reference: Optional[str], resolved: Optional[Path] = None) -> FontProfile:
    if resolved:
        key = normalize(resolved.stem)
        if key in FONT_PROFILES:
            return FONT_PROFILES[key]
    if reference:
        key = normalize(Path(reference).stem if Path(reference).suffix else reference)
        if key in FONT_PROFILES:
            return FONT_PROFILES[key]
    return FontProfile()
