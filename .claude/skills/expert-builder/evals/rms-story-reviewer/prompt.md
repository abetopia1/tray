---
tags: [expert-builder]
max_turns: 10
timeout_seconds: 600
allowed_tools: [Read, Glob, Grep, Skill]
---

Build me an expert that reviews LA County RMS user stories against my authoring standards. The standards are these. Project nomenclature is used consistently. Every story has a clear actor and business outcome. Functional requirements are grounded in evidence from transcripts or legacy documents. Acceptance criteria are testable. Open questions are listed instead of invented behavior. Technical implementation choices are not smuggled into a business requirement unless the source requires them. Audience is me. It runs as a Claude Project. Stories arrive pasted in or as an Azure DevOps export. Output is a verdict of ready or not ready, then findings that point at the line they refer to, and a rewritten story only when I ask for one. Just build it, no questions.
