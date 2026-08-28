#!/usr/bin/env python3
"""公众号排版预处理 —— 参考 gzh-design-skill 的"智能处理"阶段。

本模块在 ``converter.convert()`` 之前运行，把一篇普通 Markdown 文章增强为
更适合公众号排版的版本。所有操作都是**确定性、可回放、幂等**的，只对源码
做结构性/标点层面的增强，不增删原文实质内容。

实现的智能处理项（对应 gzh-design-skill 的排版流程）：
  1. 中文全角标点  —— 中文后的半角 , ; : ! ? . 与英文直引号归一为全角
  2. 章节自动编号  —— 按 ``##`` 出现顺序分配 01/02/03…，末章结语用 ∞ 变体
  3. 目录导读      —— 取前 3 个 ``##`` 生成「本文导读」卡片（≥3 节时）
  4. 尾部签名区    —— 末尾追加作者签名 + 点赞在看转发三连（占位可替换）
  5. 英文标签      —— 据中文章节标题生成英文 eyebrow 标签（默认关闭，需主题配合）
  6. 关键词下划线  —— 自动给每段核心短语加下划线（默认关闭，建议 LLM 写作阶段做）

代码围栏（``` ``` ```）与行内代码（`` ` ``）内的内容一律跳过，不会被改动。

用法：
    from layout import layout_markdown, LayoutOptions
    new_md, report = layout_markdown(text, LayoutOptions())
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

# ── 中文 / 标点常量 ──────────────────────────────────────────────────────────
CJK = r"[\u4e00-\u9fff\u3400-\u4dbf]"
# 半角标点（中文后应改为全角）
HALF_PUNCT_MAP = {
    ",": "，",
    ";": "；",
    ":": "：",
    "!": "！",
    "?": "？",
}
CLOSING_ENDING = re.compile(r"(结语|总结|结尾|结论|收尾|summary|conclusion)", re.I)

# ── 英文标签词典（标题含关键词 → 英文 eyebrow） ──────────────────────────────
ENGLISH_LABELS = {
    "实测": "TEST", "测试": "TEST", "实验": "TEST",
    "教程": "TUTORIAL", "指南": "GUIDE", "实操": "HOW-TO", "上手": "HOW-TO",
    "总结": "SUMMARY", "结语": "SUMMARY", "结论": "CONCLUSION",
    "思考": "THOUGHTS", "观点": "OPINION", "感悟": "THOUGHTS",
    "案例": "CASE", "例子": "CASE", "复盘": "CASE",
    "原理": "PRINCIPLE", "本质": "PRINCIPLE", "为什么": "WHY",
    "对比": "VS", "区别": "VS",
    "实践": "PRACTICE", "落地": "PRACTICE",
    "方法": "METHOD", "技巧": "TIPS", "建议": "TIPS",
    "盘点": "LIST", "清单": "LIST",
    "介绍": "INTRO", "背景": "BACKGROUND", "入门": "INTRO",
    "趋势": "TREND", "展望": "OUTLOOK", "解析": "ANALYSIS", "拆解": "ANALYSIS",
}


@dataclass
class LayoutOptions:
    """开关与占位符配置（均可在 CLI / config 中覆盖）。"""

    fullwidth_punct: bool = True       # 中文全角标点归一
    section_numbering: bool = True     # 章节自动编号
    toc: bool = True                   # 目录导读卡片
    signature: bool = True             # 尾部签名区
    english_label: bool = False        # 英文 eyebrow 标签（需主题配合视觉）
    keyword_underline: bool = False    # 关键词下划线（建议写作阶段由 LLM 完成）
    author: str = "{{作者名}}"         # 签名区作者占位（用户替换）
    bio: str = "{{一句话简介，如：热衷于分享 AI 观察与干货}}"  # 签名区简介占位
    theme_name: str = ""
    mode: str = "wechat"               # wechat | tech


# ── 代码保护：把行内代码替换成占位，处理完再还原 ─────────────────────────────
_INLINE_CODE_RE = re.compile(r"`[^`\n]+`")
_FENCE_RE = re.compile(r"^(```|~~~).*$", re.M)


def _protect_code(text: str) -> tuple[str, list[str]]:
    """Replace inline-code spans with placeholders so punctuation fixes skip them."""
    store: list[str] = []

    def _stash(m: re.Match) -> str:
        store.append(m.group(0))
        return f"\x00CODE{len(store) - 1}\x00"

    protected = _INLINE_CODE_RE.sub(_stash, text)
    return protected, store


def _restore_code(text: str, store: list[str]) -> str:
    def _unstash(m: re.Match) -> str:
        idx = int(m.group(1))
        return store[idx] if idx < len(store) else m.group(0)

    return re.sub(r"\x00CODE(\d+)\x00", _unstash, text)


def _normalize_fullwidth_punct(line: str) -> str:
    """Normalize half-width punctuation after CJK to full-width.

    Operates on a single (code-free) line. Decimal points after digits and
    English text are preserved because we only trigger on a CJK predecessor.
    """
    # , ; : ! ? 紧跟中文 → 全角
    out = re.sub(f"({CJK})([{''.join(HALF_PUNCT_MAP)}])",
                 lambda m: m.group(1) + HALF_PUNCT_MAP[m.group(2)],
                 line)
    # 半角标点紧跟中文（如 "55ms,效果"）→ 全角（覆盖拉丁后缀+中文的情况）
    out = re.sub(f"([{''.join(HALF_PUNCT_MAP)}])({CJK})",
                 lambda m: HALF_PUNCT_MAP[m.group(1)] + m.group(2),
                 out)
    # 中文后的半角句号 . → 。  （数字后的 . 保留为小数点）
    out = re.sub(f"({CJK})\\.", lambda m: m.group(1) + "。", out)
    # 英文直双引号 " 在中英混排处 → 弯引号 ""（按奇偶交替开合）
    quote_positions = [m.start() for m in re.finditer(r'"', out)]
    if quote_positions:
        out_chars = list(out)
        flip = False
        for pos in quote_positions:
            prev = out[pos - 1] if pos > 0 else ""
            nxt = out[pos + 1] if pos + 1 < len(out) else ""
            if re.match(CJK, prev) or re.match(CJK, nxt):
                out_chars[pos] = "\u201c" if not flip else "\u201d"
                flip = not flip
        out = "".join(out_chars)
    return out


# ── 章节自动编号 ──────────────────────────────────────────────────────────────
def _is_h2(line: str) -> bool:
    s = line.strip()
    return bool(re.match(r"^##\s+\S", s))


def _already_numbered(title: str) -> bool:
    return bool(re.match(r"^(∞|\d{1,2})[\s.、]+", title.strip()))


def _apply_section_numbering(lines: list[str]) -> list[str]:
    """Prepend 01/02/03 to each H2 in order; ending section gets ∞."""
    h2_indices: list[int] = [i for i, ln in enumerate(lines) if _is_h2(ln)]
    if not h2_indices:
        return lines

    n = 0
    for order, i in enumerate(h2_indices):
        title = lines[i].strip()[2:].strip()
        if _already_numbered(title):
            continue  # 幂等：已编号跳过
        n += 1
        if order == len(h2_indices) - 1 and CLOSING_ENDING.search(title):
            prefix = "∞ "
        else:
            prefix = f"{n:02d} "
        lines[i] = f"## {prefix}{title}"
    return lines


# ── 英文标签 ──────────────────────────────────────────────────────────────────
def _detect_english_label(title: str) -> Optional[str]:
    for kw, label in ENGLISH_LABELS.items():
        if kw in title:
            return label
    return None


def _apply_english_labels(lines: list[str]) -> tuple[list[str], int]:
    added = 0
    for i, ln in enumerate(lines):
        if not _is_h2(ln):
            continue
        title = ln.strip()[2:].strip()
        label = _detect_english_label(title)
        if not label:
            continue
        indent = ln[: len(ln) - len(ln.lstrip())]
        lines[i] = f"{indent}*{label}*\n{ln}"
        added += 1
    return lines, added


# ── 目录导读 ──────────────────────────────────────────────────────────────────
_TOC_MARKER = "本文导读"


def _toc_exists(lines: list[str]) -> bool:
    return any(_TOC_MARKER in ln for ln in lines)


def _build_toc(lines: list[str]) -> Optional[list[str]]:
    """Return a 导读 blockquote listing the first 3 H2 titles (without numbers)."""
    titles = []
    for ln in lines:
        if _is_h2(ln):
            t = re.sub(r"^##\s+", "", ln.strip())
            t = re.sub(r"^(∞|\d{1,2})[\s.、]+", "", t)  # 去掉自动编号
            titles.append(t)
    if len(titles) < 3:
        return None
    picked = titles[:3]
    block: list[str] = ["> 📌 **本文导读**"]
    for t in picked:
        block.append(f"> - {t}")
    return block


def _insert_toc(lines: list[str]) -> list[str]:
    toc = _build_toc(lines)
    if not toc:
        return lines
    first_h2 = next((i for i, ln in enumerate(lines) if _is_h2(ln)), None)
    insert_at = first_h2 if first_h2 is not None else 0
    result = lines[:insert_at] + [""] + toc + [""] + lines[insert_at:]
    return result


# ── 尾部签名区 ────────────────────────────────────────────────────────────────
_SIGNATURE_MARKERS = ("点赞、在看、转发", "在看、转发", "我是 {{", "我是 ")


def _signature_exists(text: str) -> bool:
    return any(m in text for m in _SIGNATURE_MARKERS)


def _build_signature(opts: LayoutOptions) -> list[str]:
    author = opts.author
    bio = opts.bio
    block = [
        "---",
        "",
        f"我是 {author}，{bio}。",
        "",
        "如果你觉得今天这篇有收获，欢迎**点赞、在看、转发**三连，我们下篇见。",
        "",
    ]
    return block


# ── 关键词下划线（谨慎特性，默认关闭） ─────────────────────────────────────────
def _apply_keyword_underline(lines: list[str]) -> list[str]:
    """Conservative heuristic: underline the bolded term in each paragraph.

    Only activates on bolded phrases (``**x**`` → ``<u>x</u>``), which the
    converter turns into a real underline span. It never invents emphasis on
    plain text — that judgment is better left to the LLM writing stage.
    """
    out = []
    for ln in lines:
        if ln.strip().startswith((">", "#", "-", "*", "1.", "```", "~~~")):
            out.append(ln)
            continue
        ln = re.sub(r"\*\*(.+?)\*\*", r"<u>\1</u>", ln)
        out.append(ln)
    return out


# ── 主入口 ────────────────────────────────────────────────────────────────────
def layout_markdown(text: str, opts: Optional[LayoutOptions] = None) -> tuple[str, dict]:
    """Run the 排版 preprocessing pipeline.

    Returns ``(new_markdown, report)`` where ``report`` lists what changed.
    Idempotent: re-running on output is a no-op for numbering/TOC/signature.
    """
    opts = opts or LayoutOptions()
    report: dict = {
        "fullwidth_punct": 0,
        "section_numbering": 0,
        "toc": False,
        "signature": False,
        "english_label": 0,
        "keyword_underline": 0,
    }

    # 1) 全角标点（逐行，跳过围栏代码）
    if opts.fullwidth_punct:
        lines = text.split("\n")
        new_lines = []
        in_fence = False
        for ln in lines:
            if _FENCE_RE.match(ln.strip()):
                in_fence = not in_fence
                new_lines.append(ln)
                continue
            if in_fence:
                new_lines.append(ln)
                continue
            protected, store = _protect_code(ln)
            fixed = _normalize_fullwidth_punct(protected)
            fixed = _restore_code(fixed, store)
            if fixed != ln:
                report["fullwidth_punct"] += 1
            new_lines.append(fixed)
        text = "\n".join(new_lines)

    lines = text.split("\n")

    # 2) 章节自动编号
    if opts.section_numbering:
        before = lines[:]
        lines = _apply_section_numbering(lines)
        report["section_numbering"] = sum(
            1 for a, b in zip(before, lines) if a != b
        )

    # 3) 英文标签
    if opts.english_label:
        lines, n = _apply_english_labels(lines)
        report["english_label"] = n

    # 4) 目录导读
    if opts.toc and not _toc_exists(lines):
        before_len = len(lines)
        lines = _insert_toc(lines)
        if len(lines) > before_len:
            report["toc"] = True

    # 5) 关键词下划线
    if opts.keyword_underline:
        before = lines[:]
        lines = _apply_keyword_underline(lines)
        report["keyword_underline"] = sum(
            1 for a, b in zip(before, lines) if a != b
        )

    text = "\n".join(lines)

    # 6) 尾部签名区（最后做，避免被上面步骤影响）
    if opts.signature and not _signature_exists(text):
        text = text.rstrip() + "\n\n" + "\n".join(_build_signature(opts))
        report["signature"] = True

    return text, report


if __name__ == "__main__":
    import sys

    path = sys.argv[1] if len(sys.argv) > 1 else "-"
    src = sys.stdin.read() if path == "-" else open(path, encoding="utf-8").read()
    out, rep = layout_markdown(src)
    sys.stdout.write(out)
    sys.stderr.write(f"[layout] {rep}\n")
