"""verify_site: violations, size budget, allowlists, CSS checks (tasks 9.1-9.3)."""
from __future__ import annotations

import pytest
from hypothesis import given, strategies as st

from page888.models import DataStatus
from page888.paginate import build_site_model
from page888.render import render_site
from page888.verify import ALLOWED_ATTRS, ALLOWED_ELEMENTS, MAX_PAGE_BYTES, verify_site
from test_paginate import NOW, STATUS, alerts_st, mk, status_st

HOSTILE = '<script>alert("x")</script>&"\'<b onclick=1>'
LONG = " ".join(["Take shelter now."] * 120)


def site(alerts, status=STATUS, area="CA"):
    return render_site(build_site_model(alerts, status, area), status, area)


def good() -> dict[str, str]:
    return site([mk(), mk(id="urn:x:2", description=LONG, instruction=LONG)])


def mutate(name: str, old: str, new: str, count: int = 1) -> dict[str, str]:
    files = good()
    assert old in files[name], old
    files[name] = files[name].replace(old, new, count)
    return files


def found(files, needle: str) -> bool:
    return any(needle in v for v in verify_site(files))


def test_good_site_has_no_violations():
    assert verify_site(good()) == []


# ---- one test per violation type (9.1)

BAD = {
    "script element": ("<main>", "<main><script>1</script>"),
    "event handler attribute onclick": ("<main>", '<main onclick="x()">'),
    "javascript: URL": ('<a class="row" href="888.html"', '<a class="row" href="javascript:x()"'),
    "noscript": ("<main>", "<main><noscript>x</noscript>"),
    "meta refresh": ("<head>", '<head><meta http-equiv="refresh" content="1">'),
    "external resource <a src>": ("<main>", '<main><a src="https://e.example/">x</a>'),
    "disallowed element <iframe>": ("<main>", "<main><iframe></iframe>"),
    "disallowed element <img>": ("<main>", '<main><img src="x.png">'),
    "disallowed element <link>": ("<head>", '<head><link rel="stylesheet" href="https://e.example/a.css">'),
    "disallowed attribute <p style>": ("<main>", '<main><p style="color:red">x</p>'),
    "aria-hidden": ("<main>", '<main><p aria-hidden="true">x</p>'),
    "non-https link": ('<a class="row" href="888.html"', '<a class="row" href="http://example.com/"'),
    "dangling link": ('<a class="row" href="888.html"', '<a class="row" href="777.html"'),
    "missing html lang": ('<html lang="en">', "<html>"),
    "main count 2 != 1": ("</main>", "</main><main>x</main>"),
    "h1 count 2 != 1": ("</main>", "<h1>x</h1></main>"),
    "nav without aria-label": ('<nav aria-label="Page navigation">', "<nav>"),
    "empty element <span>": ("<main>", "<main><span></span>"),
    "nbsp run": ("<main>", "<main><p>a&nbsp;&nbsp;b</p>"),
    "external url() in CSS": ("</style>", "a{background:url(https://e.example/x.png)}</style>"),
    "outline removal": ("</style>", "a:focus{outline:none}</style>"),
    "animation": ("</style>", "a{animation:x 1s}</style>"),
    "px width": ("</style>", ".row{width:300px}</style>"),
    "colour pair not allowed": ("</style>", "p{color:#0000ff;background:#000000}</style>"),
    "viewport": ("initial-scale=1", "initial-scale=1, user-scalable=no"),
}


@pytest.mark.parametrize("needle", sorted(BAD))
def test_each_violation_type_detected(needle):
    old, new = BAD[needle]
    files = mutate("889.html", old, new)
    assert found(files, needle), (needle, verify_site(files))


def test_empty_title_detected():
    import re

    files = good()
    files["889.html"] = re.sub(r"<title>.*?</title>", "<title> </title>", files["889.html"], count=1)
    assert found(files, "missing or empty title")


def test_missing_viewport_detected():
    files = good()
    files["889.html"] = files["889.html"].replace('<meta name="viewport" content="width=device-width, initial-scale=1">', "")
    assert found(files, "viewport")


def test_duplicate_title_detected_but_index_exempt():
    files = good()
    assert verify_site(files) == []  # index.html shares 888's title
    other = files["889.html"]
    files["890.html"] = other
    assert found(files, "duplicate title")


def test_missing_h1_on_index_and_subpages():
    files = good()
    for name in ("888.html", "889.html", "889-2.html"):
        if name not in files:
            continue
        bad = dict(files)
        bad[name] = bad[name].replace("<h1", "<h3", 1)
        assert found(bad, "h1 count 0 != 1"), name


def test_hostile_text_escaped_passes():
    files = site([mk(event=HOSTILE, description=HOSTILE, instruction=HOSTILE, area_desc=HOSTILE)])
    assert verify_site(files) == []


# ---- size budget in UTF-8 bytes

def _sized(target: int) -> dict[str, str]:
    files = good()
    page = files["889.html"]
    comment_overhead = len("<!---->")
    room = target - len(page.encode("utf-8")) - comment_overhead
    assert room >= 0
    pad = "\u00e9" * (room // 2) + "x" * (room % 2)
    files["889.html"] = page.replace("</body>", f"<!--{pad}--></body>", 1)
    assert len(files["889.html"].encode("utf-8")) == target
    assert len(files["889.html"]) < target  # characters != bytes: multi-byte proves byte counting
    return files


def test_size_boundary_in_utf8_bytes():
    assert MAX_PAGE_BYTES == 51200
    assert verify_site(_sized(51199)) == []
    assert found(_sized(51200), "size 51200 >= 51200")


@given(st.lists(alerts_st, max_size=3), status_st)
def test_prop_page_size_budget(alerts, status):
    for name, html in site(alerts, status).items():
        assert len(html.encode("utf-8")) < MAX_PAGE_BYTES, name


def test_worst_case_alert_under_budget():
    worst = mk(event="E" * 400, area_desc="W" * 3000, headline="H" * 400,
               description=("lorem " * 2000), instruction=("go " * 2000), sender_name="S" * 400,
               source_url="https://api.weather.gov/alerts/" + "a" * 500)
    files = site([worst] * 5, DataStatus(NOW, True, True, 99999))
    assert verify_site(files) == []


# ---- allowlist (R8.3)

@given(st.lists(alerts_st, max_size=3), status_st)
def test_prop_allowlist(alerts, status):
    files = site(alerts, status)
    assert verify_site(files) == []
    from htmlcheck import Doc

    for html in files.values():
        doc = Doc(html)
        for e in doc.all:
            assert e.tag in ALLOWED_ELEMENTS
            assert set(e.attrs) <= ALLOWED_ATTRS.get(e.tag, frozenset()), (e.tag, e.attrs)


def test_allowlist_is_exact_for_templates():
    from htmlcheck import Doc

    seen_tags: set[str] = set()
    seen_attrs: dict[str, set[str]] = {}
    many = [mk(id=f"urn:x:{i}", description=LONG) for i in range(4)]
    for status in (STATUS, DataStatus(NOW, True, True, 3)):
        for html in site(many, status).values():
            for e in Doc(html).all:
                seen_tags.add(e.tag)
                seen_attrs.setdefault(e.tag, set()).update(e.attrs)
    assert seen_tags <= ALLOWED_ELEMENTS
    for tag, attrs in seen_attrs.items():
        assert attrs <= ALLOWED_ATTRS.get(tag, frozenset())


# ---- 9.4: tools/check_pages.py is a subset of verify_site (R14.11, P34)

def _load_check_pages():
    import importlib.util
    from pathlib import Path

    path = Path(__file__).resolve().parent.parent / "tools" / "check_pages.py"
    spec = importlib.util.spec_from_file_location("check_pages", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _subset_holds(files: dict[str, str]) -> None:
    cp = _load_check_pages()
    verified = verify_site(files)
    for name, html in files.items():
        raw = html.encode("utf-8")
        checker = cp.PageChecker(True)
        checker.feed(raw.decode("utf-8"))
        checker.close()
        problems = checker.finish()
        if len(raw) >= cp.MAX_BYTES:
            problems.append(f"size {len(raw)} >= {cp.MAX_BYTES}")
        for p in problems:
            assert any(v == f"{name}: {p}" for v in verified), (name, p, verified)


def test_check_pages_clean_on_good_site():
    assert _subset_holds(good()) is None


@pytest.mark.parametrize("needle", sorted(BAD))
def test_prop_check_pages_subset_of_verify_bad_pages(needle):
    old, new = BAD[needle]
    _subset_holds(mutate("889.html", old, new))


def test_prop_check_pages_subset_of_verify_size_and_text():
    _subset_holds(_sized(51200))
    # visible alert text that merely looks like CSS must not trip either checker
    files = site([mk(description="see url(https://example.com/x) in text")])
    assert verify_site(files) == []
    _subset_holds(files)


@given(st.lists(alerts_st, max_size=2), status_st)
def test_prop_check_pages_subset_of_verify(alerts, status):
    files = site(alerts, status)
    _subset_holds(files)
    cp = _load_check_pages()
    for html in files.values():
        c = cp.PageChecker(True)
        c.feed(html)
        c.close()
        assert c.finish() == []


def test_check_pages_cli_agrees_on_site(tmp_path, capsys):
    cp = _load_check_pages()
    for name, html in good().items():
        (tmp_path / name).write_text(html, encoding="utf-8")
    assert cp.main([str(tmp_path), "--strict"]) == 0
    (tmp_path / "889.html").write_text(
        (tmp_path / "889.html").read_text(encoding="utf-8").replace("<main>", "<main><script>1</script>", 1),
        encoding="utf-8",
    )
    assert cp.main([str(tmp_path), "--strict"]) == 1
