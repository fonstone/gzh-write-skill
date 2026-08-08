#!/usr/bin/env python3
"""Render LaTeX-style math formulas in a markdown article to PNG images.

Scans $...$ / $$...$$ blocks, validates syntax with matplotlib mathtext,
renders each to a PNG, and replaces the formula with an image reference.
Idempotent: already-rendered formulas are skipped.

Usage:
    python3 render_formulas.py {article}.md
    python3 render_formulas.py {article}.md -o output/{slug}-formulas/
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

try:
    import matplotlib

    matplotlib.use("Agg")
    from matplotlib import font_manager as fm
    from matplotlib.mathtext import math_to_image
except ImportError:  # pragma: no cover - import fallback path
    math_to_image = None

MATH_BLOCK_RE = re.compile(r"\$\$(.+?)\$\$|\$(.+?)\$", re.DOTALL)
RENDERED_ALT_RE = re.compile(r"!\[公式 f\d+\]\(")


def find_formulas(md_text: str) -> list[tuple[int, int, str]]:
    """Return [(start, end, formula)] for each $...$ / $$...$$ match."""
    out = []
    for m in MATH_BLOCK_RE.finditer(md_text):
        formula = m.group(1) if m.group(1) is not None else m.group(2)
        out.append((m.start(), m.end(), formula))
    return out


def line_number(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


def render_formula(formula: str, out_path: Path, fontsize: int = 14, dpi: int = 300) -> None:
    """Render a formula to PNG. Raises ValueError on syntax error."""
    if math_to_image is None:
        raise RuntimeError("matplotlib is not installed")
    prop = fm.FontProperties(size=fontsize)
    math_to_image(f"${formula.strip()}$", str(out_path), prop=prop, dpi=dpi, format="png")


def render_formulas_in_markdown(md_path: Path, out_dir: Path) -> dict:
    """Render all formulas in the markdown file; rewrite file on full success."""
    text = md_path.read_text(encoding="utf-8")
    out_dir.mkdir(parents=True, exist_ok=True)

    rendered_alt = list(RENDERED_ALT_RE.finditer(text))
    next_no = len(rendered_alt) + 1

    parts, last, rendered, errors = [], 0, [], []
    for start, end, formula in find_formulas(text):
        out_path = out_dir / f"f{next_no}.png"
        try:
            render_formula(formula, out_path)
        except ValueError as exc:  # mathtext syntax errors raise ValueError
            errors.append(
                {"line": line_number(text, start), "formula": formula, "error": str(exc)}
            )
            next_no += 1
            continue
        rel = os.path.relpath(out_path, md_path.parent).replace("\\", "/")
        rendered.append(
            {"number": next_no, "line": line_number(text, start), "formula": formula, "file": rel}
        )
        parts.append(text[last:start])
        parts.append(f"![公式 f{next_no}]({rel})")
        last = end
        next_no += 1
    parts.append(text[last:])

    if errors:
        return {"rendered": rendered, "errors": errors}
    md_path.write_text("".join(parts), encoding="utf-8")
    return {"rendered": rendered, "errors": []}


def main():
    parser = argparse.ArgumentParser(description="Render math formulas in markdown to PNG images")
    parser.add_argument("path", help="Markdown article path")
    parser.add_argument(
        "-o", "--output",
        help="Formula image output dir (default: <article-stem>-formulas/ next to the article)",
    )
    args = parser.parse_args()

    if math_to_image is None:
        print("matplotlib is not installed. Run: pip install matplotlib", file=sys.stderr)
        sys.exit(2)

    md_path = Path(args.path)
    if args.output:
        out_dir = Path(args.output)
    else:
        out_dir = md_path.parent / f"{md_path.stem}-formulas"

    result = render_formulas_in_markdown(md_path, out_dir)
    for r in result["rendered"]:
        print(f"rendered f{r['number']} (line {r['line']}): {r['file']}")
    if result["errors"]:
        print("Formula errors:")
        for e in result["errors"]:
            print(f"  line {e['line']}: {e['formula'][:60]}")
            print(f"    {e['error']}")
        sys.exit(1)
    print(f"Done. {len(result['rendered'])} formulas rendered.")


if __name__ == "__main__":
    main()
