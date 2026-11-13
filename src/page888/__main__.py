"""Entry point: `python -m page888`.

Only configuration is wired so far (tasks 1-3). The build pipeline (task 13)
is not implemented yet, so a valid configuration exits 1 with a message.
"""
from __future__ import annotations

import os
import sys

from .config import ConfigError, load_config


def main() -> int:
    try:
        load_config(os.environ)
    except ConfigError as exc:
        print(f"page888: configuration error: {exc}", file=sys.stderr)
        return 2
    print("page888: build pipeline not implemented yet", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
