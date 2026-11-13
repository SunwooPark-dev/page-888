# Page 888: documentation

Page 888 turns live US National Weather Service (NWS) alerts into small static pages in a teletext style: three-digit page numbers, a 40 column by 24 row grid and eight block colours. It uses no JavaScript. This is not an official NWS product and not an official warning channel. Always check [weather.gov](https://www.weather.gov/) for official information.

## Setup

Requires Python 3.12 or newer. The generator uses only the standard library. `pytest` and `hypothesis` are needed for tests only.

```
python3.12 -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
```

## Environment variables

| Variable | Required | Meaning |
|---|---|---|
| `PAGE888_USER_AGENT` | yes | Descriptive User-Agent with contact information (a website or email). NWS requires one. The build exits with code 2 if it is unset or blank. It is never logged. |
| `PAGE888_AREA` | no, default `CA` | Area code for the alerts. See "Accepted area codes". |
| `PAGE888_OUT` | no | Output directory (default `site`). |
| `PAGE888_CACHE_DIR` | no | Cache directory (default `.cache`). |
| `PAGE888_MIN_INTERVAL_S` | no | Minimum seconds between live fetches; values below 30 are raised to 30. Default 60. |
| `PAGE888_STALE_AFTER_S` | no | Age in seconds after which data is marked stale. Default 1800. |

## Commands

```
pytest -q                                   # all tests (no network)
pytest -q -k prop                           # property tests only
PAGE888_USER_AGENT="MyApp (https://example.org/contact)" python -m page888   # build site/
python tools/check_pages.py site --strict   # fast static checks of site/
```

If the package is not installed, prefix with `PYTHONPATH=src`.

Exit codes of `python -m page888`: 0 success (including stale or fallback data), 2 configuration error, 3 no data and no cache (a notice site is published), 4 verification failed (previous site left in place), 5 the API rejected the request with a 4xx and there is no cache (a notice site is published).

Tests never use the network. `tools/record_fixtures.py` is the only script that does, and it is only used to record fixtures.

## Navigation

Typing a page number is not possible without JavaScript or a server. Navigation is by links: the index (page 888) lists each alert with its page number as a link, and every page links to the previous page, the next page and back to 888. Everything works with the keyboard.

## Page numbers

- 888: index of active alerts for the chosen area. It continues as 888/2 and so on when it has too many rows.
- 889 onward: one page per alert, most severe first, then soonest expiry. Long alerts continue on sub-pages (889/2, ...). Files are named `889.html`, `889-2.html`. `index.html` is a byte-identical copy of `888.html`.
- Page numbers are assigned per build and are not stable identifiers. Each alert page shows the alert's source id and a link to the source.

## Limits and trade-offs

- Only 111 alert pages exist (889 to 999). When there are more alerts, the least severe ones are not given pages. The last index page shows `NOT SHOWN: n MORE - SEE WEATHER.GOV` with a link. This is an accepted trade-off.
- Safety-critical text (the instruction field) is never dropped to fit a page; the alert paginates instead.
- ASCII mapping is lossy. Page text is printable ASCII. A fixed table maps common characters (for example the degree sign becomes `DEG`, curly quotes become straight quotes); other non-ASCII characters are decomposed and combining marks are dropped, and anything left becomes `?`.
- Row guarantee: each page holds at most 24 rows of at most 40 columns in the generated grid. The grid is sized in `ch` units so that it can reflow at narrow viewports or large zoom; on a very narrow viewport the browser may wrap a row, so the 24-row count refers to the generated rows, not to the rendered screen.
- Summaries are rule-based from the alert's own fields (event, severity, urgency, certainty and so on). There is no language model and nothing is added beyond fixed words.
- Per-page budget: each generated page must be smaller than 50 KB (51,200 bytes, measured in UTF-8) or the build fails. Measured sizes are in [CHECKS.md](CHECKS.md).

## Accepted area codes

Any two uppercase ASCII letters are accepted (`^[A-Z]{2}$`): US state and territory codes, DC, and the marine area codes that NWS lists. The generator does not keep a list. A code that NWS rejects (HTTP 4xx) is handled as a failed fetch: the cache for that same area is used if it exists, otherwise exit code 5 and a notice site. See the [NWS API documentation](https://www.weather.gov/documentation/services-web-api) for valid codes.

## Data attribution

Alert data comes from the NWS API at `api.weather.gov`. Each alert page names the sending office and links to the source alert. Page 888 is not endorsed by NWS.

## Fetch behaviour

The request uses `status=actual` and `area=<code>`; the nationwide feed is never fetched. Responses are cached on disk per area. Failed requests (network errors, 429, 5xx) are retried with exponential backoff and jitter, up to 4 attempts, honouring `Retry-After`. If a fetch fails, the last cached data for the same area is shown with a visible banner. If there is no data at all, a notice reading `ALERT DATA UNAVAILABLE - CHECK WEATHER.GOV` is published. Sources checked for the scheduling limits are in [SOURCES.md](SOURCES.md).

## Hosting

`.github/workflows/pages.yml` builds and deploys to GitHub Pages every 30 minutes (and on manual run and on push to `main`). Tests must pass before the build. The workflow persists `.cache/` between runs. When the build exits with 3 or 5, the notice site is deployed and the job is then marked failed. It does not deploy on exit 2 or 4. GitHub disables scheduled workflows in a public repository after 60 days without repository activity.

## Other documents

- [CHECKS.md](CHECKS.md): measured results and manual checks still pending.
- [KIRO_FEATURES.md](KIRO_FEATURES.md): how Kiro features were used.
- [BRIEF.md](BRIEF.md), [SOURCES.md](SOURCES.md).

## Licence

MIT.
