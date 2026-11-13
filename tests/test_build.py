"""Build orchestration, exit codes and cross-cutting checks (tasks 13.1, 13.3; R14.1, R14.6, R14.7, R10.5-R10.8, R11)."""
from __future__ import annotations

import re
import sys
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

import page888
from page888 import build as build_mod
from page888 import paginate as paginate_mod
from page888.build import build
from page888.cache import store_cache
from page888.config import Config
from page888.fetch import FetchError
from page888.layout import FALLBACK_TEXT, STALE_TEXT

ROOT = Path(__file__).parent.parent
NOW = datetime(2026, 11, 13, 14, 0, tzinfo=timezone.utc)  # before the fixtures' expiries
UA = "Test-Agent-Secret (secret@example.invalid)"
NOTICE = "ALERT DATA UNAVAILABLE"


def cfg(tmp_path: Path, **kw) -> Config:
    base = Config(user_agent=UA, area="CA", min_interval_s=60, stale_after_s=1800,
                  cache_dir=tmp_path / "cache", out_dir=tmp_path / "site")
    return replace(base, **kw)


def serving(body: bytes):
    return lambda _cfg: body


def failing(status: int | None = None):
    def f(_cfg):
        raise FetchError("down", status)

    return f


def run(tmp_path, fetcher, capsys=None, **kw):
    code = build(cfg(tmp_path, **kw), NOW, fetcher)
    return code, tmp_path / "site"


def text_of(site: Path) -> str:
    """Visible text of every page: tags removed, whitespace collapsed (wrapped rows rejoin)."""
    raw = "\n".join(p.read_text(encoding="utf-8") for p in sorted(site.glob("*.html")))
    raw = re.sub(r"<style>.*?</style>", " ", raw, flags=re.S)
    return " ".join(re.sub(r"<[^>]*>", " ", raw).split())


# ---- 13.1 end to end

def test_normal_build(tmp_path, fixture_bytes, capsys):
    code, site = run(tmp_path, serving(fixture_bytes("normal.json")))
    assert code == 0
    assert (site / "888.html").read_bytes() == (site / "index.html").read_bytes()
    assert len(list(site.glob("889*.html"))) >= 1
    assert STALE_TEXT not in text_of(site) and FALLBACK_TEXT not in text_of(site)


def test_log_line_has_counts_and_no_user_agent(tmp_path, fixture_bytes, capsys):
    run(tmp_path, serving(fixture_bytes("normal.json")))
    out = capsys.readouterr()
    line = (out.out + out.err).strip().splitlines()[-1]
    for key in ("area=CA", "alerts=", "skipped=", "pages=", "largest_bytes=", "data_age_s="):
        assert key in line
    assert UA not in out.out + out.err and "secret" not in out.out + out.err


def test_empty_feed_says_no_active_alerts(tmp_path, fixture_bytes):
    code, site = run(tmp_path, serving(fixture_bytes("empty.json")))
    assert code == 0
    assert "NO ACTIVE ALERTS FOR CA" in text_of(site)


def test_test_status_alerts_are_dropped(tmp_path, fixture_bytes):
    code, site = run(tmp_path, serving(fixture_bytes("test-status.json")))
    assert code == 0
    names = {p.name for p in site.iterdir()}
    assert "889.html" in names  # the one Actual alert has a page
    assert not any(n.startswith("890") for n in names)  # the Test alert has none


def test_many_alerts_overflow_line(tmp_path, fixture_bytes):
    code, site = run(tmp_path, serving(fixture_bytes("many-alerts.json")))
    assert code == 0
    assert re.search(r"NOT SHOWN: 19 MORE - SEE WEATHER\.GOV", text_of(site))
    assert len(list(site.glob("*.html"))) > 111


def test_hostile_text_is_escaped_and_build_passes(tmp_path, fixture_bytes):
    code, site = run(tmp_path, serving(fixture_bytes("hostile-text.json")))
    assert code == 0
    assert "<script" not in text_of(site).lower()


def test_stale_cache_with_failed_fetch_is_fallback_and_stale(tmp_path, fixture_bytes):
    c = cfg(tmp_path)
    store_cache(c.cache_dir, "CA", fixture_bytes("normal.json"), NOW - timedelta(hours=2))
    code, site = run(tmp_path, failing())
    assert code == 0
    t = text_of(site)
    assert STALE_TEXT in t and FALLBACK_TEXT in t


def test_fresh_fallback_without_stale(tmp_path, fixture_bytes):
    store_cache(cfg(tmp_path).cache_dir, "CA", fixture_bytes("normal.json"), NOW - timedelta(minutes=5))
    code, site = run(tmp_path, failing())
    t = text_of(site)
    assert code == 0 and FALLBACK_TEXT in t and STALE_TEXT not in t


def test_fallback_with_every_alert_expired(tmp_path, fixture_bytes):
    store_cache(cfg(tmp_path).cache_dir, "CA", fixture_bytes("normal.json"), NOW - timedelta(days=3))
    code = build(cfg(tmp_path), NOW + timedelta(days=3), failing())
    t = text_of(tmp_path / "site")
    assert code == 0
    assert "NO UNEXPIRED ALERTS IN LAST GOOD DATA" in t and "NO ACTIVE ALERTS" not in t


def test_no_data_publishes_notice_site_exit_3(tmp_path):
    code, site = run(tmp_path, failing())
    t = text_of(site)
    assert code == 3
    assert NOTICE in t and "NO ACTIVE ALERTS" not in t
    assert not list(site.glob("889*.html"))


def test_no_data_replaces_previously_published_alerts(tmp_path, fixture_bytes):
    assert run(tmp_path, serving(fixture_bytes("normal.json")))[0] == 0
    (tmp_path / "cache" / "alerts-CA.json").unlink()
    code, site = run(tmp_path, failing())
    assert code == 3 and NOTICE in text_of(site) and not list(site.glob("889*.html"))


def test_garbage_response_without_cache_is_exit_3(tmp_path):
    code, site = run(tmp_path, serving(b"<html>oops</html>"))
    assert code == 3 and NOTICE in text_of(site)


def test_4xx_without_cache_is_exit_5_with_notice(tmp_path, capsys):
    code, site = run(tmp_path, failing(400))
    assert code == 5 and NOTICE in text_of(site)
    err = capsys.readouterr().err
    assert "400" in err and "CA" in err


def test_4xx_with_cache_falls_back_exit_0(tmp_path, fixture_bytes):
    store_cache(cfg(tmp_path).cache_dir, "CA", fixture_bytes("normal.json"), NOW - timedelta(minutes=5))
    assert run(tmp_path, failing(400))[0] == 0


def test_cache_for_another_area_is_not_used(tmp_path, fixture_bytes):
    store_cache(tmp_path / "cache", "TX", fixture_bytes("normal.json"), NOW - timedelta(seconds=5))
    code, site = run(tmp_path, failing())  # CA build
    assert code == 3 and not list(site.glob("889*.html"))


def test_verify_failure_exit_4_keeps_previous_site(tmp_path, fixture_bytes, monkeypatch, capsys):
    assert run(tmp_path, serving(fixture_bytes("normal.json")))[0] == 0
    site = tmp_path / "site"
    before = {p.name: p.read_bytes() for p in site.iterdir()}
    monkeypatch.setattr(build_mod, "verify_site", lambda files: ["888.html: forced violation"])
    (tmp_path / "cache" / "alerts-CA.json").unlink()
    code = build(cfg(tmp_path), NOW, serving(fixture_bytes("empty.json")))
    assert code == 4
    assert {p.name: p.read_bytes() for p in site.iterdir()} == before
    assert "forced violation" in capsys.readouterr().err


def test_main_config_error_exit_2(monkeypatch, capsys):
    from page888.__main__ import main

    monkeypatch.delenv("PAGE888_USER_AGENT", raising=False)
    assert main() == 2
    assert "PAGE888_USER_AGENT" in capsys.readouterr().err
    monkeypatch.setenv("PAGE888_USER_AGENT", "x (x@example.invalid)")
    monkeypatch.setenv("PAGE888_AREA", "ca")
    assert main() == 2


def test_main_runs_build_with_env(tmp_path, monkeypatch, fixture_bytes):
    from page888 import __main__ as m

    monkeypatch.setenv("PAGE888_USER_AGENT", "x (x@example.invalid)")
    monkeypatch.setenv("PAGE888_AREA", "CA")
    monkeypatch.setenv("PAGE888_OUT", str(tmp_path / "out"))
    monkeypatch.setenv("PAGE888_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setattr(m, "fetch_alerts", lambda c: fixture_bytes("empty.json"))
    assert m.main() == 0
    assert (tmp_path / "out" / "888.html").exists()


# ---- 13.3

def test_stage_order_spy(tmp_path, fixture_bytes, monkeypatch):
    seen: list[str] = []

    def spy(name, fn):
        def wrapper(*a, **k):
            if name not in seen:
                seen.append(name)
            return fn(*a, **k)

        return wrapper

    monkeypatch.setattr(build_mod, "parse_feed", spy("parse", build_mod.parse_feed))
    monkeypatch.setattr(build_mod, "order_alerts", spy("order", build_mod.order_alerts))
    monkeypatch.setattr(paginate_mod, "normalise_text", spy("normalise", paginate_mod.normalise_text))
    monkeypatch.setattr(paginate_mod, "summarise", spy("summarise", paginate_mod.summarise))
    monkeypatch.setattr(build_mod, "render_site", spy("render", build_mod.render_site))
    monkeypatch.setattr(build_mod, "verify_site", spy("verify", build_mod.verify_site))
    monkeypatch.setattr(build_mod, "publish", spy("publish", build_mod.publish))

    def fetcher(_c):
        seen.append("fetch")
        return fixture_bytes("normal.json")

    assert build(cfg(tmp_path), NOW, fetcher) == 0
    pos = {n: i for i, n in enumerate(seen)}
    assert pos["fetch"] < pos["parse"] < pos["order"]
    assert pos["order"] < min(pos["normalise"], pos["summarise"])
    assert max(pos["normalise"], pos["summarise"]) < pos["render"] < pos["verify"] < pos["publish"]


def test_runtime_imports_are_stdlib_only():
    std = sys.stdlib_module_names
    bad: list[str] = []
    for path in (ROOT / "src" / "page888").glob("*.py"):
        for line in path.read_text(encoding="utf-8").splitlines():
            m = re.match(r"\s*(?:from\s+(\S+)\s+import|import\s+(\S+))", line)
            if not m:
                continue
            mod = (m.group(1) or m.group(2)).split(".")[0].rstrip(",")
            if mod and not mod.startswith(".") and mod not in std and mod != "page888":
                bad.append(f"{path.name}: {mod}")
    assert not bad


def test_no_hardcoded_user_agent_in_src():
    for path in (ROOT / "src" / "page888").glob("*.py"):
        s = path.read_text(encoding="utf-8")
        assert "SunwooPark" not in s and "github.com" not in s and "Page888 (" not in s


def test_no_hardcoded_personal_handle_in_workflows():
    files = [p for p in (ROOT / ".github").rglob("*") if p.is_file()]
    assert files
    for path in files:
        s = path.read_text(encoding="utf-8")
        assert "SunwooPark" not in s, path
        assert not re.search(r"Page888 \(https?://github\.com/", s), path
    wf = (ROOT / ".github" / "workflows" / "pages.yml").read_text(encoding="utf-8")
    assert re.search(r"PAGE888_USER_AGENT:.*\$\{\{ github\.server_url \}\}/\$\{\{ github\.repository \}\}", wf)


def test_scheduled_runs_skip_the_pytest_step():
    wf = (ROOT / ".github" / "workflows" / "pages.yml").read_text(encoding="utf-8")
    step = re.search(r"- name: Run tests\n(.*?)\n\n", wf, re.S)
    assert step, "Run tests step not found"
    assert "if: github.event_name != 'schedule'" in step.group(1)
    assert "pytest -q" in step.group(1)


def test_no_tracking_strings_in_output(tmp_path, fixture_bytes):
    _, site = run(tmp_path, serving(fixture_bytes("normal.json")))
    t = text_of(site).lower()
    for word in ("analytics", "gtag", "pixel", "cookie", "tracking", "localstorage", "beacon"):
        assert word not in t


_BROADCASTER = re.compile(r"ceefax|oracle teletext|prestel", re.I)
_NEGATED_RULE = re.compile(r"\b(no|not|never|avoid|without|forbid\w*)\b.{0,60}?(ceefax|oracle teletext|prestel)", re.I)
# Files that state the rule itself may name the term, but only inside a negated rule line.
_RULE_FILES = ["docs/BRIEF.md", "docs/reviews/*.md", ".kiro/steering/*.md", ".kiro/specs/page888/*.md",
               ".kiro/agents/*.json"]


def _files(patterns):
    out = []
    for pat in patterns:
        out += [p for p in ROOT.glob(pat) if p.is_file()]
    return out


def test_no_broadcaster_names_in_output_src_or_docs(tmp_path, fixture_bytes):
    _, site = run(tmp_path, serving(fixture_bytes("normal.json")))
    strict = [text_of(site)]
    strict_files = _files(["README.md", "docs/*.md", "src/page888/*.py", "tools/*.py"])
    rule_files = set(_files(_RULE_FILES))
    for path in strict_files:
        if path not in rule_files:
            strict.append(path.read_text(encoding="utf-8"))
    for blob in strict:
        assert not _BROADCASTER.search(blob)
    for path in rule_files:
        for line in path.read_text(encoding="utf-8").splitlines():
            if _BROADCASTER.search(line):
                assert _NEGATED_RULE.search(line), f"{path.name}: {line.strip()[:80]}"


def test_broadcaster_scan_catches_a_non_negated_line():
    assert _BROADCASTER.search("Ceefax-style, no JavaScript")
    assert not _NEGATED_RULE.search("Ceefax-style, no JavaScript")
    assert _NEGATED_RULE.search("Do not use the name Ceefax")


def test_attribution_sender_and_source_on_alert_pages_and_weather_gov_on_index(tmp_path, fixture_bytes):
    _, site = run(tmp_path, serving(fixture_bytes("normal.json")))
    pages = [p.read_text(encoding="utf-8") for p in sorted(site.glob("889*.html"))]
    assert all("NOT AN OFFICIAL WARNING CHANNEL" in x for x in pages)
    assert "SENDER NWS" in " ".join(re.sub(r"<[^>]*>", " ", x) for x in pages)
    alert_page = "\n".join(pages)
    links = re.findall(r'<a href="(https://api\.weather\.gov/alerts/[^"]+)">', alert_page)
    assert len(links) == 1 and links[0].endswith("urn:oid:test.2")
    page_text = " ".join(re.sub(r"<[^>]*>", " ", re.sub(r"<style>.*?</style>", " ", alert_page, flags=re.S)).split())
    assert re.search(r"\bID urn:oid:", page_text)
    assert "SOURCE ALERT JSON (api.weather.gov)" in page_text
    assert "OPENS RAW JSON" in page_text
    assert "https://www.weather.gov/" in (site / "888.html").read_text(encoding="utf-8")


def test_test_status_fixture_only_publishes_the_actual_alert(tmp_path, fixture_bytes):
    _, site = run(tmp_path, serving(fixture_bytes("test-status.json")))
    t = text_of(site)
    assert "urn:oid:test.3" in t
    assert "urn:oid:test.1" not in t and "urn:oid:test.2" not in t


# ---- review r1 #1, #4, #8

def test_incomplete_read_on_every_attempt_falls_back_to_cache(tmp_path, fixture_bytes):
    import http.client

    store_cache(cfg(tmp_path).cache_dir, "CA", fixture_bytes("normal.json"), NOW - timedelta(minutes=5))

    class Broken:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        status = 200

        def read(self, n=-1):
            raise http.client.IncompleteRead(b"x", 9)

    from page888.fetch import fetch_alerts

    def fetcher(c):
        return fetch_alerts(c, opener=lambda req, timeout=None: Broken(), sleep=lambda s: None)

    code, site = run(tmp_path, fetcher)
    assert code == 0
    assert FALLBACK_TEXT in text_of(site) and (site / "889.html").exists()


def test_notice_site_does_not_claim_data_as_of(tmp_path):
    code, site = run(tmp_path, failing())
    assert code == 3
    for page in site.glob("*.html"):
        assert "DATA AS OF" not in page.read_text(encoding="utf-8")
    assert "DATA AS OF" in text_of(_built(tmp_path))


def _built(tmp_path):
    # a normal build for the contrast: real data does carry the timestamp
    other = tmp_path / "other"
    other.mkdir()
    from page888.build import build as b
    from pathlib import Path as P

    fixture = (ROOT / "tests" / "fixtures" / "normal.json").read_bytes()
    c = replace(cfg(other), out_dir=other / "site", cache_dir=other / "cache")
    assert b(c, NOW, lambda _c: fixture) == 0
    return other / "site"
