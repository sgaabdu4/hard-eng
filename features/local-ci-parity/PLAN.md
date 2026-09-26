# Keep local checks as strict as CI

Status: Complete

## Outcome + scope

Local Hard Eng runs catch what CI catches and clean up after themselves:
- an interrupted pre-push removes its snapshot worktree and stops its gates;
- the zizmor gate runs GitHub's online audits locally whenever `gh` is signed in;
- the pnpm-launched mise installs even when the project sets `ignoreScripts: true`;
- a local `check` without `--base` applies the comment rule to the branch's committed changes, not only uncommitted ones.

Non-goals: other gates, SIGKILL (which no process can intercept), and a sweeper for older leftovers.

## Repository context

Owners:
- `.hooks/ship_actions.py` `pre_push`: its snapshot `finally` never ran on SIGTERM/SIGHUP, which left a registered worktree, its temporary directory and a running check.
- `.hooks/gitleaks_scan.py` `run_gate_command` and `.hooks/update.py` `github_json` (the existing `gh auth token` lookup): zizmor ran offline locally, while CI has `GH_TOKEN`, so pre-push passed a ref-version-mismatch that CI failed on.
- `.hooks/tool_setup.py`, `.hooks/ci_setup.py` and `.github/workflows/hard-eng.yml`: the launcher `pnpm dlx --allow-build=@jdxcode/mise ...` inherits the project's `ignoreScripts: true`, so mise's postinstall never fetches the binary (exit 126).
- `.hooks/comments.py` `validate_comments`: with no base it diffs only against HEAD.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: Autonomous. The user asked to fix all reported Hard Eng defects and the comment-rule scope gap.

## Acceptance + steps

- [x] SIGTERM or SIGHUP during pre-push leaves one worktree, no snapshot directory and no running gate, even one that ignores SIGTERM → `test_interrupted_pre_push_removes_its_snapshot`.
- [x] Without `GH_TOKEN`/`GITHUB_TOKEN`, the ci-security gate receives `gh auth token`; other gates and an existing token are untouched → `tests/test_runner.py`.
- [x] The mise launcher passes `--config.ignore-scripts=false` locally, in generated CI and when migrating installed workflows → `tests/test_ci_setup.py` and `tests/test_setup.py`, plus a real `pnpm dlx` under `ignoreScripts: true`.
- [x] With no base, a two-line block committed on a branch off the shipping base fails `validate_comments`; an explicit `HEAD` base keeps the old scope → `tests/test_comments.py`.

## Baseline + execution

Result: Passed
Evidence: Main `9d1f0a9`: CI passed and `check` passed 17/17 before this branch. Reproductions before each fix:
- the interrupt test failed with 2 worktrees for both signals;
- `pnpm dlx` of mise under `ignoreScripts: true` exited 126 with the binary missing;
- dart-decimate PR CI's online zizmor failed on a pin comment that local pre-push had passed.
Execution: One builder; one commit per fix.

## Risks + recovery

Supplying the token makes zizmor query GitHub locally, so it can surface online findings that local runs used to miss; those findings are real and get fixed. Recovery: revert the individual commit.

## ux_reference

N/A — hook and gate behaviour with no visual surface.

## Verification

Result: Passed
Evidence: `python3 .hooks/hard-eng.py check --plan-stage Ready` → exit 0, 17/17 gates PASS, 912 tests. Every new test failed on the code before its fix. `/codex:adversarial-review --base main` found that a gate ignoring SIGTERM outlived the snapshot. The fix waits up to 10s, then SIGKILLs the group, and the test covers that case.
E2E: Passed:
- `test_interrupted_pre_push_removes_its_snapshot` runs a real `hard-eng.py pre-push` against a snapshot worktree, with a check that starts a gate ignoring SIGTERM, and interrupts it with SIGTERM and SIGHUP.
- `pnpm dlx --config.ignore-scripts=false --allow-build=@jdxcode/mise --package=@jdxcode/mise@latest mise --version` exits 0 under `ignoreScripts: true`; without the flag it exits 126.
- `GH_TOKEN=$(gh auth token) zizmor --strict-collection --persona=auditor .github` reports no findings for hard-eng's workflows.
Limit: SIGKILL of the hook itself still cannot be intercepted.

Delivery target: Merge
Delivery: Pending — PR checks green, squash merge, main CI green.
