# Tasks: Page 888

Test-first where practical: write the test (or property) named in the task, see it fail, then implement. Each task ends with `pytest -q` passing.

- [x] 1. Project scaffold (R14.6, R14.9)
  - [x] 1.1 Create `src/page888/__init__.py`, `__main__.py`, `pyproject.toml` (no runtime deps; dev extras pytest, hypothesis), `.gitignore` (`.cache/`, `.venv/`, `site/` unless host needs it)
  - [x] 1.2 `tests/conftest.py` blocking network (socket connect guard) and shared hypothesis settings
  - [x] 1.3 Add fixtures in `tests/fixtures/`: normal, long-instruction, nulls/wrong types, Test status, hostile text, empty, many alerts (more than 111), a recorded HTTP 400 body for `status=Actual`

- [x] 2. Config (R1.1-R1.3, R1.5, R2.3, R2.12)
  - [x] 2.1 Tests: UA unset/blank raises `ConfigError`; `test_prop_valid_area` (exactly `^[A-Z]{2}$`); interval clamped to >= 30 s; defaults `max_attempts` 4, `base_delay_s` 2.0, `max_delay_s` 60.0, `timeout_s` 20.0
  - [x] 2.2 Implement `config.py` (`Config`, `load_config`, `valid_area`; env vars `PAGE888_USER_AGENT`, `PAGE888_AREA`, `PAGE888_OUT`, interval/stale settings)

- [x] 3. Data models and parsing (R1.7, R3)
  - [x] 3.1 Define `Severity`, `Alert`, `Row`, `SubPage`, `Page`, `DataStatus` in `models.py` (tz-aware times)
  - [x] 3.2 Tests: `test_prop_parse_never_raises`, `test_prop_severity_total`, `test_prop_parse_time` (tz-aware or None; no offset gives None), status != `Actual` dropped (the response value is capitalised `Actual`); invalid top-level raises `FeedError`
  - [x] 3.3 Implement `parse.py` with placeholders for missing fields, `expires` fallback to `ends`, https source URL checked with `urllib.parse.urlsplit` (non-empty host, no whitespace or control characters)

- [ ] 4. Text normalisation and wrapping (R3.6, R3.8, R6.2)
  - [ ] 4.1 Tests: `test_prop_normalise_idempotent_no_control`, `test_prop_normalise_ascii_only`, `test_prop_normalise_newlines` (single newline becomes a space, two or more survive as a paragraph break), `ASCII_MAP` examples (degree sign to `DEG`), `test_prop_wrap_width_and_preserves_chars`, `test_prop_format_time_roundtrip`
  - [ ] 4.2 Implement `text.py` (`ASCII_MAP`, `normalise_text`, `wrap`, hard-split of long words, `format_time`)

- [ ] 5. Ordering (R3.7, R4)
  - [ ] 5.1 Tests: `test_prop_order_sorted_permutation` (UTC comparison across offsets), `test_prop_order_input_invariant`, dedupe by id, expired excluded, missing expiry last in severity group
  - [ ] 5.2 Implement `order.py`

- [ ] 6. Summaries (R7)
  - [ ] 6.1 Tests: `test_prop_summary_total_deterministic`, includes severity/urgency/certainty words, no text beyond fields and fixed words
  - [ ] 6.2 Implement `summarise.py`

- [ ] 7. Layout constants and pagination (R5, R6). Do 7.1 before any other part of this task.
  - [ ] 7.1 Define `layout.py` first: `COLS=40`, `ROWS=24`, `HEADER_ROWS=1`, `BODY_ROWS=13`, `STATUS_ROWS=5`, `NAV_ROWS=3`, `FOOTER_ROWS=2`, with an import-time assert that they sum to 24. Tests: constants sum to `ROWS`; worst-case status text (`DATA AS OF` line, `STALE DATA - CHECK WEATHER.GOV`, `LIVE UPDATE FAILED - SHOWING LAST GOOD DATA` wrapped, skipped line) wraps to at most `STATUS_ROWS`; footer and nav worst-case text fit their rows at 40 columns (R6.10)
  - [ ] 7.2 Tests: `test_prop_assign_numbers`, `test_prop_filename`, `test_prop_grid_bounds` (rows plus gaps, double-height counted twice), `test_prop_no_text_lost` (in-order contains of description then instruction), `test_prop_instruction_complete` (including absent-instruction text), `test_prop_no_orphan_label`, `test_prop_double_height_rules`, `test_prop_continuation_labels`
  - [ ] 7.3 Implement `paginate_alert` (blocks, flow, label orphan rule, `(CONT.)` labels, double-height headline, h1 text for k=1 and k>=2, header `PNNN/k`)
  - [ ] 7.4 Tests then implement `paginate_index` (888/k, h1 text for k>=2, overflow line `NOT SHOWN: n MORE - SEE WEATHER.GOV` with `https://www.weather.gov/` link, empty state, `NO UNEXPIRED ALERTS IN LAST GOOD DATA` in stale/fallback mode), `paginate_notice` (R10.8) and `build_site_model`; `test_prop_order_follows_ordering` (P8 ordering clause)
  - [ ] 7.5 Test `test_prop_link_graph` (reachability, prev/next/888 links, no dangling targets); implement `NavContext`/links
  - [ ] 7.6 Example tests: header text `PNNN/k` on every sub-page (R5.4); alert page shows source id/link and "page numbers are not stable" text (R5.9); row order SUMMARY, DESCRIPTION, ACTION (R7.5); `index.html` byte-identical to `888.html` (R5.10)

- [ ] 8. Rendering (R8, R9, R10.1, R10.3, R11, R13)
  - [ ] 8.1 Implement `palette.py` (`PALETTE`, `contrast_ratio`, explicit 20-pair `ALLOWED_PAIRS`) before anything else in this task. Test `test_prop_palette_contrast`: for all 64 fg/bg combinations, membership in `ALLOWED_PAIRS` iff computed ratio >= 4.5; spot-check yellow on blue = 8.0:1 and white on red fails
  - [ ] 8.2 Tests: `test_prop_escaping` (including `quote=True` for attributes), `test_prop_https_links_only`, `test_prop_no_script_no_external` (also no `<noscript>`), `test_prop_semantics` (lang, title unique except `index.html`, one h1 on index, k=1 and k>=2 pages, one main, labelled navs, no aria-hidden, no empty elements, no nbsp runs), `test_prop_link_text`, `test_prop_severity_text`, `test_prop_footer_disclaimer_and_data_as_of`, `test_prop_paragraph_grouping` (one `<p>` per source paragraph, `<h2>` section labels), stale and fallback banners
  - [ ] 8.3 Implement `render.py` (templates, `esc`, inline CSS generated only from `PALETTE`/`ALLOWED_PAIRS`: explicit body, `a`, visited, hover and focus colours, `ch` grid, `monospace,monospace`, 24px targets, no animation, viewport meta without `user-scalable`/`maximum-scale`; nav and footer inside the grid)
  - [ ] 8.4 Render stale and fallback banners (`STALE DATA - CHECK WEATHER.GOV`, `LIVE UPDATE FAILED - SHOWING LAST GOOD DATA`) independently, and the skipped-count line (R10.3, R10.4, R10.6)
  - [ ] 8.5 Static CSS and markup tests (R13.8-R13.11, R13.15, R13.16, R13.19): no `outline:none`/`outline:0`; no `@keyframes`, `animation`, `transition`; `ch` on `.tt` and no `px` width on `.tt`/`.row`; links have `min-height`/`min-width` >= 24px; viewport meta present and no `user-scalable=no`; every colour pair in CSS is in `ALLOWED_PAIRS`; links appear only on black/blue bands; focus outline >= 3:1 on those; h1 text appears once with double height (R13.14)

- [ ] 9. Verification (R8.3, R9.3, R12, R13, R14.11)
  - [ ] 9.1 Tests: each violation type is detected by `verify_site` on hand-made bad HTML; 50 KB boundary measured in UTF-8 bytes (51,199 passes, 51,200 fails, using a multi-byte character to prove byte counting); `test_prop_page_size_budget` with worst-case alerts
  - [ ] 9.2 Implement `verify.py` (stdlib `html.parser` checks, size budget, link existence, `ALLOWED_ELEMENTS`/`ALLOWED_ATTRS`, CSS checks from 8.5, uses `palette.contrast_ratio`; no logic duplicated from `palette.py`)
  - [ ] 9.3 Extend `verify_site` and tests with the R8.3 element/attribute allowlist (any unlisted tag or attribute is a violation; `test_prop_allowlist`), the CSS checks from 8.5, viewport check, and h1-presence on index and k>=2 pages
  - [ ] 9.4 `tools/check_pages.py` is the fast hook-time subset of `verify.py` (R14.11): add `test_prop_check_pages_subset_of_verify` running both on the same good and bad pages; every `check_pages` finding must have a `verify_site` counterpart; fix `check_pages.py` where it disagrees

- [ ] 10. Cache and freshness (R2.1-R2.2, R2.9, R2.10, R10.3)
  - [ ] 10.1 Tests: `test_prop_is_fresh` (`0 <= age < interval`; future `fetched_at` never fresh), `test_prop_is_stale_monotonic` (negative age is stale), `test_prop_cache_keyed_by_area` (store for A, load for B returns None, and `get_data` never serves A's alerts for B), atomic write, invalid body not stored
  - [ ] 10.2 Implement `cache.py` (file `alerts-<AREA>.json`, entry holds area) and `get_data` (fresh cache skips fetch; failed fetch falls back with `fallback=True`, stale from age only; no cache raises)

- [ ] 11. Fetch with backoff (R1.3-R1.6, R1.8, R2.4-R2.8)
  - [ ] 11.1 Tests with fake opener/sleep/rng: UA header sent, URL has `status=actual` (lowercase) and `area=`, never `status=Actual`, no nationwide URL, `test_prop_backoff_bounds` (ceilings non-decreasing, <= cap, delays in `[0, ceiling]`), `test_prop_retry_after_parse`, 429/5xx retried up to `max_attempts` (4), 404 not retried, recorded 400 fixture raises `FetchError(400)`, `Retry-After` honoured as `max(Retry-After, delay)`, `Retry-After` > cap stops retrying, network error retried, request timeout of `timeout_s` passed to the opener
  - [ ] 11.2 Implement `fetch.py` (`urllib.request`, timeout, `backoff_ceilings`, `backoff_delays`, `parse_retry_after`)

- [ ] 12. Publish (R14.2-R14.4, R2.8)
  - [ ] 12.1 Tests (tmp dirs): `test_prop_publish_atomic_on_failure` (previous site byte-identical), stale files removed on success, root `index.html` equals page 888, `recover` after simulated crash between the two renames (site missing with `site.old` present, and both present), leftover `.site.tmp` removed
  - [ ] 12.2 Implement `publish.py` (write sibling `.site.tmp`, verify, rename `site` to `site.old`, rename tmp to `site`, delete `site.old`, `recover` at start)

- [ ] 13. Build orchestration and CLI (R14.1, R14.10, R10.5, R10.7, R10.8, exit codes)
  - [ ] 13.1 Tests with fixtures and fake fetcher: end to end normal, empty, stale, fallback, fallback with every alert expired (`NO UNEXPIRED ALERTS IN LAST GOOD DATA`), no-data (exit 3, notice site published, no `NO ACTIVE ALERTS` text), 4xx with no cache (exit 5), verify failure (exit 4, previous site untouched), config error (exit 2), cache for another area not used; log line has counts and excludes the UA
  - [ ] 13.2 Implement `build.py` and `__main__.py` (exit codes 0, 2, 3, 4, 5)
  - [ ] 13.3 Tests: stage-order spy (fetch, parse, normalise, summarise, paginate, render, verify, publish; R14.1); stdlib-only import scan of `src/page888` against `sys.stdlib_module_names` (R14.6); no analytics, tracking or cookie strings in output (R14.7); broadcaster denylist scan (`Ceefax` and similar) of output and `docs/` (R11.4); attribution, sender and source link on alert pages (R11.2, R11.3); weather.gov link on 888 (R11.5)

- [ ] 14. Checkpoint: full suite and manual checks
  - [ ] 14.1 `pytest -q` and `pytest -q -k prop` pass; no test touches the network
  - [ ] 14.2 Generate `site/` from fixtures; run `python tools/check_pages.py site --strict`; manually check with JS disabled, 200% zoom, keyboard-only, one screen reader; record results in `docs/`
  - [ ] 14.3 Confirm largest page size below 50 KB from the build log; record the measured CSS size for the README

- [ ] 15. Scheduling and hosting (R14.5, R14.7, R14.8, R2.11)
  - [ ] 15.1 Choose a free static host (see design section 9) and add its scheduled workflow with `PAGE888_USER_AGENT` as a secret and a cron no tighter than the minimum interval (verify the host's cron limits against its current docs)
  - [ ] 15.2 Persist the cache directory between runs (mandatory, not optional); make the deploy step run even when the build exits 3 or 5 so the notice site replaces stale content, while the job still fails visibly
  - [ ] 15.3 Confirm no analytics, tracking, scripts or external resources in the deployed output

- [ ] 16. Documentation and cleanup (Definition of done)
  - [ ] 16.1 README in `docs/`: setup, env vars, commands, navigation limitation (links, no typed entry), disclaimer, data attribution, accepted area codes (R1.9), the 111-alert limit and omission trade-off (R5.7), the lossy ASCII mapping (R3.6), the 24-row guarantee vs narrow-viewport reflow (R13.18)
  - [ ] 16.2 Check docs contain no broadcaster trademarks and no invented statistics (no unsourced dates or size estimates)
  - [ ] 16.3 Remove temporary files; confirm `site/` is not hand-edited
