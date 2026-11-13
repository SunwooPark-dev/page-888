"""Data models shared across the pipeline (design section 2). Times are tz-aware."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import IntEnum


class Severity(IntEnum):
    """Lower value = more severe (usable as a sort key)."""

    EXTREME = 0
    SEVERE = 1
    MODERATE = 2
    MINOR = 3
    UNKNOWN = 4


@dataclass(frozen=True)
class Alert:
    id: str
    event: str
    severity: Severity
    urgency: str  # Immediate|Expected|Future|Past|Unknown
    certainty: str  # Observed|Likely|Possible|Unlikely|Unknown
    area_desc: str
    headline: str
    description: str
    instruction: str  # "" when absent
    onset: datetime | None  # tz-aware, source offset kept (R3.8)
    expires: datetime | None  # tz-aware, source offset kept; falls back to `ends`
    sender_name: str
    source_url: str  # "" unless it passes the https check (R8.2)


@dataclass(frozen=True)
class Row:
    text: str  # <= 40 code points, ASCII
    gap_before: bool = False  # one CSS gap row before this row; counts as a row
    label: bool = False  # section label (rendered as h2)
    href: str = ""  # relative page link or https URL; "" for plain text


@dataclass(frozen=True)
class SubPage:
    number: int  # 3-digit page number, 888..999
    k: int  # 1-based
    total: int  # number of sub-pages of this page
    title: str  # h1 text
    body: tuple[Row, ...]  # rows plus gaps <= BODY_ROWS
    double_height_title: bool


@dataclass(frozen=True)
class Page:
    """A logical page: its ordered sub-pages."""

    number: int
    kind: str  # "index" | "alert" | "notice"
    subpages: tuple[SubPage, ...]
    alert_id: str | None


@dataclass(frozen=True)
class DataStatus:
    fetched_at: datetime
    stale: bool  # from age only (R10.3); also true if fetched_at is in the future
    fallback: bool  # fetch failed, cache used (independent of stale)
    skipped: int
