---
name: plaud-daily-recap
description: Build Abraham's daily Plaud meeting recap. Use when asked for the Plaud recap, a daily meeting recap, "what did Plaud capture today", or when the scheduled 1pm Plaud Daily Recap Routine fires. Every Plaud recording arrives as a [Plaud-AutoFlow] email in the PLAUD AI folder of his Dine Brands Outlook mailbox (ms365 connector) - processed meeting notes in the body, raw transcript attached. This skill fetches the window's Plaud emails, extracts them with plaud_recap.py, and composes the recap in the house meeting-intelligence format. Email is read-only - never send, forward, or delete anything.
---

# Plaud Daily Recap

Goal: one recap covering every meeting Abraham's Plaud recorder captured.
Each recording arrives as one email with the processed meeting notes in the
body and the raw transcript attached (txt / docx / srt / vtt, occasionally
pdf or audio).

**Source of record: the `PLAUD AI` folder in Abraham's Dine Brands Outlook
mailbox (the "DINE" account, reached through the ms365 connector).** Mail
rules file every `[Plaud-AutoFlow]` delivery there, so it never shows in an
inbox view. Known shape of these emails: sender displays as `PLAUD.AI`
(no-reply@plaud.ai), subject `[Plaud-AutoFlow] MM-DD <meeting type>: <title>`,
one or more attachments (~120-220 KB), often several per day. The body
starts with a corporate banner - "[CAUTION] This email originated from
outside Dine..." - which is mail-gateway noise, not meeting content; ignore
it. His Gmail (sidimohtadi@gmail.com / login@sidimohtadi.com) carries the
same stream only through 2026-05-18 - it is history, not the live source.

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

Find the mail tools with ToolSearch (`outlook` / `ms365` / `mail`; tool name
prefixes change between sessions - search by keyword, and remember the ms365
server may register under an opaque id prefix).

- **Primary:** in the DINE (Outlook/ms365) mailbox, list the messages in the
  **`PLAUD AI` folder** received **since yesterday 1:00pm PT**. If the tools
  can't address a folder by name, search the mailbox for subject
  `[Plaud-AutoFlow]` in that window instead - the folder is just where the
  rule files them. Exhaust pagination either way.
- **Secondary check (cheap, do it):** search Gmail for `{from:plaud
  subject:plaud}` in the same window, in case anything is still delivered
  there. Skip anything already fetched from Outlook (same subject + time =
  same message).
- For each hit, save into a work folder (e.g. `./plaud_inbox/`):
  - **Preferred:** the full raw message as an `.eml` file (raw MIME export;
    this preserves attachments and headers and is what `plaud_recap.py`
    parses).
  - **Fallback** (connector can't export raw): save the body as
    `NN-<slug>.body.html` and download each attachment next to it. In this
    mode skip step 2's parsing and arrange the same output shape by hand:
    one folder per meeting with `email_summary.md`, `transcript.txt`,
    `attachments/`. The recap format in step 4 is self-contained, so no
    generated skeleton is needed.

**If the ms365/Outlook tools are missing from the session**, do not guess or
fabricate, and do not fall back to Gmail-only silently (Gmail's stream ended
2026-05-18, so a Gmail-only run under-reports). Produce and deliver the
recap anyway, stating plainly: the DINE mailbox is unreachable. The fix has
two parts, both needed for scheduled runs: (1) authorize the **ms365
connector** at claude.ai → Settings → Connectors; (2) make sure the "Plaud
Daily Recap" Routine itself carries the ms365 (and Gmail) connector grants -
recreate it from a session that actually holds those tools, since a Routine
created without the grants fires sessions without them. List whatever the
reachable sources actually show, labeled as partial.

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
