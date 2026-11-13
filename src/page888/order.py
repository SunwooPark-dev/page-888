"""Dedupe, expiry filter and ordering (R3.7, R4).

Order: severity (most severe first), soonest expiry compared in UTC (absent
last), then id. Remaining fields break ties so the result does not depend on
input order. Only real ids are deduplicated: alerts carrying the missing-id
placeholder are distinct alerts and are never collapsed together.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

from .models import Alert
from .parse import NOT_STATED

_NEVER = datetime.max.replace(tzinfo=timezone.utc)
_EPOCH = datetime.min.replace(tzinfo=timezone.utc)


def _utc(dt: datetime | None, default: datetime) -> datetime:
    return dt.astimezone(timezone.utc) if dt is not None else default


def _sort_key(a: Alert) -> tuple:
    return (a.severity, _utc(a.expires, _NEVER), a.id)


def _full_key(a: Alert) -> tuple:
    """Total order over every field: makes ties (and dedupe choice) input-independent."""
    return (
        _sort_key(a), a.event, a.urgency, a.certainty, a.area_desc, a.headline, a.description,
        a.instruction, _utc(a.onset, _EPOCH), a.onset is None,
        (a.expires is not None, a.expires.utcoffset().total_seconds() if a.expires else 0.0),
        a.sender_name, a.source_url,
    )


def order_alerts(alerts: Iterable[Alert], now: datetime) -> list[Alert]:
    """Drop expired alerts (expiry <= now), dedupe real ids, sort (R4.1-R4.4)."""
    live = [a for a in alerts if a.expires is None or a.expires > now]
    ordered = sorted(live, key=_full_key)
    seen: set[str] = set()
    out: list[Alert] = []
    for a in ordered:
        if a.id != NOT_STATED:
            if a.id in seen:
                continue
            seen.add(a.id)
        out.append(a)
    return out
