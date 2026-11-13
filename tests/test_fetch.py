"""Fetch with backoff (task 11.1; R1.3-R1.6, R1.8, R2.4-R2.8). Fake opener/sleep/rng, no network."""
from __future__ import annotations

import io
import json
import random
import urllib.error
from dataclasses import replace
from datetime import datetime, timezone
from email.message import Message
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest
from hypothesis import given, strategies as st

from page888.config import Config
from page888.fetch import FetchError, backoff_ceilings, backoff_delays, fetch_alerts, parse_retry_after

UA = "Test (test@example.invalid)"
NOW = datetime(2026, 11, 13, 14, 0, tzinfo=timezone.utc)
OK_BODY = b'{"features": []}'
CFG = Config(user_agent=UA, area="CA", min_interval_s=60, stale_after_s=1800,
             cache_dir=Path("c"), out_dir=Path("s"))


class Resp:
    def __init__(self, body: bytes = OK_BODY, status: int = 200):
        self._b, self.status = io.BytesIO(body), status

    def read(self, n: int = -1) -> bytes:
        return self._b.read(n)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def http_error(code: int, retry_after: str | None = None, body: bytes = b"{}") -> urllib.error.HTTPError:
    hdrs = Message()
    if retry_after is not None:
        hdrs["Retry-After"] = retry_after
    return urllib.error.HTTPError("https://api.weather.gov/x", code, "err", hdrs, io.BytesIO(body))


class Opener:
    """Plays a script of responses/exceptions and records each call."""

    def __init__(self, *script):
        self.script, self.calls = list(script), []

    def __call__(self, req, timeout=None):
        self.calls.append((req, timeout))
        item = self.script.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item


def run(opener, cfg=CFG, seed=1):
    sleeps: list[float] = []
    out = fetch_alerts(cfg, opener=opener, sleep=sleeps.append, rng=random.Random(seed), clock=lambda: NOW)
    return out, sleeps


# ---- request shape

def test_request_has_ua_lowercase_status_and_area():
    op = Opener(Resp())
    body, _ = run(op)
    assert body == OK_BODY
    req, timeout = op.calls[0]
    assert req.get_header("User-agent") == UA
    url = urlsplit(req.full_url)
    assert (url.scheme, url.netloc, url.path) == ("https", "api.weather.gov", "/alerts/active")
    assert parse_qs(url.query) == {"area": ["CA"], "status": ["actual"]}
    assert "status=Actual" not in req.full_url
    assert timeout == CFG.timeout_s


def test_area_in_url_follows_config_and_never_nationwide():
    op = Opener(Resp())
    run(op, replace(CFG, area="TX"))
    assert "area=TX" in op.calls[0][0].full_url


def test_custom_timeout_passed():
    op = Opener(Resp())
    run(op, replace(CFG, timeout_s=7.5))
    assert op.calls[0][1] == 7.5


# ---- backoff maths

@given(st.integers(1, 12), st.floats(0.1, 10, allow_nan=False), st.floats(0.1, 200, allow_nan=False))
def test_prop_backoff_bounds(n, base, cap):
    ceil = backoff_ceilings(n, base, cap)
    assert len(ceil) == n - 1
    assert all(c <= cap for c in ceil)
    assert all(a <= b for a, b in zip(ceil, ceil[1:]))
    assert all(c == min(cap, base * 2**i) for i, c in enumerate(ceil))
    delays = backoff_delays(ceil, random.Random(0))
    assert len(delays) == len(ceil)
    assert all(0 <= d <= c for d, c in zip(delays, ceil))


def test_default_ceilings():
    assert backoff_ceilings(4, 2.0, 60.0) == [2.0, 4.0, 8.0]


@given(st.integers(0, 10**6))
def test_prop_retry_after_parse(n):
    assert parse_retry_after(str(n), NOW) == float(n)
    assert parse_retry_after(f" {n} ", NOW) == float(n)


@given(st.text(max_size=20))
def test_prop_retry_after_never_raises_and_non_negative(s):
    r = parse_retry_after(s, NOW)
    assert r is None or r >= 0


def test_retry_after_http_date_and_junk():
    assert parse_retry_after("Fri, 13 Nov 2026 14:00:30 GMT", NOW) == 30.0
    assert parse_retry_after("Fri, 13 Nov 2026 13:00:00 GMT", NOW) == 0.0  # past
    for junk in (None, "", "soon", "-5", "1.5", "nan"):
        assert parse_retry_after(junk, NOW) is None


# ---- retry behaviour

@pytest.mark.parametrize("code", [429, 500, 502, 503, 504])
def test_transient_status_retried_up_to_max_attempts(code):
    op = Opener(*[http_error(code) for _ in range(4)])
    with pytest.raises(FetchError) as ei:
        run(op)
    assert len(op.calls) == 4
    assert ei.value.status is None  # transient: not a rejection of the request


def test_sleeps_between_attempts_only_and_within_ceilings():
    op = Opener(*[http_error(503) for _ in range(4)])
    sleeps: list[float] = []
    with pytest.raises(FetchError):
        fetch_alerts(CFG, opener=op, sleep=sleeps.append, rng=random.Random(3), clock=lambda: NOW)
    assert len(sleeps) == 3
    assert all(0 <= s <= c for s, c in zip(sleeps, [2.0, 4.0, 8.0]))


def test_success_after_retry():
    op = Opener(http_error(503), urllib.error.URLError("down"), Resp())
    body, sleeps = run(op)
    assert body == OK_BODY and len(op.calls) == 3 and len(sleeps) == 2


def test_network_errors_retried():
    for exc in (urllib.error.URLError("dns"), TimeoutError("t"), ConnectionResetError("r")):
        op = Opener(exc, Resp())
        body, _ = run(op)
        assert body == OK_BODY and len(op.calls) == 2


def test_404_not_retried():
    op = Opener(http_error(404))
    with pytest.raises(FetchError) as ei:
        run(op)
    assert ei.value.status == 404 and len(op.calls) == 1


def test_recorded_400_raises_fetch_error_400_no_retry(fixture_bytes):
    op = Opener(http_error(400, body=fixture_bytes("http400-status-Actual.json")))
    with pytest.raises(FetchError) as ei:
        run(op)
    assert ei.value.status == 400 and len(op.calls) == 1


def test_retry_after_honoured_as_max_of_header_and_jitter():
    op = Opener(http_error(429, retry_after="30"), Resp())
    _, sleeps = run(op)
    assert sleeps == [30.0]  # jitter ceiling is only 2 s


def test_retry_after_smaller_than_jitter_keeps_jitter():
    op = Opener(http_error(429, retry_after="0"), Resp())
    _, sleeps = run(op)
    assert len(sleeps) == 1 and 0 <= sleeps[0] <= 2.0


def test_retry_after_above_cap_stops_retrying():
    op = Opener(http_error(429, retry_after="61"), Resp())
    sleeps: list[float] = []
    with pytest.raises(FetchError):
        fetch_alerts(CFG, opener=op, sleep=sleeps.append, rng=random.Random(1), clock=lambda: NOW)
    assert len(op.calls) == 1 and sleeps == []


def test_retry_after_equal_to_cap_still_retries():
    op = Opener(http_error(503, retry_after="60"), Resp())
    _, sleeps = run(op)
    assert sleeps == [60.0]


def test_invalid_body_is_returned_for_cache_layer_to_reject():
    """fetch does not parse; get_data/store_cache validate (design section 6)."""
    op = Opener(Resp(b"<html>"))
    body, _ = run(op)
    assert body == b"<html>"


def test_oversized_body_is_a_fetch_error():
    op = Opener(Resp(b"x" * (50 * 1024 * 1024 + 1)))
    with pytest.raises(FetchError):
        run(op)


def test_error_message_has_no_user_agent():
    op = Opener(*[http_error(503) for _ in range(4)])
    with pytest.raises(FetchError) as ei:
        run(op)
    assert UA not in str(ei.value)


def test_non_200_success_status_is_an_error_without_retry_loop_crash():
    op = Opener(Resp(status=204))
    with pytest.raises(FetchError):
        run(op)


# ---- review r1 #1: http.client errors during the body read

import http.client  # noqa: E402


class _BrokenBody(Resp):
    def __init__(self, exc: BaseException):
        super().__init__()
        self._exc = exc

    def read(self, n: int = -1) -> bytes:
        raise self._exc


@pytest.mark.parametrize("exc", [
    http.client.IncompleteRead(b"ab", 10),
    http.client.BadStatusLine("junk"),
    http.client.RemoteDisconnected("closed"),
])
def test_http_client_errors_are_retried_then_raised_as_fetch_error(exc):
    op = Opener(*[_BrokenBody(exc) for _ in range(4)])
    with pytest.raises(FetchError) as ei:
        run(op)
    assert len(op.calls) == 4
    assert ei.value.status is None


def test_incomplete_read_then_success_returns_body():
    op = Opener(_BrokenBody(http.client.IncompleteRead(b"a", 5)), Resp())
    body, sleeps = run(op)
    assert body == OK_BODY and len(op.calls) == 2 and len(sleeps) == 1


def test_fetch_error_message_has_no_user_agent_after_incomplete_read():
    op = Opener(*[_BrokenBody(http.client.IncompleteRead(b"a", 5)) for _ in range(4)])
    with pytest.raises(FetchError) as ei:
        run(op)
    assert UA not in str(ei.value)
