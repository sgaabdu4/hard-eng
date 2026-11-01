# Sandbox placeholders do not make a change big

Status: Ready

## Outcome + scope

With the Claude Code Linux sandbox on, `check` sizes a change only from files Git can add. The sandbox placeholders for protected paths no longer make a small fix big. A real new file still makes the change big. Non-goals: other users of the untracked file list, and placeholders seen from outside the sandbox.

## Repository context

Owners: `_branch_change` in `.hooks/change_size.py` reads `git ls-files --others --exclude-standard`; `size_verdict` treats each such name as a new file.
Cause (reproduced with Claude Code 2.1.316 and bubblewrap 0.9): for each missing protected path, the sandbox binds `/dev/null` to it with `bwrap --ro-bind`. Examples: `.bashrc`, `.gitconfig`, `.mcp.json`, `.idea`, `.vscode`, `.claude/agents`. Inside the sandbox each one is an empty character device. Git lists it as untracked, because the folder entry still shows the empty mount-point file. Git cannot add a character device. After the sandboxed command ends, Claude Code deletes the mount points.
Same cause: none found.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: the user asked on 2026-11-01 to find the placeholders, fix the cause at its owner with a failing test first, and keep the change small.
Decided: count only untracked regular files and symbolic links, the types Git can add. A name list or a zero-size rule would hide a real new empty file.
Known limit: outside the sandbox (hooks), a mount point is an empty regular file while another sandboxed command still runs. It looks like a real empty file, so it still counts.

## Acceptance + steps

- [ ] A two-line fix with a sandbox placeholder stays small → `tests/test_plans.py::test_sandbox_placeholder_does_not_add_a_file[small]`.
- [ ] A real new file beside a sandbox placeholder stays big → `tests/test_plans.py::test_sandbox_placeholder_does_not_add_a_file[new]`.
- [ ] `tests/agent_checks.py --client claude --case escaped-bug` passes with the sandbox on and bubblewrap installed.

## Baseline + execution

Result: Passed
Evidence: `develop` 7624c88: `python3 .hooks/hard-eng.py check --plan-stage Draft` → exit 0 (reuses the passed CI run for ccf2c7f); `tests/test_plans.py` 95 passed. The first run failed only because this clone had no submodules; `git submodule update --init --recursive` repaired it.
Execution: One builder, this session. Failing test first, then the filter in `_branch_change`.

## Risks + recovery

The test needs bubblewrap; it skips where bubblewrap is not installed, which includes the GitHub runner. Revert the filter to restore the old count.

## ux_reference

N/A — hook output with no visual surface.

## Verification

Result: Pending
Evidence: Pending.
E2E: Required — `tests/agent_checks.py --client claude --case escaped-bug` with the sandbox on and bubblewrap installed; expected proof: the case passes and the agent fixes the bug in the main folder.

Delivery target: Merge
Delivery: Pending — PR into `develop` with the `hard-eng` CI check green.
