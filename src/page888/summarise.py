"""Rule-based alert summary (R7). Fixed template, CAP fields only, no runtime LLM.

The summary contains only source values (event, severity, urgency, certainty,
areaDesc, expires, headline) and the fixed words in `FIXED_WORDS`.
"""
from __future__ import annotations

from .models import Alert
from .text import format_time, normalise_text

FIXED_WORDS = (
    "SEVERITY", "URGENCY", "CERTAINTY", "AREA", "MESSAGE", "EXPIRES", "HEADLINE", "NOT STATED",
)


def _field(value: str) -> str:
    """One-line normalised source value; blank becomes NOT STATED."""
    flat = " ".join(normalise_text(value).split())
    return flat or "NOT STATED"


def summarise(a: Alert) -> str:
    """Deterministic, total summary of one alert."""
    parts = [
        f"{_field(a.event)}.",
        f"SEVERITY {a.severity.name}.",
        f"URGENCY {a.urgency.upper()}.",
        f"CERTAINTY {a.certainty.upper()}.",
        f"AREA {_field(a.area_desc)}.",
    ]
    # The message expiry only: the event end is on the DETAILS rows and may be days later.
    if a.message_expires is not None:
        local, utc = format_time(a.message_expires)
        parts.append(f"MESSAGE EXPIRES {local} {utc}.")
    else:
        parts.append("MESSAGE EXPIRES NOT STATED.")
    parts.append(f"HEADLINE {_field(a.headline)}.")
    return " ".join(parts)
