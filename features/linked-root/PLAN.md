# A project reached through a linked folder loads its checks

Status: Complete

## Outcome + scope

A project whose root is reached through a linked folder loads its checks, so `update-pr` on a Mac no longer refuses each update. Non-goals: a change of the stop hook; a change of how a command finds its temporary folder; a release.

## Sources + coverage

Sources: the problem report that the owner pasted on 2026-11-14 about commands that fail in a temporary checkout on a Mac, read in full.
Reviewer: N/A — one short report in one message, with the code place and the steps in it.
Deliverables: None

- Outcome, confirm the cause in the code first, write the failing test, then fix it: In scope — A project reached through a linked folder loads its checks
- Rule, the report: the folder check resolves one side and not the other, so a folder inside the project is judged outside: In scope — A project reached through a linked folder loads its checks
- Rule, the report: resolve both sides and add a test with a root reached through a link: In scope — A project reached through a linked folder loads its checks
- Screen, the report: `update-pr` stops with "Gate directory must exist inside the project: .": In scope — The real `update-pr` flow loads the update branch tip
- Screen, the report: the same message with ".." as the path: Proposal — not reproduced and not changed: a folder named ".." is outside each root, resolved or not, so this fix cannot cause or remove that message; yes — user, chat of 2026-11-11 (the builder makes the decisions that the work needs and does not wait) and `AGENTS.md` (the design of this codebase is the agent's call)
- Screen, the report: the setup script, `challenge` and `ship` needed the same workaround: In scope — Each test with an isolated temporary folder reaches it through a link
- Rule, the report: the workaround sets the temporary folder to its real path: In scope — Each test with an isolated temporary folder reaches it through a link
- Outcome, the pasted question: should a stop from a child agent only report a plan finding and not block: In scope — The owner gets an answer to the stop hook question

## Repository context

Owners: `validate_group` in `.hooks/gate_config.py` owns the folder check. `tip_refusal` in `.hooks/update_pr.py` loads the update branch tip from a checkout in the temporary folder. `isolate_temporary` in `tests/conftest.py` owns the temporary folder of each update test.
Same cause: the cause is a comparison of a resolved path with a path that is not resolved. No earlier fix of this cause exists in the history of the folder check. Searched each `is_relative_to` call below `.hooks`, 40 calls; calls of `relative_to` and cuts of a path text by length were not searched one by one. The folder check was the only call found that compares a resolved path with the root that its caller gave. The others resolve both sides, compare two paths that come from the same root, or work on names inside the repository. Two calls in `hook_chain.py` compare the root with a hook path that Git gives; those were not traced for each Git setting. The test setup hid the cause: it gave each test a temporary folder with a real path. It now gives a linked one, and the full suite ran with it as the search for other places: with the old line, 17 tests failed and 8 could not start, each in the two `update-pr` test files; with the fix, each of the 4,421 tests passed. No test of setup, `challenge` or `ship` failed with the old line.
Single source: the folder check has one owner, `validate_group`; no other copy of the check exists. The temporary folder of a test has one owner, `isolate_temporary`.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: Autonomous. The owner pasted the report on 2026-11-14 as the request, and gave full authority for design and merge. A release is not part of this request.
Decisions:

1. The fix is in the folder check, not in the caller. `update-pr` loads the tip with the hooks of the new release and the temporary path of the installed release. A fix in the caller does not reach the update that brings it.
2. The check resolves the root for the comparison only. The root that each later step gets stays as the caller gave it, so the loaded checks stay the same. The test compares them.
3. The file of the folder check is at the size limit of 1,000 lines. The fix changes one line and adds none.
4. The test setup gives a linked temporary folder to each test that isolates it. A Mac always has one. This is the gate that did not catch the fault, so the case goes there and not only into one new test.
5. The stop hook stays as it is in this change. The answer to the question goes to the owner with the facts that were read and the ones that were not.

## Acceptance + steps

- [x] A project reached through a linked folder loads its checks, they equal the checks of the real path, and a real refusal stays a refusal → `tests/test_update_pr_refusal.py::test_the_tip_load_reads_a_project_reached_through_a_linked_folder`
- [x] The real `update-pr` flow loads the update branch tip from a temporary folder that is reached through a link → `tests/test_update_pr_refusal.py::test_a_fix_on_the_update_branch_is_pushed_and_merged_by_update_pr`
- [x] Each test with an isolated temporary folder reaches it through a link, so a publish test fails on the old line → `tests/test_update_pr.py::test_update_pr_pushes_opens_one_pr_and_turns_on_auto_merge`
- [x] The owner gets an answer to the stop hook question, with what was read and what was not → N/A — a chat reply, not code
- [x] The new texts and the pull request text hold nothing about a project's name, data or files → N/A — a search of the outgoing text before the push and before the pull request, recorded in Verification

## Baseline + execution

Result: Passed
Evidence: the starting code is the base branch at 70baccc4, and the Hard Eng check run of that commit passed. On that code, a load of this repository through a linked folder gave "Gate directory must exist inside the project: .".
Execution: one builder; the failing test first, then the one-line fix, the linked temporary folder of the test setup, the full suite, the independent review and the Complete gate.

## Risks + recovery

- A test that compares a temporary path with its real path can fail with the linked folder. The full suite run shows each such test.
- Recovery: revert the commits of the pull request, newest first; no data step.

## ux_reference

N/A — no screen changes; the change is one path comparison and the test setup.

## Verification

Result: Passed
Evidence: the new test failed before the fix with "Gate directory must exist inside the project: ." and passes after it. The full suite ran two times with the linked temporary folder of the test setup. With the old line: 17 failed, 8 could not start, 4,396 passed; each failure is in `tests/test_update_pr.py` or `tests/test_update_pr_refusal.py`. With the fix: 4,421 passed. A load of this repository through a linked folder gave the same checks as the real path, with and without a base. In a Python fixture project, two refusals that need a match of files to folders gave the same text through the link and through the real path: code outside the listed sources, and a missing lockfile. The independent review of the fix commit by the other client gave no finding. Not reproduced: the message with ".." as the path, and a failure of setup, `challenge` or `ship` apart from `update-pr`. Stop hook question, read: both clients have a separate stop event for a child agent, and Hard Eng registers only the stop event of the main session; a child that runs as its own process is a full session, and its stop message has no field that marks it as a child. Not read: the real stop message of a child, because a scratch folder does not load project hooks without a change of the user's own client settings. A search of the outgoing text for private words found 0.
E2E: N/A — no user journey of an app changes.
Real service: N/A — the change calls no outside service.
Retro: (1) The fault reached the base branch: each `update-pr` test passed, because the test setup gave a temporary folder with a real path and a Mac gives a linked one → `tests/conftest.py`, where `isolate_temporary` now gives a linked folder; with the old line, `tests/test_update_pr.py::test_update_pr_pushes_opens_one_pr_and_turns_on_auto_merge` and 24 more tests fail. (2) The Stop check refused the first stop, because a change of the gate file owner always needs a plan and none was written → None — the Stop check caught it before the first commit.

Delivery target: Merge
Delivery: Pending — the pull request into `develop` and its checks.
