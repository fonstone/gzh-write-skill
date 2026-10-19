#!/usr/bin/env python3
"""Deterministic theme generation for GzhWrite.

The LLM decides *taste* (which preset, which primary color); this module
decides *structure* — it expands those two inputs into a complete theme
YAML (base_css + colors + derived dark mode) that the existing theme
engine can load and the converter can inline. Contrast checking keeps a
bad primary color from shipping an unreadable theme.

The generated CSS intentionally uses simple selectors only (plus
``pre code``, which the converter special-cases) and ``var(--x)`` color
references resolved by ``theme.py``.

Usage (library):
    from theme_gen import generate_theme_yaml, validate_theme
Usage (CLI):
    python3 toolkit/cli.py theme-init <name> --primary "#0f766e" --style tech
"""

from __future__ import annotations

import colorsys
import re

import yaml

_HEX_RE = re.compile(r"^#?(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")

FONT_FAMILY = (
    '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", '
    'Arial, "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif'
)
MONO_FAMILY = '"SFMono-Regular", Consolas, "Liberation Mono", Menlo, Courier, monospace'

PRESETS = {
    "minimal": {
        "h2_css": "border-bottom: 2px solid var(--primary); padding-bottom: 8px;",
        "radius": "4px", "line_height": "1.8", "letter_spacing": "0px",
        "p_margin": "12px 0", "h1_size": "26px", "h2_size": "22px",
        "h3_size": "18px", "bq_width": "3px",
    },
    "tech": {
        "h2_css": "border-left: 4px solid var(--primary); padding-left: 12px;",
        "radius": "6px", "line_height": "1.75", "letter_spacing": "0px",
        "p_margin": "12px 0", "h1_size": "26px", "h2_size": "21px",
        "h3_size": "17px", "bq_width": "3px",
    },
    "warm": {
        "h2_css": ("background: var(--quote-bg); padding: 10px 14px; "
                   "border-radius: var(--border-radius);"),
        "radius": "10px", "line_height": "1.9", "letter_spacing": "0.2px",
        "p_margin": "14px 0", "h1_size": "25px", "h2_size": "21px",
        "h3_size": "18px", "bq_width": "4px",
    },
    "editorial": {
        "h2_css": ("border-bottom: 1px solid var(--text_light); "
                   "padding-bottom: 6px; letter-spacing: 0.5px;"),
        "radius": "2px", "line_height": "1.85", "letter_spacing": "0.3px",
        "p_margin": "14px 0", "h1_size": "27px", "h2_size": "22px",
        "h3_size": "18px", "bq_width": "3px",
    },
}


# --- color helpers -----------------------------------------------------------

def _normalize_hex(value: str) -> str:
    if not isinstance(value, str) or not _HEX_RE.match(value.strip()):
        raise ValueError(f"invalid hex color: {value!r}")
    s = value.strip().lstrip("#").lower()
    if len(s) == 3:
        s = "".join(c * 2 for c in s)
    return "#" + s


def _rgb(hex_color: str) -> tuple[int, int, int]:
    s = _normalize_hex(hex_color).lstrip("#")
    return int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)


def _lightness(hex_color: str) -> float:
    r, g, b = (c / 255.0 for c in _rgb(hex_color))
    _, l, _ = colorsys.rgb_to_hls(r, g, b)
    return l


def _adjust_lightness(hex_color: str, target_l: float) -> str:
    r, g, b = (c / 255.0 for c in _rgb(hex_color))
    h, _l, sat = colorsys.rgb_to_hls(r, g, b)
    nr, ng, nb = colorsys.hls_to_rgb(h, max(0.0, min(1.0, target_l)), sat)
    return "#{:02x}{:02x}{:02x}".format(int(nr * 255), int(ng * 255), int(nb * 255))


def _mix_with_white(hex_color: str, keep: float) -> str:
    """Blend toward white; keep=0.08 → a very light tint of the color."""
    r, g, b = _rgb(hex_color)
    nr = round(r * keep + 255 * (1 - keep))
    ng = round(g * keep + 255 * (1 - keep))
    nb = round(b * keep + 255 * (1 - keep))
    return "#{:02x}{:02x}{:02x}".format(nr, ng, nb)


def _luminance(hex_color: str) -> float:
    def _chan(c: int) -> float:
        c = c / 255.0
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = _rgb(hex_color)
    return 0.2126 * _chan(r) + 0.7152 * _chan(g) + 0.0722 * _chan(b)


def contrast_ratio(a: str, b: str) -> float:
    """WCAG relative contrast ratio between two colors."""
    la, lb = _luminance(a), _luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def _derive_darkmode(colors: dict) -> dict:
    primary = colors.get("primary", "#2563eb")
    dm_primary = _adjust_lightness(primary, min(_lightness(primary) + 0.15, 0.85))
    return {
        "background": "#1e1e1e",
        "text": _adjust_lightness(colors.get("text", "#333333"), 0.80),
        "text_light": _adjust_lightness(colors.get("text_light", "#666666"), 0.60),
        "primary": dm_primary,
        "code_bg": "#2d2d2d",
        "code_color": "#d4d4d4",
        "quote_bg": "#252525",
        "quote_border": dm_primary,
    }


# --- generation --------------------------------------------------------------

def _base_css(preset: dict) -> str:
    return f"""body {{
  font-family: {FONT_FAMILY};
  font-size: 16px;
  line-height: {preset["line_height"]};
  color: var(--text);
  background: var(--background);
  max-width: 720px;
  margin: 0 auto;
  padding: 20px;
  word-wrap: break-word;
  letter-spacing: {preset["letter_spacing"]};
}}

h1 {{
  font-size: {preset["h1_size"]};
  font-weight: 700;
  color: var(--text);
  margin: 32px 0 16px 0;
  text-align: center;
  line-height: 1.4;
}}

h2 {{
  font-size: {preset["h2_size"]};
  font-weight: 700;
  color: var(--text);
  margin: 28px 0 14px 0;
  line-height: 1.4;
  {preset["h2_css"]}
}}

h3 {{
  font-size: {preset["h3_size"]};
  font-weight: 600;
  color: var(--text);
  margin: 24px 0 12px 0;
  line-height: 1.4;
}}

p {{
  font-size: 16px;
  line-height: {preset["line_height"]};
  color: var(--text);
  margin: {preset["p_margin"]};
}}

strong {{
  font-weight: 700;
  color: var(--primary);
}}

code {{
  font-family: {MONO_FAMILY};
  font-size: 14px;
  background: var(--code-bg);
  color: var(--code-color);
  padding: 2px 6px;
  border-radius: var(--border-radius);
}}

pre {{
  background: var(--code-bg);
  color: var(--code-color);
  padding: 16px;
  border-radius: var(--border-radius);
  overflow-x: auto;
  margin: 16px 0;
  line-height: 1.6;
}}

pre code {{
  font-family: {MONO_FAMILY};
  font-size: 14px;
  background: none;
  color: inherit;
  padding: 0;
  border-radius: 0;
}}

blockquote {{
  border-left: {preset["bq_width"]} solid var(--quote-border);
  background: var(--quote-bg);
  margin: 16px 0;
  padding: 12px 16px;
  border-radius: 0 var(--border-radius) var(--border-radius) 0;
  color: var(--text_light);
}}

blockquote p {{
  margin: 8px 0;
  color: var(--text_light);
}}

ul, ol {{
  padding-left: 24px;
  margin: 12px 0;
}}

li {{
  font-size: 16px;
  line-height: {preset["line_height"]};
  color: var(--text);
  margin: 6px 0;
}}

table {{
  width: 100%;
  border-collapse: collapse;
  margin: 16px 0;
  font-size: 15px;
}}

th {{
  background: var(--quote-bg);
  color: var(--text);
  font-weight: 600;
  padding: 10px 14px;
  text-align: left;
  border: 1px solid var(--quote-bg);
}}

td {{
  padding: 10px 14px;
  border: 1px solid var(--quote-bg);
  color: var(--text);
}}

img {{
  max-width: 100%;
  height: auto;
  display: block;
  margin: 24px auto;
  border-radius: var(--border-radius);
}}

a {{
  color: var(--primary);
  text-decoration: underline;
}}

hr {{
  border: none;
  border-top: 1px solid var(--quote-bg);
  margin: 24px 0;
}}
"""


def generate_theme_yaml(name: str, primary: str, style: str = "minimal",
                        description: str = "") -> str:
    """Expand (name, primary, style) into a complete theme YAML string."""
    if style not in PRESETS:
        raise ValueError(f"unknown style '{style}' (valid: {', '.join(PRESETS)})")
    if not name or not re.match(r"^[A-Za-z0-9_-]+$", name):
        raise ValueError(f"invalid theme name: {name!r} (use letters/digits/-/_)")
    primary = _normalize_hex(primary)
    preset = PRESETS[style]

    colors = {
        "primary": primary,
        "secondary": _adjust_lightness(primary, min(_lightness(primary) + 0.10, 0.90)),
        "text": "#333333",
        "text_light": "#666666",
        "background": "#ffffff",
        "code_bg": "#f6f8fa",
        "code_color": "#24292f",
        "quote_border": primary,
        "quote_bg": _mix_with_white(primary, 0.08),
        "border_radius": preset["radius"],
    }
    colors["darkmode"] = _derive_darkmode(colors)

    data = {
        "name": name,
        "description": description or f"{style} 风格自定义主题（主色 {primary}），由 theme-init 生成",
        "colors": colors,
        "base_css": _base_css(preset),
    }
    return yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=88)


# --- validation --------------------------------------------------------------

def validate_theme(text: str) -> dict:
    """Structural check + readability warnings. Never raises on bad input."""
    warnings: list[str] = []
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        return {"ok": False, "warnings": [f"YAML parse failed: {exc}"]}
    if not isinstance(data, dict):
        return {"ok": False, "warnings": ["theme must be a YAML mapping"]}
    for key in ("name", "description", "base_css", "colors"):
        if key not in data:
            return {"ok": False, "warnings": [f"missing required field '{key}'"]}

    colors = data.get("colors") or {}
    primary = colors.get("primary", "")
    background = colors.get("background", "#ffffff")
    text_color = colors.get("text", "#333333")
    try:
        ratio = contrast_ratio(primary, background)
        if ratio < 3.0:
            warnings.append(
                f"主色 {primary} 与背景对比度不足 3:1（当前 {ratio:.1f}:1）"
                "——标题装饰线与强调文字会看不清，建议加深主色"
            )
        body_ratio = contrast_ratio(text_color, background)
        if body_ratio < 4.5:
            warnings.append(
                f"正文色 {text_color} 与背景对比度不足 4.5:1（当前 {body_ratio:.1f}:1）"
            )
    except ValueError as exc:
        warnings.append(f"颜色无法解析对比度：{exc}")
    return {"ok": True, "warnings": warnings}
