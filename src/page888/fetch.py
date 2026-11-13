"""HTTP fetch of the active-alerts feed with retry and backoff (R1.3-R1.6, R1.8, R2.4-R2.8).

Only this module (with `cache` and `publish`) talks to the network. The opener,
sleep, RNG and clock are injectable so every path is testable offline. The
User-Agent is sent but never included in an error message.
"""
from __future__ import annotations

import random
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Callable, Sequence

from .config import Config

ENDPOINT = "https://api.weather.gov/alerts/active"
MAX_BODY_BYTES = 32 * 1024 * 1024
_TRANSIENT = frozenset({429, 500, 502, 503, 504})


class FetchError(Exception):
    """The fetch failed. `status` is the HTTP status for a rejected request (4xx other than 429), else None."""

    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


def backoff_ceilings(max_attempts: int, base: float, cap: float) -> list[float]:
    """Delay ceilings between attempts: min(cap, base*2**n) for each of max_attempts-1 gaps."""
    return [min(cap, base * 2**n) for n in range(max(0, max_attempts - 1))]


def backoff_delays(ceilings: Sequence[float], rng: random.Random) -> list[float]:
    """Full jitter: one delay in [0, ceiling] per ceiling."""
    return [rng.uniform(0, c) for c in ceilings]


def parse_retry_after(value: str | None, now: datetime) -> float | None:
    """Seconds to wait from a Retry-After header (delta-seconds or HTTP-date); None if absent or unusable."""
    if not isinstance(value, str):
        return None
    v = value.strip()
    if re.fullmatch(r"[0-9]{1,9}", v, re.ASCII):
        return float(int(v))
    if not v or not re.search(r"[A-Za-z]", v):
        return None
    try:
        when = parsedate_to_datetime(v)
    except (TypeError, ValueError, IndexError, OverflowError):
        return None
    if when is None or when.tzinfo is None:
        return None
    return max(0.0, (when - now).total_seconds())


def build_url(area: str) -> str:
    # `status=actual` must be lowercase: `Actual` is rejected with HTTP 400 (design section 6).
    return ENDPOINT + "?" + urllib.parse.urlencode({"area": area, "status": "actual"})


def fetch_alerts(
    cfg: Config,
    opener: Callable[..., Any] = urllib.request.urlopen,
    sleep: Callable[[float], None] = time.sleep,
    rng: random.Random | None = None,
    clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
) -> bytes:
    """GET the feed for `cfg.area`; retry 429/5xx/network errors; raise FetchError when giving up.

    Returns the raw body unparsed (the cache layer validates it).
    """
    rng = rng or random.Random()
    req = urllib.request.Request(
        build_url(cfg.area),
        headers={"User-Agent": cfg.user_agent, "Accept": "application/geo+json"},
    )
    delays = backoff_delays(backoff_ceilings(cfg.max_attempts, cfg.base_delay_s, cfg.max_delay_s), rng)
    last = "no attempt made"
    for attempt in range(max(1, cfg.max_attempts)):
        retry_after: float | None = None
        try:
            with opener(req, timeout=cfg.timeout_s) as resp:
                if getattr(resp, "status", 200) != 200:
                    raise FetchError(f"unexpected HTTP status {resp.status}")
                body = resp.read(MAX_BODY_BYTES + 1)
            if len(body) > MAX_BODY_BYTES:
                raise FetchError("response too large")
            return body
        except FetchError:
            raise
        except urllib.error.HTTPError as exc:
            code = exc.code
            if code not in _TRANSIENT:
                if 400 <= code < 500:
                    raise FetchError(f"HTTP {code} for area {cfg.area}", status=code) from None
                raise FetchError(f"HTTP {code}") from None
            last = f"HTTP {code}"
            retry_after = parse_retry_after(exc.headers.get("Retry-After") if exc.headers else None, clock())
            if retry_after is not None and retry_after > cfg.max_delay_s:
                raise FetchError(f"{last}; Retry-After {retry_after:.0f}s exceeds the {cfg.max_delay_s:.0f}s cap") from None
        except (urllib.error.URLError, OSError) as exc:  # URLError and TimeoutError are OSErrors
            last = f"network error ({type(exc).__name__})"
        if attempt < len(delays):
            sleep(max(retry_after or 0.0, delays[attempt]))
    raise FetchError(f"giving up after {cfg.max_attempts} attempts: {last}")
