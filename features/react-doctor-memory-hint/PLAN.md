# A React Doctor out-of-memory failure says how to fix it

Status: Complete

## Outcome + scope

When React Doctor skips a check because its linter ran out of memory, the gate failure now ends with the fix: allow memory overcommit on the runner or give the job more memory, then rerun. The check is not weakened and nothing retries. Non-goals: a retry loop, a lower bar for incomplete scans, the runner setting itself.

## Repository context

Owners: `incomplete_reason` in `.hooks/react_report.py`, called by `validate_react_project` in `.hooks/reports.py`.
Same cause: three web-project gate runs failed after 12 to 67 s with "React Doctor reports incomplete checks or diagnostics" and no reason. The previous change (b310bfa) added each skipped check and its reason, so the reason now reads "oxlint ran out of memory in fixed_size.rs". The cause is the runner, not Hard Eng: oxlint reserves large address ranges, and a small VM with the default overcommit mode refuses them, so React Doctor writes `complete: false`; the runner owner confirmed three clean scans in a row after enabling overcommit. The failing runs were reruns started hours after the first attempt (the job itself ran about a minute), so no Hard Eng time limit is involved. A rerun is safe: `hard-eng.py` deletes the report file before each run, so a stale complete report cannot pass.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: The maintainer approved this stream on 2026-10-31 (edit, push, open pull requests into `develop`, no release). Decided: match "out of memory" in the whole message, case-insensitive, with no runner product names.

## Acceptance + steps

- [x] An out-of-memory reason ends with the fix → `tests/test_react_report.py::test_out_of_memory_reason_says_how_to_fix_it`.
- [x] Other reasons get no memory hint → `tests/test_react_report.py::test_other_reasons_get_no_memory_hint`.
- [x] Existing reasons, long-reason cut and the passing scan are unchanged → `tests/test_react_report.py::test_incomplete_react_scan_says_why`, `tests/test_react_report.py::test_long_reason_is_cut` and `tests/test_react_report.py::test_complete_react_scan_passes`.

## Baseline + execution

Result: Passed
Evidence: `origin/develop` 799d5cf: `tests/test_react_report.py` 7 passed. The new hint test failed before the change with the message lacking the fix.
Execution: One builder; tests first, then the message.

## Risks + recovery

A reason that mentions memory for another cause gets the same hint. Recovery: revert the commit.

## ux_reference

N/A — gate message with no visual surface.

## Verification

Result: Passed
Evidence: `check --plan-stage Complete --base origin/develop` on the branch: all 20 gates passed and 2085 tests passed. The runner side (overcommit) is outside this repository.
E2E: N/A — the tests run the real report validator on written reports; an out-of-memory scan on a small runner is not reproducible here.

Delivery target: PR
Delivery: Pending — PR into `develop` with the `hard-eng` CI check green.
