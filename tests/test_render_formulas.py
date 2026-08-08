"""Tests for render_formulas.py."""

import pytest

from render_formulas import find_formulas, render_formula, render_formulas_in_markdown


def test_find_formulas():
    text = "行内 $E=mc^2$ 与块级 $$\\frac{a}{b}$$ 公式"
    found = find_formulas(text)
    assert len(found) == 2
    assert found[0][2] == "E=mc^2"
    assert found[1][2] == "\\frac{a}{b}"


def test_render_valid_formula(tmp_path):
    out = tmp_path / "f.png"
    render_formula("E=mc^2", out)
    assert out.exists()
    assert out.stat().st_size > 0


def test_render_invalid_formula_raises(tmp_path):
    with pytest.raises(ValueError):
        render_formula("\\unknowncommand{x}", tmp_path / "bad.png")


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
