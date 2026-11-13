---
inclusion: always
---

# Structure

## Layout
```
src/page888/     generator package (models, layout, palette, fetch, cache, parse, text, order, summarise, paginate, render, verify, publish, build)
tests/           pytest + hypothesis tests, tests/fixtures/ for sample CAP JSON
tools/           check_pages.py: fast stdlib-only subset of verify.py for hooks and QA (verify.py is authoritative)
site/            generated output (never hand-edited; gitignored unless the host requires it)
docs/            BRIEF.md and other human docs
.kiro/steering/  steering files
```

## Naming
- Python: snake_case modules/functions, PascalCase classes, type hints on public functions, small pure functions for parse/paginate/render so they are property-testable.
- Tests: `tests/test_<module>.py`; property tests named `test_prop_*`.
- Output files: `site/<page>.html` for a page, `site/<page>-<k>.html` for sub-page k (e.g. `889-2.html`). Links are relative.

## Page-number scheme
- `888` index of active alerts for the chosen area.
- `889+` one page per alert, in index order (most severe first, then soonest expiry).
- Sub-pages `NNN/k` (k starts at 1; `NNN` is page 1). Each sub-page links to previous/next and back to 888.
- Page numbers are always 3 digits. Alerts beyond the 111 pages 889-999 are not given pages: the last index sub-page shows `NOT SHOWN: n MORE - SEE WEATHER.GOV` with a link (accepted trade-off; they are the least severe by sort order). The index itself paginates (888/2...) when it has too many rows. Numbers are assigned per build and are not stable identifiers; the page shows the alert's source id/link.
- `index.html` is a byte-identical copy of `888.html` (exempt from the unique-title rule).

## Definition of done
- [ ] `pytest -q` passes, including property tests (no page exceeds 40 cols x 24 rows; no text lost in pagination; all output HTML-escaped).
- [ ] Every generated page < 50 KB; build fails otherwise.
- [ ] No `<script>`, no external resources in output.
- [ ] One `<h1>`, `lang`, `title`, `<main>`, labelled `<nav>` on every page; contrast and non-colour-only checks satisfied.
- [ ] Works with JS disabled and at 200% zoom.
- [ ] NWS rules respected: User-Agent set, `status=actual` (lowercase query value), cache keyed by area + backoff, no key.
- [ ] `python tools/check_pages.py site --strict` passes (fast subset); `verify.py` passes (authoritative).
- [ ] Stdlib-only runtime; no new runtime dependencies.
- [ ] No broadcaster trademarks; no invented statistics in docs.
- [ ] Temporary files removed; docs updated if behaviour changed.
