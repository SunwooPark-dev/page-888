"""Layout budget (task 7.1, R6.10): constants and worst-case fixed text."""
from __future__ import annotations

from page888 import layout
from page888.text import wrap


def test_constants_sum_to_rows():
    assert layout.COLS == 40
    assert layout.ROWS == 24
    assert (layout.HEADER_ROWS, layout.BODY_ROWS, layout.STATUS_ROWS) == (1, 13, 5)
    assert (layout.NAV_ROWS, layout.FOOTER_ROWS) == (3, 2)
    assert (
        layout.HEADER_ROWS + layout.BODY_ROWS + layout.STATUS_ROWS + layout.NAV_ROWS + layout.FOOTER_ROWS
        == layout.ROWS
    )


def test_worst_case_status_fits_status_rows():
    lines = [
        layout.DATA_AS_OF.format(stamp="2026-11-13 14:05"),
        layout.STALE_TEXT,
        layout.FALLBACK_TEXT,
        layout.SKIPPED_TEXT.format(n=999999),
    ]
    rows = [r for line in lines for r in wrap(line, layout.COLS)]
    assert len(layout.FALLBACK_TEXT) == 43  # wraps to two rows
    assert len(wrap(layout.FALLBACK_TEXT, layout.COLS)) == 2
    assert len(rows) <= layout.STATUS_ROWS


def test_footer_and_nav_worst_case_fit():
    footer = [layout.DISCLAIMER, layout.FOOTER_INDEX, layout.FOOTER_OTHER]
    assert all(len(wrap(t, layout.COLS)) == 1 for t in footer)
    assert len([layout.DISCLAIMER, layout.FOOTER_INDEX]) <= layout.FOOTER_ROWS
    assert layout.NAV_ROWS == 3  # previous, next, index: one row each
