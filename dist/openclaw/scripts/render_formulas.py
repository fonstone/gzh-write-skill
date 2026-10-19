#!/usr/bin/env python3
"""Render LaTeX-style math formulas in a markdown article to PNG images.

Scans ``$...$`` (inline) / ``$$...$$`` (block) blocks, validates syntax with
matplotlib mathtext, renders each to a tightly-cropped transparent PNG, and
replaces the formula with an image reference carrying a WeChat-safe inline
style.

Why px and not em: WeChat's editor ignores ``em`` units on ``<img>`` and
forces ``display:block`` on every image, so an em-sized formula would show
up at the PNG's natural size on its own line, mid-sentence. The renderer
therefore renders each PNG at a small target size (inline ≈ 11pt → about
20px tall) and emits an absolute-pixel style that browsers honour (local
preview, web view); WeChat falls back to the already-small natural size.

- **Inline** ``$E=mc^2$`` → ``height:20px;width:auto;vertical-align:-3px``
  keeps the formula in the text flow, on the text baseline; ``border:0``
  cancels WeChat's auto border on images.
- **Block** ``$$...$$`` → ``display:block;margin:1.2em auto;max-width:96%``
  centers display equations and caps pathologically wide ones.

The render metrics (``height_em`` / ``ascent_em`` / ``descent_em``) are
still computed and returned for reporting and validation, but are not
emitted as CSS (WeChat would ignore them).

The renderer uses the Computer Modern font (``mathtext.fontset='cm'``) for a
classic LaTeX look, in contrast to the default DejaVu which looks like
programmer's monospace. The PNG is cropped tightly with a few pixels of
breathing room, so a small symbol like ``x`` does not get blown up to a
screen-spanning block.

Usage:
    python3 render_formulas.py article.md
    python3 render_formulas.py article.md -o output/article-formulas/
    python3 render_formulas.py article.md --color "#1f2937" --block-scale 1.15

Idempotent: formulas already replaced with ``![公式 fN](...)`` images are
skipped. On syntax errors, returns a non-zero exit code and reports line
numbers so the caller can fix the source LaTeX and re-run.
"""

from __future__ import annotations

import argparse
import io
import os
import re
import sys
from pathlib import Path
from typing import Optional

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    Image = None

try:
    import matplotlib

    matplotlib.use("Agg")
    from matplotlib import font_manager as fm
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure
except ImportError:  # pragma: no cover - import fallback path
    matplotlib = None
    fm = None
    FigureCanvasAgg = None
    Figure = None

# Math text regex: $...$ (inline) or $$...$$ (block).
MATH_BLOCK_RE = re.compile(r"\$\$(.+?)\$\$|\$(.+?)\$", re.DOTALL)
RENDERED_ALT_RE = re.compile(r"!\[公式 f\d+\]\(")

# Short command aliases the mathtext *renderer* path
# (``get_text_width_height_descent(..., ismath=True)``) does not recognize —
# it only knows the canonical long forms, even though ``MathTextParser.parse``
# accepts both. Map the common ones so authors may write ``\le``/``\ge``.
# Negative lookahead avoids clobbering ``\left``/``\geqs`` etc.
_MATH_ALIASES = [
    (re.compile(r"\\le(?![a-zA-Z])"), r"\leq"),
    (re.compile(r"\\ge(?![a-zA-Z])"), r"\geq"),
]


def _normalize_math(s: str) -> str:
    """Rewrite short mathtext aliases to their canonical long forms."""
    for pat, rep in _MATH_ALIASES:
        s = pat.sub(lambda m: rep, s)
    return s


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def _configure_mathtext(fontset: str) -> None:
    """Set matplotlib mathtext fontset (called once before rendering)."""
    if matplotlib is None:
        return
    # rcParams update; ``fontset`` is 'cm' (Computer Modern) | 'stix' | 'custom' | 'dejavusans'
    matplotlib.rcParams["mathtext.fontset"] = fontset
    matplotlib.rcParams["mathtext.default"] = "regular"


def _measure(formula: str, fontsize: float, dpi: int) -> tuple[int, int, int]:
    """Measure a formula in mathtext mode.

    Returns ``(width, total_height, descent)`` in pixels. ``total_height`` =
    ascent + descent (bottom of descender → top of ascender); ``descent`` is
    the distance below the baseline. Used only as a fast pre-check / fallback;
    the actual PNG is cropped to the true ink bounding box (see
    ``render_formula``) so nothing is ever clipped.
    """
    fig = Figure(figsize=(0.01, 0.01), dpi=dpi)
    FigureCanvasAgg(fig)  # attach the Agg canvas so get_renderer() works
    prop = fm.FontProperties(size=fontsize)
    fig.text(0, 0, f"${formula}$", fontproperties=prop)  # auto math via $...$
    fig.canvas.draw()  # ensure layout
    renderer = fig.canvas.get_renderer()
    w, h, d = renderer.get_text_width_height_descent(formula, prop, ismath=True)
    fig.clear()
    return int(w), int(h), int(d)


def render_formula(
    formula: str,
    out_path: Path,
    fontsize: float = 16.0,
    dpi: int = 300,
    color: str = "#333333",
    fontset: str = "cm",
    pad_px: int = 6,
) -> dict:
    """Render a single LaTeX formula to a tightly-cropped transparent PNG.

    The image is cropped to the *true ink bounding box* of the rendered
    glyphs (not to a text-metrics rectangle), so nothing is ever cut off —
    tall fractions, deep descenders and wide sums all render completely.

    Baseline alignment: the math is placed with its baseline at the vertical
    centre of an oversized canvas, the exact baseline position is recovered
    from that placement, and the returned ``descent_em`` tells the caller how
    far the formula baseline sits above the cropped image's bottom edge. The
    caller sets ``vertical-align: -descent_em`` so the formula baseline lands
    exactly on the text baseline (proper typographic alignment, not a crude
    middle-align).

    Returns a dict with pixel measurements and the corresponding em values
    (so the caller can decide the exact CSS style).
    """
    if matplotlib is None:
        raise RuntimeError("matplotlib is not installed")
    if Image is None:
        raise RuntimeError("Pillow (PIL) is not installed")

    _configure_mathtext(fontset)

    inner = _normalize_math(formula.strip())
    safe_color = color or "#000000"
    em = fontsize * dpi / 72.0  # 1pt = D/72 px at dpi=D → 1em (body) in px

    # Oversized canvas so even large display equations never overflow it.
    fig = Figure(figsize=(6.0, 6.0), dpi=dpi)
    FigureCanvasAgg(fig)
    prop = fm.FontProperties(size=fontsize)
    # Place the baseline at the vertical centre of the canvas (va='baseline').
    baseline_frac = 0.5
    t = fig.text(
        0.5, baseline_frac, f"${inner}$",
        fontproperties=prop, color=safe_color,
        ha="center", va="baseline",
    )
    fig.canvas.draw()

    # Canvas geometry: the formula's baseline sits at y = baseline_frac of
    # the figure (va="baseline" on fig.text centres the math axis on the
    # vertical centre of the canvas). All later metric math is in pixels.
    fig_h_px = int(round(fig.get_figheight() * dpi))
    baseline_px = baseline_frac * fig_h_px

    # Render the full figure to a transparent PNG, then use PIL's
    # alpha-channel bounding box to find the TRUE ink extent.
    # matplotlib's Text.get_window_extent is unreliable for stacked
    # constructs (fractions, \sum with limits): it under-reports the
    # top of the numerator and the top of large operators, so trusting
    # it would visibly cut content (e.g. the top of "U_busy" or the
    # top of a big Σ). PIL's getbbox on the alpha channel is the
    # ground truth — every pixel that was rendered is included — so
    # this crop is guaranteed never to clip a glyph.
    buf = io.BytesIO()
    fig.savefig(buf, dpi=dpi, transparent=True, format="png")
    fig.clear()
    buf.seek(0)
    img = Image.open(buf).convert("RGBA")
    W_canvas, H_canvas = img.size
    alpha = img.split()[-1]
    ink_bbox = alpha.getbbox()  # (l, t, r, b) of non-transparent pixels
    if ink_bbox is None:
        # Degenerate input (empty formula) — fall back to the full canvas
        # so the pipeline still produces an image rather than crashing.
        ink_bbox = (0, 0, W_canvas, H_canvas)
    l, t, r, b = ink_bbox
    x0 = max(0, l - pad_px)
    y0 = max(0, t - pad_px)
    x1 = min(W_canvas, r + pad_px)
    y1 = min(H_canvas, b + pad_px)
    img = img.crop((x0, y0, x1, y1))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path)

    W = x1 - x0
    H = y1 - y0
    # Image coordinates grow downward. The formula baseline is at
    # baseline_px; the cropped image's top edge is y0, bottom is y1.
    #   ascent  (above baseline)  = baseline_px - y0
    #   descent (below baseline)  = y1 - baseline_px
    # CSS uses ``vertical-align: -descent_em`` to drop the image until
    # the formula baseline lands on the text baseline.
    ascent_px = baseline_px - y0
    descent_px = y1 - baseline_px

    return {
        "width_px": W,
        "height_px": H,
        "ascent_px": ascent_px,
        "descent_px": descent_px,
        "pad_px": pad_px,
        "fontsize": fontsize,
        "dpi": dpi,
        "height_em": H / em,
        "ascent_em": ascent_px / em,
        "descent_em": descent_px / em,
    }


# ---------------------------------------------------------------------------
# Markdown rewriting
# ---------------------------------------------------------------------------


def find_formulas(md_text: str) -> list[tuple[int, int, str, bool]]:
    """Return ``[(start, end, formula, is_block)]`` for each ``$...$`` / ``$$...$$`` match."""
    out = []
    for m in MATH_BLOCK_RE.finditer(md_text):
        is_block = m.group(1) is not None
        formula = (m.group(1) if is_block else m.group(2)).strip()
        out.append((m.start(), m.end(), formula, is_block))
    return out


def line_number(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


def _fmt_em(value: float) -> str:
    """Format a float as a 2-decimal em value, stripping trailing zeros."""
    s = f"{value:.2f}"
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return f"{s}em"


def render_formulas_in_markdown(
    md_path: Path,
    out_dir: Path,
    fontsize: float = 11.0,
    dpi: int = 200,
    color: str = "#333333",
    fontset: str = "cm",
    pad_px: int = 3,
    inline_scale: float = 1.0,
    block_scale: float = 1.15,
    inline_max_width_px: int = 520,
) -> dict:
    """Render all formulas in the markdown file; rewrite the file on full success.

    Returns ``{"rendered": [...], "errors": [...], "metrics": {n: {...}}}``.
    On any error, the source file is left untouched.
    """
    text = md_path.read_text(encoding="utf-8")
    out_dir.mkdir(parents=True, exist_ok=True)

    rendered_alt = list(RENDERED_ALT_RE.finditer(text))
    next_no = len(rendered_alt) + 1

    parts: list[str] = []
    last = 0
    rendered: list[dict] = []
    errors: list[dict] = []
    metrics: dict[int, dict] = {}

    for start, end, formula, is_block in find_formulas(text):
        out_path = out_dir / f"f{next_no}.png"
        try:
            m = render_formula(
                formula,
                out_path,
                fontsize=fontsize,
                dpi=dpi,
                color=color,
                fontset=fontset,
                pad_px=pad_px,
            )
        except ValueError as exc:  # mathtext syntax errors raise ValueError
            errors.append(
                {"line": line_number(text, start), "formula": formula, "error": str(exc)}
            )
            next_no += 1
            continue
        except RuntimeError as exc:  # matplotlib missing
            raise

        # Compute the per-instance style.
        if is_block:
            # Block formula: keep ``display:block`` + centered margins, but
            # we no longer pin a height in em — WeChat's editor ignores
            # em units on ``<img>`` and shows the image at its natural
            # size. We render the PNG at a sensible target size
            # (block default fontsize=18pt, dpi=200 → ~50px tall) and
            # let the natural aspect ratio flow. ``max-width:96%`` caps
            # a pathologically wide equation so it never blows past the
            # column. ``border:0`` overrides WeChat's default rule that
            # puts a gray border around every <img> in the editor.
            style = (
                f"display:block;margin:1.2em auto;max-width:96%;"
                f"width:auto;height:auto;border:0"
            )
        else:
            # Inline formula: WeChat ignores em on <img> height and forces
            # ``display:block`` on every <img> in the editor, so the
            # formula image ends up the size of the original PNG, on its
            # own line, mid-sentence. We work around that two ways:
            #   1) Render the PNG at a small target size
            #      (inline default fontsize=11pt, dpi=200 → ~30px tall,
            #      close to body text height). Even shown at natural
            #      size, it fits within a single text line.
            #   2) Use ABSOLUTE pixel height + width:auto in the HTML so
            #      browsers that DO honour CSS (preview, web view) can
            #      scale the image down to a 20px-tall formula. WeChat
            #      will fall back to the natural PNG size, which is
            #      already small.
            # ``border:0`` overrides WeChat's auto-border on images.
            style = (
                f"height:20px;width:auto;vertical-align:-3px;"
                f"margin:0 3px 0 0;display:inline;border:0"
            )

        rendered.append(
            {
                "number": next_no,
                "line": line_number(text, start),
                "formula": formula,
                "file": str(out_path.name),
                "is_block": is_block,
                "height_em": m["height_em"],
                "ascent_em": m["ascent_em"],
                "descent_em": m["descent_em"],
            }
        )
        metrics[next_no] = {**m, "is_block": is_block}
        rel = os.path.relpath(out_path, md_path.parent).replace("\\", "/")
        parts.append(text[last:start])
        parts.append(f"![公式 f{next_no}]({rel}){{style=\"{style}\"}}")
        last = end
        next_no += 1
    parts.append(text[last:])

    if errors:
        return {"rendered": rendered, "errors": errors, "metrics": metrics}

    md_path.write_text("".join(parts), encoding="utf-8")
    return {"rendered": rendered, "errors": [], "metrics": metrics}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description="Render math formulas in markdown to PNG images (em-sized, Computer Modern)."
    )
    parser.add_argument("path", help="Markdown article path")
    parser.add_argument(
        "-o", "--output",
        help="Formula image output dir (default: <article-stem>-formulas/ next to the article)",
    )
    parser.add_argument(
        "--fontsize", type=float, default=11.0,
        help="Render fontsize in pt (default: 11 — produces ~30px-tall inline PNGs, "
             "close to body text size). WeChat's editor ignores CSS em on <img>, "
             "so the PNG natural size IS the on-screen size in WeChat.",
    )
    parser.add_argument(
        "--dpi", type=int, default=200,
        help="Render DPI (default: 200 — enough for retina; going higher just "
             "enlarges the PNG natural size, which WeChat will then show even "
             "bigger because it ignores CSS height on <img>).",
    )
    parser.add_argument(
        "--color", default="#333333",
        help="Text color for the formula (default: #333333, matches most themes' body text). "
             "Pass like '#1f2937' for tech-pro dark slate, or 'black' for pure black.",
    )
    parser.add_argument(
        "--fontset", default="cm", choices=("cm", "stix", "dejavusans", "custom"),
        help="Mathtext fontset (default: cm — Computer Modern / classic LaTeX look).",
    )
    parser.add_argument(
        "--pad-px", type=int, default=3,
        help="Padding around the glyphs in pixels at the render dpi (default: 3).",
    )
    parser.add_argument(
        "--inline-scale", type=float, default=1.0,
        help="Multiplier for inline formula em height (default: 1.0).",
    )
    parser.add_argument(
        "--block-scale", type=float, default=1.15,
        help="Multiplier for block (display) formula em height (default: 1.15).",
    )
    args = parser.parse_args()

    if matplotlib is None:
        print("matplotlib is not installed. Run: pip install matplotlib", file=sys.stderr)
        sys.exit(2)

    md_path = Path(args.path)
    out_dir = Path(args.output) if args.output else md_path.parent / f"{md_path.stem}-formulas"

    result = render_formulas_in_markdown(
        md_path,
        out_dir,
        fontsize=args.fontsize,
        dpi=args.dpi,
        color=args.color,
        fontset=args.fontset,
        pad_px=args.pad_px,
        inline_scale=args.inline_scale,
        block_scale=args.block_scale,
    )
    for r in result["rendered"]:
        kind = "block" if r["is_block"] else "inline"
        print(
            f"rendered f{r['number']:>2} {kind:>6} (line {r['line']:>3}, "
            f"height {r['height_em']:.2f}em, ascent {r['ascent_em']:.2f}em): "
            f"{r['file']}"
        )
    if result["errors"]:
        print("\nFormula errors:")
        for e in result["errors"]:
            print(f"  line {e['line']}: {e['formula'][:60]}")
            print(f"    {e['error']}")
        sys.exit(1)
    print(f"\nDone. {len(result['rendered'])} formulas rendered ({args.fontset} fontset, "
          f"{args.dpi} dpi, color {args.color}).")


if __name__ == "__main__":
    main()
