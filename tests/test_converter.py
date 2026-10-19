"""Tests for toolkit/converter.py — the Markdown→WeChat HTML converter.

Focuses on the published-fragment compatibility guarantees that the
dual-gate validator (validate_html) enforces: no <div>, no class=.
"""

import re
import sys
from pathlib import Path

TOOLKIT_DIR = Path(__file__).resolve().parent.parent / "toolkit"
if str(TOOLKIT_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLKIT_DIR))

from converter import WeChatConverter  # noqa: E402
from theme import load_theme  # noqa: E402


def _convert(md: str, tech: bool = False) -> str:
    conv = WeChatConverter(theme=load_theme("tech-pro"), tech_enhance=tech)
    return conv.convert(md).html


def test_code_block_has_no_div_and_no_class():
    """codehilite emits <div class="codehilite">; the fragment must instead
    use <section> with no class= (WeChat rewrites/strips both)."""
    html = _convert("```yaml\nscheduler:\n  policy: \"x\"\n```\n", tech=True)
    assert "<div" not in html
    assert "class=" not in html
    assert "<section" in html


def test_strip_unsupported_removes_div_and_class_everywhere():
    conv = WeChatConverter(theme=load_theme("tech-pro"))
    dirty = '<div class="foo" style="color:red"><p class="bar">hi</p></div>'
    clean = conv._strip_unsupported_tags(dirty)
    assert "<div" not in clean
    assert "class=" not in clean
    assert "<section" in clean


def test_inline_formula_baseline_aligned():
    """Inline formula image (already rendered by render_formulas.py) must stay
    in the text flow with a negative vertical-align (baseline alignment).

    The converter re-normalizes formula images to the WeChat-safe style:
    WeChat ignores em on <img> and forces display:block on images in its
    editor, so the emitted style uses an absolute px height plus
    display:inline instead of em-based sizing."""
    md = (
        '成本 ![公式 f1](x.png){style="height:20px;width:auto;'
        'vertical-align:-3px;margin:0 3px 0 0;display:inline;border:0"} 结束\n'
    )
    html = _convert(md)
    assert re.search(r"display:\s*inline\b", html)
    assert re.search(r"vertical-align:\s*-", html)
    assert re.search(r"height:\s*20px", html)
    assert not re.search(r"display:\s*block", html)


def test_block_formula_centered():
    md = (
        '块级 ![公式 f1](x.png){style="display:block;margin:1.2em auto;'
        'height:1.29em;max-height:2.4em;max-width:88%;width:auto"} 公式\n'
    )
    html = _convert(md)
    assert re.search(r"display:\s*block", html)
    assert re.search(r"margin:\s*1\.2em auto", html)


def test_formula_images_have_no_border_radius():
    """Both inline and block formula images must drop the theme's cosmetic
    ``border-radius`` (which is added to every <img> for a soft card look).
    A rounded formula image looks like a sticker, not math — the crop is
    already tight, so rounded corners clip the ink on the corners.

    The theme's ``img { border-radius:8px }`` rule is what the formula
    branch must explicitly opt out of; if a future refactor drops the
    ``style_dict.pop("border-radius", None)`` call, this test fails.
    """
    inline_md = (
        '行内 ![公式 f1](x.png){style="height:1.12em;vertical-align:-0.82em;'
        'margin:0 2px;width:auto;display:inline-block"} 结束\n'
    )
    block_md = (
        '块 ![公式 f1](x.png){style="display:block;margin:1.2em auto;'
        'height:1.29em;width:auto"}\n'
    )
    inline_html = _convert(inline_md)
    block_html = _convert(block_md)
    # The formula <img> must not carry border-radius. A control: a plain
    # content <img> with no height: (e.g. a hero image) SHOULD get the
    # theme's border-radius — so we check the formula <img> specifically.
    assert re.search(
        r'<img[^>]*alt="公式 f1"[^>]*style="[^"]*"', inline_html
    )
    inline_formula_img = re.search(
        r'<img[^>]*alt="公式 f1"[^>]*>', inline_html
    ).group(0)
    assert "border-radius" not in inline_formula_img
    block_formula_img = re.search(
        r'<img[^>]*alt="公式 f1"[^>]*>', block_html
    ).group(0)
    assert "border-radius" not in block_formula_img
