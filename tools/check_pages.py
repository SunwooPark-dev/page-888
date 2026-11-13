#!/usr/bin/env python3
"""Static budget/accessibility/no-JS checker for generated Page 888 HTML.

Usage: python3 tools/check_pages.py DIR [--strict]

Stdlib only. Exit 0 if all pages pass (or DIR does not exist yet), 1 otherwise.
--strict additionally rejects any http(s) URL outside a plain <a href>, any
<noscript>, <iframe>, <object>, <embed>, <link>, <style src>, meta refresh and
javascript: URLs (the no-JS guard run at Stop).
"""
from __future__ import annotations

import sys
from html.parser import HTMLParser
from pathlib import Path

MAX_BYTES = 51200  # 50 KB budget: size must be strictly below this
RESOURCE_ATTRS = ("src", "href", "action", "data", "poster", "srcset", "formaction")
STRICT_TAGS = {"noscript", "iframe", "object", "embed", "link", "form"}


def _is_external(value: str) -> bool:
    v = value.strip().lower()
    return v.startswith(("http://", "https://", "//"))


class PageChecker(HTMLParser):
    def __init__(self, strict: bool) -> None:
        super().__init__(convert_charrefs=True)
        self.strict = strict
        self.problems: list[str] = []
        self.h1 = 0
        self.main = 0
        self.has_lang = False
        self.in_title = False
        self.title_text = ""
        self.has_title = False
        self.navs: list[bool] = []
        self.in_style = False

    def _add(self, msg: str) -> None:
        if msg not in self.problems:
            self.problems.append(msg)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = {k.lower(): (v or "") for k, v in attrs}
        if tag == "script":
            self._add("script element")
        if tag == "html" and a.get("lang", "").strip():
            self.has_lang = True
        if tag == "style":
            self.in_style = True
        if tag == "title":
            self.has_title = True
            self.in_title = True
        if tag == "h1":
            self.h1 += 1
        if tag == "main":
            self.main += 1
        if tag == "nav":
            self.navs.append(bool(a.get("aria-label", "").strip()))
        for name, value in a.items():
            if name.startswith("on"):
                self._add(f"event handler attribute {name}")
            if value.strip().lower().startswith("javascript:"):
                self._add("javascript: URL")
            if name in RESOURCE_ATTRS and _is_external(value):
                if not (tag == "a" and name == "href"):
                    self._add(f"external resource <{tag} {name}>")
        if self.strict:
            if tag in STRICT_TAGS:
                self._add(f"disallowed element <{tag}>")
            if tag == "meta" and a.get("http-equiv", "").lower() == "refresh":
                self._add("meta refresh")
            if tag == "a" and a.get("href", "").strip().lower().startswith("http://"):
                self._add("non-https link")

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self.in_title = False
        if tag == "style":
            self.in_style = False

    def handle_data(self, data: str) -> None:
        if self.in_title:
            self.title_text += data
        if self.strict and self.in_style and "url(" in data.lower() and "http" in data.lower():
            self._add("external url() in CSS")

    def finish(self) -> list[str]:
        if not self.has_lang:
            self._add("missing html lang")
        if not self.has_title or not self.title_text.strip():
            self._add("missing or empty title")
        if self.main != 1:
            self._add(f"main count {self.main} != 1")
        if self.h1 != 1:
            self._add(f"h1 count {self.h1} != 1")
        if any(not ok for ok in self.navs):
            self._add("nav without aria-label")
        return self.problems


def check_file(path: Path, strict: bool) -> tuple[int, list[str]]:
    raw = path.read_bytes()
    problems: list[str] = []
    if len(raw) >= MAX_BYTES:
        problems.append(f"size {len(raw)} >= {MAX_BYTES}")
    checker = PageChecker(strict)
    checker.feed(raw.decode("utf-8", errors="replace"))
    checker.close()
    problems.extend(checker.finish())
    return len(raw), problems


def main(argv: list[str]) -> int:
    args = [a for a in argv if not a.startswith("--")]
    strict = "--strict" in argv
    if len(args) != 1:
        print("usage: check_pages.py DIR [--strict]", file=sys.stderr)
        return 2
    root = Path(args[0])
    if not root.is_dir():
        print(f"check_pages: {root} does not exist yet; nothing to check")
        return 0
    files = sorted(root.rglob("*.html"))
    failed = 0
    for f in files:
        size, problems = check_file(f, strict)
        rel = f.relative_to(root)
        if problems:
            failed += 1
            print(f"FAIL {rel} ({size} B): " + "; ".join(problems))
        else:
            print(f"OK   {rel} ({size} B)")
    print(f"check_pages: {len(files)} file(s), {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
