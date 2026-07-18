---
name: rms-story-authoring
description: Author or edit an RMS user story (Word .docx or ADO text). Use whenever drafting, restructuring, converting, or revising requirements and acceptance criteria for any RMS work item, including grid-page CRUD stories, Admin-cluster stories, funding enhancement field stories, and global/system stories, even if the user only says "write the story" or "update the AC." Carries the story structure, the Format A and Format B skeletons, the create/edit delta, the eight-column field specification set, data conventions, ADO paste hygiene, and the docx production pipeline.
---

# RMS Story Authoring

Facts (nomenclature, locked values, format selection rule, ledger) live in CLAUDE.md. This skill is the drafting procedure.

## 0. Before drafting
1. Confirm the format per CLAUDE.md Section 6. Format B (declarative) is the default; Format A (Given/When/Then) only for global/system behavior.
2. If board access exists, run the board-mirror skill first and ground the draft in a real sibling.
3. Identify the authoritative data source for field values (currently `Funding Sources_Minimum Essential_Final_071326.xlsx` for funding fields) and apply the precedence rule: PO email supersedes the workbook on conflict.
4. Flag anything unconfirmed rather than filling gaps. Ask before auto-adding content.

## 1. Story element order
1. **Title** on its own line: `US<number> <Short Title>`, matching the ADO work item title.
2. **Reference line**, italic: relationships, absorbed items, parent epic, and explicitly what the story is NOT (scope fences), so QA does not pull unrelated scope.
3. **Scope** section where the Admin-set template applies.
4. **User Narrative:** `As a <role>, I want <capability>, so that <benefit>.` Chain merged needs with a semicolon.
5. **`Requirements:`** bold label. Bold category headers at list level 0; shall statements nested at level 1. Where the template calls for them: eight-column field spec tables and dashed "Snippet placeholder" boxes; screenshots inserted before finalizing.
6. **`Acceptance Criteria:`** bold label; body per the selected format below.
7. **`Items for Michael to Confirm:`** consolidated list mirroring every inline flag one for one.

## 2. Writing requirements
- Group under a bold category header naming a capability (e.g. "Session Keep-Alive", "Grid System Defaults Registry").
- One testable shall sentence per statement. Outcomes and constraints, never implementation: no route parameters, polling intervals, timer libraries, component internals, or job schedules. When devs volunteer mechanisms in a walkthrough, capture the user-visible behavior they produce.
- Name UI locations with the CLAUDE.md nomenclature.
- Cross-cutting behavior gets the explicit line: "This behavior shall apply across the entire application."
- Unconfirmed value: write it functionally or flag it inline as bold `[Michael to Confirm]`, repeated in the Items list. Never invent.
- Broken behavior reported in a walkthrough: defect against the parent story, not a requirement. Write the requirement for the intended behavior.

## 3. Format B (declarative), the default

Canonical structure, locked from 23216 (create) and 23940 (edit), with 23794 (QA Complete) as the strongest edit analog:

```
US<number> <Screen>: <Action>

Reference: US #<sibling>, #<sibling>, ...

User Narrative: As a RMS user I want to <action> so that <benefit>.

Requirements:
<requirements block; the basic form is organized into named form groups>

Acceptance Criteria:   (declarative bullets, not Given/When/Then)
- User can <create/edit> via the <entry point> (the "+ Create" button for create,
  the Edit Record / pencil icon for edit).
- The "<Form Title>" basic form is shown on triggering the entry point from the main grid.
- The form contains the form groups listed in Requirements.
- Each form group contains the listed fields.
- Each field functions per requirements.
- Fields are configured/functioning for format, values, logic, and rules.
- Calculated/derived fields function per their formula.   (ONLY if an auto-calculated field exists)
- All field validation logic functions.
- A toast message is displayed on successful submission.
- The toast shows the correct message.
- The toast message timer functions for the correct display time.
- The <created/edited> record is listed and updated in the <grid location>.
- The record information is saved and retrievable.

Delete sub-list (edit-style stories only):
- Deletion validation/confirmation functions properly.
- The deletion sub-form contains all verbiage and elements.
- The user can delete Inactive records per the validation conditions.
```

**Create vs edit delta:**
- Create (23216): "+ Create" entry point; 6 form groups (no Status Management); no delete sub-list; carries the enumerated dropdown values.
- Edit (23940): Edit Record / pencil entry point; 7 form groups = the 6 plus STATUS MANAGEMENT; adds the delete sub-list and Update-button validations.
- Funding Source edit form groups (7): Funding Identity, Lifecycle Dates, Organizational Management, Financial Alignment, Source Name Hierarchy, Pass-Through Administration Logic, Status Management.
- 23794 delta (allocation edit, 4 sections): POSITION INFORMATION, FUNDING ALLOCATION, ALLOCATION TIMELINE, STATUS MANAGEMENT; entry via the pencil icon within the Details menu; the record lands in the Details menu allocation tab sub-grid, not the main grid.

**Constant spine (always present):** entry-point line; "form contains N sections" plus the section sub-list; the four "each field" lines; the three toast lines; the "listed and updated" plus "saved and retrievable" pair; the three-line delete sub-block on edit stories.
**Form-specific (fill in):** section count and names; the grid-location phrase; the conditional calculated-fields line (include only when an auto-calculated field exists, e.g. Funding Percentage: 23794 has it, 23940 does not).

**Field-value reference (from 23216; for enhancement fields the 071326 workbook is the value authority; verify currency before reuse):**
- FUND TYPE: Contract, Cooperative Agreement, Direct Payment, Federal Financial Participation, Federal Revenue, Federal Share of Cost, Federal Share of Cost (100%), Financial Impact Type, Grant, Grant Case Management, Grant ERAP, Loan, SAPC, Subsidies, Unknown.
- FUNDING SOURCE TYPE: Government (Federal, State, County, City, Tribal, Other), Public (non-profit), Private (non-profit), Private (for Profit), Other.
- Related attachments on 23216: "US 23216 COA Unit Codes" and "US 23216 and 23940 Source Name.xlsx".

**Caveat: mirror structure, not defects.** Live stories carry copy-paste residue and typos ("AMOUNT AVIALABLE", "Auto-popul;ated", "ORGANIZATION LEVELES", "Toast message timer is worker"). The timer typo survives in QA-Complete 23794: QA Complete validates behavior, not wording. Write the corrected phrasing; never propagate live defects.

## 4. Format A (Given/When/Then), global/system only
- One named scenario per bullet: bold name ending with a colon, Given/When/Then on the same line (docx style) or as labeled lines (ADO style).
- Given sets the precise testing start state; When is the single triggering action; Then is the observable result.
- One scenario per requirement group, plus alternate/negative paths. Every "user may choose X" requirement gets both the does and does-not scenario.
- Keep AC values identical to the requirements (timings, labels, format strings).

Gold standard (23263), compressed:

```
- Active Work Prevents Timeout: Given a user is authenticated and actively interacting
  with the application, when user activity occurs before the inactivity timeout is
  reached, then the session remains active and the user is not signed out.
- Warning Before Expiry: Given a user is authenticated and inactive, when the session
  reaches 2 minutes before expiration, then a session expiry warning message is
  displayed with a countdown timer and an option to extend the session.
- User Extends Session: Given the warning is displayed with the countdown running,
  when the user selects the option to extend before the countdown reaches zero, then
  the system refreshes the session and the user resumes normal usage without sign-out.
- User Does Not Extend Session: Given the warning is displayed with the countdown
  running, when the countdown reaches zero without the user extending, then the
  system automatically signs the user out.
```

Why it is the standard: grouped shall requirements (what, not how); a reference line stating what the story is not; every group covered; explicit positive and negative paths for the user's choice.

## 5. Field specification (eight-column set)
Specify every grid/form field with: **Field Name; Location/Placement; Datatype/Format; Validation; Values/Default/Initial Load; Business Rule/Logic; Data Source; Visibility.** Write each as a shall where it constrains behavior; flag anything unconfirmed. (Older Admin docs and Rochelle's fund-management draft use narrower column sets; flag the structural conflict, do not silently convert.)

Data conventions:
- Empty text fields load as "Undefined" on initial data upload; state it explicitly. Format-constrained fields (e.g. ALN XX.XXX) load blank instead; add a supersede note where the workbook says otherwise.
- Non-text fields (number, date, boolean, lookup) need an explicit default; flag if unconfirmed.
- "Lookup" means back-end-maintained selectable values administered under the Administration area. Name the maintenance source; never enumerate values you cannot confirm.
- Person fields store position or employee IDs even when the UI displays a name.
- FY examples: the FY is system-set and currently 2026 - 2027; do not reuse 2025 - 2026 examples.

## 6. ADO paste hygiene
- `[Michael to Confirm]` loses the leading `[` on paste into ADO; re-check after every paste.
- "Michael Slater-Lunsford" auto-converts to an @mention and notifies him on every save; avoid the full name in body text or break the auto-convert.
- Literal "log." can auto-link into an email address in exported text; check exported AC.

## 7. docx production pipeline
1. Generate with Node.js docx@9.6.1 (not python-docx). US Letter, 1-inch margins, Arial, real multilevel list numbering. One .docx per story: `US<number>_<Title_With_Underscores>.docx`.
2. Validate structure with validate.py (python-docx) plus zipfile inspection of `word/document.xml`.
3. Visual verification: convert to PDF via soffice, rasterize with `pdftoppm -jpeg -r 90`, view the pages.
4. Deliver to `/mnt/user-data/outputs/` for manual replacement. `/mnt/project` is read-only; copy to `/home/claude/work/` before editing.
5. Bash heredocs: single-quote the delimiter (e.g. `'EOF'`) to protect backticks inside code fences.

## 8. Finish
Run the story-readiness-check skill before presenting or delivering.
