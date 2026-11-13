"""Text normalisation, wrapping and time display (R3.6, R3.8, R6.2).

`normalise_text` is deliberately lossy: everything becomes printable ASCII
(plus paragraph-break newlines). The explicit `ASCII_MAP` runs first, then
NFKD decomposition drops combining marks, and anything left becomes `?`.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timezone

# Explicit table (R3.6). Values are ASCII.
ASCII_MAP: dict[str, str] = {
    "\u00a0": " ", "\u2002": " ", "\u2003": " ", "\u2009": " ", "\u202f": " ", "\u3000": " ",
    "\u2010": "-", "\u2011": "-", "\u2012": "-", "\u2013": "-", "\u2014": "-", "\u2015": "-",
    "\u2212": "-",
    "\u2018": "'", "\u2019": "'", "\u201a": "'", "\u2032": "'",
    "\u201c": '"', "\u201d": '"', "\u201e": '"', "\u2033": '"',
    "\u2026": "...",
    "\u00b0": "DEG",
    "\u2022": "*", "\u00b7": "*",
    "\u00d7": "x", "\u00b1": "+/-",
    "\u00bd": "1/2", "\u00bc": "1/4", "\u00be": "3/4",
    "\u2028": "\n", "\u2029": "\n\n",
    # invisible format characters: dropped
    "\u00ad": "", "\u200b": "", "\u200c": "", "\u200d": "", "\u2060": "", "\ufeff": "",
}

_NEWLINE_RUN = re.compile(r"[ \n]*\n[ \n]*")


def _ascii_char(c: str) -> str:
    mapped = ASCII_MAP.get(c)
    if mapped is not None:
        return mapped
    if c == "\n" or 0x20 <= ord(c) <= 0x7E:
        return c
    if c == "\t":
        return " "
    if unicodedata.category(c) in ("Cc", "Cf", "Cs"):
        return ""
    out = []
    for d in unicodedata.normalize("NFKD", c):
        if unicodedata.combining(d):
            continue
        out.append(d if 0x20 <= ord(d) <= 0x7E else "?")
    return "".join(out)


def normalise_text(s: str) -> str:
    """Printable ASCII; a single newline becomes a space, 2+ become one paragraph break.

    Idempotent. Control characters are removed, spaces collapsed, and the
    result has no leading or trailing whitespace.
    """
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    s = "".join(_ascii_char(c) for c in s)
    s = _NEWLINE_RUN.sub(lambda m: "\n\n" if m.group().count("\n") >= 2 else " ", s)
    s = re.sub(r" {2,}", " ", s)
    return s.strip(" \n")


def _wrap_paragraph(text: str, width: int) -> list[str]:
    rows: list[str] = []
    line = ""
    for word in text.split():
        while len(word) > width:  # hard-split a word longer than a row (R6.2)
            if line:
                rows.append(line)
                line = ""
            rows.append(word[:width])
            word = word[width:]
        if not line:
            line = word
        elif len(line) + 1 + len(word) <= width:
            line += " " + word
        else:
            rows.append(line)
            line = word
    if line:
        rows.append(line)
    return rows


def wrap(text: str, width: int = 40) -> list[str]:
    """Word-wrap to `width`. A paragraph break becomes one empty row.

    Every non-whitespace character is kept, in order (R6.4).
    """
    if width < 1:
        raise ValueError("width must be >= 1")
    rows: list[str] = []
    for para in re.split(r"\n\s*\n", text):
        para_rows = _wrap_paragraph(para, width)
        if not para_rows:
            continue
        if rows:
            rows.append("")
        rows.extend(para_rows)
    return rows


def _offset(dt: datetime) -> str:
    off = dt.utcoffset()
    total = int(off.total_seconds()) if off is not None else 0
    sign = "+" if total >= 0 else "-"
    minutes = abs(total) // 60
    return f"{sign}{minutes // 60:02d}:{minutes % 60:02d}"


def _stamp(dt: datetime) -> str:
    return f"{dt.year:04d}-{dt.month:02d}-{dt.day:02d} {dt.hour:02d}:{dt.minute:02d}"


def format_time(dt: datetime) -> tuple[str, str]:
    """(`YYYY-MM-DD HH:MM +HH:MM`, `= YYYY-MM-DD HH:MM UTC`), to the minute (R3.8)."""
    return f"{_stamp(dt)} {_offset(dt)}", f"= {_stamp(dt.astimezone(timezone.utc))} UTC"
