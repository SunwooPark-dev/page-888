"""Entry point: `python -m page888`. Configuration comes only from environment variables."""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone

from .build import build
from .config import ConfigError, load_config
from .fetch import fetch_alerts


def main() -> int:
    try:
        cfg = load_config(os.environ)
    except ConfigError as exc:
        print(f"page888: configuration error: {exc}", file=sys.stderr)
        return 2
    return build(cfg, datetime.now(timezone.utc), fetch_alerts)


if __name__ == "__main__":
    sys.exit(main())
