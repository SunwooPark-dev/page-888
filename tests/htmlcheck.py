"""Tiny DOM built on html.parser for render tests (test helper, not a test module)."""
from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import Iterator

VOID = {"meta", "br", "link", "img", "hr", "input"}


class Elem:
    def __init__(self, tag: str, attrs: dict[str, str | None], parent: "Elem | None") -> None:
        self.tag = tag
        self.attrs = attrs
        self.parent = parent
        self.children: list[Elem | str] = []

    @property
    def classes(self) -> list[str]:
        return (self.attrs.get("class") or "").split()

    def text(self) -> str:
        return "".join(c if isinstance(c, str) else c.text() for c in self.children)

    def flat(self) -> str:
        """Text with all whitespace removed."""
        return re.sub(r"\s+", "", self.text())

    def walk(self) -> Iterator["Elem"]:
        for c in self.children:
            if isinstance(c, Elem):
                yield c
                yield from c.walk()

    def find(self, tag: str) -> list["Elem"]:
        return [e for e in self.walk() if e.tag == tag]


class Doc(HTMLParser):
    def __init__(self, src: str) -> None:
        super().__init__(convert_charrefs=True)
        self.root = Elem("#root", {}, None)
        self.cur = self.root
        self.raw_tags: list[str] = []
        self.feed(src)
        self.close()

    def handle_starttag(self, tag, attrs):
        self.raw_tags.append(tag)
        e = Elem(tag, dict(attrs), self.cur)
        self.cur.children.append(e)
        if tag not in VOID:
            self.cur = e

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        e = self.cur
        while e is not self.root and e.tag != tag:
            e = e.parent  # type: ignore[assignment]
        if e is not self.root:
            self.cur = e.parent  # type: ignore[assignment]

    def handle_data(self, data):
        self.cur.children.append(data)

    # convenience
    def find(self, tag: str) -> list[Elem]:
        return self.root.find(tag)

    @property
    def all(self) -> list[Elem]:
        return list(self.root.walk())

    def empty_elements(self) -> list[Elem]:
        return [
            e for e in self.all
            if e.tag not in VOID and not e.text().strip() and not any(isinstance(c, Elem) for c in e.children)
        ]
