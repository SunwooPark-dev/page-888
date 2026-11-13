"""Palette and contrast (task 8.1; P22, R13.6)."""
from __future__ import annotations

import itertools

from hypothesis import given, strategies as st

from page888.palette import ALLOWED_PAIRS, PALETTE, contrast_ratio

NAMES = sorted(PALETTE)


def test_palette_has_the_eight_colours():
    assert PALETTE == {
        "black": "#000000", "red": "#ff0000", "green": "#00ff00", "yellow": "#ffff00",
        "blue": "#0000ff", "magenta": "#ff00ff", "cyan": "#00ffff", "white": "#ffffff",
    }


def test_prop_palette_contrast():
    """All 64 combinations: in ALLOWED_PAIRS iff ratio >= 4.5."""
    combos = list(itertools.product(NAMES, NAMES))
    assert len(combos) == 64
    for fg, bg in combos:
        ratio = contrast_ratio(PALETTE[fg], PALETTE[bg])
        assert ((fg, bg) in ALLOWED_PAIRS) == (ratio >= 4.5), (fg, bg, ratio)


def test_allowed_pairs_is_the_explicit_twenty():
    expected = {
        "black": {"white", "yellow", "cyan", "green", "magenta", "red"},
        "white": {"black", "blue"},
        "red": {"black"},
        "green": {"black", "blue"},
        "yellow": {"black", "blue"},
        "blue": {"white", "yellow", "cyan", "green"},
        "cyan": {"black", "blue"},
        "magenta": {"black"},
    }
    want = {(fg, bg) for bg, fgs in expected.items() for fg in fgs}
    assert len(want) == 20
    assert ALLOWED_PAIRS == want


def test_spot_checks():
    assert round(contrast_ratio(PALETTE["yellow"], PALETTE["blue"]), 1) == 8.0
    assert round(contrast_ratio(PALETTE["white"], PALETTE["black"]), 1) == 21.0
    assert ("white", "red") not in ALLOWED_PAIRS
    assert contrast_ratio(PALETTE["white"], PALETTE["red"]) < 4.5
    assert ("blue", "black") not in ALLOWED_PAIRS


@given(st.sampled_from(NAMES), st.sampled_from(NAMES))
def test_prop_contrast_symmetric_and_bounded(a, b):
    r = contrast_ratio(PALETTE[a], PALETTE[b])
    assert 1.0 <= r <= 21.0 + 1e-9
    assert abs(r - contrast_ratio(PALETTE[b], PALETTE[a])) < 1e-12
    if a == b:
        assert abs(r - 1.0) < 1e-12
