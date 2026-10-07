#!/bin/sh
# Restore the Hermes files apply.sh changed, from its last backup.
#   sh rollback.sh                 # restore config.yaml and SOUL.md, restart gateway
#   sh rollback.sh --remove-skill  # also delete ~/.hermes/skills/fuzzys-cos-brief
set -eu
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
BACKUP_DIR="$HERMES_HOME/backups/efficiency-fix"
REMOVE_SKILL=0
[ "${1:-}" = "--remove-skill" ] && REMOVE_SKILL=1

[ -f "$BACKUP_DIR/LAST" ] || { echo "no backup recorded in $BACKUP_DIR" >&2; exit 1; }
STAMP="$(cat "$BACKUP_DIR/LAST")"

if [ -f "$BACKUP_DIR/config.yaml.$STAMP" ]; then
  cp "$BACKUP_DIR/config.yaml.$STAMP" "$HERMES_HOME/config.yaml"
  echo "restored config.yaml from $STAMP"
fi
if [ -f "$BACKUP_DIR/SOUL.md.$STAMP" ]; then
  cp "$BACKUP_DIR/SOUL.md.$STAMP" "$HERMES_HOME/SOUL.md"
  echo "restored SOUL.md from $STAMP"
elif grep -q 'hermes-efficiency-rules v1' "$HERMES_HOME/SOUL.md" 2>/dev/null; then
  # SOUL.md did not exist before apply.sh; apply.sh created it with only the rules block.
  rm -f "$HERMES_HOME/SOUL.md"
  echo "removed SOUL.md (it did not exist before the fix)"
fi
if [ "$REMOVE_SKILL" -eq 1 ] && [ -d "$HERMES_HOME/skills/fuzzys-cos-brief" ]; then
  rm -rf "$HERMES_HOME/skills/fuzzys-cos-brief"
  echo "removed skill fuzzys-cos-brief"
fi
echo "ANTHROPIC_API_KEY (if added) stays in $HERMES_HOME/.env; delete that line by hand if you want it gone."
if command -v hermes >/dev/null 2>&1; then
  hermes gateway restart || echo "gateway restart returned non-zero; check 'hermes gateway status'"
fi
