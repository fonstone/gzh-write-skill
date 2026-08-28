"""Tests for toolkit/component_lint.py — the source-side first gate."""

import sys
from pathlib import Path

TOOLKIT_DIR = Path(__file__).resolve().parent.parent / "toolkit"
if str(TOOLKIT_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLKIT_DIR))

from component_lint import lint_markdown  # noqa: E402


def test_clean_markdown_passes():
    md = "# 标题\n\n## 章节\n\n这是正文，标点全角。\n"
    r = lint_markdown(md, "clean.md")
    assert r["errors"] == []


def test_unrendered_inline_formula_error():
    # In image mode, raw $...$ is still an error (must render to PNG first).
    md = "能量 $E=mc^2$ 很大。\n"
    r = lint_markdown(md, "f.md", formula_mode="image")
    assert any("未渲染的行内公式" in e["message"] for e in r["errors"])


def test_unrendered_block_formula_error():
    md = "如下：\n\n$$a^2+b^2=c^2$$\n"
    r = lint_markdown(md, "f.md", formula_mode="image")
    assert any("未渲染的块级公式" in e["message"] for e in r["errors"])


def test_raw_latex_passes_in_latex_mode():
    # In latex mode (default), raw $...$ / $$...$$ is the intended form and
    # must NOT be flagged as an error.
    md = "能量 $E=mc^2$ 很大，且 $$\\int_0^1 x\\,dx = \\frac12$$。\n"
    r = lint_markdown(md, "latex.md", formula_mode="latex")
    assert not any("公式" in e["message"] for e in r["errors"])


def test_raw_div_error():
    md = "正文。\n\n<div>不应该出现</div>\n"
    r = lint_markdown(md, "d.md")
    assert any("<div>" in e["message"] for e in r["errors"])


def test_raw_class_error():
    md = "正文 <span class=\"x\">内容</span>。\n"
    r = lint_markdown(md, "c.md")
    assert any("class=" in e["message"] for e in r["errors"])


def test_white_space_pre_error():
    md = "正文 <p style=\"white-space:pre\">x</p>。\n"
    r = lint_markdown(md, "w.md")
    assert any("white-space:pre" in e["message"] for e in r["errors"])


def test_half_punct_warning():
    md = "这是一句话,后面还有!\n"
    r = lint_markdown(md, "p.md")
    assert any("半角标点" in w["message"] for w in r["warnings"])


def test_missing_h2_warning():
    md = "# 只有标题\n\n没有章节的正文。\n"
    r = lint_markdown(md, "h.md")
    assert any("## 章节" in w["message"] for w in r["warnings"])


def test_empty_alt_warning():
    md = "![](photo.png)\n"
    r = lint_markdown(md, "a.md")
    assert any("空 alt" in w["message"] for w in r["warnings"])


def test_code_fence_skips_formula():
    md = "```\n$x = 1$  # 这是代码里的美元符号\n```\n"
    r = lint_markdown(md, "code.md")
    assert not any("公式" in e["message"] for e in r["errors"])


def test_code_fence_skips_div():
    md = "```html\n<div>code example</div>\n```\n"
    r = lint_markdown(md, "code.md")
    assert not any("<div>" in e["message"] for e in r["errors"])


def test_line_numbers_reported():
    md = "# 标题\n\n第一行。\n\n第二行有 $formula$ 未渲染。\n"
    r = lint_markdown(md, "ln.md", formula_mode="image")
    formula_err = [e for e in r["errors"] if "未渲染" in e["message"]]
    assert formula_err and formula_err[0]["line"] == 5


def test_formula_image_style_not_flagged():
    """Formula images carry ``{style="..."}`` (attr_list) whose double quotes
    must NOT be flagged as 正文英文直引号 false positives."""
    md = '成本 ![公式 f1](formulas/f1.png){style="height:1.12em;vertical-align:-0.82em"} 结束\n'
    r = lint_markdown(md, "formula.md")
    assert not any("直引号" in w["message"] for w in r["warnings"])
