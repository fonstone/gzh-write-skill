#!/usr/bin/env python3
"""Per-article run state for the GzhWrite pipeline.

Each article gets its own run directory (``output/runs/<run_id>/``) with a
``state.yaml`` tracking the eight pipeline steps, artifacts, flags and
topic metadata. This provides:

- resumability (``status`` / ``list`` answer "继续上次" without guessing);
- isolation (concurrent articles never overwrite each other);
- a single writer for the ``history.yaml`` entry at pipeline finish
  (``finish`` builds the entry from run state instead of hand-appending
  YAML — including the trailing-newline edge case that used to corrupt
  appends).

Any command failure exits non-zero with a readable message; the SKILL.md
pipeline treats a failure as a degraded step and falls back to its legacy
behaviour (flat output/ files + manual history write).

Usage:
    python3 scripts/run_manager.py start --topic "选题" --mode tech --framework "全景架构型"
    python3 scripts/run_manager.py step write completed
    python3 scripts/run_manager.py update --patch '{"artifacts": {"draft": "output/x.md"}}'
    python3 scripts/run_manager.py status --json
    python3 scripts/run_manager.py list
    python3 scripts/run_manager.py finish
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent

STEPS = ["env", "topic", "framework", "write", "seo", "visual", "layout", "wrapup"]
STATUSES = ["pending", "in_progress", "completed", "failed", "skipped"]

_UNSAFE_RE = re.compile(r'[\\/:*?"<>|\s]+')


def make_slug(topic: str, max_len: int = 40) -> str:
    """Filesystem-safe slug; keeps CJK, strips Windows-unsafe characters."""
    slug = _UNSAFE_RE.sub("-", (topic or "").strip()).strip("-")
    slug = slug[:max_len].strip("-")
    return slug or "untitled"


def runs_dir(root: Path) -> Path:
    return Path(root) / "output" / "runs"


def _write_state(run_dir: Path, state: dict) -> None:
    (run_dir / "state.yaml").write_text(
        yaml.safe_dump(state, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


_REQUIRED_TYPES = {
    "run_id": str,
    "status": str,
    "mode": str,
    "steps": dict,
    "topic": dict,
    "artifacts": dict,
    "flags": dict,
}


def load_run(run_dir: Path) -> dict:
    path = Path(run_dir) / "state.yaml"
    if not path.exists():
        raise FileNotFoundError(f"no state file at {path}")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValueError(f"malformed state file {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"malformed state file {path}: not a run state mapping")
    for key, typ in _REQUIRED_TYPES.items():
        if not isinstance(data.get(key), typ):
            raise ValueError(
                f"malformed state file {path}: missing or invalid '{key}' "
                f"(expected {typ.__name__})"
            )
    missing_steps = [s for s in STEPS if s not in data["steps"]]
    if missing_steps:
        raise ValueError(f"malformed state file {path}: missing steps {missing_steps}")
    return data


def latest_run(root: Path) -> Path | None:
    base = runs_dir(root)
    if not base.is_dir():
        return None
    candidates = [
        d for d in base.iterdir() if d.is_dir() and (d / "state.yaml").exists()
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda d: (d / "state.yaml").stat().st_mtime)


def _resolve_run(root: Path, run_id: str | None) -> Path:
    if run_id:
        run_dir = runs_dir(root) / run_id
        if not run_dir.is_dir():
            raise FileNotFoundError(f"run not found: {run_id}")
        return run_dir
    run_dir = latest_run(root)
    if run_dir is None:
        raise FileNotFoundError("no runs found; run `start` first")
    return run_dir


def start(root: Path, topic: str = "", mode: str = "wechat",
          framework: str = "") -> Path:
    now = datetime.now()
    base_id = f"{now:%Y%m%d-%H%M%S}-{make_slug(topic)}"
    run_id = base_id
    run_dir = runs_dir(root) / run_id
    counter = 2
    while run_dir.exists():
        run_id = f"{base_id}-{counter}"
        run_dir = runs_dir(root) / run_id
        counter += 1
    run_dir.mkdir(parents=True)
    state = {
        "version": 1,
        "run_id": run_id,
        "status": "active",
        "created": f"{now:%Y-%m-%d %H:%M:%S}",
        "finished": None,
        "mode": mode,
        "topic": {
            "title": topic or "",
            "keywords": [],
            "source": "用户指定" if topic else "",
        },
        "framework": framework or "",
        "material_gate": None,
        "steps": {s: "pending" for s in STEPS},
        "artifacts": {"draft": None, "article": None, "sources": None, "preview": None},
        "flags": {},
        "last_error": None,
    }
    _write_state(run_dir, state)
    return run_dir


def set_step(root: Path, name: str, status: str, run_id: str | None = None,
             error: str | None = None) -> dict:
    if name not in STEPS:
        raise ValueError(f"unknown step '{name}' (valid: {', '.join(STEPS)})")
    if status not in STATUSES:
        raise ValueError(f"unknown status '{status}' (valid: {', '.join(STATUSES)})")
    run_dir = _resolve_run(root, run_id)
    state = load_run(run_dir)
    state["steps"][name] = status
    if status == "failed" and error:
        state["last_error"] = error
    _write_state(run_dir, state)
    return state


def _deep_merge(dst: dict, patch: dict) -> None:
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(dst.get(key), dict):
            _deep_merge(dst[key], value)
        else:
            dst[key] = value


def update(root: Path, patch: dict, run_id: str | None = None) -> dict:
    if not isinstance(patch, dict):
        raise ValueError("patch must be a JSON object (mapping)")
    run_dir = _resolve_run(root, run_id)
    state = load_run(run_dir)
    _deep_merge(state, patch)
    _write_state(run_dir, state)
    return state


def _history_entry(state: dict) -> dict:
    flags = state.get("flags") or {}
    return {
        "date": (state.get("created") or "")[:10],
        "title": (state.get("topic") or {}).get("title") or "(未命名)",
        "topic_source": (state.get("topic") or {}).get("source") or "用户指定",
        "topic_keywords": (state.get("topic") or {}).get("keywords") or [],
        "paper_sources": flags.get("paper_sources"),
        "output_file": (state.get("artifacts") or {}).get("article")
        or (state.get("artifacts") or {}).get("draft") or "",
        "framework": state.get("framework") or "",
        "enhance_strategy": flags.get("enhance_strategy"),
        "material_gate": state.get("material_gate") or "passed",
        "word_count": flags.get("word_count"),
        "media_id": flags.get("media_id"),
        "writing_persona": flags.get("writing_persona"),
        "dimensions": flags.get("dimensions") or [],
        "closing_type": flags.get("closing_type"),
        "composite_score": flags.get("composite_score"),
        "writing_config_snapshot": flags.get("writing_config_snapshot"),
        "stats": None,
    }


def _entry_key(entry: dict) -> tuple:
    return (entry.get("date"), entry.get("title"), entry.get("output_file"))


def _append_history(root: Path, entry: dict) -> None:
    hist = Path(root) / "history.yaml"
    if hist.exists():
        text = hist.read_text(encoding="utf-8")
        if text.strip():
            existing = yaml.safe_load(text)
            if existing is not None and not isinstance(existing, list):
                raise ValueError("history.yaml is not a YAML list")
            # Crash-retry guard: never append an identical trailing entry.
            if (
                isinstance(existing, list) and existing
                and isinstance(existing[-1], dict)
                and _entry_key(existing[-1]) == _entry_key(entry)
            ):
                return
            if not text.endswith("\n"):
                # Regression: "stats: null" without a trailing newline used to
                # glue the new entry to the previous one.
                text += "\n"
        block = yaml.safe_dump([entry], allow_unicode=True, sort_keys=False)
        hist.write_text(text + block, encoding="utf-8")
    else:
        hist.write_text(
            yaml.safe_dump([entry], allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )


def finish(root: Path, run_id: str | None = None) -> dict | None:
    """Complete a run and append its history entry.

    Idempotent: a run already marked completed returns ``None`` without
    touching history (retries after an interrupted finish never duplicate
    the archive entry).
    """
    run_dir = _resolve_run(root, run_id)
    state = load_run(run_dir)
    if state.get("status") == "completed":
        return None
    entry = _history_entry(state)
    _append_history(root, entry)          # history first: state only flips on success
    state["status"] = "completed"
    state["finished"] = f"{datetime.now():%Y-%m-%d %H:%M:%S}"
    _write_state(run_dir, state)
    return entry


# --- CLI --------------------------------------------------------------------

def _print_state(state: dict) -> None:
    print(f"run:      {state.get('run_id', '?')}")
    print(f"status:   {state.get('status', '?')}    mode: {state.get('mode', '?')}")
    if state.get("topic", {}).get("title"):
        print(f"topic:    {state['topic']['title']}")
    if state.get("framework"):
        print(f"framework:{state['framework']}")
    steps = state.get("steps", {})
    print("steps:    " + "  ".join(f"{k}={v}" for k, v in steps.items()))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="GzhWrite per-article run state")
    ap.add_argument("--root", default=str(REPO_ROOT), help="project root")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_start = sub.add_parser("start", help="create a new run")
    p_start.add_argument("--topic", default="")
    p_start.add_argument("--mode", default="wechat", choices=["wechat", "tech"])
    p_start.add_argument("--framework", default="")

    p_step = sub.add_parser("step", help="update one pipeline step")
    p_step.add_argument("name", choices=STEPS)
    p_step.add_argument("status", choices=STATUSES)
    p_step.add_argument("--error", default=None)
    p_step.add_argument("--run", default=None)

    p_update = sub.add_parser("update", help="deep-merge a JSON patch into state")
    p_update.add_argument("--patch", required=True)
    p_update.add_argument("--run", default=None)

    p_status = sub.add_parser("status", help="show the latest (or given) run")
    p_status.add_argument("--run", default=None)
    p_status.add_argument("--json", action="store_true")

    p_list = sub.add_parser("list", help="list all runs")
    p_list.add_argument("--json", action="store_true")

    p_finish = sub.add_parser("finish", help="complete the run and write history")
    p_finish.add_argument("--run", default=None)
    p_finish.add_argument("--json", action="store_true")

    args = ap.parse_args(argv)
    root = Path(args.root)

    try:
        if args.cmd == "start":
            run_dir = start(root, topic=args.topic, mode=args.mode,
                            framework=args.framework)
            print(run_dir.name)
        elif args.cmd == "step":
            state = set_step(root, args.name, args.status, args.run, args.error)
            print(f"{args.name}={state['steps'][args.name]}")
        elif args.cmd == "update":
            state = update(root, json.loads(args.patch), args.run)
            print(f"updated run {state['run_id']}")
        elif args.cmd == "status":
            run_dir = _resolve_run(root, args.run)
            state = load_run(run_dir)
            if args.json:
                print(json.dumps(state, ensure_ascii=False, indent=2))
            else:
                _print_state(state)
        elif args.cmd == "list":
            base = runs_dir(root)
            rows = []
            if base.is_dir():
                for d in sorted(base.iterdir()):
                    if (d / "state.yaml").exists():
                        try:
                            st = load_run(d)
                            rows.append({
                                "run_id": st.get("run_id", d.name),
                                "status": st.get("status"),
                                "mode": st.get("mode"),
                                "created": st.get("created"),
                                "topic": (st.get("topic") or {}).get("title", ""),
                            })
                        except (ValueError, FileNotFoundError):
                            rows.append({"run_id": d.name, "status": "corrupt"})
            if args.json:
                print(json.dumps(rows, ensure_ascii=False, indent=2))
            else:
                for r in rows:
                    print(f"{r['run_id']}  [{r.get('status')}]  {r.get('topic', '')}")
        elif args.cmd == "finish":
            entry = finish(root, args.run)
            if entry is None:
                print("already finished (no-op)")
            elif args.json:
                print(json.dumps(entry, ensure_ascii=False, indent=2))
            else:
                print(f"finished: {entry['title']}")
    except (ValueError, FileNotFoundError, json.JSONDecodeError, OSError) as exc:
        print(f"run_manager error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
