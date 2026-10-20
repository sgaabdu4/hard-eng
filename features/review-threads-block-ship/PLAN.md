# Review threads block ship

Status: Complete

## Outcome + scope

`ship --stage ready` and `ship --stage merge` refuse a PR with an unresolved or uncounted review thread, whatever GitHub's mergeable state says. Non-goals: GitHub native auto-merge, which merges without `ship`, and replying to threads.

## Repository context

Owners: `_ready_state` in `.hooks/shipping.py` verifies the open PR for both stages. Before, the thread check lived only in `_other_merge_requirement`, which runs on the admin-bypass path; a `clean` PR skipped it, and GitHub reports `clean` with open threads unless the branch rule asks for resolved conversations. The check moves to `_ready_state` and reuses `_complete_nodes`, which fails closed on a short page.
Same cause: one cause, the thread check sat on one path instead of the shared ready check.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: Abid asked on 2026-10-20 to build the deep-study findings into `develop`, gate bugs first, with every decision made by the agent.

## Acceptance + steps

- [x] A clean or blocked PR with an open or uncounted review thread is refused → `tests/test_review_bypass.py::test_ready_refuses_an_open_or_uncounted_review_thread_on_every_path`.
- [x] Both paths still pass without one → `tests/test_shipping.py::test_ready_bypasses_only_a_review_nobody_but_the_author_can_give`.

## Baseline + execution

Result: Passed
Evidence: `develop` 9c61244: the two new cases failed because a clean PR shipped with an open thread; the full suite had only the 8 known environment failures.
Execution: One builder; failing tests, then the check move.

## Risks + recovery

Each ready check makes one more small GraphQL call. A PR with more than 100 threads is refused as uncounted; recovery is to resolve threads.

## ux_reference

N/A — shipping gate change with no visual surface.

## Verification

Result: Passed
Evidence: Branch full suite 1796 passed, the same 8 environment failures as `develop`. Ruff, Pyrefly, Vulture, jscpd and deptry pass; `.hooks/shipping.py` stays at 997 lines. Independent review not done: Codex is not installed in cloud sessions.
E2E: N/A — the tests drive the real `verify` with a fake GitHub API; a live PR merge is not repeatable in tests.

Delivery target: Merge
Delivery: Pending — PR into `develop` with the `hard-eng` CI check green.
