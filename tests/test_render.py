"""HTML rendering: escaping, links, structure, banners, index alias (tasks 8.2, 8.4, 7.6)."""
from __future__ import annotations

import re

from hypothesis import given, settings, strategies as st

from htmlcheck import Doc, Elem
from page888 import layout
from page888.models import DataStatus, Severity
from page888.paginate import NOT_STABLE, build_site_model
from page888.parse import https_url_or_empty
from page888.render import esc, render_site
from page888.text import normalise_text
from test_paginate import NOW, STATUS, alerts_st, mk, status_st

ALLOWED_TAGS = {"html", "head", "meta", "title", "style", "body", "header", "main", "nav",
                "footer", "h1", "h2", "p", "span", "a", "ul", "ol", "li"}
ALLOWED_ATTRS = {"html": {"lang"}, "meta": {"charset", "name", "content"}, "a": {"href", "class"},
                 "nav": {"aria-label", "class"}}
LONG = " ".join(["Take shelter now."] * 60)


def site(alerts, status=STATUS, area="CA"):
    return render_site(build_site_model(alerts, status, area), status, area)


def main_of(doc: Doc) -> Elem:
    return doc.find("main")[0]


def alert_docs(files, number=889):
    names = sorted((n for n in files if re.fullmatch(rf"{number}(-\d+)?\.html", n)), key=lambda n: (len(n), n))
    return [Doc(files[n]) for n in names]


def rendered_rows(doc: Doc) -> int:
    n = 0
    for e in doc.all:
        if "row" in e.classes:
            dh, p = False, e.parent
            while p is not None:
                dh = dh or (p.tag == "h1" and "dh" in p.classes)
                p = p.parent
            n += 2 if dh else 1
        if "gap" in e.classes:
            n += 1
    return n


# ---- esc

def test_esc_quotes_attributes():
    assert esc("<a href=\"x\">'&") == "&lt;a href=&quot;x&quot;&gt;&#x27;&amp;"


# ---- escaping (R8.1, R8.3, R8.4; P17)

@given(alerts_st, status_st)
def test_prop_escaping(a, status):
    files = site([a], status)
    for name, html in files.items():
        doc = Doc(html)
        assert set(doc.raw_tags) <= ALLOWED_TAGS, name
        for e in doc.all:
            assert set(e.attrs) <= ALLOWED_ATTRS.get(e.tag, {"class"}), (name, e.tag, e.attrs)
        body = re.sub(r"<style>.*?</style>", "", html, flags=re.S)
        assert "<script" not in body.lower()


@given(alerts_st)
def test_prop_escaping_keeps_text(a):
    """Hostile characters survive escaping: parsed text still holds description then instruction."""
    files = site([a])
    names = sorted(n for n in files if re.fullmatch(r"889(-\d+)?\.html", n))
    names.sort(key=lambda n: (len(n), n))
    flat = ""
    for n in names:
        m = main_of(Doc(files[n]))
        flat += "".join(p.flat() for p in m.find("p") if "status" not in p.classes)
    want = re.sub(r"\s+", "", normalise_text(a.description)) + re.sub(
        r"\s+", "", normalise_text(a.instruction) or "NO INSTRUCTION FIELD IN SOURCE - SEE DESCRIPTION"
    )
    assert want in flat


def test_hostile_markup_is_inert():
    a = mk(event="<script>alert(1)</script>", description='"><img src=x onerror=alert(1)>',
           area_desc="<b>&amp;</b>")
    for html in site([a]).values():
        assert "<script" not in html and "<img" not in html and "<b>" not in html
    doc = Doc(site([a])["889.html"])
    assert "<script>alert(1)</script>" in doc.find("h1")[0].text()


def test_attribute_values_are_escaped_with_quotes():
    url = "https://ex.example/a?x=\"1\"&y=<b>'z'"
    files = site([mk(source_url=url)])
    links = [e for n, h in files.items() if n.startswith("889") for e in Doc(h).find("a")
             if e.attrs["href"] == url]
    assert links and all(set(e.attrs) <= {"href", "class"} for e in links)


# ---- links (R8.2, R13.5; P18, P21)

def test_non_https_source_is_plain_text():
    for bad in ("javascript:alert(1)", "http://x.example/a", "https:///nohost", "ftp://x.example/"):
        doc = Doc(site([mk(source_url=bad)])["889.html"])
        assert all(e.attrs["href"] != bad for e in doc.find("a"))
    doc = Doc(site([mk(source_url="javascript:alert(1)")])["889.html"])
    assert "javascript:" not in " ".join(str(e.attrs.get("href")) for e in doc.find("a"))


@given(alerts_st)
def test_prop_https_links_only(a):
    for name, html in site([a, mk(id="b", source_url="http://x.example/")]).items():
        for e in Doc(html).find("a"):
            href = e.attrs["href"] or ""
            assert re.fullmatch(r"[0-9]{3}(-[0-9]+)?\.html", href) or href.startswith("https://"), (name, href)


@given(alerts_st, status_st)
def test_prop_no_script_no_external(a, status):
    for html in site([a], status).values():
        low = html.lower()
        for bad in ("<script", "<noscript", "javascript:", "http-equiv", "<iframe", "<link", "<img",
                    "@import", "url("):
            assert bad not in low, bad
        doc = Doc(html)
        for e in doc.all:
            assert not any(k.startswith("on") or k in ("src", "srcset", "action") for k in e.attrs)
            for k, v in e.attrs.items():
                if v and "://" in v:
                    assert e.tag == "a" and k == "href"


# ---- semantics (R13.1-R13.5, R13.12, R13.13; P20)

def _many():
    return [mk(id=f"id{i}", instruction=LONG if i == 0 else "Act now.") for i in range(30)]


def test_prop_semantics():
    files = site(_many())
    assert len(files) > 30
    titles: dict[str, list[str]] = {}
    for name, html in files.items():
        doc = Doc(html)
        assert html.startswith("<!DOCTYPE html>")
        assert doc.find("html")[0].attrs["lang"] == "en"
        t = doc.find("title")
        assert len(t) == 1 and t[0].text().strip()
        titles.setdefault(t[0].text(), []).append(name)
        assert len(doc.find("h1")) == 1
        assert len(doc.find("main")) == 1
        navs = doc.find("nav")
        assert navs and all(n.attrs.get("aria-label") for n in navs)
        assert len({n.attrs["aria-label"] for n in navs}) == len(navs)
        assert not [e for e in doc.all if "aria-hidden" in e.attrs]
        assert not doc.empty_elements(), name
        assert "&nbsp;" not in html and "\u00a0" not in html
        assert len(doc.find("header")) == 1 and len(doc.find("footer")) == 1
    for names in titles.values():
        assert len(names) == 1 or set(names) == {"888.html", "index.html"}


def test_h1_on_index_and_continuation_pages():
    files = site(_many())
    assert "888-2.html" in files and "889-2.html" in files
    for n in ("888.html", "888-2.html", "889.html", "889-2.html"):
        assert len(Doc(files[n]).find("h1")) == 1
    assert Doc(files["889-2.html"]).find("h1")[0].text().startswith("Flood Warning (CONT. 2/")
    assert Doc(files["888-2.html"]).find("h1")[0].text().startswith("ALERT INDEX CA (CONT. 2/")


@given(alerts_st)
def test_prop_rendered_row_count(a):
    for html in site([a]).values():
        assert rendered_rows(Doc(html)) <= layout.ROWS


@given(alerts_st, status_st)
def test_prop_rendered_rows_with_banners(a, status):
    for html in site([a], status).values():
        doc = Doc(html)
        assert rendered_rows(doc) <= layout.ROWS
        assert all(len(e.text()) <= layout.COLS for e in doc.all if "row" in e.classes)


def test_h1_text_once_and_double_height():
    doc = Doc(site([mk(event="Flood Warning")])["889.html"])
    h1 = doc.find("h1")[0]
    assert "dh" in h1.classes
    assert [e for e in main_of(doc).walk() if e.tag == "h1"] == [h1]
    assert re.sub(r"\s+", "", h1.text()) == "FloodWarning"


def test_link_text_is_meaningful():
    for name, html in site(_many()).items():
        for e in Doc(html).find("a"):
            text = e.text().strip()
            assert text, name
            assert not re.search(r"click here|^here$|^link$", text, re.I)
            assert " ," not in text and not text.endswith((",", "-", "(", " ."))
            if re.fullmatch(r"[0-9]{3}(-[0-9]+)?\.html", e.attrs["href"] or ""):
                assert re.search(r"\b[0-9]{3}\b", text) and len(text.split()) >= 3, text


def test_prop_link_text_targets_exist():
    files = site(_many())
    for html in files.values():
        for e in Doc(html).find("a"):
            h = e.attrs["href"]
            if not h.startswith("https://"):
                assert h in files


# ---- severity, footer, status (R13.7, R10.1, R11.1; P23, P24)

def test_prop_severity_text():
    alerts = [mk(id=f"s{i}", severity=sev) for i, sev in enumerate(Severity)]
    files = site(alerts)
    index = main_of(Doc(files["888.html"])).text()
    for i, sev in enumerate(Severity):
        assert sev.name in index
        assert sev.name in main_of(Doc(files[f"{889 + i}.html"])).text()


@given(status_st)
def test_prop_footer_disclaimer_and_data_as_of(status):
    for html in site([mk(instruction=LONG)], status).values():
        doc = Doc(html)
        assert "NOT AN OFFICIAL WARNING CHANNEL" in doc.find("footer")[0].text()
        assert "DATA AS OF 2026-11-13 14:00 UTC" in main_of(doc).text()


def test_index_footer_links_to_weather_gov():
    doc = Doc(site([mk()])["888.html"])
    links = [e.attrs["href"] for e in doc.find("footer")[0].find("a")]
    assert links == ["https://www.weather.gov/"]
    other = Doc(site([mk()])["889.html"]).find("footer")[0]
    assert not other.find("a") and "US NWS" in other.text()


# ---- paragraph grouping (R13.17)

def test_prop_paragraph_grouping():
    a = mk(description="One.\n\nSecond para that wraps over two rows of forty.", instruction="Do.",
           area_desc="A", headline="H", urgency="Past", certainty="Unknown")
    kids = [e for d in alert_docs(site([a])) for e in main_of(d).children
            if isinstance(e, Elem) and e.tag != "h1" and "status" not in e.classes]
    h2s = [e for e in kids if e.tag == "h2"]
    assert [h.text() for h in h2s][:3] == ["SUMMARY", "DESCRIPTION", "ACTION"]
    names = [e.text() if e.tag == "h2" else e.tag for e in kids]
    d, ac = names.index("DESCRIPTION"), names.index("ACTION")
    paras = kids[d + 1 : ac]
    assert [p.tag for p in paras] == ["p", "p"]
    assert len(paras[0].find("span")) == 1
    assert len(paras[1].find("span")) >= 2
    assert all(isinstance(c, Elem) and c.tag == "span" and "row" in c.classes for c in paras[1].children if isinstance(c, Elem))
    assert all("row" in h.classes for h in h2s)


def test_row_order_summary_description_action():
    text = " ".join(main_of(d).text() for d in alert_docs(site([mk()])))
    assert text.index("SUMMARY") < text.index("DESCRIPTION") < text.index("ACTION")


def test_alert_page_id_link_and_not_stable():
    docs = alert_docs(site([mk()]))
    text = " ".join(main_of(d).text() for d in docs)
    assert "urn:x:1" in text and NOT_STABLE in text
    assert any(e.attrs["href"] == "https://api.weather.gov/alerts/x" for d in docs for e in d.find("a"))
    assert "SENDER NWS Test" in text


def test_index_is_a_list():
    doc = Doc(site([mk(id="a"), mk(id="b")])["888.html"])
    ol = main_of(doc).find("ol")
    assert len(ol) == 1 and len(ol[0].find("li")) == 2
    assert all(li.find("a") for li in ol[0].find("li"))


# ---- banners (R10.3, R10.4, R10.6, R10.7; P25) -- task 8.4

STALE, FALLBACK = layout.STALE_TEXT, layout.FALLBACK_TEXT


def _status_text(html: str) -> str:
    return " ".join(p.text() for p in main_of(Doc(html)).find("p") if "status" in p.classes)


@given(st.booleans(), st.booleans(), st.integers(0, 50))
def test_prop_banners_independent(stale, fallback, skipped):
    status = DataStatus(NOW, stale, fallback, skipped)
    for html in site([mk(instruction=LONG)], status).values():
        t = re.sub(r"\s+", " ", _status_text(html))
        assert (STALE in t) == stale
        assert (FALLBACK in t) == fallback
        assert (f"SKIPPED UNREADABLE ALERTS: {skipped}" in t) == (skipped > 0)
        assert "DATA AS OF" in t


def test_banners_have_text_class():
    html = site([mk()], DataStatus(NOW, True, True, 0))["889.html"]
    doc = Doc(html)
    assert [e.text() for e in doc.all if "b-red-black" in e.classes][0] == STALE


def test_empty_states():
    fresh = Doc(site([], STATUS)["888.html"])
    assert "NO ACTIVE ALERTS FOR CA" in main_of(fresh).text()
    for status in (DataStatus(NOW, True, False, 0), DataStatus(NOW, False, True, 0), DataStatus(NOW, True, True, 0)):
        t = main_of(Doc(site([], status)["888.html"])).text()
        assert "NO UNEXPIRED ALERTS IN LAST GOOD DATA" in t and "NO ACTIVE ALERTS" not in t
        assert t.index("NO UNEXPIRED") < t.index("DATA AS OF")


# ---- index.html alias (R5.10) -- task 7.6

def test_index_html_byte_identical_to_888():
    for alerts in ([], [mk()], _many()):
        files = site(alerts)
        assert files["index.html"].encode("utf-8") == files["888.html"].encode("utf-8")


def test_index_html_byte_identical_for_notice():
    from page888.paginate import paginate_notice

    pages = paginate_notice("CA", STATUS)
    files = render_site(pages, STATUS, "CA")
    assert set(files) == {"888.html", "index.html"}
    assert files["index.html"].encode() == files["888.html"].encode()
    t = main_of(Doc(files["888.html"])).text()
    assert "ALERT DATA UNAVAILABLE - CHECK WEATHER.GOV" in t and "NO ACTIVE ALERTS" not in t
    assert "NOT AN OFFICIAL WARNING CHANNEL" in Doc(files["888.html"]).find("footer")[0].text()
    assert any(e.attrs["href"] == "https://www.weather.gov/" for e in Doc(files["888.html"]).find("a"))


@settings(max_examples=30)
@given(st.lists(alerts_st, max_size=4))
def test_prop_index_alias(alerts):
    files = site(alerts)
    assert files["index.html"] == files["888.html"]


# ---- review r1 #2, #3, #9, #11 at HTML level

def _strip(html: str) -> str:
    html = re.sub(r"<style>.*?</style>", " ", html, flags=re.S)
    return re.sub(r"<[^>]*>", "", html)


def test_long_event_links_end_in_ellipsis_not_mid_word():
    a = mk(event="Small Craft Advisory For Hazardous Seas And Winds Extended",
           instruction=" ".join(["Take shelter now."] * 80))
    files = site([a])
    for name, html in files.items():
        for e in Doc(html).find("a"):
            t = e.text().strip()
            assert len(t) <= layout.COLS, (name, t)
            if "Small" in t:
                assert t.endswith("...") or t.endswith("Extended"), (name, t)


def test_long_id_continuation_rows_join_without_space():
    long_id = "urn:oid:2.49.0.1.840.0." + "6d93" * 20
    files = site([mk(id=long_id)])
    stripped = [_strip(h) for n, h in files.items() if n.startswith("889")]
    assert any(f"ID {long_id}" in t for t in stripped)  # whole token on one page, no space at row breaks


def test_source_link_has_short_name_and_page_says_it_is_raw_json():
    files = site([mk()])
    pages = [h for n, h in files.items() if n.startswith("889")]
    links = [e for h in pages for e in Doc(h).find("a") if (e.attrs["href"] or "").startswith("https://")]
    assert [e.text().strip() for e in links] == ["SOURCE ALERT JSON (api.weather.gov)"]
    holder = next(h for h in pages if "SOURCE ALERT JSON (api.weather.gov)" in h)
    assert "LINK BELOW OPENS RAW JSON DATA" in _strip(holder)  # statement and link share a page


def test_footer_rows_are_separated_by_a_space():
    for name in ("888.html", "889.html"):
        foot = re.search(r"<footer>(.*?)</footer>", site([mk()])[name], re.S).group(1)
        text = _strip(foot)
        assert "WARNING CHANNEL CHECK" in text or "WARNING CHANNEL SOURCE" in text, text


def test_index_item_rows_are_separated_by_a_space():
    html = site([mk()])["888.html"]
    items = re.findall(r"<li>(.*?)</li>", html, re.S)
    assert items and "889 SEVERE Flood Warning Some County" in _strip(items[0])


@given(st.one_of(
    st.text(max_size=60),
    st.sampled_from(["javascript:alert(1)", "http://x.example/", "https://[bad", "https:///x",
                     "https://u@x.example/\"><script>", "https://x.example/a b", "data:text/html,x"]),
))
def test_prop_hostile_source_url_never_becomes_a_link(url):
    from page888.verify import verify_site

    files = site([mk(source_url=url)])
    assert verify_site(files) == []
    safe = bool(https_url_or_empty(url))
    for html in files.values():
        for e in Doc(html).find("a"):
            href = e.attrs["href"] or ""
            if re.fullmatch(r"[0-9]{3}(-[0-9]+)?\.html", href) or href == "https://www.weather.gov/":
                continue
            assert safe and href == url == https_url_or_empty(href)
    if safe:
        assert any(e.attrs["href"] == url for n, h in files.items() if n.startswith("889") for e in Doc(h).find("a"))
