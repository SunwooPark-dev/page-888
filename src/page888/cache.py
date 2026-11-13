"""Disk cache of the last good feed, keyed by area, and freshness rules (R2, R10.3).

The file is `alerts-<AREA>.json`; the entry also holds the area, so a file
for another area is never used as data for this one (R2.10).
"""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

from .config import Config, valid_area
from .models import DataStatus
from .parse import parse_feed


def cache_path(cache_dir: Path, area: str) -> Path:
    if not valid_area(area):
        raise ValueError(f"invalid area {area!r}")
    return Path(cache_dir) / f"alerts-{area}.json"


def is_fresh(fetched_at: datetime, now: datetime, min_interval_s: int) -> bool:
    """True iff 0 <= age < interval; a future `fetched_at` is never fresh (R2.2)."""
    return timedelta(0) <= now - fetched_at < timedelta(seconds=min_interval_s)


def is_stale(fetched_at: datetime, now: datetime, stale_after_s: int) -> bool:
    """True if age exceeds the threshold, or age is negative (R10.3)."""
    age = now - fetched_at
    return age < timedelta(0) or age > timedelta(seconds=stale_after_s)


def load_cache(cache_dir: Path, area: str) -> tuple[bytes, datetime] | None:
    """The stored (body, fetched_at) for exactly this area, else None (never raises)."""
    try:
        entry = json.loads(cache_path(cache_dir, area).read_text(encoding="utf-8"))
        if not isinstance(entry, dict) or entry.get("area") != area:
            return None
        body, stamp = entry["body"], entry["fetched_at"]
        if not isinstance(body, str) or not isinstance(stamp, str):
            return None
        fetched_at = datetime.fromisoformat(stamp)
        if fetched_at.tzinfo is None or fetched_at.utcoffset() is None:
            return None
        return body.encode("utf-8"), fetched_at
    except (OSError, ValueError, KeyError, UnicodeError):
        return None


def store_cache(cache_dir: Path, area: str, body: bytes, fetched_at: datetime) -> None:
    """Atomically store a validated body. Raises FeedError (nothing written) if it is not a feed."""
    parse_feed(body)
    if fetched_at.tzinfo is None:
        raise ValueError("fetched_at must be timezone-aware")
    path = cache_path(cache_dir, area)
    path.parent.mkdir(parents=True, exist_ok=True)
    entry = {"area": area, "fetched_at": fetched_at.isoformat(), "body": body.decode("utf-8")}
    fd, tmp = tempfile.mkstemp(prefix=".alerts-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(entry, fh)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def get_data(cfg: Config, now: datetime, fetcher: Callable[[Config], bytes]) -> tuple[bytes, DataStatus]:
    """Feed bytes plus status. Fresh cache skips the fetch; a failed or invalid fetch falls back.

    With no usable cache for this area the original fetch error propagates.
    `skipped` is 0 here; the build fills it in after parsing.
    """
    cached = load_cache(cfg.cache_dir, cfg.area)
    if cached and is_fresh(cached[1], now, cfg.min_interval_s):
        body, at = cached
        return body, DataStatus(at, is_stale(at, now, cfg.stale_after_s), False, 0)
    try:
        body = fetcher(cfg)
        store_cache(cfg.cache_dir, cfg.area, body, now)  # validates before writing
    except Exception:
        if cached is None:
            raise
        body, at = cached
        return body, DataStatus(at, is_stale(at, now, cfg.stale_after_s), True, 0)
    return body, DataStatus(now, False, False, 0)
