"""Contract tests: assert the promises SKILL.md makes to its users.

These tests guard the *product contract* (behaviour the pipeline promises),
not Python behaviour. If a refactor silently drops one of these promises,
the suite fails instead of shipping a changed contract.
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL_TEXT = (REPO_ROOT / "SKILL.md").read_text(encoding="utf-8")


# --- Path integrity ---------------------------------------------------------

_PREFIX_RE = re.compile(
    r"\{skill_dir\}/((?:references|scripts|toolkit|templates|personas)/[A-Za-z0-9_./-]+)"
)
_BARE_SCRIPTS_RE = re.compile(r"\bscripts/([A-Za-z0-9_-]+\.(?:py|sh))")
_BARE_TOOLKIT_RE = re.compile(r"\btoolkit/([A-Za-z0-9_./-]+\.py)")
_BARE_TEMPLATES_RE = re.compile(r"\btemplates/([A-Za-z0-9_-]+\.md)")


def test_all_referenced_paths_exist():
    refs = set(_PREFIX_RE.findall(SKILL_TEXT))
    refs |= {"scripts/" + m for m in _BARE_SCRIPTS_RE.findall(SKILL_TEXT)}
    refs |= {"toolkit/" + m for m in _BARE_TOOLKIT_RE.findall(SKILL_TEXT)}
    refs |= {"templates/" + m for m in _BARE_TEMPLATES_RE.findall(SKILL_TEXT)}
    # Referenced by SKILL.md but intentionally absent in a fresh clone:
    # user-generated / conditional resources (gitignored by design).
    allow_missing = {"references/exemplars/index.yaml"}
    missing = sorted(
        p for p in refs
        if not (REPO_ROOT / p).exists() and p not in allow_missing
    )
    assert missing == [], f"SKILL.md references missing paths: {missing}"


# --- Publish authorization --------------------------------------------------

def test_publish_defaults_to_local_delivery():
    assert "发布授权" in SKILL_TEXT
    assert "本地成稿" in SKILL_TEXT
    assert "用户当轮明确" in SKILL_TEXT
    assert "publish.mode: confirmation" in SKILL_TEXT
    assert "publish.mode: auto" in SKILL_TEXT


def test_step7_checks_publish_authorization_before_publishing():
    assert "发布授权检查" in SKILL_TEXT
    assert "只执行 preview" in SKILL_TEXT


def test_config_example_documents_publish_modes():
    cfg = (REPO_ROOT / "config.example.yaml").read_text(encoding="utf-8")
    assert "publish:" in cfg
    assert "confirmation" in cfg
    assert "auto" in cfg


# --- Material gate / dual-mode promises -------------------------------------

def test_material_gate_compression_promise_intact():
    assert "material_gate: compressed" in SKILL_TEXT
    assert "≤600 字" in SKILL_TEXT          # wechat compressed length
    assert "800-1200 字" in SKILL_TEXT      # tech compressed length


def test_dual_mode_priority_rule_intact():
    assert "第一优先：叙事架构" in SKILL_TEXT
    assert "第二优先：问题驱动法" in SKILL_TEXT
    assert "第三优先：说服力原则" in SKILL_TEXT


# --- Run state machine ------------------------------------------------------

def test_skill_md_uses_run_manager():
    assert "run_manager.py start" in SKILL_TEXT
    assert "run_manager.py step" in SKILL_TEXT
    assert "run_manager.py finish" in SKILL_TEXT
    assert "继续上次" in SKILL_TEXT


def test_skill_md_wires_source_ledger_and_claims_audit():
    assert "source_ledger.py add" in SKILL_TEXT
    assert "claims_audit.py" in SKILL_TEXT
    assert "excerpt" in SKILL_TEXT


def test_skill_md_mentions_unified_check_command():
    assert "cli.py check" in SKILL_TEXT
    assert "聚合入口" in SKILL_TEXT


def test_skill_md_mentions_theme_generator():
    assert "theme-init" in SKILL_TEXT
    assert "theme-generator.md" in SKILL_TEXT


def test_skill_md_mentions_multiplatform_rewrite():
    assert "multiplatform-rewrite.md" in SKILL_TEXT
    assert "不覆盖原稿" in SKILL_TEXT
