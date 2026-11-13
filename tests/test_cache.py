"""Cache and freshness (tasks 10.1; P25, P26, P31; R2.1-R2.2, R2.9, R2.10, R10.3)."""
from __future__ import annotations

import json
import os
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from hypothesis import given, strategies as st

from page888.cache import cache_path, get_data, is_fresh, is_stale, load_cache, store_cache
from page888.config import Config
from page888.fetch import FetchError
from page888.parse import FeedError

NOW = datetime(2026, 11, 13, 14, 0, tzinfo=timezone.utc)
BODY_CA = b'{"features": [{"id": "ca"}]}'
BODY_TX = b'{"features": [{"id": "tx"}]}'
secs = st.integers(-10_000, 10_000)


def cfg(tmp_path: Path, area: str = "CA", **kw) -> Config:
    base = Config(user_agent="t (t@example.invalid)", area=area, min_interval_s=60, stale_after_s=1800,
                  cache_dir=tmp_path / "cache", out_dir=tmp_path / "site")
    return replace(base, **kw)


class Boom(FetchError):
    def __init__(self, msg="down"):
        super().__init__(msg)


def failing(_cfg):
    raise Boom("down")


def test_unexpected_programming_error_is_not_swallowed(tmp_path):
    """Only FetchError/FeedError mean 'fetch failed'; a bug must surface (R2.7)."""
    c = cfg(tmp_path)
    store_cache(c.cache_dir, "CA", BODY_CA, NOW - timedelta(seconds=120))

    def buggy(_c):
        raise KeyError("bug")

    with pytest.raises(KeyError):
        get_data(c, NOW, buggy)


# ---- freshness

@given(secs, st.integers(30, 3600))
def test_prop_is_fresh(age, interval):
    assert is_fresh(NOW - timedelta(seconds=age), NOW, interval) == (0 <= age < interval)


def test_future_fetched_at_never_fresh():
    assert not is_fresh(NOW + timedelta(seconds=1), NOW, 60)


@given(secs, secs, st.integers(1, 5000))
def test_prop_is_stale_monotonic(a, b, threshold):
    lo, hi = sorted((max(a, 0), max(b, 0)))
    s_lo = is_stale(NOW - timedelta(seconds=lo), NOW, threshold)
    s_hi = is_stale(NOW - timedelta(seconds=hi), NOW, threshold)
    assert not s_lo or s_hi  # older data is never fresher
    assert is_stale(NOW - timedelta(seconds=hi), NOW, threshold) == (hi > threshold)


def test_negative_age_is_stale():
    assert is_stale(NOW + timedelta(seconds=1), NOW, 1800)


# ---- storage

def test_roundtrip_and_file_name(tmp_path):
    store_cache(tmp_path, "CA", BODY_CA, NOW)
    assert cache_path(tmp_path, "CA").name == "alerts-CA.json"
    assert load_cache(tmp_path, "CA") == (BODY_CA, NOW)


def test_prop_cache_keyed_by_area(tmp_path):
    store_cache(tmp_path, "CA", BODY_CA, NOW)
    assert load_cache(tmp_path, "TX") is None


def test_entry_area_mismatch_is_no_cache(tmp_path):
    """A CA entry copied to the TX file name is still not TX data."""
    store_cache(tmp_path, "CA", BODY_CA, NOW)
    os.replace(cache_path(tmp_path, "CA"), cache_path(tmp_path, "TX"))
    assert load_cache(tmp_path, "TX") is None


@pytest.mark.parametrize("junk", [b"", b"not json", b"[]", b'{"area": "CA"}', b'{"area":"CA","fetched_at":"x","body":"{}"}',
                                  b'{"area":"CA","fetched_at":"2026-11-13T14:00:00","body":"{}"}'])
def test_corrupt_entry_is_no_cache(tmp_path, junk):
    tmp_path.joinpath("alerts-CA.json").write_bytes(junk)
    assert load_cache(tmp_path, "CA") is None


def test_missing_dir_is_no_cache(tmp_path):
    assert load_cache(tmp_path / "nope", "CA") is None


def test_atomic_write_leaves_old_entry_on_failure(tmp_path, monkeypatch):
    store_cache(tmp_path, "CA", BODY_CA, NOW)

    def broken(*a, **k):
        raise OSError("disk full")

    monkeypatch.setattr(os, "replace", broken)
    with pytest.raises(OSError):
        store_cache(tmp_path, "CA", BODY_TX, NOW + timedelta(minutes=5))
    monkeypatch.undo()
    assert load_cache(tmp_path, "CA") == (BODY_CA, NOW)
    assert [p.name for p in tmp_path.iterdir()] == ["alerts-CA.json"]  # temp file cleaned up


def test_invalid_body_not_stored(tmp_path):
    for bad in (b"not json", b'{"nofeatures": 1}', b"[]"):
        with pytest.raises(FeedError):
            store_cache(tmp_path, "CA", bad, NOW)
    assert not any(tmp_path.glob("*"))


# ---- get_data

def test_fresh_cache_skips_fetch(tmp_path):
    c = cfg(tmp_path)
    store_cache(c.cache_dir, "CA", BODY_CA, NOW - timedelta(seconds=10))
    body, status = get_data(c, NOW, failing)  # would raise if called
    assert body == BODY_CA
    assert (status.stale, status.fallback, status.skipped) == (False, False, 0)
    assert status.fetched_at == NOW - timedelta(seconds=10)


def test_old_cache_triggers_fetch_and_is_replaced(tmp_path):
    c = cfg(tmp_path)
    store_cache(c.cache_dir, "CA", BODY_CA, NOW - timedelta(seconds=120))
    body, status = get_data(c, NOW, lambda _c: BODY_TX)
    assert body == BODY_TX and status.fetched_at == NOW and not status.fallback and not status.stale
    assert load_cache(c.cache_dir, "CA") == (BODY_TX, NOW)


def test_no_cache_fetches_and_stores(tmp_path):
    c = cfg(tmp_path)
    body, status = get_data(c, NOW, lambda _c: BODY_CA)
    assert body == BODY_CA and not status.fallback
    assert load_cache(c.cache_dir, "CA") == (BODY_CA, NOW)


def test_failed_fetch_falls_back_to_cache(tmp_path):
    c = cfg(tmp_path)
    store_cache(c.cache_dir, "CA", BODY_CA, NOW - timedelta(seconds=120))
    body, status = get_data(c, NOW, failing)
    assert body == BODY_CA and status.fallback is True and status.stale is False  # stale from age only


def test_fallback_with_old_cache_is_also_stale(tmp_path):
    c = cfg(tmp_path)
    store_cache(c.cache_dir, "CA", BODY_CA, NOW - timedelta(seconds=1801))
    _, status = get_data(c, NOW, failing)
    assert status.fallback and status.stale


def test_fallback_with_future_fetched_at_is_stale(tmp_path):
    c = cfg(tmp_path)
    store_cache(c.cache_dir, "CA", BODY_CA, NOW + timedelta(hours=1))
    _, status = get_data(c, NOW, failing)
    assert status.fallback and status.stale


def test_no_cache_and_failed_fetch_raises_original_error(tmp_path):
    with pytest.raises(Boom):
        get_data(cfg(tmp_path), NOW, failing)


def test_prop_get_data_never_serves_other_areas_alerts(tmp_path):
    store_cache(tmp_path / "cache", "CA", BODY_CA, NOW - timedelta(seconds=5))
    c = cfg(tmp_path, area="TX")
    with pytest.raises(Boom):
        get_data(c, NOW, failing)  # CA cache is fresh but is not TX's
    body, status = get_data(c, NOW, lambda _c: BODY_TX)
    assert body == BODY_TX and not status.fallback
    assert load_cache(c.cache_dir, "CA") == (BODY_CA, NOW - timedelta(seconds=5))


def test_invalid_fetch_body_not_cached_and_falls_back(tmp_path):
    c = cfg(tmp_path)
    store_cache(c.cache_dir, "CA", BODY_CA, NOW - timedelta(seconds=120))
    body, status = get_data(c, NOW, lambda _c: b"<html>oops</html>")
    assert body == BODY_CA and status.fallback
    assert load_cache(c.cache_dir, "CA") == (BODY_CA, NOW - timedelta(seconds=120))


def test_invalid_fetch_body_without_cache_raises_feed_error(tmp_path):
    with pytest.raises(FeedError):
        get_data(cfg(tmp_path), NOW, lambda _c: b"nope")
    assert not (tmp_path / "cache").exists() or not any((tmp_path / "cache").iterdir())


def test_min_interval_clamp_applies_through_config():
    from page888.config import load_config

    c = load_config({"PAGE888_USER_AGENT": "x (x@example.invalid)", "PAGE888_MIN_INTERVAL_S": "1"})
    assert c.min_interval_s == 30


def test_recorded_fixture_roundtrips_and_other_area_fixture_is_not_served(tmp_path, fixture_bytes):
    ca, tx = fixture_bytes("recorded-CA.json"), fixture_bytes("recorded-TX.json")
    store_cache(tmp_path, "CA", ca, NOW)
    assert load_cache(tmp_path, "CA") == (ca, NOW)
    c = cfg(tmp_path.parent / "other", area="TX", cache_dir=tmp_path)
    body, status = get_data(c, NOW, lambda _c: tx)
    assert body == tx and not status.fallback
    assert load_cache(tmp_path, "CA") == (ca, NOW)
