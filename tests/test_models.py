import dataclasses

import pytest

from page888.models import Alert, DataStatus, Page, Row, Severity, SubPage


def test_severity_order_is_most_severe_first():
    assert sorted(Severity, reverse=True)[0] is Severity.UNKNOWN
    assert [s.name for s in sorted(Severity)] == ["EXTREME", "SEVERE", "MODERATE", "MINOR", "UNKNOWN"]


def test_models_are_frozen():
    row = Row("X")
    assert row.gap_before is False
    with pytest.raises(dataclasses.FrozenInstanceError):
        row.text = "Y"  # type: ignore[misc]


def test_model_fields_match_design():
    names = lambda c: [f.name for f in dataclasses.fields(c)]  # noqa: E731
    assert names(Alert) == [
        "id", "event", "severity", "urgency", "certainty", "area_desc", "headline", "description",
        "instruction", "onset", "expires", "sender_name", "source_url", "ends", "message_expires",
    ]
    assert names(SubPage) == ["number", "k", "total", "title", "body", "double_height_title"]
    assert names(Page) == ["number", "kind", "subpages", "alert_id"]
    assert names(DataStatus) == ["fetched_at", "stale", "fallback", "skipped"]
