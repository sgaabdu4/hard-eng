---
name: triage
description: Triage issues and external PRs into roles, verification status, and agent-ready briefs.
user-invocable: true
disable-model-invocation: true
---

# Triage

Move issues and external PRs through the repo's triage state machine.

Load `references/workflow.md` before triage.

Owns category/state roles, issue or PR verification, durable agent briefs, and
out-of-scope notes for rejected enhancement requests.
