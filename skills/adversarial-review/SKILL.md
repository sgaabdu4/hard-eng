---
name: adversarial-review
description: Independently challenge prepared engineering work with the opposite model when the user explicitly requests an adversarial review.
disable-model-invocation: true
argument-hint: "Plan, diagnosis, diff, or proof to challenge"
---

# Adversarial Review

## Contract

- Trigger = user explicitly requests an adversarial review.
- Input = prepared plan | diagnosis | diff | test or release proof + repository root.
- Output = adjudicated findings + coverage + unknowns; implementation forbidden.
- External reviewer output = advisory evidence; host verification owns truth.
- Workflow = read [workflow.md](references/workflow.md) before running.

## Route

| Active model family | Independent reviewer | Fixed effort |
|---|---|---|
| OpenAI GPT in Codex | Claude Fable 5 via `claude -p` | `max` |
| Anthropic Claude in Claude Code | GPT-5.6 Sol via `codex exec` | `max` |

- Active family = current host model, never inferred from installed binaries.
- Unknown family = ask which reviewer to use; silent choice forbidden.
- Same-provider reviewer + fallback model/provider = forbidden.

## Boundary

- Repository + packet must be cleared for the reviewer provider before invocation; uncertainty → `question-me` → wait.
- Secret + credential + token + private key + customer or patient data = exclude.
- Fable route = verify current retention/ZDR terms; current contract may retain inputs for 30 days + does not offer Zero Data Retention.
- Reviewer access = repository read/search only.
- Reviewer mutation + hooks + plugins + MCP/connectors + browser/computer use + web search + memory + subagents = forbidden.
- Packet + output = temporary files outside the repository; commit forbidden.
- External failure = stop + report route/model/failure fingerprint; automatic retry/fallback forbidden.

## Run

1. Build the packet per [workflow.md](references/workflow.md).
2. Resolve this skill root + create one temporary directory.
3. Invoke:

   `python3 <skill-root>/scripts/run_review.py --host <codex|claude> --repo <repo> --packet <packet.json> --output <review.json>`

4. Read the complete structured output.
5. Verify every finding per [workflow.md](references/workflow.md).
6. Delete temporary packet + raw review after adjudication.

## Complete

- Each finding = `Verified | Rejected | Unknown` + host evidence.
- Verified `Critical` or `Medium` = fix/fold into plan before build or delivery; explicit deferral includes impact + owner + next action.
- Every named review area = checked with evidence | explicit unknown.
- Final = `PASS | CONCERNS | FAIL` from host adjudication; raw reviewer verdict alone never passes.
