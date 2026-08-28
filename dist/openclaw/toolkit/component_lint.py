#!/usr/bin/env python3
"""源侧 lint —— 双门校验的第一道关（参考 gzh-design-skill 的 component_lint）。

``validate_html.py`` 校验**最终 HTML 产物**（第二道门）；本脚本校验**源 Markdown
文章**，在转换/排版之前就抓出问题，并给出源文件行号，省得等到粘贴后才发现。

与 gzh-design-skill 的区别：那边 lint 的是 references/ 组件库 .md；本工程没有
组件库概念（主题用 YAML + converter 生成），所以这里 lint 的是**待排版的
Markdown 源文件**——检查作者手写的原始内容里是否夹带了平台会剥离/失效的标记。

**ERROR（必须修）**
- 未渲染的 ``$...$`` / ``$$...$$`` 公式（image 模式下忘了跑 render_formulas.py；
  latex 模式下保留原始 LaTeX 由下游渲染器显示，不算错误）
- 源 Markdown 里手写 ``<div>`` / ``class=`` / ``id=`` / ``<style>`` /
  ``position:fixed|absolute|sticky`` / ``@media`` / ``display:grid`` / ``var(--x)``
  （这些粘贴到公众号会被剥离，纯属无效写法）
- ``white-space:pre``（会把源码缩进渲染成大左缩进+空行）

**WARNING（建议修）**
- 中文后的半角标点 , ; : ! ? .
- 正文英文直引号 " '
- 文章缺少 H2 章节结构（整篇没有 ##）
- 图片 ``![]()`` 空 alt（公众号会显示破图标，应补说明）

代码围栏（``` ``` ```）与行内代码（`` ` ``）内的内容一律跳过。

用法：
    python3 component_lint.py article.md
    python3 component_lint.py article.md --json
退出码：1 = 有 ERROR，0 = 通过。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from typing import Optional

# ── ERROR 级：源 Markdown 里夹带的平台失效标记 ───────────────────────────────
# 未渲染公式：仅 image 模式视为错误（忘了跑 render_formulas.py）。在 latex
# 模式下，原始 $...$ / $$...$$ 是「刻意保留、由下游 MathJax/KaTeX 渲染器显示」
# 的合法形式，不应报错。
RX_INLINE_FORMULA = re.compile(r"(?<![\\$])\$(?!\$)([^$\n]+?)\$(?!\$)")
RX_BLOCK_FORMULA = re.compile(r"\$\$([^$]+?)\$\$")
# image 模式下才把这两个模式算作 forbidden
_FORMULA_RX = (RX_INLINE_FORMULA, RX_BLOCK_FORMULA)

FORBIDDEN: list[tuple[re.Pattern, str]] = [
    (RX_INLINE_FORMULA,
     "未渲染的行内公式 $...$（请先运行 render_formulas.py，或把 config 的 formula_mode 设为 latex）"),
    (RX_BLOCK_FORMULA,
     "未渲染的块级公式 $$...$$（请先运行 render_formulas.py，或把 config 的 formula_mode 设为 latex）"),
    (re.compile(r"</?div[\s>]", re.I),
     "源文件出现 <div>（公众号会改写，请用 Markdown 语法）"),
    (re.compile(r"\sclass\s*=", re.I),
     "源文件出现 class=（会被公众号剥离，请改用 Markdown/主题）"),
    (re.compile(r"\sid\s*=", re.I),
     "源文件出现 id=（会被公众号剥离）"),
    (re.compile(r"<style[\s>]", re.I),
     "源文件出现 <style>（平台禁用，样式应走主题/内联）"),
    (re.compile(r"position\s*:\s*(fixed|absolute|sticky)", re.I),
     "position: fixed|absolute|sticky 不被支持"),
    (re.compile(r"display\s*:\s*grid", re.I),
     "display:grid 不被支持"),
    (re.compile(r"var\s*\(\s*--", re.I),
     "CSS 变量 var(--x) 不被支持"),
    (re.compile(r"@(media|keyframes|import)", re.I),
     "@media/@keyframes/@import 不被支持"),
    (re.compile(r"white-space\s*:\s*pre", re.I),
     "white-space:pre 会把源码缩进渲染成大左缩进+空行，勿用手写"),
]

# ── WARNING 级 ────────────────────────────────────────────────────────────────
CJK = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf]")
HALF_PUNCT = re.compile(r"[\u4e00-\u9fff][,;:!?]")
ASCII_DOUBLE = re.compile(r'"')
ASCII_SINGLE = re.compile(r"'")
FENCE_RE = re.compile(r"^(```|~~~)")


def _strip_code(text: str) -> str:
    """Remove fenced code blocks (keep line count for accurate line numbers)."""
    lines = text.split("\n")
    out = []
    in_fence = False
    for ln in lines:
        if FENCE_RE.match(ln.strip()):
            in_fence = not in_fence
            out.append("")  # 占位维持行号
            continue
        out.append("" if in_fence else ln)
    return "\n".join(out)


def _strip_inline_code(text: str) -> str:
    return re.sub(r"`[^`\n]+`", "", text)


def _strip_markup(text: str) -> str:
    """Strip Markdown markup that legitimately contains ASCII quotes/brackets.

    Formula images carry an ``attr_list`` style attribute — ``![公式 fN](p)
    {style="height:1.12em; ..."}`` — whose double quotes must NOT be flagged
    as "正文英文直引号". Drop attr_list ``{...}``, images, links and inline
    code before the prose-level punctuation/quote checks.
    """
    text = re.sub(r"\{[^}]*\}", "", text)            # attr_list {style="..."}
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)  # images
    text = re.sub(r"\[[^\]]*\]\([^)]*\)", "", text)   # links
    text = re.sub(r"`[^`\n]+`", "", text)             # inline code
    return text


def lint_markdown(text: str, name: str = "<input>", formula_mode: str = "latex") -> dict:
    """Lint raw Markdown source. Returns structured result.

    ``formula_mode``:
      - ``"latex"`` (default): raw ``$...$`` / ``$$...$$`` is the intended
        form (rendered by a downstream MathJax/KaTeX renderer), so it is NOT
        flagged as an error.
      - ``"image"``: unrendered formulas are errors (must run
        render_formulas.py to convert them to PNG images first).
    """
    errors: list[dict] = []
    warnings: list[dict] = []

    # In latex mode, drop the two formula patterns from the forbidden set —
    # raw $...$ is intentional, not a "forgot to render" mistake.
    if formula_mode == "latex":
        forbidden = [(rx, msg) for (rx, msg) in FORBIDDEN if rx not in _FORMULA_RX]
    else:
        forbidden = FORBIDDEN

    code_free = _strip_code(text)
    lines = code_free.split("\n")

    # ERROR：逐行扫描 forbidden 模式（已剔除代码块/标记）
    for rx, msg in forbidden:
        for i, ln in enumerate(lines, 1):
            # 行内代码/公式图片标记也剔除，避免误报
            clean = _strip_markup(ln)
            if rx.search(clean):
                errors.append({"line": i, "message": msg, "sample": ln.strip()[:60]})

    # WARNING：半角标点 / 直引号（代码块外，且排除行内代码与公式标记）
    for i, ln in enumerate(lines, 1):
        clean = _strip_markup(ln)
        if CJK.search(clean):
            if HALF_PUNCT.search(clean):
                warnings.append({"line": i, "message": "中文后半角标点（应改全角 , ; : ! ? 。）",
                                  "sample": ln.strip()[:60]})
            if ASCII_DOUBLE.search(clean) or ASCII_SINGLE.search(clean):
                warnings.append({"line": i, "message": "正文英文直引号 \" '（应改中文弯引号 ""''）",
                                  "sample": ln.strip()[:60]})

    # WARNING：缺少 H2 结构
    h2_count = sum(1 for ln in lines if re.match(r"^\s*##\s+\S", ln))
    if h2_count == 0:
        warnings.append({"line": 0, "message": "文章没有任何 ## 章节标题（公众号长文建议分章节）",
                         "sample": ""})

    # WARNING：空 alt 图片
    for i, ln in enumerate(lines, 1):
        clean = _strip_inline_code(ln)
        for m in re.finditer(r"!\[\s*\]\(([^)]+)\)", clean):
            warnings.append({"line": i, "message": f"图片空 alt（应补说明文字）: {m.group(1)[:40]}",
                             "sample": ln.strip()[:60]})

    return {
        "name": name,
        "errors": errors,
        "warnings": warnings,
        "stats": {"h2_sections": h2_count, "lines": len(lines)},
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[3])
    ap.add_argument("file", help="Markdown 源文件路径")
    ap.add_argument("--json", action="store_true", help="输出 JSON 而非文本")
    ap.add_argument("--formula-mode", choices=("latex", "image"), default="latex",
                    help="公式承载方式：latex=保留原始 $...$（默认），image=需预渲染为图片")
    args = ap.parse_args()

    try:
        with open(args.file, encoding="utf-8", errors="replace") as f:
            text = f.read()
    except OSError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2

    result = lint_markdown(text, name=args.file, formula_mode=args.formula_mode)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1 if result["errors"] else 0

    s = result["stats"]
    print(f"📐 源侧排版检查 — {s['name'] if False else result['name']}")
    print(f"   {s['lines']} 行 · {s['h2_sections']} 个 ## 章节")
    if result["errors"]:
        print(f"\n❌ ERROR ×{len(result['errors'])}（必须修复）:")
        for e in result["errors"]:
            loc = f"L{e['line']}" if e["line"] else "—"
            print(f"   • [{loc}] {e['message']}")
            if e["sample"]:
                print(f"        ↳ {e['sample']}")
    if result["warnings"]:
        print(f"\n⚠️  WARNING ×{len(result['warnings'])}（建议检查）:")
        for w in result["warnings"][:15]:
            loc = f"L{w['line']}" if w["line"] else "—"
            print(f"   • [{loc}] {w['message']}")
        if len(result["warnings"]) > 15:
            print(f"   … 其余 {len(result['warnings']) - 15} 条略")
    if not result["errors"] and not result["warnings"]:
        print("\n✅ 源文件排版就绪")
    elif not result["errors"]:
        print("\n✅ 无致命问题（warning 请人工确认）")
    return 1 if result["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
