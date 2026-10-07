# Hermes efficiency fix

Why a task Claude finishes in 3 minutes took Hermes over an hour, and the
package that fixes it. Everything here runs on the Mac that hosts Hermes.
Nothing has been applied yet; the cloud session that built this could not
reach the Mac.

## What happened

Read from the iMessage heartbeats in the screenshot:

| Clock | Iteration | Phase shown |
|---|---|---|
| 39 min | 22 / 60 | waiting for API response |
| 42 min | 23 / 60 | process_manage |
| 45 min | 25 / 60 | terminal |
| 48 min | 25 / 60 | terminal (same iteration, 3 min later) |
| 51 min | 28 / 60 | receiving stream response |
| 54 min | 28 / 60 | terminal |
| 57 min | 28 / 60 | terminal (same iteration, 6 min later) |
| 60 min | 30 / 60 | receiving stream response |
| 63 min | 31 / 60 | terminal |

Nine iterations in 24 minutes is 2.7 minutes per iteration. Claude's 3-minute
run was a handful of iterations at a few seconds each. Hermes also announced
that its first pass "exceeded its 15-minute budget" and started a "recovery
pass", which means the second half of the hour repeated the first half.

Causes, in order of weight:

1. **Model.** On September 24 Hermes was pointed at `MiniMax-M2.7` through
   OAuth as its main model, with no fallback. That is the slow reasoning
   variant. "receiving stream response" for whole 3-minute windows is the
   model generating. The high-speed variant exists on the same login and was
   never selected.
2. **Task shape.** The brief ran as open-ended exploration: terminal and
   process_manage calls to capture files and poke at trackers, re-discovered
   on every run. Claude had a connector that reads the trackers directly and
   a skill that says exactly what to do. Hermes had neither.
3. **Context bloat.** Every terminal result could add up to 50,000 characters
   to the conversation, and each later model call re-reads all of it. Context
   compression ran on the same slow model.
4. **Budget design.** The iteration cap of 60 and the 15-minute budget stop a
   run; they do not speed it up. Hermes restarted instead of delivering a
   partial result.

`diagnose/collect.sh` reconstructs the real timeline from Hermes's session
database so this diagnosis can be checked against evidence, not a screenshot.

## What the package changes

| Setting | Before | After | Why |
|---|---|---|---|
| `model.default` | MiniMax-M2.7 | tier fast: MiniMax-M2.7-highspeed; tier claude: claude-opus-5-5 | seconds per model call |
| `fallback_providers` | none | tier claude: MiniMax-M2.7-highspeed | an outage no longer stalls a run |
| `agent.reasoning_effort` | default (medium) | fast: low; claude: medium | less thinking per procedural step |
| `agent.run_budget_seconds` | unset (no limit) | 1200 | wrap-up notice at 16 min, hard end at 20 min, partial result delivered |
| `agent.max_turns` | 60 | 60 (explicit) | unchanged; the fix is seconds per iteration |
| `agent.budget_warning_ratio` | off | 0.7 | one checkpoint notice before the cap |
| `agent.turn_liveness.timeout_s` | 600 | 300 | a wedged turn is recovered in 5 min, not 10 |
| `terminal.timeout` | 180 | 120 | a hung command costs 2 min, not 3 |
| `tool_output.max_bytes` | 50000 | 20000 | smaller context, faster later calls |
| `compression.threshold` | 0.50 | 0.40 | compress earlier |
| `auxiliary.*` | main model for everything | fast: low effort; claude: Haiku 4.5 for compression, titles, approvals | side tasks stop paying the main model's latency |
| `delegation.*` | no child timeout | 600 s cap, 2 parallel, 40 iterations | a subagent cannot run away |
| `tool_loop_guardrails.hard_stop_*` | warn only | hard stop at 3 identical failures | repeated identical calls end the run |

Plus two files:

- `rules/SOUL-efficiency.md` is appended to `~/.hermes/SOUL.md`: plan in at
  most 8 tool calls, batch with execute_code, never restart, deliver partial
  work at a budget warning, APIs before screenshots.
- `skills/fuzzys-cos-brief/` is installed to `~/.hermes/skills/`: the
  two-tracker Chief-of-Staff brief as one script run (read both Smartsheet
  trackers by API, diff against the last read, print the brief). Three tool
  calls, no browser, no captures.

## Install

On the Mac, in Terminal:

```sh
cd ~/Downloads
git clone --branch claude/hermes-efficiency-fix-8d233b https://github.com/abetopia1/tray.git tray-hermes-fix
cd tray-hermes-fix/hermes-fix
sh apply.sh --tier fast --dry-run     # shows the config diff, changes nothing
sh apply.sh --tier fast               # applies, backs up, restarts the gateway
```

Pick a tier:

- `--tier fast` keeps the MiniMax login and needs nothing new. Do this today.
- `--tier claude` makes Claude Opus 5.5 the main driver with MiniMax as
  fallback. It asks for an Anthropic API key (console.anthropic.com) and
  stores it in `~/.hermes/.env`. If you would rather use your Claude Max
  login, run `hermes model`, choose Anthropic OAuth, then
  `sh apply.sh --tier claude --oauth`.

The brief skill needs a Smartsheet token once:

```sh
echo 'SMARTSHEET_ACCESS_TOKEN=paste-here' >> ~/.hermes/.env   # Smartsheet > Personal Settings > API Access
python3 ~/.hermes/skills/fuzzys-cos-brief/scripts/tracker_brief.py --show-columns
```

The second command prints the columns it detected for each tracker. Pin the
Network Stack sheet id, the key column, and the date columns in
`~/.hermes/skills/fuzzys-cos-brief/config.json` if the guesses are wrong.

## Verify

1. `hermes doctor` reports no config errors.
2. `hermes config get model.default` prints the tier's model.
3. From iMessage send `/fuzzys-cos-brief`. Expect the brief in 2 to 3 minutes.
4. After the next long task, run `sh diagnose/collect.sh` and send back the
   report path it prints. The report includes the per-step timeline and a
   model-bound or tool-bound verdict.

## Rollback

```sh
sh rollback.sh                  # config.yaml and SOUL.md back to the pre-fix backup, gateway restarted
sh rollback.sh --remove-skill   # also removes the brief skill
```

Backups live in `~/.hermes/backups/efficiency-fix/`. An API key added to
`~/.hermes/.env` is left in place.

## Files

| Path | Purpose |
|---|---|
| `apply.sh` | one-command install with backup, diff, restart |
| `rollback.sh` | restore the last backup |
| `merge_config.py` | deep-merges the overlays into config.yaml, prints the diff |
| `overlays/common.yaml` | settings shared by both tiers |
| `overlays/tier-fast.yaml`, `overlays/tier-claude.yaml` | model choice per tier |
| `rules/SOUL-efficiency.md` | operating rules appended to SOUL.md |
| `skills/fuzzys-cos-brief/` | SKILL.md, config.example.json, scripts/tracker_brief.py |
| `diagnose/collect.sh` | read-only diagnostic bundle |
| `diagnose/hermes_timeline.py` | per-step timeline from `~/.hermes/state.db` |

## Assumptions and limits

- The task in the screenshot was taken to be the Fuzzy's two-tracker brief
  ("either tracker", "captured files", "report"). The config changes and the
  SOUL rules apply to every task; only the skill is specific to that brief.
- Config keys were checked against the Hermes docs on 2026-10-07 (main
  branch). An older Hermes build may not know a key; `hermes doctor` says so,
  and an unknown key is ignored, not fatal. `hermes update` first if in doubt.
- The merge drops YAML comments from config.yaml. The backup keeps them.
- `run_budget_seconds: 1200` ends any single run at 20 minutes. For a job you
  know is longer: `hermes config set agent.run_budget_seconds 3600`.
- The Smartsheet script reads only. It never writes a cell, sends mail, or
  captures a screen.
