# Pre-push rewrite guard

Status: Complete

## Outcome + scope

Pre-push fails when a gate changed a tracked file in the pushed snapshot, for example a formatter that fixes files in place. The pushed commit then differs from the files that passed, so the pass proves nothing about the push. Non-goals: gate commands, CI, the working-tree check and untracked report files.

## Repository context

Owners: `pre_push` in `.hooks/ship_actions.py` runs `check` in a detached snapshot worktree and returned its exit code alone. A gate could rewrite a tracked file there, pass, and the push went on with the old file. The snapshot uses the stripped Git environment from `snapshot_environment`, so the new `git diff` call uses it too.
Same cause: none found. Source: Compound Engineering study, item S6, handed over by the deep-study build thread.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: Abid asked on 2026-10-20 to find and ship Hard Eng flow fixes into `develop` without weaker checks, with every decision made by the agent. Decided: check tracked files only, since gates write reports to untracked paths.

## Acceptance + steps

- [x] A gate that rewrites a pushed file fails pre-push, names the file and leaves the checkout unchanged → `tests/test_ship_actions.py::test_pre_push_fails_when_a_gate_rewrites_a_pushed_file`.
- [x] A passing snapshot with its own Git environment still passes → `tests/test_ship_actions.py::test_pre_push_snapshot_has_its_own_git_environment`.

## Baseline + execution

Result: Passed
Evidence: `develop` 1f9f585: the new test failed (pre-push returned 0); `tests/test_ship_actions.py` had only the 2 known environment failures of `test_interrupted_pre_push_removes_its_snapshot` in this cloud container, which pass in CI.
Execution: One builder; failing test first, then the check after the snapshot `check` passes.

## Risks + recovery

A gate that must write a tracked file to pass now fails the push; that gate was already proving a different tree. Revert the one block in `pre_push` to restore the old result.

## ux_reference

N/A — hook output with no visual surface.

## Verification

Result: Passed
Evidence: Branch full suite 1,820 passed; the same 8 environment failures as `develop` (no Dart or Swift in this container, and the 2 interrupted pre-push cases). Ruff format, lint, complexity and annotations, Pyrefly, Vulture, jscpd, deptry, semgrep, gitleaks and OSV pass. Independent review not done: Codex is not installed in cloud sessions.
E2E: N/A — the test runs the real pre-push hook against a real Git snapshot.

Delivery target: Merge
Delivery: Pending — PR into `develop` with the `hard-eng` CI check green.
