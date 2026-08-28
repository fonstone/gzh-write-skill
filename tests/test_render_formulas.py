"""Tests for render_formulas.py."""

import re

import pytest

from render_formulas import find_formulas, render_formula, render_formulas_in_markdown


def test_find_formulas():
    text = "行内 $E=mc^2$ 与块级 $$\\frac{a}{b}$$ 公式"
    found = find_formulas(text)
    assert len(found) == 2
    assert found[0][2] == "E=mc^2"
    assert found[1][2] == "\\frac{a}{b}"


def test_find_formulas_block_flag():
    text = "行内 $E=mc^2$ 与块级 $$\\frac{a}{b}$$ 公式"
    found = find_formulas(text)
    assert found[0][3] is False  # inline $...$
    assert found[1][3] is True   # block $$...$$


def test_render_valid_formula(tmp_path):
    out = tmp_path / "f.png"
    render_formula("E=mc^2", out)
    assert out.exists()
    assert out.stat().st_size > 0


def test_render_invalid_formula_raises(tmp_path):
    with pytest.raises(ValueError):
        render_formula("\\unknowncommand{x}", tmp_path / "bad.png")


def test_render_formula_returns_em_metrics(tmp_path):
    m = render_formula("E=mc^2", tmp_path / "f.png")
    # Em metrics are what the CSS style is built from; all must be positive
    # and the height must exceed the ascent (descent adds to total height).
    assert m["height_em"] > 0
    assert m["ascent_em"] > 0
    assert m["descent_em"] > 0
    assert m["height_em"] > m["ascent_em"]
    # A plain single-line formula should be roughly text-height, not screen-height.
    assert m["height_em"] < 2.0


def test_render_inline_formula_gets_baseline_em_style(tmp_path):
    md = tmp_path / "article.md"
    md.write_text("成本 $E=mc^2$ 结束\n", encoding="utf-8")
    out_dir = tmp_path / "formulas"

    result = render_formulas_in_markdown(md, out_dir)

    assert not result["errors"]
    new_text = md.read_text(encoding="utf-8")
    # Inline: em-scaled height, ``vertical-align: -descent_em`` (the true
    # distance from the cropped image's bottom to the formula baseline —
    # this is what drops the image until the formula baseline lands on the
    # text baseline), small horizontal margin, inline flow. No max-height
    # cap (the alpha-bbox crop already guarantees nothing is clipped, and
    # a cap would squish tall fractions like \frac{...}{...}).
    assert re.search(
        r'!\[公式 f1\]\(formulas/f1\.png\)\{style="height:[\d.]+em;'
        r'vertical-align:-[\d.]+em;margin:0 \.12em;width:auto;'
        r'display:inline-block"\}',
        new_text,
    ), new_text


def test_render_block_formula_gets_block_style(tmp_path):
    md = tmp_path / "article.md"
    md.write_text("块级 $$\\frac{a}{b}$$ 公式\n", encoding="utf-8")
    out_dir = tmp_path / "formulas"

    result = render_formulas_in_markdown(md, out_dir)

    assert not result["errors"]
    new_text = md.read_text(encoding="utf-8")
    # Block: centered, em height, aspect-preserving caps (3em height /
    # 92% width so a single tall display equation never eats the whole
    # screen on mobile while still keeping the equation legible).
    assert re.search(
        r'!\[公式 f1\]\(formulas/f1\.png\)\{style="display:block;margin:1\.2em auto;'
        r'height:[\d.]+em;max-height:3em;max-width:92%;width:auto"\}',
        new_text,
    ), new_text


def test_inline_style_matches_render_metrics(tmp_path):
    """The em values in the style must match the metrics returned by render.

    Inline formulas use ``vertical-align: -descent_em`` (NOT ``-ascent_em``).
    The image's bottom edge sits on the text baseline by default; the
    formula baseline is ``descent_em`` above that bottom. Lowering the
    image by exactly ``descent_em`` places the formula baseline on the
    text baseline — proper typographic alignment. Using ``-ascent_em``
    instead would float the formula up by the cap-height, which is the
    "公式显示不自然" bug the alpha-bbox + descent fix addresses.
    """
    md = tmp_path / "article.md"
    md.write_text("成本 $E=mc^2$ 结束\n", encoding="utf-8")
    out_dir = tmp_path / "formulas"

    result = render_formulas_in_markdown(md, out_dir)

    assert not result["errors"]
    m = result["metrics"][1]
    new_text = md.read_text(encoding="utf-8")
    assert f"height:{round(m['height_em'], 2):g}em" in new_text
    assert f"vertical-align:-{round(m['descent_em'], 2):g}em" in new_text
    # height_em must equal ascent_em + descent_em (the alpha-bbox crop
    # gives a true ink extent, so ascent+descent reconstructs the full
    # image height with no clipping).
    assert abs(m["height_em"] - (m["ascent_em"] + m["descent_em"])) < 0.02


def test_render_formulas_in_markdown(tmp_path):
    md = tmp_path / "article.md"
    md.write_text("成本 $E=mc^2$，块级 $$\\sum_{i=1}^{n} i$$ 结束\n", encoding="utf-8")
    out_dir = tmp_path / "formulas"

    result = render_formulas_in_markdown(md, out_dir)

    assert not result["errors"]
    assert len(result["rendered"]) == 2
    new_text = md.read_text(encoding="utf-8")
    assert "![公式 f1](" in new_text
    assert "![公式 f2](" in new_text
    assert (out_dir / "f1.png").exists()
    assert (out_dir / "f2.png").exists()


def test_render_multiline_block_formula(tmp_path):
    md = tmp_path / "article.md"
    md.write_text("块级：\n$$\n\\sum_{i=1}^{n} (x_i - \\mu)^2\n$$\n", encoding="utf-8")
    out_dir = tmp_path / "formulas"

    result = render_formulas_in_markdown(md, out_dir)

    assert not result["errors"]
    assert len(result["rendered"]) == 1
    new_text = md.read_text(encoding="utf-8")
    assert "![公式 f1](" in new_text
    assert (out_dir / "f1.png").exists()


def test_idempotent(tmp_path):
    md = tmp_path / "article.md"
    md.write_text("成本 $E=mc^2$\n", encoding="utf-8")
    out_dir = tmp_path / "formulas"

    render_formulas_in_markdown(md, out_dir)
    result = render_formulas_in_markdown(md, out_dir)

    assert len(result["rendered"]) == 0
    assert md.read_text(encoding="utf-8").count("![公式") == 1


def test_error_reports_line(tmp_path):
    md = tmp_path / "article.md"
    md.write_text("第一行\n第二行有 $\\frac{1}{2}$\n第三行有 $\\badcommand$\n", encoding="utf-8")

    result = render_formulas_in_markdown(md, tmp_path / "formulas")

    assert len(result["errors"]) == 1
    assert result["errors"][0]["line"] == 3
    assert "\\badcommand" in result["errors"][0]["formula"]


def test_short_aliases_le_ge_render(tmp_path):
    """``\\le``/``\\ge`` are auto-normalized to ``\\leq``/``\\geq`` (the forms the
    mathtext *renderer* path recognizes) so authors may write either."""
    out = tmp_path / "f.png"
    # Should not raise ParseFatalException
    render_formula("x \\le y \\le z \\ge w", out, color="#1f2937")
    assert out.exists() and out.stat().st_size > 0

    # Full block formula mixing a short alias must also render without error.
    md = tmp_path / "a.md"
    md.write_text("$$\\min \\sum_i w_i \\cdot T_i \\quad \\text{s.t.} \\quad \\sum_j r_{ij} \\le C_j$$\n",
                  encoding="utf-8")
    result = render_formulas_in_markdown(md, tmp_path / "formulas")
    assert not result["errors"]
    assert "![公式 f1](" in md.read_text(encoding="utf-8")
