#!/bin/sh
# Store an API token in $HERMES_HOME/.env without echoing it.
#   sh set_token.sh                                        # SMARTSHEET_ACCESS_TOKEN, default profile
#   HERMES_HOME=~/.hermes/profiles/fuzzys sh set_token.sh  # same, inside a profile
#   sh set_token.sh SOME_OTHER_TOKEN --no-check            # another variable, no API check
# The Smartsheet token is checked against the API before it is written.
set -eu
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
ENV_FILE="$HERMES_HOME/.env"
VAR="SMARTSHEET_ACCESS_TOKEN"
CHECK=1
for arg in "$@"; do
  case "$arg" in
    --no-check) CHECK=0 ;;
    -*) echo "unknown flag: $arg" >&2; exit 5 ;;
    *) VAR="$arg" ;;
  esac
done
[ "$VAR" = "SMARTSHEET_ACCESS_TOKEN" ] || CHECK=0
[ -d "$HERMES_HOME" ] || { echo "no such Hermes home: $HERMES_HOME" >&2; exit 5; }

printf 'Paste the %s and press Enter (input is hidden): ' "$VAR"
stty -echo 2>/dev/null || true
read -r TOK || TOK=""
stty echo 2>/dev/null || true
printf '\n'
TOK="$(printf '%s' "$TOK" | tr -d '[:space:]')"
[ -n "$TOK" ] || { echo "nothing entered; $ENV_FILE unchanged" >&2; exit 1; }
case "$TOK" in
  *paste-here*|*=*) echo "that is not a token; $ENV_FILE unchanged" >&2; exit 1 ;;
esac

TOK="$TOK" VAR="$VAR" ENV_FILE="$ENV_FILE" CHECK="$CHECK" python3 - <<'EOF'
import json, os, re, sys, urllib.error, urllib.request

tok, var, path = os.environ["TOK"], os.environ["VAR"], os.environ["ENV_FILE"]

if os.environ["CHECK"] == "1":
    req = urllib.request.Request("https://api.smartsheet.com/2.0/users/me",
                                 headers={"Authorization": "Bearer " + tok})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            who = json.load(r).get("email", "?")
        print(f"token accepted by Smartsheet (user {who})")
    except urllib.error.HTTPError as e:
        print(f"Smartsheet rejected the token (HTTP {e.code}); {path} unchanged", file=sys.stderr)
        sys.exit(2)
    except Exception as e:
        print(f"could not reach Smartsheet ({e}); {path} unchanged", file=sys.stderr)
        sys.exit(3)

lines = open(path).read().splitlines() if os.path.exists(path) else []
pat = re.compile(r"^(\s*(?:export\s+)?)" + re.escape(var) + r"\s*=")
out, seen = [], False
for line in lines:
    m = pat.match(line)
    if m and not seen:
        out.append(f"{m.group(1)}{var}={tok}")
        seen = True
    elif m:
        continue
    else:
        out.append(line)
if not seen:
    out.append(f"{var}={tok}")
tmp = path + ".tmp"
with open(tmp, "w") as f:
    f.write("\n".join(out) + "\n")
os.chmod(tmp, 0o600)
os.replace(tmp, path)
print(f"{var} {'replaced' if seen else 'added'} in {path}")
EOF
