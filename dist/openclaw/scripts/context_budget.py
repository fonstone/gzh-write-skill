#!/usr/bin/env python3
"""Measure the static doc-context load of a full GzhWrite pipeline run.

The GzhWrite pipeline instructs the agent to load a set of documents
(SKILL.md itself, references/*, the mode's persona, and -- in tech mode --
the article templates). This script parses those *load* directives out of
SKILL.md, classifies each referenced file by the mode that loads it, and
reports lines / chars / estimated tokens so context bloat is measurable
and CI-gateable.

Classification policy
---------------------
- ``both``     -- loaded on the happy path of both modes. Only refs listed
  in ``KNOWN_BOTH`` may resolve to "both" without an explicit branch
  marker; anything else that would default to "both" is reported as
  ``unclassified`` (visible in ``--json``, and a test fails on it) so a
  new document cannot silently join both happy paths.
- ``wechat`` / ``tech`` -- loaded only on that mode's happy path.
  Determined by fenced ``if mode == tech: ... 否则: ...`` blocks, inline
  markers (``如果 mode=tech``), and prose ambient markers
  (``wechat 模式：`` / ``tech 模式：``) that scope the fence that
  immediately follows.
- ``auxiliary`` -- deliberately NOT loaded by the pipeline (first-run and
  on-demand references, fallback libraries, and dev-references whose
  rules are enforced by scripts). Excluded from both totals, in the
  baseline and after.
- Bare ``templates/*.md`` mentions are tech-mode deep-article specs and
  are counted as ``tech`` reads.

Token estimate: ``round(chars / 2)`` (≈2 characters per token for mixed
Chinese/ASCII text). The number is deliberately an estimate — the budget
gate only needs a consistent unit.

Usage:
    python3 scripts/context_budget.py                 # human table (all modes)
    python3 scripts/context_budget.py --json          # machine output
    python3 scripts/context_budget.py --mode wechat --budget-tokens 120000
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

READ_RE = re.compile(
    r"\{skill_dir\}/((?:references|templates|personas)/[\w./-]+\.(?:md|yaml))"
)

# Docs deliberately NOT part of the happy path (first-run extras, on-demand
# references, dev-references, fallback libraries). Excluded from both totals.
AUXILIARY = {
    "references/onboard.md",            # first-run / 重新设置风格
    "references/learn-edits.md",        # 学习我的修改
    "references/effect-review.md",      # 效果复盘
    "references/style-template.md",     # referenced from onboard only
    "references/exemplar-seeds.yaml",   # fallback when exemplar library is empty
    "references/exemplars/index.yaml",  # user-private, conditional
    "references/multiplatform-rewrite.md",  # on-demand
    "references/theme-generator.md",        # on-demand
    "references/writing-techniques.md",      # 磨稿/改稿阶段才加载
    "references/wechat-constraints.md",      # dev-reference: rules enforced by converter/validator, never loaded by the pipeline
    "references/ai-patterns-examples.md",    # 改稿阶段参考
}

# References that are genuinely loaded by BOTH modes and carry no inline
# branch marker. A ref that resolves to "both" only because it never had a
# marker must be listed here; otherwise it is reported as "unclassified"
# so a new document cannot silently join both happy paths.
KNOWN_BOTH = {
    "references/topic-selection.md",
    "references/topic-diagnosis.md",
    "references/content-enhance.md",
    "references/ai-patterns.md",
    "references/seo-rules.md",
    "references/visual-prompts.md",
}

# Bare (non-{skill_dir}) template mentions in SKILL.md: tech-mode
# deep-article specs, mandatory reads in tech mode.
BARE_TEMPLATE_RE = re.compile(r"\btemplates/[A-Za-z0-9_-]+\.md")

TECH_TAG = re.compile(r"mode\s*==?\s*tech|tech\s*模式|Tech\s*模式")
WECHAT_TAG = re.compile(r"mode\s*==?\s*wechat|wechat\s*模式|公众号模式")

DEFAULT_PERSONAS = {
    "wechat": "personas/midnight-friend.yaml",
    "tech": "personas/tech-explainer.yaml",
}

_SCOPE_RANK = {"wechat": 1, "tech": 2, "both": 3}


def _union(a: str, b: str) -> str:
    """Widest scope wins; auxiliary always wins (policy exclusion)."""
    if a == "auxiliary" or b == "auxiliary":
        return "auxiliary"
    return a if _SCOPE_RANK[a] >= _SCOPE_RANK[b] else b


def _line_scope(line: str):
    """Inline mode markers on this line, or None."""
    has_tech, has_we = bool(TECH_TAG.search(line)), bool(WECHAT_TAG.search(line))
    if has_tech and not has_we:
        return "tech"
    if has_we and not has_tech:
        return "wechat"
    return None


def parse_references(text: str) -> list[tuple[str, str]]:
    """Parse ``{skill_dir}/...`` load directives; return ordered (rel, scope).

    Deduplicated by path with the widest scope kept (a file loaded by both
    modes is ``both``). A prose-level mode marker (``wechat 模式：`` /
    ``tech 模式：``) scopes only the fence that immediately follows it; any
    other prose line clears it, so a marker can never leak across sections.
    """
    scopes: dict[str, str] = {}
    order: list[str] = []
    signaled: set[str] = set()

    in_fence = False
    branch: str | None = None    # explicit if/else branch inside a fence
    ambient: str | None = None   # scope of the currently open fence
    pending: str | None = None   # marker for the *next* fence

    for raw in text.splitlines():
        s = raw.strip()

        if s.startswith("```"):
            if not in_fence:
                in_fence = True
                branch = None
                ambient = pending
            else:
                in_fence = False
                branch = None
                ambient = None
            pending = None
            continue

        if not in_fence:
            # Prose scoping: a marker line arms the next fence; every other
            # non-empty line disarms it.
            if s.startswith("#") or s == "---":
                pending = None
            elif s:
                pending = _line_scope(s)
        else:
            if re.match(r"if\s+mode\s*==\s*tech", s):
                branch = "tech"
                continue
            if s.startswith("否则") or re.match(r"else\b", s):
                branch = "wechat"
                continue

        line_scope = _line_scope(s)
        for m in READ_RE.finditer(raw):
            rel = m.group(1)
            if line_scope is not None or (in_fence and (branch or ambient)):
                signaled.add(rel)
            if rel in AUXILIARY:
                scope = "auxiliary"
            elif in_fence:
                scope = line_scope or branch or ambient or "both"
            else:
                # Prose-level scope applies inside fences only; a bare
                # out-of-fence ``读取:`` line without its own marker is a
                # both-modes read.
                scope = line_scope or "both"
            if rel not in scopes:
                order.append(rel)
                scopes[rel] = scope
            else:
                scopes[rel] = _union(scopes[rel], scope)

    out: list[tuple[str, str]] = []
    for rel in order:
        scope = scopes[rel]
        if scope == "both" and rel not in signaled and rel not in KNOWN_BOTH:
            scope = "unclassified"
        out.append((rel, scope))
    return out


def _tokens(chars: int) -> int:
    return round(chars / 2)


def _entry(name: str, path: Path, scope: str) -> dict:
    text = path.read_text(encoding="utf-8")
    lines = text.count("\n") + (0 if text.endswith("\n") or not text else 1)
    return {
        "name": name,
        "scope": scope,
        "lines": lines,
        "chars": len(text),
        "tokens": _tokens(len(text)),
    }


def measure(repo_root: Path) -> dict:
    """Return entries + per-mode totals for the given project root."""
    skill_path = repo_root / "SKILL.md"
    text = skill_path.read_text(encoding="utf-8")

    entries = [_entry("SKILL.md", skill_path, "both")]
    missing: list[str] = []

    for rel, scope in parse_references(text):
        p = repo_root / rel
        if p.exists():
            entries.append(_entry(rel, p, scope))
        else:
            missing.append(rel)

    # Bare template mentions (tech-mode deep-article specs) are mandatory
    # tech-mode reads: count them explicitly.
    seen_names = {e["name"] for e in entries}
    for m in BARE_TEMPLATE_RE.finditer(text):
        rel = m.group(0)
        if rel in seen_names:
            continue
        seen_names.add(rel)
        p = repo_root / rel
        if p.exists():
            entries.append(_entry(rel, p, "tech"))
        else:
            missing.append(rel)

    for mode, rel in DEFAULT_PERSONAS.items():
        p = repo_root / rel
        if p.exists():
            entries.append(_entry(rel, p, mode))

    totals = {}
    for mode in ("wechat", "tech"):
        chars = sum(e["chars"] for e in entries if e["scope"] in ("both", mode))
        totals[mode] = {"chars": chars, "tokens": _tokens(chars)}

    return {"entries": entries, "totals": totals, "missing": sorted(set(missing))}


def _print_table(result: dict, mode: str) -> None:
    print(f"{'file':<48}{'scope':<11}{'lines':>7}{'chars':>9}{'~tok':>8}")
    print("-" * 83)
    for e in result["entries"]:
        if mode != "all" and e["scope"] not in ("both", mode):
            continue
        print(f"{e['name']:<48}{e['scope']:<11}{e['lines']:>7}{e['chars']:>9}{e['tokens']:>8}")
    print("-" * 83)
    for m in ("wechat", "tech"):
        if mode in (m, "all"):
            t = result["totals"][m]
            print(f"{('TOTAL ' + m):<48}{'':<11}{'':>7}{t['chars']:>9}{t['tokens']:>8}")
    if result["missing"]:
        print("\nmissing: " + ", ".join(result["missing"]))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Measure GzhWrite pipeline context load")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--mode", choices=["wechat", "tech", "all"], default="all")
    ap.add_argument("--budget-tokens", type=int, default=None,
                    help="fail (exit 1) when a selected mode exceeds this budget")
    ap.add_argument("--root", default=str(REPO_ROOT), help="project root (default: repo root)")
    args = ap.parse_args(argv)

    result = measure(Path(args.root))

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        _print_table(result, args.mode)

    if args.budget_tokens is not None:
        modes = ["wechat", "tech"] if args.mode == "all" else [args.mode]
        over = [m for m in modes if result["totals"][m]["tokens"] > args.budget_tokens]
        if over:
            for m in over:
                print(
                    f"context budget exceeded: {m} {result['totals'][m]['tokens']} "
                    f"> {args.budget_tokens} ~tokens",
                    file=sys.stderr,
                )
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
