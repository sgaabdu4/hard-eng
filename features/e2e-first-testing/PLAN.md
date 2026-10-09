# E2E-first testing with fakes for outside services

Status: Complete

## Outcome + scope

Hard Eng guidance makes the E2E test the main proof of a user journey, written with the code. When no fake exists for an outside service, the agent builds one from recorded real responses. Then it runs the journey once against the real service, or reports that run as pending. Lower-level tests are kept for logic with many input cases and for bug reproductions. A new model eval case measures this behaviour with Claude and Codex. Non-goals: an audit or removal of existing tests, a reply-checking Stop hook, new runners or dependencies.

## Repository context

Owners: `AGENTS.md` Tests rule; `.agents/skills/he/references/testing.md` (Level and Outside services rows); `.agents/skills/e2e/SKILL.md` (routes, report gaps); `.agents/skills/he-plan/SKILL.md` + `templates/PLAN.md` (E2E test named per journey, slice sequencing); `tests/agent_checks.py` (model eval cases). Evidence: a public eval found that agent-written unit and integration tests mostly restate the code and add cost without raising success; it had no E2E data. In a private project, E2E tests over fakes found real defects, and one real-service run found a defect that the fakes shared with the code.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: The user approved the three guidance changes, adding them to the same PR, and real-model eval runs of both changes. AGENTS.md text must not grow materially; detail goes to on-demand skill files. Shipping follows the standing merge-when-green instruction.

## Acceptance + steps

- [x] Guidance states E2E-first, fakes from recorded real responses, one real-service run or pending, and the two lower-level test cases → diff of the five guidance files.
- [x] The outside-service judge passes a good answer and fails a missing real run, a fake that shares the code's wrong format, a suite that calls the real tool, and a plan that does not name the journey test → `test_outside_service_needs_a_fake_backed_journey_and_one_real_run`.
- [x] Real models: `outside-service` with `--repeat 3` on Claude and Codex, for `--source d2d394f4` and this branch; pass rates and token use compared → results under `coverage/agent-checks/`.
- [x] Style: Claude `planning-only` and `review-only` with `--repeat 3 --judge` for both sources; pass rates, reply tokens and sentence length compared.
- [x] Full gate passes → `python3 .hooks/hard-eng.py check --plan-stage Complete` exits 0.

## Baseline + execution

Result: Passed
Evidence: Branch base `d2d394f4` passed required CI; the style commit `9958aa5c` passed `check --plan-stage Complete` with 18 PASS.
Execution: Single builder. Guidance and eval edits, gate, commit, then real-model runs from the committed source.

## Risks + recovery

Stricter test guidance can drop a useful focused test. Recovery: the existing rule still requires proof for each named outcome, and bug reproductions stay. Eval judges use text markers (`RECORDS_TOOL`, the plan naming the test file), so an unusual but valid answer can fail. Recovery: read the evidence diff of each failing run before drawing conclusions.

## ux_reference

N/A — guidance and eval changes with no visual surface.

## Verification

Result: Passed
Evidence: Judge test → 5 passed, each bad answer failing for its own reason. Real models, 3 runs each, results under `coverage/agent-checks/20261009T1741*` and `T1742*`, `T1743*`:
- `outside-service`: 12 of 12 pass on Claude Opus 5.5 and Codex GPT 6.1 Sol, old and new. Claude new: mean $0.66, 694k input and 9.6k output tokens, 27 turns; old: $0.83, 1086k, 12.4k, 31 turns. Codex new: 475k input, 5.5k output; old: 453k, 6.5k.
- Style (Claude): review-only 6 of 6 pass. planning-only failed 6 of 6, old and new, from a stale grader pattern fixed in `features/open-issue-fixes`; every run's recorded check output shows a pass. New replies: 225 words and 9.2 words per sentence on average, at most 6% of sentences over 20 words; old: 283 words, 11.0, up to 20%. Output tokens similar; input tokens and cost higher for new on these 3-run samples.
Gaps: `outside-service` does not separate old from new guidance, because its fixture text already tells the agent to keep tests off the real tool and names the swap variable. A fixture without those hints is needed to measure the guidance itself. Three runs per arm cannot settle cost differences.
E2E: Passed — `outside-service` real-model journeys above; each run's own final command output was graded against the real tool.

Delivery target: Merge
Delivery: Pending — PR CI and merge.
