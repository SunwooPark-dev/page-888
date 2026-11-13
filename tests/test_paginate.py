"""Pagination, numbering, index, notice and link graph (tasks 7.2-7.6; P8-P10, P12-P15)."""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from hypothesis import given, strategies as st

from page888 import layout
from page888.models import Alert, DataStatus, Severity
from page888.order import order_alerts
from page888.paginate import (
    INDEX_ALIAS, NO_INSTRUCTION, NOT_STABLE, assign_numbers, body_cost, build_nav, build_site_model,
    filename, footer_rows, header_text, nav_rows, page_rows, paginate_alert, paginate_index,
    paginate_notice, status_rows,
)
from page888.text import normalise_text

NOW = datetime(2026, 11, 13, 14, 0, tzinfo=timezone.utc)
STATUS = DataStatus(NOW, False, False, 0)

_ALPHA = st.sampled_from(list("abcXYZ019 .,;:-<>&\"'\n") + ["\u00b0", "\u2019", "\u00e9"])
txt = st.text(_ALPHA, max_size=400)
words = st.lists(st.text("abcdefgh", min_size=1, max_size=70), max_size=120).map(" ".join)
long_text = st.one_of(txt, words)


def mk(**kw) -> Alert:
    d = dict(
        id="urn:x:1", event="Flood Warning", severity=Severity.SEVERE, urgency="Immediate",
        certainty="Likely", area_desc="Some County", headline="H", description="Desc.",
        instruction="Move to higher ground.", onset=NOW, expires=NOW + timedelta(hours=2),
        sender_name="NWS Test", source_url="https://api.weather.gov/alerts/x",
    )
    d.update(kw)
    return Alert(**d)


alerts_st = st.builds(
    mk,
    id=st.text(_ALPHA, max_size=30), event=txt, area_desc=txt, headline=txt,
    description=long_text, instruction=long_text, sender_name=txt,
    severity=st.sampled_from(list(Severity)),
    expires=st.one_of(st.none(), st.just(NOW + timedelta(hours=1))),
    onset=st.one_of(st.none(), st.just(NOW)),
    source_url=st.sampled_from([
        "", "https://api.weather.gov/alerts/" + "a" * 90, "javascript:alert(1)", "http://x.example/",
        "https://[bad", "https://\u00e9.example/\u2603", 'https://x.example/"><script>',
    ]),
)
status_st = st.builds(
    DataStatus, st.just(NOW), st.booleans(), st.booleans(), st.integers(0, 10**6)
)


def label_rows(sp):
    return [r for r in sp.body if r.label]


# ---- 7.2 numbering and filenames

@given(st.integers(0, 400))
def test_prop_assign_numbers(n):
    nums, over = assign_numbers(n)
    assert nums == sorted(set(nums))
    assert len(nums) <= 111 and over == n - len(nums)
    assert all(889 <= x <= 999 for x in nums)
    if nums:
        assert nums[0] == 889


@given(st.integers(100, 999), st.integers(1, 500), st.integers(100, 999), st.integers(1, 500))
def test_prop_filename(n1, k1, n2, k2):
    f = filename(n1, k1)
    assert re.fullmatch(r"\d{3}(-\d+)?\.html", f)
    assert (k1 == 1) == ("-" not in f)
    assert (f == filename(n2, k2)) == ((n1, k1) == (n2, k2))


# ---- grid bounds, completeness, labels, double height

@given(alerts_st, status_st)
def test_prop_grid_bounds(a, status):
    page = paginate_alert(a, 889, status, None)
    nav = build_nav([page])
    for sp in page.subpages:
        assert body_cost(sp) <= layout.BODY_ROWS
        assert all(len(r.text) <= layout.COLS for r in sp.body)
        assert page_rows(sp, status, nav[(sp.number, sp.k)]) <= layout.ROWS
        assert all(len(r.text) <= layout.COLS for r in status_rows(status))
        assert len(status_rows(status)) <= layout.STATUS_ROWS
        assert len(header_text(sp, "CA")) <= layout.COLS


@given(alerts_st)
def test_prop_no_text_lost(a):
    page = paginate_alert(a, 889, STATUS, None)
    flat = "".join(r.text for sp in page.subpages for r in sp.body if not r.label)
    flat = re.sub(r"\s+", "", flat)
    want = re.sub(r"\s+", "", normalise_text(a.description)) + re.sub(
        r"\s+", "", normalise_text(a.instruction) or NO_INSTRUCTION
    )
    assert want in flat


@given(alerts_st)
def test_prop_instruction_complete(a):
    page = paginate_alert(a, 889, STATUS, None)
    rows = [r for sp in page.subpages for r in sp.body]
    first = next(j for j, r in enumerate(rows) if r.label and r.text == "ACTION")
    end = next(j for j, r in enumerate(rows) if r.label and r.text == "DETAILS")
    got = re.sub(r"\s+", "", "".join(r.text for r in rows[first:end] if not r.label))
    want = re.sub(r"\s+", "", normalise_text(a.instruction) or NO_INSTRUCTION)
    assert got == want


def test_absent_instruction_text():
    page = paginate_alert(mk(instruction=""), 889, STATUS, None)
    text = "".join(r.text for sp in page.subpages for r in sp.body if not r.label)
    assert NO_INSTRUCTION.replace(" ", "") in text.replace(" ", "")


@given(alerts_st)
def test_prop_no_orphan_label(a):
    for sp in paginate_alert(a, 889, STATUS, None).subpages:
        assert sp.body and not sp.body[-1].label
        for r, nxt in zip(sp.body, sp.body[1:]):
            if r.label:
                assert not nxt.label and not nxt.gap_before


@given(alerts_st)
def test_prop_double_height_rules(a):
    page = paginate_alert(a, 889, STATUS, None)
    dh = [sp for sp in page.subpages if sp.double_height_title]
    assert len(dh) <= 1
    for sp in dh:
        assert sp.k == 1
        lines = re.findall(r".{1,20}(?:\s|$)", sp.title)
        assert len(sp.title) <= 40 and len(lines) <= 2
        assert body_cost(sp) <= layout.BODY_ROWS


def test_double_height_used_for_short_event_only():
    assert paginate_alert(mk(event="Flood Warning"), 889, STATUS, None).subpages[0].double_height_title
    long = mk(event="Severe Thunderstorm Warning Extended Area")
    assert not paginate_alert(long, 889, STATUS, None).subpages[0].double_height_title


@given(alerts_st)
def test_prop_continuation_labels(a):
    page = paginate_alert(a, 889, STATUS, None)
    prev_section = None
    for sp in page.subpages:
        first = sp.body[0]
        assert first.label
        if sp.k > 1 and prev_section is not None and first.text.endswith("(CONT.)"):
            assert first.text[: -len(" (CONT.)")] == prev_section
        for r in sp.body:
            if r.label:
                prev_section = r.text.removesuffix(" (CONT.)")


def test_long_instruction_continues_with_label():
    a = mk(instruction=" ".join(["Take shelter now."] * 80))
    page = paginate_alert(a, 889, STATUS, None)
    assert page.subpages[-1].total == len(page.subpages) > 2
    labels = [r.text for sp in page.subpages[1:] for r in sp.body if r.label]
    assert "ACTION (CONT.)" in labels


def test_hard_split_only_for_long_words():
    a = mk(description="x" * 100)
    rows = [r.text for sp in paginate_alert(a, 889, STATUS, None).subpages for r in sp.body]
    assert "x" * 40 in rows and "x" * 20 in rows


# ---- titles (5.3)

def test_titles_k1_and_continuation():
    a = mk(instruction=" ".join(["Take shelter now."] * 80))
    sps = paginate_alert(a, 889, STATUS, None).subpages
    n = len(sps)
    assert sps[0].title == "Flood Warning"
    assert sps[1].title == f"Flood Warning (CONT. 2/{n})"
    assert not sps[1].double_height_title


# ---- 7.4 index, notice, site model

def test_index_overflow_line_and_link():
    many = [mk(id=f"id{i}") for i in range(115)]
    pages = build_site_model(many, STATUS, "CA")
    idx = pages[0]
    last = idx.subpages[-1].body[-1]
    assert last.text == "NOT SHOWN: 4 MORE - SEE WEATHER.GOV"
    assert last.href == "https://www.weather.gov/"
    assert len(pages) == 1 + 111
    assert pages[-1].number == 999
    assert len(idx.subpages) > 1
    assert idx.subpages[1].title.startswith("ALERT INDEX CA (CONT. 2/")
    for sp in idx.subpages:
        assert body_cost(sp) <= layout.BODY_ROWS


def test_index_empty_states():
    sp = paginate_index([], STATUS, "CA")[0].subpages[0]
    assert [r.text for r in sp.body] == ["NO ACTIVE ALERTS FOR CA"]
    for st_ in (DataStatus(NOW, True, False, 0), DataStatus(NOW, False, True, 0)):
        sp = paginate_index([], st_, "CA")[0].subpages[0]
        assert [r.text for r in sp.body] == ["NO UNEXPIRED ALERTS IN LAST GOOD DATA"]


def test_index_rows_have_number_severity_event():
    sp = paginate_index([mk()], STATUS, "CA")[0].subpages[0]
    assert sp.title == "ALERT INDEX CA"
    assert sp.body[0].text == "889 SEVERE Flood Warning" and sp.body[0].href == "889.html"
    assert sp.body[1].text == "Some County, EXP 11-13 16:00"


def test_notice_page():
    (page,) = paginate_notice("CA", STATUS)
    assert page.kind == "notice" and page.number == 888 and len(page.subpages) == 1
    text = " ".join(r.text for r in page.subpages[0].body)
    assert "ALERT DATA UNAVAILABLE - CHECK WEATHER.GOV" in text
    assert "NO ACTIVE ALERTS" not in text


@given(st.lists(alerts_st, max_size=12))
def test_prop_order_follows_ordering(xs):
    ordered = order_alerts(xs, NOW)
    pages = build_site_model(ordered, STATUS, "CA")
    nums, _ = assign_numbers(len(ordered))
    assert [p.number for p in pages[1:]] == nums
    assert [p.alert_id for p in pages[1:]] == [a.id for a in ordered]


# ---- 7.5 link graph

@given(st.lists(alerts_st, max_size=8))
def test_prop_link_graph(xs):
    pages = build_site_model(order_alerts(xs, NOW), STATUS, "CA")
    nav = build_nav(pages)
    existing = {(sp.number, sp.k) for p in pages for sp in p.subpages}
    assert set(nav) == existing
    for key, ctx in nav.items():
        for link in (ctx.prev, ctx.next, ctx.index):
            if link:
                assert (link.number, link.k) in existing
                assert len(link.text) <= layout.COLS and str(link.number) in link.text
        assert len(nav_rows(ctx)) <= layout.NAV_ROWS
        if key != (888, 1):
            assert ctx.index and (ctx.index.number, ctx.index.k) == (888, 1)
    seen, frontier = {(888, 1)}, [(888, 1)]
    while frontier:
        ctx = nav[frontier.pop()]
        for link in (ctx.prev, ctx.next):
            if link and (link.number, link.k) not in seen:
                seen.add((link.number, link.k))
                frontier.append((link.number, link.k))
    assert seen == existing


# ---- 7.6 examples

def test_header_text_pnnn_k_on_every_subpage():
    a = mk(instruction=" ".join(["Take shelter now."] * 80))
    for sp in paginate_alert(a, 890, STATUS, None).subpages:
        assert header_text(sp, "CA").startswith(f"P890/{sp.k} CA ")
    for sp in paginate_index([mk()] * 3, STATUS, "CA")[0].subpages:
        assert header_text(sp, "CA").startswith(f"P888/{sp.k}")


def test_alert_page_shows_source_and_not_stable():
    rows = [r for sp in paginate_alert(mk(), 889, STATUS, None).subpages for r in sp.body]
    text = " ".join(r.text for r in rows)
    assert "ID urn:x:1" in text and NOT_STABLE in text
    link = [r for r in rows if r.href == "https://api.weather.gov/alerts/x"]
    assert [r.text for r in link] == ["SOURCE ALERT JSON (api.weather.gov)"]
    assert any("OPENS RAW JSON" in r.text for r in rows)


def test_section_order_summary_description_action():
    rows = [r.text for sp in paginate_alert(mk(), 889, STATUS, None).subpages for r in sp.body if r.label]
    assert rows.index("SUMMARY") < rows.index("DESCRIPTION") < rows.index("ACTION")


def test_index_alias_matches_page_888():
    pages = build_site_model([mk()], STATUS, "CA")
    assert INDEX_ALIAS == ("index.html", filename(888, 1))
    assert pages[0].number == 888


def test_status_and_footer_rows():
    full = DataStatus(NOW, True, True, 3)
    assert not any("DATA AS OF" in r.text for r in status_rows(DataStatus(None, False, False, 0)))
    texts = [r.text for r in status_rows(full)]
    assert texts[0] == "DATA AS OF 2026-11-13 14:00 UTC"
    assert layout.STALE_TEXT in texts and "SKIPPED UNREADABLE ALERTS: 3" in texts
    assert len(texts) == layout.STATUS_ROWS
    assert [r.text for r in footer_rows(False)][0] == layout.DISCLAIMER
    assert footer_rows(True)[1].href == layout.WEATHER_GOV


# ---- review r1 #2, #3: word-boundary truncation

LONG_EVENT = "Small Craft Advisory For Hazardous Seas And Winds Extended"
LONG_AREA = "Yosemite NP outside of the valley; Greater Lake Tahoe Area; Lassen Volcanic National Park"


def _ends_on_word_boundary(cut: str, full: str) -> bool:
    """`cut` (without the trailing ...) is a prefix of `full` ending exactly at a word end."""
    return full.startswith(cut) and (len(cut) == len(full) or full[len(cut)] == " ")


def test_index_area_is_cut_at_a_word_with_ellipsis_and_no_space_before_comma():
    sp = paginate_index([mk(area_desc=LONG_AREA)], STATUS, "CA")[0].subpages[0]
    detail = sp.body[1].text
    assert len(detail) <= layout.COLS and detail.endswith(", EXP 11-13 16:00")
    area = detail.rsplit(", EXP", 1)[0]
    assert area.endswith("...") and not area.endswith(" ...") and not area.endswith(" ")
    assert _ends_on_word_boundary(area[:-3], LONG_AREA)


def test_index_area_that_fits_is_untouched_and_trailing_space_is_not_left_before_comma():
    sp = paginate_index([mk(area_desc="Eastern Sierra Slopes Extra Words")], STATUS, "CA")[0].subpages[0]
    assert " ," not in sp.body[1].text


def test_index_link_label_is_cut_at_a_word_with_ellipsis():
    sp = paginate_index([mk(event=LONG_EVENT)], STATUS, "CA")[0].subpages[0]
    text = sp.body[0].text
    assert len(text) <= layout.COLS and text.endswith("...")
    assert text.startswith("889 SEVERE ")
    assert _ends_on_word_boundary(text[len("889 SEVERE "):-3], LONG_EVENT)


def test_index_link_label_with_one_huge_word_is_still_marked():
    sp = paginate_index([mk(event="X" * 80)], STATUS, "CA")[0].subpages[0]
    assert sp.body[0].text.endswith("...") and len(sp.body[0].text) == layout.COLS


def test_short_index_labels_are_not_marked():
    sp = paginate_index([mk()], STATUS, "CA")[0].subpages[0]
    assert "..." not in sp.body[0].text and "..." not in sp.body[1].text


@given(alerts_st)
def test_prop_index_rows_never_cut_mid_word(a):
    from page888.paginate import _flat

    sp = paginate_index([a], STATUS, "CA")[0].subpages[0]
    link, detail = sp.body[0].text, sp.body[1].text
    assert len(link) <= layout.COLS and len(detail) <= layout.COLS
    assert not detail.rsplit(", EXP", 1)[0].endswith(" ")  # no stray space before our comma
    event = _flat(a.event) or "NOT STATED"
    prefix = f"889 {a.severity.name} "
    assert link.startswith(prefix)
    label = link[len(prefix):]
    if label.endswith("..."):
        cut = label[:-3]
        assert event.startswith(cut) and cut == cut.rstrip()
        assert len(cut) == 0 or _ends_on_word_boundary(cut, event) or len(link) == layout.COLS
    else:
        assert label == event


def _nav_for(event: str, instruction: str = "") -> list:
    a = mk(event=event, instruction=instruction or " ".join(["Take shelter now."] * 80))
    pages = build_site_model([a], STATUS, "CA")
    return list(build_nav(pages).items())


def test_nav_labels_keep_full_number_and_cut_title_at_a_word():
    seen = 0
    for (number, k), ctx in _nav_for(LONG_EVENT):
        for link in (ctx.prev, ctx.next, ctx.index):
            if link is None:
                continue
            seen += 1
            assert len(link.text) <= layout.COLS
            assert f" {link.number}/{link.k}" in link.text, link.text
            assert not re.search(r"\(CONT\. ?\d*$|\(CONT$", link.text.removesuffix("..."))
            if link.text.endswith("..."):
                body = link.text[: -3]
                assert not body.endswith(" ")
    assert seen > 4


def test_nav_label_for_continuation_page_has_no_dangling_cont():
    items = dict(_nav_for("Winter Storm Warning"))
    ctx = items[(889, 3)]
    assert ctx.prev.text == "PREV 889/2 Winter Storm Warning"
    assert ctx.next.text == "NEXT 889/4 Winter Storm Warning"


@given(alerts_st)
def test_prop_nav_labels_are_word_aligned(a):
    pages = build_site_model([a], STATUS, "CA")
    titles = {(sp.number, sp.k): sp.title for p in pages for sp in p.subpages}
    for ctx in build_nav(pages).values():
        for link in (ctx.prev, ctx.next, ctx.index):
            if link is None:
                continue
            head = {"prev": "PREV", "next": "NEXT", "index": "INDEX"}[link.kind]
            pre = f"{head} {link.number}/{link.k} "
            assert link.text.startswith(pre.rstrip())
            rest = link.text[len(pre):]
            full = re.sub(r" \(CONT\. [0-9]+/[0-9]+\)$", "", titles[(link.number, link.k)])
            if rest == full or rest == "":
                continue
            assert rest.endswith("...")
            cut = rest[:-3]
            assert full.startswith(cut) and cut == cut.rstrip()
            assert len(cut) == 0 or _ends_on_word_boundary(cut, full) or len(link.text) == layout.COLS


# ---- review r1 #4: notice site status

def test_notice_status_rows_have_no_data_as_of():
    rows = status_rows(DataStatus(None, False, False, 0))
    assert rows and not any("DATA AS OF" in r.text for r in rows)
    assert all(len(r.text) <= layout.COLS for r in rows)


# ---- review r1 #5: expiry date on the index

def test_index_exp_shows_date_and_time():
    a = mk(expires=datetime(2026, 11, 17, 4, 0, tzinfo=timezone(timedelta(hours=-8))))
    sp = paginate_index([a], STATUS, "CA")[0].subpages[0]
    assert sp.body[1].text.endswith("EXP 11-17 04:00")
    sp = paginate_index([mk(expires=None)], STATUS, "CA")[0].subpages[0]
    assert sp.body[1].text.endswith("EXP NOT STATED")


# ---- review r1 #6: message expiry versus event end

def _details(a):
    rows = [r for sp in paginate_alert(a, 889, STATUS, None).subpages for r in sp.body]
    start = next(i for i, r in enumerate(rows) if r.label and r.text == "DETAILS")
    end = next(i for i, r in enumerate(rows) if r.label and r.text == "SOURCE")
    return [r.text for r in rows[start + 1:end] if not r.label]


def test_details_show_message_expiry_and_ends_separately():
    ends = datetime(2026, 11, 17, 4, 0, tzinfo=timezone(timedelta(hours=-8)))
    a = mk(message_expires=NOW + timedelta(hours=2), ends=ends)
    d = _details(a)
    assert any(t.startswith("MESSAGE EXPIRES 2026-11-13 16:00") for t in d)
    assert any(t.startswith("ENDS 2026-11-17 04:00 -08:00") for t in d)
    assert "= 2026-11-17 12:00 UTC" in d
    assert not any(t.startswith("EXPIRES ") for t in d)


def test_details_ends_not_stated_when_absent():
    d = _details(mk(ends=None))
    assert "ENDS NOT STATED" in d


# ---- review r1 #9: unbreakable tokens

def test_long_id_rows_join_without_space_and_link_has_short_name():
    long_id = "urn:oid:2.49.0.1.840.0." + "6d93" * 20
    a = mk(id=long_id)
    rows = [r for sp in paginate_alert(a, 889, STATUS, None).subpages for r in sp.body]
    start = next(i for i, r in enumerate(rows) if r.text.startswith("ID "))
    chunks = [rows[start]]
    for r in rows[start + 1:]:
        if not r.join:
            break
        chunks.append(r)
    assert len(chunks) > 1 and not chunks[0].join and all(c.join for c in chunks[1:])
    assert "".join(c.text for c in chunks) == "ID " + long_id
    assert all(len(c.text) <= layout.COLS for c in chunks)


def test_source_link_name_uses_host_only_when_it_is_plain_ascii():
    rows = [r for sp in paginate_alert(mk(source_url="https://alerts.example.gov/a/b"), 889, STATUS, None).subpages
            for r in sp.body if r.href]
    assert [r.text for r in rows] == ["SOURCE ALERT JSON (alerts.example.gov)"]
    rows = [r for sp in paginate_alert(mk(source_url="https://" + "h" * 60 + ".example/x"), 889, STATUS, None).subpages
            for r in sp.body if r.href]
    assert [r.text for r in rows] == ["SOURCE ALERT JSON"]


# ---- review r1 #11: rows are space-joined in text mode

def test_footer_rows_are_not_glued():
    # covered in test_render (HTML level); the model keeps them as separate rows
    assert len(footer_rows(True)) == 2
