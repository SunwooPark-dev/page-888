<!-- teletext-qa custom agent (.kiro/agents/teletext-qa.json) via Kiro CLI 3.3.0, 2026-11-13, read-only tools. Saved verbatim from the agent output. -->

# Page 888 review

**Verdict: FAIL.** Three findings are High or Medium-High, and several others break explicit R-numbers.

I did not re-run anything. I used the coordinator's results (`pytest -q` → 358 passed; `check_pages.py site --strict` → 353 files, 0 failed) and read the source, the tests and `site/index.html`, `889.html`, `889-2.html` and `889-6.html`. I also read `888.html`'s alias `index.html` and the index sub-page markup only through `index.html`. I could not verify that the action versions in `pages.yml` exist, such as `checkout@v7` and `cache@v6`. I also could not verify the pinned `pytest==9.2.0` and `hypothesis==6.170.15`.

## High

1. **A mid-body network error skips the cache fallback and crashes the build.**
   - `src/page888/fetch.py`, the `except (urllib.error.URLError, OSError)` clause in `fetch_alerts`. Violates R2.4 and R2.7.
   - Problem: `resp.read()` can raise `http.client.IncompleteRead` or `BadStatusLine`. Both derive from `HTTPException`, not `OSError`.
   - Neither is caught in `fetch_alerts`, `get_data` (catches only `FetchError` and `FeedError`) or `build`.
   - The result is a traceback and exit 1. The cached data is not used and nothing is retried. The workflow then treats exit 1 as "no deploy", so the site freezes. Page text is built at generation time, so it carries no stale banner.
   - Fix: catch `http.client.HTTPException` next to `OSError` in `fetch_alerts` so it is retried and then raised as `FetchError`. Add a test whose opener raises `IncompleteRead`.

## Medium

2. **Truncated index labels cut mid-word with no marker.**
   - `paginate.py:195-205`, `_cut` and `_index_rows`. Violates R13.5, and R6.4 in spirit.
   - Evidence from the live build in `site/index.html`: "Yosemite NP outside of," (should be "…of the valley"), "Greater Lake Tahoe Are,", "Lassen Volcanic Nation," and "Eastern Sierra Slopes ," (stray space before the comma).
   - The link text `f"{number} {severity} {event}"` is hard-cut at 40 columns. A long event such as "Small Craft Advisory For Hazardous Seas" loses its tail, so the link name is wrong.
   - Fix: cut at a word boundary with an ellipsis, and `rstrip()` before the comma. For the link row, shorten the severity or event words, or let it wrap onto 2 rows inside the `<a>`.

3. **Truncated prev/next labels.**
   - `paginate.py:265-268`, `_link`. Same requirements as finding 2.
   - Site evidence: "NEXT 889/2 Winter Storm Warning (CONT. 2" and "PREV 889/5 Winter Storm Warning (CONT. 5".
   - The label is `_cut` to 40 columns, which drops the "/6)" part and ends mid-token.
   - Fix: build the label as a fixed prefix `PREV 889/5` plus the title, and shorten the title to the remaining space with `...`. Or drop the title on continuation pages, since the number carries the meaning.

4. **The notice site claims "DATA AS OF <now>".**
   - `build.py:35`, `_publish_notice`: `DataStatus(now, False, False, 0)`. Violates R10.1 and R10.8 (a notice must not imply data exists).
   - Every page, including the "ALERT DATA UNAVAILABLE" page, shows `DATA AS OF <build time> UTC` via `status_rows`. That reads as fresh data when there is none.
   - No test covers it. `test_index_html_byte_identical_for_notice` only checks the notice text.
   - Fix: add `DataStatus.fetched_at: datetime | None`, or a `notice` flag, and make `status_rows` emit no "DATA AS OF" line for notices. Assert its absence in a test.

5. **The index shows only the clock time of the expiry, not the date.**
   - `paginate.py:199-205`: `exp = f"EXP {local[11:]}"`. Related to R3.8.
   - For multi-day alerts the date is lost. `889` shows "EXP 18:00 -08:00" on the index, but its headline says "until November 17 at 4:00AM".
   - Fix: show `EXP MM-DD HH:MM` (at least when the date is not the build date) and keep the 40-column limit.

6. **"EXPIRES" can contradict the event end.**
   - `parse.py:88`: `expires = parse_time(expires) or parse_time(ends)`.
   - On `889-1`: "EXPIRES 2026-11-13 18:00 -08:00" sits next to "HEADLINE …until November 17 at 4:00AM PST". `expires` is the message expiry. `ends` is the event end.
   - The spec's fallback rule (R3.1) is followed, but a reader will take "EXPIRES tonight" as the end of the warning. This is a public-safety readability problem.
   - Fix: keep `expires` for ordering and filtering, and also parse `ends`. Show `ENDS` as a separate DETAILS row (`ENDS NOT STATED` when absent). Rename the summary word to `MESSAGE EXPIRES` or add `ENDS`.

7. **Test gate in the scheduled workflow.**
   - `.github/workflows/pages.yml:43-45`, "Run tests". Relates to R10.3 and R14.5.
   - Every 30-minute scheduled run runs `pytest -q` first, with hypothesis. A flaky property test or a health-check failure stops the whole refresh, and nothing is deployed.
   - The published pages then age without any stale banner, because the banner is computed at build time. `verify_site` and `check_pages` already gate the output.
   - Fix: add `if: github.event_name != 'schedule'` to the test step. Optionally also use `if: always()` plus a separate alert job.

8. **A personal handle is hard-coded in the workflow.**
   - `pages.yml:22`: `Page888 (https://github.com/SunwooPark-dev/page-888)`. Violates R1.3 and the "never hardcode a personal contact" rule in tech.md.
   - `test_no_hardcoded_user_agent_in_src` (`tests/test_build.py:244`) scans only `src/`, so it cannot catch this.
   - Fix: use `Page888 (${{ github.server_url }}/${{ github.repository }})` or a repository variable (`vars.PAGE888_USER_AGENT`). Extend the test to scan `.github/`.

9. **Link text and copy/paste break on the source URL.**
   - `paginate.py:167`, `render.py` `_runs` (the `" "` joiner).
   - The URL is hard-split across rows and the rows are joined with a space inside one `<a>`. In `889-6` the accessible name and copied text read "…urn:oid:2 .49.0.1.840.0.6d93… 75bd…". The same happens to the `ID …` row.
   - The target is `api.weather.gov/alerts/urn:oid:…`, which returns raw GeoJSON, not a readable page. Screen-reader and old-phone users get JSON.
   - Fix: join the continuation rows of one unbreakable token without a space (use a `<wbr>`-free approach such as a single `.row` with `overflow-wrap:anywhere`). Give the link a short accessible name such as `SOURCE ALERT (api.weather.gov)`. Consider a human-readable target, or say in the page that the link opens JSON.

## Low

10. **No row or column check in `verify_site`.**
    - `verify.py`. R6.1 and the "generator must fail the build" intent.
    - `verify_site` checks size, structure and CSS only. It never counts `.row` and `.gap` elements (24) or measures row text (40). Those limits are enforced only by tests over the pagination model.
    - A regression in `render.py` would ship, and `check_pages.py` would not notice.
    - Fix: count rows per page in `_Checker`, with `.dh` rows counting twice, and fail the build on more than 24 rows or on row text over 40.

11. **Rows run together where the CSS `display:block` is not applied.**
    - `render.py:177`, `_footer`, and `_item` in `_body` (index `<li>`).
    - The footer and the index items concatenate rows with no whitespace: "WARNINGYosemite…", "CHANNELSOURCE: US NWS…". `_runs` adds `" "` but these two paths do not.
    - Text-mode browsers and reader views show the words run together.
    - Fix: join with `" "` in both places.

12. **Source URL is checked loosely and displayed unnormalised.**
    - `parse.py` `https_url_or_empty`. Spec-conformant (R8.2), but permissive.
    - It accepts any host, userinfo (`https://weather.gov@evil.example/`) and non-ASCII characters. `paginate.py:167` shows the raw URL, bypassing `normalise_text`, so a wide character can break the 40-column grid.
    - Fix: require ASCII, reject `@` in the netloc, and ideally allow only `weather.gov` and its subdomains.

13. **Index pagination is conservative.**
    - `paginate.py`, `cap_rest` is computed with the worst-case title (2 rows).
    - Page `889-2` leaves a spare row, and the index shows only 6 alerts per sub-page (9 sub-pages for about 50 alerts). Not a violation, but a reader needs many clicks.
    - Fix: compute the cap from the real title of each sub-page.

14. **`lang="en"` on text that has been ASCII-folded.**
    - `text.py`, `normalise_text`. Spanish NWS text loses its accents, or gets "?" for unmapped characters, and is still labelled English.
    - Fix: document this limitation in `docs/`.

## Tests that do not test what they claim

- **`tests/test_build.py:274`:** `assert "https://api.weather.gov/alerts/" in alert_page or "SOURCE" in alert_page`. "SOURCE:" is in the footer of every alert page, so this can never fail. It does not test R11.3 or R5.9. Assert the `<a href>` and the `ID` row instead.
- **`tests/test_build.py:84`:** `assert len(...) == 1 or "889-2.html" in ...`. The `or` branch makes the first half weak. Only the "890.html absent" line tests anything.
- **`tests/test_build.py:263`:** the broadcaster denylist skips any line containing "no", "not" or "never". A line such as "Ceefax-style, no JavaScript" passes. It also scans only `docs/*.md`, not `README.md`, `.kiro/` or `src/`.
- **`tests/test_paginate.py:247` and the `test_link_text_is_meaningful` test in `test_render.py`:** they assert only `len(link.text) <= 40` and "contains a 3-digit number". That lets the truncated labels in findings 2 and 3 pass. There is no test with a long event or area in the index, and no test that checks for a word-boundary cut.
- **`alerts_st` in `tests/test_paginate.py`:** `source_url` is drawn from two safe values. R8.2's property test (hostile URLs never become a link) is therefore only covered by hand-picked examples in `test_non_https_source_is_plain_text`.
- **Notice tests:** nothing asserts that "DATA AS OF" is absent on the notice site (finding 4).

## Checked and fine

- **Escaping:** `esc` uses `quote=True` on every API-derived string and every `href`. The `ALLOWED_ELEMENTS` and `ALLOWED_ATTRS` allowlist is enforced in `verify.py`.
- **No-JS rules:** no script, no handlers, no external resources. Links are limited to relative page files or https. `javascript:` values are flagged.
- **Row budgets:** header 1, body 13, status 5, navigation 3, footer 2 (sum 24, asserted in `layout.py`). The pages I read stay inside them.
- **Instruction text:** `ACTION` is never dropped. When the field is absent the page shows `NO INSTRUCTION FIELD IN SOURCE - SEE DESCRIPTION`.
- **Page structure:** every page I read has one `h1`, `lang`, a unique title, one `main` and a labelled `nav`.
- **Colours and zoom:** CSS colours come only from `ALLOWED_PAIRS`. The grid width is in `ch`.
- **Cache and fallback:** the cache is keyed by area. Fresh, stale and fallback decisions follow R2.2, R2.7 and R10.3.
- **Publish and workflow deploy:** the directory swap with crash recovery matches R14.2. The workflow deploys only on exit 0, 3 or 5 and then fails the job when the exit code is not 0.

**FAIL**
