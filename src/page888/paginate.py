"""Alerts to grid pages of at most 40x24 rendered rows (design sections 2.1 and 4).

Pure functions. Body text is flowed into sub-pages; header, status, navigation
and footer rows are produced here so the row counts live in one place.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timezone
from typing import Sequence

from .layout import (
    BODY_ROWS, COLS, DATA_AS_OF, DISCLAIMER, FALLBACK_TEXT, FOOTER_INDEX, FOOTER_OTHER,
    MAX_DOUBLE_HEIGHT_COLS, SKIPPED_TEXT, STALE_TEXT, WEATHER_GOV,
)
from .models import Alert, DataStatus, Page, Row, SubPage
from .parse import NOT_STATED
from .summarise import summarise
from .text import _stamp, format_time, normalise_text, wrap

FIRST_ALERT_PAGE = 889
LAST_ALERT_PAGE = 999
INDEX_PAGE = 888
INDEX_ALIAS = ("index.html", "888.html")  # byte-identical copy, made at publish time (R5.10)
NO_INSTRUCTION = "NO INSTRUCTION FIELD IN SOURCE - SEE DESCRIPTION"
NO_DESCRIPTION = "NO DESCRIPTION FIELD IN SOURCE"
NOT_STABLE = "PAGE NUMBERS ARE NOT STABLE IDS"
_WORST_SUFFIX = " (CONT. 999/999)"


# ---------------------------------------------------------------- numbering

def assign_numbers(n_alerts: int) -> tuple[list[int], int]:
    """(numbers for shown alerts, overflow count) (R5.2, R5.5, R5.7)."""
    shown = max(0, min(n_alerts, LAST_ALERT_PAGE - FIRST_ALERT_PAGE + 1))
    return list(range(FIRST_ALERT_PAGE, FIRST_ALERT_PAGE + shown)), max(0, n_alerts) - shown


def filename(number: int, k: int) -> str:
    return f"{number:03d}.html" if k == 1 else f"{number:03d}-{k}.html"


# ---------------------------------------------------------------- titles

def _flat(s: str) -> str:
    return " ".join(normalise_text(s).split())


def fit_title(base: str, suffix: str = "") -> str:
    """Title that wraps to at most 2 rows; the base is cut (with `...`) if needed."""
    base = _flat(base) or NOT_STATED
    text = base + suffix
    while len(wrap(text, COLS)) > 2:
        base = base[: max(1, min(len(base) - 1, 2 * COLS - len(suffix) - 3 - 1))].rstrip()
        text = base + "..." + suffix
        if len(base) == 1:
            break
    return text


def _title_cost(title: str, double: bool) -> int:
    if double:
        return 2 * len(wrap(title, MAX_DOUBLE_HEIGHT_COLS))
    return len(wrap(title, COLS))


def body_cost(sp: SubPage) -> int:
    """Rows used by h1 plus body (gaps counted, double-height lines twice)."""
    return _title_cost(sp.title, sp.double_height_title) + sum(1 + r.gap_before for r in sp.body)


# ---------------------------------------------------------------- flow

@dataclass(frozen=True)
class _Item:
    text: str
    gap: bool = False
    label: bool = False
    section: str = ""
    href: str = ""


def _text_items(section: str, text: str, href: str = "") -> list[_Item]:
    items: list[_Item] = []
    gap = False
    for r in wrap(text, COLS):
        if r == "":
            gap = True
            continue
        items.append(_Item(r, gap, False, section, href))
        gap = False
    return items


def _section(name: str, text: str, href: str = "") -> list[_Item]:
    body = _text_items(name, text, href)
    return [_Item(name, True, True, name)] + body if body else []


def _flow(items: Sequence[_Item], cap_first: int, cap_rest: int) -> list[list[Row]]:
    pages: list[list[Row]] = [[]]
    used = 0
    cap = cap_first
    i = 0
    while i < len(items):
        it = items[i]
        page = pages[-1]
        fresh = not page or page[-1].label
        gap = it.gap and not fresh
        need = 1 + gap + (1 if it.label else 0)
        if not page and not it.label and len(pages) > 1:
            lab = f"{it.section} (CONT.)"
            page.append(Row(lab, False, True))
            used += 1
            continue
        if used + need > cap and page:
            pages.append([])
            used = 0
            cap = cap_rest
            continue
        page.append(Row(it.text, gap, it.label, it.href))
        used += 1 + gap
        i += 1
    return pages


# ---------------------------------------------------------------- alert pages

@dataclass(frozen=True)
class NavLink:
    kind: str  # "prev" | "next" | "index"
    number: int
    k: int
    text: str  # <= 40 columns

    @property
    def href(self) -> str:
        return filename(self.number, self.k)


@dataclass(frozen=True)
class NavContext:
    prev: NavLink | None = None
    next: NavLink | None = None
    index: NavLink | None = None


def _alert_items(a: Alert) -> list[_Item]:
    desc = normalise_text(a.description) or NO_DESCRIPTION
    instr = normalise_text(a.instruction) or NO_INSTRUCTION
    details: list[str] = []
    if a.onset is not None:
        local, utc = format_time(a.onset)
        details += [f"ONSET {local}", utc]
    if a.expires is not None:
        local, utc = format_time(a.expires)
        details += [f"EXPIRES {local}", utc]
    details.append(f"SENDER {_flat(a.sender_name) or NOT_STATED}")
    items = _section("SUMMARY", summarise(a))
    items += _section("DESCRIPTION", desc)
    items += _section("ACTION", instr)
    items += [_Item("DETAILS", True, True, "DETAILS")]
    items += [_Item(r, False, False, "DETAILS") for d in details for r in wrap(d, COLS)]
    items += [_Item("SOURCE", True, True, "SOURCE")]
    items += [_Item(r, False, False, "SOURCE") for r in wrap(f"ID {_flat(a.id)}", COLS)]
    if a.source_url:
        items += [_Item(r, False, False, "SOURCE", a.source_url) for r in wrap(f"LINK {a.source_url}", COLS)]
    items += [_Item(NOT_STABLE, False, False, "SOURCE")]
    return items


def paginate_alert(a: Alert, number: int, status: DataStatus, nav: NavContext | None = None) -> Page:
    """One alert to its sub-pages. `status` and `nav` do not change the body."""
    event = _flat(a.event) or NOT_STATED
    dh_lines = wrap(event, MAX_DOUBLE_HEIGHT_COLS)
    double = len(dh_lines) <= 2 and all(len(w) <= MAX_DOUBLE_HEIGHT_COLS for w in event.split())
    title1 = event if double else fit_title(event)
    cap_first = BODY_ROWS - _title_cost(title1, double)
    cap_rest = BODY_ROWS - _title_cost(fit_title(event, _WORST_SUFFIX), False)
    pages = _flow(_alert_items(a), cap_first, cap_rest)
    n = len(pages)
    subs = tuple(
        SubPage(
            number, k, n,
            title1 if k == 1 else fit_title(event, f" (CONT. {k}/{n})"),
            tuple(rows), double and k == 1,
        )
        for k, rows in enumerate(pages, 1)
    )
    return Page(number, "alert", subs, a.id)


# ---------------------------------------------------------------- index and notice

def _cut(s: str) -> str:
    return s[:COLS]


def _index_rows(a: Alert, number: int) -> list[Row]:
    exp = "EXP NOT STATED"
    if a.expires is not None:
        local = format_time(a.expires)[0]
        exp = f"EXP {local[11:]}"
    area = _flat(a.area_desc) or NOT_STATED
    detail = f"{area[: max(0, COLS - len(exp) - 2)]}, {exp}"
    link = f"{number:03d} {a.severity.name} {_flat(a.event) or NOT_STATED}"
    return [Row(_cut(link), False, False, filename(number, 1)), Row(_cut(detail))]


def _single_page(number: int, kind: str, title: str, rows: list[Row]) -> Page:
    sp = SubPage(number, 1, 1, title, tuple(rows), False)
    return Page(number, kind, (sp,), None)


def paginate_index(alerts: Sequence[Alert], status: DataStatus, area: str) -> list[Page]:
    """Page 888 (and 888/k). `alerts` must already be in R4 order."""
    numbers, overflow = assign_numbers(len(alerts))
    base = f"ALERT INDEX {_flat(area)}"
    blocks: list[list[Row]] = [_index_rows(a, n) for a, n in zip(alerts, numbers)]
    if not blocks:
        text = "NO UNEXPIRED ALERTS IN LAST GOOD DATA" if (status.stale or status.fallback) \
            else f"NO ACTIVE ALERTS FOR {_flat(area)}"
        blocks = [[Row(r)] for r in wrap(text, COLS)]
    tail: list[Row] = []
    if overflow:
        tail = [Row(f"NOT SHOWN: {overflow} MORE - SEE WEATHER.GOV", False, False, WEATHER_GOV)]
    cap_first = BODY_ROWS - _title_cost(fit_title(base), False)
    cap_rest = BODY_ROWS - _title_cost(fit_title(base, _WORST_SUFFIX), False)
    pages: list[list[Row]] = [[]]
    cap = cap_first
    for blk in blocks:
        if len(pages[-1]) + len(blk) > cap and pages[-1]:
            pages.append([])
            cap = cap_rest
        pages[-1].extend(blk)
    if tail and len(pages[-1]) + 1 > cap:
        pages.append([])
    pages[-1].extend(tail)
    n = len(pages)
    subs = tuple(
        SubPage(INDEX_PAGE, k, n, fit_title(base) if k == 1 else fit_title(base, f" (CONT. {k}/{n})"),
                tuple(rows), False)
        for k, rows in enumerate(pages, 1)
    )
    return [Page(INDEX_PAGE, "index", subs, None)]


def paginate_notice(area: str, status: DataStatus) -> list[Page]:
    """Notice site (R10.8): no alert content."""
    rows = [Row(r) for r in wrap("ALERT DATA UNAVAILABLE - CHECK WEATHER.GOV", COLS)]
    rows.append(Row("WEATHER.GOV", True, False, WEATHER_GOV))
    return [_single_page(INDEX_PAGE, "notice", "ALERT DATA UNAVAILABLE", rows)]


def build_site_model(alerts: Sequence[Alert], status: DataStatus, area: str) -> list[Page]:
    """Index page then one page per shown alert. `alerts` is already in R4 order."""
    numbers, _ = assign_numbers(len(alerts))
    pages = paginate_index(alerts, status, area)
    pages += [paginate_alert(a, n, status, None) for a, n in zip(alerts, numbers)]
    return pages


# ---------------------------------------------------------------- links

def _link(kind: str, sp: SubPage) -> NavLink:
    label = {"prev": "PREV", "next": "NEXT", "index": "INDEX"}[kind]
    return NavLink(kind, sp.number, sp.k, _cut(f"{label} {sp.number}/{sp.k} {sp.title}"))


def build_nav(pages: Sequence[Page]) -> dict[tuple[int, int], NavContext]:
    """Prev/next follow the flat page order; every sub-page except 888/1 links to 888."""
    flat = [sp for p in pages for sp in p.subpages]
    out: dict[tuple[int, int], NavContext] = {}
    first = flat[0] if flat else None
    for i, sp in enumerate(flat):
        out[(sp.number, sp.k)] = NavContext(
            _link("prev", flat[i - 1]) if i > 0 else None,
            _link("next", flat[i + 1]) if i + 1 < len(flat) else None,
            _link("index", first) if first is not None and i > 0 else None,
        )
    return out


# ---------------------------------------------------------------- fixed blocks

def header_text(sp: SubPage, area: str) -> str:
    return _cut(f"P{sp.number}/{sp.k} {area} {sp.k}/{sp.total}")


def status_rows(status: DataStatus) -> tuple[Row, ...]:
    stamp = _stamp(status.fetched_at.astimezone(timezone.utc))
    lines = [DATA_AS_OF.format(stamp=stamp)]
    if status.stale:
        lines.append(STALE_TEXT)
    if status.fallback:
        lines.append(FALLBACK_TEXT)
    if status.skipped > 0:
        lines.append(SKIPPED_TEXT.format(n=status.skipped))
    return tuple(Row(r) for line in lines for r in wrap(line, COLS))


def nav_rows(nav: NavContext) -> tuple[Row, ...]:
    return tuple(Row(l.text, False, False, l.href) for l in (nav.prev, nav.next, nav.index) if l)


def footer_rows(is_index: bool) -> tuple[Row, ...]:
    if is_index:
        return (Row(DISCLAIMER), Row(FOOTER_INDEX, False, False, WEATHER_GOV))
    return (Row(DISCLAIMER), Row(FOOTER_OTHER))


def page_rows(sp: SubPage, status: DataStatus, nav: NavContext) -> int:
    """Total rendered rows of the page: header + h1/body + status + nav + footer."""
    return 1 + body_cost(sp) + len(status_rows(status)) + len(nav_rows(nav)) + len(footer_rows(sp.number == INDEX_PAGE))
