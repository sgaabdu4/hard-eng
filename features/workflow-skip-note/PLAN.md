# Say when a customised workflow is not given the docs-only steps

Status: Complete

## Outcome + scope

When an update leaves `.github/workflows/hard-eng.yml` without the docs-only steps because the workflow was customised, setup prints one line to stderr saying so and what to copy from the template. A workflow that already has the steps stays silent, and the workflow is still never edited in that case. No new file other than this plan.

## Repository context

Owner: `.hooks/ci_setup.py` `migrate_docs_path`. It only adds the steps when the generated cache and check steps each appear once without an `if:`; otherwise it returned the content unchanged with no output. A trial on a real monorepo whose generated workflow had been customised showed the effect: the update succeeded, the workflow kept installing every tool for docs-only changes, and nothing told the user. The neighbouring "Existing CI retained" and "CI setup pending" notes already go to stderr.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: The user asked for this note after the trial report, and to merge PR 137 first. The note goes to stderr because setup's `--plan` mode writes JSON to stdout. After PR 138 passed CI, the user approved merging it.

## Acceptance + steps

- [x] A customised workflow produces the note and no change; an upgraded workflow produces neither → `test_old_workflow_gains_docs_only_steps` extended.
- [x] Full check passes.

## Baseline + execution

Result: Passed
Evidence: main at 15ee86d, whose push CI passed for PR 137.
Execution: Single session on `feature/workflow-skip-note`.

## Risks + recovery

The note repeats on each update until the project adds the steps. Recovery is reverting this branch.

## ux_reference

N/A — one line of setup output; no product appearance.

## Verification

Result: Passed
E2E: Passed — in a throwaway worktree of the real monorepo, this branch's `setup.py` run with the project's previous source printed the note, exited 0 and left the workflow unchanged; the project's own checkout was untouched.
Evidence: `tests/test_ci_setup.py` 29 passed. The full check result is recorded in the delivery line below.

Delivery target: Merge
Delivery: Pending — `hard-eng.py check --base origin/main` exit 0: all 17 checks, 794 tests and 4 performance checks passed. PR 138 CI passed; merge, merged-main CI and cleanup remain unverified.
