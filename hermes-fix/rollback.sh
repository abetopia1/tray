#!/bin/sh
# Restore the Hermes files apply.sh changed, from its last backup.
#   sh rollback.sh                 # restore config.yaml and SOUL.md, restart gateway
#   sh rollback.sh --remove-skill  # also delete the two brief skills from ~/.hermes/skills
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
SOUL="$HERMES_HOME/SOUL.md"
if [ -f "$BACKUP_DIR/SOUL.md.$STAMP" ]; then
  cp "$BACKUP_DIR/SOUL.md.$STAMP" "$SOUL"
  echo "restored SOUL.md from $STAMP"
elif grep -q 'hermes-efficiency-rules v1' "$SOUL" 2>/dev/null; then
  # No SOUL backup from the pre-fix run; strip only the rules block.
  awk '/<!-- hermes-efficiency-rules v1 -->/{skip=1} !skip{print} /<!-- \/hermes-efficiency-rules -->/{skip=0}' "$SOUL" > "$SOUL.tmp" \
    && mv "$SOUL.tmp" "$SOUL"
  echo "removed the efficiency rules block from SOUL.md"
fi
if [ "$REMOVE_SKILL" -eq 1 ]; then
  for name in fuzzys-cos-brief cos-daily-brief; do
    if [ -d "$HERMES_HOME/skills/$name" ]; then
      rm -rf "$HERMES_HOME/skills/$name"
      echo "removed skill $name"
    fi
  done
fi
# The next apply.sh starts a fresh pre-fix baseline.
rm -f "$BACKUP_DIR/LAST"
echo "ANTHROPIC_API_KEY (if added) stays in $HERMES_HOME/.env; delete that line by hand if you want it gone."
if command -v hermes >/dev/null 2>&1; then
  # Profiles are served by the default profile's gateway; restart that one.
  HERMES_HOME="$HOME/.hermes" hermes gateway restart || echo "gateway restart returned non-zero; check 'hermes gateway status'"
fi
