"""Tests for `toolkit/cli.py check` — the unified QA command."""

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CLI = REPO_ROOT / "toolkit" / "cli.py"
CLEAN_MD = "# 标题\n\n这是一段干净的正文，没有违规内容。\n"


def _run(*args):
    return subprocess.run(
        [sys.executable, str(CLI), "check", *map(str, args)],
        capture_output=True, text=True,
    )


def test_clean_article_exits_zero(tmp_path):
    md = tmp_path / "clean.md"
    md.write_text(CLEAN_MD, encoding="utf-8")
    proc = _run(md)
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_violating_article_exits_one():
    fixture = REPO_ROOT / "evals" / "fixtures" / "human-prose-violations.md"
    proc = _run(fixture)
    assert proc.returncode == 1, proc.stdout + proc.stderr


def test_tech_fixture_exits_one_with_tech_flag():
    fixture = REPO_ROOT / "evals" / "fixtures" / "tech-prose-violations.md"
    proc = _run(fixture, "--tech", "--mode", "tech")
    assert proc.returncode == 1, proc.stdout + proc.stderr


def test_json_report_shape(tmp_path):
    md = tmp_path / "clean.md"
    md.write_text(CLEAN_MD, encoding="utf-8")
    proc = _run(md, "--json")
    assert proc.returncode == 0, proc.stderr
    data = json.loads(proc.stdout)
    assert data["verdict"] == "pass"
    sections = data["sections"]
    for key in ("component_lint", "prose", "l1", "html", "humanness"):
        assert key in sections
    assert sections["html"] is None       # no --html given
    assert sections["l1"]["passed"] is True


def test_prose_report_decodes_as_utf8():
    """Regression: child scripts ran with the console's GBK encoding while
    the parent decoded as UTF-8, so the prose report came back empty on
    Windows. The report must survive the round trip."""
    fixture = REPO_ROOT / "evals" / "fixtures" / "human-prose-violations.md"
    proc = _run(fixture, "--json")
    assert proc.returncode == 1
    data = json.loads(proc.stdout)
    report = data["sections"]["prose"]["report"]
    assert report, "prose report must not be empty"
    assert any("\u4e00" <= ch <= "\u9fff" for ch in report), report


def test_check_respects_formula_mode(tmp_path):
    md = tmp_path / "formula.md"
    md.write_text("# 标题\n\n公式 $E=mc^2$ 留在正文。\n", encoding="utf-8")
    ok = _run(md)                                  # default latex: raw $..$ is expected
    assert ok.returncode == 0, ok.stdout + ok.stderr
    bad = _run(md, "--formula-mode", "image")      # image mode: unrendered formula is an ERROR
    assert bad.returncode == 1, bad.stdout + bad.stderr


def test_html_error_fails_verdict(tmp_path):
    md = tmp_path / "clean.md"
    md.write_text(CLEAN_MD, encoding="utf-8")
    html = tmp_path / "bad.html"
    html.write_text('<div class="x">违规</div>', encoding="utf-8")
    proc = _run(md, "--html", html, "--json")
    assert proc.returncode == 1
    data = json.loads(proc.stdout)
    assert data["sections"]["html"]["errors"]


def test_html_clean_passes(tmp_path):
    md = tmp_path / "clean.md"
    md.write_text(CLEAN_MD, encoding="utf-8")
    html = tmp_path / "ok.html"
    html.write_text(
        '<section><p style="color:#333333;font-size:16px">正文</p></section>',
        encoding="utf-8",
    )
    proc = _run(md, "--html", html, "--json")
    assert proc.returncode == 0, proc.stdout
    data = json.loads(proc.stdout)
    assert data["sections"]["html"]["errors"] == []
