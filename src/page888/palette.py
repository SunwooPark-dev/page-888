"""The eight teletext colours, the allowed foreground/background pairs and contrast.

Pure. Used by render (CSS is generated only from here), verify and tests (R13.6).
"""
from __future__ import annotations

PALETTE: dict[str, str] = {
    "black": "#000000",
    "red": "#ff0000",
    "green": "#00ff00",
    "yellow": "#ffff00",
    "blue": "#0000ff",
    "magenta": "#ff00ff",
    "cyan": "#00ffff",
    "white": "#ffffff",
}

# background -> foregrounds that reach 4.5:1 (explicit; checked against computed ratios).
_ON: dict[str, tuple[str, ...]] = {
    "black": ("white", "yellow", "cyan", "green", "magenta", "red"),
    "white": ("black", "blue"),
    "red": ("black",),
    "green": ("black", "blue"),
    "yellow": ("black", "blue"),
    "blue": ("white", "yellow", "cyan", "green"),
    "cyan": ("black", "blue"),
    "magenta": ("black",),
}

# (foreground, background): the only pairs that may appear in CSS.
ALLOWED_PAIRS: frozenset[tuple[str, str]] = frozenset(
    (fg, bg) for bg, fgs in _ON.items() for fg in fgs
)

MIN_TEXT_CONTRAST = 4.5
MIN_UI_CONTRAST = 3.0


def _linear(channel: int) -> float:
    c = channel / 255
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def _luminance(hex_colour: str) -> float:
    h = hex_colour.lstrip("#")
    r, g, b = (int(h[i : i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * _linear(r) + 0.7152 * _linear(g) + 0.0722 * _linear(b)


def contrast_ratio(fg: str, bg: str) -> float:
    """WCAG contrast ratio of two `#rrggbb` colours (1.0 to 21.0)."""
    a, b = _luminance(fg), _luminance(bg)
    hi, lo = max(a, b), min(a, b)
    return (hi + 0.05) / (lo + 0.05)
