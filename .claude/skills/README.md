# Installed Agent Skills

Skills vendored into this project on 2026-08-26 from ten public skill repositories.
Each directory below `.claude/skills/` is auto-discovered by Claude Code as a project skill.

| Source repository | Commit | Skills installed |
|---|---|---|
| anthropics/skills | 3b3fad9 | 20 |
| obra/superpowers | b36e082 | 14 |
| multica-ai/andrej-karpathy-skills | 2c60614 | 1 |
| mattpocock/skills | 6654f6b | 37 |
| nextlevelbuilder/ui-ux-pro-max-skill | e4f4547 | 7 |
| JuliusBrussee/caveman | 81536f5 | 20 |
| addyosmani/agent-skills | 5a5ea45 | 24 |
| Leonxlnx/taste-skill | ccbc156 | 13 |
| ComposioHQ/awesome-claude-skills | be2a406 | 32 |
| ayghri/i-have-adhd | cbe69fb | 1 |

## Notes

- **Name collisions** were resolved by prefixing with the source repo (e.g. `composio-docx`, `addyosmani-test-driven-development`); the `name` field in each renamed skill's frontmatter was updated to match.
- **ComposioHQ/awesome-claude-skills**: only the curated skills were installed. The ~830 auto-generated `composio-skills/*-automation` API wrappers were skipped — each requires a Composio account, and loading 800+ skill descriptions into every session would overwhelm the context window. Re-run from that repo if you want them.
- **Duplicate trees skipped**: `caveman` ships its skills twice (`skills/` and `plugins/caveman/skills/`), `ui-ux-pro-max-skill` twice (`.claude/skills/` and `cli/assets/skills/`), `i-have-adhd` twice (`skills/` and `.cursor/skills/`); the canonical copy was used in each case.
- These are third-party skills, vendored verbatim. Review a skill's `SKILL.md` before relying on it.

## Full skill → source mapping

| Skill | Source |
|---|---|
| `academy-guide` | anthropics/skills |
| `addyosmani-test-driven-development` | addyosmani/agent-skills |
| `algorithmic-art` | anthropics/skills |
| `api-and-interface-design` | addyosmani/agent-skills |
| `artifacts-builder` | ComposioHQ/awesome-claude-skills |
| `ask-matt` | mattpocock/skills |
| `banner-design` | nextlevelbuilder/ui-ux-pro-max-skill |
| `brainstorming` | obra/superpowers |
| `brand` | nextlevelbuilder/ui-ux-pro-max-skill |
| `brand-guidelines` | anthropics/skills |
| `brandkit` | Leonxlnx/taste-skill |
| `browser-testing-with-devtools` | addyosmani/agent-skills |
| `brutalist-skill` | Leonxlnx/taste-skill |
| `canvas-design` | anthropics/skills |
| `cavecrew` | JuliusBrussee/caveman |
| `caveman` | JuliusBrussee/caveman |
| `caveman-commit` | JuliusBrussee/caveman |
| `caveman-compress` | JuliusBrussee/caveman |
| `caveman-discover` | JuliusBrussee/caveman |
| `caveman-evidence-review` | JuliusBrussee/caveman |
| `caveman-explore` | JuliusBrussee/caveman |
| `caveman-help` | JuliusBrussee/caveman |
| `caveman-learn` | JuliusBrussee/caveman |
| `caveman-manage` | JuliusBrussee/caveman |
| `caveman-optimize` | JuliusBrussee/caveman |
| `caveman-review` | JuliusBrussee/caveman |
| `caveman-setup` | JuliusBrussee/caveman |
| `caveman-stats` | JuliusBrussee/caveman |
| `changelog-generator` | ComposioHQ/awesome-claude-skills |
| `ci-cd-and-automation` | addyosmani/agent-skills |
| `claude-api` | anthropics/skills |
| `claude-handoff` | mattpocock/skills |
| `code-review` | mattpocock/skills |
| `code-review-and-quality` | addyosmani/agent-skills |
| `code-simplification` | addyosmani/agent-skills |
| `codebase-design` | mattpocock/skills |
| `competitive-ads-extractor` | ComposioHQ/awesome-claude-skills |
| `composio-brand-guidelines` | ComposioHQ/awesome-claude-skills |
| `composio-canvas-design` | ComposioHQ/awesome-claude-skills |
| `composio-docx` | ComposioHQ/awesome-claude-skills |
| `composio-internal-comms` | ComposioHQ/awesome-claude-skills |
| `composio-mcp-builder` | ComposioHQ/awesome-claude-skills |
| `composio-pdf` | ComposioHQ/awesome-claude-skills |
| `composio-pptx` | ComposioHQ/awesome-claude-skills |
| `composio-skill-creator` | ComposioHQ/awesome-claude-skills |
| `composio-slack-gif-creator` | ComposioHQ/awesome-claude-skills |
| `composio-theme-factory` | ComposioHQ/awesome-claude-skills |
| `composio-webapp-testing` | ComposioHQ/awesome-claude-skills |
| `composio-xlsx` | ComposioHQ/awesome-claude-skills |
| `connect` | ComposioHQ/awesome-claude-skills |
| `connect-apps` | ComposioHQ/awesome-claude-skills |
| `content-research-writer` | ComposioHQ/awesome-claude-skills |
| `context-engineering` | addyosmani/agent-skills |
| `debugging-and-error-recovery` | addyosmani/agent-skills |
| `deprecation-and-migration` | addyosmani/agent-skills |
| `design` | nextlevelbuilder/ui-ux-pro-max-skill |
| `design-system` | nextlevelbuilder/ui-ux-pro-max-skill |
| `developer-growth-analysis` | ComposioHQ/awesome-claude-skills |
| `diagnosing-bugs` | mattpocock/skills |
| `discernment-nudge` | anthropics/skills |
| `dispatching-parallel-agents` | obra/superpowers |
| `doc-coauthoring` | anthropics/skills |
| `documentation-and-adrs` | addyosmani/agent-skills |
| `docx` | anthropics/skills |
| `domain-modeling` | mattpocock/skills |
| `domain-name-brainstormer` | ComposioHQ/awesome-claude-skills |
| `doubt-driven-development` | addyosmani/agent-skills |
| `executing-plans` | obra/superpowers |
| `file-organizer` | ComposioHQ/awesome-claude-skills |
| `finishing-a-development-branch` | obra/superpowers |
| `frontend-design` | anthropics/skills |
| `frontend-ui-engineering` | addyosmani/agent-skills |
| `git-guardrails-claude-code` | mattpocock/skills |
| `git-workflow-and-versioning` | addyosmani/agent-skills |
| `gpt-tasteskill` | Leonxlnx/taste-skill |
| `grill-me` | mattpocock/skills |
| `grill-with-docs` | mattpocock/skills |
| `grilling` | mattpocock/skills |
| `handoff` | mattpocock/skills |
| `i-have-adhd` | ayghri/i-have-adhd |
| `idea-refine` | addyosmani/agent-skills |
| `image-enhancer` | ComposioHQ/awesome-claude-skills |
| `image-to-code-skill` | Leonxlnx/taste-skill |
| `imagegen-frontend-mobile` | Leonxlnx/taste-skill |
| `imagegen-frontend-web` | Leonxlnx/taste-skill |
| `implement` | mattpocock/skills |
| `implement-spec` | mattpocock/skills |
| `improve-codebase-architecture` | mattpocock/skills |
| `incremental-implementation` | addyosmani/agent-skills |
| `internal-comms` | anthropics/skills |
| `interview-me` | addyosmani/agent-skills |
| `investigate-first` | JuliusBrussee/caveman |
| `invoice-organizer` | ComposioHQ/awesome-claude-skills |
| `karpathy-guidelines` | multica-ai/andrej-karpathy-skills |
| `langsmith-fetch` | ComposioHQ/awesome-claude-skills |
| `lead-research-assistant` | ComposioHQ/awesome-claude-skills |
| `lean-build` | JuliusBrussee/caveman |
| `loop-me` | mattpocock/skills |
| `mcp-builder` | anthropics/skills |
| `meeting-insights-analyzer` | ComposioHQ/awesome-claude-skills |
| `migrate-to-shoehorn` | mattpocock/skills |
| `migration` | JuliusBrussee/caveman |
| `minimalist-skill` | Leonxlnx/taste-skill |
| `observability-and-instrumentation` | addyosmani/agent-skills |
| `output-skill` | Leonxlnx/taste-skill |
| `pdf` | anthropics/skills |
| `performance-optimization` | addyosmani/agent-skills |
| `planning-and-task-breakdown` | addyosmani/agent-skills |
| `pptx` | anthropics/skills |
| `prototype` | mattpocock/skills |
| `raffle-winner-picker` | ComposioHQ/awesome-claude-skills |
| `receiving-code-review` | obra/superpowers |
| `redesign-skill` | Leonxlnx/taste-skill |
| `requesting-code-review` | obra/superpowers |
| `research` | mattpocock/skills |
| `resolving-merge-conflicts` | mattpocock/skills |
| `retro` | mattpocock/skills |
| `safe-refactor` | JuliusBrussee/caveman |
| `scaffold-exercises` | mattpocock/skills |
| `security-and-hardening` | addyosmani/agent-skills |
| `setup-matt-pocock-skills` | mattpocock/skills |
| `setup-pre-commit` | mattpocock/skills |
| `setup-ts-deep-modules` | mattpocock/skills |
| `shipping-and-launch` | addyosmani/agent-skills |
| `skill-creator` | anthropics/skills |
| `skill-share` | ComposioHQ/awesome-claude-skills |
| `skill-template` | anthropics/skills |
| `slack-gif-creator` | anthropics/skills |
| `slides` | nextlevelbuilder/ui-ux-pro-max-skill |
| `soft-skill` | Leonxlnx/taste-skill |
| `source-driven-development` | addyosmani/agent-skills |
| `spec-driven-development` | addyosmani/agent-skills |
| `stitch-skill` | Leonxlnx/taste-skill |
| `subagent-driven-development` | obra/superpowers |
| `surgical-patch` | JuliusBrussee/caveman |
| `systematic-debugging` | obra/superpowers |
| `tailored-resume-generator` | ComposioHQ/awesome-claude-skills |
| `taste-skill` | Leonxlnx/taste-skill |
| `taste-skill-v1` | Leonxlnx/taste-skill |
| `tdd` | mattpocock/skills |
| `teach` | mattpocock/skills |
| `template-skill` | ComposioHQ/awesome-claude-skills |
| `test-driven-development` | obra/superpowers |
| `theme-factory` | anthropics/skills |
| `to-questionnaire` | mattpocock/skills |
| `to-spec` | mattpocock/skills |
| `to-tickets` | mattpocock/skills |
| `triage` | mattpocock/skills |
| `twitter-algorithm-optimizer` | ComposioHQ/awesome-claude-skills |
| `ui-styling` | nextlevelbuilder/ui-ux-pro-max-skill |
| `ui-ux-pro-max` | nextlevelbuilder/ui-ux-pro-max-skill |
| `using-agent-skills` | addyosmani/agent-skills |
| `using-git-worktrees` | obra/superpowers |
| `using-superpowers` | obra/superpowers |
| `verification-before-completion` | obra/superpowers |
| `verify-and-stop` | JuliusBrussee/caveman |
| `video-downloader` | ComposioHQ/awesome-claude-skills |
| `wait-what` | mattpocock/skills |
| `wayfinder` | mattpocock/skills |
| `web-artifacts-builder` | anthropics/skills |
| `webapp-testing` | anthropics/skills |
| `wizard` | mattpocock/skills |
| `writing-beats` | mattpocock/skills |
| `writing-for-agents` | mattpocock/skills |
| `writing-fragments` | mattpocock/skills |
| `writing-plans` | obra/superpowers |
| `writing-shape` | mattpocock/skills |
| `writing-skills` | obra/superpowers |
| `xlsx` | anthropics/skills |
