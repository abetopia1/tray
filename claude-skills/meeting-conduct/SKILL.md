---
name: meeting-conduct
description: Conduct rules for RMS ceremonies (internal PO review with Michael, Sprint Backlog Grooming and Refinement, walkthroughs) plus the transcript-to-recap procedure. Use when preparing for, participating in, or processing the output of any RMS meeting, including whenever a meeting transcript or recording notes are provided for summarization.
---

# Meeting Conduct

Cadence facts (Tuesday PO review, Wednesday refinement) live in CLAUDE.md Section 1.

## In the meeting
- Read only the `Requirements:` details aloud. Do not show the RMS system by default.
- Do not walk the Acceptance Criteria in grooming/refinement; validating AC against RMS is QA's responsibility.
- Show RMS only when a question needs the system for clarity.
- Make edits in real time during the meeting to preempt unsolicited QA questions.

## After the meeting (transcript handling)
Turn the transcript into a structured recap:
1. **Resolved items**, each mapped to the story whose flag it closes; note the ledger line in CLAUDE.md Section 9 to update.
2. **Open items**, each mapped to a story and, where applicable, converted to a [Michael to Confirm] flag (inline plus the Items list).
3. **Required documentation updates**: which .docx, which section, which CLAUDE.md ledger line.
4. **Board actions** (state moves, tag changes, duplicate closures) listed but not executed without confirmation.

Defect discipline applies throughout: behavior reported broken in the meeting is a defect against the parent story, never a new requirement.
