# Test-first bug fixes, a clean Claude reviewer and two agent-runner fixes

Status: Complete

## Outcome + scope

1. Bug fixes start with a failing reproduction test whose expected result comes from the report or contract, then the fix. New features keep "tests may follow code".
2. The Claude challenge reviewer starts with `--safe-mode`, so the reviewed repository's hooks, rules files and plugins do not run or steer it.
3. `tests/agent_checks.py --repeat` below 1 is refused instead of reporting success with no runs.
4. The agent runner grades every Codex `agent_message` of the turn, not only the last one, so a closing "done" line cannot hide the answer.

Dropped: adding `onFailure: "block"` to the Claude Stop hook. Claude Code 2.1.295 ignores it on Stop (live probe logged `not blocking (onFailure: "block" is ignored on Stop)` and the turn finished). Non-goals: forcing TDD on features, new checks, hooks or files.

## Repository context

Owners: `AGENTS.md` Tests rule; `.agents/skills/he/references/testing.md` opening line + Regression row; `.hooks/challenge.py` `command`; `tests/agent_checks.py` `main` + `codex_run`; tests in `tests/test_challenge.py` and `tests/test_agent_checks.py`.
Why item 1: an agent that writes the test after the fix tends to copy the fixed code's output into the assertion, so the test cannot show the bug existed.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: User approved items 1–4 on 2026-10-09 and asked for a Codex adversarial review loop on GPT-6 Astra before the PR, fixing only genuine, realistic, substantial findings.

## Acceptance + steps

- [x] Rule text: `AGENTS.md` and `testing.md` require the failing reproduction test before a bug fix, expected result from the report or contract; the existing "unavailable red evidence remains a stated gap" stays → diff review.
- [x] Safe-mode reviewer → `test_codex_host_runs_claude_with_read_only_tools` asserts `--safe-mode`; failed before the fix, passes after.
- [x] Repeat below 1 refused → `test_a_run_that_would_test_nothing_is_refused[0|-1]` exits 2 naming `--repeat`; before the fix `main()` returned success with no runs.
- [x] Codex answer before a closing line is graded → `test_a_codex_review_keeps_the_answer_before_its_closing_line` with a fake `codex` CLI emitting two messages; before the fix the report was only "Review complete."
- [x] CI repair: a stop signal that lands after the update records its outcome no longer turns it into "update exited -15" → `test_a_stop_after_the_result_is_recorded_keeps_the_result` exits 1 before the fix, 0 after; CI had failed `test_interrupted_update_stops_every_process_and_records_failure[during-cleanup]` on this race (40 local reruns did not hit it).
- [x] Full `check` passes; Codex adversarial review loop has no substantial findings.

## Baseline + execution

Result: Passed
Evidence: `python3 .hooks/hard-eng.py check --plan-stage Draft` on 487b633 (main plus the plan-evidence-baseline commits, since merged) → exit 0: every gate PASS, 1459 tests, 91.08% line coverage.
Execution: Single session. Each bug fix wrote its failing test first (red run: 4 failed for the expected reasons), then the fix (40 passed).

## Risks + recovery

Safe mode also hides the reviewed repository's rules files from the Claude reviewer; it reviews from the prompt and the diff only, which is the intended independence. Some bugs cannot be reproduced in a test; the Regression row keeps that as a stated gap. Recovery: revert the commits.

## ux_reference

N/A — agent instruction text and developer tooling, no visible interface.

## Verification

Result: Passed
Evidence: Rebased on main be2d512. `python3 .hooks/hard-eng.py check --plan-stage Ready` → exit 0: every gate PASS, 1462 tests, 91.10% line coverage. Codex adversarial review on GPT-6 Astra, round 1: approve, no material findings.
E2E: Passed — the real `challenge.command("claude", …)` argv with `--model haiku` against a scratch repository whose SessionStart hook touches a marker: without `--safe-mode` the marker appeared; with it the marker did not, `git log --oneline` still ran, and a Write attempt was refused (no file created). The Codex message fix is proved through `codex_run` with a fake CLI; no live paid Codex run.

Delivery target: Merge
Delivery: Pending
