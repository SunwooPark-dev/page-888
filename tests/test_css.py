"""Static CSS and markup checks (task 8.5; P22, P33; R13.6, R13.8-R13.11, R13.14-R13.16, R13.19)."""
from __future__ import annotations

import re

from hypothesis import given

from htmlcheck import Doc
from page888.models import DataStatus
from page888.paginate import build_site_model
from page888.palette import ALLOWED_PAIRS, MIN_UI_CONTRAST, PALETTE, contrast_ratio
from page888.render import CSS, render_site
from test_paginate import NOW, STATUS, alerts_st, mk

HEX_TO_NAME = {v: k for k, v in PALETTE.items()}


def rules(css: str = CSS) -> list[tuple[list[str], dict[str, str]]]:
    out = []
    for block in css.split("}"):
        if "{" not in block:
            continue
        sel, body = block.split("{", 1)
        decls = dict(d.split(":", 1) for d in body.split(";") if ":" in d)
        out.append(([s.strip() for s in sel.split(",")], {k.strip(): v.strip() for k, v in decls.items()}))
    return out


def page_css() -> str:
    files = render_site(build_site_model([mk()], STATUS, "CA"), STATUS, "CA")
    return Doc(files["889.html"]).find("style")[0].text()


def test_css_in_page_is_generated_css():
    assert page_css() == CSS


@given(alerts_st)
def test_prop_css_identical_on_every_page(a):
    files = render_site(build_site_model([a], STATUS, "CA"), STATUS, "CA")
    for html in files.values():
        assert Doc(html).find("style")[0].text() == CSS


def test_no_outline_removal():
    flat = re.sub(r"\s+", "", CSS).lower()
    assert "outline:none" not in flat and "outline:0" not in flat and "outline-style:none" not in flat
    assert any("outline" in d for _, d in rules())


def test_no_animation():
    low = CSS.lower()
    for bad in ("@keyframes", "animation", "transition", "blink"):
        assert bad not in low


def test_grid_in_ch_without_px_width():
    tt = [d for sels, d in rules() if any(".tt" in s for s in sels)]
    assert tt and any(d.get("width", "").endswith("ch") for d in tt)
    for sels, d in rules():
        if any(".tt" in s or ".row" in s for s in sels):
            for prop in ("width", "min-width", "max-width"):
                assert "px" not in d.get(prop, ""), (sels, prop)
    assert "monospace,monospace" in CSS.replace(" ", "")


def test_link_targets_at_least_24px():
    link = [d for sels, d in rules() if "a" in sels]
    assert link
    for prop in ("min-height", "min-width"):
        assert any(float(re.fullmatch(r"([\d.]+)px", d.get(prop, "0px")).group(1)) >= 24 for d in link)


def test_viewport_meta():
    html = render_site(build_site_model([mk()], STATUS, "CA"), STATUS, "CA")["888.html"]
    metas = [e for e in Doc(html).find("meta") if e.attrs.get("name") == "viewport"]
    assert len(metas) == 1
    assert metas[0].attrs["content"] == "width=device-width, initial-scale=1"
    assert "user-scalable" not in html and "maximum-scale" not in html


def test_double_height_by_css_scaling():
    assert any(d.get("font-size") == "2em" for sels, d in rules() if "h1.dh" in sels)


# ---- colours

def _name(value: str) -> str:
    assert value in HEX_TO_NAME, value
    return HEX_TO_NAME[value]


def test_only_palette_hex_colours():
    for h in re.findall(r"#[0-9a-fA-F]+", CSS):
        assert h in HEX_TO_NAME, h
    no_selectors = re.sub(r"[^{}]*\{", "{", CSS)  # declarations only
    assert not re.search(r"rgb|hsl|(?<![-\w])(?:white|black|red|blue|green|yellow|cyan|magenta)(?![-\w])", no_selectors)


def test_prop_css_pairs_allowed():
    pairs = []
    for sels, d in rules():
        has_fg, has_bg = "color" in d, "background" in d
        assert has_fg == has_bg, sels  # every colour rule sets both, so the pair is explicit
        if has_fg:
            pairs.append((sels, (_name(d["color"]), _name(d["background"]))))
    assert pairs
    for sels, pair in pairs:
        assert pair in ALLOWED_PAIRS, (sels, pair)
        assert contrast_ratio(PALETTE[pair[0]], PALETTE[pair[1]]) >= 4.5


def test_explicit_body_link_visited_hover_focus_colours():
    by_sel = {s: d for sels, d in rules() for s in sels}
    for sel in ("body.tt", "a", "a:visited", "a:hover", "h1", "h2"):
        assert "color" in by_sel[sel] and "background" in by_sel[sel], sel
    assert by_sel["a"]["color"] == by_sel["a:visited"]["color"] == by_sel["a:hover"]["color"] == "#00ffff"
    assert by_sel["a"]["background"] == "#000000"
    assert by_sel["body.tt"]["color"] == "#ffffff" and by_sel["body.tt"]["background"] == "#000000"
    for sel in ("a:focus", "a:focus-visible"):
        assert "#ffff00" in by_sel[sel]["outline"]


def test_prop_links_only_on_black_or_blue_with_focus_contrast():
    link_bg = {d["background"] for sels, d in rules() if "a" in sels}
    assert {_name(b) for b in link_bg} <= {"black", "blue"}
    outline = next(d["outline"] for sels, d in rules() if "a:focus-visible" in sels)
    colour = re.search(r"#[0-9a-f]{6}", outline).group(0)
    for bg in ("black", "blue"):
        assert contrast_ratio(colour, PALETTE[bg]) >= MIN_UI_CONTRAST
    assert (HEX_TO_NAME[colour], "black") in ALLOWED_PAIRS


@given(alerts_st)
def test_prop_links_not_inside_bands(a):
    """Links sit on the black page background; colour bands never contain a link."""
    files = render_site(build_site_model([a], DataStatus(NOW, True, True, 2), "CA"), STATUS, "CA")
    for html in files.values():
        for link in Doc(html).find("a"):
            p = link.parent
            while p is not None:
                assert not any(c.startswith("b-") for c in p.classes)
                p = p.parent
