# Judge agent cases on usable plans, verified diagnoses and recorded actions

Status: Ready

## Outcome + scope

`tests/agent_checks.py` judges each case on two separate questions: is the final state correct, and did the recorded client events show the required workflow actions? Planning-only passes only a PLAN.md that passes the existing stage validation and addresses `average`. A legitimate Draft with open material decisions passes; an empty, placeholder or unsupported Ready plan fails. Review-only keeps its deterministic no-file-change check. It also requires the report to locate `average`, name the floor-division mechanism, and give a concrete input whose stated wrong result the judge confirms by running the fixture's defective code. Whatever judgement remains goes to an opt-in `--judge` model that grades against a rubric the candidate never sees, after calibrating on a known-correct report and a known denial. Without `--judge`, such a report is BLOCKED, never PASS. `--repeat N` and `--source REV` compare revisions through the same runner, with identical requests, fixtures, models and settings. Separately, `.agents/skills/he/references/efficiency.md` gains a compact optimisation procedure, used only when a performance target is in scope. Non-goals: new runners, result stores, skills, hooks, CI agent runs, mandatory model judges and fixed repeat counts.

## Repository context

Owners: `tests/agent_checks.py` (source-only, on demand; fixtures, judges, client runs, `results.json` under ignored `coverage/agent-checks/`); `.hooks/plans.py` `validate_plan` and `check --plan-stage` (stage validation); `.agents/skills/he/references/efficiency.md`. The Codex `--json` stream records `item.completed` `command_execution` (command, exit_code) and `file_change` items. The Claude `stream-json` stream records `tool_use` (Bash, Edit, Write, MultiEdit) and the paired `tool_result` with `is_error`. Judges currently see only the fixture files, Git state and the final message.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: Autonomous. The user asked for these changes as written, with focused regressions, available authenticated real-agent cases, applicable gates and `/codex:adversarial-review` at the end.

## Acceptance + steps

- [x] Reproduced before the fix: the current planning-only judge passes an empty PLAN.md, and the review judge passes a denial that contains the keywords → recorded in Baseline.
- [x] Planning-only fails empty, placeholder, off-request and unsupported Ready plans; passes a Draft with an open material decision and a Ready plan whose baseline check is recorded in the events → `tests/test_agent_checks.py`.
- [x] Review-only fails a keyword-matching denial, a report without a verifiable wrong result, and any file change. A correct report passes with a calibrated judge verdict, and is BLOCKED without `--judge`. A judge that misgrades a calibration control blocks the case → `tests/test_agent_checks.py` with a stub judge.
- [x] Workflow: continue-approved requires a recorded successful Complete check after the last recorded edit; failed-baseline requires a recorded failing check. Post-run checks remain as outcome evidence. Both clients' event formats normalise to the same actions → `tests/test_agent_checks.py`.
- [ ] `--repeat` and `--source` record the revision per run; the existing PASS/FAIL/BLOCKED statuses, client isolation and evidence layout are unchanged.
- [x] efficiency.md holds the optimisation procedure.
- [ ] Real cases run on the available authenticated clients; full gate passes; `/codex:adversarial-review` findings resolved.

## Baseline + execution

Result: Passed
Evidence: Starting tree `a0886aa` (the comment-rule head, main once merged): `python3 .hooks/hard-eng.py check --plan-stage Ready` → exit 0; 17/17 gates PASS, 887 tests passed; 1m51s. Reproduced by calling main's unchanged judges on built fixtures: an empty PLAN.md → PASS, a `# TODO` PLAN.md → PASS, and the review denial "It does not use floor division (//) and nothing is truncated; no defects found." → PASS. All three should fail.
Execution: One builder; reproduction tests, judges, event normalisation, runner options, efficiency guidance, then real-agent runs on an idle machine.

## Risks + recovery

Agent behaviour varies by run and model; repeated runs record the spread instead of claiming stability. A model judge can misgrade; calibration controls block the case when it does. Recovery: rerun, narrow a case, or grade by hand from the saved rubric and report.

## ux_reference

N/A — developer script, tests and skill guidance with no visual surface.

## Verification

Result: Pending
Evidence: Pending
E2E: Required — real Codex and Claude Code runs of all cases through `tests/agent_checks.py`.

Delivery target: Merge
Delivery: Pending — PR checks green, squash merge to main, main CI green.
