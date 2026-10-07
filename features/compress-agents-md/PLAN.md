# Compress the shared agent rules

Status: Complete

## Outcome + scope

`AGENTS.md` keeps every rule, condition, exception, command and link in fewer tokens, so each installed project's per-session instruction load shrinks. A prompt audit of the file reports any dated or duplicated wording.

Non-goals: changing any rule's meaning; editing `AGENTS.override.md`, skills or hooks.

## Repository context

Owners:
- `AGENTS.md`: shared rules; `.hooks/agent_hooks.py` installs its stripped text into every project.
- Evidence: no test asserts its wording; every path, anchor and command it names resolves (`checks.md#publication-privacy`, `testing.md`, `he/SKILL.md`, `update-pr`, `gap-issue`, the `Gap:` line in `basic_mode.py`, `SOURCE_FILE` in `update.py`).

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: The user asked on 2026-10-07 to compress `AGENTS.md` with Writing Great Skills without losing anything and to audit it with the Claude API prompt audit; merge when green is approved.

## Acceptance + steps

- [x] Every clause of the old file maps to the new file → clause map in the PR description.
- [x] The three overlapping rules on additions (before-editing, YAGNI, Additions) state each requirement once.
- [x] The startup rule drops migration-relative wording and splits into terse sub-bullets with every command and condition kept.
- [x] Full gate passes → `python3 .hooks/hard-eng.py check --base origin/main --plan-stage Complete` exits 0.

## Baseline + execution

Result: Passed
Evidence: main `6a4e86fc` passed its Hard Eng CI run; this branch starts from it unchanged.
Execution: Main agent in this checkout.

## Risks + recovery

A reworded rule could read differently to an agent; the clause map is the review aid. Token counts were not measured (no API credentials here); size fell from 5,369 to about 4,800 bytes. Recovery is reverting this branch.

## ux_reference

N/A — agent instruction text; no visual surface.

## Verification

Result: Passed
Evidence: Clause-by-clause comparison of old and new text found no dropped condition, exception, command or link.
Gate: `python3 .hooks/hard-eng.py check --base origin/main --plan-stage Complete` → exit 0.
E2E: N/A — no runtime behaviour changes; install copies the file verbatim.

Delivery target: Merge
Delivery: Pending
