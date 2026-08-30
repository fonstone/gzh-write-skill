"""Tests for toolkit/doocs_themes.py — Doocs MD layout backend.

Verifies that the md.doocs.org official themes, once inlined into the
WeChat payload, still pass the dual-gate validator (no <style>/<div>/class=,
no leftover var(--)), and that the recognizable Doocs visual signatures
(white-on-primary centered h2 for the default theme, blockquote left border)
are actually emitted as inline styles.
"""

import re
import sys
from pathlib import Path

TOOLKIT_DIR = Path(__file__).resolve().parent.parent / "toolkit"
if str(TOOLKIT_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLKIT_DIR))

from doocs_themes import build_doocs_theme, list_doocs_themes  # noqa: E402
from converter import WeChatConverter  # noqa: E402
from validate_html import validate as validate_html  # noqa: E402

SAMPLE_MD = """# 主标题

这是正文段落，验证 Doocs 排版是否内联到微信 HTML。

## 小节标题

> 引用一句话，应该有左边框和背景色。

| 列A | 列B |
|---|---|
| 1 | 2 |

- 列表项一
- 列表项二

**加粗** 与 *斜体*。
"""


def _fragment(theme_name="default", primary="#e64340"):
    theme = build_doocs_theme(theme_name=theme_name, primary_color=primary)
    return WeChatConverter(theme=theme).convert(SAMPLE_MD).html


def test_list_doocs_themes():
    themes = list_doocs_themes()
    assert "default" in themes
    assert "grace" in themes
    assert "simple" in themes
    assert "base" not in themes  # base.css is the shared layer, not a theme


def test_all_themes_validate_clean():
    for tname in list_doocs_themes():
        html = _fragment(theme_name=tname)
        v = validate_html(html, name=f"doocs-{tname}", formula_mode="latex")
        assert v["errors"] == [], f"{tname} has errors: {v['errors']}"


def test_fragment_is_wechat_safe():
    html = _fragment()
    assert "<style" not in html, "fragment must not ship a <style> block"
    assert "<div" not in html, "fragment must not contain <div>"
    assert "class=" not in html, "fragment must not use class= attributes"
    # inline styles must be present (排版已逐元素内联)
    assert html.count("style=") > 10


def test_default_h2_signature():
    html = _fragment(theme_name="default")
    m = re.search(r"<h2[^>]*style='([^']*)'", html)
    assert m, "h2 should carry inline style"
    style = m.group(1)
    assert "color: #fff" in style or "color:#fff" in style, "default h2 should be white text"
    assert "background" in style, "default h2 should have a background fill"


def test_blockquote_has_border():
    # default/grace 用左边框；simple 用上/下/右边框 —— 三者都把 Doocs 引用
    # 样式内联成某种 border。这里只断言「存在边框样式」。
    for tname in list_doocs_themes():
        html = _fragment(theme_name=tname)
        m = re.search(r"<blockquote[^>]*style='([^']*)'", html)
        assert m, f"{tname}: blockquote should carry inline style"
        assert "border-" in m.group(1), f"{tname}: blockquote missing border styling"


def test_primary_color_override():
    html = _fragment(theme_name="default", primary="#123456")
    m = re.search(r"<h2[^>]*style='([^']*)'", html)
    assert m and "#123456" in m.group(1), "primary override should reach h2 background"
