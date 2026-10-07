#!/bin/sh
# Read-only Hermes diagnostic bundle. Writes one markdown report and prints its path.
#   sh collect.sh            # last 3 days
#   sh collect.sh --days 7
set -u
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
DIR="$(cd "$(dirname "$0")" && pwd)"
DAYS=3
[ "${1:-}" = "--days" ] && DAYS="${2:-3}"
OUT_DIR="$HERMES_HOME/cache/diagnostics"
mkdir -p "$OUT_DIR"
OUT="$OUT_DIR/hermes-diagnostic-$(date +%Y%m%d-%H%M%S).md"

section() { printf '\n## %s\n\n```\n' "$1"; }
endsection() { printf '```\n'; }

{
  echo "# Hermes diagnostic, $(date)"
  section "versions"
  hermes --version 2>&1 </dev/null
  sw_vers 2>/dev/null
  python3 --version 2>&1
  endsection
  section "hermes doctor"
  hermes doctor 2>&1 </dev/null
  endsection
  section "hermes prompt-size"
  hermes prompt-size 2>&1 </dev/null
  endsection
  section "config.yaml (lines with key/token/secret/password dropped)"
  grep -ivE 'api_key|token|secret|password' "$HERMES_HOME/config.yaml" 2>&1
  endsection
  section "cron jobs"
  hermes cron list 2>&1 </dev/null
  endsection
  section "skills installed"
  ls "$HERMES_HOME/skills" 2>&1
  endsection
  section "errors.log (last 60 lines)"
  tail -n 60 "$HERMES_HOME/logs/errors.log" 2>&1
  endsection
  section "session timeline (longest session, last $DAYS days)"
  python3 "$DIR/hermes_timeline.py" --days "$DAYS" 2>&1
  endsection
  section "recent sessions"
  python3 "$DIR/hermes_timeline.py" --list --days "$DAYS" 2>&1
  endsection
} > "$OUT" 2>&1

echo "$OUT"
