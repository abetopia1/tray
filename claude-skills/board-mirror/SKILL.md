---
name: board-mirror
description: 'Harvest real sibling stories from the Azure DevOps board before drafting or converting any RMS story, to lock format, phrasing, and values from the most-advanced populated sibling. Use whenever board access exists and a story is about to be drafted, mirrored, reformatted, or compared against "how the team writes them." Read-only: never create, edit, move, or delete work items during a harvest.'
---

# Board Mirror (sibling harvest)

## Workflow
1. **Find the siblings.** Identify the screen/epic the new story belongs to (Funding Source, Position Management, Org Definition, Administration, Reporting & Analytics, or global/system) and query the board for stories under that area. Mirror the most-advanced sibling that is actually populated, not merely the one in the highest-sounding state.
2. **Know the family ceilings (observed, July 2026).**
   - Signed Off exists on: the Technical and Main Menu family, where 23234 and 23243 are the complete exemplars and the [Tech] items 23248/23249 are Signed-Off placeholder stubs (empty AC, never mirror them); and, as of 7/14/2026, the Funding Source enhancement cluster (24617, 24619, 24621, 24872).
   - The older Funding Source grid-page set (23215 to 23218, 23940) topped out at In QA / Refined.
   - Position Management reaches QA Complete (23214, 23794).
   - Do not filter on a state a family does not use; confirm the column-to-state mapping per family.
3. **Read the real fields.** For 2 to 3 siblings, read Description and Acceptance Criteria verbatim. Note grouping, phrasing, declarative vs Given/When/Then, and how cross-cutting features are referenced.
4. **Mirror structure and intent, not defects.** Live stories carry copy-paste residue and typos (stale Location paths, "AMOUNT AVIALABLE", "Toast message timer is worker"). The timer typo survives in QA-Complete 23794: QA sign-off validates behavior, not wording. Correct the phrasing; never propagate defects.
5. **Strongest siblings by story type:**
   - Grid-page create: 23216. Grid-page edit: 23940, with QA-Complete analog 23794.
   - Funding enhancement field stories: 24617 (Signed Off, eight-column field-spec style).
   - Admin cluster Format B: the delivered US23200 / US23201 / US24499 docs (latest revision; older Given/When/Then revisions are stale).
   - Global/system Format A: 23234, 23243.
6. **Check the nomenclature source.** If the board holds a newer nomenclature sheet, prefer it over the CLAUDE.md table and update CLAUDE.md.
7. **Verify values** (labels, format strings, timings) against live RMS or the sibling; flag anything unconfirmed.
8. **Sync back.** When the board reveals a changed pattern (new AC convention, renamed nomenclature, new grouping, new state ceiling), update the relevant CLAUDE.md section and note the source story id.

## Discovery prompts
- "List user stories under area path containing 'Funding Source', ordered by state and newest first."
- "Get work item <id> and show its Description and Acceptance Criteria fields."
- "List the children of epic/feature <id>."
- "Find work items with title or tag containing 'session', 'fiscal year', or 'login'."

## Safety
Read-only. A harvest must never cause a write. Any write (state move, tag, link, duplicate closure) happens only on explicit separate instruction, confirmed first.
