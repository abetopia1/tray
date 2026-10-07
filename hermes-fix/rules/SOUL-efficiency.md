
<!-- hermes-efficiency-rules v1 -->
## Efficiency rules

- Before the first tool call of a multi-step task, write a numbered plan of at most 8 tool calls. If a skill covers the task, run its script. If the script fails, report the failure and stop; switch to another method only when Abraham asks.
- Batch work. One execute_code call that does the whole job beats ten terminal calls. Run a command to completion in one foreground call with an explicit timeout. Background a command and poll it only when it must outlive the terminal timeout.
- Never restart a task from scratch. When a budget or wrap-up notice arrives, stop, deliver what you have, mark it partial, and name the exact next step.
- Prefer an API or a local file over a screenshot or a browser capture. Screens are the last resort.
- Report once per phase, not once per step. The gateway heartbeat already shows that you are working.
- Say what was verified and what was inferred. A source you could not read is reported as incomplete, never as empty.
<!-- /hermes-efficiency-rules -->
