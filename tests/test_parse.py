import json
from datetime import datetime, timedelta, timezone

import pytest
from hypothesis import given, strategies as st

from page888.models import Alert, Severity
from page888.parse import (
    NOT_STATED,
    FeedError,
    https_url_or_empty,
    parse_alert,
    parse_feed,
    parse_severity,
    parse_time,
)

json_values = st.recursive(
    st.none() | st.booleans() | st.integers() | st.floats(allow_nan=True) | st.text(),
    lambda c: st.lists(c, max_size=4) | st.dictionaries(st.text(max_size=12), c, max_size=6),
    max_leaves=20,
)
PROP_KEYS = ["id", "event", "severity", "urgency", "certainty", "areaDesc", "headline", "description",
             "instruction", "onset", "expires", "ends", "senderName", "status", "@id"]
features = st.fixed_dictionaries(
    {"properties": st.dictionaries(st.sampled_from(PROP_KEYS), json_values, max_size=10)},
    optional={"id": json_values},
)


@given(json_values)
def test_prop_parse_never_raises(value):
    result = parse_alert(value)
    assert result is None or isinstance(result, Alert)


@given(features)
def test_prop_parse_never_raises_on_featurelike(value):
    result = parse_alert(value)
    assert result is None or isinstance(result, Alert)
    if result is not None:
        # only Actual alerts survive (R1.7), with every text field a str
        assert value["properties"]["status"] == "Actual"
        for name in ("id", "event", "urgency", "certainty", "area_desc", "headline", "description",
                     "instruction", "sender_name", "source_url"):
            assert isinstance(getattr(result, name), str)
        assert isinstance(result.severity, Severity)


@given(json_values)
def test_prop_severity_total(value):
    assert isinstance(parse_severity(value), Severity)


@pytest.mark.parametrize("name,sev", [("Extreme", Severity.EXTREME), ("Severe", Severity.SEVERE),
                                      ("Moderate", Severity.MODERATE), ("Minor", Severity.MINOR),
                                      ("Unknown", Severity.UNKNOWN)])
def test_severity_known_values(name, sev):
    assert parse_severity(name) is sev


@pytest.mark.parametrize("v", ["extreme", "EXTREME", "Catastrophic", "", None, 3, ["Severe"], True])
def test_severity_other_values_are_unknown(v):
    assert parse_severity(v) is Severity.UNKNOWN


@given(json_values)
def test_prop_parse_time(value):
    t = parse_time(value)
    assert t is None or (t.tzinfo is not None and t.utcoffset() is not None)


@given(st.datetimes(min_value=datetime(1900, 1, 1), max_value=datetime(2100, 1, 1)))
def test_prop_parse_time_no_offset_is_none(naive):
    assert parse_time(naive.isoformat()) is None


@given(st.datetimes(min_value=datetime(1900, 1, 1), max_value=datetime(2100, 1, 1)),
       st.integers(min_value=-14 * 60, max_value=14 * 60))
def test_prop_parse_time_keeps_offset_and_instant(naive, minutes):
    aware = naive.replace(tzinfo=timezone(timedelta(minutes=minutes)))
    parsed = parse_time(aware.isoformat())
    assert parsed == aware
    assert parsed.utcoffset() == aware.utcoffset()


def test_parse_time_z_and_garbage():
    assert parse_time("2026-11-13T18:00:00Z") == datetime(2026, 11, 13, 18, tzinfo=timezone.utc)
    for bad in ["", "yesterday", "2026-11-13", "2026-13-45T00:00:00+00:00", None, 5, "9999-12-31T23:59:59-23:59"]:
        assert parse_time(bad) is None


def _feat(**props):
    base = {"id": "urn:x", "status": "Actual", "severity": "Severe", "event": "Flood Warning"}
    base.update(props)
    return {"id": "https://api.weather.gov/alerts/urn:x", "properties": base}


def test_status_other_than_actual_is_dropped():
    for status in ["Test", "Exercise", "actual", "ACTUAL", None, 1, "System", "Draft"]:
        assert parse_alert(_feat(status=status)) is None
    assert parse_alert(_feat()) is not None


def test_missing_fields_get_placeholders():
    a = parse_alert({"properties": {"status": "Actual"}})
    assert a is not None
    assert a.event == a.headline == a.description == a.area_desc == a.sender_name == NOT_STATED
    assert a.id == NOT_STATED
    assert a.instruction == ""
    assert a.severity is Severity.UNKNOWN
    assert a.urgency == a.certainty == "Unknown"
    assert a.onset is None and a.expires is None and a.source_url == ""


def test_blank_strings_are_placeholders():
    a = parse_alert(_feat(event="   ", headline="", description="\n"))
    assert a.event == a.headline == a.description == NOT_STATED


def test_urgency_and_certainty_validated():
    a = parse_alert(_feat(urgency="Immediate", certainty="Observed"))
    assert (a.urgency, a.certainty) == ("Immediate", "Observed")
    a = parse_alert(_feat(urgency="Whenever", certainty=5))
    assert (a.urgency, a.certainty) == ("Unknown", "Unknown")


def test_expires_falls_back_to_ends():
    ends = "2026-11-14T09:00:00-05:00"
    a = parse_alert(_feat(expires=None, ends=ends))
    assert a.expires == parse_time(ends)
    a = parse_alert(_feat(expires="garbage", ends=ends))
    assert a.expires == parse_time(ends)
    exp = "2026-11-13T18:00:00-05:00"
    assert parse_alert(_feat(expires=exp, ends=ends)).expires == parse_time(exp)
    assert parse_alert(_feat(expires=None, ends=None)).expires is None


def test_expires_without_offset_is_absent():
    assert parse_alert(_feat(expires="2026-11-13T18:00:00")).expires is None


def test_id_prefers_properties_then_feature():
    assert parse_alert(_feat(id="urn:abc")).id == "urn:abc"
    f = _feat(id=None)
    f["id"] = "feature-id"
    assert parse_alert(f).id == "feature-id"


@pytest.mark.parametrize("url,ok", [
    ("https://api.weather.gov/alerts/urn:x", True),
    ("http://api.weather.gov/x", False),
    ("javascript:alert(1)", False),
    ("https://", False),
    ("https:///path", False),
    ("https://example.com/a b", False),
    ("https://example.com/a\tb", False),
    ("https://example.com/\x00", False),
    ("https://example.com/\u2028", False),
    ("https://example.com/\x7f", False),
    ("//example.com/x", False),
    ("https://[::1/x", False),
    ("", False), (None, False), (5, False),
])
def test_https_url_check(url, ok):
    assert (https_url_or_empty(url) != "") is ok
    if ok:
        assert https_url_or_empty(url) == url


@given(json_values)
def test_prop_https_url_total_and_safe(value):
    out = https_url_or_empty(value)
    assert isinstance(out, str)
    if out:
        assert out.startswith("https://")
        assert not any(c.isspace() or ord(c) < 32 or ord(c) == 127 for c in out)


def test_source_url_from_feature_id_then_properties_at_id():
    assert parse_alert(_feat()).source_url == "https://api.weather.gov/alerts/urn:x"
    f = _feat(**{"@id": "https://api.weather.gov/alerts/other"})
    f["id"] = "javascript:alert(1)"
    assert parse_alert(f).source_url == "https://api.weather.gov/alerts/other"


# ---- parse_feed ----

def test_feed_invalid_top_level_raises():
    for raw in [b"", b"not json", b"[]", b"7", b"null", b'{"type":"x"}', b'{"features": {}}',
                b'{"features": null}', b"\xff\xfe", b'{"features": "x"}']:
        with pytest.raises(FeedError):
            parse_feed(raw)


@given(st.binary(max_size=200))
def test_prop_parse_feed_only_raises_feederror(raw):
    try:
        alerts, skipped = parse_feed(raw)
    except FeedError:
        return
    assert skipped >= 0 and all(isinstance(a, Alert) for a in alerts)


def test_feed_empty_fixture(fixture_bytes):
    assert parse_feed(fixture_bytes("empty.json")) == ([], 0)


def test_feed_normal_fixture(fixture_bytes):
    alerts, skipped = parse_feed(fixture_bytes("normal.json"))
    assert skipped == 0 and len(alerts) == 3
    assert {a.severity for a in alerts} == {Severity.SEVERE, Severity.EXTREME, Severity.MINOR}
    third = next(a for a in alerts if a.event == "Frost Advisory")
    assert third.instruction == "" and third.expires == parse_time("2026-11-14T09:00:00-05:00")
    assert all(a.onset is not None and a.onset.tzinfo for a in alerts)


def test_feed_drops_test_status_without_counting_skipped(fixture_bytes):
    alerts, skipped = parse_feed(fixture_bytes("test-status.json"))
    assert [a.id for a in alerts] == ["urn:oid:test.3"]
    assert skipped == 0


def test_feed_nulls_wrong_types_counts_skipped(fixture_bytes):
    alerts, skipped = parse_feed(fixture_bytes("nulls-wrong-types.json"))
    # 2 usable Actual alerts with junk fields + the one with offset-less expires + feat(9)
    assert len(alerts) == 4
    # no/None/str properties plus four non-object features: 7 skipped
    assert skipped == 7
    assert alerts[0].event == NOT_STATED and alerts[0].severity is Severity.UNKNOWN
    assert alerts[1].id == "42" or alerts[1].id == NOT_STATED  # wrong-typed id never raises
    assert alerts[2].expires is None


def test_feed_hostile_fixture_is_kept_verbatim_and_bad_urls_removed(fixture_bytes):
    alerts, skipped = parse_feed(fixture_bytes("hostile-text.json"))
    assert skipped == 0 and len(alerts) == 2
    assert alerts[0].event == "<script>alert(1)</script>"  # escaping is render's job
    assert alerts[1].source_url == ""


def test_feed_many_fixture(fixture_bytes):
    alerts, skipped = parse_feed(fixture_bytes("many-alerts.json"))
    assert len(alerts) == 130 and skipped == 0


@pytest.mark.parametrize("name,minimum", [("recorded-CA.json", 40), ("recorded-TX.json", 1)])
def test_feed_recorded(fixture_bytes, name, minimum):
    alerts, skipped = parse_feed(fixture_bytes(name))
    assert len(alerts) >= minimum and skipped == 0
    assert all(a.source_url.startswith("https://") for a in alerts)
    assert all(a.expires is None or a.expires.tzinfo for a in alerts)


def test_feed_http400_body_is_not_a_feed(fixture_bytes):
    with pytest.raises(FeedError):
        parse_feed(fixture_bytes("http400-status-Actual.json"))


def test_feed_accepts_str_or_bytes_json():
    raw = json.dumps({"features": [_feat()]}).encode()
    assert len(parse_feed(raw)[0]) == 1


def test_ends_and_message_expiry_are_parsed_separately():
    exp, ends = "2026-11-13T18:00:00-08:00", "2026-11-17T04:00:00-08:00"
    a = parse_alert(_feat(expires=exp, ends=ends))
    assert a.message_expires == parse_time(exp) and a.ends == parse_time(ends)
    assert a.expires == parse_time(exp)  # ordering and filtering still use the message expiry first
    a = parse_alert(_feat(expires=None, ends=ends))
    assert a.message_expires is None and a.ends == parse_time(ends) and a.expires == parse_time(ends)
    a = parse_alert(_feat(expires=exp, ends=None))
    assert a.ends is None and a.message_expires == parse_time(exp)
    assert parse_alert(_feat(ends="2026-11-17T04:00:00")).ends is None
