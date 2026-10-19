"""Regression: CLI output must not crash on GBK (legacy cp936) consoles.

The preview/report printers use emoji; a plain Windows console defaults to
GBK and used to raise UnicodeEncodeError mid-command. The CLI now
reconfigures its streams with errors="replace" so execution and exit
codes are never broken by console encoding.
"""

import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CLI = REPO_ROOT / "toolkit" / "cli.py"


def test_preview_survives_gbk_console(tmp_path):
    md = tmp_path / "a.md"
    md.write_text("# 标题\n\n一段正文。\n", encoding="utf-8")
    out = tmp_path / "preview.html"
    env = {**os.environ, "PYTHONIOENCODING": "gbk"}
    proc = subprocess.run(
        [sys.executable, str(CLI), "preview", str(md), "--no-open", "-o", str(out)],
        capture_output=True, env=env,
    )
    assert proc.returncode == 0, proc.stderr.decode("utf-8", errors="replace")
    assert out.exists()
