"""Tests for toolkit/validate_html.py — the dual-gate output validator."""

import sys
from pathlib import Path

TOOLKIT_DIR = Path(__file__).resolve().parent.parent / "toolkit"
if str(TOOLKIT_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLKIT_DIR))

from validate_html import validate  # noqa: E402


def _clean_section_html() -> str:
    return (
        '<section style="margin:0 auto;max-width:677px;">'
        '<h1 style="font-size:20px;color:#1f2937;">标题</h1>'
        "<p style=\"font-size:16px;line-height:1.75;color:#333;\">正文内容。</p>"
        "</section>"
    )


def test_clean_html_passes():
    r = validate(_clean_section_html())
    assert r["errors"] == []
    assert r["warnings"] == []


def test_forbidden_style_tag():
    r = validate("<style>p{color:red}</style><p>正文</p>")
    assert any("<style>" in e for e in r["errors"])


def test_forbidden_div_tag():
    r = validate("<div><p>正文</p></div>")
    assert any("<div>" in e for e in r["errors"])


def test_forbidden_class_and_id():
    r = validate('<p class="foo" id="bar">正文</p>')
    assert any("class" in e for e in r["errors"])
    assert any("id" in e for e in r["errors"])


def test_forbidden_position_fixed():
    r = validate('<p style="position:fixed;top:0;">正文</p>')
    assert any("position" in e for e in r["errors"])


def test_forbidden_media_query():
    r = validate("<p>@media screen and (max-width:600px)</p>")
    assert any("@media" in e for e in r["errors"])


def test_forbidden_css_var():
    r = validate('<p style="color:var(--main-color);">正文</p>')
    assert any("CSS 变量" in e for e in r["errors"])


def test_leftover_inline_formula_is_error():
    # In image mode, raw $...$ is still an error (must render to PNG first).
    r = validate("<p>能量 $E=mc^2$ 很大</p>", formula_mode="image")
    assert any("未渲染的行内公式" in e for e in r["errors"])


def test_leftover_block_formula_is_error():
    r = validate("<p>如下：</p><p>$$a^2+b^2=c^2$$</p>", formula_mode="image")
    assert any("未渲染的块级公式" in e for e in r["errors"])


def test_raw_latex_not_flagged_in_latex_mode():
    # In latex mode, raw $...$ is the intended form — not an error.
    r = validate("<p>能量 $E=mc^2$ 与 $$\\int x\\,dx$$</p>", formula_mode="latex")
    assert not any("公式" in e for e in r["errors"])


def test_rendered_formula_image_is_not_flagged():
    html = (
        '<p>能量 <img src="formulas/f1.png" alt="公式 f1" '
        'style="height:1em;vertical-align:-0.7em"/> 很大</p>'
    )
    r = validate(html)
    assert r["errors"] == []
    assert r["stats"]["formula_images"] == 1


def test_formula_dollar_in_code_not_flagged():
    html = (
        '<pre style="white-space:pre-wrap;font-family:monospace;">'
        "cost = $amount * 2\n</pre>"
    )
    r = validate(html)
    assert not any("公式" in e for e in r["errors"])


def test_half_width_punct_after_cjk_warns():
    r = validate("<p>这是一句话,后面还有!</p>")
    assert any("半角标点" in w for w in r["warnings"])


def test_half_width_punct_in_code_block_not_warned():
    html = (
        '<pre style="white-space:pre-wrap;font-family:monospace;">'
        "print(x, y)\n</pre>"
    )
    r = validate(html)
    assert not any("半角标点" in w for w in r["warnings"])


def test_stats_reported():
    html = _clean_section_html() + "<p>更多的中文内容在此。</p>"
    r = validate(html, name="t.html")
    assert r["stats"]["name"] == "t.html"
    assert r["stats"]["cjk_chars"] > 5
    assert r["stats"]["images"] == 0


def test_ascii_quote_warns():
    r = validate("<p>他称之为\"深度学习\"的时代</p>")
    assert any("直引号" in w for w in r["warnings"])
