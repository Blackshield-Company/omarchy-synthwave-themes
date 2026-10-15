"""Palette loading and WCAG contrast helpers. Stdlib only."""
from __future__ import annotations

import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PALETTES = ROOT / "palettes"
ANSI_NAMES = ["black", "red", "green", "yellow", "blue", "magenta", "cyan", "white"]
HEX = re.compile(r"^#[0-9a-fA-F]{6}$")
COLOR_KEYS = [
    "accent", "selection", "muted",
    "background", "dark_background", "darker_background", "lighter_background",
    "foreground", "dark_foreground", "light_foreground", "bright_foreground",
    "red", "yellow", "orange", "green", "cyan", "blue", "magenta", "brown",
    "bright_red", "bright_yellow", "bright_green", "bright_cyan", "bright_blue", "bright_magenta",
    "black", "white", "bright_black", "bright_white",
]
RESOLUTIONS = [(1920, 1080), (2560, 1440), (3440, 1440), (5120, 1440)]
DEFAULT_RES = (2560, 1440)


def load(path: Path) -> dict:
    return tomllib.loads(Path(path).read_text())


def all_palettes() -> list[dict]:
    return [load(p) for p in sorted(PALETTES.glob("*.toml"))]


def ansi16(c: dict) -> list[str]:
    return [c[n] for n in ANSI_NAMES] + [c["bright_" + n] for n in ANSI_NAMES]


def rgb(hexstr: str) -> tuple[int, int, int]:
    h = hexstr.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def luminance(hexstr: str) -> float:
    def ch(v: int) -> float:
        s = v / 255
        return s / 12.92 if s <= 0.04045 else ((s + 0.055) / 1.055) ** 2.4
    r, g, b = (ch(v) for v in rgb(hexstr))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a: str, b: str) -> float:
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


# (foreground key, background key, minimum ratio). 4.5 = WCAG AA body text,
# 3.0 = WCAG AA for UI components / large text (dimmed comments, borders).
TEXT_PAIRS = (
    [("foreground", bg, 7.0) for bg in ("background", "dark_background", "darker_background")]
    + [("foreground", "lighter_background", 4.5), ("bright_foreground", "selection", 4.5),
       ("foreground", "selection", 4.5), ("accent", "background", 4.5),
       ("muted", "background", 4.5), ("muted", "lighter_background", 3.0)]
    + [(n, "background", 4.5) for n in ANSI_NAMES[1:]]
    + [("bright_" + n, "background", 4.5) for n in ANSI_NAMES]
    + [(n, "lighter_background", 3.0) for n in ANSI_NAMES[1:]]
    + [("background", "accent", 4.5)]  # dark text on accent chips (tabs, cursor)
)


def contrast_report(c: dict) -> list[tuple[str, str, float, float, bool]]:
    out = []
    for fg, bg, need in TEXT_PAIRS:
        r = contrast(c[fg], c[bg])
        out.append((fg, bg, r, need, r >= need))
    return out
