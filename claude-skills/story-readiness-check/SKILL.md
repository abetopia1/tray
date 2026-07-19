---
name: story-readiness-check
description: Pre-delivery review gate for an RMS user story. Run before presenting a story, delivering a .docx, proposing a state move, calling a story "ready" or "refined," or handing anything to the PO or QA, even if the user only asks to "finalize" or "clean up" a story. Merges the self-review pass and the final checklist into one gate.
---

# Story Readiness Check

Run every item. A story is not "ready" with any item failing or unaddressed.

## Review pass
1. **Coverage.** Every requirement group maps to at least one AC. Format A: every choice requirement has both the does and does-not scenario. Format B: the constant spine is present and complete for the story type (create vs edit), including the delete sub-list on edit stories and the calculated-fields line only where an auto-calculated field exists.
2. **Live verification.** Step through each requirement against the running RMS: field names and labels verbatim, UI locations in nomenclature, format strings exact. Anything unverifiable is written functionally or flagged, never guessed.
3. **Nomenclature pass.** Every named element uses the CLAUDE.md Section 3 terms (form group not group form, main grid not grid/tables, basic form not basic/group forms).
4. **No fabrication, defect discipline.** No invented values. Broken behavior seen in a walkthrough is logged as a defect against the parent story, never written as a requirement.
5. **Flag integrity.** Inline [Michael to Confirm] flags match the consolidated Items list one for one. A story with any open flag is never proposed for Signed Off / Approved for Development. Hard gate.
6. **Source hygiene.** The authoritative data source is named and attached, with the correct workbook revision (same-filename revisions replaced, not assumed). Stale extracts (e.g. pivot_fields_RMS.xlsx) are not cited. Stale duplicate drafts are identified for retirement.
7. **Familiarity.** The requirements can be presented line by line without reading from the screen.

## Final checklist
- [ ] Title matches the ADO item.
- [ ] Reference line present where applicable, stating what the story is NOT.
- [ ] Narrative in As-a / I-want / so-that form (semicolon chaining for merged needs).
- [ ] Requirements grouped under bold headers, all shall, all WHAT-not-HOW.
- [ ] Cross-cutting behavior marked as applying across the entire application, and referenced (not restated) from related stories.
- [ ] Format matches the CLAUDE.md Section 6 selection rule and mirrors a real sibling.
- [ ] AC covers every requirement group; positive and negative paths where applicable.
- [ ] Values verified against live RMS or flagged; FY examples current (FY 2026 - 2027).
- [ ] No em-dashes; no fabricated values; no propagated live-story typos.
- [ ] One .docx per story per the file conventions; validated (validate.py) and visually checked (PDF rasterization).
- [ ] Delivered to /mnt/user-data/outputs/.
