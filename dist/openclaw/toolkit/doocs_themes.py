"""
Doocs MD 排版后端（md.doocs.org 官方主题）。

设计目标：把 md.doocs.org 编辑器的官方排版主题「复用」进 GzhWrite 的发布
管线，让文章拥有和 Doocs 微信公众号排版编辑器一样的视觉效果，同时保证
推送到草稿箱的 HTML 仍然是微信安全的（内联样式）。

为什么不能直接 POST 给 md.doocs.org？
  Doocs 的 Markdown→HTML 转换完全在浏览器端完成，服务端（Cloudflare
  Worker）只提供「分享 / 同步 / 图床」能力，并没有稳定的 /api/convert 接口。
  而且 Doocs 主题依赖 <style> + CSS 变量（var(--md-*)），微信草稿箱会
  剥离 <style> 与自定义属性 —— 直接把 Doocs 的 HTML 推过去样式会全丢。

本模块的做法：
  1. 读取随技能打包的官方主题 CSS（toolkit/doocs/themes/*.css）。
  2. 把 var(--md-*) 全部解析成具体数值（对齐 Doocs 编辑器默认值，
     主色 / 字号 / 字体可经配置覆盖）。
  3. 用既有的 theme 引擎（theme.py 的 get_inline_css_rules + WeChatConverter）
     把「标题/段落/引用/表格/图片/列表/强调」等纯排版规则**逐元素内联**。
  4. 丢弃 Doocs 的组件类（.markdown-alert / .codespan / .hljs …）以及
     section / #output 等结构性选择器，避免与 converter 已有的代码卡片、
     列表转 section、容器块转换打架。

最终通过和本地主题完全相同的草稿箱管线发布，运行时无需联网。
"""

import logging
import re
from pathlib import Path

import cssutils
from theme import Theme

cssutils.log.setLevel(logging.CRITICAL)

_THEMES_DIR = Path(__file__).parent / "doocs" / "themes"

# Doocs CSS 自定义属性的具体取值。对齐 doocs/md 仓库
# packages/core/src/theme/cssVariables.ts 的默认值，主色/字号可逐次覆盖。
DEFAULT_VARS = {
    "md-primary-color": "#3b82f6",
    "md-font-family": (
        '"PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", '
        "-apple-system, BlinkMacSystemFont, \"Segoe UI\", sans-serif"
    ),
    "md-font-size": "16px",
    "md-line-height": "1.75",
    "md-block-spacing": "1",
    "md-link-color": "#576b95",
    # 仅以 hsl(var(--foreground)) 形式使用，故给逗号语法以便微信渲染
    "foreground": "213, 11%, 20%",
    "blockquote-background": "#f6f8fa",
    "md-blockquote-background": "#f6f8fa",
}

# 允许内联的标签选择器；其余一律丢弃。
_ALLOWED_TAGS = {
    "h1", "h2", "h3", "h4", "h5", "h6", "p", "blockquote",
    "table", "thead", "tbody", "tr", "th", "td",
    "ul", "ol", "li", "hr", "strong", "em", "a", "img", "figure", "figcaption", "span",
}

# 即使选择器「简单」也禁止内联的类 / 结构（converter 已用不同方式渲染）。
_BLOCKED_SUBSTR = (
    "section", "#output", ".alert", ".markdown-alert",
    ".codespan", ".hljs", ".md-figcaption", ".mermaid",
)

# Doocs 的全局字体/字号/行高原本挂在 section / #output 上，但这两个结构性
# 选择器在微信里不能用（converter 已把列表/卡片转成 section）。这里补一条
# 针对正文的基线排版，保证段落、列表项、表格文字都有统一字体与行高。
_BASE_TYPO = """
p, li, td, th, blockquote, figcaption,
h1, h2, h3, h4, h5, h6 {
  font-family: var(--md-font-family);
  font-size: var(--md-font-size);
  line-height: var(--md-line-height);
}
"""


def list_doocs_themes() -> list[str]:
    """返回可用的 Doocs 主题名（不含 base.css）。"""
    names = []
    for p in _THEMES_DIR.glob("*.css"):
        if p.name == "base.css":
            continue
        names.append(p.stem)
    return sorted(names)


def _resolve_vars(css: str, overrides: dict) -> str:
    """把 var(--xxx) / var(--xxx, fallback) 替换成具体值。

    未知变量：有 fallback 用 fallback，否则保留原样（避免产生非法声明）。
    """
    vars_ = dict(DEFAULT_VARS)
    if overrides:
        vars_.update(overrides)

    _var_re = re.compile(r"var\(\s*--([a-zA-Z0-9_-]+)\s*(?:,\s*([^()]*?)\s*)?\)")

    def repl(m: re.Match) -> str:
        name = m.group(1).strip().lstrip("-")
        if name in vars_:
            return str(vars_[name])
        # 未知变量：优先用 fallback，否则保留原声明
        return m.group(2).strip() if m.group(2) else m.group(0)

    # 嵌套 var()（如 var(--a, var(--b))）需要多趟解析：先把内层 b 解析成
    # 具体值，外层 a 才能在下一趟命中 fallback/默认值。最多迭代若干趟直到稳定。
    out = css
    for _ in range(8):
        new = _var_re.sub(repl, out)
        if new == out:
            break
        out = new
    return out


def _strip_color_mix(css: str, primary: str) -> str:
    """微信不支持 color-mix()，直接用主色替掉，避免边框/背景失效。"""
    return re.sub(r"color-mix\([^)]*\)", primary, css)


def _is_safe_selector(sel: str) -> bool:
    """只放行纯标签的排版选择器。"""
    sel = sel.strip()
    if not sel:
        return False
    # 丢弃 class / id 形式的组件规则（.markdown-alert / #output ...）
    if sel[0] in ".#":
        return False
    # 伪类 / 组合符 / 属性选择器一律拒绝
    for ch in (":", "@", ">", "+", "~", "[", "*"):
        if ch in sel:
            return False
    tag = sel.split()[0].split(":")[0].lower()
    return tag in _ALLOWED_TAGS


def _filter_css(css_text: str) -> str:
    """保留安全的排版规则，返回拼接后的 CSS 文本。"""
    sheet = cssutils.parseString(css_text, validate=False)
    parts = []
    for rule in sheet:
        if rule.type != rule.STYLE_RULE:
            continue
        sels = [s.strip() for s in str(rule.selectorText).split(",")]
        if all(_is_safe_selector(s) for s in sels):
            text = rule.cssText
            if isinstance(text, bytes):
                text = text.decode("utf-8")
            parts.append(text)
    return "\n".join(parts)


def build_doocs_theme(
    theme_name: str = "default",
    primary_color: str = None,
    font_size: str = None,
) -> Theme:
    """
    构造一个与 WeChatConverter 兼容的 Theme 对象，使用 Doocs 官方主题。

    Args:
        theme_name: default / grace / simple（见 toolkit/doocs/themes/）。
        primary_color: 覆盖主题主色（标题下划线、强调、引用左边框等）。
        font_size: 覆盖正文字号，如 "16px"。
    Returns:
        theme.Theme —— 直接传给 WeChatConverter(theme=...)。
    """
    base = (_THEMES_DIR / "base.css").read_text(encoding="utf-8")
    theme_path = _THEMES_DIR / f"{theme_name}.css"
    if not theme_path.exists():
        avail = ", ".join(list_doocs_themes())
        raise FileNotFoundError(f"未知 Doocs 主题: {theme_name}（可用: {avail}）")
    theme_css = theme_path.read_text(encoding="utf-8")

    overrides = {}
    if primary_color:
        overrides["md-primary-color"] = primary_color
    if font_size:
        overrides["md-font-size"] = font_size

    combined = _BASE_TYPO + "\n" + base + "\n" + theme_css
    combined = _resolve_vars(combined, overrides)
    combined = _strip_color_mix(
        combined, overrides.get("md-primary-color", DEFAULT_VARS["md-primary-color"])
    )
    filtered = _filter_css(combined)

    primary = overrides.get("md-primary-color", DEFAULT_VARS["md-primary-color"])
    colors = {
        "text": "#24292f",
        "primary": primary,
        "background": "#ffffff",
        # 与本地主题一致的暗黑模式映射，保证微信深色模式下也协调
        "darkmode": {
            "text": "#c8c8c8",
            "background": "#1e1e1e",
            "primary": primary,
            "code_bg": "#2d2d2d",
            "code_color": "#d4d4d4",
            "quote_bg": "#2a2a2a",
        },
    }
    return Theme(
        name=f"doocs-{theme_name}",
        description=f"Doocs MD «{theme_name}» 主题（md.doocs.org 官方排版）",
        base_css=filtered,
        colors=colors,
    )
