"""
Markdown to WeChat-compatible HTML converter.

Forked from wechat_article_skills/scripts/markdown_to_html.py,
adapted for YAML-driven themes and agent integration.
"""

import base64
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import markdown
import urllib.request
from bs4 import BeautifulSoup

from theme import Theme, load_theme, get_inline_css_rules

# ── Math ($...$ / $$...$$) protection ────────────────────────────────────────
# python-markdown would mangle LaTeX containing _ * \ inside $...$ (e.g.
# U_{busy} → U<em>busy</em>, or \frac eaten). We stash each formula in a
# placeholder that markdown leaves untouched, then restore the raw LaTeX
# verbatim after parsing — so a downstream MathJax/KaTeX renderer shows it
# exactly as written.
_MATH_RE = re.compile(r"\$\$.+?\$\$|\$[^$\n]+?\$", re.DOTALL)

# Fenced code blocks and inline code must never be scanned for math: a shell
# snippet like ``echo $$ > tasks`` would otherwise open a ``$$...$$`` region
# that swallows everything up to the next block formula — silently dropping
# images, formulas and whole paragraphs that follow it.
_CODE_SPLIT_RE = re.compile(r"(```.*?```|`[^`\n]*`)", re.DOTALL)


def _protect_math(text: str) -> tuple[str, list[str]]:
    """Replace $...$ / $$...$$ with inert placeholders; return (text, store).

    Code spans and fences are left untouched so a literal ``$$`` inside a
    shell example cannot be mistaken for a display-math delimiter.
    """
    store: list[str] = []

    def _stash(m: re.Match) -> str:
        store.append(m.group(0))
        return f"zmathph{len(store) - 1}z"

    out: list[str] = []
    for seg in _CODE_SPLIT_RE.split(text):
        is_code = seg.startswith("```") or (
            len(seg) > 1 and seg.startswith("`") and seg.endswith("`")
        )
        out.append(seg if is_code else _MATH_RE.sub(_stash, seg))
    return "".join(out), store


def _restore_math(html: str, store: list[str]) -> str:
    """Put the raw LaTeX back where its placeholder sits."""
    if not store:
        return html

    def _unstash(m: re.Match) -> str:
        idx = int(m.group(1))
        return store[idx] if 0 <= idx < len(store) else m.group(0)

    return re.sub(r"zmathph(\d+)z", _unstash, html)


@dataclass
class ConvertResult:
    """Result of a Markdown → WeChat HTML conversion."""

    html: str  # WeChat-compatible inline-style HTML (body content only)
    title: str  # Extracted H1 title
    digest: str  # Auto-generated summary (first 120 chars)
    images: list[str] = field(default_factory=list)  # Image references found


class WeChatConverter:
    """Convert Markdown to WeChat-compatible inline-style HTML."""

    # tech-enhance inline-code category styles. Applied only when
    # tech_enhance=True to add subtle differentiation of register /
    # function / identifier tokens in technical articles. Default color
    # values fall back to theme.colors when available.
    _TECH_CODE_CATEGORIES = {
        # x86 / ARM / RISC-V register patterns: %rbp, %rax, x0, flag.Z etc.
        "register": r"(^%[a-z0-9]+$|^[rxe][0-9a-z]+$|^[a-z]+\\.[a-z]+$|^\\$[a-z0-9_]+$)",
        # function / syscall name ending with ( or () — pure identifier hooks
        "function": r"^[a-zA-Z_][a-zA-Z0-9_]*\\(\\)?$",
        # hex / binary literal
        "number":   r"^(0x[0-9a-fA-F]+|0b[01]+|\\d+[dh]?$)",
        # kebab / snake env / config key (PATH, DB_HOST, -O2)
        "param":    r"^(--?[a-zA-Z-]+|[A-Z][A-Z0-9_]{2,}|[a-z][a-z0-9_]*=[^\\s]+)$",
    }

    _GITHUB_CODE_HIGHLIGHT = {
        "#008000": "#cf222e",
        "#b00040": "#cf222e",
        "#0000ff": "#8250df",
        "#ba2121": "#0a3069",
        "#408080": "#6e7781",
        "#000000": "#1f2328",
        "#a00000": "#82071e",
        "#00a000": "#116329",
    }

    _GITHUB_CODE_HIGHLIGHT_DARK = {
        "#008000": "#ff7b72",
        "#b00040": "#ff7b72",
        "#0000ff": "#d2a8ff",
        "#ba2121": "#a5d6ff",
        "#408080": "#8b949e",
        "#000000": "#e6edf3",
        "#a00000": "#ffdcd7",
        "#00a000": "#aceabb",
    }

    # Beautiful code-card palette. Light values are used as the normal inline
    # style; the matching dark values are mirrored onto data-darkmode-*
    # attributes so the card also looks right when WeChat's dark mode is on.
    _CODE_CARD = {
        # light (normal, GitHub-ish)
        "border": "#d0d7de",
        "header_bg": "#eaeef2",
        "header_fg": "#57606a",
        "code_bg": "#f6f8fa",
        "code_fg": "#24292f",
        # dark (WeChat dark mode)
        "dm_border": "#30363d",
        "dm_header_bg": "#161b22",
        "dm_header_fg": "#8b949e",
        "dm_code_bg": "#0d1117",
        "dm_code_fg": "#c9d1d9",
    }

    def __init__(
        self,
        theme: Optional[Theme] = None,
        theme_name: str = "professional-clean",
        tech_enhance: bool = False,
    ):
        if theme is not None:
            self._theme = theme
        else:
            self._theme = load_theme(theme_name)
        self._css_rules = get_inline_css_rules(self._theme)
        self._tech_enhance = tech_enhance

    def convert(self, markdown_text: str) -> ConvertResult:
        """
        Convert Markdown text to WeChat-compatible HTML.

        Returns ConvertResult with:
          - html: inline-style HTML (body content only, no <html>/<head> wrapper)
          - title: extracted H1 title (or empty string)
          - digest: first 120 characters of plain text
          - images: list of image src references
        """
        title = self._extract_title(markdown_text)
        markdown_text = self._strip_h1(markdown_text)

        # Pre-process container blocks (:::dialogue, :::timeline, etc.)
        markdown_text = self._preprocess_containers(markdown_text)

        # CJK fix: auto-space between CJK and Latin characters
        markdown_text = self._fix_cjk_spacing(markdown_text)

        # Protect $...$ / $$...$$ from markdown's emphasis/escape processing,
        # parse to HTML, then restore the raw LaTeX verbatim (so $U_{busy}$
        # and $\frac{a}{b}$ survive intact for a downstream renderer).
        protected, math_store = _protect_math(markdown_text)
        html = self._markdown_to_html(protected)
        html = _restore_math(html, math_store)

        # Annotate fenced code blocks with their language. codehilite (with
        # noclasses) strips the ``language-*`` class from <code>, so we recover
        # the language from the source fence order and pair it to the <pre>
        # elements in document order. This drives the code-card header label.
        html = self._annotate_code_langs(markdown_text, html)

        # Convert <u>...</u> (keyword underline from layout / author) into a
        # real underline span — WeChat strips bare <u>, but inline
        # text-decoration survives. Done right after parse, before styling.
        html = self._convert_underline(html)

        # Enhance code blocks (add data-lang attribute)
        html = self._enhance_code_blocks(html)

        # Process images (ensure responsive styling)
        html, images = self._process_images(html)

        # CJK fix: move punctuation outside bold tags
        html = self._fix_cjk_bold_punctuation(html)

        # CJK fix: convert ul/ol to section-based lists (WeChat renders native lists unreliably)
        html = self._convert_lists_to_sections(html)

        # Convert external links to footnotes (WeChat blocks external links)
        html = self._convert_links_to_footnotes(html)

        # Apply inline CSS from theme
        html = self._apply_inline_styles(html)

        # Apply WeChat compatibility fixes
        html = self._apply_wechat_fixes(html)

        # tech-enhance: classify inline <code> tokens (register/fn/param/number)
        if self._tech_enhance:
            html = self._enhance_inline_code_categories(html)
            html = self._enhance_param_tables(html)

        # Inject dark mode attributes
        html = self._inject_darkmode(html)

        # Apply GitHub-like syntax highlighting colors (after dark mode so data-darkmode-* attrs exist)
        html = self._apply_github_code_highlight(html)

        # Wrap code blocks in beautiful cards (after colors so the card frames
        # the already-highlighted code; before the unsupported-tag strip so the
        # original <div class="codehilite">> is replaced, not converted).
        html = self._build_code_cards(html)

        # Final WeChat-compat pass: the published fragment must contain no
        # <div> (WeChat rewrites it) and no class= (WeChat strips it). The
        # codehilite extension emits <div class="codehilite"> and fenced code
        # adds class="language-*"; both are converted to <section> + inline
        # styles we already emit, so stripping is lossless for rendering.
        html = self._strip_unsupported_tags(html)

        # Generate digest from plain text
        digest = self._generate_digest(html)

        return ConvertResult(html=html, title=title, digest=digest, images=images)

    def convert_file(self, input_path: str) -> ConvertResult:
        """Convert a Markdown file."""
        path = Path(input_path)
        if not path.exists():
            raise FileNotFoundError(f"Input file not found: {input_path}")

        text = path.read_text(encoding="utf-8")
        return self.convert(text)

    # -- internal methods --

    def _extract_title(self, text: str) -> str:
        """Extract the first H1 title from Markdown text."""
        for line in text.split("\n"):
            stripped = line.strip()
            if stripped.startswith("# ") and not stripped.startswith("## "):
                return stripped[2:].strip()
        return ""

    def _strip_h1(self, text: str) -> str:
        """Remove H1 lines — WeChat has a separate title field."""
        lines = []
        for line in text.split("\n"):
            stripped = line.strip()
            if stripped.startswith("# ") and not stripped.startswith("## "):
                continue
            lines.append(line)
        return "\n".join(lines)

    def _markdown_to_html(self, text: str) -> str:
        """Parse Markdown to HTML using python-markdown with extensions."""
        extensions = [
            "markdown.extensions.fenced_code",
            "markdown.extensions.tables",
            "markdown.extensions.nl2br",
            "markdown.extensions.sane_lists",
            "markdown.extensions.attr_list",
            "codehilite",
        ]
        extension_configs = {
            "codehilite": {
                "linenums": False,
                "guess_lang": True,
                "noclasses": True,  # Inline syntax highlight styles
            }
        }
        md = markdown.Markdown(extensions=extensions, extension_configs=extension_configs)
        return md.convert(text)

    def _convert_underline(self, html: str) -> str:
        """Turn ``<u>text</u>`` into an inline underline span.

        WeChat's editor strips bare ``<u>`` tags, but an inline
        ``text-decoration: underline`` span survives paste. The layout stage
        (or the author) emits ``<u>``; this normalizes it so underlines render.
        """
        return re.sub(
            r"<u>(.*?)</u>",
            r'<span style="text-decoration: underline;">\1</span>',
            html,
            flags=re.DOTALL,
        )

    def _annotate_code_langs(self, md_text: str, html: str) -> str:
        """Recover fenced-code languages from the markdown and tag each ``<pre>``.

        codehilite (noclasses) drops the ``language-*`` class, so the language
        is lost by the time we build the code card. We read the fence info
        strings (```` ```python ````) from the source, in document order, and
        set ``data-lang`` on the matching ``<pre>`` elements (also in order).
        """
        langs: list[str] = []
        for m in re.finditer(r"```[ \t]*([A-Za-z0-9_+\-]+)?", md_text):
            lang = (m.group(1) or "").lower()
            # Only count opening fences that declare a language; bare/closing
            # fences (no language token) are ignored so the pairing with <pre>
            # elements (which only exist for real code blocks) stays aligned.
            if lang:
                langs.append(lang)
        if not langs:
            return html
        soup = BeautifulSoup(html, "html.parser")
        pres = soup.find_all("pre")
        for pre, lang in zip(pres, langs):
            if lang:
                pre["data-lang"] = lang
        return str(soup)

    def _enhance_code_blocks(self, html: str) -> str:
        """Add data-lang attribute to <pre> elements for language labeling."""
        soup = BeautifulSoup(html, "html.parser")
        for pre in soup.find_all("pre"):
            code = pre.find("code")
            if code:
                for cls in code.get("class", []):
                    if cls.startswith("language-"):
                        pre["data-lang"] = cls.replace("language-", "")
                        break
        return str(soup)

    def _build_code_cards(self, html: str) -> str:
        """Wrap each ``<pre>`` (from codehilite) into a beautiful code card.

        GitHub-style card: a header bar with mac-style traffic-light dots
        and the language label, plus a rounded, padded, monospaced body.
        All styling is inline (no ``class``/``<div>``) and the card carries
        ``data-darkmode-*`` attributes so it also looks right in WeChat's
        dark mode.

        Output structure (flat, ``<section>`` outer + ``<p>`` slices)::

            <section style="card-shell">
              <p style="header">[red][yellow][green] LANG</p>
              <p style="body"><pre><code>...</code></pre></p>
            </section>

        Why ``<p>`` for header/body instead of nested ``<section>``:
        WeChat's editor treats each top-level ``<section>`` as its own
        paragraph; nesting two ``<section>``s under one card turns the
        header into a tiny "YAML" paragraph followed by the code, with
        a visible gap between them — visibly broken. ``<p>`` slices inside
        a single ``<section>`` shell render as one continuous card with
        the header on top and the code below it.

        The original ``<div class="codehilite">`` wrapper is replaced by
        the card, so the downstream ``_strip_unsupported_tags`` pass has
        nothing to convert.
        """
        soup = BeautifulSoup(html, "html.parser")
        c = self._CODE_CARD
        font_stack = ("-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'PingFang SC',"
                      "'Microsoft YaHei',sans-serif")
        mono_stack = ("'SFMono-Regular',Consolas,'Liberation Mono',Menlo,monospace")

        for div in soup.find_all("div", class_="codehilite"):
            pre = div.find("pre")
            if pre is None:
                continue
            lang = (pre.get("data-lang") or "code").upper()

            # Header: three mac dots + language label.
            header = soup.new_tag("p")
            header["style"] = (
                f"margin:0;background:{c['header_bg']};padding:9px 14px;"
                f"font-size:12px;color:{c['header_fg']};"
                f"font-family:{font_stack};letter-spacing:.4px;"
            )
            header["data-darkmode-bgcolor"] = c["dm_header_bg"]
            header["data-darkmode-color"] = c["dm_header_fg"]
            for dot_color in ("#ff5f56", "#ffbd2e", "#27c93f"):
                dot = soup.new_tag("span")
                dot["style"] = (
                    "display:inline-block;width:9px;height:9px;border-radius:50%;"
                    f"background:{dot_color};margin-right:6px;vertical-align:middle;"
                )
                header.append(dot)
            label = soup.new_tag("span")
            label["style"] = "font-weight:600;vertical-align:middle;"
            label.string = lang
            header.append(label)

            # Strip the chip-cosmetic style the theme applied to the inner
            # ``<code>`` (padding / background / border-radius / border /
            # font-size / color / font-family). Without this the theme's
            # ``code`` rule paints every line of code as a separate sticker
            # inside the card, which WeChat then renders as broken text.
            code = pre.find("code")
            if code is not None:
                existing = code.get("style", "")
                style_dict = {}
                if existing:
                    for item in existing.split(";"):
                        if ":" in item:
                            k, v = item.split(":", 1)
                            style_dict[k.strip()] = v.strip()
                for k in ("padding", "background", "border-radius", "border",
                         "color", "font-size", "font-family"):
                    style_dict.pop(k, None)
                style_dict["background"] = "transparent"
                style_dict["padding"] = "0"
                style_dict["border-radius"] = "0"
                style_dict["border"] = "0"
                style_dict["font-size"] = "13px"
                style_dict["font-family"] = mono_stack
                style_dict["color"] = c["code_fg"]
                code["style"] = "; ".join(f"{k}: {v}" for k, v in style_dict.items())
                code["data-darkmode-color"] = c["dm_code_fg"]

            # Pre style: code background + padding + monospace, but no
            # border-radius (the outer card provides the rounded corners
            # via ``overflow:hidden``). ``white-space:pre`` (NOT pre-wrap)
            # so code indentation is preserved exactly as written; long
            # lines overflow horizontally (overflow-x:auto) instead of
            # being mangled.
            pre["style"] = (
                f"margin:0;padding:12px 16px;background:{c['code_bg']};"
                f"font-family:{mono_stack};font-size:13px;line-height:1.7;"
                f"color:{c['code_fg']};border-radius:0;white-space:pre;"
                f"word-wrap:normal;overflow-x:auto;border:0;"
            )
            pre["data-darkmode-color"] = c["dm_code_fg"]
            pre["data-darkmode-bgcolor"] = "transparent"

            # Card shell — a single <section> with TWO direct children: a
            # <p> header (mac dots + language label) and a <pre> body.
            # We deliberately avoid wrapping the pre in a body <p>, because
            # WeChat's editor splits nested <section><p><p><pre> chains
            # into separate visual blocks; a flat <section><p><pre> is
            # what WeChat keeps as one logical code card.
            card = soup.new_tag("section")
            card["style"] = (
                f"border:1px solid {c['border']};border-radius:8px;"
                f"overflow:hidden;margin:1.6em 0;background:{c['code_bg']};"
            )
            card["data-darkmode-bgcolor"] = c["dm_code_bg"]
            card.append(header)
            card.append(pre)
            div.replace_with(card)

        return str(soup)

    def _apply_github_code_highlight(self, html: str) -> str:
        soup = BeautifulSoup(html, "html.parser")
        is_dark = bool(soup.find("pre", {"data-darkmode-bgcolor": True}))
        color_map = self._GITHUB_CODE_HIGHLIGHT_DARK if is_dark else self._GITHUB_CODE_HIGHLIGHT

        for code_block in soup.find_all("code"):
            if code_block.parent and code_block.parent.name == "pre":
                for span in code_block.find_all("span"):
                    style = span.get("style", "")
                    if "color:" not in style and "color :" not in style:
                        continue
                    m = re.search(r"color\s*:\s*([^;]+)", style)
                    if not m:
                        continue
                    pyg_color = m.group(1).strip().lower()
                    # Normalize 3-digit hex to 6-digit (#00f -> #0000ff)
                    if re.match(r"^#[0-9a-f]{3}$", pyg_color):
                        pyg_color = "#" + "".join(c * 2 for c in pyg_color[1:])
                    gh_color = color_map.get(pyg_color)
                    if gh_color:
                        new_style = re.sub(
                            r"color\s*:\s*[^;]+",
                            f"color: {gh_color}",
                            style,
                        )
                        span["style"] = new_style
                        if is_dark:
                            span["data-darkmode-color"] = gh_color
        return str(soup)

    def _process_images(self, html: str) -> tuple[str, list[str]]:
        """Extract image references and ensure responsive styling."""
        soup = BeautifulSoup(html, "html.parser")
        images = []
        for img in soup.find_all("img"):
            src = img.get("src", "")
            if src:
                images.append(src)
            # Ensure responsive image styles (skip images that already carry
            # explicit sizing, e.g. formula images from render_formulas.py)
            existing = img.get("style", "")
            if "max-width" not in existing and "height" not in existing:
                additions = "max-width: 100%; height: auto; display: block; margin: 24px auto"
                img["style"] = f"{existing}; {additions}" if existing else additions
        return str(soup), images

    def _apply_inline_styles(self, html: str) -> str:
        """Apply theme CSS rules as inline styles on matching elements.

        Special handling:
        - ``pre code`` selector is allowed to **override** the cosmetic
          properties (``padding``, ``background``, ``border-radius``,
          ``border``, ``color``, ``font-size``, ``font-family``) that the
          bare ``code`` selector would otherwise paint onto block-code
          embedded ``<code>`` tokens. Without this, a tech-pro / linear
          etc. theme would render every code block as a row of sticker-like
          tokens with padding and a rounded background — visually broken.
        - Formula ``<img>`` keep the precise sizing the renderer emitted
          (``display:inline-block``/``display:block``, ``height``, vertical
          baseline alignment, ``max-width``); the bare ``img`` selector is
          not allowed to override those.
        """
        soup = BeautifulSoup(html, "html.parser")

        # Properties that the ``pre code`` selector can override on the
        # bare ``code`` selector — i.e. those the theme uses to make inline
        # ``<code>`` look like highlighted chips. When ``pre code`` fires,
        # the bare-chips look must be cleared on block-code embeds.
        _PRE_CODE_OVERRIDE = {
            "padding", "background", "border-radius", "border",
            "color", "font-size", "font-family",
        }

        # First pass: apply selectors in declared order, but remember which
        # elements a later selector touched so the bare ``code`` selector's
        # cosmetic props can be cleared afterwards.
        pre_code_touched: set[int] = set()
        for selector, styles in self._css_rules.items():
            if selector.strip() == "body":
                continue
            try:
                elements = soup.select(selector)
            except Exception:
                continue
            for elem in elements:
                # ``pre code`` wins over a prior ``code`` for these properties
                if selector == "pre code":
                    pre_code_touched.add(id(elem))
                    existing = elem.get("style", "")
                    style_dict = {}
                    if existing:
                        for item in existing.split(";"):
                            if ":" in item:
                                k, v = item.split(":", 1)
                                style_dict[k.strip()] = v.strip()
                    # Strip chip-cosmetic props, then apply ``pre code`` fully.
                    for k in _PRE_CODE_OVERRIDE:
                        style_dict.pop(k, None)
                    for prop, val in styles.items():
                        style_dict[prop] = val
                    elem["style"] = "; ".join(f"{k}: {v}" for k, v in style_dict.items())
                    continue

                existing = elem.get("style", "")
                style_dict = {}
                if existing:
                    for item in existing.split(";"):
                        if ":" in item:
                            key, val = item.split(":", 1)
                            style_dict[key.strip()] = val.strip()

                for prop, val in styles.items():
                    if prop not in style_dict:
                        style_dict[prop] = val

                # Formula images (from render_formulas.py) carry explicit
                # sizing and must stay in the text flow. The renderer set
                # ``height:20px;width:auto`` for inline (absolute pixels —
                # not em, because WeChat ignores em on <img>), or
                # ``display:block;max-width:96%`` for block math. We KEEP
                # those, or the theme's generic ``img`` rule will overwrite
                # them and break layout. Block formulas are identified by
                # the explicit ``display:block`` their renderer set.
                #
                # ``border:0`` must be enforced here too: WeChat's editor
                # auto-adds a gray border to every <img>, and a bordered
                # formula image looks like a UI sticker, not math.
                if elem.name == "img":
                    norm = existing.replace(" ", "")
                    is_block_formula = "display:block" in norm
                    has_height = "height:" in norm
                    if has_height and not is_block_formula:
                        # Inline formula: keep the renderer's text-flow
                        # values (display:inline, fixed-px height, small
                        # horizontal margin, vertical-align). Drop the
                        # rounded corners the theme adds to every <img>.
                        style_dict["display"] = "inline"
                        style_dict["height"] = "20px"
                        style_dict["width"] = "auto"
                        style_dict["vertical-align"] = "-3px"
                        style_dict["margin"] = "0 3px 0 0"
                        style_dict["border"] = "0"
                        style_dict.pop("border-radius", None)
                    elif is_block_formula:
                        # Block formula: keep the renderer's
                        # display/margin, drop rounded corners, kill the
                        # border WeChat auto-adds.
                        style_dict["display"] = "block"
                        style_dict["margin"] = "1.2em auto"
                        style_dict["max-width"] = "96%"
                        style_dict["width"] = "auto"
                        style_dict["height"] = "auto"
                        style_dict["border"] = "0"
                        style_dict.pop("border-radius", None)

                elem["style"] = "; ".join(f"{k}: {v}" for k, v in style_dict.items())

        # Second pass: drop the chip-cosmetic props from any ``<code>``
        # inside a ``<pre>`` that ``pre code`` may have left in the dict
        # because the prop was absent in the rule (defensive: clears any
        # leftover ``background``/``padding``/``border-radius`` from the
        # ``code`` pass).
        for code in soup.find_all("code"):
            parent = code.parent
            if not parent or parent.name != "pre":
                continue
            style = code.get("style", "")
            if not style:
                continue
            new_items = []
            for item in style.split(";"):
                if ":" not in item:
                    continue
                k = item.split(":", 1)[0].strip()
                if k in _PRE_CODE_OVERRIDE:
                    continue
                new_items.append(item)
            new_style = "; ".join(new_items).strip("; ")
            if new_style:
                code["style"] = new_style
            else:
                del code["style"]

        return str(soup)

    def _apply_wechat_fixes(self, html: str) -> str:
        """
        Apply WeChat-specific compatibility fixes:
        1. Force explicit color on every <p> tag
        2. Ensure code blocks preserve whitespace
        """
        soup = BeautifulSoup(html, "html.parser")
        text_color = self._theme.colors.get("text", "#333333")

        # Fix 1: Ensure all <p> tags have explicit color
        for p in soup.find_all("p"):
            style = p.get("style", "")
            if "color" not in style:
                p["style"] = f"{style}; color: {text_color}" if style else f"color: {text_color}"

        # Fix 2: Ensure <pre> has whitespace preservation
        for pre in soup.find_all("pre"):
            style = pre.get("style", "")
            if "white-space" not in style:
                pre["style"] = f"{style}; white-space: pre-wrap; word-wrap: break-word" if style else "white-space: pre-wrap; word-wrap: break-word"

        return str(soup)

    def _strip_unsupported_tags(self, html: str) -> str:
        """Convert <div>→<section> and drop class= from the published fragment.

        WeChat rewrites ``<div>`` and strips ``class`` attributes on paste, so
        any such markup in the fragment would silently lose its styling. We
        already emit inline styles everywhere, so renaming to ``<section>`` and
        deleting ``class`` is visually lossless while keeping the fragment
        within WeChat's allowed tag/attribute set.
        """
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup.find_all("div"):
            tag.name = "section"
        for tag in soup.find_all(True):
            if tag.has_attr("class"):
                del tag["class"]
        return str(soup)

    # -- tech-enhance inline code / param tables --

    def _enhance_inline_code_categories(self, html: str) -> str:
        """Color-classify inline <code> tokens for tech articles.

        Adds a distinguishing color for register, function, number,
        env/param tokens when the inner text matches a known pattern.
        The base <code> style is preserved; only `color` is overridden
        per category. Used only in tech mode to reduce visual monotony
        without resorting to syntax-highlight libraries.
        """
        import re as _re

        colors = self._theme.colors
        cat_colors = {
            "register": colors.get("code_reg", "#b45309"),
            "function": colors.get("code_fn",  "#0891b2"),
            "number":   colors.get("code_color", "#0f3a6e"),
            "param":    colors.get("code_param", "#6d28d9"),
        }

        compiled = {cat: _re.compile(pat) for cat, pat in self._TECH_CODE_CATEGORIES.items()}

        soup = BeautifulSoup(html, "html.parser")
        for code in soup.find_all("code"):
            # Skip inline <code> inside <pre> — those are block code
            if code.parent and code.parent.name == "pre":
                continue
            text = code.get_text().strip()
            if not text or " " in text:
                continue
            for cat, rx in compiled.items():
                if rx.match(text):
                    existing = code.get("style", "")
                    if "color:" in existing or "color :" in existing:
                        # override existing color
                        existing = _re.sub(r"color\s*:\s*[^;]+;?", "", existing)
                    code["style"] = f"{existing}; color: {cat_colors[cat]}".strip("; ")
                    break
        return str(soup)

    def _enhance_param_tables(self, html: str) -> str:
        """Mark parameter tables so the theme can style them distinctly.

        Detects tables whose header row matches common parameter table
        signatures (参数 / Parameter / Flag / 选项 / Field / 字段 / Name /
        类型 / Type / Default / 默认值). Adds `data-tablekind="params"`
        to the <table> and a class-style data attribute so the theme's
        CSS (tech-pro.yaml) can give the first column monospace + accent
        color without changing default table CSS for every theme.
        """
        import re as _re

        param_header_keywords = {
            "参数", "parameter", "param", "flag", "选项", "option",
            "字段", "field", "name", "类型", "type", "默认值", "default",
            "含义", "description", "说明", "寄存器", "register",
        }

        soup = BeautifulSoup(html, "html.parser")
        for table in soup.find_all("table"):
            ths = table.find_all("th")
            if not ths:
                continue
            header_texts = {th.get_text().strip().lower() for th in ths}
            if any(kw in header_texts for kw in param_header_keywords):
                table["data-tablekind"] = "params"
                # Ensure first column cells get monospace + accent in tech mode
                for row in table.find_all("tr"):
                    cells = row.find_all("td")
                    if cells:
                        first = cells[0]
                        existing = first.get("style", "")
                        if "font-family" not in existing:
                            first["style"] = (
                                existing +
                                ("; " if existing else "") +
                                "font-family: 'SFMono-Regular', Consolas, "
                                "'Liberation Mono', Menlo, Courier, monospace; "
                                "font-size: 13px; color: #0f3a6e; "
                                "white-space: nowrap; font-weight: 600"
                            ).strip("; ")
        return str(soup)

    def _fix_cjk_spacing(self, text: str) -> str:
        """Auto-insert thin space between CJK and Latin/digit characters.

        WeChat renders CJK-Latin without spacing, making mixed text hard to read.
        This inserts a thin space (U+200A) at CJK↔Latin boundaries.
        Runs on raw Markdown before parsing, skipping code blocks, links, and
        **math regions** (``$...$`` / ``$$...$$``) — a thin space inside a
        formula would break downstream MathJax/KaTeX delimiters.
        """
        # CJK unicode ranges
        cjk = r'[\u4e00-\u9fff\u3400-\u4dbf\u3000-\u303f\uff00-\uffef]'
        latin = r'[A-Za-z0-9]'

        # Protect math regions so the spacing rules never touch their contents.
        math_store: list[str] = []

        def _stash(m: re.Match) -> str:
            math_store.append(m.group(0))
            return f"\x00MATH{len(math_store) - 1}\x00"

        protected = re.sub(r"\$\$.+?\$\$|\$[^$\n]+?\$", _stash, text, flags=re.DOTALL)

        lines = protected.split('\n')
        result = []
        in_code_block = False

        for line in lines:
            if line.strip().startswith('```'):
                in_code_block = not in_code_block
                result.append(line)
                continue
            if in_code_block:
                result.append(line)
                continue

            # CJK followed by Latin
            line = re.sub(f'({cjk})({latin})', r'\1 \2', line)
            # Latin followed by CJK
            line = re.sub(f'({latin})({cjk})', r'\1 \2', line)
            result.append(line)

        out = '\n'.join(result)
        # Restore math regions verbatim.
        out = re.sub(r"\x00MATH(\d+)\x00",
                     lambda m: math_store[int(m.group(1))], out)
        return out

    def _fix_cjk_bold_punctuation(self, html: str) -> str:
        """Move Chinese punctuation outside bold/strong tags.

        WeChat renders bold CJK punctuation with ugly spacing.
        Move trailing punctuation (，。！？；：、) outside </strong>.
        """
        # Match: <strong>内容+中文标点</strong> → <strong>内容</strong>标点
        pattern = r'(<strong>)(.*?)([，。！？；：、]+)(</strong>)'
        return re.sub(pattern, r'\1\2\4\3', html)

    def _convert_lists_to_sections(self, html: str) -> str:
        """Convert <ul>/<ol> to styled <section> elements.

        WeChat's native list rendering is unreliable (inconsistent bullet
        style, broken indentation on some devices). Using section+span
        for bullets/numbers gives full control over appearance.
        """
        soup = BeautifulSoup(html, "html.parser")
        text_color = self._theme.colors.get("text", "#333333")
        primary = self._theme.colors.get("primary", "#2563eb")

        for ul in soup.find_all("ul"):
            section = soup.new_tag("section")
            for li in ul.find_all("li", recursive=False):
                item = soup.new_tag("section", style=f"display: flex; align-items: flex-start; margin-bottom: 8px; color: {text_color}")
                bullet = soup.new_tag("span", style=f"color: {primary}; margin-right: 8px; flex-shrink: 0; font-size: 18px; line-height: 1.6")
                bullet.string = "•"
                content = soup.new_tag("span", style="flex: 1")
                for child in list(li.children):
                    content.append(child.extract() if hasattr(child, 'extract') else child)
                item.append(bullet)
                item.append(content)
                section.append(item)
            ul.replace_with(section)

        for idx, ol in enumerate(soup.find_all("ol")):
            section = soup.new_tag("section")
            for num, li in enumerate(ol.find_all("li", recursive=False), 1):
                item = soup.new_tag("section", style=f"display: flex; align-items: flex-start; margin-bottom: 8px; color: {text_color}")
                number = soup.new_tag("span", style=f"color: {primary}; margin-right: 8px; flex-shrink: 0; font-weight: 700; line-height: 1.8")
                number.string = f"{num}."
                content = soup.new_tag("span", style="flex: 1")
                for child in list(li.children):
                    content.append(child.extract() if hasattr(child, 'extract') else child)
                item.append(number)
                item.append(content)
                section.append(item)
            ol.replace_with(section)

        return str(soup)

    # -- External link → footnote conversion --

    def _convert_links_to_footnotes(self, html: str) -> str:
        """Convert external <a> links to superscript footnote numbers.

        WeChat blocks external links — readers see dead text. This converts
        each external link to a superscript number with the URL collected
        into a reference list appended at the end.
        """
        soup = BeautifulSoup(html, "html.parser")
        footnotes = []
        counter = 0
        primary = self._theme.colors.get("primary", "#2563eb")

        for a in soup.find_all("a"):
            href = a.get("href", "")
            if not href or href.startswith("#"):
                continue  # skip anchors

            counter += 1
            text = a.get_text()
            footnotes.append((counter, text, href))

            # Replace <a> with text + superscript number
            sup = soup.new_tag("sup")
            sup_link = soup.new_tag("span", style=f"color: {primary}; font-size: 12px")
            sup_link.string = f"[{counter}]"
            sup.append(sup_link)
            a.replace_with(text, sup)

        if footnotes:
            # Append reference section
            hr = soup.new_tag("hr", style="border: none; border-top: 1px solid #e5e5e5; margin: 32px 0 16px")
            soup.append(hr)
            ref_title = soup.new_tag("p", style="font-size: 13px; color: #999999; margin-bottom: 8px; font-weight: 700")
            ref_title.string = "参考链接"
            soup.append(ref_title)
            for num, text, href in footnotes:
                ref = soup.new_tag("p", style="font-size: 12px; color: #999999; margin: 2px 0; word-break: break-all")
                ref.string = f"[{num}] {text}: {href}"
                soup.append(ref)

        return str(soup)

    # -- Dark mode --

    def _inject_darkmode(self, html: str) -> str:
        """Inject data-darkmode-* attributes for WeChat dark mode.

        WeChat auto-inverts colors in dark mode, which often breaks
        designed color schemes. Explicit darkmode attributes tell WeChat
        exactly what colors to use instead of guessing.
        """
        darkmode = self._theme.colors.get("darkmode", {})
        if not darkmode:
            return html

        soup = BeautifulSoup(html, "html.parser")
        dm_text = darkmode.get("text", "#c8c8c8")
        dm_bg = darkmode.get("background", "#1e1e1e")
        dm_primary = darkmode.get("primary", "#6aadff")

        # Body-level elements (p, li, section, span)
        for tag_name in ("p", "span", "section"):
            for elem in soup.find_all(tag_name):
                style = elem.get("style", "")
                # Only set if element has a color
                if "color" in style:
                    elem["data-darkmode-color"] = dm_text
                    elem["data-darkmode-bgcolor"] = "transparent"

        # Headings
        dm_heading = darkmode.get("text", "#e0e0e0")
        for tag_name in ("h1", "h2", "h3", "h4"):
            for elem in soup.find_all(tag_name):
                elem["data-darkmode-color"] = dm_heading
                elem["data-darkmode-bgcolor"] = "transparent"

        # Code blocks
        dm_code_bg = darkmode.get("code_bg", "#2d2d2d")
        dm_code_color = darkmode.get("code_color", "#d4d4d4")
        for pre in soup.find_all("pre"):
            pre["data-darkmode-bgcolor"] = dm_code_bg
            pre["data-darkmode-color"] = dm_code_color
        for code in soup.find_all("code"):
            code["data-darkmode-color"] = dm_code_color

        # Blockquotes
        dm_quote_bg = darkmode.get("quote_bg", "#2a2a2a")
        for bq in soup.find_all("blockquote"):
            bq["data-darkmode-bgcolor"] = dm_quote_bg
            bq["data-darkmode-color"] = dm_text

        # Strong/em with primary color
        for strong in soup.find_all("strong"):
            strong["data-darkmode-color"] = dm_primary

        return str(soup)

    # -- Container block syntax --

    def _preprocess_containers(self, text: str) -> str:
        """Pre-process :::container blocks into styled HTML before Markdown parsing.

        Supports:
          :::dialogue   — chat bubble layout
          :::timeline   — vertical timeline with dots
          :::callout    — Obsidian-style callout (tip/warning/info/danger)
          :::quote      — styled pull quote
        """
        text = self._process_dialogue(text)
        text = self._process_timeline(text)
        text = self._process_callout(text)
        text = self._process_quote_block(text)
        return text

    def _process_dialogue(self, text: str) -> str:
        """Convert :::dialogue blocks to chat bubble HTML."""
        primary = self._theme.colors.get("primary", "#2563eb")

        def replace_dialogue(match):
            content = match.group(1).strip()
            bubbles = []
            for line in content.split('\n'):
                line = line.strip()
                if not line:
                    continue
                if line.startswith('> '):
                    # Right-aligned (reply) bubble
                    msg = line[2:].strip()
                    bubbles.append(f'<section style="display: flex; justify-content: flex-end; margin-bottom: 12px">'
                                   f'<section style="background: {primary}; color: white; padding: 10px 14px; border-radius: 12px 12px 2px 12px; max-width: 80%; font-size: 15px; line-height: 1.6">{msg}</section></section>')
                else:
                    # Left-aligned bubble
                    bubbles.append(f'<section style="display: flex; justify-content: flex-start; margin-bottom: 12px">'
                                   f'<section style="background: #f3f4f6; color: #333; padding: 10px 14px; border-radius: 12px 12px 12px 2px; max-width: 80%; font-size: 15px; line-height: 1.6">{line}</section></section>')
            return '\n'.join(bubbles)

        return re.sub(r':::dialogue\n(.*?)\n:::', replace_dialogue, text, flags=re.DOTALL)

    def _process_timeline(self, text: str) -> str:
        """Convert :::timeline blocks to vertical timeline HTML."""
        primary = self._theme.colors.get("primary", "#2563eb")

        def replace_timeline(match):
            content = match.group(1).strip()
            items = []
            for line in content.split('\n'):
                line = line.strip()
                if not line:
                    continue
                # Format: "**title** description" or just "description"
                items.append(
                    f'<section style="display: flex; margin-bottom: 16px">'
                    f'<section style="flex-shrink: 0; width: 12px; display: flex; flex-direction: column; align-items: center">'
                    f'<section style="width: 10px; height: 10px; border-radius: 50%; background: {primary}; margin-top: 6px"></section>'
                    f'<section style="width: 2px; flex: 1; background: #e5e7eb; margin-top: 4px"></section>'
                    f'</section>'
                    f'<section style="flex: 1; padding-left: 12px; padding-bottom: 8px; font-size: 15px; line-height: 1.7">{line}</section>'
                    f'</section>'
                )
            return '\n'.join(items)

        return re.sub(r':::timeline\n(.*?)\n:::', replace_timeline, text, flags=re.DOTALL)

    def _process_callout(self, text: str) -> str:
        """Convert :::callout blocks to styled callout boxes.

        Syntax: :::callout tip/warning/info/danger
        """
        colors_map = {
            "tip": ("#059669", "#ecfdf5", "💡"),
            "warning": ("#d97706", "#fffbeb", "⚠️"),
            "info": ("#2563eb", "#eff6ff", "ℹ️"),
            "danger": ("#dc2626", "#fef2f2", "🚨"),
        }

        def replace_callout(match):
            ctype = match.group(1).strip().lower()
            content = match.group(2).strip()
            color, bg, icon = colors_map.get(ctype, colors_map["info"])
            return (f'<section style="background: {bg}; border-left: 4px solid {color}; '
                    f'padding: 14px 16px; border-radius: 4px; margin: 16px 0; font-size: 15px; line-height: 1.7">'
                    f'<section style="font-weight: 700; color: {color}; margin-bottom: 6px">{icon} {ctype.upper()}</section>'
                    f'{content}</section>')

        return re.sub(r':::callout\s+(\w+)\n(.*?)\n:::', replace_callout, text, flags=re.DOTALL)

    def _process_quote_block(self, text: str) -> str:
        """Convert :::quote blocks to styled pull quotes."""
        primary = self._theme.colors.get("primary", "#2563eb")

        def replace_quote(match):
            content = match.group(1).strip()
            return (f'<section style="margin: 24px 0; padding: 20px 24px; border-left: 4px solid {primary}; '
                    f'background: linear-gradient(135deg, #f8f9fa 0%, #ffffff 100%); border-radius: 0 8px 8px 0">'
                    f'<section style="font-size: 18px; line-height: 1.8; color: #333; font-style: italic">'
                    f'"{content}"</section></section>')

        return re.sub(r':::quote\n(.*?)\n:::', replace_quote, text, flags=re.DOTALL)

    # -- Digest generation --

    def _generate_digest(self, html: str, max_bytes: int = 120) -> str:
        """Generate a digest that fits within WeChat's byte limit (120 bytes UTF-8)."""
        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text(separator=" ", strip=True)
        # Drop raw LaTeX ($...$ / $$...$$) so the summary reads as prose.
        text = re.sub(r"\$\$.+?\$\$|\$[^$\n]+?\$", "", text, flags=re.DOTALL)
        text = re.sub(r"\s+", " ", text).strip()

        # Truncate to fit within max_bytes (UTF-8)
        ellipsis = "..."
        ellipsis_bytes = len(ellipsis.encode("utf-8"))
        target_bytes = max_bytes - ellipsis_bytes

        encoded = text.encode("utf-8")
        if len(encoded) <= max_bytes:
            return text

        # Truncate at valid UTF-8 boundary
        truncated = encoded[:target_bytes].decode("utf-8", errors="ignore").rstrip()
        return truncated + ellipsis


def _inline_mermaid_js() -> str:
    """Return an inline <script> tag for mermaid.js using a base64 data URL.

    Falls back to a public CDN if the bundled copy is missing.
    """
    bundled = Path(__file__).parent / "assets" / "mermaid.min.js"
    if bundled.exists():
        b64 = base64.b64encode(bundled.read_bytes()).decode("ascii")
        return f'<script src="data:application/javascript;base64,{b64}"></script>'
    return '<script src="https://cdn.jsdelivr.net/npm/mermaid@10.9.1/dist/mermaid.min.js"></script>'


_MERMAID_SCRIPT = """
    <!-- Mermaid: render fenced ```mermaid blocks as real diagrams (preview only) -->
    __MERMAID_JS_TAG__
    <script>
      document.addEventListener('DOMContentLoaded', function () {
        if (typeof mermaid === 'undefined') { return; }
        mermaid.initialize({ startOnLoad: false, theme: 'default', securityLevel: 'loose' });
        var pres = document.querySelectorAll('pre[data-lang="mermaid"]');
        if (!pres.length) { return; }
        pres.forEach(function (pre) {
          var section = pre.parentNode;
          var code = pre.querySelector('code');
          var src = code ? code.textContent : pre.textContent;
          var div = document.createElement('div');
          div.className = 'mermaid';
          div.style.textAlign = 'center';
          div.style.margin = '1.6em 0';
          div.textContent = src;
          section.parentNode.replaceChild(div, section);
        });
        try {
          mermaid.run({ querySelector: '.mermaid' });
        } catch (e) {
          console.error('Mermaid render failed:', e);
        }
      });
    </script>
"""


def _render_mermaid_to_svg_dataurl(src: str):
    """Render a mermaid source string into an inline ``data:image/svg+xml`` URL.

    Uses mermaid.ink (network). Returns None on any failure so the caller can
    fall back to the client-side inline script (which some preview panes run).
    """
    try:
        b64 = base64.urlsafe_b64encode(src.strip().encode("utf-8")).decode("ascii").rstrip("=")
        url = f"https://mermaid.ink/svg/{b64}?bgColor=white&theme=default"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            svg = resp.read().decode("utf-8", "replace")
        if not svg.lstrip().startswith("<svg"):
            return None
        sb64 = base64.b64encode(svg.encode("utf-8")).decode("ascii")
        return f"data:image/svg+xml;base64,{sb64}"
    except Exception:
        return None


def _inline_mermaid_images(body_html: str) -> str:
    """Replace ``pre[data-lang="mermaid"]`` blocks with rendered <img> (preview).

    The preview pane may not execute <script>, so we server-side render each
    mermaid diagram to an inline SVG image. Blocks that fail to render keep
    their original <pre> for the client-side fallback.
    """
    soup = BeautifulSoup(body_html, "html.parser")
    changed = False
    for pre in soup.find_all("pre", {"data-lang": "mermaid"}):
        code = pre.find("code")
        src = code.get_text() if code else pre.get_text()
        dataurl = _render_mermaid_to_svg_dataurl(src)
        if not dataurl:
            continue
        img = soup.new_tag("img")
        img["src"] = dataurl
        img["alt"] = "mermaid 流程图"
        img["style"] = "max-width:100%;height:auto;display:block;margin:1.4em auto;"
        pre.replace_with(img)
        changed = True
    return str(soup) if changed else body_html


def preview_html(body_html: str, theme: Theme, mathjax: bool = False, mermaid: bool = True) -> str:
    """
    Wrap body content in a full HTML document for browser preview.
    This is only for local preview — NOT for WeChat publishing.

    ``mathjax``: when True (latex formula mode), inject MathJax so raw
    ``$...$`` / ``$$...$$`` render as real math in the browser preview. This
    makes the local preview show formulas naturally; the WeChat fragment
    itself still carries the raw LaTeX for the downstream renderer.

    ``mermaid``: when True (default), render fenced ```mermaid code blocks
    as real flowcharts in the browser preview. The WeChat fragment keeps the
    raw mermaid source as a fenced code block.
    """
    mathjax_script = ""
    if mathjax:
        mathjax_script = (
            "\n    <!-- MathJax: render raw $...$ / $$...$$ as math (preview only) -->\n"
            "    <script>\n"
            "      window.MathJax = {\n"
            "        tex: { inlineMath: [['$', '$'], ['\\\\(', '\\\\)']],\n"
            "              displayMath: [['$$', '$$'], ['\\\\[', '\\\\]']] },\n"
            "        svg: { fontCache: 'global' }\n"
            "      };\n"
            "    </script>\n"
            "    <script id=\"MathJax-script\" async\n"
            "      src=\"https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-svg.js\"></script>\n"
        )
    mermaid_script = _MERMAID_SCRIPT.replace("__MERMAID_JS_TAG__", _inline_mermaid_js()) if mermaid else ""
    # Server-side render mermaid blocks to inline SVG so the preview shows the
    # diagram even when the preview pane does not execute <script>.
    try:
        body_html = _inline_mermaid_images(body_html)
    except Exception:
        pass
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Preview</title>
    <style>
{theme.base_css}
    </style>{mathjax_script}{mermaid_script}
</head>
<body>
    {body_html}
</body>
</html>"""
