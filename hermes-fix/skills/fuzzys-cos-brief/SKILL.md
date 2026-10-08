---
name: fuzzys-cos-brief
description: Fuzzy's Smartsheet trackers brief, changes and dates
version: 1.1.0
platforms: [macos, linux]
metadata:
  hermes:
    tags: [fuzzys, smartsheet, brief, work]
    category: work
    requires_toolsets: [terminal]
---

# Fuzzy's Chief of Staff brief

Use this skill when Abraham asks for the quick Fuzzy's tracker brief, a
tracker status report, "what changed in the trackers", "check the All Sites
Master", "check the Network Stack", or anything about captured tracker
files. The full morning Chief of Staff brief (calendar, Plaud, drafts, five
sections) is the `cos-daily-brief` skill, not this one. A cron job can
attach this skill with -s.

The budget is 3 tool calls and under 3 minutes. The script reads both
trackers through the Smartsheet API, diffs them against the last delivered
brief, and prints the brief. You do not browse, take screenshots, open
Smartsheet in a browser, export files, or delegate this task to a subagent.

## Procedure

1. One terminal call, foreground, with timeout=300:

   `python3 ${HERMES_SKILL_DIR}/scripts/tracker_brief.py`

2. Exit code 0: reply with the printed brief verbatim. Add nothing the brief
   does not contain. If Abraham asked a specific question that the brief
   answers, put a one-line answer above it.

3. For any other exit code, or a tool timeout (exit 124), reply with the
   last ERROR line verbatim, prefixed with "Brief not produced:", and stop.
   One retry is allowed for exit code 3 and for a tool timeout. The error
   line names what Abraham has to fix (token, config, sheet access). That is
   his job, not yours.

## Never

- Never write to a tracker, send email, or change a tracker row.
- Never try a second method after a failed run. No browser, no screenshots,
  no "recovery pass". The error line is the deliverable.
- Never paste raw snapshot JSON into the chat.
- Never edit config.json or .env yourself.
