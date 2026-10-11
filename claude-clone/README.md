# Claude Clone

Three small files that make Claude think, write, and prioritize like Abraham. They follow the seven-step "clone yourself inside Claude" method. The first draft was compiled on 2026-10-11 from the Sentient OS vault, so it is a strong starting point and not yet a verified self-portrait. Edit it before you trust it.

## Files

| File | Job | Budget |
|---|---|---|
| `about-me.md` | Who I am, how I think, how I write, hard no's | 2,000 to 4,000 tokens, 5,000 hard ceiling |
| `anti-ai-writing-style.md` | Banned words, banned patterns, formatting rules | fits in what the total leaves |
| `my-company.md` | Current goals, focus, what I am saying no to | under 1,000 tokens |
| `prompts/taste-interviewer.md` | 100-question interview to refine the files | not loaded into Claude |
| `prompts/voice-compiler.md` | Compresses the interview into a new about-me.md | not loaded into Claude |
| `scripts/token_budget.py` | Checks every budget and the 6,000 total | not loaded into Claude |

Current measurement from the script, using its conservative estimate.

| File | Tokens |
|---|---|
| about-me.md | about 2,400 |
| anti-ai-writing-style.md | about 1,600 |
| my-company.md | about 950 |
| total | about 5,000 |

Run the check after every edit.

```
python3 claude-clone/scripts/token_budget.py
```

## Load it into Claude

1. In Claude, open Projects and create a project named after yourself.
2. Under Project knowledge, upload `about-me.md`, `anti-ai-writing-style.md`, and `my-company.md`. Upload only those three.
3. Set the project instructions to one line. "Read about-me.md, anti-ai-writing-style.md, and my-company.md before every response, and follow them."
4. Use the most capable model available with extended thinking on.
5. Install Wispr Flow and talk instead of typing. You say more true things out loud.

Your account already carries a global style guide in Claude settings. Keep that as the baseline and let `anti-ai-writing-style.md` carry the detail, or move the detail into one place. Two overlapping guides drift apart.

## Refine it with the interview

The current files were compiled from notes, not from you talking. Run the interview when you have 90 minutes.

1. Paste `prompts/taste-interviewer.md` into a fresh chat and answer 100 questions by voice.
2. Save the transcript Claude prints at the end as `interview-transcript.md` in this folder.
3. Paste `prompts/voice-compiler.md` into another fresh chat, attach the transcript, `about-me.md`, and `anti-ai-writing-style.md`.
4. Replace `about-me.md` with the output, fold the compiler's my-company notes into `my-company.md`, and run the budget script.

## Edit me first

These lines were drafted from the vault and are the ones most likely to need a correction from you.

- Job titles in `about-me.md`, Implementations IT Manager and Sr. Information Systems Analyst.
- The "70 percent introvert" line and the strengths list.
- The vendor-dispute email quoted as a voice sample.
- The taste section. Add or cut titles, teams, and activities.
- The travel line in `my-company.md`, which says travel through October 23, 2026.
- The "Saying no to" list, which is inferred from recent behavior rather than stated by you.
- The status of Masri and the Mocka Station work.

## Keep it alive

Open this folder as an Obsidian vault, or drop it inside your existing vault. Edit the files like any note. Claude Projects does not watch a local folder, so after an edit replace the file in Project knowledge. Review `my-company.md` once a quarter and `about-me.md` whenever your answer to an interview question changes. A missed review is not a broken system.
