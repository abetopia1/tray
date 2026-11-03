# Expert builder

A meta prompt. It turns a short brief into the system prompt for a Claude
"expert", one of the domain specialists in Abraham's prompt library. The
output is one copyable block plus a few lines of notes. It descends from the
"Lyra v3" meta prompt posted publicly in 2026, rewritten for current Claude
models and for how this library is actually used. The changes are listed
below.

`SKILL.md` is the whole prompt. One file serves three homes.

## Use

### Claude Project

Paste everything in `SKILL.md` below the frontmatter, from the line
`# Expert builder` to the end, into the Project's custom instructions. Then
describe the expert you want in the chat. A detailed brief, or "just build
it", gets the block straight away. A thin brief gets up to three numbered
questions with defaults in brackets.

### Claude Code

The skill is scoped to this repository. In a session here, type
`/expert-builder <brief>` or ask for an expert in plain words.

### Hermes

```sh
cp -R .claude/skills/expert-builder ~/.hermes/skills/
# or, for a profile:
cp -R .claude/skills/expert-builder ~/.hermes/profiles/fuzzys/skills/
```

The frontmatter already carries the Hermes metadata. The skill is not wired
into `hermes-fix/apply.sh` because that package is the efficiency fix and
this skill is unrelated to it.

## Changes from Lyra v3

| Change | Why |
|---|---|
| The persona and credentials ("Lyra, a senior prompt engineer") are gone. The role line says what the prompt does. | Role-play credentials do nothing on current Claude models. The Fable 5 prompting guide lists them as noise. |
| The language toggle and the French tag names are gone. English throughout. Language is a field of the brief. | The original was a French prompt translated halfway. Its default was `fr` while its identity section demanded English, and its tag names were French while a rule said they were English. |
| Three ranked priorities (relevance, then accuracy, then no fabrication) became three required standards plus one tie-break: an honest gap beats a plausible guess. | Accuracy and no-fabrication are the same axis. Ranking relevance above them lets a plausible guess win. The tie-break is the rule from the Hermes work, where a missing source is incomplete, never empty. |
| Nine mandatory framing questions and "never generate before" became "ask only what the brief leaves open and would change the expert", with defaults in brackets. "Just build it" is honored. | Nine questions every time cost a round trip for answers that have sensible defaults. The brief table carries those defaults. |
| "Accuracy takes precedence over speed, the expert may think longer" is dropped. | Thinking depth is a platform setting. The original's own note said so one section later. |
| The toggle block (langue, balisage, web, citations, cadrage) folded into the brief table. | Configuration switches inside a chat prompt are one more thing to maintain. Defaults in the table do the same job. |
| Tags are English and four of them are optional (`data`, `guardrails`, `style`, `language`). | The smallest prompt that keeps the controls. A section exists because the domain needs it, not because the skeleton lists it. |
| Added the "reported" label, a source hierarchy, four recurring output shapes, and a pause rule before anything that sends or changes external state. | These are the patterns Abraham's mature prompts already use (source-of-truth hierarchy, facts versus inference, decision artifacts, draft-only guardrails). |
| Added an optional `style` block for experts that run outside Abraham's Claude account. | His global style guide already covers claude.ai. Hermes and the API do not see it. |
| The audit gained three red flags: a section that restates the account style guide, a section that exists only because the skeleton lists it, two rules at the same rank that collide. | Those were the padding the original could not catch. |
| Kept as they were: XML framing with the reason stated, the split between prompt structure and output format, no scripted chain of thought, no "hide your reasoning", filled examples, the self-check, one block plus notes. | These were the good bones. |

On the XML question the post raised. The tags are not placebo and not magic.
They matter where sections are long enough that the model has to tell them
apart, and where an example or a data block needs a hard boundary. A short
prompt does fine with headings.

## Tests

Two cases live under `evals/`, in the layout `claude plugin eval` reads.

| Case | Checks |
|---|---|
| `rms-story-reviewer` | A detailed brief with "just build it" yields one block, XML sections, a filled example of the verdict and findings, the knowledge labels, and no scripted reasoning. |
| `vague-brief-asks-few-questions` | A one-line brief yields at most four numbered questions with bracketed defaults, or a block with every assumption listed. |

Run them from the skill directory with the Claude Code CLI. These are billed
model runs.

```sh
cd .claude/skills/expert-builder && claude plugin eval .
```

Both cases were run once by hand on 2026-11-03 with a fresh agent that saw
only the skill text. Both passed their graders. The two replies are kept
verbatim in `references/example.md`.

## Files

| Path | Purpose |
|---|---|
| `SKILL.md` | the meta prompt, with frontmatter for Claude Code and Hermes |
| `README.md` | this file |
| `references/example.md` | the two test briefs and the replies they produced |
| `evals/*/` | the two test cases: `prompt.md`, `case.yaml`, `graders/` |
