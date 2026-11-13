# Design: Page 888

## 1. Architecture

Pipeline, one pure stage per module; only `fetch`, `cache`, `publish` and `build` touch I/O.

```
fetch -> cache -> parse -> normalise -> summarise -> paginate -> render -> verify -> publish
```

- fetch: GET `https://api.weather.gov/alerts/active?area=XX&status=actual` (lowercase `actual`; see section 6) with User-Agent, retries, backoff.
- cache: store last good raw JSON plus fetch time and area in `.cache/` (gitignored, persisted by the scheduled job); decide fresh/stale/fallback.
- parse: raw JSON to `Alert` list; tolerant of missing fields; drops any alert whose `status` property is not `Actual`.
- normalise: clean text, sort, dedupe, drop expired.
- summarise: rule-based summary lines.
- paginate: alerts to `Page` objects of grid rows (at most 40x24).
- render: `Page` to HTML string (inline CSS, templates in code).
- verify: static checks on rendered HTML (R8, R9, R12, R13). Authoritative.
- publish: write to sibling temp dir, directory swap into `site/` with crash recovery.

Package `src/page888/`:

| Module | Responsibility | Reqs |
|---|---|---|
| `models.py` | `Severity`, `Alert`, `Row`, `SubPage`, `Page`, `DataStatus` | all |
| `layout.py` | grid and row-budget constants (section 2.1); no logic beyond constants and `assert` of the sum | R6 |
| `palette.py` | `PALETTE`, `ALLOWED_PAIRS`, `contrast_ratio` (pure, used by render, verify and tests) | R13.6 |
| `config.py` | env/CLI config, validation | R1, R2 |
| `fetch.py` | HTTP + retry/backoff | R1, R2 |
| `cache.py` | disk cache keyed by area, freshness | R2, R10 |
| `parse.py` | CAP JSON to `Alert` | R1.7, R3 |
| `text.py` | normalise, `ASCII_MAP`, wrap | R3.6, R6 |
| `order.py` | sort, dedupe, expiry filter | R3.7, R4 |
| `summarise.py` | templates | R7 |
| `paginate.py` | grid layout, sub-pages, numbering | R5, R6 |
| `render.py` | HTML + CSS | R8, R9, R13 |
| `verify.py` | output checks, size budget, allowlists | R8, R9, R12, R13 |
| `publish.py` | directory swap, recovery, cleanup | R14 |
| `build.py`, `__main__.py` | orchestration, exit codes, log | R14 |
| `tools/check_pages.py` (outside the package) | fast hook-time subset of `verify.py` | R14.11 |

`tools/check_pages.py` is a standalone stdlib script (it does not import `page888`, so it runs from a bare checkout inside editor hooks and the Stop guard). It checks the cheap subset: size budget, `<script>`/inline handlers/`javascript:`, external resources (`--strict`), `lang`, `<title>`, one `<h1>`, one `<main>`, labelled `<nav>`. `verify.py` is the authoritative implementation of everything, including that subset. Test `test_prop_check_pages_subset_of_verify` feeds the same bad pages to both and asserts every `check_pages` finding has a `verify_site` counterpart. Where they disagree, `verify.py` wins and `check_pages.py` is fixed.

## 2. Data models

```python
from dataclasses import dataclass
from datetime import datetime
from enum import IntEnum

class Severity(IntEnum):   # lower = more severe (sort key)
    EXTREME = 0; SEVERE = 1; MODERATE = 2; MINOR = 3; UNKNOWN = 4

@dataclass(frozen=True)
class Alert:
    id: str
    event: str
    severity: Severity
    urgency: str          # Immediate|Expected|Future|Past|Unknown
    certainty: str        # Observed|Likely|Possible|Unlikely|Unknown
    area_desc: str
    headline: str
    description: str
    instruction: str      # "" when absent
    onset: datetime | None     # tz-aware, source offset kept (R3.8)
    expires: datetime | None   # tz-aware, source offset kept; falls back to `ends`
    sender_name: str
    source_url: str       # "" unless it passes the https check (R8.2)

@dataclass(frozen=True)
class Row:
    text: str             # <= 40 code points, ASCII
    gap_before: bool = False   # one CSS gap row before this row; counts as a row

@dataclass(frozen=True)
class SubPage:
    number: int           # 3-digit page number, 888..999
    k: int                # 1-based
    total: int            # number of sub-pages of this page
    title: str            # h1 text (see 5.3)
    body: tuple[Row, ...] # len(rows)+gaps <= BODY_ROWS
    double_height_title: bool

@dataclass(frozen=True)
class Page:               # a logical page = its ordered sub-pages
    number: int
    kind: str             # "index" | "alert" | "notice"
    subpages: tuple[SubPage, ...]
    alert_id: str | None

@dataclass(frozen=True)
class DataStatus:
    fetched_at: datetime
    stale: bool           # from age only (R10.3); also true if fetched_at is in the future
    fallback: bool        # fetch failed, cache used (independent of stale)
    skipped: int
```

### 2.1 Layout budget (`layout.py`, defined before any pagination code)

All constants live in `layout.py`; `paginate`, `render`, `verify` and the property tests import them. Row 0 is the first rendered row.

| Block | Constant | Rows | Content (worst case) |
|---|---|---|---|
| header | `HEADER_ROWS` | 1 | `P889/12` style page id, area, `k/total`; fixed text, at most 40 columns |
| body | `BODY_ROWS` | 13 | h1 (double height = 2 rows per line), alert or index content, gaps |
| status | `STATUS_ROWS` | 5 | `DATA AS OF YYYY-MM-DD HH:MM UTC` (1); `STALE DATA - CHECK WEATHER.GOV` (1); `LIVE UPDATE FAILED - SHOWING LAST GOOD DATA` is 43 characters, so wrapped to 2; `SKIPPED UNREADABLE ALERTS: n` (1) |
| navigation | `NAV_ROWS` | 3 | one link row each for previous, next, index (each at most 40 columns, truncated title) |
| footer | `FOOTER_ROWS` | 2 | `NOT AN OFFICIAL WARNING CHANNEL` (31); on 888 the second row is `CHECK WEATHER.GOV OR LOCAL NWS OFFICE` (37, with the link), elsewhere `SOURCE: US NWS API.WEATHER.GOV` |

`HEADER_ROWS + BODY_ROWS + STATUS_ROWS + NAV_ROWS + FOOTER_ROWS == ROWS == 24` is asserted at import. `COLS = 40`. The status, navigation and footer blocks use at most their constant, so the maximum is reached only in the worst case. Rendered rows are counted as the number of `.row` elements plus the number of `.gap` spacers; `<nav>` and `<footer>` content is part of that count. Each `.row` is at most 40 code points after unescaping. A double-height h1 line is one `.row` that counts as 2 (class `.dh`). The trade-off of a 13-row body is more sub-pages for long alerts; no text is lost, only spread over more pages. Header, status and footer text is produced by `paginate` so the counts stay in one place; header and status text that would exceed their rows is a bug caught by P12.

Time display (R3.8): `EXPIRES 2026-11-13 18:00 -05:00` then `= 2026-11-13 23:00 UTC` on the next row. Index rows show `EXP 18:00 -05:00`. Header/status times are UTC and labelled.

## 3. Module interfaces

```python
# palette.py
PALETTE: dict[str, str]                      # name -> hex
ALLOWED_PAIRS: frozenset[tuple[str, str]]    # (fg, bg), 20 pairs, every ratio >= 4.5 (R13.6)
def contrast_ratio(fg: str, bg: str) -> float: ...

# config.py
@dataclass(frozen=True)
class Config:
    user_agent: str; area: str; min_interval_s: int; stale_after_s: int
    max_attempts: int = 4; base_delay_s: float = 2.0; max_delay_s: float = 60.0
    timeout_s: float = 20.0; cache_dir: Path; out_dir: Path
def load_config(env: Mapping[str, str]) -> Config: ...   # raises ConfigError
def valid_area(code: str) -> bool: ...                   # fullmatch [A-Z]{2}

# fetch.py
class FetchError(Exception):
    status: int | None                                   # HTTP status for 4xx, else None
def backoff_ceilings(max_attempts: int, base: float, cap: float) -> list[float]: ...   # min(cap, base*2**n)
def backoff_delays(ceilings: Sequence[float], rng: random.Random) -> list[float]: ... # full jitter in [0, ceiling]
def parse_retry_after(value: str | None, now: datetime) -> float | None: ...
def fetch_alerts(cfg: Config, opener: Callable[..., Any] = urllib.request.urlopen,
                 sleep: Callable[[float], None] = time.sleep, rng: random.Random | None = None) -> bytes: ...

# cache.py   (file name: alerts-<AREA>.json; entry holds area, fetched_at, body)
def is_fresh(fetched_at: datetime, now: datetime, min_interval_s: int) -> bool: ...   # 0 <= age < interval
def is_stale(fetched_at: datetime, now: datetime, stale_after_s: int) -> bool: ...    # age > threshold or age < 0
def load_cache(cache_dir: Path, area: str) -> tuple[bytes, datetime] | None: ...      # area mismatch -> None
def store_cache(cache_dir: Path, area: str, body: bytes, fetched_at: datetime) -> None: ...  # atomic write
def get_data(cfg: Config, now: datetime, fetcher: Callable[[Config], bytes]) -> tuple[bytes, DataStatus]: ...

# parse.py
def parse_feed(raw: bytes) -> tuple[list[Alert], int]: ...      # (alerts, skipped); raises FeedError on invalid top level
def parse_alert(feature: object) -> Alert | None: ...           # never raises; None if unusable or status != "Actual"
def parse_severity(v: object) -> Severity: ...
def parse_time(v: object) -> datetime | None: ...               # tz-aware or None

# text.py
ASCII_MAP: dict[str, str]                                       # explicit table, e.g. "\u00b0" -> "DEG"
def normalise_text(s: str) -> str: ...                          # idempotent, ASCII only
def wrap(text: str, width: int = 40) -> list[str]: ...          # preserves all non-space chars, order
def format_time(dt: datetime) -> tuple[str, str]: ...           # (local-offset line, UTC line)

# order.py
def order_alerts(alerts: Iterable[Alert], now: datetime) -> list[Alert]: ...

# summarise.py
def summarise(a: Alert) -> str: ...                             # deterministic, template based

# paginate.py
def paginate_alert(a: Alert, number: int, status: DataStatus, nav: NavContext) -> Page: ...
def paginate_index(alerts: Sequence[Alert], status: DataStatus, area: str) -> list[Page]: ...
def paginate_notice(area: str, status: DataStatus) -> list[Page]: ...   # R10.8
def assign_numbers(n_alerts: int) -> tuple[list[int], int]: ... # (numbers for shown alerts, overflow count)
def build_site_model(alerts: Sequence[Alert], status: DataStatus, area: str) -> list[Page]: ...
def filename(number: int, k: int) -> str: ...                   # "889.html" / "889-2.html"

# render.py
def esc(s: str) -> str: ...                                     # html.escape(s, quote=True)
def render_subpage(sp: SubPage, nav: NavLinks, status: DataStatus) -> str: ...
CSS: str                                                         # generated from PALETTE / ALLOWED_PAIRS only

# verify.py
class VerifyError(Exception): ...
ALLOWED_ELEMENTS: frozenset[str]; ALLOWED_ATTRS: Mapping[str, frozenset[str]]
def verify_site(files: Mapping[str, str]) -> list[str]: ...     # violations; empty = ok. Size is len(s.encode("utf-8")).

# publish.py
def recover(out_dir: Path) -> None: ...                         # run first; see section 6
def publish(files: Mapping[str, str], out_dir: Path) -> None: ...  # sibling temp dir + directory swap

# build.py
def build(cfg: Config, now: datetime, fetcher=...) -> int: ...  # exit code
```

Exit codes: 0 ok (including stale or fallback, logged); 2 config error (including bad area pattern); 3 no data and no cache (transient failure); 4 verification failed; 5 API rejected the request with a 4xx and no cache (for example an unknown area). Codes 3 and 5 publish the notice site (R10.8) before exiting.

## 4. Pagination algorithm

Input: alert, layout constants (section 2.1).

1. Build a list of logical blocks in order: h1 (event, maybe double height), meta rows (SEVERITY/URGENCY/CERTAINTY, AREA, ONSET, EXPIRES with their UTC lines, SENDER), SUMMARY, DESCRIPTION, ACTION (full `instruction`, or `NO INSTRUCTION FIELD IN SOURCE - SEE DESCRIPTION`), SOURCE (`ID`/link, and `PAGE NUMBERS ARE NOT STABLE IDS`). Compared alert text for R6.4 is `description` then `instruction` only.
2. Wrap each block's text to 40 columns with `wrap`: greedy word fill; a word longer than 40 is hard-split into 40-char chunks (the only mid-word break); paragraph breaks become one gap (collapsed at page starts). Each source paragraph becomes one logical paragraph (one `<p>` in render).
3. Flow rows into pages of `BODY_ROWS` (13), counting gaps and double-height lines (2 each). A section label row is only placed if at least 2 rows (label plus one text row) fit; otherwise break first. A block is never dropped; overflow continues on the next sub-page, with the section repeated as `ACTION (CONT.)` (and `DESCRIPTION (CONT.)`) on the continuation.
4. Double-height headline: used only on sub-page 1, only if the event wrapped at 20 columns takes at most 2 double-rows (4 body rows); otherwise normal height. Cost = 2 rows per wrapped line.
5. Emit `SubPage`s with k = 1..n; the header row shows `PNNN/k` and the area, the nav rows show previous, next and index links.
6. Because sub-pages are produced by chunking a row list, concatenating rows with labels, `(CONT.)` markers and blanks removed reproduces the normalised description then instruction (property P13).

Numbering: shown alerts get 889, 890, ... up to 999 (111 pages max). The index lists alerts, one row pair per alert: `NNN SEVERITY EVENT` (link row) and `AREA, EXP time` (detail row), so 6 alerts per 13-row index sub-page, minus the h1 rows. If rows exceed index body capacity, the index continues as 888/2 and so on. If alerts exceed 111, only the first 111 in R4 order get pages and the last index sub-page ends with `NOT SHOWN: n MORE - SEE WEATHER.GOV` plus a link to `https://www.weather.gov/` (R5.7). This is an accepted trade-off: the omitted alerts are the least severe and latest expiring, and the README records it. Sub-pages of alert pages reuse the page's number with k, so they do not consume numbers. Numbers are per build.

Empty state: page 888 with `NO ACTIVE ALERTS FOR <AREA>`; in stale or fallback mode with no unexpired alerts, `NO UNEXPIRED ALERTS IN LAST GOOD DATA` immediately followed by the banner rows (R10.7). Notice state (R10.8): `ALERT DATA UNAVAILABLE - CHECK WEATHER.GOV`, 888 and index.html only.

## 5. HTML/CSS template approach

Templates are Python string constants with `esc()` (`html.escape(..., quote=True)`) applied at every substitution point; render functions never concatenate raw API text. No third-party template engine.

### 5.1 Page skeleton

```html
<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>P889/1 SEVERE FLOOD WARNING - Page 888</title>
<style>/* inline; size reported by the build log after measuring */</style></head>
<body class="tt">
<header><p class="row hdr">P889/1 CA 1/3</p></header>
<main>
  <h1 class="row dh">FLOOD WARNING</h1>
  <h2 class="row">SUMMARY</h2>
  <p><span class="row">SEVERE FLOOD WARNING FOR ...</span><span class="row">...</span></p>
  <h2 class="row gap">ACTION</h2>
  <p><span class="row">...</span></p>
  <p class="status"><span class="row">DATA AS OF 2026-11-13 14:05 UTC</span> ...</p>
</main>
<nav aria-label="Page navigation"><ul><li class="row"><a href="888.html">INDEX 888 ALERT INDEX</a></li> ...</ul></nav>
<footer><p><span class="row">NOT AN OFFICIAL WARNING CHANNEL</span><span class="row">...</span></p></footer>
</body></html>
```

The grid is the whole body: header, main, nav and footer sit inside `body.tt`, so the 24-row count covers all of them. A `.gap` is a margin-top of one row height on the following element and counts as one row.

### 5.2 CSS rules

- Everything is generated from `PALETTE` and `ALLOWED_PAIRS`; no hand-written colour that is not in the list. Body: `body.tt{margin:0 auto;width:40ch;max-width:100%;font-family:monospace,monospace;font-size:1rem;line-height:1.5;background:#000;color:#fff}`. White on black is an allowed pair (21:1).
- Rows: `.row{display:block;white-space:pre-wrap;overflow-wrap:anywhere;min-height:1.5em}` (a safety net only; rows are at most 40 code points). Reflow on viewports narrower than 40 characters is accepted under WCAG 1.4.10 (R13.18); alignment and the visual 24-row count are then not preserved, and the font stack `monospace,monospace` stops browsers shrinking the monospace default.
- Links: `a,a:visited,a:hover{color:#0ff;background:#000;text-decoration:underline}` (cyan on black, 16.7:1; the same colours in every state so a default blue never appears). Links appear only on black or blue backgrounds. `a:focus-visible{outline:3px solid #ff0;outline-offset:2px}` (yellow gives 19.6:1 on black and 8.0:1 on blue). `a{display:inline-block;min-height:24px;min-width:24px}`. No `outline:none`.
- Colour bands: classes `.b-<bg>-<fg>` exist only for pairs in `ALLOWED_PAIRS` (for example `.b-blue-yellow`). Text bands that carry severity also state it in words.
- Double height: `h1.dh{font-size:2em;line-height:1.5;margin:0}` for the single `<h1>`; the generator wraps its text at 20 columns. No duplicated text.
- No `@keyframes`, `animation`, `transition`; no `<noscript>`; `prefers-reduced-motion` and `prefers-contrast` are not needed.
- CSS size is not estimated here; the build log reports the measured page size and the README quotes it after a build.

### 5.3 h1 and titles

- Alert page k=1: h1 is the event (double height when it fits); `<title>` is `P889/1 <SEVERITY> <EVENT> - Page 888`.
- Alert sub-page k>=2: h1 is `<EVENT> (CONT. k/n)` at normal height.
- Index sub-page 1: h1 is `ALERT INDEX <AREA>`; index sub-page k>=2: h1 is `ALERT INDEX <AREA> (CONT. k/n)`. Notice page: h1 `ALERT DATA UNAVAILABLE`.
- Header row 0 holds the page id, area and `k/total` only. The date and time are in the status block (`DATA AS OF`), so the steering description of row 0 was reconciled to this layout.
- Titles are unique per file except `index.html`, an exact copy of `888.html` (R5.10, R13.2).

### 5.4 Links, structure and navigation

- Index uses an ordered list of links `889 SEVERE Flood Warning` (link text contains number, severity, event). The source link is `<a href="...">` with `esc(url, quote=True)`, rendered only when `urlsplit` gives scheme `https`, non-empty host, and no whitespace or control characters (R8.2); otherwise the URL is plain text.
- Paragraph grouping: each logical paragraph is a single `<p>` containing one `<span class="row">` per wrapped row (no `<br>`); section labels are `<h2 class="row">`. Spans are block-level through CSS only, so assistive technology reads a sentence as one paragraph (R13.17).
- Navigation without JS: numbered links only; a `GO TO` list on 888. Typing is not supported (documented limitation). CSS-only `:target` is not used.
- Navigation link text includes the target page number and a title truncated to fit 40 columns (the full title is on the target page).

## 6. Error handling

| Condition | Behaviour |
|---|---|
| UA missing | `ConfigError`, exit 2, no request |
| area not `[A-Z]{2}` | `ConfigError`, exit 2, no request |
| 429/5xx/network | retry up to `max_attempts` (4): ceiling = `min(cap, base*2^n)` with `base`=2 s, `cap`=60 s, jittered in `[0, ceiling]`; if `Retry-After` is present, delay = `max(Retry-After, jittered)`; if `Retry-After` > cap, stop retrying; request timeout 20 s |
| 4xx (not 429) | `FetchError(status)` immediately, no retry; fallback to the area's cache, otherwise exit 5 (for example HTTP 400 for an unknown area) |
| invalid JSON / no `features` | `FeedError`, treated as fetch failure; cache untouched |
| Fetch failed, cache for this area exists | build with `fallback=True`, banner text (stale decided by age alone), exit 0 |
| Fetch failed, no cache (or cache for another area) | publish notice site (R10.8), exit 3 (or 5) |
| Bad feature | skipped, counted, shown in the status block |
| Verify failure | exit 4, violations printed, `site/` untouched |
| Page >= 50 KB (UTF-8 bytes) | verify failure (R12) |
| Disk error in publish | temp dir removed, previous `site/` kept |

Publish swap (R14.2): POSIX `rename` cannot replace a non-empty directory, so `publish` does (1) write all files to `.site.tmp` beside `site`, (2) `rename(site, site.old)`, (3) `rename(.site.tmp, site)`, (4) delete `site.old`. It is not strictly atomic: between steps 2 and 3 `site` is absent. `recover(out_dir)` runs at the start of every build: `site` missing and `site.old` present, rename `site.old` back; both present, delete `site.old`; a leftover `.site.tmp` is deleted. Hosts that upload an artifact are unaffected because the upload happens after the job ends.

Stale-site problem (R2.8, R2.11, R10.8): a page cannot flag itself stale after the build ends, so the scheduled job must (a) persist the cache between runs, and (b) deploy whatever `site/` the build leaves, including the notice site after exit 3 or 5 (job step runs the deploy even when the build step exits 3 or 5, and still fails the run visibly). A job that cannot persist its cache is non-conforming.

Time is injected (`now` parameter) and sleep/opener/rng are injectable so every error path is testable offline. The User-Agent is never logged.

NWS `status` casing (verified 2026-11-13 by a live request): the query parameter is lowercase `status=actual`; `status=Actual` returns HTTP 400 with enum `[actual, exercise, system, test, draft]`. The `properties.status` value in the response is `Actual`. Both facts are encoded in `fetch.py` and `parse.py` and covered by tests.

## 7. Correctness properties

Each is a hypothesis property named `test_prop_*`; ids trace to requirements.

| Id | Property | Reqs |
|---|---|---|
| P1 | For any JSON value as a feature, `parse_alert` never raises; result is `Alert` or `None`. | R3.2, R3.5 |
| P2 | Every parsed alert has `properties.status == "Actual"` origin; non-Actual inputs never appear. | R1.7 |
| P3 | `parse_severity` maps any input into `Severity`; unknown maps to UNKNOWN. | R3.3 |
| P4 | `parse_time` returns a tz-aware datetime or None, never raises; no offset gives None. | R3.4 |
| P5 | `normalise_text` is idempotent; output has no control characters; output is printable ASCII plus paragraph-break newlines; no lone single newline survives (collapsed to a space); two or more newlines survive as a paragraph break. | R3.6 |
| P6 | Dedupe by real id: output real ids unique, subset of input ids; placeholder-id (`NOT STATED`) alerts are never collapsed. | R3.7 |
| P7 | `order_alerts` output is a permutation of its non-expired input, sorted by (severity, expiry-or-inf in UTC, id), invariant under input shuffling. | R4.1-R4.4 |
| P8 | `assign_numbers(n)` yields distinct, ascending 3-digit numbers starting at 889, at most 111, with overflow = n - shown. The page order produced by `build_site_model` follows the P7 order (alert at number 889+i is the i-th of `order_alerts`). | R5.2, R5.5, R5.7, R4.1 |
| P9 | `filename(number, k)` matches `^\d{3}(-\d+)?\.html$`, k=1 has no suffix, is injective. | R5.3, R5.4 |
| P10 | Link graph of `build_site_model`: every page reachable from 888, every link target exists, each sub-page links to prev/next/888. | R5.8 |
| P11 | For any text, every row from `wrap` has length <= 40, and non-whitespace characters are preserved in order. | R6.1, R6.2 |
| P12 | For any alert and any `DataStatus`, every `SubPage` has body rows plus gaps <= `BODY_ROWS`, each row <= 40 code points, and the rendered page (counting `.row` plus `.gap`, double-height lines as 2) is <= 24 rows including header, status, nav and footer. Continuation: whenever a section spans sub-pages, each later sub-page begins that section with its label plus `(CONT.)`. | R6.1, R6.3, R6.6, R6.10, R6.11 |
| P13 | Strip section labels and `(CONT.)` markers and whitespace from the body text of all sub-pages in order; the result contains the normalised description followed by the normalised instruction (each with whitespace removed) as an in-order substring. An absent instruction yields the fixed `NO INSTRUCTION FIELD IN SOURCE - SEE DESCRIPTION` text under ACTION. | R6.4, R6.5 |
| P14 | No page ends with a section label as its last body row; no word is split except words > 40 chars. | R6.8, R6.9 |
| P15 | Double-height headline: at most one per page, line <= 20 chars, rows counted twice. | R6.6, R6.7 |
| P16 | `summarise` is deterministic, total (never raises), and includes severity, urgency and certainty words. | R7.2, R7.3, R7.6 |
| P17 | For any text containing `<>&"'` in any field, rendered HTML has no unescaped occurrence; attribute values use `quote=True`; every element and attribute is in `ALLOWED_ELEMENTS` / `ALLOWED_ATTRS`. | R8.1, R8.3, R8.4 |
| P18 | Source link rendered as `<a>` only when `urlsplit` gives scheme https, a non-empty host and no whitespace or control characters; other values appear as plain text. | R8.2 |
| P19 | Rendered output never contains `<script`, `<noscript`, `on*=` attributes, `javascript:`, external `src`/`href` (other than the source link and the weather.gov link), `http-equiv`. | R9.1, R9.2, R9.4 |
| P20 | Every rendered page has `lang`, exactly one `<h1>` (including index sub-pages and alert sub-pages k>=2), one `<main>`, labelled `<nav>` with distinct labels, no `aria-hidden`, no empty elements, no `&nbsp;` runs. Titles are unique across files except `index.html` vs `888.html`. | R13.1-R13.5, R13.12, R13.13 |
| P21 | Link text for page links contains the page number and a title; never "click here". | R13.5 |
| P22 | For all 64 (fg, bg) combinations of `PALETTE`, membership in `ALLOWED_PAIRS` holds iff `contrast_ratio >= 4.5`; every colour pair present in the generated CSS (including body, `a`, `a:visited`, `a:hover`, band classes and the focus outline against the link backgrounds) is in `ALLOWED_PAIRS` (the outline is checked at >= 3:1). | R13.6, R13.16, R13.19 |
| P23 | Severity word appears in text on every alert page and index row. | R13.7 |
| P24 | Every page contains `NOT AN OFFICIAL WARNING CHANNEL` and `DATA AS OF`. | R10.1, R11.1 |
| P25 | `is_stale` is monotonic in age for age >= 0, and true for negative age; stale pages contain the stale text; non-stale ones do not; fallback pages contain the fallback text whether or not stale. | R10.3, R10.4 |
| P26 | `is_fresh` true iff `0 <= age < interval`; a future `fetched_at` is never fresh; interval is clamped to >= 30 s. | R2.2, R2.3 |
| P27 | `backoff_ceilings`: length = max_attempts - 1, non-decreasing, each <= cap, equals `min(cap, base*2**n)`. `backoff_delays` with any rng: each delay in `[0, ceiling]`. `parse_retry_after` is total and returns None or a value >= 0; the wait rule `max(Retry-After, delay)` stops retrying when `Retry-After` > cap. | R2.4, R2.5 |
| P28 | `valid_area` accepts exactly strings matching `^[A-Z]{2}$`. | R1.5 |
| P29 | Every rendered page is < 51,200 UTF-8 bytes, for alerts with worst-case field sizes. | R12.1 |
| P30 | Failed verify or fetch leaves existing `site/` byte-identical; successful publish leaves no stale files; a crash simulated between the two renames is repaired by `recover`. | R14.2-R14.4 |
| P31 | Cache keyed by area: storing for area A and loading for area B returns None; fetch for B never serves A's alerts. | R2.10 |
| P32 | Time display: `format_time` output parses back to the same instant in both lines; ordering uses UTC. | R3.8, R4.1 |
| P33 | Generated CSS contains no `outline:none`/`outline:0`, `@keyframes`, `animation`, `transition`; contains `ch` on `.tt` and no `px` width on `.tt`/`.row`; links have `min-height` and `min-width` >= 24px; viewport meta present without `user-scalable=no` or `maximum-scale`. | R13.8-R13.11, R13.15 |
| P34 | `check_pages` findings are a subset of `verify_site` findings on the same files. | R14.11 |

Example-based tests (not PBT): UA unset exits non-zero (R1.2), UA header sent and URL has `status=actual&area=` with lowercase `actual` and never `Actual` (R1.3-1.4, via fake opener), a recorded HTTP 400 response for `status=Actual` maps to `FetchError(400)` and exit 5 (R1.8), no retry on 404 (R2.6), invalid JSON not cached (R2.9), cache fallback banner (R2.7, R10.4), empty-state page (R10.2), stale-with-all-expired page text (R10.7), notice site contents and exit 3 (R2.8, R10.8), index overflow line and link (R5.7), header text `PNNN/k` (R5.4), id and "not stable" text present (R5.9), row order SUMMARY, DESCRIPTION, ACTION (R7.5), sender and source link (R11.3), attribution (R11.2), broadcaster denylist scan of output and docs (R11.4), stage-order spy (R14.1), stdlib-only import scan against `sys.stdlib_module_names` (R14.6), no analytics/cookie strings (R14.7), log line excludes UA (R14.10), 51,199 bytes passes and 51,200 fails (R12.1, with a multi-byte character to prove UTF-8 byte counting).

## 8. Testing strategy

- pytest and hypothesis, dev-only; `tests/test_<module>.py`; property tests `test_prop_*`; fixtures in `tests/fixtures/` (recorded CAP JSON samples: normal, long instruction, nulls, Test status, hostile text, empty, very many alerts, a recorded HTTP 400 body for `status=Actual`).
- No network: `fetch_alerts` takes an injectable opener, sleep and rng; a conftest guard patches `socket.socket.connect` to fail tests that try.
- Custom hypothesis strategies: `cap_feature()` (valid with random nulls/wrong types), `hostile_text()` (markup, quotes, control chars, long unbroken words, non-ASCII), `alerts()`.
- `verify.py` is the authoritative static checker and doubles as test oracle; `tools/check_pages.py` is the fast subset for hooks, tested against it (P34). Tests also parse output with `html.parser` (stdlib) to confirm structure.
- Contrast is computed from hex values in `PALETTE` (`palette.contrast_ratio`), compared with the steering table; P22 exhaustively checks all 64 pairs.
- Manual checks (listed in docs, not automated): 200% zoom, JS disabled, keyboard-only, one screen reader pass.
- CI runs `pytest -q`; the build job runs `python -m page888` with the secret UA.

## 9. Hosting and scheduling options

All free-tier-capable options; none chosen by this spec. Pick one when deploying and check its current terms.

| Option | Schedule | Publish | Notes |
|---|---|---|---|
| GitHub Actions + GitHub Pages | `on: schedule` cron (minimum cron granularity is 5 minutes; verify against current GitHub docs) plus manual dispatch | Pages deploy artifact, or commit `site/` to a branch | UA contact held in a repository secret/variable |
| GitLab CI schedule + GitLab Pages | pipeline schedule | Pages job artifact `public/` (set `PAGE888_OUT=public`) | |
| Cloudflare Pages / Netlify with an external scheduler (e.g. Actions cron triggering a deploy hook) | external | deploy hook or CLI upload | Check each host's free-tier limits |
| Any static file host fed by a cron on a machine the owner already has | cron | rsync | Owner-managed |

Requirements for all: Python 3.12 available, secret/env `PAGE888_USER_AGENT`, a cache directory that is persisted between runs (mandatory, R2.11: CI cache action, cache branch or a path on the owner's machine), and a deploy step that runs even when the build exits 3 or 5 so the notice site replaces stale content (section 6). Schedules must not run more often than the 30 s minimum; a coarse interval of several minutes is the practical lower bound on these hosts. Output directory is configurable via `PAGE888_OUT` (default `site`).

## Revision log (review r1, 2026-11-13)

Source: `docs/reviews/2026-11-13-teletext-qa-design-review-r1.md`. Requirement numbers are stable; new criteria were appended.

High
- 1 Resolved: persisted cache mandatory (R2.11, R14.5, task 15.2); exit 3/5 now publishes a notice site (R2.8, R10.8) so old alerts cannot sit on a live site; deploy step must run after exit 3/5 (section 6).
- 2 Resolved: cache keyed by area in file name and entry (R2.10, `load_cache(area)`, P31).
- 3 Resolved: fixed row budget 1+13+5+3+2=24 in `layout.py` (section 2.1, R6.10, R6.11); nav and footer inside the grid; "rendered row" defined as `.row` plus `.gap`; worst-case status text sized (43-char fallback banner wraps to 2 rows).
- 4 Resolved: body, `a`, visited, hover, focus colours set from the palette; footer and nav inside the grid (R13.16, R13.19, P22).
- 5 Resolved: explicit 20-pair `ALLOWED_PAIRS`, CSS generated only from it, all 64 combinations tested; `contrast_ratio` moved to `palette.py` built in task 8.1 (R13.6, P22).
- 6 Resolved: one `<p>` per logical paragraph with row spans, `<h2>` section labels (R13.17, section 5.4).
- 7 Resolved: rename-based directory swap with `recover` and a stated non-atomic window (R14.2, section 6, P30).

Medium
- 8 Resolved: alert text defined; "contains in order"; explicit `ASCII_MAP` (R3.6, R6.4, P13).
- 9 Resolved: R6.9 exception for words over 40 characters.
- 10 Resolved: `NO INSTRUCTION FIELD IN SOURCE - SEE DESCRIPTION` (R6.5).
- 11 Resolved: one behaviour (count line plus `weather.gov` link, no extra pages); omission recorded as an accepted trade-off (R5.7, section 4).
- 12 Resolved: `index.html` exempt from unique title (R5.10, R13.2).
- 13 Resolved: fallback and stale are independent (R2.7, R10.3, R10.4, P25).
- 14 Resolved: `NO UNEXPIRED ALERTS IN LAST GOOD DATA` (R10.7).
- 15 Resolved: defaults and `timeout_s` listed; Retry-After rule precise; testable ceiling sequence (R2.4, R2.5, R2.12, P27).
- 16 Resolved: tz-aware times, source offset plus UTC line (R3.8, P32).
- 17 Resolved: added requirement-mapped tests P32-P34 and example tests (section 7) and tasks 7.6, 8.5, 9.3, 9.4, 13.3 (tasks.md).
- 18 Resolved: P5 extended with newline collapsing and ASCII-only.
- 19 Resolved: UTF-8 byte measurement stated; boundary test with a multi-byte character (R12.1, P29).
- 20 Resolved: P8 ordering clause; P12 continuation clause.
- 21 Resolved: pattern validation is intentional; 4xx handled (R1.8, R1.9, exit code 5); `status` casing verified live 2026-11-13 (R1.4).
- 22 Resolved: `0 <= age < interval` (R2.2, P26).
- 23 Resolved: `models.py`, `layout.py`, `palette.py` added to the module table; tasks reordered so `palette.py` precedes 8.1.
- 24 Resolved: `tools/check_pages.py` documented as the fast hook-time subset; `verify.py` authoritative; subset test P34 (R14.11, structure.md).
- 25 Resolved: reflow accepted under WCAG 1.4.10; `monospace, monospace` (R13.18, section 5.2).

Low
- 26 Resolved: product.md says "click".
- 27 Resolved: header row 0 holds page id, area, k/total; date in status block; h1 in body (section 5.3, teletext-style.md).
- 28 Resolved: R9.1 states no `<noscript>`.
- 29 Resolved: h1 text defined for index, k>=2 and notice pages (section 5.3).
- 30 Resolved: yellow on blue is 8.0:1 in teletext-style.md and R13.19.
- 31 Resolved: links only on black or blue bands; outline yellow checked (R13.19, P22).
- 32 Resolved: `esc(quote=True)` and `urlsplit` validation (R8.2, R8.4, P18).

Invented statistics
- Teletext dates dropped from product.md. "~2 KB" CSS estimate removed (section 5.2). GitHub cron claim marked "verify against current docs" (section 9).

Intentionally deferred
- Listing omitted alerts individually beyond 111 pages (item 11): deferred; the count line plus official link is the accepted behaviour, because more than 111 simultaneous alerts in one area is an extreme case and extra index rows would reduce room for the rest.
- Enumerating valid area codes in the validator (item 21): deferred; unknown but well-formed codes are handled via the HTTP 400 path, and a code list would go stale.
- Detection of a persisted cache being silently lost on the host: deferred to the host workflow (task 15.2); the notice-site rule limits the harm.
- Large-text contrast exceptions (3:1 pairs): not used; every pair needs 4.5:1, which keeps the check simple.
