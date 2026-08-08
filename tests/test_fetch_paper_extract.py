"""Tests for fetch_paper.py PDF extraction mode (channel A)."""

import json

from fetch_paper import build_package


def test_build_package_from_pdf(sample_pdf, tmp_path):
    out = tmp_path / "assets"
    pkg = build_package(str(sample_pdf), out)

    assert (out / "paper.json").exists()
    data = json.loads((out / "paper.json").read_text(encoding="utf-8"))
    assert data["title"] == "Speculative Decoding for Fast LLM Inference"
    assert "Alice Chen" in data["authors"][0]
    assert len(data["chapters"]) >= 2
    assert data["chapters"][0]["title"] == "Introduction"
    assert len(data["figures"]) == 2
    assert data["figures"][0]["number"] == 1
    assert data["figures"][0]["extract_failed"] is False
    assert data["figures"][0]["file"] == "images/fig1.png"
    assert (out / "images" / "fig1.png").exists()
    assert (out / "images" / "fig2.png").exists()
    assert "latency from 12.4 ms" in data["abstract"]
    assert (out / "text").is_dir()
    assert len(list((out / "text").glob("*.txt"))) >= 2


def test_build_package_tolerates_missing_image(tmp_path):
    """A PDF with a figure caption but no embedded image still builds."""
    import fitz

    doc = fitz.open()
    p1 = doc.new_page()
    p1.insert_text((72, 72), "Paper Without Images", fontsize=14)
    p1.insert_text((72, 100), "Figure 1. Placeholder caption.", fontsize=10)
    path = tmp_path / "noimg.pdf"
    doc.save(str(path))
    doc.close()

    out = tmp_path / "assets"
    pkg = build_package(str(path), out)
    data = json.loads((out / "paper.json").read_text(encoding="utf-8"))
    assert data["figures"][0]["extract_failed"] is True
    assert data["figures"][0]["file"] == ""
