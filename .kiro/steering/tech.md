---
inclusion: always
---

# Tech

## Stack
- Static site generator in Python 3.12, standard library only at runtime (urllib, json, html, pathlib, etc.). No third-party runtime dependencies.
- Dev only: pytest, hypothesis (property tests).
- Output: static HTML with inline CSS. No JavaScript shipped: no `<script>`, no inline event handlers, no external JS, no web fonts, no external CSS or images.
- Free static hosting, regenerated on a schedule.

## NWS API (api.weather.gov)
- Endpoint: `/alerts/active`, narrowed server-side by area (e.g. `?area=CA`). The nationwide feed is large; never ship or fetch it per page.
- No API key.
- A descriptive `User-Agent` with contact info is REQUIRED; requests without one get 403. Make it configurable (env var), never hardcode a personal contact, and fail loudly if unset.
- Always filter with the query parameter `status=actual` (lowercase; the feed includes Test messages). Verified against the live API on 2026-11-13: `status=Actual` returns HTTP 400 with the enum `[actual, exercise, system, test, draft]`. The `status` property in each returned alert has the value `Actual` (capitalised); after parsing, drop any alert whose `properties.status` is not `Actual`.
- Cache by area (area code in the cache file name and entry); a cache for another area is no cache. The scheduled job must persist the cache between runs. Defaults: 4 attempts, 2 s base delay, 60 s delay cap, 20 s request timeout. A `Retry-After` above the cap stops retrying; a 4xx other than 429 is not retried.
- If there is no data and no cache, publish a notice site (`ALERT DATA UNAVAILABLE - CHECK WEATHER.GOV`) rather than leaving old alerts live or showing "no active alerts".
- Rate limit is not public: cache responses on disk, regenerate on an interval of tens of seconds or more (never tighter), honour `Retry-After`, use exponential backoff with jitter on 429/5xx/network errors, cap retries, and on failure keep serving the last good output rather than emptying the site.
- Treat all API text as untrusted: HTML-escape everything, tolerate missing/null fields.

## Hard budgets
- Each generated page < 50 KB including inline CSS (the generator must fail the build when exceeded).
- Grid: 40 columns x 24 rendered rows per page (`.row` elements plus `.gap` spacers), with fixed row budgets defined in `layout.py`: header 1, body 13, status 5, navigation 3, footer 2. Longer content paginates into sub-pages NNN/k.
- Size is measured in UTF-8 bytes.

## Accessibility (WCAG 2.2 AA intent)
- `<html lang="en">`, unique descriptive `<title>`, exactly one `<h1>`, content in `<main>`, labelled `<nav aria-label="...">`.
- Meaningful link text (not "click here"); page-number links include the page title.
- Contrast >= 4.5:1 for all text; only the explicit `ALLOWED_PAIRS` list in teletext-style.md may be used (CSS is generated from it, including links, body and focus colours); 3:1 for UI boundaries such as the focus outline.
- Group wrapped rows of one paragraph into one `<p>`; section labels are `<h2>`.
- Never convey information by colour alone (severity also stated in text).
- Visible focus indicator; all navigation works by keyboard; target size at least 24x24 CSS px.
- Decorative spacing via CSS, never empty elements or repeated `&nbsp;`. Respect zoom/reflow: no fixed pixel layout that breaks at 200% zoom.
- Do not use `aria-hidden` on real content.

## Testing commands
```
python3.12 -m venv .venv && . .venv/bin/activate
pip install pytest hypothesis
pytest -q                 # all tests
pytest -q -k property     # hypothesis property tests
python -m page888         # generate site/ (needs PAGE888_USER_AGENT set)
python tools/check_pages.py site --strict   # fast hook-time subset; verify.py is authoritative
```
Tests must not hit the network; use recorded/fixture CAP JSON.
