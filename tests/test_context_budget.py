"""Tests for context_budget.py — the static pipeline context-load meter."""

import subprocess
import sys
from pathlib import Path

import context_budget

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "context_budget.py"


SYNTHETIC = """\
# Synthetic Skill

## Step 3
```
if mode == tech:
  读取: {skill_dir}/references/tech-a.md
否则:
  读取: {skill_dir}/references/wech-a.md
```

双模式材料：
读取: {skill_dir}/references/topic-selection.md

未标记的孤立引用：
读取: {skill_dir}/references/orphan.md

如果 mode=tech，额外加载 `{skill_dir}/references/tech-b.md`。

wechat 模式：
```
读取: {skill_dir}/references/wech-b.md
```

## 辅助功能
读取: {skill_dir}/references/onboard.md
"""


def test_parse_references_classifies_branches():
    scopes = dict(context_budget.parse_references(SYNTHETIC))
    assert scopes["references/tech-a.md"] == "tech"
    assert scopes["references/wech-a.md"] == "wechat"
    assert scopes["references/topic-selection.md"] == "both"      # KNOWN_BOTH
    assert scopes["references/orphan.md"] == "unclassified"       # no signal, not allowlisted
    assert scopes["references/tech-b.md"] == "tech"               # inline marker
    assert scopes["references/wech-b.md"] == "wechat"             # ambient "wechat 模式：" prose
    assert scopes["references/onboard.md"] == "auxiliary"


def test_parse_references_dedupes_with_widest_scope():
    text = (
        "如果 mode=tech，见 `{skill_dir}/references/x.md`。\n"
        "读取: {skill_dir}/references/x.md\n"
    )
    scopes = dict(context_budget.parse_references(text))
    assert scopes["references/x.md"] == "both"


def test_measure_on_real_skill_md_has_no_unclassified():
    m = context_budget.measure(REPO_ROOT)
    assert m["totals"]["wechat"]["tokens"] > 0
    assert m["totals"]["tech"]["tokens"] > 0
    unclassified = [e["name"] for e in m["entries"] if e["scope"] == "unclassified"]
    assert unclassified == [], f"unclassified refs need a marker or KNOWN_BOTH: {unclassified}"
    names = {e["name"] for e in m["entries"]}
    assert "SKILL.md" in names
    assert "references/topic-selection.md" in names
    assert "templates/ARTICLE_TEMPLATE.md" in names   # tech-mode spec is counted
    assert m["missing"] == []


def test_classification_golden_on_real_skill_md():
    text = (REPO_ROOT / "SKILL.md").read_text(encoding="utf-8")
    scopes = dict(context_budget.parse_references(text))
    # Tech-only docs must not leak into the wechat path.
    assert scopes["references/tech-writing-guide.md"] == "tech"
    assert scopes["references/tech-frameworks.md"] == "tech"
    assert scopes["references/tech-self-check-pyramid.md"] == "tech"
    # Wechat-only docs.
    assert scopes["references/writing-guide.md"] == "wechat"
    assert scopes["references/human-prose.md"] == "wechat"
    # Shared docs.
    assert scopes["references/ai-patterns.md"] == "both"
    assert scopes["references/topic-selection.md"] == "both"
    # Auxiliary docs never count into either happy-path total.
    assert scopes["references/onboard.md"] == "auxiliary"
    assert scopes["references/exemplar-seeds.yaml"] == "auxiliary"
    assert scopes["references/wechat-constraints.md"] == "auxiliary"


def test_auxiliary_docs_excluded_from_totals():
    m = context_budget.measure(REPO_ROOT)
    counted = [e for e in m["entries"] if e["scope"] != "auxiliary"]
    aux_chars = sum(e["chars"] for e in m["entries"] if e["scope"] == "auxiliary")
    assert aux_chars > 0
    both_chars = sum(e["chars"] for e in counted if e["scope"] == "both")
    wechat_only = sum(e["chars"] for e in counted if e["scope"] == "wechat")
    tech_only = sum(e["chars"] for e in counted if e["scope"] == "tech")
    assert m["totals"]["wechat"]["chars"] == both_chars + wechat_only
    assert m["totals"]["tech"]["chars"] == both_chars + tech_only


def test_budget_flag_exits_nonzero_when_over_budget():
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--mode", "wechat", "--budget-tokens", "1"],
        capture_output=True, text=True,
    )
    assert proc.returncode == 1
    assert "budget" in (proc.stderr + proc.stdout).lower()


def test_json_output_is_parseable():
    import json
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--json", "--mode", "all"],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0
    data = json.loads(proc.stdout)
    assert "totals" in data and "wechat" in data["totals"] and "tech" in data["totals"]
    assert "entries" in data


# --- Budget red lines (Task 2 of the optimization plan) ---------------------

# Measured 2026-10-19, before the mode-conditional loading work.
BASELINE_WECHAT_TOKENS = 78518
# Tech mode measures 77,888 tokens including the tech deep-article
# templates (baseline including templates: 84,706 → −8.0%). The absolute
# budget carries ~3% headroom (tech has no fixed percentage promise).
TECH_BUDGET_TOKENS = 80300


def test_wechat_budget_below_85pct_of_baseline():
    m = context_budget.measure(REPO_ROOT)
    budget = int(BASELINE_WECHAT_TOKENS * 0.85)
    assert m["totals"]["wechat"]["tokens"] <= budget, (
        f"wechat {m['totals']['wechat']['tokens']} > {budget} (<85% of baseline "
        f"{BASELINE_WECHAT_TOKENS})"
    )


def test_tech_within_absolute_budget():
    m = context_budget.measure(REPO_ROOT)
    assert m["totals"]["tech"]["tokens"] <= TECH_BUDGET_TOKENS, m["totals"]["tech"]


def test_mode_conditional_scopes():
    """After the optimization each doc is loaded by exactly one happy path."""
    text = (REPO_ROOT / "SKILL.md").read_text(encoding="utf-8")
    scopes = dict(context_budget.parse_references(text))
    tech_only = [
        "references/tech-writing-guide.md",
        "references/tech-frameworks.md",
        "references/tech-narrative-architecture.md",
        "references/tech-writing-persuasion.md",
        "references/tech-prose.md",
        "references/tech-self-check-pyramid.md",
        "references/headline_templates.md",
        "references/ending_templates.md",
        "references/tech-common-pitfalls.md",
    ]
    wechat_only = [
        "references/writing-guide.md",
        "references/human-prose.md",
        "references/frameworks.md",
        "references/article-archetypes.md",
        "references/style-examples.md",
        "references/self-check-pyramid.md",
        "references/wechat-theme-guide.md",
    ]
    for rel in tech_only:
        assert scopes[rel] == "tech", (rel, scopes.get(rel))
    for rel in wechat_only:
        assert scopes[rel] == "wechat", (rel, scopes.get(rel))
    # The deferred technique library stays out of both happy paths.
    assert scopes["references/writing-techniques.md"] == "auxiliary"

