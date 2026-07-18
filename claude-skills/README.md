# RMS Claude Skills

Five skills for RMS user-story work, kept here so they can be installed on any
machine or uploaded to claude.ai. This folder is deliberately **not**
`.claude/skills/` — these are meant to be installed at the user level, not
scoped to this project.

| Skill | Purpose |
| --- | --- |
| `rms-story-authoring` | Drafting procedure for RMS user stories (Format A/B skeletons, field specs, docx pipeline) |
| `story-readiness-check` | Pre-delivery review gate before presenting or delivering a story |
| `board-mirror` | Read-only harvest of sibling stories from the Azure DevOps board before drafting |
| `meeting-conduct` | Conduct rules for RMS ceremonies and the transcript-to-recap procedure |
| `ado-board-setup` | One-time setup/repair of Azure DevOps board access (org `phlacounty`) |

## Make them available in every Claude instance (recommended)

Upload each skill to your claude.ai account: **Settings → Capabilities →
Skills → Upload skill**. Account-level skills sync to every surface signed in
to your account — claude.ai chat, the desktop app, and remote Claude Code
sessions — the same way other custom skills already do. Each skill uploads as
its `SKILL.md` (or a zip of its folder).

## Install on one machine (Claude Code CLI)

```bash
bash claude-skills/install.sh
```

This copies each skill to `~/.claude/skills/<name>/SKILL.md`, which Claude
Code loads for every project on that machine. Start a new session afterwards
to pick them up.

## Notes

- Directory names must match the `name:` field in each `SKILL.md` frontmatter.
- The skills reference an RMS project `CLAUDE.md` (nomenclature, ledger,
  format-selection rule); they are fully effective only alongside that file.
