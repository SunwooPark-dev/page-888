<!-- teletext-qa custom agent via Kiro CLI 3.3.0, 2026-11-13, round 2 re-review, read-only tools. Saved verbatim from the agent output. Coordinator note on N2: each action's latest release was checked with gh api on 2026-11-13: checkout v7.0.1, setup-python v7.1.0, cache v6.1.0, upload-pages-artifact v5.0.0, deploy-pages v5.0.1, so the major tags exist; SHA pinning is still open. -->

# Page 888 review, round 2

Verdict: no open High finding (PASS at the end). I did not modify files or run git or shell. I cite the coordinator's results:

- `.venv/bin/pytest -q` → 399 passed in 10.74s
- `python3 tools/check_pages.py site --strict` → check_pages: 342 file(s), 0 failed

I read `fetch.py`, `paginate.py`, `render.py`, `verify.py`, `parse.py`, `build.py`, `cache.py`, `models.py`, `layout.py`, `pages.yml`, `tools/check_pages.py`, and `site/index.html`, `889.html`, `889-2.html` and `889-6.html`. I confirmed that most cited tests exist by name (grep output was truncated, so I did not see every one). I did not read test bodies, so I cannot say the new tests are strong. I can't verify the pinned action versions (`checkout@v7`, `cache@v6`, `upload-pages-artifact@v5`, `deploy-pages@v5`) or the pinned `pytest==9.2.0` and `hypothesis==6.170.15`.

## Round-1 findings

| # | Verdict | Evidence |
|---|---------|----------|
| 1 mid-body network error crashes the build | VERIFIED FIXED | `fetch.py:111-114` catches `(URLError, OSError, http.client.HTTPException)` and retries. `resp.read()` sits inside the `try` (`fetch.py:96-97`). The give-up path raises `FetchError` (`fetch.py:118`), and `cache.get_data` falls back on `FetchError`. Tests: `test_fetch.py:250`, `:258`, `test_build.py:337`. |
| 2 truncated index labels | VERIFIED FIXED | `paginate.truncate_words` (`paginate.py:62-77`) cuts at a word, adds `...` and leaves no space before it. `_index_rows` (`paginate.py:~213-222`) uses it for the area and the link label. `site/index.html` now shows "Yosemite NP outside..., EXP 11-13 18:00" and "Lassen Volcanic..., EXP …". The link label still loses its tail, but the full title is on the target page. That is acceptable. |
| 3 truncated prev/next labels | VERIFIED FIXED | `_link` (`paginate.py:~290-295`) keeps `PREV 889/5` whole and strips `(CONT. k/n)` through `_CONT_SUFFIX`. `site/889-2.html` shows "PREV 889/1 Winter Storm Warning" and "NEXT 889/3 Winter Storm Warning". |
| 4 notice site says "DATA AS OF" | VERIFIED FIXED | `build.py:34` uses `DataStatus(None, …)`. `paginate.status_rows` (`paginate.py:345-346`) emits `NO ALERT DATA AVAILABLE` when `fetched_at is None`. The type is `datetime \| None` (`models.py:69`). Tests: `test_build.py:364`, `test_paginate.py:420`. |
| 5 index expiry has no date | VERIFIED FIXED | `paginate.py:~213-216` shows `EXP {local[5:16]}`, for example `EXP 11-13 18:00` in `site/index.html`. Test: `test_paginate.py:428`. |
| 6 EXPIRES vs event end | PARTIAL | Alert pages are fixed. `parse.py:~84-88` stores `ends` and `message_expires` separately. `paginate.py:~166-167` shows `MESSAGE EXPIRES` and `ENDS` as separate rows, with `ENDS NOT STATED` when absent. `889.html` now reads "MESSAGE EXPIRES 2026-11-13 18:00". The index still says plain `EXP 11-13 18:00` for an event whose headline runs until Nov 17. See N1. |
| 7 tests gate the scheduled refresh | VERIFIED FIXED | `pages.yml:43-46` has `if: github.event_name != 'schedule'` on "Run tests". Test: `test_build.py:262`. |
| 8 hard-coded personal handle | VERIFIED FIXED | `pages.yml:22` is `Page888 (${{ github.server_url }}/${{ github.repository }})`. Test: `test_build.py:251`, which scans `.github/`. |
| 9 source URL split and spaced | VERIFIED FIXED | `_token_items` (`paginate.py:~148-155`) chunks the ID row and marks continuation rows `join`. `render._runs` (`render.py:~92-96`) omits the space for `join` rows. The link is named `SOURCE ALERT JSON (api.weather.gov)` and preceded by `LINK BELOW OPENS RAW JSON DATA`, with a hold so they stay together (`site/889-6.html`). The raw URL is no longer printed. |
| 10 no row or column check in `verify_site` | VERIFIED FIXED | `verify.py` counts `.row` elements, counts `.gap` spacers, counts rows inside `h1.dh` twice (`_Checker.handle_starttag`), and fails when the count exceeds `ROWS` (`verify_page`). It also fails on row text over `COLS` (`handle_endtag`). Tests: `test_verify.py:263-299`. `tools/check_pages.py` has no row check, which matches the stated "subset" design (see N4). |
| 11 rows run together | VERIFIED FIXED | `render._footer` and `_item` join with `" "`. `site/index.html` and `889-2.html` show spaces between the spans. Tests: `test_render.py:382`, `:389`. |
| 12 source URL allow-list | NOT FIXED (deferred) | `parse.https_url_or_empty` (`parse.py:~56-68`) still accepts any https host, including userinfo. The mitigation is real: the raw URL is no longer displayed, the label is host-only and ASCII-only (`_source_label`), and the link is escaped. `test_render.py:400` is a hypothesis test that hostile URLs never become links. Low severity, so the deferral is accepted. |
| 13 conservative index cap | NOT FIXED (deferred) | `paginate.py:~270` still sizes `cap_rest` for the worst-case title. `site/index.html` shows 6 alerts per sub-page (1/8). Low, and not a rule violation. |
| 14 `lang="en"` on ASCII-folded text | PARTIAL | `docs/README.md:55-56` documents the limitation and says "Not fixed yet". The page markup is unchanged, which is fine for a Low finding. |

## Tests that did not test what they claimed (round 1)

- **Attribution test (`or "SOURCE"`):** `test_build.py:313` was renamed and rewritten. I did not read its body.
- **`len(...) == 1 or …` test:** `test_build.py:81` was rewritten. I did not read its body.
- **Broadcaster denylist:** `test_build.py:291` and `:307` exist. I did not read their bodies.
- **Link tests:** the new word-boundary properties exist (`test_paginate.py:349`, `:398`, `test_render.py:354`).
- **`alerts_st` hostile URLs:** `test_render.py:400` exists.
- **Notice `DATA AS OF` test:** `test_build.py:364` and `test_paginate.py:420` exist.

All of these are present by name. Their strength is unverified because I did not read the bodies.

## New issues (High or Medium)

No new High issues.

- **N1, Medium (residual of #6): the index shows message expiry as `EXP` and never the event end.**
  - Where: `paginate.py:~213-216`, and `parse.py:88` (`expires = message_expires or ends`).
  - Evidence: `site/index.html` shows `889 … EXP 11-13 18:00`, while the alert's headline says "until November 17 at 4:00AM". Index readers still see "expires tonight" for a multi-day warning.
  - Requirement: R3.1 and R3.8 ordering is fine. This is the same readability concern as r1 #6 (safety-relevant, not a hard R violation).
  - Fix: label the index value `MSG EXP`, or show `ENDS MM-DD HH:MM` when `ends` is present and later than the message expiry. Add a test that the index never presents `message_expires` as the event end.

- **N2, Medium (process): the workflow action versions are unverifiable.**
  - Where: `pages.yml:36`, `:39`, `:50`, `:67`, `:75`, `:79`, `:84`.
  - Evidence: `checkout@v7`, `setup-python@v7`, `cache/restore@v6`, `cache/save@v6`, `upload-pages-artifact@v5` and `deploy-pages@v5` all use floating major tags. If a tag does not exist, every scheduled run fails and the live site freezes without a stale banner.
  - Requirement: tech.md says to pin exact versions and flag unusual dependencies.
  - Fix: confirm each tag exists, and pin by full commit SHA. The workflow's first scheduled run is still unseen (task 17.3).

## Low observations (no action needed for PASS)

- **N3:** The `a:hover` rule (specificity 0,1,1) overrides `.row{display:block}` on `<a class="row">`, so a hovered nav link switches to `inline-block` (`render.py` CSS, `a,a:visited,a:hover{…display:inline-block}`). The risk is a hover layout shift, not a violation. Fix: put the `display` property on `a` only, not on `a:hover`.
- **N4:** `tools/check_pages.py` still has no row or column check, so a row-count regression is caught only by `verify_site` at build time. This matches the "fast subset" design, but the workflow's `--strict` step does not cover it.
- **N5:** `889-6.html` is a page that holds only the source link, because of the `hold` logic.
- **N6:** `render._runs` puts a leading space inside an `<a>` before the first span when a link follows a non-link row (`889-6.html`). It is harmless.

## Checked and fine

- **Escaping:** `esc` uses `quote=True` on all text and hrefs.
- **Page budgets and structure:** every page I read has one `h1`, `lang`, a unique title, one `main` and a labelled `nav`. No `aria-hidden`.
- **Colour and zoom:** CSS colour pairs come only from `ALLOWED_PAIRS`. The grid is `40ch` with `max-width:100%`.
- **No JavaScript or external resources:** there is no `<script>`, no handlers and no external resources. The only external links are the `https` source-alert `<a href>` and weather.gov.
- **Runtime dependencies:** `fetch.py` imports only the standard library.
- **Status row budget:** worst-case status rows are 5 (1 + 1 + 2 + 1), within `STATUS_ROWS`.
- **Caching and fetching:** the cache is keyed by area and stored atomically. `fetch.py` sends lowercase `status=actual` and honours `Retry-After` against the cap. Non-transient 4xx errors are not retried.
- **Deploy gating:** the workflow deploys only on exit codes 0, 3 and 5, and fails the job when the exit code is not 0.

**PASS** (no open High; N1 and N2 are Medium and should be handled next)
