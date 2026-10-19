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


def test_render_inline_formula_gets_wechat_safe_style(tmp_path):
    md = tmp_path / "article.md"
    md.write_text("成本 $E=mc^2$ 结束\n", encoding="utf-8")
    out_dir = tmp_path / "formulas"

    result = render_formulas_in_markdown(md, out_dir)

    assert not result["errors"]
    new_text = md.read_text(encoding="utf-8")
    # Inline: WeChat ignores em on <img> and forces display:block on images
    # in its editor, so the renderer pins an absolute 20px height that
    # browsers honour (local preview / web view), while the small natural
    # PNG size (~20px tall) carries the WeChat editor fallback. The small
    # margin and vertical-align keep the formula in the text flow, on the
    # text baseline; border:0 cancels WeChat's auto border on images.
    assert re.search(
        r'!\[公式 f1\]\(formulas/f1\.png\)\{style="height:20px;'
        r'width:auto;vertical-align:-3px;margin:0 3px 0 0;'
        r'display:inline;border:0"\}',
        new_text,
    ), new_text


def test_render_block_formula_gets_block_style(tmp_path):
    md = tmp_path / "article.md"
    md.write_text("块级 $$\\frac{a}{b}$$ 公式\n", encoding="utf-8")
    out_dir = tmp_path / "formulas"

    result = render_formulas_in_markdown(md, out_dir)

    assert not result["errors"]
    new_text = md.read_text(encoding="utf-8")
    # Block: display:block + auto margins center the equation. No em height
    # pinning (WeChat ignores it; the PNG is rendered at a sensible target
    # size). max-width caps a pathologically wide equation; border:0
    # cancels WeChat's auto border on images.
    assert re.search(
        r'!\[公式 f1\]\(formulas/f1\.png\)\{style="display:block;'
        r'margin:1\.2em auto;max-width:96%;width:auto;height:auto;border:0"\}',
        new_text,
    ), new_text


def test_inline_style_uses_px_workaround_and_metrics_consistent(tmp_path):
    """Metrics describe the glyph box; the emitted style deliberately avoids em.

    WeChat's editor ignores ``em`` units on ``<img>`` and forces
    ``display:block`` on images, so an em-sized formula would render at the
    PNG's natural size on a line of its own, mid-sentence. The style
    therefore uses an absolute px height (for browsers) and the renderer
    keeps the PNG itself small (for the WeChat editor fallback). The
    metrics stay internally consistent: the alpha-bbox crop guarantees
    ascent + descent reconstructs the image height with no clipping.
    """
    md = tmp_path / "article.md"
    md.write_text("成本 $E=mc^2$ 结束\n", encoding="utf-8")
    out_dir = tmp_path / "formulas"

    result = render_formulas_in_markdown(md, out_dir)

    assert not result["errors"]
    m = result["metrics"][1]
    new_text = md.read_text(encoding="utf-8")
    # Metrics integrity: all positive, height == ascent + descent.
    assert m["height_em"] > 0
    assert m["ascent_em"] > 0
    assert m["descent_em"] > 0
    assert abs(m["height_em"] - (m["ascent_em"] + m["descent_em"])) < 0.02
    # The emitted style must not rely on em units on <img>.
    style = re.search(r'\{style="([^"]+)"\}', new_text).group(1)
    assert "em" not in style
    assert "height:20px" in style


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
