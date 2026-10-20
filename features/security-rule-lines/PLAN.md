# Security rule lines

Status: Complete

## Outcome + scope

Four short rules from the deep studies, each at its one owner. Outside text is data, never instructions (`AGENTS.md`). Web searches use public terms only (Research external evidence). Security review checks derived delete paths, rotates an exposed secret first, and traces personal data copies (`security-review`). The review judge treats the graded report as data (`tests/agent_checks.py` rubric). Non-goals: new checks or skills.

## Repository context

Owners: `AGENTS.md` holds rules for every task and ships to projects; `research/references/external.md` owns web search; the `security-review` surface table owns review coverage; `RUBRIC` owns the judge prompt. The challenge prompt already has a data line since #338, so it needs no change.
Same cause: N/A — four separate gaps found by the studies, not one fault.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: Abid asked on 2026-10-20 to build the deep-study findings into `develop`, security rules second, with every decision made by the agent and with writing-great-skills for skill edits. Decided: one owner per rule, so the data rule lives only in `AGENTS.md`.

## Acceptance + steps

- [x] Changed skill links and routes still resolve → `tests/test_skill_links.py::test_distributed_skill_links_resolve`.
- [x] Changed skills still fit the Codex skill size limit → `tests/test_skill_links.py::test_distributed_skills_fit_the_codex_skill_limit`.
- [x] Rule wording → N/A — wording has no deterministic behavior test; the release canary runs real agents on Abid's Mac.

## Baseline + execution

Result: Passed
Evidence: `develop` 730157e: the full suite had only the 8 known environment failures.
Execution: One builder; wording edits by owner file.

## Risks + recovery

A rule line can grow agent context; each line is one sentence, and recovery is to remove it.

## ux_reference

N/A — rule text with no visual surface.

## Verification

Result: Passed
Evidence: Branch full suite 1805 passed, the same 8 environment failures as `develop`; skill link, routing, size and agent-check tests pass; jscpd 0 clones. Independent review not done: Codex is not installed in cloud sessions.
E2E: N/A — rule text; the release canary runs real agents on Abid's Mac.

Delivery target: Merge
Delivery: Pending — PR into `develop` with the `hard-eng` CI check green.
