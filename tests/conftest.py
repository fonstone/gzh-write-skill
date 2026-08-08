"""Shared fixtures for gzh-write script tests.

Adds scripts/ to sys.path so tests can import script modules directly.
"""

import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def _make_image(path: Path, color: tuple = (80, 120, 200), size: tuple = (160, 100)) -> None:
    from PIL import Image

    Image.new("RGB", size, color).save(path)


@pytest.fixture
def sample_pdf(tmp_path):
    """Build a 3-page test PDF: title/abstract/2 chapters/2 figure captions + images.

    All text is English because fitz.insert_text needs Latin glyphs by default.
    """
    img1 = tmp_path / "img1.png"
    img2 = tmp_path / "img2.png"
    _make_image(img1, color=(200, 60, 60))
    _make_image(img2, color=(60, 200, 60))

    import fitz

    doc = fitz.open()
    p1 = doc.new_page()
    p1.insert_text((72, 72), "Speculative Decoding for Fast LLM Inference", fontsize=18)
    p1.insert_text((72, 120), "Alice Chen, Bob Wang", fontsize=12)
    p1.insert_text((72, 160), "Abstract", fontsize=12)
    p1.insert_text((72, 180), "We propose a method that reduces latency from 12.4 ms to 9.8 ms.", fontsize=10)
    p1.insert_text((72, 240), "1. Introduction", fontsize=14)
    p1.insert_text((72, 260), "Speculative decoding drafts tokens in parallel.", fontsize=10)

    p2 = doc.new_page()
    p2.insert_text((72, 72), "2. Method", fontsize=14)
    p2.insert_text((72, 100), "Figure 1. Draft-then-verify architecture.", fontsize=10)
    p2.insert_image(fitz.Rect(72, 120, 232, 220), filename=str(img1))

    p3 = doc.new_page()
    p3.insert_text((72, 72), "3. Conclusion", fontsize=14)
    p3.insert_text((72, 100), "Figure 2. Latency comparison results.", fontsize=10)
    p3.insert_image(fitz.Rect(72, 120, 232, 220), filename=str(img2))

    path = tmp_path / "sample.pdf"
    doc.save(str(path))
    doc.close()
    return path


@pytest.fixture
def sample_article(tmp_path):
    """Article that references paper figures, sections, and data anchors."""
    path = tmp_path / "article.md"
    path.write_text(
        "## 论文精读\n\n"
        "投机解码把延迟从 12.4 ms 降到 9.8 ms（论文第 2 节，图 2）。\n"
        "如图 1 所示，架构是草稿-验证。原文见 arXiv: https://arxiv.org/abs/2405.00001\n",
        encoding="utf-8",
    )
    return path
