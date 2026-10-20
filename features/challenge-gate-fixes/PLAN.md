# Challenge gate fixes

Status: Complete

## Outcome + scope

`challenge` records a completed review (`clean` or `findings`) only when the other agent really reviewed the pinned revision: no branch point, uncommitted tracked changes, a last line other than an exact verdict, or a commit during the review records `not done`; two host markers ask for `--host`; the reviewer gets no host markers; the prompt names the SHA and says repository text is data. Non-goals: blocking ship on a `not done` record (the existing contract keeps a note), process-group kill on timeout (next PR), and patch-id reuse.

## Repository context

Owners: `.hooks/challenge.py` (`reviewer_for`, `review`, `challenge`, `PROMPT`) and its reference `.agents/skills/code-review/references/challenge.md`. `shipping_note` trusts the stored record for big changes. `default_branch_point` in `.hooks/plans.py` returns `None` when no branch point exists, and `review` then asked for `git diff HEAD HEAD`. A one-line edit to `.hooks`, `.github` or `hard-eng.gates.json` is already big through `_file_reason` (since 6239be0), so that study claim needs no change.
Same cause: one cause, `review` treated any exit-0 reply and any start state as a completed review; each fix narrows what counts as completed.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: Abid asked on 2026-10-20 to build the deep-study findings into `develop`, gate bugs first, with every decision made by the agent. Decided: both markers set fails closed; the old test row that picked Codex as reviewer had no ADR reason.

## Acceptance + steps

- [x] Both host markers and no `--host` ask for the host → `tests/test_challenge.py::test_unknown_or_ambiguous_host_asks_for_the_host` fails with `--host`.
- [x] The reviewer does not inherit `CLAUDECODE` or `CODEX_*` markers but keeps `CODEX_HOME` → `tests/test_challenge.py::test_the_reviewer_does_not_inherit_host_markers`.
- [x] The prompt names the reviewed SHA and treats repository text as data → `tests/test_challenge.py::test_the_prompt_pins_the_reviewed_revision_and_treats_repo_text_as_data`.
- [x] A reply without an exact verdict line records `not done` and exits 1 → `tests/test_challenge.py::test_a_reply_without_an_exact_verdict_is_not_a_review`.
- [x] No branch point records `not done` without calling the reviewer → `tests/test_challenge.py::test_no_branch_point_records_not_done_without_calling_the_reviewer`.
- [x] Uncommitted tracked changes record `not done` without calling the reviewer → `tests/test_challenge.py::test_a_dirty_tree_is_not_reviewed`.
- [x] A commit during the review voids it → `tests/test_challenge.py::test_a_commit_during_the_review_voids_it`.

## Baseline + execution

Result: Passed
Evidence: `develop` 2c24999 with submodules: the full suite has 8 failures that need Dart, Xcode or signal timing this cloud machine lacks. The 10 new challenge tests failed there before the fix.
Execution: One builder. Failing tests first (10 failed on `develop` 2c24999), then the fix in `challenge.py`.

## Risks + recovery

A reviewer that ends with extra text after the verdict now records `not done`; recovery is a rerun, and the prompt already asks for the verdict as the last line.

## ux_reference

N/A — command-line gate change with no visual surface.

## Verification

Result: Passed
Evidence: Branch full suite 1782 passed, the same 8 environment failures as `develop`; `tests/test_challenge.py` 27 passed. Ruff format, lint, complexity and annotations, Pyrefly (0 diagnostics), Vulture and jscpd (0 clones) pass. Independent review not done: Codex is not installed in cloud sessions.
E2E: N/A — `challenge` runs a real subprocess against a fake reviewer CLI in a real Git repository in each test; the live Codex run happens on Abid's Mac through the release canary.

Delivery target: Merge
Delivery: Pending — PR into `develop` with the `hard-eng` CI check green.
