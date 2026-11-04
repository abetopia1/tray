---
name: photo-tidy
description: Organise the iPhone photo library from the Mac, fully local, nothing deleted, every change approved and undoable
version: 1.0.0
platforms: [macos]
metadata:
  hermes:
    tags: [photos, iphone, personal, local, read-mostly]
    category: personal
    requires_toolsets: [terminal, file]
---

# Photo tidy

Use this skill when Abraham says "tidy my photos", "clean up my photos",
"organise my photo library", "apply the photo plan", "undo the photo
changes", "any new photos", or "test the photo searches". The pipeline
runs on this Mac only. The Photos library here is the iPhone's library,
synced by iCloud Photos, so albums made here appear on the phone.

Six scripts, one job each, all under `${HERMES_SKILL_DIR}/scripts/`:

| Script | What it does | Writes |
|---|---|---|
| `pt_scan.py` | inventory of every photo and video: dates, GPS, Photos labels, people, scores, a thumbnail, perceptual hashes | `RUN_DIR/inventory.jsonl`, thumbnails |
| `pt_plan.py` | junk candidates with reasons, duplicate groups with a keeper, events split by time gap and location, place names, event names from the local Ollama model (rule names when Ollama is off) | `RUN_DIR/plan.json` |
| `pt_review.py` | local review page: junk, duplicates, groups, names, approve | `RUN_DIR/decisions.json` |
| `pt_apply.py` | approved decisions become albums in a "Hermes Tidy" folder in Photos (or folder moves in folder mode), optional export copies | `RUN_DIR/apply.log.jsonl` |
| `pt_undo.py` | takes an apply back from its log | `RUN_DIR/undo.log.jsonl` |
| `pt_watch.py` | finds photos no run has seen; scans and plans just those | a new `RUN_DIR` |
| `pt_search.py` | runs Abraham's real searches against a run and reports hits | nothing |

Long steps run detached and are polled. Every `--wait` call returns within
the terminal timeout: exit 0 means done, 3 means still running (call it
again), 1 means failed (relay the last line and stop). Never restart a
step that is still running. Never run more than 8 polls in one turn; when
the eighth poll is still running, reply with the status line and the
`NEXT=` command, and continue when Abraham asks.

## Tidy (scan, plan, review)

Budget: 12 tool calls plus polls. Say once, before the first poll, that a
full scan of a large library takes 10 to 30 minutes.

1. `python3 ${HERMES_SKILL_DIR}/scripts/pt_scan.py --background` (timeout 60).
   It prints `RUN_DIR=`, `STATUS=`, `NEXT=`. Keep RUN_DIR.
2. Poll with the printed `NEXT=` line, which is
   `pt_scan.py --wait RUN_DIR --seconds 110` (timeout 120), until exit 0.
3. `python3 ${HERMES_SKILL_DIR}/scripts/pt_plan.py --run-dir RUN_DIR --background`
   (timeout 60), then poll with its `NEXT=` line until exit 0. Naming calls
   Ollama once per event; a few minutes for a few hundred events.
4. `python3 ${HERMES_SKILL_DIR}/scripts/pt_review.py serve --run-dir RUN_DIR --background`
   (timeout 30). Add `--host 0.0.0.0` when Abraham is on the phone; the
   output then has `PHONE_URL=` for the Tailscale address.
5. Reply with: the `SUMMARY` and `SAMPLE_EVENTS` lines from the plan, every
   ledger row that is BLOCKED or PARTIAL with its reason, the review URL,
   and one sentence: go through the four tabs, press Approve on the last
   one, then say "apply the photo plan". Nothing has moved yet.

A trial on part of the library: add `--limit 500` to step 1.

## Apply

Only when Abraham's own message in this conversation asks to apply.

1. `python3 ${HERMES_SKILL_DIR}/scripts/pt_apply.py --run-dir RUN_DIR` (timeout 60).
   This is a dry run. It prints `PLANNED` counts and the first albums. If it
   prints `NOT_APPLIED:` (no approval, plan changed, already applied), relay
   that line and stop.
2. `python3 ${HERMES_SKILL_DIR}/scripts/pt_apply.py --run-dir RUN_DIR --yes --background`
   (timeout 60), then poll `pt_apply.py --wait RUN_DIR --seconds 110` until
   exit 0. Add `--export DIR` only when Abraham named an export folder.
3. Reply with the `APPLIED` line, the `UNDO=` line, and: on the iPhone the
   albums are under Photos > Albums > Hermes Tidy; the Review albums hold
   the junk and duplicates and he deletes from them himself if he wants to.

If apply fails with a Photos automation error (-1743), say so and give the
Terminal command from the output; the permission belongs to the app that
runs the command, and Terminal has it from the probe.

## Undo

`python3 ${HERMES_SKILL_DIR}/scripts/pt_undo.py --run-dir RUN_DIR` shows the
steps. When Abraham's message asked for the undo, run it again with `--yes`
(timeout 600) and reply with the `UNDONE` line.

## New photos (also the cron job)

`python3 ${HERMES_SKILL_DIR}/scripts/pt_watch.py --run --background`
(timeout 60), then poll `pt_watch.py --wait RUN_DIR --seconds 110`. Reply
with the `NEW=` line, the `SUMMARY` line and the review command. `NEW=0`
is a complete answer. A cron job for this, created once by hand:

`hermes cron create "0 21 * * *" "Run the photo watcher with the photo-tidy skill and report its NEW and SUMMARY lines." --skill photo-tidy --name "Photo watcher" --deliver local`

## Search test

`python3 ${HERMES_SKILL_DIR}/scripts/pt_search.py --run-dir RUN_DIR --fields raw`
then the same with `--fields all` (timeout 120 each). Reply with both
tables and the two `RESULT` lines; the difference is what the plan's names
and places added.

## Rules

- Never delete a photo, an album, a file or a run. The scripts have no
  delete path except `pt_undo.py`, which removes only what `pt_apply.py`
  created. Never suggest a deletion command.
- Never pass `--yes` unless Abraham's message in this conversation asks
  for that action. Never edit `decisions.json`, `plan.json` or an
  inventory. Approval comes from the review page only.
- Never open a thumbnail or a photo with vision, never read `thumbs/`,
  never paste file names of photos into the reply beyond what the script
  summaries print. The pixels are for Abraham's review page, not for you.
- Never run osascript, open Photos, or touch `~/Pictures` yourself. The
  scripts are the only path.
- Never delegate to a subagent, never improvise a second method when a
  script fails. Relay the last `ERROR` line verbatim and stop.
- Say what was verified and what was inferred: a ledger row that is
  BLOCKED means that source was not read, never that it was empty.
- No em dashes, no emoji.
