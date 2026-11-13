# Test fixtures

Tests never use the network. Everything here is static.

Recorded from the live NWS API by `tools/record_fixtures.py` (the only script that touches the network):

- `recorded-CA.json`, `recorded-TX.json`: `GET /alerts/active?area=XX&status=actual`. Each feature's `geometry` was set to null (Page 888 does not use it) and the file carries a `_page888_recorded` note with the recording date and feature counts. If a recording ever exceeds 300,000 bytes, trailing features are dropped and the note shows `features_kept` below `features_total`.
- `http400-status-Actual.json`: the HTTP 400 body returned for `status=Actual` (capitalised).

Hand-made (synthetic data, not real alerts): `normal`, `long-instruction`, `nulls-wrong-types`, `test-status`, `hostile-text`, `empty`, and `many-alerts` (130 alerts, more than the 111 pages 889-999).
