#!/bin/sh
# Apply the Hermes efficiency fix on the Mac that runs Hermes.
#
#   sh apply.sh --tier fast            # keep MiniMax login, switch to the high-speed model
#   sh apply.sh --tier claude          # Claude Opus 5.5 main driver, MiniMax as fallback
#   sh apply.sh --tier fast --dry-run  # show the config diff, change nothing
#
# Options: --dry-run  --no-restart  --skip-skill  --skip-soul
#          --oauth    (claude tier: you logged in with 'hermes model' > Anthropic OAuth; that
#                      route needs Claude Max with extra-usage credits, not Pro)
# Env:     HERMES_HOME (default ~/.hermes)   HERMES_PY (python with PyYAML)
#
# POSIX sh on purpose: macOS /bin/bash is 3.2 and /bin/sh is fine for this.
# Every change is backed up first; rollback.sh restores the pre-fix backup.

set -eu

TIER=""
DRY_RUN=0
RESTART=1
DO_SKILL=1
DO_SOUL=1
OAUTH=0

while [ $# -gt 0 ]; do
  case "$1" in
    --tier) TIER="${2:-}"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    --no-restart) RESTART=0; shift ;;
    --skip-skill) DO_SKILL=0; shift ;;
    --skip-soul) DO_SOUL=0; shift ;;
    --oauth) OAUTH=1; shift ;;
    -h|--help) sed -n '2,15p' "$0"; exit 0 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
done

case "$TIER" in
  fast|claude) ;;
  *) echo "usage: sh apply.sh --tier fast|claude [--dry-run] [--no-restart] [--skip-skill] [--skip-soul] [--oauth]" >&2; exit 2 ;;
esac

die() { echo "error: $*" >&2; exit 1; }

PKG_DIR="$(cd "$(dirname "$0")" && pwd)"
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
ROOT_HOME="$HOME/.hermes"
# A profile is a separate Hermes home under ~/.hermes/profiles/<name>. Its
# gateway is the default profile's multiplexing gateway, so the restart and
# the verification commands below address the profile with -p.
PROFILE=""
case "$HERMES_HOME" in
  "$ROOT_HOME"/profiles/*) PROFILE="${HERMES_HOME#"$ROOT_HOME"/profiles/}"; PROFILE="${PROFILE%%/*}" ;;
esac
HERMES_P=""
[ -n "$PROFILE" ] && HERMES_P="-p $PROFILE "
CONFIG="$HERMES_HOME/config.yaml"
ENV_FILE="$HERMES_HOME/.env"
SOUL="$HERMES_HOME/SOUL.md"
SKILLS_DEST="$HERMES_HOME/skills"
BACKUP_DIR="$HERMES_HOME/backups/efficiency-fix"
STAMP="$(date +%Y%m%d-%H%M%S)-$$"   # the pid keeps two runs in one second from sharing a backup

command -v hermes >/dev/null 2>&1 || die "hermes is not on PATH. Open a new Terminal or run: export PATH=\"\$HOME/.local/bin:\$PATH\""
[ -d "$HERMES_HOME" ] || die "$HERMES_HOME does not exist. Run 'hermes ${HERMES_P}setup' first."
[ -f "$CONFIG" ] || die "$CONFIG not found. Run 'hermes ${HERMES_P}model' once so Hermes writes its config."

# A Python that can import PyYAML. The Hermes venv always has one.
find_python() {
  # The install lives under the root home even when a profile is the target.
  for cand in "${HERMES_PY:-}" \
              "$ROOT_HOME"/installs/*/environments/*/bin/python3 \
              "$ROOT_HOME"/installs/*/environments/*/bin/python \
              "$ROOT_HOME/hermes-agent/venv/bin/python3" \
              "$ROOT_HOME/hermes-agent/.venv/bin/python3" \
              "$ROOT_HOME/venv/bin/python3" \
              "$ROOT_HOME/.venv/bin/python3" \
              "$HOME/.hermes-agent/venv/bin/python3"; do
    if [ -n "$cand" ] && [ -x "$cand" ] && "$cand" -c 'import yaml' >/dev/null 2>&1; then
      echo "$cand"; return 0
    fi
  done
  # Unknown layout: any python3 under the root home that can import yaml.
  for cand in $(find "$ROOT_HOME" -maxdepth 6 -type f -name python3 -path '*/bin/*' 2>/dev/null | head -40); do
    if [ -x "$cand" ] && "$cand" -c 'import yaml' >/dev/null 2>&1; then
      echo "$cand"; return 0
    fi
  done
  launcher="$(command -v hermes)"
  if command -v python3 >/dev/null 2>&1; then
    real="$(python3 -c 'import os,sys; print(os.path.realpath(sys.argv[1]))' "$launcher" 2>/dev/null || echo "$launcher")"
    cand="$(dirname "$real")/python3"
    if [ -x "$cand" ] && "$cand" -c 'import yaml' >/dev/null 2>&1; then
      echo "$cand"; return 0
    fi
    if python3 -c 'import yaml' >/dev/null 2>&1; then
      echo "python3"; return 0
    fi
  fi
  return 1
}

PY="$(find_python)" || die "no Python with PyYAML found under $ROOT_HOME. Point HERMES_PY at Hermes's own interpreter, for example: HERMES_PY=\"\$(find \$HOME/.hermes -name python3 -path '*/bin/*' | head -1)\" sh apply.sh ...   or run: python3 -m pip install pyyaml"

echo "== Hermes efficiency fix: tier=$TIER  home=$HERMES_HOME${PROFILE:+  profile=$PROFILE}  python=$PY"
if [ "$DRY_RUN" -eq 1 ]; then
  echo "== dry run: nothing will be written"
fi

# 1. Backups
if [ "$DRY_RUN" -eq 0 ]; then
  mkdir -p "$BACKUP_DIR"
  cp "$CONFIG" "$BACKUP_DIR/config.yaml.$STAMP"
  [ -f "$SOUL" ] && cp "$SOUL" "$BACKUP_DIR/SOUL.md.$STAMP"
  [ -f "$ENV_FILE" ] && cp "$ENV_FILE" "$BACKUP_DIR/env.$STAMP"
  # LAST names the first, pre-fix backup. A second apply keeps it.
  [ -f "$BACKUP_DIR/LAST" ] || printf '%s\n' "$STAMP" > "$BACKUP_DIR/LAST"
  echo "== backup written: $BACKUP_DIR/*.$STAMP (rollback target: $(cat "$BACKUP_DIR/LAST"))"
fi

# 2. API key for the claude tier (never echoed, never logged)
if [ "$TIER" = "claude" ]; then
  if [ "$OAUTH" -eq 1 ]; then
    echo "== --oauth: skipping the API key; Hermes will use the Anthropic OAuth login from 'hermes model'"
  elif grep -q '^ANTHROPIC_API_KEY=' "$ENV_FILE" 2>/dev/null; then
    echo "== ANTHROPIC_API_KEY already present in $ENV_FILE"
  elif [ "$DRY_RUN" -eq 1 ]; then
    echo "== would ask for ANTHROPIC_API_KEY and store it in $ENV_FILE"
  else
    key="${ANTHROPIC_API_KEY:-}"
    if [ -z "$key" ]; then
      printf 'Paste your Anthropic API key (input hidden, from console.anthropic.com): '
      stty -echo 2>/dev/null || true
      read -r key
      stty echo 2>/dev/null || true
      echo
    fi
    [ -n "$key" ] || die "no API key given. Alternative: 'hermes model' > Anthropic OAuth (Claude Max with extra-usage credits), then re-run with --oauth."
    umask 077
    if [ -s "$ENV_FILE" ] && [ -n "$(tail -c 1 "$ENV_FILE")" ]; then
      printf '\n' >> "$ENV_FILE"
    fi
    printf 'ANTHROPIC_API_KEY=%s\n' "$key" >> "$ENV_FILE"
    chmod 600 "$ENV_FILE"
    unset key
    echo "== ANTHROPIC_API_KEY stored in $ENV_FILE (mode 600)"
  fi
fi

# 3. Merge the overlays into config.yaml (prints the diff)
echo "== config.yaml changes:"
set +e
if [ "$DRY_RUN" -eq 1 ]; then
  "$PY" "$PKG_DIR/merge_config.py" --config "$CONFIG" --overlays "$PKG_DIR/overlays" --tier "$TIER" --dry-run
else
  "$PY" "$PKG_DIR/merge_config.py" --config "$CONFIG" --overlays "$PKG_DIR/overlays" --tier "$TIER"
fi
rc=$?
set -e
case "$rc" in
  0|3) ;;
  *) die "merge_config.py failed (exit $rc). config.yaml is unchanged; backup at $BACKUP_DIR" ;;
esac

# 4. Operating rules appended to SOUL.md (once; guarded by a marker)
if [ "$DO_SOUL" -eq 1 ]; then
  if [ ! -f "$SOUL" ]; then
    # Hermes seeds SOUL.md on first start. Creating it here would make these
    # rules the agent's whole identity, so wait for the seeded file instead.
    echo "== $SOUL not found; rules skipped. Start Hermes once, then re-run apply.sh."
  elif grep -q 'hermes-efficiency-rules v1' "$SOUL" 2>/dev/null; then
    echo "== SOUL.md already carries the efficiency rules"
  elif [ "$DRY_RUN" -eq 1 ]; then
    echo "== would append efficiency rules to $SOUL"
  else
    cat "$PKG_DIR/rules/SOUL-efficiency.md" >> "$SOUL"
    echo "== efficiency rules appended to $SOUL"
  fi
fi

# 5. The brief skills: fuzzys-cos-brief (two-tracker brief, one script) and
#    cos-daily-brief (the full morning brief: one collector, one writing step)
if [ "$DO_SKILL" -eq 1 ]; then
  for SKILL_SRC in "$PKG_DIR"/skills/*/; do
    SKILL_NAME="$(basename "$SKILL_SRC")"
    SKILL_DEST="$SKILLS_DEST/$SKILL_NAME"
    if [ "$DRY_RUN" -eq 1 ]; then
      echo "== would install skill $SKILL_NAME to $SKILL_DEST"
      continue
    fi
    mkdir -p "$SKILL_DEST/scripts"
    cp "$SKILL_SRC/SKILL.md" "$SKILL_DEST/SKILL.md"
    for f in "$SKILL_SRC"/scripts/*; do
      [ -f "$f" ] && cp "$f" "$SKILL_DEST/scripts/"
    done
    if [ -f "$SKILL_SRC/config.example.json" ]; then
      cp "$SKILL_SRC/config.example.json" "$SKILL_DEST/config.example.json"
      [ -f "$SKILL_DEST/config.json" ] || cp "$SKILL_SRC/config.example.json" "$SKILL_DEST/config.json"
    fi
    echo "== skill installed: $SKILL_DEST (config.json kept if it already existed)"
  done
  if [ "$DRY_RUN" -eq 0 ]; then
    if ! grep -q '^SMARTSHEET_ACCESS_TOKEN=' "$ENV_FILE" 2>/dev/null; then
      echo "   note: SMARTSHEET_ACCESS_TOKEN is not in $ENV_FILE yet; the brief skill needs it."
      echo "   Smartsheet > Personal Settings > API Access > Generate, then:"
      echo "   HERMES_HOME=\"$HERMES_HOME\" sh $PKG_DIR/set_token.sh"
    fi
  fi
fi

# 6. Restart the gateway so the new config is live. A profile is served by the
#    default profile's multiplexing gateway, so that is the one to restart;
#    starting a second gateway inside the profile would fight over the bot.
if [ "$DRY_RUN" -eq 0 ] && [ "$RESTART" -eq 1 ]; then
  echo "== restarting the default gateway"
  HERMES_HOME="$ROOT_HOME" hermes gateway restart || echo "   gateway restart returned non-zero; run 'hermes gateway status' and 'hermes ${HERMES_P}doctor'"
fi

if [ "$DRY_RUN" -eq 1 ]; then
  echo
  echo "Dry run complete. Nothing was changed. Re-run without --dry-run to apply."
  exit 0
fi

cat <<MSG

Done. Verify in this order:
  1. hermes ${HERMES_P}doctor                      # auth + config sanity
  2. hermes ${HERMES_P}config get model.default    # expect $( [ "$TIER" = claude ] && echo claude-opus-5-5 || echo MiniMax-M2.7-highspeed )
  3. Run the brief once from Terminal, inside this profile:
       hermes ${HERMES_P}chat --oneshot -q "Run the Fuzzy's Chief of Staff brief with the fuzzys-cos-brief skill"
     Expect the brief in about 2-3 minutes and at most 3 tool calls.
     (The skill needs SMARTSHEET_ACCESS_TOKEN in $ENV_FILE; HERMES_HOME="$HERMES_HOME" sh $PKG_DIR/set_token.sh stores it.)
  4. After the next long task, run:  HERMES_HOME="$HERMES_HOME" sh $PKG_DIR/diagnose/collect.sh
     and send me the report it writes.
  5. For the full morning brief (cos-daily-brief skill, one collector + one writing step) and the
     cron swap, see README.md, "The daily brief, rebuilt".
Rollback at any time:  HERMES_HOME="$HERMES_HOME" sh $PKG_DIR/rollback.sh   (restores the pre-fix backup)
MSG
