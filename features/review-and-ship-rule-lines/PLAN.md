# Review and ship rule lines

Status: Complete

## Outcome + scope

Five one-line rules from the deep studies, each at its one owner, each a non-default condition that writing-great-skills' Need test keeps:

1. `he-ship`: `Fixes #N` closes an issue only on merge into the default branch; for another base, write `Refs #N` and close it after release.
2. Review method: compatibility code for a shape that never shipped is an unsupported addition.
3. `e2e`: a reused server or app must run this checkout's current build.
4. Workflow: before editing, check open PRs and active tasks that touch the same files and agree an order.
5. Challenge: after fixes, rerun with `--base <last reviewed SHA>`; after two rounds whose findings all fail verification, stop and report the remaining claims as gaps.

Non-goals: the other listed rule lines. They repeat existing rules (testing.md already requires a failure for the expected reason; Research already separates documented, observed, inferred and unknown) or are generic agent advice.

## Repository context

Owners: `he-ship/SKILL.md` PR line, `code-review/references/review.md` Intent line, `e2e/SKILL.md` first proof line, `he/references/workflow.md` Isolation line, `code-review/references/challenge.md`. `challenge` already takes `--base`.
Same cause: N/A — separate gaps found by the studies, not one fault.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: Abid asked on 2026-10-20 to build the deep-study findings into `develop` with writing-great-skills for skill edits, with every decision made by the agent. Decided: keep only lines that pass the Need test.

## Acceptance + steps

- [x] Changed skill links and routes still resolve → `tests/test_skill_links.py::test_distributed_skill_links_resolve`.
- [x] Changed skills still fit the Codex skill size limit → `tests/test_skill_links.py::test_distributed_skills_fit_the_codex_skill_limit`.
- [x] The documented `challenge --base` flag exists → `tests/test_skill_links.py::test_documented_commands_and_flags_exist`.
- [x] Rule wording → N/A — wording has no deterministic behavior test; the release canary runs real agents on Abid's Mac.

## Baseline + execution

Result: Passed
Evidence: `develop` 376e9de: the full suite had only the 8 known environment failures.
Execution: One builder; wording edits by owner file.

## Risks + recovery

Each line adds agent context; recovery is to remove it.

## ux_reference

N/A — rule text with no visual surface.

## Verification

Result: Passed
Evidence: Skill link, routing, size, documented-command and requirement tests pass (26); `check --quick` passes. Independent review not done: Codex is not installed in cloud sessions.
E2E: N/A — rule text; the release canary runs real agents on Abid's Mac.

Delivery target: Merge
Delivery: Pending — PR into `develop` with the `hard-eng` CI check green.
