#!/bin/sh
# One-time setup for the photo-tidy skill on the Mac that runs Hermes.
#
#   sh setup.sh                # create .venv next to this file and install the libraries
#   sh setup.sh --ollama       # also pull the naming model (and the embedding model if enabled) named in config.json
#   sh setup.sh --check        # report what is installed, change nothing
#
# POSIX sh on purpose: macOS /bin/bash is 3.2. Nothing here touches a photo.

set -eu

SKILL_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV="$SKILL_DIR/.venv"
CONFIG="$SKILL_DIR/config.json"
OLLAMA=0
CHECK=0
while [ $# -gt 0 ]; do
  case "$1" in
    --ollama) OLLAMA=1; shift ;;
    --check) CHECK=1; shift ;;
    -h|--help) sed -n '2,9p' "$0"; exit 0 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
done

die() { echo "error: $*" >&2; exit 1; }

# A python3 of at least 3.10. Homebrew first, then uv's managed pythons, then PATH.
find_python() {
  for cand in /opt/homebrew/bin/python3 /opt/homebrew/bin/python3.12 /opt/homebrew/bin/python3.11 /usr/local/bin/python3 \
              "$HOME"/.local/share/uv/python/cpython-3.1[123]*/bin/python3 "$(command -v python3 || true)"; do
    [ -n "$cand" ] && [ -x "$cand" ] || continue
    if "$cand" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
      echo "$cand"; return 0
    fi
  done
  return 1
}

[ -f "$CONFIG" ] || cp "$SKILL_DIR/config.example.json" "$CONFIG"

if [ "$CHECK" -eq 1 ]; then
  echo "skill dir: $SKILL_DIR"
  echo "config:    $CONFIG"
  if [ -x "$VENV/bin/python3" ]; then
    "$VENV/bin/python3" - <<'PY'
import importlib, sys
print("venv python:", sys.version.split()[0])
for m in ("osxphotos", "PIL", "pillow_heif", "imagehash", "reverse_geocoder"):
    try:
        mod = importlib.import_module(m)
        print(f"  {m}: ok {getattr(mod, '__version__', '')}")
    except Exception as err:
        print(f"  {m}: MISSING ({err})")
PY
  else
    echo "venv: not created yet (run sh setup.sh)"
  fi
  if command -v ollama >/dev/null 2>&1; then echo "ollama: $(ollama --version 2>/dev/null | head -1)"; ollama list 2>/dev/null | head -20; else echo "ollama: not on PATH (naming falls back to rule names)"; fi
  exit 0
fi

PY="$(find_python)" || die "no python3 >= 3.10 found. Install one with: brew install python@3.12"
echo "== python: $PY"
if [ ! -x "$VENV/bin/python3" ]; then
  if command -v uv >/dev/null 2>&1; then
    uv venv --python "$PY" "$VENV"
  else
    "$PY" -m venv "$VENV"
  fi
  echo "== venv created: $VENV"
fi
echo "== installing libraries (osxphotos, Pillow, pillow-heif, ImageHash, reverse_geocoder)"
if command -v uv >/dev/null 2>&1; then
  uv pip install --python "$VENV/bin/python3" -q --upgrade pip osxphotos pillow pillow-heif imagehash reverse_geocoder
else
  "$VENV/bin/python3" -m pip install -q --upgrade pip
  "$VENV/bin/python3" -m pip install -q osxphotos pillow pillow-heif imagehash reverse_geocoder
fi
"$VENV/bin/python3" -c 'import osxphotos, PIL, pillow_heif, imagehash, reverse_geocoder; print("== libraries ok: osxphotos", osxphotos.__version__)'

if [ "$OLLAMA" -eq 1 ]; then
  command -v ollama >/dev/null 2>&1 || die "ollama is not on PATH. Install it from https://ollama.com, start it, then re-run with --ollama."
  MODEL="$("$VENV/bin/python3" -c 'import json,sys; c=json.load(open(sys.argv[1])); print(c.get("naming",{}).get("model","qwen3.5:4b"))' "$CONFIG")"
  echo "== pulling naming model $MODEL"
  if ! ollama pull "$MODEL"; then
    echo "   pull failed. Pick a tag that exists (ollama search qwen, or https://ollama.com/library/qwen3.5) and set naming.model in $CONFIG."
  fi
  EMB_ON="$("$VENV/bin/python3" -c 'import json,sys; c=json.load(open(sys.argv[1])); print("1" if c.get("embeddings",{}).get("enabled") else "0")' "$CONFIG")"
  if [ "$EMB_ON" = "1" ]; then
    EMB="$("$VENV/bin/python3" -c 'import json,sys; c=json.load(open(sys.argv[1])); print(c.get("embeddings",{}).get("model","embeddinggemma-2"))' "$CONFIG")"
    echo "== pulling embedding model $EMB"
    ollama pull "$EMB" || echo "   pull failed; set embeddings.enabled to false or fix embeddings.model in $CONFIG"
  fi
fi

cat <<MSG

Done. Next, from Terminal (so macOS asks for the Photos permission here, not inside Hermes):
  python3 $SKILL_DIR/scripts/pt_photos.py --library-info     # which library will be read, how many items
  python3 $SKILL_DIR/scripts/pt_photos.py --probe            # makes and removes a test album; expect PASS
  python3 $SKILL_DIR/scripts/pt_scan.py --limit 300          # trial scan, a minute or two
Then tell Hermes: "tidy my photos" and it follows the skill.
Config: $CONFIG   (source.mode photos reads the Mac's Photos library, which iCloud Photos syncs from the iPhone)
MSG
