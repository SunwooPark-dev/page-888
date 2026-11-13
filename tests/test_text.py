import unicodedata
from datetime import datetime, timedelta, timezone

from hypothesis import given, strategies as st

from page888.text import ASCII_MAP, format_time, normalise_text, wrap

any_text = st.text(max_size=300)
ws_text = st.text(alphabet=st.sampled_from(list("ab c\n\r\t\u00a0\u00b0\u2014x\x00\x07")), max_size=120)


@given(any_text)
def test_prop_normalise_idempotent_no_control(s):
    out = normalise_text(s)
    assert normalise_text(out) == out
    assert not any(unicodedata.category(c) == "Cc" and c != "\n" for c in out)


@given(any_text)
def test_prop_normalise_ascii_only(s):
    out = normalise_text(s)
    assert all(c == "\n" or 0x20 <= ord(c) <= 0x7E for c in out)


@given(ws_text)
def test_prop_normalise_newlines(s):
    out = normalise_text(s)
    # every surviving newline is part of a run of exactly two (paragraph break)
    import re

    for run in re.findall(r"\n+", out):
        assert run == "\n\n"
    assert not out.startswith(("\n", " ")) and not out.endswith(("\n", " "))


def test_newline_examples():
    assert normalise_text("a\nb") == "a b"
    assert normalise_text("a\n\nb") == "a\n\nb"
    assert normalise_text("a\n\n\n\nb") == "a\n\nb"
    assert normalise_text("a \r\n b") == "a b"
    assert normalise_text("a\r\n\r\nb") == "a\n\nb"


def test_ascii_map_examples():
    assert normalise_text("95\u00b0F") == "95DEGF"
    assert normalise_text("a\u2013b\u2014c") == "a-b-c"
    assert normalise_text("\u201cq\u201d \u2018s\u2019") == "\"q\" 's'"
    assert normalise_text("wait\u2026") == "wait..."
    assert normalise_text("a\u00a0b") == "a b"
    assert normalise_text("caf\u00e9") == "cafe"
    assert normalise_text("\u4e2d") == "?"
    assert normalise_text("a\x00b\x07c") == "abc"
    assert ASCII_MAP["\u00b0"] == "DEG"
    assert all(c.isascii() for v in ASCII_MAP.values() for c in v)


@given(any_text, st.integers(min_value=1, max_value=60))
def test_prop_wrap_width_and_preserves_chars(s, width):
    rows = wrap(s, width)
    assert all(len(r) <= width for r in rows)
    assert "".join("".join(rows).split()) == "".join(s.split())


def test_wrap_examples():
    assert wrap("") == []
    assert wrap("aaa bbb ccc", 7) == ["aaa bbb", "ccc"]
    assert wrap("x" * 85) == ["x" * 40, "x" * 40, "x" * 5]
    assert wrap("ab " + "x" * 45, 40) == ["ab", "x" * 40, "x" * 5]
    assert wrap("one\n\ntwo") == ["one", "", "two"]
    assert wrap("one\ntwo") == ["one two"]


aware = st.datetimes(
    min_value=datetime(1990, 1, 1), max_value=datetime(2100, 1, 1),
    timezones=st.builds(
        lambda m: timezone(timedelta(minutes=m)), st.integers(min_value=-14 * 60, max_value=14 * 60)
    ),
).map(lambda d: d.replace(second=0, microsecond=0))


@given(aware)
def test_prop_format_time_roundtrip(dt):
    local, utc = format_time(dt)
    assert utc.startswith("= ") and utc.endswith(" UTC")
    parsed_local = datetime.fromisoformat(local[:16].replace(" ", "T") + local[17:])
    parsed_utc = datetime.fromisoformat(utc[2:18].replace(" ", "T") + "+00:00")
    assert parsed_local == dt == parsed_utc
    assert len(local) == len("2026-11-13 14:00 -08:00")


def test_format_time_example():
    dt = datetime(2026, 11, 13, 14, 0, tzinfo=timezone(timedelta(hours=-8)))
    assert format_time(dt) == ("2026-11-13 14:00 -08:00", "= 2026-11-13 22:00 UTC")
