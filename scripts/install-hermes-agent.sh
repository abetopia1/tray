#!/usr/bin/env bash
# Installs Hermes Agent (https://github.com/NousResearch/hermes-agent) into an
# isolated Python venv and links the `hermes` command onto PATH.
# Requires Python 3.11-3.13. Override install locations with
# HERMES_VENV_DIR and HERMES_BIN_DIR.
set -euo pipefail

VENV_DIR="${HERMES_VENV_DIR:-$HOME/.hermes-agent/venv}"
BIN_DIR="${HERMES_BIN_DIR:-$HOME/.local/bin}"

python3 - <<'EOF'
import sys
if not ((3, 11) <= sys.version_info[:2] < (3, 14)):
    sys.exit(f"Python 3.11-3.13 required, found {sys.version.split()[0]}")
EOF

python3 -m venv "$VENV_DIR"
"$VENV_DIR/bin/pip" install --upgrade pip hermes-agent

mkdir -p "$BIN_DIR"
ln -sf "$VENV_DIR/bin/hermes" "$BIN_DIR/hermes"

"$BIN_DIR/hermes" --version

echo
echo "Hermes Agent installed."
echo "  1. Make sure '$BIN_DIR' is on your PATH."
echo "  2. Run 'hermes setup' to configure an LLM provider (API key)."
echo "  3. Run 'hermes' to start chatting."
