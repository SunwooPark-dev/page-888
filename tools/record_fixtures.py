#!/usr/bin/env python3
"""Record live NWS responses as test fixtures (the ONLY script that may use the network).

Usage: python3 tools/record_fixtures.py [AREA ...]      (default: CA TX)

Writes tests/fixtures/recorded-<AREA>.json from
  https://api.weather.gov/alerts/active?area=<AREA>&status=actual
and tests/fixtures/http400-status-Actual.json from the HTTP 400 body that
`status=Actual` (capitalised) returns. Recorded feeds are truncated to stay
under MAX_BYTES by dropping trailing features; the recorded top level gets a
`_page888_recorded` note (area, date, original and kept feature counts).
Stdlib only.
"""
from __future__ import annotations

import json
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

USER_AGENT = "Page888 (https://github.com/SunwooPark-dev/page-888)"
BASE = "https://api.weather.gov/alerts/active"
MAX_BYTES = 300_000
FIXTURES = Path(__file__).resolve().parent.parent / "tests" / "fixtures"


def get(url: str) -> tuple[int, bytes]:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/geo+json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


def truncate(doc: dict, max_bytes: int) -> dict:
    """Drop trailing features until the compact JSON fits; return the new doc."""
    feats = list(doc.get("features", []))
    total = len(feats)
    # Geometry is large and unused by Page 888: drop it first.
    for f in feats:
        if isinstance(f, dict):
            f["geometry"] = None
    doc["features"] = feats
    while feats and len(json.dumps(doc, indent=1).encode()) > max_bytes:
        feats.pop()
    doc["_page888_recorded"] = {
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "features_total": total,
        "features_kept": len(feats),
        "note": "geometry removed; trailing features dropped to stay under size limit",
    }
    return doc


def main(areas: list[str]) -> int:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    for area in areas:
        if not re.fullmatch(r"[A-Z]{2}", area):
            print(f"bad area {area!r}", file=sys.stderr)
            return 2
        status, body = get(f"{BASE}?area={area}&status=actual")
        if status != 200:
            print(f"{area}: HTTP {status}", file=sys.stderr)
            return 1
        doc = truncate(json.loads(body), MAX_BYTES)
        out = FIXTURES / f"recorded-{area}.json"
        out.write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8")
        print(f"{out.name}: {doc['_page888_recorded']}")
    status, body = get(f"{BASE}?area={areas[0]}&status=Actual")
    if status != 400:
        print(f"expected HTTP 400 for status=Actual, got {status}", file=sys.stderr)
        return 1
    out = FIXTURES / "http400-status-Actual.json"
    out.write_text(json.dumps(json.loads(body), indent=1) + "\n", encoding="utf-8")
    print(f"{out.name}: recorded HTTP 400 body")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:] or ["CA", "TX"]))
