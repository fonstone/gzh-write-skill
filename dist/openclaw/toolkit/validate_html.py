#!/usr/bin/env python3
"""Validate WeChat-compatible HTML output of ``toolkit/cli.py``.

This is the second gate of the dual-gate quality loop adopted from
``gzh-design-skill`` (https://github.com/isjiamu/gzh-design-skill). It runs
on the final HTML to deterministically catch platform-breaking patterns that
the agent might miss in a subjective review.

The first gate is the converter's theme application (it has already run
when this script is invoked). This second gate checks:

**Errors (will fail the build)**
- Forbidden tags: ``<style>``, ``<script>``, ``<link>``, ``<div>``
- Forbidden attributes: ``class=``, ``id=``  (公众号编辑器会剥离)
- Forbidden CSS: ``position: fixed|absolute|sticky``, ``float:``,
  ``@media``, ``@keyframes``, ``@import``, ``display: grid``,
  ``var(--...)`` CSS vars, external font ``url(...woff/ttf/otf/eot)``
- Leftover unrendered formula markers: ``$...$`` / ``$$...$$`` in plain
  text (caller forgot to run render_formulas.py). **Skipped in latex mode**,
  where raw LaTeX is the intended, downstream-rendered form.

**Warnings (won't fail, but worth fixing)**
- Half-width punctuation after CJK characters (should be 全角)
- English straight quotes (``" '``) inside text
- Unclosed ``<span leaf>`` would be a third error in gzh-design-skill, but
  this project's converter does not use leaf spans (publishing goes through
  the WeChat API which preserves inline styles natively), so the leaf
  check is informational only.

Usage:
    python3 validate_html.py article.html
    python3 validate_html.py < article.html   # stdin

Exit codes:
    0 — no errors (warnings allowed)
    1 — errors found
    2 — file not found / IO error
"""

from __future__ import annotations

import argparse
import re
import sys
from html.parser import HTMLParser

# ── Error-level patterns ─────────────────────────────────────────────────────
# (regex, message); 命中即 ERROR
FORBIDDEN: list[tuple[re.Pattern, str]] = [
    (re.compile(r"<style[\s>]", re.I),     "<style> 标签会被公众号剥离 — 样式必须全部内联"),
    (re.compile(r"<script[\s>]", re.I),    "<script> 标签会被过滤"),
    (re.compile(r"<link[\s>]", re.I),      "<link> 外部资源会被过滤"),
    (re.compile(r"</?div[\s>]", re.I),     "<div> 会被改写 — 请用 <section> 代替"),
    (re.compile(r"\sclass\s*=", re.I),     "class 属性会被剥离 — 请用内联 style"),
    (re.compile(r"\sid\s*=", re.I),        "id 属性会被剥离"),
    (re.compile(r"position\s*:\s*(fixed|absolute|sticky)", re.I),
     "position: fixed|absolute|sticky 不被支持"),
    (re.compile(r"float\s*:", re.I),       "float 不被支持 — 请用 flex/inline-block"),
    (re.compile(r"@media", re.I),          "@media 媒体查询不被支持"),
    (re.compile(r"@keyframes", re.I),      "@keyframes 动画不被支持"),
    (re.compile(r"@import", re.I),         "@import 不被支持"),
    (re.compile(r"display\s*:\s*grid", re.I), "display: grid 不被支持 — 请用 flex"),
    (re.compile(r"var\s*\(\s*--", re.I),   "CSS 变量 var(--x) 不被支持 — 请写死值"),
    (re.compile(r"url\s*\(\s*['\"]?https?://[^)]*\.(woff2?|ttf|otf|eot)", re.I),
     "外部字体不被支持"),
]

# ── CJK + punctuation patterns ──────────────────────────────────────────────
CJK = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf\u3000-\u303f\uff00-\uffef]")
# 中文字后紧跟半角逗号/分号/叹号/问号（应改全角）；只查"中文在前"避免中英混排误伤
HALF_PUNCT = re.compile(r"[\u4e00-\u9fff][,;!?]")
ASCII_QUOTE = re.compile("""["']""")
# 公式残留：成对 $...$ 或 $$...$$
LEFTOVER_INLINE = re.compile(r"(?<![\\$])\$(?!\$)([^$\n]+?)\$(?!\$)")
LEFTOVER_BLOCK = re.compile(r"\$\$([^$]+?)\$\$")
# 代码区特征：等宽字体或 white-space:pre —— 其内半角符号是正常的
CODE_STYLE = re.compile(r"monospace|white-space\s*:\s*pre(?![-\w])|courier|consolas|sf mono", re.I)


def _check_leftover_formulas(html: str) -> list[str]:
    """Return leftover formula markers in the HTML (excluding rendered images)."""
    soup = _html_to_soup(html)
    for el in soup(["code", "pre", "script", "style"]):
        el.decompose()
    text = soup.get_text(separator="\n")
    findings: list[str] = []
    for m in LEFTOVER_BLOCK.finditer(text):
        findings.append(f"未渲染的块级公式: $${m.group(1)[:30]}{'…' if len(m.group(1)) > 30 else ''}$$")
    for m in LEFTOVER_INLINE.finditer(text):
        findings.append(f"未渲染的行内公式: ${m.group(1)[:30]}{'…' if len(m.group(1)) > 30 else ''}$")
    return findings


def _html_to_soup(html: str):
    """Cheap html parser; BeautifulSoup is already a dep of the converter."""
    from bs4 import BeautifulSoup
    return BeautifulSoup(html, "html.parser")


class _StatsParser(HTMLParser):
    """Walk the HTML to gather: leaf-span count, half-punct snippets, code depth."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.leaf_depth = 0
        self.code_depth = 0
        self.leaf_total = 0
        self.half_punct_samples: list[str] = []
        self.ascii_quote_samples: list[str] = []

    def handle_starttag(self, tag, attrs):
        ad = dict(attrs)
        if tag == "span" and "leaf" in ad:
            self.leaf_total += 1
            self.leaf_depth += 1
        if CODE_STYLE.search(ad.get("style", "") or ""):
            self.code_depth += 1

    def handle_endtag(self, tag):
        # Naive: track per open tag; for our stats we only need depth, so just
        # decrement when the tag matches the last-open. Good enough for stats.
        if tag == "span" and self.leaf_depth > 0:
            self.leaf_depth -= 1
        if self.code_depth > 0 and tag in ("pre", "code", "span"):
            self.code_depth -= 1

    def handle_data(self, data):
        if self.code_depth > 0:
            return
        if CJK.search(data):
            if HALF_PUNCT.search(data):
                snippet = data[:24] + ("…" if len(data) > 24 else "")
                self.half_punct_samples.append(snippet)
            if ASCII_QUOTE.search(data):
                snippet = data[:24] + ("…" if len(data) > 24 else "")
                self.ascii_quote_samples.append(snippet)


def validate(html: str, name: str = "<input>", formula_mode: str = "latex") -> dict:
    """Run all checks. Returns ``{"errors": [...], "warnings": [...], "stats": {...}}``.

    ``formula_mode``:
      - ``"latex"`` (default): raw ``$...$`` / ``$$...$$`` is the intended form
        (rendered by a downstream MathJax/KaTeX renderer), so the leftover-
        formula check is skipped.
      - ``"image"``: unrendered ``$...$`` is an error (must run
        render_formulas.py first).
    """
    errors: list[str] = []
    warnings: list[str] = []
    for rx, msg in FORBIDDEN:
        hits = len(rx.findall(html))
        if hits:
            errors.append(f"{msg}（命中 {hits} 处）")

    # Formula leftovers — only an error in image mode. In latex mode the raw
    # $...$ is intentional and rendered downstream, so don't flag it.
    if formula_mode != "latex":
        leftovers = _check_leftover_formulas(html)
        errors.extend(leftovers)

    # Style stats + CJK punctuation
    parser = _StatsParser()
    try:
        parser.feed(html)
    except Exception as exc:  # 容错：解析失败不致命
        warnings.append(f"HTML 解析中断: {exc}")

    if parser.half_punct_samples:
        sample = "；".join(f"「{s}」" for s in parser.half_punct_samples[:3])
        warnings.append(
            f"{len(parser.half_punct_samples)} 处正文疑似半角标点（中文后跟 , ; ! ? ），"
            f"应改中文全角（代码块内不计）。例：{sample}"
        )
    if parser.ascii_quote_samples:
        sample = "；".join(f"「{s}」" for s in parser.ascii_quote_samples[:3])
        warnings.append(
            f"{len(parser.ascii_quote_samples)} 处正文出现英文直引号 \" ' ，"
            f"应改中文弯引号“”‘’。例：{sample}"
        )

    # Counts (informational, not warning-level)
    soup = _html_to_soup(html)
    formula_imgs = sum(1 for img in soup.find_all("img")
                       if (img.get("alt", "") or "").startswith("公式 "))
    all_imgs = len(soup.find_all("img"))
    cjk_chars = len(CJK.findall(html))

    return {
        "errors": errors,
        "warnings": warnings,
        "stats": {
            "name": name,
            "size_bytes": len(html.encode("utf-8")),
            "cjk_chars": cjk_chars,
            "images": all_imgs,
            "formula_images": formula_imgs,
            "leaf_spans": parser.leaf_total,
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("file", nargs="?", help="HTML 文件路径（省略时从 stdin 读）")
    ap.add_argument("--stdin", action="store_true", help="从标准输入读取")
    ap.add_argument("--formula-mode", choices=("latex", "image"), default="latex",
                    help="公式承载方式：latex=保留原始 $...$（默认），image=需预渲染为图片")
    args = ap.parse_args()

    if args.stdin or not args.file:
        html = sys.stdin.read()
        name = "<stdin>"
    else:
        try:
            with open(args.file, encoding="utf-8", errors="replace") as f:
                html = f.read()
        except OSError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 2
        name = args.file

    result = validate(html, name, formula_mode=args.formula_mode)
    s = result["stats"]
    print(f"📋 公众号 HTML 合规校验 — {s['name']}")
    print(f"   大小 {s['size_bytes']:,} B · 中文字符 {s['cjk_chars']:,} · "
          f"图片 {s['images']}（公式 {s['formula_images']}）· span leaf {s['leaf_spans']}")
    if result["errors"]:
        print(f"\n❌ ERROR ×{len(result['errors'])}（必须修复，否则粘贴后失效）:")
        for e in result["errors"]:
            print(f"   • {e}")
    if result["warnings"]:
        print(f"\n⚠️  WARNING ×{len(result['warnings'])}（建议检查）:")
        for w in result["warnings"]:
            print(f"   • {w}")
    if not result["errors"] and not result["warnings"]:
        print("\n✅ 完全合规，可直接推送")
    elif not result["errors"]:
        print("\n✅ 无致命问题，可推送（warning 请人工确认）")
    return 1 if result["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
