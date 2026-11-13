"""Pages to HTML strings with inline CSS (design section 5; R8, R9, R13).

Every API-derived string goes through `esc` (quote=True). CSS colours come only
from `PALETTE` and `ALLOWED_PAIRS`; there is no script and no external resource.
"""
from __future__ import annotations

import html
import re
from typing import Iterable, Mapping, Sequence

from .layout import COLS, FALLBACK_TEXT, MAX_DOUBLE_HEIGHT_COLS, STALE_TEXT
from .models import DataStatus, Page, Row, SubPage
from .palette import ALLOWED_PAIRS, PALETTE
from .paginate import (
    INDEX_ALIAS, INDEX_PAGE, NavContext, build_nav, filename, footer_rows, header_text, nav_rows,
    status_rows,
)
from .parse import https_url_or_empty
from .text import wrap

TITLE_SUFFIX = "Page 888"
NAV_LABEL = "Page navigation"
LANG = "en"
_REL_PAGE = re.compile(r"[0-9]{3}(-[0-9]+)?\.html")
_BANNER_ROWS = frozenset([STALE_TEXT, *wrap(FALLBACK_TEXT, COLS)])


def esc(s: str) -> str:
    """HTML-escape text or an attribute value."""
    return html.escape(s, quote=True)


# ---------------------------------------------------------------- CSS

def _pair(fg: str, bg: str) -> str:
    assert (fg, bg) in ALLOWED_PAIRS, (fg, bg)
    return f"color:{PALETTE[fg]};background:{PALETTE[bg]}"


def _band(bg: str, fg: str) -> str:
    return f".b-{bg}-{fg}{{{_pair(fg, bg)}}}"


def build_css() -> str:
    focus = f"outline:3px solid {PALETTE['yellow']};outline-offset:2px"
    rules = [
        f"html{{{_pair('white', 'black')}}}",
        "body.tt{margin:0 auto;width:40ch;max-width:100%;font-family:monospace,monospace;"
        f"font-size:1rem;line-height:1.5;{_pair('white', 'black')}}}",
        "header,main,nav,footer,p,ul,ol,li,h1,h2{margin:0;padding:0}",
        "ul,ol{list-style:none}",
        f"h1,h2{{font-weight:normal;font-size:1em}}",
        f"h1{{{_pair('yellow', 'black')}}}",
        f"h2{{{_pair('green', 'black')}}}",
        "h1.dh{font-size:2em}",
        ".row{display:block;white-space:pre-wrap;overflow-wrap:anywhere;min-height:1.5em}",
        ".gap{margin-top:1.5em}",
        _band("blue", "white"),
        _band("red", "black"),
        f"a,a:visited,a:hover{{{_pair('cyan', 'black')};text-decoration:underline;"
        "display:inline-block;min-height:24px;min-width:24px}",
        f"a:focus{{{focus}}}",
        f"a:focus-visible{{{focus}}}",
    ]
    return "".join(rules)


CSS = build_css()


# ---------------------------------------------------------------- helpers

def safe_href(href: str) -> str:
    """`href` only if it is a page file name or a safe https URL, else ''."""
    if _REL_PAGE.fullmatch(href):
        return href
    return https_url_or_empty(href)


def _row(r: Row, tag: str = "span", extra: str = "") -> str:
    classes = ["row"] + ([extra] if extra else []) + (["gap"] if r.gap_before else [])
    return f'<{tag} class="{" ".join(classes)}">{esc(r.text)}</{tag}>'


def _runs(rows: Iterable[Row], banners: bool = False) -> str:
    """Rows as spans; consecutive rows with the same safe href share one <a>."""
    out: list[str] = []
    cur: str | None = None
    first = True
    for r in rows:
        href = safe_href(r.href)
        if href != cur:
            if cur:
                out.append("</a>")
            if href:
                out.append(f'<a href="{esc(href)}">')
            cur = href
        extra = "b-red-black" if banners and r.text in _BANNER_ROWS else ""
        if not first and not r.join:
            out.append(" ")  # keeps wrapped rows readable as running text; collapsed by CSS
            # (rows of one unbreakable token, such as an ID, are joined with no space)
        first = False
        out.append(_row(r, "span", extra))
    if cur:
        out.append("</a>")
    return "".join(out)


def _h1(sp: SubPage) -> str:
    width = MAX_DOUBLE_HEIGHT_COLS if sp.double_height_title else COLS
    spans = " ".join(f'<span class="row">{esc(line)}</span>' for line in wrap(sp.title, width))
    return f'<h1 class="dh">{spans}</h1>' if sp.double_height_title else f"<h1>{spans}</h1>"


def _body(sp: SubPage) -> str:
    out: list[str] = []
    cur: list[Row] | None = None  # open paragraph
    li: list[Row] | None = None  # open index list item
    items: list[list[Row]] = []

    def close_items() -> None:
        nonlocal items
        if items:
            lis = "".join(f"<li>{_item(i)}</li>" for i in items)
            out.append(f"<ol>{lis}</ol>")
            items = []

    def _item(rows: list[Row]) -> str:
        head, rest = rows[0], rows[1:]
        link = _row(head, "a").replace("<a ", f'<a href="{esc(head.href)}" ', 1)
        return " ".join([link, *(_row(r) for r in rest)])  # space keeps text-mode rows apart

    def close_para() -> None:
        nonlocal cur
        if cur:
            out.append(f"<p>{_runs(cur)}</p>")
        cur = None

    is_index = sp.number == INDEX_PAGE
    for r in sp.body:
        if is_index and _REL_PAGE.fullmatch(r.href) and not r.label:
            close_para()
            li = [r]
            items.append(li)
        elif is_index and li is not None and not r.href and not r.gap_before and not r.label:
            li.append(r)
        elif r.label:
            close_para()
            close_items()
            li = None
            out.append(_row(r, "h2"))
        else:
            li = None
            close_items()
            if cur is None or r.gap_before:
                close_para()
                cur = []
            cur.append(r)
    close_para()
    close_items()
    return "".join(out)


def _nav(nav: NavContext) -> str:
    rows = nav_rows(nav)
    if not rows:
        inner = '<p class="row">NO OTHER PAGES</p>'
    else:
        inner = "<ul>" + "".join(
            f'<li><a class="row" href="{esc(r.href)}">{esc(r.text)}</a></li>' for r in rows
        ) + "</ul>"
    return f'<nav aria-label="{esc(NAV_LABEL)}">{inner}</nav>'


def _footer(rows: Sequence[Row]) -> str:
    return "<footer><p>" + " ".join(
        f'<a class="row" href="{esc(safe_href(r.href))}">{esc(r.text)}</a>'
        if safe_href(r.href) else _row(r)
        for r in rows
    ) + "</p></footer>"


# ---------------------------------------------------------------- pages

def render_subpage(sp: SubPage, nav: NavContext, status: DataStatus, area: str) -> str:
    title = f"P{sp.number}/{sp.k} {sp.title} - {TITLE_SUFFIX}"
    header = header_text(sp, area)
    return (
        "<!DOCTYPE html>\n"
        f'<html lang="{LANG}"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{esc(title)}</title><style>{CSS}</style></head>"
        '<body class="tt">'
        f'<header><p class="row b-blue-white">{esc(header)}</p></header>'
        f"<main>{_h1(sp)}{_body(sp)}"
        f'<p class="status">{_runs(status_rows(status), banners=True)}</p></main>'
        f"{_nav(nav)}{_footer(footer_rows(sp.number == INDEX_PAGE))}"
        "</body></html>\n"
    )


def render_site(pages: Sequence[Page], status: DataStatus, area: str) -> dict[str, str]:
    """File name to HTML for every sub-page, plus `index.html` (a copy of 888.html, R5.10)."""
    navs = build_nav(pages)
    files: dict[str, str] = {}
    for page in pages:
        for sp in page.subpages:
            files[filename(sp.number, sp.k)] = render_subpage(sp, navs[(sp.number, sp.k)], status, area)
    alias, source = INDEX_ALIAS
    if source in files:
        files[alias] = files[source]
    return files
