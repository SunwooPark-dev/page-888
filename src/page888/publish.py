"""Publish a verified site by directory swap with crash recovery (R14.2-R14.4, design section 6).

POSIX `rename` cannot replace a non-empty directory, so the swap is: write
`.site.tmp`, rename `site` to `site.old`, rename the temp dir to `site`,
delete `site.old`. `recover` repairs a crash between the two renames.
"""
from __future__ import annotations

import os
import re
import shutil
from pathlib import Path
from typing import Mapping

_NAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")


def _tmp(out_dir: Path) -> Path:
    return out_dir.parent / ".site.tmp"


def _old(out_dir: Path) -> Path:
    return out_dir.parent / f"{out_dir.name}.old"


def recover(out_dir: Path) -> None:
    """Repair leftovers of an interrupted publish. Run at the start of every build."""
    out_dir = Path(out_dir)
    tmp, old = _tmp(out_dir), _old(out_dir)
    if tmp.exists():
        shutil.rmtree(tmp, ignore_errors=True)
    if old.exists():
        if out_dir.exists():
            shutil.rmtree(old)
        else:
            os.rename(old, out_dir)


def publish(files: Mapping[str, str], out_dir: Path) -> None:
    """Replace `out_dir` with exactly `files` (name to text); on failure keep the previous site."""
    out_dir = Path(out_dir)
    for name in files:
        if not _NAME_RE.fullmatch(name) or ".." in name:
            raise ValueError(f"unsafe file name {name!r}")
    out_dir.parent.mkdir(parents=True, exist_ok=True)
    recover(out_dir)
    tmp, old = _tmp(out_dir), _old(out_dir)
    try:
        tmp.mkdir()
        for name, text in files.items():
            (tmp / name).write_bytes(text.encode("utf-8"))
    except BaseException:
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    had_site = out_dir.exists()
    try:
        if had_site:
            os.rename(out_dir, old)
        os.rename(tmp, out_dir)
    except BaseException:
        if had_site and old.exists() and not out_dir.exists():
            os.rename(old, out_dir)
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    if old.exists():
        shutil.rmtree(old, ignore_errors=True)
