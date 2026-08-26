---
name: plaud-daily-recap
description: Build Abraham's daily Plaud meeting recap. Use when asked for the Plaud recap, a daily meeting recap, "what did Plaud capture today", or when the scheduled 1pm Plaud Daily Recap Routine fires. Every Plaud recording arrives in his inbox as an email - processed meeting notes in the body, raw transcript attached. This skill fetches the day's Plaud emails, extracts them with plaud_recap.py, and composes the recap in the house meeting-intelligence format. Email is read-only - never send, forward, or delete anything.
---

# Plaud Daily Recap

Goal: one recap covering every meeting Abraham's Plaud recorder captured on the
target day. Source of record is his inbox: each recording arrives as one email
with the processed meeting notes in the body and the raw transcript attached
(txt / docx / srt / vtt, occasionally pdf or audio).

## 0. Date and timezone

Target day = **today in `America/Los_Angeles`** unless a different date was
asked for. The 1pm run covers everything received from local midnight to run
time. Do not use the container clock's date directly - it is usually UTC.

## 1. Fetch the day's Plaud emails

Use whatever email connector tools this session has (Gmail; Outlook via ms365 if
his mail moves there). Check with ToolSearch for `gmail` / `mail` / `outlook`
tools first.

- Search the inbox for messages **received on the target day** whose sender or
  subject contains `plaud` (senders are typically `@plaud.ai` /
  Plaud-app share addresses). Widen to a plain subject search for the meeting
  titles if the sender filter finds nothing but Abraham says meetings happened.
- For each hit, save into a work folder (e.g. `./plaud_inbox/`):
  - **Preferred:** the full raw message as an `.eml` file (this preserves
    attachments and headers and is what `plaud_recap.py` parses).
  - **Fallback** (connector can't export raw): save the body as
    `NN-<slug>.body.html` and download each attachment next to it. In this
    mode skip step 2's parsing and arrange the same output shape by hand:
    one folder per meeting with `email_summary.md`, `transcript.txt`,
    `attachments/`.

**If no email connector tools are available in this session**, do not guess or
fabricate. Produce and deliver the recap anyway, stating plainly: inbox access
is missing; fix is enabling the **Gmail connector** for Claude at claude.ai →
Settings → Connectors, and enabling it for Claude Code sessions. List no
meetings.

## 2. Extract

From the repo root (this file's repo):

```
python3 plaud_recap.py --source ./plaud_inbox --date <YYYY-MM-DD> --tz America/Los_Angeles
```

Output lands in `plaud_out/<date>/`: one folder per meeting
(`email_summary.md`, `transcript.txt`, `attachments/`), plus `meetings.json`
and `recap_skeleton.md`. The script only decodes and organizes - it makes no
judgment calls. `--debug` explains any skipped message; `--match`/`--all`
loosen the sender filter; `--any-date` drops the date filter.

## 3. Read the material

Read **both** the Plaud processed notes (`email_summary.md`) and the raw
transcript (`transcript.txt`) for every meeting. The raw transcript is ground
truth; Plaud's own notes are a hint, not the record. Transcripts carry
speech-recognition errors and tentative wording - treat them accordingly.

## 4. Compose the recap

Fill `recap_skeleton.md`'s structure (per meeting, then rollup):

- **Per meeting:** purpose/context; participants (only those identifiable -
  never guess); **decisions with the evidence** (quote or transcript section);
  **action items as a table with owner / due / dependency / status** - leave a
  cell blank and flag it rather than inventing an owner or date; risks,
  blockers, and open questions (including contradictory statements);
  site or workstream impact.
- **Daily rollup:** meetings captured, top actions across meetings, decisions
  of the day, risks and unresolved questions, follow-ups drafted awaiting
  approval, and gaps/data hygiene (missing transcripts, undecodable
  attachments, suspect dates or store numbers).
- Mark uncertain names, store numbers, and dates with `(?)` and surface them in
  the rollup instead of silently "fixing" them. Merge duplicate items across
  meetings rather than repeating them.
- Zero Plaud emails for the day is a **valid recap** - say so plainly, don't
  pad it.

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
