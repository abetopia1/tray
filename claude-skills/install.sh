#!/usr/bin/env bash
# Install the RMS skills into the user-level Claude Code skills directory
# (~/.claude/skills), making them available in EVERY project on this machine,
# not just repos that carry a .claude/skills folder.
#
# Usage:  bash claude-skills/install.sh
# Override the destination with CLAUDE_SKILLS_DIR if needed.
set -euo pipefail

SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEST_DIR="${CLAUDE_SKILLS_DIR:-$HOME/.claude/skills}"

SKILLS=(
  rms-story-authoring
  story-readiness-check
  board-mirror
  meeting-conduct
  ado-board-setup
)

mkdir -p "$DEST_DIR"
for skill in "${SKILLS[@]}"; do
  mkdir -p "$DEST_DIR/$skill"
  cp "$SRC_DIR/$skill/SKILL.md" "$DEST_DIR/$skill/SKILL.md"
  echo "installed $skill -> $DEST_DIR/$skill/SKILL.md"
done

echo
echo "Done. Start a new Claude Code session (or restart the current one) to load them."
