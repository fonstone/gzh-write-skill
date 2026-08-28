"""Tests for toolkit/layout.py — the 排版 preprocessing stage."""

import sys
from pathlib import Path

TOOLKIT_DIR = Path(__file__).resolve().parent.parent / "toolkit"
if str(TOOLKIT_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLKIT_DIR))

from layout import LayoutOptions, layout_markdown  # noqa: E402


def test_fullwidth_punct_basic():
    md = "这是一句话,后面还有!和?以及:分号;结束."
    out, rep = layout_markdown(md, LayoutOptions(toc=False, signature=False,
                                                 section_numbering=False))
    assert "，" in out and "！" in out and "？" in out
    assert "：" in out and "；" in out and "。" in out
    assert rep["fullwidth_punct"] == 1  # one line changed


def test_fullwidth_punct_preserves_decimal_and_english():
    md = "延迟从 120ms 降到 55ms,效果明显."
    out, _ = layout_markdown(md, LayoutOptions(toc=False, signature=False,
                                               section_numbering=False))
    # 数字后的 . 保留（小数点），但中文后的 , 要变全角
    assert "120ms" in out and "55ms" in out
    assert "，效果明显" in out


def test_code_fence_punct_protected():
    md = "正文,这里.\n```\ncode, with. half-width\n```\n结尾."
    out, rep = layout_markdown(md, LayoutOptions(toc=False, signature=False,
                                                 section_numbering=False))
    # 代码块内的半角标点不变
    assert "code, with. half-width" in out
    # 代码块外的变了
    assert "正文，这里。" in out


def test_section_numbering():
    md = "# 标题\n\n## 先定位瓶颈\n\n正文。\n\n## 设计层级\n\n正文。\n\n## 总结与坑\n\n结尾。\n"
    out, rep = layout_markdown(md, LayoutOptions(toc=False, signature=False))
    assert "## 01 先定位瓶颈" in out
    assert "## 02 设计层级" in out
    assert "## ∞ 总结与坑" in out  # 结语用 ∞
    assert rep["section_numbering"] == 3


def test_section_numbering_skips_already_numbered():
    md = "## 01 已编号\n\n正文。\n\n## 02 也编号\n\n正文。\n"
    out, rep = layout_markdown(md, LayoutOptions(toc=False, signature=False))
    assert "## 01 已编号" in out
    assert "## 02 也编号" in out
    assert rep["section_numbering"] == 0  # 幂等，不再加


def test_toc_inserted_when_three_sections():
    md = "# 标题\n\n导语段落。\n\n## 一章\n\nx。\n\n## 二章\n\ny。\n\n## 三章\n\nz。\n"
    out, rep = layout_markdown(md, LayoutOptions(signature=False))
    assert "本文导读" in out
    assert rep["toc"] is True
    # 目录条目不含编号（已去除），但正文章节标题保留编号
    assert "- 一章" in out
    assert "## 01 一章" in out


def test_toc_skipped_when_fewer_than_three():
    md = "# 标题\n\n## 一章\n\nx。\n\n## 二章\n\ny。\n"
    out, rep = layout_markdown(md, LayoutOptions(signature=False))
    assert "本文导读" not in out
    assert rep["toc"] is False


def test_signature_appended():
    md = "# 标题\n\n正文。\n"
    out, rep = layout_markdown(md, LayoutOptions(toc=False, section_numbering=False))
    assert "点赞、在看、转发" in out
    assert "我是 {{作者名}}" in out
    assert rep["signature"] is True


def test_signature_not_duplicated():
    md = "# 标题\n\n正文。\n\n我是 张三，爱写技术。\n\n如果你觉得今天这篇有收获，欢迎**点赞、在看、转发**三连，我们下篇见。\n"
    out, rep = layout_markdown(md, LayoutOptions(toc=False, section_numbering=False))
    # 已存在签名区 → 不重复追加
    assert rep["signature"] is False
    assert out.count("点赞、在看、转发") == 1


def test_english_label_added():
    md = "# 标题\n\n## 实操教程\n\n正文。\n"
    out, rep = layout_markdown(md, LayoutOptions(toc=False, signature=False,
                                                 section_numbering=False,
                                                 english_label=True))
    assert "*TUTORIAL*" in out
    assert rep["english_label"] == 1


def test_keyword_underline_from_bold():
    md = "# 标题\n\n这是**核心观点**需要强调。\n"
    out, rep = layout_markdown(md, LayoutOptions(toc=False, signature=False,
                                                 section_numbering=False,
                                                 keyword_underline=True))
    assert "<u>核心观点</u>" in out
    assert rep["keyword_underline"] == 1


def test_idempotent_full_run():
    md = "# 标题\n\n导语。\n\n## 一章\n\n正文,有半角。\n\n## 二章\n\n更多。\n\n## 三章\n\n结尾。\n"
    opts = LayoutOptions()
    once, _ = layout_markdown(md, opts)
    twice, _ = layout_markdown(once, opts)
    assert once == twice


def test_layout_does_not_alter_code_blocks():
    md = "```python\nx = 1 + 2  # comment, no change.\n```\n"
    out, _ = layout_markdown(md, LayoutOptions())
    assert "x = 1 + 2  # comment, no change." in out
