"""Configuration from environment variables (R1.1-R1.3, R1.5, R2.3, R2.12)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping

ENV_USER_AGENT = "PAGE888_USER_AGENT"
ENV_AREA = "PAGE888_AREA"
ENV_OUT = "PAGE888_OUT"
ENV_CACHE_DIR = "PAGE888_CACHE_DIR"
ENV_MIN_INTERVAL = "PAGE888_MIN_INTERVAL_S"
ENV_STALE_AFTER = "PAGE888_STALE_AFTER_S"

DEFAULT_AREA = "CA"
DEFAULT_MIN_INTERVAL_S = 60
MIN_INTERVAL_FLOOR_S = 30  # R2.2/R2.3: never configurable below this
DEFAULT_STALE_AFTER_S = 30 * 60  # R10.3

_AREA_RE = re.compile(r"[A-Z]{2}", re.ASCII)


class ConfigError(Exception):
    """Invalid or missing configuration (exit code 2)."""


@dataclass(frozen=True)
class Config:
    # repr=False: the User-Agent may contain contact details and must not be logged.
    user_agent: str = field(repr=False)
    area: str
    min_interval_s: int
    stale_after_s: int
    cache_dir: Path
    out_dir: Path
    max_attempts: int = 4
    base_delay_s: float = 2.0
    max_delay_s: float = 60.0
    timeout_s: float = 20.0


def valid_area(code: str) -> bool:
    """True exactly for two uppercase ASCII letters (R1.5)."""
    return isinstance(code, str) and _AREA_RE.fullmatch(code) is not None


def _int_env(env: Mapping[str, str], name: str, default: int) -> int:
    raw = env.get(name)
    if raw is None:
        return default
    if not re.fullmatch(r"-?[0-9]+", raw.strip(), re.ASCII):
        raise ConfigError(f"{name} must be a whole number of seconds, got {raw!r}")
    return int(raw)


def load_config(env: Mapping[str, str]) -> Config:
    """Build a Config from `env`; raises ConfigError before any network use."""
    ua = (env.get(ENV_USER_AGENT) or "").strip()
    if not ua:
        raise ConfigError(f"{ENV_USER_AGENT} is not set; set it to a descriptive User-Agent with contact info")
    if any(ord(c) < 32 or ord(c) == 127 for c in ua):
        raise ConfigError(f"{ENV_USER_AGENT} must not contain control characters")

    area = env.get(ENV_AREA, DEFAULT_AREA)
    if not valid_area(area):
        raise ConfigError(f"{ENV_AREA} must be two uppercase letters (for example CA), got {area!r}")

    interval = max(MIN_INTERVAL_FLOOR_S, _int_env(env, ENV_MIN_INTERVAL, DEFAULT_MIN_INTERVAL_S))
    stale_after = _int_env(env, ENV_STALE_AFTER, DEFAULT_STALE_AFTER_S)
    if stale_after <= 0:
        raise ConfigError(f"{ENV_STALE_AFTER} must be greater than zero")

    return Config(
        user_agent=ua,
        area=area,
        min_interval_s=interval,
        stale_after_s=stale_after,
        cache_dir=Path(env.get(ENV_CACHE_DIR) or ".cache"),
        out_dir=Path(env.get(ENV_OUT) or "site"),
    )
