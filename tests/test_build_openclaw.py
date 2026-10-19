"""Tests for build_openclaw.py — the OpenClaw dist builder."""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import build_openclaw  # noqa: E402


def _build(tmp_path):
    out = tmp_path / "dist"
    build_openclaw.build(out)
    return out


def test_build_includes_templates_and_toolkit_assets(tmp_path):
    out = _build(tmp_path)
    assert (out / "SKILL.md").exists()
    # SKILL.md mandates templates/ in tech mode; the build must ship them.
    assert (out / "templates" / "ARTICLE_TEMPLATE.md").exists()
    assert (out / "templates" / "reference-ai-os.md").exists()
    # Tech mode mandates style-tech.yaml; it must ship and match the source.
    shipped = out / "style-tech.yaml"
    assert shipped.exists()
    assert shipped.read_bytes() == (REPO_ROOT / "style-tech.yaml").read_bytes()
    # Toolkit modules added after the last manual dist build must be present.
    assert (out / "toolkit" / "doocs_themes.py").exists()
    assert (out / "toolkit" / "assets" / "mermaid.min.js").exists()


def test_prune_exemplars_is_recursive(tmp_path):
    ex = tmp_path / "references" / "exemplars"
    (ex / "account-a").mkdir(parents=True)
    (ex / "a.md").write_text("x", encoding="utf-8")
    (ex / "account-a" / "b.md").write_text("x", encoding="utf-8")
    (ex / "account-a" / "index.yaml").write_text("x", encoding="utf-8")
    (ex / ".gitkeep").write_text("", encoding="utf-8")
    build_openclaw._prune_exemplars(ex)
    assert (ex / ".gitkeep").exists()
    assert not list(ex.rglob("*.md"))
    assert not list(ex.rglob("index.yaml"))


def test_build_excludes_user_exemplars_keeps_gitkeep(tmp_path):
    out = _build(tmp_path)
    exemplars = out / "references" / "exemplars"
    assert exemplars.is_dir()
    assert (exemplars / ".gitkeep").exists()
    assert not (exemplars / "index.yaml").exists()
    assert list(exemplars.glob("*.md")) == [], "user exemplars must not ship"


def test_build_transforms_skill_md_for_openclaw(tmp_path):
    out = _build(tmp_path)
    text = (out / "SKILL.md").read_text(encoding="utf-8")
    assert "{baseDir}" in text
    assert "{skill_dir}" not in text
    assert "TaskCreate" in text
    assert "todowrite" not in text
    assert "web_search" in text
