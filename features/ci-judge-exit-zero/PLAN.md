# Workflow judge: an earlier exit ends the step with success

Status: Complete

## Outcome + scope

The workflow judge for `pre_push_checks: "ci"` refuses a `run` step where a line before the check can end the step with success. Non-goals: any other judge rule; the declined exit trap finding of the earlier judge PR is reversed here for the `exit 0` trap form only.

## Sources + coverage

Sources: N/A — the request is the only source: the coordinator's message of 2026-11-18 with a reproduced probe from the challenge of the base branch.

## Repository context

Owners: `.hooks/ci_jobs.py` (`shell_runs_it`) owns the step rules; the new pattern `STEP_ENDING` sits next to its siblings.
Same cause: the closed-block rule looked at lines inside a shell block only, so a one-line list (`cond && exit 0`), a bare `exit`, a `return`, an exit inside a function and a `trap` handler were not seen. One pattern over the text before the check covers all of them.
Single source: N/A — one function owns the rule; no copy was found.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: The coordinator named the rule, the branch and the tests; the PR is not merged here.

## Acceptance + steps

- [x] A step with `exit 0`, a bare `exit`, `return 0`, `exit "$CODE"`, `cond && exit 0`, `cond || exit 0`, an exit inside a function, or `trap "exit 0" EXIT` before the check is refused → `tests/test_shipping_policy.py::test_a_workflow_that_does_not_run_the_whole_check_on_every_pull_request_is_refused`
- [x] A step whose earlier lines only exit with a non-zero number, and a `--exit-code` flag, are accepted → `tests/test_shipping_policy.py::test_a_condition_or_filter_that_skips_no_pull_request_does_not_refuse_the_workflow`
- [x] Hard Eng's own workflows, the generated launcher line and the paired docs-only form stay accepted → `tests/test_shipping_policy.py::test_the_hard_eng_workflows_with_a_docs_only_step_pair_run_the_whole_check`

## Baseline + execution

Result: Passed
Evidence: On `origin/develop` the eight new refused rows fail. On `origin/main` the judge has another layout, so the same eight forms were run through its `ci_check_gap`: all eight were accepted. Of 25 installed projects, read from their origin default branches, 19 are accepted and 6 refused under the old and the new rule alike; no refusal is new.
Execution: One change in `.hooks/ci_jobs.py`, one docs sentence, the test rows.

## Risks + recovery

A check line after text that mentions `exit` as a bare word is now refused, such as an `echo` that prints it. Recovery: revert the commit.

## ux_reference

N/A — no screen changes; Hard Eng has no app UI.

## Verification

Result: Passed
Evidence: The focused tests, the static gates and the Complete check passed on the head.
E2E: N/A — the change is a pure check of workflow text, proved by the tests above.
Real service: N/A — no service is called.
Retro: Escaped bug: the gate that should have caught it is the tests gate, `tests/test_shipping_policy.py`: its rows covered the closed block form and a bare `exit 0` line was never a row. The challenge of the earlier judge PR missed it too and the next challenge found it. Fix: one pattern over all text before the check, with a row for each form.

Delivery target: PR
Delivery: Pending — required remote proof.
