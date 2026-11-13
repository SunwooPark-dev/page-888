# Design-phase review: Page 888

I read all four steering files and the three spec files. I did not run pytest or `check_pages` (no code or `site/` exists yet). I recomputed the steering contrast table from the hex values. The "unverified" items below are external-API claims I couldn't check offline.

Verdict: FAIL. There are 7 high-severity items, mostly safety, layout and accessibility gaps.

## High severity

1. **requirements R2.8, R10.3, tasks 15.2: a stale site can never be flagged stale.**
   - R10.3 puts a stale banner on every page, but the banner is computed only at build time.
   - If fetches keep failing and no cache exists, the build exits 3 and the old deployment stays live. Its alerts keep showing past their expiry and never get a STALE banner.
   - Task 15.2 makes cache persistence optional, so this is the default CI behaviour.
   - Fix: make a persisted cache mandatory for the scheduled job. Also have the exit-3 path re-render the last published data with a stale banner, or require the host to keep deploying fallback builds.

2. **design §3 `cache.py`, requirements R2: the cache is not keyed by area.**
   - If `PAGE888_AREA` changes, the fresh-cache and fallback paths can serve another state's alerts.
   - Fix: store the area in the cache entry (or the cache filename). Treat a mismatch as no cache. Add a test.

3. **design §2 and §5, steering teletext-style: the 40x24 budget is not consistently defined.**
   - Steering has row 0 as header and row 23 as footer. Design adds a status row 22 and says "reserve footer as 2 rows, body = 1-20 if needed". `BODY_ROWS` is therefore 20 or 21.
   - The HTML skeleton puts `<nav>` and `<footer>` outside `.tt`, so R6.1 and P12 can't say what counts as a row.
   - Worst-case status text doesn't fit one row. `LIVE UPDATE FAILED - SHOWING LAST GOOD DATA` is 43 characters. On top of that, one page can need `DATA AS OF`, the stale banner, the skipped count, the disclaimer and the nav hint.
   - Fix: define `layout.py` first. Give the header, status and footer fixed row counts that cover the worst case. Say whether `<nav>` and `<footer>` are inside the grid. Define "rendered rows" as the count of `.row` elements, each at most 40 code points after unescaping.

4. **design §5 CSS: link colours and everything outside `.tt` use browser defaults.**
   - Only `.tt` gets colours. Default links are blue, which is blue on black at 2.4:1 if they sit in the grid. They would also be default-coloured on a white body if they sit in `<nav>`.
   - `<footer>` carries the disclaimer outside the palette.
   - Fix: set body, `a`, `a:visited` and focus-outline colours explicitly from `PALETTE`. Add them to the P22 pair test.

5. **requirements R13.6, design P22, task 8.1: the contrast rules are incomplete and have no mechanism.**
   - Steering tabulates only black, blue and red backgrounds. R13.6 forbids a handful of pairs. Pairs on green, cyan, white, yellow and magenta backgrounds are undefined, and white on green is about 1.4:1.
   - "Forbidden pairs absent from CSS" has no CSS parser behind it, and no task builds one.
   - Task 8.1 uses `contrast_ratio`, which is only implemented in task 9.2.
   - Fix: enumerate an explicit `ALLOWED_PAIRS` list. Generate the CSS only from it. Test all 64 pairs. Move `contrast_ratio` into task 8.1 or earlier.

6. **design §5: each grid row is a separate `<p>`.**
   - Sentences broken at 40 columns become separate paragraphs, so screen readers pause mid-sentence.
   - Section labels (SUMMARY, ACTION) are plain `<p>`. Steering asks for headings, lists and links.
   - Fix: group rows into one block per logical paragraph, using `<br>` or per-row spans. Make section labels `<h2>`. The "one `<h1>`" rule still holds.

7. **design §4 and §6, requirements R14.2: the "atomic swap" of `site/` isn't possible as written.**
   - POSIX `rename` cannot replace a non-empty directory.
   - Fix: say how the swap works, for example rename `site` to `site.old`, rename `tmp` to `site`, then delete `site.old`. Or use a symlink swap. Specify recovery if it crashes between steps. Weaken "atomic" if it can't be guaranteed.

## Medium severity

8. **requirements R6.4 and design P13.**
   - R6.4 says the body text equals the source text. P13 says it contains the source text.
   - The body also holds labels, `(CONT.)` repeats and the generated summary, so equality can't hold.
   - "Alert text" is undefined: does it include headline and areaDesc, or only description and instruction?
   - R3.6 maps non-ASCII to an undefined substitute, which is lossy.
   - Fix: define the compared fields and use "contains in order". Define an explicit ASCII mapping table (for example degree sign to `DEG`).

9. **requirements R6.2 and R6.9.**
   - R6.2 hard-splits words over 40 characters. R6.9 forbids mid-word breaks.
   - Fix: state the exception in R6.9, as P14 already does.

10. **requirements R6.5, R3.2 and product "no guesswork".**
    - `NO INSTRUCTION ISSUED` asserts something the feed doesn't say. A missing `instruction` field often means the guidance is in the description.
    - It also conflicts with the `NOT STATED` placeholder used everywhere else.
    - Fix: use `NO INSTRUCTION FIELD IN SOURCE - SEE DESCRIPTION`.

11. **requirements R5.7, design §4, steering structure and product.**
    - Alerts beyond page 999 are dropped from the site. These are the lowest-severity ones, because of the sort order. That sits uneasily with "never drop safety-critical text".
    - R5.7 says "additional index sub-pages" and "with the source link". Design puts one `NOT SHOWN: n MORE - SEE WEATHER.GOV` line on the last sub-page with no link.
    - Fix: pick one behaviour, name the URL, and record the limit as an accepted trade-off in the docs.

12. **requirements R5.10 with R13.2 and P20.** `index.html` is a copy of 888, so two files share a title and break "unique title". Fix: exempt it explicitly or give it a distinct title.

13. **requirements R2.7 and R10.3/R10.4.** R2.7 says a cache fallback marks data stale. R10 defines stale as older than 30 minutes and fallback as a separate banner. A fallback within 30 minutes isn't stale. Fix: say that fallback sets `fallback=True` and `stale` is computed from age only.

14. **requirements R10.5 and design §4.** With fallback on an old cache, every alert may be expired. The page then reads `NO ACTIVE ALERTS FOR <AREA>`, which reads as "all clear". Fix: in fallback or stale mode, replace it with `NO UNEXPIRED ALERTS IN LAST GOOD DATA` and keep the banner adjacent.

15. **requirements R2.4, R2.5, P27.**
    - No numeric defaults for attempts, base delay, cap or request timeout. The timeout appears in task 11.2 but not in R2 or `Config`.
    - "non-decreasing in its base" is untestable with full jitter.
    - R2.5 says "wait at least that long (delay capped)", which is contradictory.
    - Fix: list default values and add `timeout_s`. State the Retry-After rule precisely, for example "if Retry-After exceeds the cap, stop retrying".

16. **requirements R3.1 and design §2, time display.**
    - `Alert` stores UTC only. The display format and zone for onset and expires aren't specified.
    - Users are non-experts, and UTC expiry times invite misreading.
    - Fix: keep tz-aware values and show the source offset or zone label in text.

17. **requirements R5.4 and R5.9, R7.5, R8.3, R9.4, R11.2, R11.3, R11.5, R13.8-R13.11 and R13.14-R13.15, R14.1 and R14.6: no task or test.**
    - Task 8.2 and `verify` (9.2) cover none of these. Task 8.3 implements some of them but nothing checks them.
    - Missing checks are: an element and attribute allowlist for R8.3; CSS checks for `outline:none`, `ch` units, `@keyframes` and `animation`; target size; viewport with no `user-scalable=no`; and `<h1>` presence on index and k>=2 pages.
    - Also missing are a stage-order spy test and a test scanning imports for non-stdlib modules.
    - Fix: add the tests above and extend `verify` with them.

18. **requirements R3.6 with P5.** R3.6 is `[PBT]` but P5 covers only idempotence and control characters. Newline collapsing and ASCII-only output are untested. Fix: add properties for both.

19. **design §3 `verify_site` and requirements R12.** The mapping holds `str`. Size must be measured as UTF-8 bytes. Fix: say so, and keep the 51,199/51,200 boundary test.

20. **requirements R5.2 and P8, R6.3 and P12.** P8 doesn't check R4 ordering, which R5.2 requires. P12 cites R6.3 but doesn't test continuation. Fix: add an ordering clause to P8 and a continuation clause to P12.

21. **requirements R1.5 and P28, design §2.** "As accepted by NWS" implies a list, but the property tests a pattern. A well-formed but unknown code returns 400 and has no defined exit path. Fix: either document the list or map `FetchError` for 4xx to an exit code. Also confirm the exact casing of `status=Actual` against the NWS OpenAPI spec. I couldn't verify it offline, and the NWS docs list lowercase enum values.

22. **requirements R2.2 and P26.** `is_fresh` with a future `fetched_at` (negative age) is true forever. Fix: require `0 <= age < interval`.

23. **tasks 8.1 and 9.2 vs design §1.** Task 8.1 uses `contrast_ratio` from 9.2. Tasks 7 and 3.1 add `layout.py` and `models.py`, which the design module table lacks.

24. **`tools/check_pages.py` and `.kiro/hooks/*`.** `tools/check_pages.py` is invoked by two hooks and the QA agent. It appears in neither `structure.md` nor the design or tasks, and it overlaps `verify.py`. Fix: either document it, or have one implementation (`verify.py`) and have the tool call it.

25. **design §5.** `.tt{width:40ch;max-width:100%}` rewraps on narrow viewports, which are the target devices. Row alignment and the 24-row count are then lost visually. Also, `font:1rem monospace` shrinks to about 13px in some browsers. Fix: document the reflow as accepted under WCAG 1.4.10. Use `font-family:monospace,monospace`.

## Low severity

26. **steering product.md "type or click a 3-digit page number" vs requirements assumption.** Typed entry is impossible without JS or a server, and the requirements already say so. Fix: reword product.md to "click".

27. **steering teletext-style vs design §5.** Steering says row 0 has page number, title and date/time. Design puts the date in a status row and puts the h1 inside the header. Reconcile where the double-height h1 and the date sit.

28. **requirements R9.1.** "`<noscript>` dependence" is ambiguous. Fix: state "SHALL NOT emit `<noscript>`".

29. **design §5.** The h1 text for index pages and for sub-pages k>=2 is unspecified. The double-height h1 is on sub-page 1 only, but every page needs one h1.

30. **teletext-style.md, contrast table.** Yellow on blue is listed as 8.4:1. Recomputed from the hex values, it is 8.0:1. It still passes, but the table should be corrected. The other values match.

31. **design §5.** Focus outline `#ff0` has no contrast check against yellow or cyan bands. Fix: keep bands to pairs that pass, or choose the outline per band.

32. **Source URL handling (R8.2).** Specify `esc(..., quote=True)` for `href` attributes. Parse the URL with `urllib.parse` and reject whitespace and control characters, not just check the scheme.

## Invented or unsupported statistics

- **product.md, "Teletext (1974-2012 TV text services)".** The dates are unsourced. 2012 matches one broadcaster's shutdown, and teletext still runs in some markets. Fix: say "largely retired in many markets" with no dates, or cite a source.
- **design §5, "inline, ~2 KB" CSS.** This is an unmeasured estimate. Fix: drop it, or replace it with a measured size after the build.
- **design §9, GitHub Actions "minimum cron granularity is 5 minutes".** This is an external-service claim I couldn't verify offline, and the design already says to check current terms. Fix: add "verify against current GitHub docs".
- Not flagged: "111 pages" is arithmetic (889 to 999), and the contrast numbers are computed.

## Verdict

**FAIL.** Items 1-7 should be resolved before implementation starts. I'd do 1-3 and 8 first, because they change the data model and layout constants that the rest of the tasks build on.
