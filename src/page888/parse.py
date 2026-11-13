"""Parse an NWS alerts feed into `Alert` objects (R1.7, R3).

All functions are total on arbitrary JSON values: API text is untrusted and
fields may be missing, null or of the wrong type. Text is kept as received;
`text.normalise_text` runs later in the pipeline.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlsplit

from .models import Alert, Severity

NOT_STATED = "NOT STATED"
ACTUAL = "Actual"  # value of properties.status in the response (capitalised)

_URGENCY = frozenset({"Immediate", "Expected", "Future", "Past", "Unknown"})
_CERTAINTY = frozenset({"Observed", "Likely", "Possible", "Unlikely", "Unknown"})
_SEVERITY = {s.name.capitalize(): s for s in Severity}


class FeedError(Exception):
    """The response is not a usable alerts feed (invalid JSON or no `features` list)."""


def _text(value: object, default: str = NOT_STATED) -> str:
    """A non-blank string, else `default`."""
    if isinstance(value, str) and value.strip():
        return value
    return default


def _enum(value: object, allowed: frozenset[str]) -> str:
    return value if isinstance(value, str) and value in allowed else "Unknown"


def parse_severity(value: object) -> Severity:
    """Map any value to a Severity; anything unrecognised is UNKNOWN (R3.3)."""
    if isinstance(value, str):
        return _SEVERITY.get(value, Severity.UNKNOWN)
    return Severity.UNKNOWN


def parse_time(value: object) -> datetime | None:
    """ISO-8601 with an explicit offset -> tz-aware datetime (offset kept), else None (R3.4, R3.8)."""
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.strip())
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            return None
        parsed.astimezone(timezone.utc)  # reject values that overflow when converted to UTC
    except (ValueError, OverflowError):
        return None
    return parsed


def https_url_or_empty(value: object) -> str:
    """`value` if it is a safe https URL (R8.2), else ''."""
    if not isinstance(value, str) or not value:
        return ""
    if any(c.isspace() or ord(c) < 32 or ord(c) == 127 for c in value):
        return ""
    try:
        parts = urlsplit(value)
        host = parts.hostname
    except ValueError:
        return ""
    if parts.scheme != "https" or not host:
        return ""
    return value


def parse_alert(feature: object) -> Alert | None:
    """One GeoJSON feature -> Alert. None if unusable or status is not `Actual`. Never raises."""
    if not isinstance(feature, dict):
        return None
    props = feature.get("properties")
    if not isinstance(props, dict):
        return None
    if props.get("status") != ACTUAL:
        return None

    alert_id = _text(props.get("id"), "") or _text(feature.get("id"), NOT_STATED)
    source_url = https_url_or_empty(feature.get("id")) or https_url_or_empty(props.get("@id"))
    expires = parse_time(props.get("expires")) or parse_time(props.get("ends"))

    return Alert(
        id=alert_id,
        event=_text(props.get("event")),
        severity=parse_severity(props.get("severity")),
        urgency=_enum(props.get("urgency"), _URGENCY),
        certainty=_enum(props.get("certainty"), _CERTAINTY),
        area_desc=_text(props.get("areaDesc")),
        headline=_text(props.get("headline")),
        description=_text(props.get("description")),
        instruction=_text(props.get("instruction"), ""),
        onset=parse_time(props.get("onset")),
        expires=expires,
        sender_name=_text(props.get("senderName")),
        source_url=source_url,
    )


def parse_feed(raw: bytes) -> tuple[list[Alert], int]:
    """Parse a response body -> (alerts, skipped).

    `skipped` counts features that are not objects or have no `properties`
    object (R3.5). Alerts dropped for status != Actual are not counted.
    Raises FeedError if the top level is not an object with a `features` list.
    """
    try:
        doc: Any = json.loads(raw)
    except (ValueError, RecursionError) as exc:
        raise FeedError(f"response is not valid JSON: {type(exc).__name__}") from None
    if not isinstance(doc, dict) or not isinstance(doc.get("features"), list):
        raise FeedError("response has no 'features' list")

    alerts: list[Alert] = []
    skipped = 0
    for feature in doc["features"]:
        if not isinstance(feature, dict) or not isinstance(feature.get("properties"), dict):
            skipped += 1
            continue
        alert = parse_alert(feature)
        if alert is not None:
            alerts.append(alert)
    return alerts, skipped
