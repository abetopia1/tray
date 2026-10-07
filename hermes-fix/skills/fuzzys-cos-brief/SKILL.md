---
name: fuzzys-cos-brief
description: Fuzzy's Toast two-tracker Chief-of-Staff brief in one script run
version: 1.0.0
platforms: [macos, linux]
metadata:
  hermes:
    tags: [fuzzys, smartsheet, brief, work]
    category: work
    requires_toolsets: [terminal]
---

# Fuzzy's Chief of Staff brief

Use this when Abraham asks for the Fuzzy's brief, the Chief of Staff brief,
the morning brief, "what changed in the trackers", or when a cron job attaches
this skill.

Budget: 3 tool calls, under 3 minutes. The script reads the trackers, diffs
them against the last read, and formats the brief. You do not browse, take
screenshots, open Smartsheet in a browser, or export files.

## Procedure

1. Run, in one terminal call:

   `python3 ~/.hermes/skills/fuzzys-cos-brief/scripts/tracker_brief.py`

2. Exit code 0: send the printed brief verbatim as your reply. Add nothing the
   brief does not contain. If the user asked a specific question that the brief
   answers, put a one-line answer above it.

3. Exit code other than 0: send the last error line verbatim, prefixed with
   "Brief not produced:", and stop. One retry is allowed only for exit code 3
   (network). Never work around a failed read by another method.

## Never

- Never write to a tracker, send email, or change a tracker row.
- Never start a "recovery pass" or a second approach. Partial output plus the
  exact error is the deliverable.
- Never paste raw snapshot JSON into the chat.

## One-time setup (Abraham)

- `SMARTSHEET_ACCESS_TOKEN` in `~/.hermes/.env` (Smartsheet, Personal
  Settings, API Access, Generate new access token).
- `config.json` next to this file holds the sheet IDs or names, the key column,
  and the date columns. `python3 scripts/tracker_brief.py --show-columns`
  prints what the script detected so the columns can be pinned.
