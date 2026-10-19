"""Tests for theme_gen.py — deterministic theme generation."""

import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "toolkit"))

import theme_gen  # noqa: E402
from theme import load_theme  # noqa: E402
from converter import WeChatConverter  # noqa: E402

CLI = REPO_ROOT / "toolkit" / "cli.py"


def _write_and_load(tmp_path, text, name):
    themes_dir = tmp_path / "themes"
    themes_dir.mkdir(exist_ok=True)
    (themes_dir / f"{name}.yaml").write_text(text, encoding="utf-8")
    return load_theme(name, themes_dir=str(themes_dir))


def test_generated_theme_loads_and_converts(tmp_path):
    text = theme_gen.generate_theme_yaml("my-theme", "#0f766e", style="tech")
    theme = _write_and_load(tmp_path, text, "my-theme")
    assert theme.name == "my-theme"
    assert theme.colors["primary"] == "#0f766e"
    conv = WeChatConverter(theme=theme)
    result = conv.convert("# 标题\n\n这是**重点**正文。\n")
    assert "#0f766e" in result.html


def test_presets_differ_and_cover_required_selectors():
    outputs = {
        preset: theme_gen.generate_theme_yaml(f"t-{preset}", "#2563eb", style=preset)
        for preset in ("minimal", "tech", "warm", "editorial")
    }
    assert len(set(outputs.values())) == 4, "each preset must produce a distinct theme"
    for text in outputs.values():
        for selector in ("h1", "h2", "h3", "p", "strong", "blockquote", "code", "pre",
                         "img", "a", "hr", "table", "th", "td", "li"):
            assert selector in text, selector


def test_validation_warns_on_low_contrast():
    text = theme_gen.generate_theme_yaml("washed", "#f8fafc", style="minimal")  # near-white
    result = theme_gen.validate_theme(text)
    assert result["ok"] is True
    assert any("对比度" in w for w in result["warnings"])

    good = theme_gen.generate_theme_yaml("solid", "#1f2937", style="minimal")
    result = theme_gen.validate_theme(good)
    assert not any("主色" in w and "对比度" in w for w in result["warnings"])


def test_validation_rejects_malformed_yaml():
    assert theme_gen.validate_theme("{{{{ not yaml")["ok"] is False
    assert theme_gen.validate_theme("name: x")["ok"] is False  # missing keys


def test_invalid_hex_raises():
    with pytest.raises(ValueError):
        theme_gen.generate_theme_yaml("bad", "not-a-color")
    with pytest.raises(ValueError):
        theme_gen.generate_theme_yaml("bad", "#12")


def test_darkmode_derived():
    text = theme_gen.generate_theme_yaml("dark-check", "#2563eb")
    data = yaml.safe_load(text)
    dm = data["colors"]["darkmode"]
    assert dm["background"] != data["colors"]["background"]
    assert dm["primary"].startswith("#")


def test_cli_theme_init_writes_and_refuses_overwrite(tmp_path):
    out = tmp_path / "themes"
    cmd = [sys.executable, str(CLI), "theme-init", "cli-theme",
           "--primary", "#b45309", "--style", "warm", "--output", str(out)]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    path = out / "cli-theme.yaml"
    assert path.exists()
    assert "#b45309" in path.read_text(encoding="utf-8")

    proc = subprocess.run(cmd, capture_output=True, text=True)
    assert proc.returncode == 1          # refuses overwrite without --force

    proc = subprocess.run(cmd + ["--force"], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr
