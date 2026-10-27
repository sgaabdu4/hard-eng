# Say why a base-branch push runs the checks again

Status: Complete

## Outcome + scope

When a CI push to the shipping base branch cannot reuse the merged PR's passed checks, the job prints one line with the reason before it runs the checks. Non-goals: changing when reuse applies, changing project workflows, new permissions.

## Repository context

Owners: `.hooks/shipping.py::reused_pull_request`.
Same cause: a CI audit on 2026-10-27 found 15 installed projects whose main pushes rerun every check. One project's PR passed on the same tree; its workflow grants only `contents: read`, so the PR lookup fails and the fallback gives no reason. Every fallback path returns `None` silently.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: Abid on 2026-10-27, after the CI audit: fix the reruns after merge.
Decision: print only when the push is a CI push to the base branch, so local runs and PR runs stay quiet. The reason is the existing `ShippingError` text, which carries the last line of a failed `gh` call.

## Acceptance + steps

- [x] Each fallback on a CI base-branch push prints its reason → `tests/test_shipping.py::test_push_runs_checks_when_pull_request_proof_is_missing`.
- [x] Runs that are not CI pushes to the base branch print nothing → `tests/test_shipping.py::test_only_ci_pushes_to_the_base_branch_reuse_pull_request_checks`.

## Baseline + execution

Result: Passed
Evidence: Branch point develop add9450e; its PR #425 passed `hard-eng`, `canary` and the new-project jobs in CI.
Execution: One builder, this session.

## Risks + recovery

N/A — one extra output line; the reuse decision does not change.

## ux_reference

N/A — CI log text only; no visible UI.

## Verification

Result: Passed
Evidence: The 10 new fallback cases failed on develop add9450e and pass here; `tests/test_shipping.py` passes (87). ruff and pyrefly pass on the changed files.
E2E: N/A — the tests run the real reuse code against a fixture repository and a fake GitHub API.
Delivery target: Merge
Delivery: Pending — the PR merges into develop.
