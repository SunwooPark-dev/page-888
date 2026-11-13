from datetime import datetime, timezone

from hypothesis import given, strategies as st

from page888.models import Alert, Severity
from page888.parse import parse_alert
from page888.summarise import FIXED_WORDS, summarise
from page888.text import format_time, normalise_text

texts = st.text(max_size=60)
times = st.none() | st.datetimes(timezones=st.just(timezone.utc),
                                 min_value=datetime(2000, 1, 1), max_value=datetime(2100, 1, 1))
alerts = st.builds(
    Alert,
    id=texts, event=texts, severity=st.sampled_from(list(Severity)),
    urgency=st.sampled_from(["Immediate", "Expected", "Future", "Past", "Unknown"]),
    certainty=st.sampled_from(["Observed", "Likely", "Possible", "Unlikely", "Unknown"]),
    area_desc=texts, headline=texts, description=texts, instruction=texts,
    onset=times, expires=times, sender_name=texts, source_url=texts,
)


@given(alerts)
def test_prop_summary_total_deterministic(a):
    s = summarise(a)
    assert isinstance(s, str) and s
    assert s == summarise(a)


@given(alerts)
def test_prop_summary_has_severity_urgency_certainty(a):
    s = summarise(a).upper()
    assert a.severity.name in s
    assert a.urgency.upper() in s
    assert a.certainty.upper() in s


lower = st.text(alphabet="abcdefghij ", max_size=40)  # disjoint from the UPPERCASE fixed words


@given(alerts, lower, lower, lower, lower)
def test_prop_summary_only_fields_and_fixed_words(a, event, area, headline, _unused):
    a = Alert(**{**a.__dict__, "event": event, "area_desc": area, "headline": headline})
    rest = summarise(a)
    # fixed words and uppercase enum words first, then the source values
    fixed = list(FIXED_WORDS) + [a.severity.name, a.urgency.upper(), a.certainty.upper()]
    for w in sorted(fixed, key=len, reverse=True):
        rest = rest.replace(w, "")
    if a.expires:
        for t in format_time(a.expires):
            rest = rest.replace(t, "")
    for p in sorted((normalise_text(x) for x in (event, area, headline)), key=len, reverse=True):
        if p:
            rest = rest.replace(p, "")
    assert not [c for c in rest if c.isalnum()], rest


def test_all_fields_missing():
    a = parse_alert({"properties": {"status": "Actual"}})
    s = summarise(a)
    assert "SEVERITY" in s and "UNKNOWN" in s


def test_example():
    a = parse_alert({"properties": {
        "status": "Actual", "event": "Flood Warning", "severity": "Severe", "urgency": "Expected",
        "certainty": "Likely", "areaDesc": "Kern County", "headline": "Flood Warning issued",
        "expires": "2026-11-13T14:00:00-08:00"}})
    s = summarise(a)
    for needle in ("Flood Warning", "SEVERE", "EXPECTED", "LIKELY", "Kern County", "2026-11-13 14:00 -08:00"):
        assert needle in s
