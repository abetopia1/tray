---
name: cos-daily-brief
description: Daily Chief of Staff brief from all sources, 5 sections
version: 1.0.0
platforms: [macos]
metadata:
  hermes:
    tags: [fuzzys, chief-of-staff, brief, cron, read-only, work]
    category: work
    requires_toolsets: [terminal, file]
---

# Chief of Staff daily brief

Use this skill for the scheduled morning brief and whenever Abraham asks for
"the Chief of Staff brief", "the daily brief", "the morning brief" or a
re-run after a meeting. For a tracker-only question, use `fuzzys-cos-brief`
instead. The brief is read-only decision support for Abe's IT Manager role on
the Fuzzy's Toast rollout. Nothing is sent, scheduled, saved in a mailbox or
changed in a tracker.

One script collects every source in parallel with a time cap per source and
writes an evidence bundle. You read the bundle, write the brief, run the
checker, and reply with the brief. Budget: 8 tool calls, 15 minutes. The
complete brief must be in the final response; a file on disk alone is
undelivered.

## Procedure

1. Collect. One terminal call, foreground, timeout=600:

   `python3 ${HERMES_SKILL_DIR}/scripts/cos_collect.py`

   It prints `RUN_DIR=...`, `BUNDLE_PARTS=N`, one `BUNDLE_PART_n=` path per
   part, and a `LEDGER:` block. Exit 0 with BLOCKED rows in the ledger is
   normal; those sources are BLOCKED in the coverage table with the ledger's
   reason. Exit 2 or 5, or a tool timeout: reply "Brief not produced:" plus
   the last ERROR line, verbatim, and stop. One retry for a tool timeout.

2. Read. One read_file per bundle part, all issued in the same turn, each
   with a limit of 400 lines. The bundle holds everything the brief needs:
   coverage ledger, live tracker rows, the diff since the last capture, the
   horizon reconciliation, calendar, Plaud notes and excerpts, Abe's drafts.
   Read a raw transcript (one read_file, limit 400) only to quote a
   commitment exactly. Do not read snapshot JSON.

3. Captures, optional. If the bundle lists PNG captures and the brief needs
   the mailbox or Teams state, read at most two with vision, Outlook first.
   Transcribe literally. Visible rows are headers, not bodies; anything
   outside the visible area is "not captured". A truncated or failed read
   leaves the source PARTIAL.

4. Write. One write_file to `<RUN_DIR>/brief.md` with the complete brief in
   the output shape below.

5. Check. One terminal call, timeout=60:

   `python3 ${HERMES_SKILL_DIR}/scripts/cos_check.py <RUN_DIR>`

   PASS copies the brief to the Desktop and prints `DESKTOP_COPY=`. FAIL
   lists what to fix (em dashes, emoji, a missing section, a store number
   not in the live Master). Fix those items with one write_file and run the
   check once more. A second FAIL is delivered anyway with
   "CHECK FAILED: <reasons>" as the first line.

6. Deliver. The final response is the complete brief, verbatim, with the
   Desktop path on the last line.

## Output shape, fixed order

- Header. First line: coverage COMPLETE, PARTIAL or BLOCKED, then the single
  action Abe can take in two minutes, in bold. Then a short "what changed"
  block (tracker diff, new recordings, new drafts), then the coverage table
  copied from the bundle's ledger: source | capture time | status | what it
  establishes. COMPLETE only when the source was read in full; a source not
  accessed is BLOCKED with the reason; missing evidence is UNKNOWN, never
  empty.
- 1. Five highest-value actions. Table: Priority | Specific action |
  Store/project | Accountable owner | Deadline | Why it matters | Source.
  Rank: today's go-live, then a stale fact in something Abe is about to
  send, then dated escalations with a stated deadline, then leadership
  visibility. One "delegate or chase" line after the table. Do not pad to
  five.
- 2. Readiness radar. The reconciliation sentence from the bundle, quoted.
  At-risk table: store, group, FBC | planning date and install | status
  class (CONFIRMED BLOCKER, EMERGING RISK, DATE CONFLICT, CONFIG GAPS,
  WATCH) | evidence | consequence | owner and next action | latest safe
  decision point. Then this week's live sites, the 30-day slate, and
  franchisee patterns split into explicit and inferred.
- 3. Commitments. Pending, Open and At-risk tables, then today's meetings
  with times from the calendar and two useful questions per operational
  meeting.
- 4. Two-minute leadership brief as one blockquote: outcomes, exceptions,
  decisions leadership must make, next week. State the evidence basis under
  it.
- 5. Approval-ready follow-ups. Up to three, labelled LOCAL DRAFT TEXT ONLY,
  NOT SAVED IN A MAILBOX, NOT SENT. Each states status, required action,
  timing, impact, fallback. Recipients only when verified from a header,
  an invite or Abe's own draft, otherwise "address unverified". CONFIRM
  BEFORE SENDING on decision-class text. A verification and discrepancy
  table. Dates the brief introduces are labelled recommendations.
- Last line: one concrete next action.

## Rules of evidence

- Cite the source for every fact: a tracker row by store number, a
  recording by id and timestamp, a calendar event by time, a draft by file.
  Confirmed means visible in evidence; reported means a participant or
  vendor said it; inferred and recommended are labelled.
- Store numbers are 5 to 6 digits with a # prefix and must match the live
  Master by number and name; the checker rejects numbers that are not in
  the Master. Keep a literal discrepancy (a header that says 3000041 for
  #30114) as a discrepancy, never silently normalized.
- POS System = TOAST means already live, never an upcoming cutover. An MSP
  installation is network work, not the Toast cutover. A status of
  Complete with a confirmed date still in the future is an ambiguity to
  ask about, not a completion.
- Relative deadlines come from the source message date, not the run date.
- One outbound per recipient per site per day includes Abe's own drafts;
  fold a new ask into replacement text for his draft. A stale fact in
  something he is about to send outranks every finding except a live-day
  go-live.
- A same-day earlier brief on the Desktop means this is a re-run: lead with
  what changed since it, and let a new recording's first-person commitments
  outrank the tracker diff.
- A stale Scale export, an older capture or a cache fragment is dated
  evidence under its own date, never today's refresh.
- No em dashes, no emoji, anywhere. Plain hyphens and commas.

## Never

- Never send, draft into a mailbox, change a tracker or calendar, or click
  in any window. The collector takes screenshots without focus changes.
- Never delegate this to a subagent, open a browser, run a second
  collection method, or improvise a "recovery pass". If a source is
  BLOCKED, it is BLOCKED in the table.
- Never paste raw JSON, transcripts or the bundle into the reply.
- Never print a credential. Never edit config.json or .env.
