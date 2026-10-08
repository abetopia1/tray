# Hermes efficiency fix

A task Claude finishes in 3 minutes took Hermes over an hour. This package
says why and fixes it. Everything here runs on the Mac that hosts Hermes;
the cloud session that built it cannot reach the Mac, so `apply.sh` is the
install.

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
run was a handful of iterations at a few seconds each. Six of the nine
samples landed inside a tool phase, and iterations 25 and 28 each sat in
`terminal` for 3 minutes or more, which matches commands running into the
180-second terminal timeout. Three samples caught the model generating or
waiting on the API. Hermes also announced that its first pass "exceeded its
15-minute budget" and started a "recovery pass". That budget and the restart
were the model's own plan, not a Hermes setting, and they mean the second
half of the hour repeated the first half.

Four causes, each fixed by a different part of the package:

1. **Task shape.** The brief ran as open-ended exploration. Terminal and
   process_manage calls captured files and poked at trackers, re-discovered
   on every run, and some of them hung until the timeout. Claude had a
   connector that reads the trackers directly and a skill that says exactly
   what to do. Hermes had neither. The skill in this package fixes that.
2. **Model.** On September 24 Hermes was pointed at `MiniMax-M2.7` through
   OAuth as its main model, with no fallback. That is the slow reasoning
   variant. The high-speed variant exists on the same login and was never
   selected. The config overlay fixes that.
3. **Context bloat.** Every terminal result could add up to 50,000
   characters to the conversation, and each later model call re-reads all of
   it. Context compression ran through the main model's route. The overlay
   caps tool output, compresses earlier, and routes side tasks elsewhere.
4. **No wrap-up discipline.** Hermes had no wall-clock budget configured, so
   nothing told the model to stop exploring and deliver. The SOUL rules and
   the run budget notice fix that.

The split between model time and tool time is a reading of nine samples, not
a measurement. `diagnose/collect.sh` reconstructs the real timeline from
Hermes's session database so the ranking can be checked against evidence.

### Measured on the Mac

The first diagnostic (October 8, fuzzys profile) settled the ranking. The
longest run of the previous three days was an 83-minute cron turn on
`gpt-6.1-sol` through the Codex route at `reasoning_effort: ultra`.

| Measure | Value |
|---|---|
| time waiting on the model | 93% (16 calls, 4m50s average) |
| longest single model call | 72m50s, a silent Codex hang that Hermes retried by resending the whole 0.9 MB payload |
| largest tool result | 192,716 chars, one screenshot read by `vision_analyze` |
| request payload by the end | 1.7 MB (today's run), compaction pass 1m37s |
| identical tool calls repeated | 15 |

So the two-hour briefs were model-bound, and the model was slow because
every call carried megabytes of screenshots and tool output. The claude tier
plus the output caps address exactly that. One more thing the diagnostic
showed: a provider switch leaves `model.api_mode: codex_responses` behind,
and Hermes applies it to whatever provider is named. The overlays now clear
it.

## What the package changes

| Setting | Before (Hermes default or the Sept 24 setup) | After | Why |
|---|---|---|---|
| `model.default` | MiniMax-M2.7 | tier fast: MiniMax-M2.7-highspeed; tier claude: claude-opus-5-5 | seconds per model call |
| `fallback_providers` | none | tier claude: MiniMax-M2.7-highspeed | an outage no longer stalls a run |
| `agent.reasoning_effort` | default (medium) | fast: low; claude: medium | less thinking per procedural step |
| `agent.run_budget_seconds` | unset (feature off) | 1200 | one wrap-up notice at 16 min and hung provider calls cut to half the remaining budget; not a hard stop; resets on every message |
| `agent.max_turns` | 60 | 60 (explicit) | unchanged; the only hard ceiling on a run |
| `agent.budget_warning_ratio` | off | 0.7 | one checkpoint notice before the cap |
| `agent.turn_liveness.timeout_s` | 600 | 300 | a wedged turn is recovered in 5 min, not 10 |
| `terminal.timeout` | 180 | 120 | a hung command costs 2 min, not 3 |
| `tool_output.max_bytes` | 50000 | 20000 | smaller context, faster later calls |
| `compression.threshold` | 0.50 | 0.40 | compress earlier |
| `auxiliary.*` | provider auto | fast: low effort for side tasks; claude: Haiku 4.5 for compression and approvals | side tasks stop paying the main model's latency |
| `delegation.*` | no inactivity cap | 600 s inactivity cap, 40 iterations per subagent | a stalled subagent is abandoned |
| `tool_loop_guardrails.hard_stop_after` | 5 / 8 / 5 (gateway already hard-stops) | 3 / 5 / 4 | a replay loop ends sooner, and the model still gets one warning first |

Two files come with the overlay.

- `rules/SOUL-efficiency.md` is appended to `~/.hermes/SOUL.md`. The rules
  are to plan in at most 8 tool calls, batch with execute_code, run commands
  to completion in the foreground, never restart, deliver partial work at a
  budget warning, and prefer APIs over screenshots. Subagents started with
  delegate_task do not load SOUL.md, so the skill below also forbids
  delegating the brief.
- `skills/fuzzys-cos-brief/` is installed to `~/.hermes/skills/`. It runs the
  two-tracker Chief-of-Staff brief as one script. The script reads the All
  Sites Master and the Network Stack tracker by API, diffs them against the
  last delivered brief, and prints the brief. Three tool calls, no browser,
  no captures.

## Install

On the Mac, in Terminal:

```sh
cd ~/Downloads && git clone https://github.com/abetopia1/tray.git tray-hermes-fix
sh tray-hermes-fix/hermes-fix/apply.sh --tier fast     # backs up, applies, restarts the gateway
```

Add `--dry-run` to the second command to see the config diff without
changing anything.

Pick a tier.

- `--tier fast` keeps the MiniMax login and needs nothing new. Do this today.
- `--tier claude` makes Claude Opus 5.5 the main driver with MiniMax as
  fallback. It asks for an Anthropic API key (console.anthropic.com) and
  stores it in `~/.hermes/.env`. The Claude subscription route works only on
  Claude Max with extra usage enabled and credits purchased, because Hermes
  bills those credits and never the base allowance, and Claude Pro cannot use
  it at all. With that in place, run `hermes model`, choose Anthropic OAuth,
  then `sh apply.sh --tier claude --oauth`. Without it, use the API key.

The brief skill needs a Smartsheet token once (Smartsheet > Personal
Settings > API Access):

```sh
sh tray-hermes-fix/hermes-fix/set_token.sh      # prompts for the token with input hidden, checks it, writes ~/.hermes/.env
python3 ~/.hermes/skills/fuzzys-cos-brief/scripts/tracker_brief.py --show-columns
```

The second command prints the columns it found for each tracker. The sheet
ids and key columns are already pinned in
`~/.hermes/skills/fuzzys-cos-brief/config.json` (All Sites Master keyed by
`a6 Original Restaurant Number`, Network Stack by
`Original Restaurant Number`). Fix them there if the printout disagrees, and
add date columns if the detected list looks wrong.

## Profiles

A Hermes profile is a separate home under `~/.hermes/profiles/<name>` with
its own config, `.env`, SOUL.md, and skills. The fix only touches the home
it is pointed at, so a profile that should run the brief needs its own
apply. Point `HERMES_HOME` at the profile:

```sh
HERMES_HOME=~/.hermes/profiles/fuzzys sh apply.sh --tier fast
HERMES_HOME=~/.hermes/profiles/fuzzys sh set_token.sh
hermes -p fuzzys chat --oneshot -q "Run the Fuzzy's Chief of Staff brief with the fuzzys-cos-brief skill"
```

The script knows a profile home when it sees one. It restarts the default
profile's gateway, which serves every profile, instead of starting a second
gateway inside the profile, and it prints its verification commands with
`-p <name>`. A profile whose bot credential is a copy of the default's is
parked by that gateway and gets no messages, so run the brief from Terminal
as above, or give the profile its own line with `hermes -p fuzzys photon
setup`. Rollback and the diagnostic take the same `HERMES_HOME`.

## Verify

1. `hermes doctor` reports no config errors.
2. `hermes config get model.default` prints the tier's model.
3. From iMessage send `/fuzzys-cos-brief`, or from Terminal run the
   `hermes chat --oneshot` line above. Expect the brief in 2 to 3 minutes.
4. After the next long task, run `sh diagnose/collect.sh` and send back the
   report path it prints. The report includes the per-step timeline of the
   slowest turn and a model-bound or tool-bound verdict.

## Rollback

```sh
sh rollback.sh                  # config.yaml and SOUL.md back to the pre-fix backup, gateway restarted
sh rollback.sh --remove-skill   # also removes the brief skill
```

Backups live in `~/.hermes/backups/efficiency-fix/`. Every apply writes a
timestamped copy, and rollback restores the first one, taken before the fix,
even after a second apply. An API key added to `~/.hermes/.env` is left in
place.

## Files

| Path | Purpose |
|---|---|
| `apply.sh` | one-command install with backup, diff, restart |
| `rollback.sh` | restore the pre-fix backup |
| `set_token.sh` | store the Smartsheet token in `.env` with hidden input and an API check |
| `merge_config.py` | deep-merges the overlays into config.yaml, prints the diff |
| `overlays/common.yaml` | settings shared by both tiers |
| `overlays/tier-fast.yaml`, `overlays/tier-claude.yaml` | model choice per tier |
| `rules/SOUL-efficiency.md` | operating rules appended to SOUL.md |
| `skills/fuzzys-cos-brief/` | SKILL.md, config.example.json, scripts/tracker_brief.py |
| `diagnose/collect.sh` | read-only diagnostic bundle |
| `diagnose/hermes_timeline.py` | per-turn timeline from `~/.hermes/state.db` |

## Assumptions and limits

- The task in the screenshot was taken to be the Fuzzy's two-tracker brief
  ("either tracker", "captured files", "report"). The config changes and the
  SOUL rules apply to every task; only the skill is specific to that brief.
- Config keys were checked against the Hermes docs on 2026-10-07 (main
  branch). An older Hermes build may not know a key; `hermes doctor` says so,
  and an unknown key is ignored, not fatal. Run `hermes update` first if in
  doubt.
- The merge drops YAML comments from config.yaml. The backup keeps them.
- `run_budget_seconds: 1200` asks the model to wrap up at 16 minutes. It does
  not end the run; the only hard ceiling is `agent.max_turns`. For a job you
  know is longer, run `hermes config set agent.run_budget_seconds 3600`.
- The Smartsheet script reads only. It never writes a cell, sends mail, or
  captures a screen.
