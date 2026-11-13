"""Static checks on rendered HTML (R8, R9, R12, R13). The authoritative checker.

`verify_site` returns a list of violations (empty means OK), each prefixed with
the file name. Message texts for the cheap checks are shared with
`tools/check_pages.py`, which is a subset of this module (R14.11, P34).
Colour logic comes from `palette`; nothing is duplicated here.
"""
from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import Mapping
from urllib.parse import urlsplit

from .palette import ALLOWED_PAIRS, MIN_TEXT_CONTRAST, MIN_UI_CONTRAST, PALETTE, contrast_ratio

MAX_PAGE_BYTES = 51200  # a page must be strictly smaller (R12)
INDEX_ALIAS = "index.html"

ALLOWED_ELEMENTS: frozenset[str] = frozenset(
    {"html", "head", "meta", "title", "style", "body", "header", "main", "nav", "footer",
     "h1", "h2", "p", "span", "a", "ul", "ol", "li"}
)
ALLOWED_ATTRS: Mapping[str, frozenset[str]] = {
    "html": frozenset({"lang"}),
    "meta": frozenset({"charset", "name", "content"}),
    "body": frozenset({"class"}),
    "h1": frozenset({"class"}),
    "h2": frozenset({"class"}),
    "p": frozenset({"class"}),
    "span": frozenset({"class"}),
    "a": frozenset({"href", "class"}),
    "nav": frozenset({"aria-label"}),
}

_VOID = frozenset({"meta", "br", "link", "img", "hr", "input"})
_RESOURCE_ATTRS = ("src", "href", "action", "data", "poster", "srcset", "formaction")
_PAGE_FILE = re.compile(r"[0-9]{3}(-[0-9]+)?\.html")
_HEX_TO_NAME = {v: k for k, v in PALETTE.items()}
_COLOUR_WORD = re.compile(
    r"(?<![-\w])(?:rgb|hsl|white|black|red|blue|green|yellow|cyan|magenta)(?![-\w])"
)


def _is_external(value: str) -> bool:
    return value.strip().lower().startswith(("http://", "https://", "//"))


def _px(value: str) -> float | None:
    m = re.fullmatch(r"([0-9.]+)px", value.strip())
    return float(m.group(1)) if m else None


def css_rules(css: str) -> list[tuple[list[str], dict[str, str]]]:
    """Split simple CSS into (selectors, declarations) pairs."""
    out = []
    for block in css.split("}"):
        if "{" not in block:
            continue
        sel, body = block.split("{", 1)
        decls = {}
        for d in body.split(";"):
            if ":" in d:
                k, v = d.split(":", 1)
                decls[k.strip()] = v.strip()
        out.append(([s.strip() for s in sel.split(",")], decls))
    return out


def check_css(css: str) -> list[str]:
    """Checks on the inline stylesheet (R13.6, R13.8-R13.11, R13.15, R13.16)."""
    found: list[str] = []
    low = re.sub(r"\s+", "", css).lower()
    if "outline:none" in low or "outline:0" in low or "outline-style:none" in low:
        found.append("outline removal")
    for word in ("@keyframes", "animation", "transition", "blink"):
        if word in low:
            found.append(f"animation or motion in CSS ({word})")
    if "url(" in low:
        found.append("external url() in CSS" if "http" in low or "//" in low else "url() in CSS")
    for h in re.findall(r"#[0-9a-fA-F]+", css):
        if h.lower() not in _HEX_TO_NAME:
            found.append(f"colour {h} not in palette")
    decls_only = re.sub(r"[^{}]*\{", "{", css)
    if _COLOUR_WORD.search(decls_only):
        found.append("named or functional colour in CSS")
    rules = css_rules(css)
    link_decls: list[dict[str, str]] = []
    for sels, d in rules:
        if ("color" in d) != ("background" in d):
            found.append(f"colour rule without explicit pair: {','.join(sels)}")
        if "color" in d and "background" in d:
            fg, bg = _HEX_TO_NAME.get(d["color"].lower()), _HEX_TO_NAME.get(d["background"].lower())
            if fg is None or bg is None or (fg, bg) not in ALLOWED_PAIRS:
                found.append(f"colour pair not allowed: {d['color']} on {d['background']}")
            elif contrast_ratio(PALETTE[fg], PALETTE[bg]) < MIN_TEXT_CONTRAST:
                found.append(f"contrast below {MIN_TEXT_CONTRAST}: {fg} on {bg}")
            if any(s == "a" for s in sels):
                if bg not in ("black", "blue"):
                    found.append("links must sit on black or blue")
        if any(".tt" in s or ".row" in s for s in sels):
            for prop in ("width", "min-width", "max-width"):
                if "px" in d.get(prop, ""):
                    found.append(f"px width on {','.join(sels)}")
        if "a" in sels:
            link_decls.append(d)
        if any(s.startswith("a:focus") for s in sels):
            m = re.search(r"#[0-9a-fA-F]{6}", d.get("outline", ""))
            if not m:
                found.append("focus style without outline colour")
            else:
                for bg in ("black", "blue"):
                    if contrast_ratio(m.group(0).lower(), PALETTE[bg]) < MIN_UI_CONTRAST:
                        found.append(f"focus outline contrast below {MIN_UI_CONTRAST} on {bg}")
    for prop in ("min-height", "min-width"):
        if not any((_px(d.get(prop, "")) or 0) >= 24 for d in link_decls):
            found.append(f"link {prop} below 24px")
    if not any("outline" in d for _, d in rules):
        found.append("no focus outline rule")
    return found


class _Checker(HTMLParser):
    def __init__(self, files: Mapping[str, str]) -> None:
        super().__init__(convert_charrefs=True)
        self.files = files
        self.problems: list[str] = []
        self.h1 = self.main = 0
        self.has_lang = self.has_title = self.in_title = False
        self.title = ""
        self.navs: list[bool] = []
        self.viewport: list[str] = []
        self.css = ""
        self.in_style = False
        self.stack: list[dict] = []

    def add(self, msg: str) -> None:
        if msg not in self.problems:
            self.problems.append(msg)

    def handle_starttag(self, tag, attrs):
        a = {k.lower(): (v or "") for k, v in attrs}
        if self.stack:
            self.stack[-1]["content"] = True
        if tag == "script":
            self.add("script element")
        if tag not in ALLOWED_ELEMENTS:
            self.add(f"disallowed element <{tag}>")
        if tag == "html" and a.get("lang", "").strip():
            self.has_lang = True
        if tag == "title":
            self.has_title = self.in_title = True
        if tag == "style":
            self.in_style = True
        if tag == "h1":
            self.h1 += 1
        if tag == "main":
            self.main += 1
        if tag == "nav":
            self.navs.append(bool(a.get("aria-label", "").strip()))
        if tag == "meta" and a.get("name") == "viewport":
            self.viewport.append(a.get("content", ""))
        if tag == "meta" and a.get("http-equiv", "").lower() == "refresh":
            self.add("meta refresh")
        allowed = ALLOWED_ATTRS.get(tag, frozenset())
        for name, value in a.items():
            if name.startswith("on"):
                self.add(f"event handler attribute {name}")
            if name == "aria-hidden":
                self.add("aria-hidden")
            if value.strip().lower().startswith("javascript:"):
                self.add("javascript: URL")
            if name not in allowed:
                self.add(f"disallowed attribute <{tag} {name}>")
            if name in _RESOURCE_ATTRS and _is_external(value) and not (tag == "a" and name == "href"):
                self.add(f"external resource <{tag} {name}>")
        if tag == "a":
            self.check_href(a.get("href", ""))
        if tag not in _VOID:
            classes = a.get("class", "").split()
            self.stack.append({"tag": tag, "content": False, "band": any(c.startswith("b-") for c in classes)})
            if tag == "a" and any(f["band"] for f in self.stack[:-1]):
                self.add("link inside a colour band")

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in _VOID and self.stack and self.stack[-1]["tag"] == tag:
            self.handle_endtag(tag)

    def check_href(self, href: str) -> None:
        h = href.strip()
        if h.lower().startswith("http://"):
            self.add("non-https link")
        elif h.lower().startswith("https://"):
            parts = urlsplit(h)
            if not parts.netloc or re.search(r"[\s\x00-\x1f\x7f]", href):
                self.add("malformed https link")
        elif h.lower().startswith("javascript:"):
            pass
        elif _PAGE_FILE.fullmatch(h):
            if h not in self.files:
                self.add(f"dangling link {h}")
        else:
            self.add(f"link target not allowed {h!r}")

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False
        if tag == "style":
            self.in_style = False
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i]["tag"] == tag:
                frame = self.stack[i]
                del self.stack[i:]
                if not frame["content"]:
                    self.add(f"empty element <{tag}>")
                if self.stack and frame["content"]:
                    self.stack[-1]["content"] = True
                break

    def handle_data(self, data):
        if self.in_title:
            self.title += data
        if self.in_style:
            self.css += data
        elif "\xa0\xa0" in data:
            self.add("nbsp run")
        if data.strip() and self.stack:
            self.stack[-1]["content"] = True
        if self.in_style and "url(" in data.lower() and "http" in data.lower():
            self.add("external url() in CSS")


def verify_page(name: str, html: str, files: Mapping[str, str]) -> tuple[list[str], str]:
    """Problems of one page (without file prefix) and its title."""
    problems: list[str] = []
    size = len(html.encode("utf-8"))
    if size >= MAX_PAGE_BYTES:
        problems.append(f"size {size} >= {MAX_PAGE_BYTES}")
    c = _Checker(files)
    c.feed(html)
    c.close()
    if not c.has_lang:
        c.add("missing html lang")
    if not c.has_title or not c.title.strip():
        c.add("missing or empty title")
    if c.main != 1:
        c.add(f"main count {c.main} != 1")
    if c.h1 != 1:
        c.add(f"h1 count {c.h1} != 1")
    if any(not ok for ok in c.navs):
        c.add("nav without aria-label")
    if not c.navs:
        c.add("no nav")
    if len(c.viewport) != 1:
        c.add("viewport meta missing or repeated")
    elif c.viewport[0] != "width=device-width, initial-scale=1" or "user-scalable" in html or "maximum-scale" in html:
        c.add("viewport meta restricts zoom")
    problems.extend(c.problems)
    problems.extend(check_css(c.css))
    return problems, c.title.strip()


def verify_site(files: Mapping[str, str]) -> list[str]:
    """All violations in `files` (name to HTML); empty list means the site passes."""
    out: list[str] = []
    titles: dict[str, str] = {}
    for name in sorted(files):
        problems, title = verify_page(name, files[name], files)
        out.extend(f"{name}: {p}" for p in problems)
        if name != INDEX_ALIAS and title:
            if title in titles:
                out.append(f"{name}: duplicate title (also {titles[title]})")
            titles[title] = name
    if INDEX_ALIAS in files and "888.html" in files and files[INDEX_ALIAS] != files["888.html"]:
        out.append(f"{INDEX_ALIAS}: not identical to 888.html")
    return out
