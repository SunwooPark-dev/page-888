# Checks

Results of automated checks run on 2026-11-13 in the project `.venv` (Python 3.13.5 in the venv; the workflow is set to 3.12, which has not been run here). Numbers below were measured in that run.

## Automated

| Check | Result |
|---|---|
| `pytest -q` | 358 passed |
| `pytest -q -k prop` | 91 passed, 267 deselected |
| Network use in tests | blocked by a socket guard in `tests/conftest.py` |

## Generated sites

Fixture builds used a fake fetcher that returns a fixture file (offline); the live build used `python -m page888` with `PAGE888_AREA=CA`.

| Source | Alerts | Files | Largest page (bytes) | `check_pages.py site --strict` |
|---|---|---|---|---|
| `recorded-CA.json` (recorded live data) | 47 | 335 | 2,592 | 0 failed |
| `many-alerts.json` (130 synthetic alerts) | 130 | 353 | 2,558 | 0 failed |
| `normal.json` | 2 | 8 | 2,256 | 0 failed |
| `empty.json` | 0 | 2 | 1,560 | 0 failed |
| Live NWS API, area CA | 50 | 353 | 2,588 (`888-7.html`) | 0 failed |

- Budget: 51,200 bytes per page. Largest measured page in any build above: 2,592 bytes.
- Inline CSS measured on `888.html`: 834 bytes (UTF-8).
- Build exit code of the live run: 0. The `many-alerts` fixture filled pages 889 to 999.
- `site/` currently holds the live CA build. It is generated output and is not hand-edited.

`tools/check_pages.py` is the fast subset. `verify.py` is authoritative and runs inside every build (a failure gives exit 4); all builds above exited 0.

## Manual checks

UNTESTED - pending manual check. No person has done these yet.

- UNTESTED - pending manual check: JavaScript disabled in a real browser.
- UNTESTED - pending manual check: 200% zoom (and reflow at narrow widths).
- UNTESTED - pending manual check: keyboard-only navigation (tab order, visible focus).
- UNTESTED - pending manual check: at least one screen reader.
- UNTESTED - pending manual check: old phones or old browsers. No old-device or screen-reader support is claimed.

## Hosting

- Action versions in the workflow were taken from the latest release tags reported by the GitHub API on 2026-11-13: checkout v7, setup-python v7, cache v6, upload-pages-artifact v5, deploy-pages v5.
- The workflow file `.github/workflows/pages.yml` exists. It has not been run on GitHub yet, so the scheduled run, cache persistence, deploy and the deployed output are UNCONFIRMED until after the first deploy.
