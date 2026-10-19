"""Tests for source_ledger.py — per-article source ledger."""

import json
import subprocess
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import source_ledger  # noqa: E402


def _article(tmp_path):
    art = tmp_path / "output"
    art.mkdir()
    md = art / "2026-10-19-tech-demo.md"
    md.write_text("# Demo\n", encoding="utf-8")
    return md


def test_add_creates_file_with_incrementing_ids(tmp_path):
    md = _article(tmp_path)
    s1 = source_ledger.add_source(md, url="https://example.com/a", title="来源A")
    s2 = source_ledger.add_source(md, url="https://example.com/b", title="来源B")
    assert s1["id"] == "src1"
    assert s2["id"] == "src2"
    ledger_path = md.with_suffix(".sources.yaml")
    assert ledger_path.exists()
    data = yaml.safe_load(ledger_path.read_text(encoding="utf-8"))
    assert [s["id"] for s in data["sources"]] == ["src1", "src2"]


def test_add_dedupes_by_url_and_updates_note(tmp_path):
    md = _article(tmp_path)
    source_ledger.add_source(md, url="https://example.com/a", title="旧标题")
    source_ledger.add_source(md, url="https://example.com/a", title="新标题", note="补充")
    sources = source_ledger.load_sources(md)
    assert len(sources) == 1
    assert sources[0]["title"] == "新标题"
    assert sources[0]["note"] == "补充"
    assert sources[0]["id"] == "src1"


def test_excerpt_and_verified_persisted(tmp_path):
    md = _article(tmp_path)
    source_ledger.add_source(
        md, url="https://example.com/c", excerpt="延迟从 12.4 ms 降到 9.8 ms",
        verified=True,
    )
    sources = source_ledger.load_sources(md)
    assert sources[0]["excerpt"] == "延迟从 12.4 ms 降到 9.8 ms"
    assert sources[0]["verified"] is True


def test_missing_file_returns_empty_list(tmp_path):
    md = _article(tmp_path)
    assert source_ledger.load_sources(md) == []


def test_cli_add_and_list(tmp_path):
    md = _article(tmp_path)
    proc = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "source_ledger.py"),
         "add", "--article", str(md), "--url", "https://example.com/x",
         "--title", "CLI来源", "--json"],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stderr
    added = json.loads(proc.stdout)
    assert added["id"] == "src1"

    proc = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "source_ledger.py"),
         "list", "--article", str(md), "--json"],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stderr
    items = json.loads(proc.stdout)
    assert len(items) == 1
    assert items[0]["url"] == "https://example.com/x"
