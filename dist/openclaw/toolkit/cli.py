#!/usr/bin/env python3
"""
CLI entry point for GzhWrite.

Usage:
    python cli.py preview article.md --theme professional-clean
    python cli.py publish article.md --appid wx123 --secret abc123
    python cli.py themes
"""

import argparse
import sys
import webbrowser
from pathlib import Path

import yaml

from converter import WeChatConverter, preview_html
from theme import load_theme, list_themes, Theme
from wechat_api import get_access_token, upload_image, upload_thumb
from publisher import create_draft, create_image_post
from validate_html import validate as validate_html
from component_lint import lint_markdown as lint_source
from layout import layout_markdown, LayoutOptions

# Config file search order
CONFIG_PATHS = [
    Path.cwd() / "config.yaml",
    Path(__file__).parent.parent / "config.yaml",  # skill root
    Path(__file__).parent / "config.yaml",          # toolkit dir
    Path.home() / ".config" / "gzh-write" / "config.yaml",
]


def load_config() -> dict:
    """Load config from first found config.yaml."""
    for p in CONFIG_PATHS:
        if p.exists():
            with open(p, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
    return {}


def _add_layout_flags(p):
    """Attach the shared 排版 toggle flags to a subparser."""
    p.add_argument("--no-layout", action="store_true",
                   help="跳过排版预处理（直接转换，不走智能处理）")
    p.add_argument("--no-punct", action="store_true", help="关闭中文全角标点归一")
    p.add_argument("--no-numbering", action="store_true", help="关闭章节自动编号")
    p.add_argument("--no-toc", action="store_true", help="关闭目录导读卡片")
    p.add_argument("--no-signature", action="store_true", help="关闭尾部签名区")
    p.add_argument("--english-label", action="store_true", help="为 ## 标题加英文 eyebrow 标签")
    p.add_argument("--keyword-underline", action="store_true", help="给加粗短语加下划线（实验性）")


def _build_layout_options(args, cfg) -> LayoutOptions:
    """Construct LayoutOptions from CLI args + config fallbacks."""
    wechat_cfg = cfg.get("wechat", {})
    author = getattr(args, "author", None) or wechat_cfg.get("author") or "{{作者名}}"
    return LayoutOptions(
        fullwidth_punct=not getattr(args, "no_punct", False),
        section_numbering=not getattr(args, "no_numbering", False),
        toc=not getattr(args, "no_toc", False),
        signature=not getattr(args, "no_signature", False),
        english_label=getattr(args, "english_label", False),
        keyword_underline=getattr(args, "keyword_underline", False),
        author=author,
        bio=cfg.get("bio", "{{一句话简介，如：热衷于分享 AI 观察与干货}}"),
        mode=("tech" if getattr(args, "tech", False) else "wechat"),
    )


def _formula_mode(args, cfg) -> str:
    """Resolve formula mode: CLI flag wins, else config, else 'latex'."""
    cli_val = getattr(args, "formula_mode", None)
    if cli_val:
        return cli_val
    return cfg.get("formula_mode", "latex")


def _maybe_render_formula_images(args, cfg):
    """In 'image' mode, convert raw $...$ to PNG images via render_formulas.py.

    In 'latex' mode this is a no-op — raw LaTeX is kept for the downstream
    renderer. Returns nothing; on failure prints an error and exits.
    """
    if _formula_mode(args, cfg) != "image":
        return
    import subprocess
    script = Path(__file__).resolve().parent.parent / "scripts" / "render_formulas.py"
    if not script.exists():
        print(f"❌ image 模式需要 {script}，但文件不存在。", file=sys.stderr)
        sys.exit(2)
    print("   🖼  公式模式 image：预渲染 $...$ 为 PNG 图片 …")
    proc = subprocess.run(
        [sys.executable, str(script), str(Path(args.input).resolve())],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        print(proc.stdout)
        print(proc.stderr, file=sys.stderr)
        print("❌ 公式图片渲染失败，已终止。请修复 LaTeX 后重试。", file=sys.stderr)
        sys.exit(1)
    print(proc.stdout)


def _run_pipeline(args, cfg, theme):
    """Run the full 排版 pipeline: source-lint → layout → convert.

    Returns ``(result, lint, report)``. Source-lint (first gate) and
    layout (排版预处理) run before the deterministic converter, matching
    gzh-design-skill's 双门 + 智能处理 flow adapted to this project.
    """
    # In image mode, pre-render raw $...$ to PNG images before lint/layout so
    # the rest of the pipeline sees the rendered <img> references.
    _maybe_render_formula_images(args, cfg)

    src = Path(args.input).read_text(encoding="utf-8")

    # ── 第一道门：源侧 lint（在排版/转换之前抓平台失效标记）──
    lint = lint_source(src, name=args.input, formula_mode=_formula_mode(args, cfg))
    _print_lint(lint)

    # ── 排版预处理（参考 gzh-design-skill 智能处理）──
    if not getattr(args, "no_layout", False):
        opts = _build_layout_options(args, cfg)
        enriched, report = layout_markdown(src, opts)
        _print_layout_report(report)
    else:
        enriched, report = src, {}

    converter = WeChatConverter(theme=theme, tech_enhance=getattr(args, "tech", False))
    result = converter.convert(enriched)
    return result, lint, report


def _print_lint(lint: dict) -> None:
    """Pretty-print the source-side lint result (first gate)."""
    if lint["errors"]:
        print(f"\n📐 源侧检查 ERROR ×{len(lint['errors'])}（建议先修复再排版）:")
        for e in lint["errors"][:12]:
            loc = f"L{e['line']}" if e["line"] else "—"
            print(f"   • [{loc}] {e['message']}")
        if len(lint["errors"]) > 12:
            print(f"   … 其余 {len(lint['errors']) - 12} 条略")
    if lint["warnings"]:
        print(f"   ⚠️  源侧 WARNING ×{len(lint['warnings'])}（建议检查）")
    if not lint["errors"] and not lint["warnings"]:
        print("   📐 源侧检查：无问题")


def _print_layout_report(report: dict) -> None:
    """Pretty-print what the 排版 preprocessing changed."""
    if not report:
        return
    parts = []
    if report.get("fullwidth_punct"):
        parts.append(f"全角标点 {report['fullwidth_punct']} 处")
    if report.get("section_numbering"):
        parts.append(f"章节编号 {report['section_numbering']} 处")
    if report.get("toc"):
        parts.append("目录导读")
    if report.get("signature"):
        parts.append("签名区")
    if report.get("english_label"):
        parts.append(f"英文标签 {report['english_label']} 处")
    if report.get("keyword_underline"):
        parts.append(f"关键词下划线 {report['keyword_underline']} 处")
    if parts:
        print(f"   ✨ 自动排版：{'; '.join(parts)}")


def _resolve_theme(args, cfg) -> Theme:
    """Pick the layout Theme: Doocs backend or local theme.

    layout.source == "doocs"  → build_doocs_theme(...)  (md.doocs.org 官方排版)
    otherwise                 → load_theme(...)         (内置 20 主题)
    """
    layout_cfg = cfg.get("layout", {}) or {}
    source = getattr(args, "layout_source", None) or layout_cfg.get("source", "local")
    if str(source).lower() == "doocs":
        from doocs_themes import build_doocs_theme, list_doocs_themes
        dox = layout_cfg.get("doocs", {}) or {}
        theme_name = getattr(args, "doocs_theme", None) or dox.get("theme", "default")
        primary = getattr(args, "doocs_primary", None) or dox.get("primary")
        font_size = getattr(args, "doocs_font_size", None) or dox.get("font_size")
        try:
            return build_doocs_theme(
                theme_name=theme_name, primary_color=primary, font_size=font_size
            )
        except FileNotFoundError as e:
            avail = ", ".join(list_doocs_themes())
            print(f"⚠️  Doocs 主题 {theme_name} 不存在（可用: {avail}），回退到本地主题。",
                  file=sys.stderr)
        # fall through to local theme on error
    theme_name = args.theme or cfg.get("theme", "professional-clean")
    return load_theme(theme_name)


def cmd_preview(args):
    """Generate HTML preview and open in browser."""
    cfg = load_config()
    theme = _resolve_theme(args, cfg)
    formula_mode = _formula_mode(args, cfg)
    result, lint, report = _run_pipeline(args, cfg, theme)

    # Wrap in full HTML for browser preview. In latex mode, inject MathJax so
    # the raw $...$ / $$...$$ render as real math in the local browser.
    full_html = preview_html(result.html, theme, mathjax=(formula_mode == "latex"))

    # Write to temp file
    input_path = Path(args.input)
    output = args.output or str(input_path.with_suffix(".html"))
    Path(output).write_text(full_html, encoding="utf-8")

    print(f"Title: {result.title}")
    print(f"Digest: {result.digest}")
    print(f"Images: {len(result.images)}")
    print(f"Output: {output}")

    # Run the dual-gate validation (auto-validate after preview).
    # NOTE: validate the WeChat fragment (result.html), not the browser
    # preview wrapper — the wrapper legitimately uses <style>/<div> for
    # local viewing only; only the fragment is pushed to 公众号.
    v = validate_html(result.html, name=output, formula_mode=formula_mode)
    _print_validation(v)

    if not args.no_open:
        webbrowser.open(f"file://{Path(output).absolute()}")
        print("Opened in browser.")


def cmd_publish(args):
    """Convert, upload images, and create WeChat draft."""
    cfg = load_config()
    wechat_cfg = cfg.get("wechat", {})

    # Resolve from CLI args → config.yaml fallback
    appid = args.appid or wechat_cfg.get("appid")
    secret = args.secret or wechat_cfg.get("secret")
    author = args.author or wechat_cfg.get("author")
    tech_enhance = args.tech or cfg.get("mode", "") == "tech"

    if not appid or not secret:
        print("Error: --appid and --secret required (or set in config.yaml)", file=sys.stderr)
        sys.exit(1)

    theme = _resolve_theme(args, cfg)
    result, lint, report = _run_pipeline(args, cfg, theme)

    # Publishing must not ship content that fails the first gate
    # (unrendered formulas, raw <div>/class=, etc. would break on paste).
    if lint["errors"]:
        print(f"\n❌ 源侧检查有 {len(lint['errors'])} 个 ERROR，已终止发布。"
              f"请修复后再 publish。", file=sys.stderr)
        sys.exit(1)

    formula_mode = _formula_mode(args, cfg)

    print(f"Title: {result.title}")
    print(f"Digest: {result.digest}")
    print(f"Images found: {len(result.images)}")

    # Get access token
    token = get_access_token(appid, secret)
    print("Access token obtained.")

    # Upload images referenced in article and replace src
    # Resolve relative paths against the markdown file's directory
    md_dir = Path(args.input).resolve().parent
    html = result.html
    for img_src in result.images:
        if img_src.startswith(("http://", "https://")):
            print(f"Skipping remote image: {img_src}")
            continue

        # Try: absolute → relative to CWD → relative to markdown file
        img_path = Path(img_src)
        if not img_path.is_absolute():
            if not img_path.exists():
                img_path = md_dir / img_src

        if img_path.exists():
            print(f"Uploading image: {img_src}")
            wechat_url = upload_image(token, str(img_path))
            html = html.replace(img_src, wechat_url)
            print(f"  -> {wechat_url}")
        else:
            print(f"Warning: image not found: {img_src} (searched {md_dir})")

    # Upload cover image if provided
    thumb_media_id = None
    if args.cover:
        print(f"Uploading cover: {args.cover}")
        thumb_media_id = upload_thumb(token, args.cover)
        print(f"  -> media_id: {thumb_media_id}")

    # Create draft
    title = args.title or result.title or Path(args.input).stem
    digest = args.digest or result.digest
    draft = create_draft(
        access_token=token,
        title=title,
        html=html,
        digest=digest,
        thumb_media_id=thumb_media_id,
        author=author,
    )

    print(f"\nDraft created! media_id: {draft.media_id}")

    # Auto-validate the published HTML (errors would only surface after paste;
    # catching them here saves a round-trip to the editor).
    v = validate_html(html, name=f"<publish:{args.input}>", formula_mode=formula_mode)
    _print_validation(v)


def cmd_themes(args):
    """List available themes."""
    names = list_themes()
    for name in names:
        theme = load_theme(name)
        print(f"  {name:24s} {theme.description}")


def cmd_image_post(args):
    """Create a WeChat image post (小绿书) from image files."""
    cfg = load_config()
    wechat_cfg = cfg.get("wechat", {})

    appid = args.appid or wechat_cfg.get("appid")
    secret = args.secret or wechat_cfg.get("secret")

    if not appid or not secret:
        print("Error: --appid and --secret required (or set in config.yaml)", file=sys.stderr)
        sys.exit(1)

    images = args.images
    if not images:
        print("Error: at least 1 image required", file=sys.stderr)
        sys.exit(1)
    if len(images) > 20:
        print(f"Error: max 20 images, got {len(images)}", file=sys.stderr)
        sys.exit(1)

    token = get_access_token(appid, secret)
    print(f"Uploading {len(images)} images as permanent materials...")

    media_ids = []
    for img_path in images:
        p = Path(img_path)
        if not p.exists():
            print(f"Error: image not found: {img_path}", file=sys.stderr)
            sys.exit(1)
        print(f"  Uploading: {p.name}")
        mid = upload_thumb(token, str(p))
        media_ids.append(mid)
        print(f"    -> {mid}")

    title = args.title
    if len(title) > 32:
        print(f"Warning: title truncated to 32 chars (was {len(title)})")
        title = title[:32]

    content = args.content or ""

    result = create_image_post(
        access_token=token,
        title=title,
        image_media_ids=media_ids,
        content=content,
        open_comment=True,
    )

    print(f"\nImage post draft created!")
    print(f"  media_id: {result.media_id}")
    print(f"  images: {result.image_count}")
    print(f"  title: {title}")
    print(f"  请到公众号后台草稿箱检查并发布")


def cmd_gallery(args):
    """Render all themes side by side in a browser gallery."""
    from concurrent.futures import ThreadPoolExecutor

    # Use provided markdown or a built-in sample
    if args.input:
        md_text = Path(args.input).read_text(encoding="utf-8")
    else:
        md_text = _gallery_sample_markdown()

    names = list_themes()
    results = {}

    def render_theme(name):
        theme = load_theme(name)
        converter = WeChatConverter(theme=theme)
        result = converter.convert(md_text)
        return name, theme.description, result.html

    # Parallel rendering
    with ThreadPoolExecutor(max_workers=8) as pool:
        for name, desc, html in pool.map(lambda n: render_theme(n), names):
            results[name] = (desc, html)

    # Build gallery HTML
    gallery_html = _build_gallery_html(results, names)
    output = args.output or "/tmp/gzh-write-gallery.html"
    Path(output).write_text(gallery_html, encoding="utf-8")
    print(f"Gallery: {output} ({len(names)} themes)")

    if not args.no_open:
        webbrowser.open(f"file://{Path(output).absolute()}")


def cmd_learn_theme(args):
    """Learn a theme from a WeChat article URL."""
    import subprocess
    script = Path(__file__).parent.parent / "scripts" / "learn_theme.py"
    cmd = [sys.executable, str(script), args.url, "--name", args.name]
    result = subprocess.run(cmd)
    sys.exit(result.returncode)


def cmd_validate(args):
    """Run the WeChat HTML compliance validator on a file."""
    try:
        with open(args.file, encoding="utf-8", errors="replace") as f:
            html = f.read()
    except OSError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(2)
    v = validate_html(html, name=args.file)
    _print_validation(v)
    sys.exit(1 if v["errors"] else 0)


def cmd_layout(args):
    """Run the 排版 preprocessing standalone and write the enriched Markdown."""
    cfg = load_config()
    src = Path(args.input).read_text(encoding="utf-8")

    opts = LayoutOptions(
        fullwidth_punct=not args.no_punct,
        section_numbering=not args.no_numbering,
        toc=not args.no_toc,
        signature=not args.no_signature,
        english_label=args.english_label,
        keyword_underline=args.keyword_underline,
        author=args.author or cfg.get("wechat", {}).get("author") or "{{作者名}}",
        bio=args.bio or cfg.get("bio", "{{一句话简介}}"),
    )
    enriched, report = layout_markdown(src, opts)
    _print_layout_report(report)

    output = args.output or str(Path(args.input).with_suffix(".layout.md"))
    Path(output).write_text(enriched, encoding="utf-8")
    print(f"Layout written: {output}")


def _print_validation(v: dict) -> None:
    """Pretty-print the validator result (shared by preview/publish/validate)."""
    s = v["stats"]
    print(f"   校验: {s['size_bytes']:,} B · 中文字符 {s['cjk_chars']:,} · "
          f"图片 {s['images']}（公式 {s['formula_images']}）")
    if v["errors"]:
        print(f"   ❌ ERROR ×{len(v['errors'])}（必须修复）:")
        for e in v["errors"]:
            print(f"      • {e}")
    if v["warnings"]:
        print(f"   ⚠️  WARNING ×{len(v['warnings'])}（建议检查）:")
        for w in v["warnings"]:
            print(f"      • {w}")
    if not v["errors"] and not v["warnings"]:
        print("   ✅ 完全合规")
    elif not v["errors"]:
        print("   ✅ 无致命问题（warning 请人工确认）")


def _gallery_sample_markdown():
    return """# 示例文章标题

## 第一部分

这是一段正常的文章内容，用来展示不同主题的排版效果。GzhWrite 支持多种排版主题，每种都有独特的视觉风格。

说实话，选主题这件事——看截图永远不如看实际渲染效果。

## 关键数据

| 指标 | 数值 | 变化 |
|------|------|------|
| 阅读量 | 12,580 | +23% |
| 分享率 | 4.7% | +0.8% |
| 完读率 | 68% | -2% |

## 代码示例

```python
def hello():
    print("Hello, GzhWrite!")
```

> 好的排版不是让读者注意到设计，而是让读者忘记设计，只记住内容。

## 列表展示

- 第一个要点：简洁是设计的灵魂
- 第二个要点：一致性比创意更重要
- 第三个要点：移动端体验优先

**加粗文本**和*斜体文本*的样式也需要关注。

最后这段用来展示文章结尾的留白和间距效果。一篇好文章的结尾，应该像一首好歌的最后一个音符——恰到好处地收束。
"""


def _join_newline(items):
    """Join items with comma + newline (workaround for f-string limitation)."""
    return ",\n".join(items)


def _build_gallery_html(results, names):
    cards = []
    for name in names:
        desc, html = results[name]
        # Escape for embedding in JS
        escaped_html = html.replace('\\', '\\\\').replace('`', '\\`').replace('$', '\\$')
        cards.append(f"""
        <div class="theme-card" onclick="selectTheme('{name}')">
          <div class="theme-name">{name}</div>
          <div class="theme-desc">{desc}</div>
          <div class="phone-frame">
            <div class="phone-content" id="preview-{name}">{html}</div>
          </div>
          <button class="copy-btn" onclick="event.stopPropagation(); copyHTML('{name}')">复制 HTML</button>
        </div>""")

    # Store HTML data for copy
    data_entries = []
    for name in names:
        desc, html = results[name]
        safe = html.replace('\\', '\\\\').replace("'", "\\'").replace('\n', '\\n')
        data_entries.append(f"  '{name}': '{safe}'")

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>GzhWrite 主题画廊</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #0f0f0f; color: #fff; }}
.header {{ text-align: center; padding: 40px 20px 20px; }}
.header h1 {{ font-size: 28px; font-weight: 700; }}
.header p {{ color: #888; margin-top: 8px; font-size: 15px; }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(340px, 1fr)); gap: 24px; padding: 24px; max-width: 1440px; margin: 0 auto; }}
.theme-card {{ background: #1a1a1a; border-radius: 12px; padding: 16px; cursor: pointer; transition: transform 0.2s, box-shadow 0.2s; }}
.theme-card:hover {{ transform: translateY(-4px); box-shadow: 0 8px 24px rgba(0,0,0,0.4); }}
.theme-name {{ font-size: 16px; font-weight: 700; margin-bottom: 4px; }}
.theme-desc {{ font-size: 13px; color: #888; margin-bottom: 12px; }}
.phone-frame {{ background: #fff; border-radius: 8px; overflow: hidden; max-height: 480px; overflow-y: auto; }}
.phone-content {{ padding: 16px; font-size: 14px; transform: scale(0.85); transform-origin: top left; width: 118%; }}
.copy-btn {{ margin-top: 12px; width: 100%; padding: 8px; background: #333; color: #fff; border: none; border-radius: 6px; cursor: pointer; font-size: 14px; }}
.copy-btn:hover {{ background: #555; }}
.toast {{ position: fixed; bottom: 40px; left: 50%; transform: translateX(-50%); background: #333; color: #fff; padding: 10px 24px; border-radius: 8px; font-size: 14px; display: none; z-index: 999; }}
</style>
</head>
<body>
<div class="header">
  <h1>GzhWrite 主题画廊</h1>
  <p>{len(names)} 个主题 · 点击卡片查看大图 · 点击「复制 HTML」直接粘贴到公众号编辑器</p>
</div>
<div class="grid">
{''.join(cards)}
</div>
<div class="toast" id="toast">已复制到剪贴板</div>
<script>
const themeData = {{
{_join_newline(data_entries)}
}};
function copyHTML(name) {{
  const html = themeData[name];
  if (html) {{
    navigator.clipboard.writeText(html).then(() => {{
      const t = document.getElementById('toast');
      t.style.display = 'block';
      setTimeout(() => t.style.display = 'none', 1500);
    }});
  }}
}}
function selectTheme(name) {{
  localStorage.setItem('gzh-write-theme', name);
  // Scroll to card for visual feedback
  const el = document.getElementById('preview-' + name);
  if (el) el.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
}}
</script>
</body>
</html>"""


def main():
    parser = argparse.ArgumentParser(
        prog="gzh-write",
        description="Markdown to WeChat HTML converter and publisher",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # preview
    p_preview = sub.add_parser("preview", help="Generate HTML and open in browser")
    p_preview.add_argument("input", help="Markdown file path")
    p_preview.add_argument("-t", "--theme", default="professional-clean", help="Theme name")
    p_preview.add_argument("-o", "--output", help="Output HTML file path")
    p_preview.add_argument("--no-open", action="store_true", help="Don't open browser")
    p_preview.add_argument("--tech", action="store_true", help="Enable tech-enhance mode (register/fn/param coloring + param tables)")
    p_preview.add_argument("--formula-mode", choices=("latex", "image"), default=None,
                           help="公式承载方式：latex=保留原始 $...$（由下游渲染器显示，默认）；image=预渲染为 PNG 图片")
    p_preview.add_argument("--layout-source", choices=("local", "doocs"), default=None,
                           help="排版引擎来源：local=内置主题；doocs=复用 md.doocs.org 官方排版主题")
    p_preview.add_argument("--doocs-theme", default=None, help="Doocs 主题名（default/grace/simple）")
    p_preview.add_argument("--doocs-primary", default=None, help="Doocs 主色覆盖，如 #3b82f6")
    p_preview.add_argument("--doocs-font-size", default=None, help="Doocs 正文字号，如 16px")
    _add_layout_flags(p_preview)

    # publish
    p_publish = sub.add_parser("publish", help="Convert and publish as WeChat draft")
    p_publish.add_argument("input", help="Markdown file path")
    p_publish.add_argument("-t", "--theme", default=None, help="Theme name")
    p_publish.add_argument("--appid", default=None, help="WeChat AppID (or set in config.yaml)")
    p_publish.add_argument("--secret", default=None, help="WeChat AppSecret (or set in config.yaml)")
    p_publish.add_argument("--cover", help="Cover image file path")
    p_publish.add_argument("--title", help="Override article title")
    p_publish.add_argument("--author", default=None, help="Article author (also used in signature area)")
    p_publish.add_argument("--digest", default=None, help="Override article digest (≤120 UTF-8 bytes)")
    p_publish.add_argument("--tech", action="store_true", help="Enable tech-enhance mode (auto-on when config mode=tech)")
    p_publish.add_argument("--formula-mode", choices=("latex", "image"), default=None,
                           help="公式承载方式：latex=保留原始 $...$（默认）；image=预渲染为 PNG 图片")
    p_publish.add_argument("--layout-source", choices=("local", "doocs"), default=None,
                           help="排版引擎来源：local=内置主题；doocs=复用 md.doocs.org 官方排版主题")
    p_publish.add_argument("--doocs-theme", default=None, help="Doocs 主题名（default/grace/simple）")
    p_publish.add_argument("--doocs-primary", default=None, help="Doocs 主色覆盖，如 #3b82f6")
    p_publish.add_argument("--doocs-font-size", default=None, help="Doocs 正文字号，如 16px")
    _add_layout_flags(p_publish)

    # layout（独立排版预处理）
    p_layout = sub.add_parser("layout", help="Run 排版 preprocessing on a Markdown file (auto-number / TOC / signature / fullwidth punct)")
    p_layout.add_argument("input", help="Markdown file path")
    p_layout.add_argument("-o", "--output", help="Output enriched Markdown path (default: <input>.layout.md)")
    p_layout.add_argument("--author", default=None, help="Signature-area author (default: {{作者名}} placeholder)")
    p_layout.add_argument("--bio", default=None, help="Signature-area one-line bio")
    p_layout.add_argument("--no-punct", action="store_true", help="Disable full-width punctuation normalization")
    p_layout.add_argument("--no-numbering", action="store_true", help="Disable section auto-numbering")
    p_layout.add_argument("--no-toc", action="store_true", help="Disable TOC / 导读 card")
    p_layout.add_argument("--no-signature", action="store_true", help="Disable trailing signature area")
    p_layout.add_argument("--english-label", action="store_true", help="Add English eyebrow labels to ## headings")
    p_layout.add_argument("--keyword-underline", action="store_true", help="Underline **bold** phrases (experimental)")

    # themes
    sub.add_parser("themes", help="List available themes")

    # image-post (小绿书)
    p_imgpost = sub.add_parser("image-post", help="Create WeChat image post (小绿书)")
    p_imgpost.add_argument("images", nargs="+", help="Image file paths (1-20, first = cover)")
    p_imgpost.add_argument("-t", "--title", required=True, help="Post title (max 32 chars)")
    p_imgpost.add_argument("-c", "--content", default="", help="Plain text description (max ~1000 chars)")
    p_imgpost.add_argument("--appid", default=None, help="WeChat AppID")
    p_imgpost.add_argument("--secret", default=None, help="WeChat AppSecret")

    # gallery
    p_gallery = sub.add_parser("gallery", help="Open theme gallery in browser")
    p_gallery.add_argument("input", nargs="?", default=None, help="Markdown file (optional, uses sample if omitted)")
    p_gallery.add_argument("-o", "--output", help="Output HTML file path")
    p_gallery.add_argument("--no-open", action="store_true", help="Don't open browser")

    # learn-theme
    p_learn = sub.add_parser("learn-theme", help="Learn formatting theme from a WeChat article URL")
    p_learn.add_argument("url", help="WeChat article URL")
    p_learn.add_argument("--name", required=True, help="Theme name")

    # validate
    p_val = sub.add_parser("validate", help="Validate a WeChat HTML file for platform compliance (dual-gate QA)")
    p_val.add_argument("file", help="HTML file to validate")

    args = parser.parse_args()

    try:
        if args.command == "preview":
            cmd_preview(args)
        elif args.command == "publish":
            cmd_publish(args)
        elif args.command == "themes":
            cmd_themes(args)
        elif args.command == "image-post":
            cmd_image_post(args)
        elif args.command == "gallery":
            cmd_gallery(args)
        elif args.command == "learn-theme":
            cmd_learn_theme(args)
        elif args.command == "validate":
            cmd_validate(args)
        elif args.command == "layout":
            cmd_layout(args)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
