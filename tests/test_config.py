import string
from pathlib import Path

import pytest
from hypothesis import given, strategies as st

from page888.config import Config, ConfigError, load_config, valid_area

UA = "Page888 test (https://example.invalid/contact)"


def env(**kw):
    base = {"PAGE888_USER_AGENT": UA, "PAGE888_AREA": "CA"}
    base.update(kw)
    return {k: v for k, v in base.items() if v is not None}


@pytest.mark.parametrize("ua", [None, "", " ", "\t\n", "bad\r\nX-Injected: 1", "nul\x00"])
def test_user_agent_unset_blank_or_unsafe_raises(ua):
    with pytest.raises(ConfigError) as ei:
        load_config(env(PAGE888_USER_AGENT=ua))
    assert "PAGE888_USER_AGENT" in str(ei.value)


def test_user_agent_is_trimmed_and_kept():
    assert load_config(env(PAGE888_USER_AGENT=f"  {UA}  ")).user_agent == UA


@given(st.text())
def test_prop_valid_area(code):
    import re
    assert valid_area(code) == (re.fullmatch(r"[A-Z]{2}", code, re.ASCII) is not None)


@given(st.from_regex(r"[A-Z]{2}", fullmatch=True))
def test_prop_valid_area_accepts_two_capitals(code):
    assert valid_area(code)
    assert load_config(env(PAGE888_AREA=code)).area == code


@pytest.mark.parametrize("bad", ["ca", "C", "CAL", "C1", "", " CA", "CA\n", "\u00c7A", "C A", "CA "])
def test_bad_area_raises_without_normalising(bad):
    assert not valid_area(bad)
    with pytest.raises(ConfigError) as ei:
        load_config(env(PAGE888_AREA=bad))
    assert "PAGE888_AREA" in str(ei.value)


def test_valid_area_rejects_non_str():
    assert not valid_area(None)  # type: ignore[arg-type]
    assert not valid_area(12)  # type: ignore[arg-type]


def test_defaults():
    cfg = load_config({"PAGE888_USER_AGENT": UA})
    assert isinstance(cfg, Config)
    assert cfg.area == "CA"
    assert cfg.max_attempts == 4
    assert cfg.base_delay_s == 2.0
    assert cfg.max_delay_s == 60.0
    assert cfg.timeout_s == 20.0
    assert cfg.min_interval_s == 60
    assert cfg.stale_after_s == 1800
    assert cfg.out_dir == Path("site")
    assert cfg.cache_dir == Path(".cache")


def test_out_and_cache_env():
    cfg = load_config(env(PAGE888_OUT="out", PAGE888_CACHE_DIR="/tmp/c"))
    assert cfg.out_dir == Path("out") and cfg.cache_dir == Path("/tmp/c")


@given(st.integers(min_value=-10_000, max_value=10_000))
def test_prop_interval_clamped_to_30(n):
    cfg = load_config(env(PAGE888_MIN_INTERVAL_S=str(n)))
    assert cfg.min_interval_s == max(30, n)


@pytest.mark.parametrize("var", ["PAGE888_MIN_INTERVAL_S", "PAGE888_STALE_AFTER_S"])
@pytest.mark.parametrize("bad", ["abc", "1.5", "", "1e3"])
def test_non_integer_numbers_raise(var, bad):
    with pytest.raises(ConfigError) as ei:
        load_config(env(**{var: bad}))
    assert var in str(ei.value)


def test_stale_after_must_be_positive():
    with pytest.raises(ConfigError):
        load_config(env(PAGE888_STALE_AFTER_S="0"))
    assert load_config(env(PAGE888_STALE_AFTER_S="600")).stale_after_s == 600


def test_config_repr_does_not_leak_user_agent():
    assert UA not in repr(load_config(env()))


def test_config_is_frozen():
    with pytest.raises(Exception):
        load_config(env()).area = "TX"  # type: ignore[misc]
