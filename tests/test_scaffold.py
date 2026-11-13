import json
import socket
import urllib.request

import pytest

from conftest import FIXTURES, NetworkBlocked


def test_network_is_blocked():
    with pytest.raises(NetworkBlocked):
        socket.create_connection(("api.weather.gov", 443), timeout=1)
    with pytest.raises(NetworkBlocked):
        urllib.request.urlopen("https://api.weather.gov/alerts/active", timeout=1)


@pytest.mark.parametrize(
    "name",
    ["normal", "long-instruction", "nulls-wrong-types", "test-status", "hostile-text", "empty",
     "many-alerts", "recorded-CA", "recorded-TX", "http400-status-Actual"],
)
def test_fixture_present_and_valid_json(name):
    path = FIXTURES / f"{name}.json"
    assert path.exists()
    json.loads(path.read_text(encoding="utf-8"))


def test_recorded_fixtures_under_300kb():
    for path in FIXTURES.glob("recorded-*.json"):
        assert path.stat().st_size < 300_000


def test_many_alerts_exceeds_page_range():
    assert len(json.loads((FIXTURES / "many-alerts.json").read_text())["features"]) > 111


def test_http400_fixture_has_enum_and_status():
    body = json.loads((FIXTURES / "http400-status-Actual.json").read_text())
    assert body["status"] == 400
    assert "actual" in json.dumps(body)
