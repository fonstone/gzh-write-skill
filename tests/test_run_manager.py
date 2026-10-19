"""Tests for run_manager.py — per-article pipeline state."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import run_manager  # noqa: E402


@pytest.fixture
def root(tmp_path):
    return tmp_path


def test_start_creates_state(root):
    run_dir = run_manager.start(root, topic="测试选题", mode="tech", framework="全景架构型")
    state = yaml.safe_load((run_dir / "state.yaml").read_text(encoding="utf-8"))
    assert state["status"] == "active"
    assert state["mode"] == "tech"
    assert state["framework"] == "全景架构型"
    assert state["topic"]["title"] == "测试选题"
    assert set(state["steps"]) == set(run_manager.STEPS)
    assert all(v == "pending" for v in state["steps"].values())
    assert run_dir.parent == root / "output" / "runs"


def test_step_updates_and_validates(root):
    run_manager.start(root, topic="t", mode="wechat")
    state = run_manager.set_step(root, "write", "completed")
    assert state["steps"]["write"] == "completed"
    with pytest.raises(ValueError):
        run_manager.set_step(root, "nope", "completed")
    with pytest.raises(ValueError):
        run_manager.set_step(root, "write", "done")


def test_update_patch_merges(root):
    run_manager.start(root, topic="t", mode="tech")
    state = run_manager.update(
        root, {"artifacts": {"draft": "output/a.md"}, "material_gate": "passed"}
    )
    assert state["artifacts"]["draft"] == "output/a.md"
    assert state["artifacts"]["article"] is None      # untouched key preserved
    assert state["material_gate"] == "passed"


def test_finish_appends_history_entry(root):
    run_dir = run_manager.start(root, topic="测试选题", mode="tech", framework="源码拆解型")
    run_manager.update(
        root,
        {
            "artifacts": {"article": "output/2026-10-19-tech-x.md"},
            "topic": {"keywords": ["缓存", "RTOS"], "source": "热点抓取"},
            "flags": {
                "word_count": 5200,
                "writing_persona": "tech-explainer",
                "enhance_strategy": "density_boost",
                "writing_config_snapshot": {"sentence_variance": 0.42},
            },
        },
    )
    run_manager.finish(root)
    hist = yaml.safe_load((root / "history.yaml").read_text(encoding="utf-8"))
    assert isinstance(hist, list) and len(hist) == 1
    entry = hist[0]
    assert entry["title"] == "测试选题"
    assert entry["output_file"] == "output/2026-10-19-tech-x.md"
    assert entry["framework"] == "源码拆解型"
    assert entry["material_gate"] == "passed"
    assert entry["word_count"] == 5200
    assert entry["topic_keywords"] == ["缓存", "RTOS"]
    assert entry["topic_source"] == "热点抓取"
    assert entry["enhance_strategy"] == "density_boost"
    assert entry["writing_config_snapshot"] == {"sentence_variance": 0.42}
    assert entry["stats"] is None
    state = yaml.safe_load((run_dir / "state.yaml").read_text(encoding="utf-8"))
    assert state["status"] == "completed"
    assert state["finished"]


def test_finish_handles_history_without_trailing_newline(root):
    # Regression: a history.yaml ending with "stats: null" and no final
    # newline used to glue two entries together on append.
    (root / "history.yaml").write_text(
        '- date: "2026-09-01"\n  title: "旧稿"\n  stats: null', encoding="utf-8"
    )
    run_manager.start(root, topic="新稿", mode="tech")
    run_manager.finish(root)
    hist = yaml.safe_load((root / "history.yaml").read_text(encoding="utf-8"))
    assert len(hist) == 2
    assert hist[1]["title"] == "新稿"


def test_status_latest_run(root):
    r1 = run_manager.start(root, topic="第一篇", mode="wechat")
    r2 = run_manager.start(root, topic="第二篇", mode="tech")
    os.utime(r1 / "state.yaml", (1, 1))
    assert run_manager.latest_run(root) == r2


def test_malformed_state_returns_error_and_leaves_file_untouched(root):
    run_dir = run_manager.start(root, topic="t", mode="wechat")
    p = run_dir / "state.yaml"
    p.write_text("{{{{ not yaml", encoding="utf-8")
    before = p.read_bytes()
    with pytest.raises((ValueError, yaml.YAMLError)):
        run_manager.set_step(root, "write", "completed")
    assert p.read_bytes() == before


def test_structural_corruption_reports_readable_error(root):
    """A parseable-but-incomplete state.yaml must raise ValueError (not KeyError)."""
    run_dir = run_manager.start(root, topic="t", mode="wechat")
    p = run_dir / "state.yaml"
    p.write_text("run_id: r1\n", encoding="utf-8")
    before = p.read_bytes()
    with pytest.raises(ValueError) as exc:
        run_manager.set_step(root, "write", "completed")
    assert "malformed" in str(exc.value)
    assert p.read_bytes() == before


def test_cli_structural_corruption_exits_readable(root):
    run_dir = run_manager.start(root, topic="t", mode="wechat")
    (run_dir / "state.yaml").write_text("run_id: r1\n", encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "run_manager.py"),
         "--root", str(root), "step", "write", "completed"],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert proc.returncode == 1
    assert "malformed" in (proc.stderr or "")
    assert "Traceback" not in (proc.stderr or "")


def test_update_rejects_non_mapping_patch(root):
    run_manager.start(root, topic="t", mode="wechat")
    with pytest.raises(ValueError):
        run_manager.update(root, [1, 2])


def test_finish_is_idempotent(root):
    run_manager.start(root, topic="重复封存", mode="tech")
    first = run_manager.finish(root)
    assert first and first["title"] == "重复封存"
    second = run_manager.finish(root)
    assert second is None
    hist = yaml.safe_load((root / "history.yaml").read_text(encoding="utf-8"))
    assert len(hist) == 1


def test_finish_after_state_reset_does_not_duplicate(root):
    """Crash-retry guard: identical trailing entry is never appended twice."""
    run_dir = run_manager.start(root, topic="重试", mode="tech")
    run_manager.finish(root)
    state = yaml.safe_load((run_dir / "state.yaml").read_text(encoding="utf-8"))
    state["status"] = "active"
    state["finished"] = None
    (run_dir / "state.yaml").write_text(
        yaml.safe_dump(state, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    run_manager.finish(root)
    hist = yaml.safe_load((root / "history.yaml").read_text(encoding="utf-8"))
    assert len(hist) == 1


def test_slug_keeps_cjk_strips_unsafe():
    s = run_manager.make_slug('a/b:c*d?e"f<g>h|i j 中文')
    for ch in '/:*?"<>| ':
        assert ch not in s
    assert "中文" in s
    assert run_manager.make_slug("") == "untitled"


def test_cli_status_json(root):
    run_manager.start(root, topic="t", mode="wechat")
    proc = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "run_manager.py"),
         "--root", str(root), "status", "--json"],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stderr
    data = json.loads(proc.stdout)
    assert data["status"] == "active"
    assert data["steps"]["env"] == "pending"
