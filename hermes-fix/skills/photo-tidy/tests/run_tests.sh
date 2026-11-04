#!/bin/sh
# End-to-end test of the folder pipeline on synthetic photos. No real photo
# is read. Needs a python with the skill's libraries: pass it as $1 or let
# the skill's .venv be used.
#
#   sh run_tests.sh [PYTHON]
set -eu
HERE="$(cd "$(dirname "$0")" && pwd)"
SKILL="$(cd "$HERE/.." && pwd)"
S="$SKILL/scripts"
PY="${1:-$SKILL/.venv/bin/python3}"
[ -x "$PY" ] || { echo "no python at $PY; run sh $SKILL/setup.sh or pass one"; exit 2; }
export PT_NO_VENV=1
W="$(mktemp -d)"
trap 'rm -rf "$W"' EXIT
fail() { echo "FAIL: $*"; exit 1; }
need() { grep -q "$2" "$1" || fail "$3 (expected '$2' in $1)"; }

"$PY" "$HERE/make_fixture.py" "$W/fixture" >/dev/null
cat > "$W/config.json" <<JSON
{"source": {"mode": "folder", "folder": "$W/fixture"}, "run_root": "$W/runs", "workers": 2,
 "junk": {"screenshot_min_age_days": 0}, "naming": {"enabled": false},
 "searches": [{"q": "sharm", "min_events": 1}, {"q": "iceland", "min_events": 1}, {"q": "cairo may 2024", "min_events": 1}]}
JSON
CFG="--config $W/config.json"
find "$W/fixture" -type f | sort > "$W/before.txt"

echo "1 scan"
"$PY" "$S/pt_scan.py" $CFG > "$W/scan.out"
need "$W/scan.out" "COUNTS total=73 photos=72 videos=1 dated=73" "scan counts"
RUN="$(sed -n 's/^RUN_DIR=//p' "$W/scan.out")"

echo "2 scan in background + wait"
"$PY" "$S/pt_scan.py" $CFG --background --tag bg > "$W/bg.out"
BGRUN="$(sed -n 's/^RUN_DIR=//p' "$W/bg.out")"
i=0; while [ $i -lt 30 ]; do if "$PY" "$S/pt_scan.py" --wait "$BGRUN" --seconds 5 > "$W/wait.out"; then break; fi; i=$((i+1)); done
need "$W/wait.out" "scan: done" "background scan finished"
rm -rf "$BGRUN"

echo "3 plan"
"$PY" "$S/pt_plan.py" $CFG --run-dir "$RUN" > "$W/plan.out" 2>/dev/null
need "$W/plan.out" "SUMMARY items=73 events=8 buckets=4" "plan summary"
"$PY" - "$RUN" <<'PY'
import json, sys, os
run = sys.argv[1]
plan = json.load(open(os.path.join(run, "plan.json")))
inv = {json.loads(l)["id"]: json.loads(l) for l in open(os.path.join(run, "inventory.jsonl"))}
junk = {inv[j["id"]]["name"]: j["reasons"] for j in plan["junk"]}
for n in ("IMG_pocket_0.jpg", "IMG_white_1.jpg", "Screenshot 2024-03-01 at 10.10.00.jpg", "tiny_sticker.jpg", "IMG_blurry_0.jpg", "IMG_blurry_1.jpg"):
    assert n in junk, f"junk should hold {n}: {sorted(junk)}"
assert "IMG_sharm_00.jpg" not in junk, "a normal photo was called junk"
groups = {inv[g["keep"]]["name"]: sorted(inv[o]["name"] for o in g["others"]) for g in plan["dups"]}
assert groups.get("IMG_cairo_02.jpg") == ["WhatsApp Image 2024-05-13 at 09.12.44.jpg"], groups
assert groups.get("IMG_sharm_03.jpg") == ["IMG_sharm_03 copy.jpg"], groups
assert groups.get("IMG_sharm_05.jpg") == ["IMG_sharm_05_resent.jpg", "IMG_sharm_05_shift.jpg"], groups
for g in plan["dups"]:
    names = {inv[i]["name"] for i in [g["keep"]] + g["others"]}
    assert not (any("white" in n for n in names) and any("pocket" in n for n in names)), f"black and white frames grouped: {names}"
assert 3 <= len(plan["dups"]) <= 4, [g["kind"] for g in plan["dups"]]
titles = [e["title"] for e in plan["events"]]
assert any("Sharm" in t for t in titles) and any("Cairo" in t for t in titles), titles
assert sum(1 for e in plan["events"] if e["bucket"]) == 4
print("   plan assertions ok")
PY

echo "4 review server + decisions"
PORT=18765
"$PY" "$S/pt_review.py" serve $CFG --run-dir "$RUN" --port $PORT --background > "$W/review.out"
sleep 1.5
curl -sf "http://127.0.0.1:$PORT/" | grep -q "Photo Tidy" || fail "review page did not serve"
curl -sf "http://127.0.0.1:$PORT/api/plan" | grep -q '"events"' || fail "api/plan"
curl -sf "http://127.0.0.1:$PORT/api/inventory" | grep -q '"thumb"' || fail "api/inventory"
THUMB="$(ls "$W/runs/thumbs" | head -1)"
curl -sf -o /dev/null "http://127.0.0.1:$PORT/thumbs/$THUMB" || fail "thumb route"
curl -sf -o /dev/null -w '%{http_code}' "http://127.0.0.1:$PORT/thumbs/../plan.json" | grep -q 404 || fail "path traversal must 404"
"$PY" - "$RUN" "$PORT" <<'PY'
import json, sys, os, urllib.request
run, port = sys.argv[1], sys.argv[2]
plan = json.load(open(os.path.join(run, "plan.json")))
dec = {"junk": {j["id"]: True for j in plan["junk"]}, "dups": {g["gid"]: True for g in plan["dups"]}, "events": {}, "keep": {}}
first = next(e for e in plan["events"] if not e["bucket"])
dec["events"][first["eid"]] = {"name": "Renamed By Test"}
second = [e for e in plan["events"] if not e["bucket"]][1]
dec["events"][second["eid"]] = {"merge_prev": True}
def post(path, body):
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req).read())
assert post("/api/decisions", dec)["ok"]
saved = json.load(open(os.path.join(run, "decisions.json")))
assert saved["junk"] and not saved.get("approved_at")
r = post("/api/approve", dec)
assert r["ok"] and r["approved_at"], r
print("   decisions saved and approved")
PY
"$PY" "$S/pt_review.py" stop $CFG --run-dir "$RUN" >/dev/null

echo "5 apply (dry run, then real, with export)"
"$PY" "$S/pt_apply.py" $CFG --run-dir "$RUN" > "$W/dry.out"
need "$W/dry.out" "DRY_RUN" "dry run"
need "$W/dry.out" "Renamed By Test" "renamed event title"
"$PY" "$S/pt_apply.py" $CFG --run-dir "$RUN" --yes --export "$W/export" > "$W/apply.out"
need "$W/apply.out" "APPLIED" "apply"
[ -d "$W/fixture/Review/Junk" ] || fail "junk folder missing"
[ -d "$W/fixture/Review/Duplicates" ] || fail "duplicates folder missing"
find "$W/fixture/Review/Duplicates" -name "WhatsApp Image 2024-05-13 at 09.12.44.jpg" | grep -q . || fail "dup copy not moved"
find "$W/fixture/Review/Junk" -name "Screenshot 2024-03-01 at 10.10.00.jpg" | grep -q . || fail "screenshot not moved to junk"
ls "$W/fixture/Organized/2024/" | grep -q "Sharm" || fail "Sharm event folder missing"
ls "$W/fixture/Organized/2023/" | grep -q "Renamed By Test" || fail "renamed folder missing"
[ "$(ls "$W/fixture/Organized/2023/" | wc -l)" -eq 2 ] || fail "merge should leave two 2023 folders: $(ls "$W/fixture/Organized/2023/")"
[ "$(find "$W/export" -type f | wc -l)" -gt 40 ] || fail "export copies missing"
[ "$(find "$W/fixture" -type f | wc -l)" -eq 73 ] || fail "file count changed after apply"
"$PY" "$S/pt_apply.py" $CFG --run-dir "$RUN" --yes > "$W/apply2.out" || true
need "$W/apply2.out" "NOT_APPLIED" "second apply must refuse"
"$PY" - "$RUN" "$S" <<'PY'
import sys, os, json
sys.path.insert(0, sys.argv[2])
import pt_apply, pt_plan
placed = pt_apply.placed_ids(sys.argv[1])
moved = [json.loads(l) for l in open(os.path.join(sys.argv[1], "apply.log.jsonl")) if '"op": "move"' in l]
assert len(placed) >= len(moved) > 50, (len(placed), len(moved))
assert pt_plan.parse_name('{"name": "Beach Day"}') == "Beach Day"
assert pt_plan.parse_name('Sure! {"name": "Family Iftar"} there you go') == "Family Iftar"
assert pt_plan.parse_name('```json\n{"name": "Old Cairo Walk"}\n```') == "Old Cairo Walk"
assert pt_plan.parse_name('Tundra Brake Job\nmore') == "Tundra Brake Job"
print("   placed_ids and parse_name ok")
PY

echo "6 undo"
"$PY" "$S/pt_undo.py" $CFG --run-dir "$RUN" > "$W/undo_dry.out"
need "$W/undo_dry.out" "DRY_RUN" "undo dry run"
"$PY" "$S/pt_undo.py" $CFG --run-dir "$RUN" --yes > "$W/undo.out"
need "$W/undo.out" "UNDONE ok=" "undo"
grep -q "failed=0" "$W/undo.out" || fail "undo had failures: $(cat "$W/undo.out")"
find "$W/fixture" -type f | sort > "$W/after.txt"
cmp -s "$W/before.txt" "$W/after.txt" || { diff "$W/before.txt" "$W/after.txt" | head; fail "undo did not restore the folder exactly"; }
[ "$(find "$W/export" -type f 2>/dev/null | wc -l)" -eq 0 ] || fail "export copies not removed"

echo "7 search"
"$PY" "$S/pt_search.py" $CFG --run-dir "$RUN" > "$W/search.out" || true
need "$W/search.out" "RESULT 3/3" "searches: $(cat "$W/search.out")"
"$PY" "$S/pt_search.py" $CFG --run-dir "$RUN" -q "nothing like this" > "$W/search2.out" || true
need "$W/search2.out" "MISS" "a miss is reported"

echo "8 watch"
cp "$W/fixture/IMG_sharm_01.jpg" "$W/fixture/IMG_newphone_01.jpg"
"$PY" "$S/pt_watch.py" $CFG > "$W/watch.out"
need "$W/watch.out" "NEW=1" "watch finds one new file"
"$PY" "$S/pt_watch.py" $CFG --run --no-llm > "$W/watch2.out" 2>/dev/null
need "$W/watch2.out" "SUMMARY items=1" "watch planned the new file"
NEWRUN="$(sed -n 's/^RUN_DIR=//p' "$W/watch2.out" | tail -1)"
grep -q '"prior_keep": true' "$NEWRUN/plan.json" || fail "new copy should match the earlier run's photo"

echo "9 no delete path outside pt_undo"
if grep -nE "os\.remove|os\.unlink|shutil\.rmtree|send2trash|delete media item|delete every|unlinkat" "$S"/pt_scan.py "$S"/pt_plan.py "$S"/pt_review.py "$S"/pt_watch.py "$S"/pt_search.py "$S"/pt_common.py | grep -v "^$S/pt_apply.py"; then fail "a delete call appeared outside pt_apply/pt_undo"; fi
echo "PASS: all steps"
