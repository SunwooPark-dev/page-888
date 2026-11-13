# Requirements: Page 888

Static teletext-style renderer of live US NWS alerts for one chosen area. Python 3.12 stdlib only, no JavaScript, free static hosting.

Legend: **[PBT]** = suitable for property-based testing (hypothesis). Others are example/integration/static-check tests. "The system" is the generator (`python -m page888`) and its output in `site/`.

Assumption: one build covers one area (state/area code from `PAGE888_AREA`). Typing a page number is not possible without JS or a server, so "remote-control" navigation is delivered as numbered links (and a visible "go to" list on 888); this is a documented limitation.

Numbering note (revision r1): existing criteria keep their numbers; criteria added in response to review r1 are appended at the end of each requirement.

Definitions:
- **Alert text** = the normalised `description` and `instruction` fields. Headline, areaDesc and event are display fields, not alert text.
- **Rendered row** = one `.row` element or one `.gap` spacer (a blank row produced by CSS). Each `.row` holds at most 40 code points after unescaping. A page has at most 24 rendered rows in total (see R6.10).
- **Stale** is computed from data age only (R10.3). **Fallback** means the fetch failed and the cache was used (R2.7). They are independent flags.

## R1. Fetch NWS alerts
**User story:** As the site owner, I want the generator to fetch only the alerts for my area, politely, so that the NWS service is not abused and requests are not rejected.

1. WHEN the generator starts, THE SYSTEM SHALL read the User-Agent from the `PAGE888_USER_AGENT` environment variable.
2. IF `PAGE888_USER_AGENT` is unset or blank, THEN THE SYSTEM SHALL exit non-zero before any network request and print a message naming the variable.
3. THE SYSTEM SHALL send the configured User-Agent on every request to `api.weather.gov` and SHALL NOT hardcode any contact details.
4. THE SYSTEM SHALL request `/alerts/active` with the query parameters `status=actual` (lowercase) and `area=<code>`, and SHALL NOT use an API key. Verified against the live API on 2026-11-13: `status=Actual` returns HTTP 400 with the allowed enum `[actual, exercise, system, test, draft]`. The `status` property inside each returned feature has the value `Actual` (capitalised); the parser compares against `Actual`.
5. IF the area code is not exactly two uppercase ASCII letters, THEN THE SYSTEM SHALL exit non-zero (exit code 2) without a request. **[PBT]** (validator accepts exactly strings matching `^[A-Z]{2}$`)
6. THE SYSTEM SHALL NOT fetch the nationwide feed.
7. WHEN a parsed alert has a status other than `Actual`, THE SYSTEM SHALL drop it. **[PBT]**
8. IF the API rejects a well-formed request with a 4xx (for example an unknown area code returns HTTP 400), THEN THE SYSTEM SHALL treat it as a failed fetch without retry (R2.6), use the cache if one exists for the same area (R2.7), and otherwise exit with code 5 and a message naming the HTTP status and area.
9. THE SYSTEM SHALL document the accepted area codes (states, DC, territories, marine areas as listed by NWS) in the README; validation by pattern alone is intentional and unknown codes are handled by R1.8.

## R2. Caching, rate-limit courtesy and fallback
**User story:** As the site owner, I want caching, backoff and last-good fallback, so that outages never blank the site.

1. WHEN a fetch succeeds, THE SYSTEM SHALL write the raw response, the fetch timestamp and the area code to the on-disk cache.
2. WHILE the cached response is for the configured area and its age satisfies `0 <= age < minimum interval` (default 60 s, never configurable below 30 s), THE SYSTEM SHALL use the cache and make no request. A cache whose `fetched_at` is in the future (negative age) is never fresh. **[PBT]** (cache-freshness decision function)
3. IF the configured interval is below 30 s, THEN THE SYSTEM SHALL clamp it to 30 s.
4. IF the response is 429, 5xx, or a network error, THEN THE SYSTEM SHALL retry with exponential backoff plus full jitter, up to the capped number of attempts and the capped delay (defaults in R2.12). **[PBT]** (the delay ceiling `min(cap, base * 2^n)` is non-decreasing in n and bounded by the cap; each jittered delay lies in `[0, ceiling]`)
5. WHEN a 429 or 5xx response carries `Retry-After`, THE SYSTEM SHALL wait `max(Retry-After, jittered delay)` before the next attempt. IF `Retry-After` is greater than the delay cap, THEN THE SYSTEM SHALL stop retrying and treat the fetch as failed. **[PBT]** (parse of seconds and HTTP-date values; result is None or >= 0)
6. IF a 4xx other than 429 is returned, THEN THE SYSTEM SHALL NOT retry.
7. IF all attempts fail and a prior good cache for the same area exists, THEN THE SYSTEM SHALL build from the cache with `fallback=True`. Whether the data is also stale is decided only by its age (R10.3).
8. IF all attempts fail and no usable cache exists, THEN THE SYSTEM SHALL exit with code 3 (or 5 for R1.8), and SHALL publish only the `ALERT DATA UNAVAILABLE` notice site described in R10.8 so that a previously published site cannot keep presenting alerts as current. It SHALL NOT publish an empty "no active alerts" page. IF no site has ever been published, the notice site is still published.
9. IF the response body is not valid JSON or lacks a `features` list, THEN THE SYSTEM SHALL treat it as a failed fetch and SHALL NOT replace the cache with it.
10. THE SYSTEM SHALL key the cache by area: the cache file name includes the area code and the stored entry records it. A cache entry whose area differs from the configured area SHALL be treated as no cache. **[PBT]**
11. THE SYSTEM SHALL require, for the scheduled job, that the cache directory is persisted between runs (R14.5); a scheduled job configuration that does not persist the cache is non-conforming.
12. THE SYSTEM SHALL use these defaults, all in `Config`: `max_attempts` 4 (total tries, so at most 3 retries), `base_delay_s` 2.0, `max_delay_s` 60.0, `timeout_s` 20.0 per request.

## R3. Parse and tolerate missing data
**User story:** As a reader, I want a page even when some alert fields are absent, so that incomplete data does not hide an alert.

1. THE SYSTEM SHALL extract: id, event, severity, urgency, certainty, areaDesc, headline, description, instruction, onset, expires (falling back to `ends` when absent), senderName, and the source link.
2. WHEN a field is missing, null, or of the wrong type, THE SYSTEM SHALL substitute a defined placeholder (e.g. `NOT STATED`) rather than raise. **[PBT]** (arbitrary JSON feature dicts never raise)
3. WHEN severity is not one of Extreme, Severe, Moderate, Minor, Unknown, THE SYSTEM SHALL treat it as Unknown. **[PBT]**
4. WHEN a timestamp is unparseable, THE SYSTEM SHALL treat it as absent. **[PBT]**
5. WHEN a feature is not an object or has no `properties`, THE SYSTEM SHALL skip it and count it as skipped; the build continues.
6. THE SYSTEM SHALL normalise text: strip control characters, collapse NWS hard-wrapped single newlines into spaces while keeping paragraph breaks (two or more consecutive newlines), and map every non-ASCII character to ASCII using the explicit `ASCII_MAP` table in `text.py` (for example the degree sign to `DEG`, en/em dash to `-`, curly quotes to straight quotes, ellipsis to `...`, non-breaking space to a space), then NFKD-decompose and drop combining marks for letters not in the table, and finally replace any remaining character with `?`. The mapping is lossy by design and is documented. **[PBT]** (output has no control characters; idempotent; output is printable ASCII plus paragraph-break newlines; no single newline survives)
7. IF two alerts share a real id, THEN THE SYSTEM SHALL keep one. Alerts whose id is the missing-id placeholder (`NOT STATED`) are distinct alerts and SHALL NOT be collapsed together. **[PBT]**
8. THE SYSTEM SHALL keep onset and expires as timezone-aware values with the offset given by the source, and SHALL display them as `YYYY-MM-DD HH:MM +HH:MM` followed on the next row by the same instant in UTC (`= YYYY-MM-DD HH:MM UTC`), so a reader sees both the local time at the source and UTC. WHEN the source has no offset, THE SYSTEM SHALL treat the timestamp as unparseable (R3.4). **[PBT]** (display round-trips to the same instant)

## R4. Severity ordering
**User story:** As a reader, I want the most dangerous alerts first, so that I see them before the rest.

1. THE SYSTEM SHALL order alerts by severity (Extreme, Severe, Moderate, Minor, Unknown), then by soonest expiry (compared in UTC), then by id. **[PBT]** (result sorted by key; permutation of input)
2. WHERE expiry is absent, THE SYSTEM SHALL order that alert after those with expiry within the same severity. **[PBT]**
3. THE SYSTEM SHALL produce the same order for the same input regardless of input order. **[PBT]**
4. THE SYSTEM SHALL exclude alerts whose expiry is already past at build time.

## R5. Page numbering
**User story:** As a reader, I want predictable 3-digit page numbers, so that I can navigate like a remote control.

1. THE SYSTEM SHALL render the index of active alerts as page 888.
2. THE SYSTEM SHALL assign alert pages 889 upward, one per alert, in the order from R4. **[PBT]**
3. THE SYSTEM SHALL write page NNN to `site/NNN.html` and sub-page k>=2 to `site/NNN-k.html`, with relative links only. **[PBT]** (filename function)
4. THE SYSTEM SHALL number sub-pages from 1 (page NNN is sub-page 1) and display them as `NNN/k`. (Test: header row text on every sub-page equals `PNNN/k` form.)
5. THE SYSTEM SHALL keep every page number to exactly 3 digits.
6. IF the index does not fit on one page, THEN THE SYSTEM SHALL paginate it as 888/2, 888/3, ... .
7. IF the alert count exceeds the available page range (889-999, 111 alerts), THEN THE SYSTEM SHALL give pages only to the first 111 alerts in R4 order, and SHALL show on the last index sub-page one line `NOT SHOWN: n MORE - SEE WEATHER.GOV` plus a hyperlink to `https://www.weather.gov/`. It SHALL NOT produce a 4-digit number and SHALL NOT create extra alert pages. Accepted trade-off: the omitted alerts are the lowest in R4 order (least severe, latest expiry) and are not individually listed; the README records this limit. **[PBT]**
8. THE SYSTEM SHALL link each sub-page to previous, next (where they exist) and back to 888. **[PBT]** (link graph: every page reachable from 888, no dangling links)
9. THE SYSTEM SHALL show each alert's source id or link on its page and SHALL state that page numbers are not stable identifiers. (Test: both strings present on every alert page.)
10. THE SYSTEM SHALL write `index.html` as a byte-identical copy of `888.html` so the site root works without JS. Because they are the same document, `index.html` is exempt from the unique-title rule (R13.2).

## R6. 40x24 pagination without text loss
**User story:** As a reader on a small device, I want long alerts split across pages, so that nothing is cut off.

1. THE SYSTEM SHALL lay out every page on a grid of at most 40 columns by 24 rendered rows (see Definitions and R6.10), including header, status, navigation and footer rows. **[PBT]**
2. THE SYSTEM SHALL wrap text at word boundaries and hard-split words longer than 40 characters. **[PBT]**
3. WHEN content exceeds the body rows, THE SYSTEM SHALL continue it on sub-pages, and each continuation of a section SHALL be preceded by its label with `(CONT.)`. **[PBT]**
4. THE SYSTEM SHALL NOT drop or truncate any character of the alert text: the concatenated body text of all sub-pages, with `(CONT.)` labels and section labels removed and all whitespace removed, SHALL contain the normalised description followed by the normalised instruction, each with whitespace removed, in that order. **[PBT]**
5. THE SYSTEM SHALL NOT drop the `instruction` field to fit a page; instruction text SHALL appear in full under an `ACTION` label. WHEN the `instruction` field is absent or blank, THE SYSTEM SHALL show `NO INSTRUCTION FIELD IN SOURCE - SEE DESCRIPTION` under the `ACTION` label. **[PBT]**
6. WHERE a double-height headline is used, THE SYSTEM SHALL count it as 2 rows per line and fit at most 20 characters per line, falling back to normal height if it does not fit. **[PBT]**
7. THE SYSTEM SHALL use at most one double-height headline per page.
8. THE SYSTEM SHALL avoid orphaning a section label (e.g. `ACTION`) as the last row of a page. **[PBT]**
9. THE SYSTEM SHALL NOT split a page break mid-word, except that a single word longer than 40 characters is hard-split (R6.2). **[PBT]**
10. THE SYSTEM SHALL use these fixed row budgets, defined once in `layout.py`: header 1 row, body 13 rows, status block 5 rows, navigation 3 rows, footer 2 rows (total 24). These counts are maxima that cover the worst case (status block: `DATA AS OF`, `STALE DATA - CHECK WEATHER.GOV`, `LIVE UPDATE FAILED - SHOWING LAST GOOD DATA` wrapped to 2 rows, and the skipped-alerts line). A page may use fewer rows but never more in any block. `<nav>` and `<footer>` rows are part of the 24-row grid. **[PBT]**
11. THE SYSTEM SHALL emit each blank row as a CSS gap that counts as one rendered row, and SHALL count gaps when enforcing the 24-row limit. **[PBT]**

## R7. Rule-based summary
**User story:** As a reader, I want a short plain summary first, so that I can grasp the alert quickly.

1. THE SYSTEM SHALL produce a summary from CAP fields only (event, severity, urgency, certainty, areaDesc, expires, headline), using fixed templates and no runtime LLM.
2. THE SYSTEM SHALL state severity, urgency and certainty as words in the summary. **[PBT]**
3. THE SYSTEM SHALL produce a summary for any alert, including one with all optional fields missing. **[PBT]**
4. THE SYSTEM SHALL NOT add facts that are not present in the alert fields (the summary uses only source values or fixed words).
5. THE SYSTEM SHALL follow the summary with the full official description and instruction text. (Test: on every alert, row order is SUMMARY, DESCRIPTION, ACTION.)
6. THE SYSTEM SHALL be deterministic: same alert, same summary. **[PBT]**

## R8. HTML escaping and untrusted text
**User story:** As a reader, I want assurance that malicious alert text cannot inject markup.

1. THE SYSTEM SHALL HTML-escape all API-derived text, attribute values and URLs before output. **[PBT]** (strings containing `<>&"'` never appear unescaped)
2. THE SYSTEM SHALL only emit hyperlinks to the source alert when the URL parses with `urllib.parse.urlsplit` to scheme `https` with a non-empty host, and contains no whitespace or control characters; any other value SHALL be rendered as plain text. **[PBT]**
3. THE SYSTEM SHALL parse each generated page and find no element or attribute outside an explicit allowlist (`ALLOWED_ELEMENTS`, `ALLOWED_ATTRS` per element, defined in `verify.py`) that covers exactly what the templates emit. **[PBT]**
4. THE SYSTEM SHALL escape `href` and other attribute values with `html.escape(value, quote=True)`. **[PBT]**

## R9. No JavaScript, no external resources
**User story:** As a user with an old browser, I want pages that work with JS disabled.

1. THE SYSTEM SHALL NOT emit `<script>`, inline event-handler attributes, `javascript:` URLs, or `<noscript>`. **[PBT]** (over generated alerts)
2. THE SYSTEM SHALL emit only inline CSS and SHALL NOT reference external CSS, fonts, images, iframes or other external resources; the only external URLs are the visible `<a href>` link to the source alert and the `https://www.weather.gov/` link (R5.7, R11.5).
3. WHEN verifying output, THE SYSTEM SHALL fail the build if any rule in this requirement is violated.
4. THE SYSTEM SHALL use no `<meta http-equiv="refresh">`.

## R10. Stale, empty and error states
**User story:** As a reader, I want to know how fresh the data is and when there is nothing to report.

1. THE SYSTEM SHALL show `DATA AS OF <YYYY-MM-DD HH:MM> UTC` (fetch time of the data used) in the status block of every page. **[PBT]**
2. WHEN there are no active alerts for the area and the data is neither stale nor fallback, THE SYSTEM SHALL render page 888 with `NO ACTIVE ALERTS FOR <AREA>`, and SHALL still show the disclaimer and source link.
3. WHILE the data in use is older than the stale threshold (default 30 minutes since fetch), or its fetch time is in the future, THE SYSTEM SHALL show `STALE DATA - CHECK WEATHER.GOV` on every page, in text, in addition to any colour. **[PBT]** (threshold function)
4. IF the build used the cache because the fetch failed (fallback), THEN THE SYSTEM SHALL show `LIVE UPDATE FAILED - SHOWING LAST GOOD DATA` on every page, whether or not the data is also stale.
5. THE SYSTEM SHALL NOT present the `NO ACTIVE ALERTS` page when the cause is a fetch failure with no data (see R2.8, R10.8).
6. THE SYSTEM SHALL show how many alerts were skipped as unparseable, when more than zero.
7. WHILE the data is stale or fallback and no unexpired alerts remain, THE SYSTEM SHALL render page 888 with `NO UNEXPIRED ALERTS IN LAST GOOD DATA` instead of `NO ACTIVE ALERTS`, directly followed by the stale and/or fallback banner rows.
8. WHEN there is no data and no usable cache (R2.8), THE SYSTEM SHALL build a notice site consisting of `888.html` and `index.html` only, whose body reads `ALERT DATA UNAVAILABLE - CHECK WEATHER.GOV` with the disclaimer and a link to `https://www.weather.gov/`, and SHALL carry no alert content and no `NO ACTIVE ALERTS` text.

## R11. Attribution and disclaimer
**User story:** As the site owner, I must not imply official status.

1. THE SYSTEM SHALL show on every page the text `NOT AN OFFICIAL WARNING CHANNEL` in the footer rows. **[PBT]**
2. THE SYSTEM SHALL attribute the data to the US National Weather Service (api.weather.gov) as source, without implying endorsement.
3. THE SYSTEM SHALL show sender (`senderName`) and a link to the source alert on each alert page.
4. THE SYSTEM SHALL NOT use broadcaster names or logos, including "Ceefax". (Test: scan generated output and docs for a denylist.)
5. THE SYSTEM SHALL point readers to local official channels (NWS, weather.gov) in the footer text of page 888, with a link to `https://www.weather.gov/`.

## R12. Size budget
**User story:** As a user on a metered connection, I want small pages.

1. THE SYSTEM SHALL keep each generated page under 50 KB (51,200 bytes, measured as the UTF-8 encoded length) including inline CSS. **[PBT]** (worst-case generated alerts)
2. IF any page is at or above the budget, THEN THE SYSTEM SHALL fail the build and SHALL NOT publish.
3. THE SYSTEM SHALL report the largest page size in the build log, and the README SHALL quote the CSS size only as measured after a build.

## R13. Accessibility (WCAG 2.2 AA intent)
**User story:** As a screen-reader or low-vision user, I want a well-structured, high-contrast page.

1. THE SYSTEM SHALL set `<html lang="en">` on every page.
2. THE SYSTEM SHALL give every page a unique, descriptive `<title>` (page number plus title), except `index.html`, which is identical to `888.html` by R5.10. **[PBT]**
3. THE SYSTEM SHALL include exactly one `<h1>` per page, including index sub-pages and alert sub-pages with k>=2. **[PBT]**
4. THE SYSTEM SHALL place content in a single `<main>` and SHALL provide a `<nav>` with an `aria-label`; where several navs exist, labels SHALL be distinct. **[PBT]**
5. THE SYSTEM SHALL use link text that is meaningful out of context and includes the page number and title (never "click here"). **[PBT]**
6. THE SYSTEM SHALL generate all CSS colour pairs only from an explicit `ALLOWED_PAIRS` list (foreground, background) in which every pair has a computed contrast of at least 4.5:1, and SHALL NOT use any other pair, for normal or large text. The list is: on black: white, yellow, cyan, green, magenta, red; on white: black, blue; on red: black; on green: black, blue; on yellow: black, blue; on blue: white, yellow, cyan, green; on cyan: black, blue; on magenta: black. All other 44 of the 64 foreground/background combinations (including blue on black, white on red, red/magenta/black on blue, and every pair with equal colours) are forbidden. **[PBT]** (all 64 combinations: pair in the list iff computed ratio >= 4.5; CSS contains only listed pairs)
7. THE SYSTEM SHALL state severity in text on every alert page and index row, so that meaning does not depend on colour. **[PBT]**
8. THE SYSTEM SHALL NOT use blinking, flashing or animation (no `@keyframes`, no `animation`, no `transition`). (Static CSS check.)
9. THE SYSTEM SHALL provide a visible focus indicator on all links and SHALL NOT remove outlines (no `outline:none` or `outline:0`). (Static CSS check.)
10. THE SYSTEM SHALL make all navigation operable by keyboard, with link targets of at least 24x24 CSS px (CSS rule `min-height` and `min-width` of at least 24px on `a`). (Static CSS check.)
11. THE SYSTEM SHALL size the grid in `ch` units, with no fixed pixel layout for the grid width, so that content reflows and stays usable at 200% zoom. (Static CSS check: `ch` present on `.tt`; no `px` width on `.tt` or `.row`.)
12. THE SYSTEM SHALL use CSS for decorative spacing and SHALL NOT emit empty elements or runs of `&nbsp;`. **[PBT]**
13. THE SYSTEM SHALL NOT apply `aria-hidden` to real content.
14. WHERE a double-height headline is used, THE SYSTEM SHALL render it as the single `<h1>` via CSS scaling, with no duplicated text. (Test: h1 text appears once.)
15. THE SYSTEM SHALL include `<meta name="viewport" content="width=device-width, initial-scale=1">` and SHALL NOT include `user-scalable=no` or `maximum-scale`. (Static check.)
16. THE SYSTEM SHALL set body, `a`, `a:visited`, `a:hover` and the focus outline colours explicitly from `PALETTE` and `ALLOWED_PAIRS` (links are cyan on black), so that no browser-default link or page colours appear anywhere on the page, including `<nav>` and `<footer>`. **[PBT]**
17. THE SYSTEM SHALL group each logical paragraph of text into one `<p>` whose wrapped rows are `<span class="row">` children, SHALL render section labels as `<h2>`, and SHALL render the index as a list, so that screen readers read sentences without pauses at the 40-column breaks. **[PBT]** (no sentence-internal row boundary is a paragraph boundary: one `<p>` per source paragraph)
18. THE SYSTEM SHALL accept that rows reflow on viewports narrower than 40 characters (WCAG 1.4.10 Reflow) and that row alignment is then not preserved; the font stack SHALL be `monospace, monospace` so the browser does not shrink the font. The 24-row guarantee is a property of the generated markup, not of the rendered viewport.
19. THE SYSTEM SHALL use the focus outline colour yellow `#ffff00` and SHALL place links only on black or blue backgrounds, where yellow gives at least 3:1 (19.6:1 on black, 8.0:1 on blue). **[PBT]**

## R14. Build, schedule and hosting
**User story:** As the site owner, I want an automatic, free, static deployment.

1. WHEN `python -m page888` runs, THE SYSTEM SHALL execute fetch, parse, normalise, summarise, paginate, render, verify, then publish, in that order. (Test: stage-order spy.)
2. THE SYSTEM SHALL build into a sibling temporary directory on the same filesystem and publish only after verification passes, by directory swap: rename `site` to `site.old`, rename the temporary directory to `site`, then delete `site.old`. The swap is not strictly atomic; there is a short window between the two renames in which `site` does not exist. On start-up THE SYSTEM SHALL recover: if `site` is missing and `site.old` exists, rename `site.old` back to `site`; if both exist, delete `site.old`. **[PBT]** (failed verify leaves previous site byte-identical, tested with a temp dir; simulated crash between renames is recovered)
3. IF verification fails, THEN THE SYSTEM SHALL keep the previous `site/` and exit non-zero.
4. THE SYSTEM SHALL remove stale page files from the previous build on a successful publish (e.g. 889-3.html when no longer needed).
5. THE SYSTEM SHALL run on a schedule no tighter than the minimum interval in R2.2, SHALL persist the cache directory between scheduled runs (R2.11), and SHALL be hostable on a free static host with no server-side runtime.
6. THE SYSTEM SHALL use only the Python standard library at runtime; pytest and hypothesis are development-only. (Test: scan `src/page888` imports against `sys.stdlib_module_names`.)
7. THE SYSTEM SHALL NOT include analytics, tracking, cookies or accounts.
8. WHERE the host requires committed output, `site/` MAY be committed by the scheduled job; otherwise it SHALL be gitignored.
9. THE SYSTEM SHALL ensure tests never access the network and use fixture CAP JSON under `tests/fixtures/`.
10. THE SYSTEM SHALL log a one-line build summary (area, alert count, skipped, pages, largest page bytes, data age) without logging the User-Agent value.
11. THE SYSTEM SHALL ship `tools/check_pages.py` as a fast, standalone, stdlib-only subset of `verify.py` for editor hooks and the QA agent. `verify.py` is the authoritative check; every violation `check_pages.py` reports SHALL also be reported by `verify_site`. **[PBT]**
