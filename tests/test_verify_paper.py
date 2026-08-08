"""Tests for verify_paper.py."""

import json

from fetch_paper import build_package
from verify_paper import verify_paper


def _build_assets(sample_pdf, tmp_path):
    out = tmp_path / "assets"
    build_package(str(sample_pdf), out)
    return out


def test_verify_clean_article(sample_pdf, sample_article, tmp_path):
    out = _build_assets(sample_pdf, tmp_path)
    report = verify_paper(sample_article, out)

    assert all(f["status"] == "verified" for f in report["figures"])
    assert all(s["status"] == "verified" for s in report["sections"])
    assert report["metadata"]["status"] == "verified"
    assert all(a["status"] == "verified" for a in report["data_anchors"])


def test_verify_missing_figure(sample_pdf, tmp_path):
    out = _build_assets(sample_pdf, tmp_path)
    article = tmp_path / "a.md"
    article.write_text(
        "如图 9 所示。原文见 https://arxiv.org/abs/2405.00001\n", encoding="utf-8"
    )
    report = verify_paper(article, out)
    assert any(f["status"] == "not_found" for f in report["figures"])


def test_verify_missing_data_anchor(sample_pdf, tmp_path):
    out = _build_assets(sample_pdf, tmp_path)
    article = tmp_path / "a.md"
    article.write_text(
        "延迟降低到 123.4 ms（图 1）。原文见 https://arxiv.org/abs/2405.00001\n",
        encoding="utf-8",
    )
    report = verify_paper(article, out)
    assert any(a["status"] == "needs_human_check" for a in report["data_anchors"])


def test_verify_missing_metadata(sample_pdf, tmp_path):
    out = _build_assets(sample_pdf, tmp_path)
    article = tmp_path / "a.md"
    article.write_text("如图 1 所示，架构是草稿-验证。\n", encoding="utf-8")
    report = verify_paper(article, out)
    assert report["metadata"]["status"] == "not_found"


def test_verify_json_output(sample_pdf, sample_article, tmp_path, capsys):
    out = _build_assets(sample_pdf, tmp_path)
    import sys

    from verify_paper import main as verify_main

    sys.argv = ["verify_paper.py", str(sample_article), "--assets", str(out), "--json"]
    verify_main()
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert "figures" in data and "metadata" in data
