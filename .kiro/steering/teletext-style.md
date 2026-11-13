---
inclusion: fileMatch
fileMatchPattern: "{**/templates/**,**/*.css,**/*.html,**/*.html.tmpl,**/*.tmpl,**/render*.py,**/style*.py}"
---

# Teletext style

## Grid
- 40 columns x 24 rendered rows, monospace, one character per cell. Fixed row budget (defined in `layout.py`): header 1 (row 0: page id `PNNN/k`, area, `k/total`), body 13 (h1 first, then content), status 5 (`DATA AS OF` date/time in UTC, stale and fallback banners, skipped count), navigation 3, footer 2 (disclaimer). Total 24. Nav and footer are inside the grid.
- A rendered row is a `.row` element or a `.gap` spacer; each `.row` is at most 40 characters. Group wrapped rows of one paragraph in one `<p>` of `<span class="row">`; section labels are `<h2>`.
- Size the grid in `ch` units (width `40ch`) with a fixed line height; font stack `monospace, monospace`. Content wider than 40 characters is wrapped by the generator, never by overflow. On viewports narrower than 40 characters rows reflow (accepted under WCAG 1.4.10).
- Use `<pre>`-like semantics only where it keeps meaning; structure still uses headings, lists and links.

## Palette (8 colours)
black `#000000`, red `#ff0000`, green `#00ff00`, yellow `#ffff00`, blue `#0000ff`, magenta `#ff00ff`, cyan `#00ffff`, white `#ffffff`.

Contrast (WCAG ratio, computed from the hex values above):
- On black: white 21:1, yellow 19.6:1, cyan 16.7:1, green 15.3:1, magenta 6.7:1, red 5.3:1 (all pass 4.5:1); blue 2.4:1 FAILS, never use blue text on black.
- On white: black 21:1, blue 8.6:1 pass; red 4.0:1, magenta 3.1:1, green 1.4:1 and the rest fail.
- On red: black 5.3:1 passes; white 4.0:1 fails.
- On green: black 15.3:1, blue 6.3:1 pass; the rest fail.
- On yellow: black 19.6:1, blue 8.0:1 pass; the rest fail.
- On blue: white 8.6:1, yellow 8.0:1, cyan 6.9:1, green 6.3:1 pass; red 2.1:1, magenta 2.7:1, black 2.4:1 FAIL.
- On cyan: black 16.7:1, blue 6.9:1 pass; the rest fail.
- On magenta: black 6.7:1 passes; white 3.1:1 and blue 2.7:1 fail.

`ALLOWED_PAIRS` (foreground on background), the only pairs that may appear in CSS, 20 of the 64 combinations:
- black bg: white, yellow, cyan, green, magenta, red
- white bg: black, blue
- red bg: black
- green bg: black, blue
- yellow bg: black, blue
- blue bg: white, yellow, cyan, green
- cyan bg: black, blue
- magenta bg: black

There are no large-text exceptions. CSS is generated from this list; a test checks all 64 combinations against computed ratios.
- Default body: white on black. Links: cyan on black, same colours for link, visited and hover (never browser defaults). Links appear only on black or blue backgrounds. Focus outline: yellow `#ffff00` (19.6:1 on black, 8.0:1 on blue).
- Blue is for background bands only, with white/yellow/cyan/green text.
- Colour never carries meaning alone: severity is always written (e.g. "SEVERE"), colour only reinforces it.

## Double-height headlines
- Headline (the alert event) may be double height: rendered with CSS scaling (e.g. `font-size: 2em` / `line-height: 2` over two rows), not by duplicating text.
- A double-height line consumes 2 of the 24 rows; account for it in pagination.
- Double-height lines must be shorter: at 2x width only 20 characters fit in 40 columns. Wrap to multiple double rows or fall back to normal height; never overflow.
- Still a real heading element (the single `<h1>`); no duplicated or hidden copy for screen readers.
- Keep to one double-height headline per page.

## Never
- Never use JavaScript, web fonts, images, or external resources.
- Never use blue text on black, or any foreground/background pair not in `ALLOWED_PAIRS`.
- Never rely on colour, blinking or position alone to convey meaning; no flashing/blinking (WCAG seizure and motion concerns).
- Never use empty elements or `&nbsp;` runs for spacing; use CSS.
- Never exceed 40x24 per page or truncate safety text silently; paginate to sub-pages.
- Never use broadcaster names, logos or "Ceefax".
- Never remove focus outlines.
