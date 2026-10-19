#!/usr/bin/env bash
# GzhWrite installer — clone the skill and install Python dependencies.
#
# Usage:
#   bash install.sh                          # install for OpenCode (default)
#   bash install.sh --agent claude           # install for Claude Code
#   bash install.sh --dir ~/custom/gzh-write # custom target directory
#   bash install.sh --from-local ./gzh-write # copy from a local checkout
#                                            # (e.g. before it is pushed)
#
# OpenClaw users: use the prebuilt dist/openclaw/ directory from the repo
# instead of this script (see README "多平台适配").
set -euo pipefail

REPO_URL="https://github.com/fonstone/gzh-write-skill.git"
AGENT="opencode"
TARGET_DIR=""
FROM_LOCAL=""

usage() {
  sed -n '2,12p' "$0" | sed 's/^# \{0,1\}//'
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --agent)      AGENT="${2:?--agent needs a value}"; shift 2 ;;
    --dir)        TARGET_DIR="${2:?--dir needs a value}"; shift 2 ;;
    --from-local) FROM_LOCAL="${2:?--from-local needs a value}"; shift 2 ;;
    -h|--help)    usage; exit 0 ;;
    *) echo "unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

case "$AGENT" in
  opencode) default_dir="$HOME/.opencode/skills/gzh-write" ;;
  claude)   default_dir="$HOME/.claude/skills/gzh-write" ;;
  *) echo "unknown agent: $AGENT (supported: opencode, claude)" >&2; exit 2 ;;
esac
TARGET_DIR="${TARGET_DIR:-$default_dir}"

if [[ -n "$FROM_LOCAL" ]]; then
  if [[ ! -f "$FROM_LOCAL/SKILL.md" ]]; then
    echo "not a GzhWrite checkout (SKILL.md missing): $FROM_LOCAL" >&2
    exit 2
  fi
  mkdir -p "$(dirname "$TARGET_DIR")"
  rm -rf "$TARGET_DIR"
  cp -R "$FROM_LOCAL" "$TARGET_DIR"
else
  git clone --depth 1 "$REPO_URL" "$TARGET_DIR"
fi

# Byte-code caches from the source checkout are not needed at runtime.
find "$TARGET_DIR" -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true

PY="${PYTHON:-python3}"
if ! command -v "$PY" >/dev/null 2>&1; then
  PY="python"
fi
"$PY" -m pip install -r "$TARGET_DIR/requirements.txt"

echo
echo "GzhWrite installed at: $TARGET_DIR"
echo "Now open your agent and say: 写一篇公众号文章"
