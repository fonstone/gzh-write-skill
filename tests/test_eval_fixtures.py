"""Golden fixtures for the L1 / prose gates, wired into pytest.

Runs the real scripts (not reimplementations) against checked-in fixtures
so a rule change that silently alters verdicts fails CI.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURES = REPO_ROOT / "evals" / "fixtures"


def _run(script, *args):
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    return subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / script), *map(str, args)],
        capture_output=True, text=True, encoding="utf-8", env=env,
    )


def _l1(fixture, mode="wechat"):
    proc = _run("l1_hard_rules.py", fixture, "--json", "--mode", mode)
    return json.loads(proc.stdout)


def test_l1_clean_fixture_passes():
    data = _l1(FIXTURES / "l1-clean.md")
    assert data["summary"]["passed"] is True, data


def test_l1_violations_fixture_fails_with_hits():
    data = _l1(FIXTURES / "l1-violations.md")
    assert data["summary"]["passed"] is False
    assert data["summary"]["total_hits"] > 0


def test_prose_clean_fixture_has_zero_failures():
    proc = _run("check_prose.py", FIXTURES / "human-prose-clean.md")
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_prose_violations_fixture_reports_failures():
    proc = _run("check_prose.py", FIXTURES / "human-prose-violations.md")
    assert proc.returncode != 0
    assert (proc.stdout or "").strip(), "failing run must report the offending sentences"
