---
name: plaud-daily-recap
description: Build Abraham's daily Plaud meeting recap. Use when asked for the Plaud recap, a daily meeting recap, "what did Plaud capture today", or when the scheduled 1pm Plaud Daily Recap Routine fires. Every Plaud recording arrives in his inbox as an email - processed meeting notes in the body, raw transcript attached. This skill fetches the day's Plaud emails, extracts them with plaud_recap.py, and composes the recap in the house meeting-intelligence format. Email is read-only - never send, forward, or delete anything.
---

# Plaud Daily Recap

Goal: one recap covering every meeting Abraham's Plaud recorder captured.
Source of record is his inbox: each recording arrives as one email with the
processed meeting notes in the body and the raw transcript attached
(txt / docx / srt / vtt, occasionally pdf or audio).

## 0. Date, timezone, and covered window

All times are **`America/Los_Angeles`**. Do not use the container clock's
date directly - it is usually UTC.

The scheduled run covers the **24 hours ending at run time**: everything
received since yesterday ~1pm PT through now. Today's meetings are the body
of the recap; anything from yesterday afternoon/evening (received after
yesterday's run) is a **"Late arrivals from yesterday"** section, so no
meeting is ever skipped and none is recapped twice. For a manual ask
("recap for <date>"), cover just that date.

Scheduling note for maintainers: the Routine's cron is UTC-fixed, so its
wall-clock time drifts one hour across DST transitions; a companion one-shot
Routine flips the cron at each transition to keep 1pm Pacific.

## 1. Fetch the window's Plaud emails

Use whatever email connector tools this session has (Gmail; Outlook via ms365
if his mail moves there). Check with ToolSearch for `gmail` / `mail` /
`outlook` tools first.

- Search the inbox for messages **received since yesterday 1:00pm PT** (e.g.
  Gmail `after:`/`before:` spanning both days) whose sender or subject
  contains `plaud` (senders are typically `@plaud.ai` / Plaud-app share
  addresses). If the tool paginates, keep fetching until the result set is
  exhausted. Widen to a plain subject search for the meeting titles if the
  sender filter finds nothing but Abraham says meetings happened.
- For each hit, save into a work folder (e.g. `./plaud_inbox/`):
  - **Preferred:** the full raw message as an `.eml` file (this preserves
    attachments and headers and is what `plaud_recap.py` parses).
  - **Fallback** (connector can't export raw): save the body as
    `NN-<slug>.body.html` and download each attachment next to it. In this
    mode skip step 2's parsing and arrange the same output shape by hand:
    one folder per meeting with `email_summary.md`, `transcript.txt`,
    `attachments/`. The recap format in step 4 is self-contained, so no
    generated skeleton is needed.

**If no email connector tools are available in this session**, do not guess
or fabricate. Produce and deliver the recap anyway, stating plainly: inbox
access is missing. The fix has two parts, both needed for scheduled runs:
(1) connect/authenticate the **Gmail connector** at claude.ai → Settings →
Connectors; (2) make sure the "Plaud Daily Recap" Routine itself carries the
Gmail connector grant - recreate it from the claude.ai Routines UI or from a
session that actually holds Gmail tools, since a Routine created without the
grant fires sessions with no connector tools regardless of account settings.
List no meetings.

## 2. Extract

From the repo root (this file's repo), once per covered day:

```
python3 plaud_recap.py --source ./plaud_inbox --date <today> --tz America/Los_Angeles
python3 plaud_recap.py --source ./plaud_inbox --date <yesterday> --tz America/Los_Angeles
```

Because step 1 only fetched mail received after yesterday ~1pm, the
`<yesterday>` bundle contains exactly the late arrivals. Zero matches is not
an error: the script still writes the empty bundle and exits 0.

Output lands in `plaud_out/<date>/`: one folder per meeting
(`email_summary.md`, `transcript.txt`, `attachments/`), plus `meetings.json`
and `recap_skeleton.md`. The script only decodes and organizes - it makes no
judgment calls. `--debug` explains any skipped message; `--match`/`--all`
loosen the sender filter; `--any-date` drops the date filter. Re-runs are
safe: an existing bundle for the same day is rebuilt from scratch.

## 3. Read the material

Read **both** the Plaud processed notes (`email_summary.md`) and the raw
transcript (`transcript.txt`) for every meeting. The raw transcript is ground
truth; Plaud's own notes are a hint, not the record. Transcripts carry
speech-recognition errors and tentative wording - treat them accordingly.

## 4. Compose the recap

The canonical structure (also emitted as `recap_skeleton.md`):

- Title: `# Plaud Daily Recap — <date>`, then per meeting:
  - `## N. <title> — <HH:MM>` with **Source email** and **Raw transcript**
    lines;
  - `### Decisions` as a `| Decision | Evidence (quote or transcript section) |`
    table;
  - `### Action items` as a `| # | Action | Owner | Due | Dependency | Status |`
    table;
  - `### Risks, blockers, open questions`;
  - `### Site / workstream impact`.
- Then `## Late arrivals from yesterday` (same per-meeting structure, only if
  the `<yesterday>` bundle has meetings; omit the section otherwise).
- Then `## Daily rollup` with: meetings captured; top actions across
  meetings; decisions of the day; risks and unresolved questions; follow-ups
  drafted awaiting approval (drafts only - nothing sent); gaps / data hygiene
  (missing transcripts, undecodable attachments, suspect dates or store
  numbers).

Composition rules:

- Participants: only those identifiable in the transcript - never guess.
- Decisions need the evidence; action items need owner / due / dependency /
  status - leave a cell blank and flag it rather than inventing an owner or
  date.
- The script does not dedupe: if two emails cover the same recording (same or
  near-identical subject, overlapping transcript/notes text, received close
  together - a resend or a split notes/transcript delivery), recap them as
  **one** meeting, use the richer transcript, count it once in the rollup,
  and note the duplicate delivery under gaps/data hygiene.
- Mark uncertain names, store numbers, and dates with `(?)` and surface them
  in the rollup instead of silently "fixing" them. Merge duplicate items
  across meetings rather than repeating them.
- Zero Plaud emails for the window is a **valid recap** - say so plainly,
  don't pad it.

## 5. Deliver

1. Publish the finished recap as an Artifact (title `Plaud Daily Recap`,
   favicon 🎙️, the date prominent on the page).
2. End with a short chat summary: number of meetings, the top 3 actions, any
   blockers, and the artifact link. When this runs as a scheduled Routine,
   that closing summary is what reaches Abraham's phone/email notification -
   lead with the headline numbers.

## Hard rules

- Email is **read-only**: never send, forward, delete, archive, or mark
  anything. Anything drafted for sending is shown verbatim as a draft only.
- Never change any external record (Smartsheet, calendars, files in Drive).
- Don't turn every statement into a decision; don't resolve ambiguity by
  inventing specifics. Traceability beats polish.
