"""Grid and row-budget constants (design section 2.1, R6.10). Constants only."""
from __future__ import annotations

COLS = 40
ROWS = 24
HEADER_ROWS = 1
BODY_ROWS = 13
STATUS_ROWS = 5
NAV_ROWS = 3
FOOTER_ROWS = 2

assert HEADER_ROWS + BODY_ROWS + STATUS_ROWS + NAV_ROWS + FOOTER_ROWS == ROWS

MAX_DOUBLE_HEIGHT_COLS = COLS // 2  # a double-height line fits 20 characters

# Fixed texts (worst cases are checked in tests/test_layout.py).
DATA_AS_OF = "DATA AS OF {stamp} UTC"
STALE_TEXT = "STALE DATA - CHECK WEATHER.GOV"
FALLBACK_TEXT = "LIVE UPDATE FAILED - SHOWING LAST GOOD DATA"
SKIPPED_TEXT = "SKIPPED UNREADABLE ALERTS: {n}"
DISCLAIMER = "NOT AN OFFICIAL WARNING CHANNEL"
FOOTER_INDEX = "CHECK WEATHER.GOV OR LOCAL NWS OFFICE"
FOOTER_OTHER = "SOURCE: US NWS API.WEATHER.GOV"
WEATHER_GOV = "https://www.weather.gov/"
