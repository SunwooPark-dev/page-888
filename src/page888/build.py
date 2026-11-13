"""Build orchestration: fetch -> cache -> parse -> order -> paginate -> render -> verify -> publish.

Exit codes: 0 ok (including stale or fallback), 3 no data and no cache,
4 verification failed, 5 API rejected the request (4xx) and no cache.
(2 for configuration errors is returned by `__main__`.) Codes 3 and 5 publish the
notice site first (R10.8). The User-Agent is never logged.
"""
from __future__ import annotations

import sys
from dataclasses import replace
from datetime import datetime
from typing import Callable

from .cache import get_data
from .config import Config
from .fetch import FetchError, fetch_alerts
from .models import DataStatus
from .order import order_alerts
from .paginate import build_site_model, paginate_notice
from .parse import FeedError, parse_feed
from .publish import publish, recover
from .render import render_site
from .verify import verify_site

EXIT_OK, EXIT_NO_DATA, EXIT_VERIFY, EXIT_REJECTED = 0, 3, 4, 5


def _err(msg: str) -> None:
    print(f"page888: {msg}", file=sys.stderr)


def _publish_notice(cfg: Config, now: datetime) -> bool:
    """Publish the notice site; True if it verified and was published."""
    status = DataStatus(now, False, False, 0)
    files = render_site(paginate_notice(cfg.area, status), status, cfg.area)
    problems = verify_site(files)
    if problems:
        for p in problems:
            _err(f"notice site verification failed: {p}")
        return False
    publish(files, cfg.out_dir)
    return True


def build(cfg: Config, now: datetime, fetcher: Callable[[Config], bytes] = fetch_alerts) -> int:
    """Run one build and return the exit code."""
    recover(cfg.out_dir)
    try:
        raw, status = get_data(cfg, now, fetcher)
        alerts, skipped = parse_feed(raw)
    except (FetchError, FeedError) as exc:
        code = EXIT_REJECTED if isinstance(exc, FetchError) and exc.status is not None else EXIT_NO_DATA
        http = f" (HTTP {exc.status})" if isinstance(exc, FetchError) and exc.status is not None else ""
        _err(f"no data for {cfg.area}{http} and no usable cache: {exc}")
        if not _publish_notice(cfg, now):
            return EXIT_VERIFY
        return code

    status = replace(status, skipped=skipped)
    shown_order = order_alerts(alerts, now)
    files = render_site(build_site_model(shown_order, status, cfg.area), status, cfg.area)
    problems = verify_site(files)
    if problems:
        for p in problems:
            _err(f"verification failed: {p}")
        return EXIT_VERIFY
    publish(files, cfg.out_dir)

    largest = max(len(t.encode("utf-8")) for t in files.values())
    age = int((now - status.fetched_at).total_seconds())
    print(
        f"page888: area={cfg.area} alerts={len(shown_order)} skipped={skipped} pages={len(files)} "
        f"largest_bytes={largest} data_age_s={age} stale={status.stale} fallback={status.fallback}"
    )
    return EXIT_OK
