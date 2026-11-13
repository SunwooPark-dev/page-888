"""Publish: sibling temp dir, directory swap, crash recovery (task 12.1; P30; R14.2-R14.4, R2.8)."""
from __future__ import annotations

import os
from pathlib import Path

import pytest
from hypothesis import given, strategies as st

from page888.publish import publish, recover

names = st.from_regex(r"[0-9]{3}(-[1-9])?\.html", fullmatch=True)
files_st = st.dictionaries(names, st.text(max_size=50), min_size=1, max_size=5)


def snapshot(d: Path) -> dict[str, bytes]:
    return {p.name: p.read_bytes() for p in sorted(d.iterdir())}


def good(extra: dict[str, str] | None = None) -> dict[str, str]:
    f = {"888.html": "<p>new 888</p>", "index.html": "<p>new 888</p>", "889.html": "<p>new</p>"}
    f.update(extra or {})
    return f


def test_publish_creates_site(tmp_path):
    out = tmp_path / "site"
    publish(good(), out)
    assert snapshot(out) == {k: v.encode() for k, v in good().items()}
    assert (out / "index.html").read_bytes() == (out / "888.html").read_bytes()
    assert sorted(p.name for p in tmp_path.iterdir()) == ["site"]  # no temp or .old left


def test_stale_files_removed_on_success(tmp_path):
    out = tmp_path / "site"
    publish(good({"890.html": "old", "889-2.html": "old"}), out)
    publish(good(), out)
    assert set(snapshot(out)) == set(good())


@given(files_st, files_st)
def test_prop_publish_replaces_exactly(first, second):
    import tempfile

    with tempfile.TemporaryDirectory() as t:
        out = Path(t) / "site"
        publish(first, out)
        publish(second, out)
        assert snapshot(out) == {k: v.encode("utf-8") for k, v in second.items()}


def test_prop_publish_atomic_on_failure(tmp_path, monkeypatch):
    """A write failure leaves the previous site byte-identical and removes the temp dir."""
    out = tmp_path / "site"
    publish(good(), out)
    before = snapshot(out)
    real = Path.write_bytes
    calls = {"n": 0}

    def flaky(self, data):
        calls["n"] += 1
        if calls["n"] == 2:
            raise OSError("disk full")
        return real(self, data)

    monkeypatch.setattr(Path, "write_bytes", flaky)
    with pytest.raises(OSError):
        publish(good({"890.html": "x"}), out)
    monkeypatch.undo()
    assert snapshot(out) == before
    assert sorted(p.name for p in tmp_path.iterdir()) == ["site"]


def test_failure_in_swap_restores_previous_site(tmp_path, monkeypatch):
    out = tmp_path / "site"
    publish(good(), out)
    before = snapshot(out)
    real = os.rename

    def fail_second(src, dst, *a, **k):
        if Path(src).name == ".site.tmp":
            raise OSError("boom")
        return real(src, dst, *a, **k)

    monkeypatch.setattr(os, "rename", fail_second)
    with pytest.raises(OSError):
        publish(good({"890.html": "x"}), out)
    monkeypatch.undo()
    assert snapshot(out) == before
    assert sorted(p.name for p in tmp_path.iterdir()) == ["site"]


def test_rejects_unsafe_file_names(tmp_path):
    for bad in ("../x.html", "a/b.html", "", ".hidden"):
        with pytest.raises(ValueError):
            publish({bad: "x"}, tmp_path / "site")
    assert not (tmp_path / "site").exists()


# ---- recovery

def test_recover_site_missing_old_present(tmp_path):
    old = tmp_path / "site.old"
    old.mkdir()
    (old / "888.html").write_text("keep")
    recover(tmp_path / "site")
    assert (tmp_path / "site" / "888.html").read_text() == "keep"
    assert not old.exists()


def test_recover_both_present_deletes_old(tmp_path):
    (tmp_path / "site").mkdir()
    (tmp_path / "site" / "888.html").write_text("new")
    (tmp_path / "site.old").mkdir()
    (tmp_path / "site.old" / "888.html").write_text("old")
    recover(tmp_path / "site")
    assert (tmp_path / "site" / "888.html").read_text() == "new"
    assert not (tmp_path / "site.old").exists()


def test_recover_removes_leftover_tmp(tmp_path):
    tmp = tmp_path / ".site.tmp"
    tmp.mkdir()
    (tmp / "x.html").write_text("partial")
    recover(tmp_path / "site")
    assert not tmp.exists()
    assert not (tmp_path / "site").exists()


def test_recover_noop_when_clean_or_parent_missing(tmp_path):
    recover(tmp_path / "site")
    recover(tmp_path / "nope" / "site")


def test_publish_after_simulated_crash_between_renames(tmp_path):
    out = tmp_path / "site"
    publish(good(), out)
    os.rename(out, tmp_path / "site.old")  # crash after step 2
    (tmp_path / ".site.tmp").mkdir()
    publish(good({"890.html": "n"}), out)  # recovers first
    assert "890.html" in snapshot(out)
    assert sorted(p.name for p in tmp_path.iterdir()) == ["site"]
