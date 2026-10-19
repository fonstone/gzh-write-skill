"""Tests for claims_audit.py — cross-check draft claims against sources."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import claims_audit  # noqa: E402


def _write(tmp_path, article_text, sources=None, paper_texts=None):
    md = tmp_path / "article.md"
    md.write_text(article_text, encoding="utf-8")
    if sources is not None:
        import yaml
        md.with_suffix(".sources.yaml").write_text(
            yaml.safe_dump({"sources": sources}, allow_unicode=True),
            encoding="utf-8",
        )
    if paper_texts:
        text_dir = tmp_path / "paper-assets" / "text"
        text_dir.mkdir(parents=True)
        for i, t in enumerate(paper_texts):
            (text_dir / f"0{i}.txt").write_text(t, encoding="utf-8")
    return md


def _by_text(report):
    return {c["text"]: c for c in report["claims"]}


def test_extract_number_claims_with_lines(tmp_path):
    md = _write(tmp_path, "第一行\n延迟 12.4 ms，提升 21 倍\n")
    claims = claims_audit.extract_claims(md.read_text(encoding="utf-8"))
    texts = [c["text"] for c in claims if c["type"] == "number"]
    assert "12.4 ms" in texts
    assert "21 倍" in texts
    line2 = [c for c in claims if c["line"] == 2]
    assert line2


def test_extract_quotes(tmp_path):
    md = _write(tmp_path, "专家说：「缓存一致性是分布式系统里最难的部分」\n")
    claims = claims_audit.extract_claims(md.read_text(encoding="utf-8"))
    quotes = [c for c in claims if c["type"] == "quote"]
    assert quotes and "缓存一致性是分布式系统里最难的部分" in quotes[0]["text"]


def test_code_blocks_and_formulas_skipped(tmp_path):
    md = _write(
        tmp_path,
        "正文 12 ms。\n```python\nx = 999999 ms\n```\n行内 `777 ms` 和公式 $E=88.8$ 以及块级 $$\n66.6 \text{ ms}\n$$\n",
    )
    claims = claims_audit.extract_claims(md.read_text(encoding="utf-8"))
    texts = [c["text"] for c in claims]
    assert "12 ms" in texts
    assert not any("999999" in t for t in texts)
    assert not any("777" in t for t in texts)
    assert not any("88.8" in t for t in texts)
    assert not any("66.6" in t for t in texts)


def test_audit_statuses_supported_weak_unsupported(tmp_path):
    sources = [
        {"id": "src1", "url": "https://example.com/a", "title": "T", "date": "",
         "verified": True, "note": "",
         "excerpt": "延迟从 12.4 ms 降到 9.8 ms；响应控制在 300 以内"},
        {"id": "src2", "url": "https://example.com/b", "title": "T2", "date": "",
         "verified": True, "note": "",
         "excerpt": "专家表示：「缓存一致性是分布式系统里最难的部分」"},
    ]
    md = _write(
        tmp_path,
        "延迟从 12.4 ms 降到 9.8 ms。\n"
        "响应 300 ms 内完成。\n"
        "吞吐提升 21 倍。\n"
        "专家说：「缓存一致性是分布式系统里最难的部分」\n",
        sources=sources,
    )
    report = claims_audit.audit(md)
    by_text = _by_text(report)
    assert by_text["12.4 ms"]["status"] == "supported"
    assert by_text["9.8 ms"]["status"] == "supported"
    assert by_text["300 ms"]["status"] == "weak"       # number seen, unit absent
    assert by_text["21 倍"]["status"] == "unsupported"
    quote = next(c for c in report["claims"] if c["type"] == "quote")
    assert quote["status"] == "supported"
    assert report["summary"]["total"] == len(report["claims"])


def test_unit_alias_and_fullwidth_normalization(tmp_path):
    sources = [
        {"id": "src1", "url": "https://example.com/a", "title": "", "date": "",
         "verified": True, "note": "", "excerpt": "耗时 5 ms，占用 3 GB 显存"},
    ]
    md = _write(tmp_path, "耗时 5 毫秒，占用 ３ ＧＢ 显存。\n", sources=sources)
    report = claims_audit.audit(md)
    statuses = {c["text"]: c["status"] for c in report["claims"]}
    # "5 毫秒" aliases to 5ms; fullwidth "３ ＧＢ" normalizes to 3GB.
    assert any(s == "supported" for s in statuses.values())
    assert not any(s == "unsupported" for s in statuses.values())


def test_paper_assets_extend_evidence(tmp_path):
    sources = [
        {"id": "src1", "url": "https://example.com/a", "title": "", "date": "",
         "verified": False, "note": "", "excerpt": ""},
    ]
    md = _write(tmp_path, "论文报告 FID 4.62，超过基线。\n", sources=sources,
                paper_texts=["Our method achieves FID 4.62 on CIFAR-10."])
    without = claims_audit.audit(md)
    with_paper = claims_audit.audit(md, paper_assets=tmp_path / "paper-assets")
    assert next(c for c in without["claims"] if c["text"] == "4.62")["status"] == "unsupported"
    assert next(c for c in with_paper["claims"] if c["text"] == "4.62")["status"] == "supported"


def test_bare_decimal_adjacent_to_cjk_is_extracted(tmp_path):
    """Chinese prose rarely puts a space before a number; the boundary
    guards must use ASCII classes so CJK neighbours do not hide claims."""
    md = _write(tmp_path, "模型在 FID为4.62的成绩上领先。\n")
    claims = claims_audit.extract_claims(md.read_text(encoding="utf-8"))
    texts = [c["text"] for c in claims]
    assert "4.62" in texts, texts


def test_malformed_sources_file_errors_readably(tmp_path):
    md = _write(tmp_path, "一篇文章。\n")
    md.with_suffix(".sources.yaml").write_text("- just a list\n", encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "claims_audit.py"), str(md)],
        capture_output=True, text=True, encoding="utf-8",
        env={**__import__("os").environ, "PYTHONIOENCODING": "utf-8"},
    )
    assert proc.returncode == 1
    assert "Traceback" not in (proc.stderr or "")


def test_missing_ledger_prints_hint(tmp_path):
    import os
    md = _write(tmp_path, "吞吐提升 21 倍。\n")   # no sources file at all
    proc = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "claims_audit.py"), str(md)],
        capture_output=True, text=True, encoding="utf-8",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    assert proc.returncode == 0
    assert "台账" in (proc.stderr or "")


def test_cli_strict_exit_codes(tmp_path):
    md = _write(tmp_path, "吞吐提升 21 倍。\n")
    base_cmd = [sys.executable, str(REPO_ROOT / "scripts" / "claims_audit.py"), str(md), "--json"]
    proc = subprocess.run(base_cmd, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    data = json.loads(proc.stdout)
    assert data["summary"]["unsupported"] >= 1

    proc = subprocess.run(base_cmd + ["--strict"], capture_output=True, text=True)
    assert proc.returncode == 1
