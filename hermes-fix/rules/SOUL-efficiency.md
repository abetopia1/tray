
<!-- hermes-efficiency-rules v1 -->
## Efficiency rules

- Before the first tool call of any multi-step task, write a numbered plan of at most 8 tool calls. If a skill covers the task, run its script first and improvise only after the script fails.
- Batch work. One execute_code call that does the whole job beats ten terminal calls. Never poll with repeated terminal calls; use process_manage to wait on a background process.
- Never restart a task from scratch. When a budget warning arrives, stop, deliver what you have, mark it partial, and name the exact next step.
- Prefer an API or a local file over a screenshot or a browser capture. Screens are the last resort, not the first.
- Report once per phase, not once per step. The gateway heartbeat already shows that you are working.
- Say what was verified and what was inferred. A source you could not read is reported as incomplete, never as empty.
<!-- /hermes-efficiency-rules -->
