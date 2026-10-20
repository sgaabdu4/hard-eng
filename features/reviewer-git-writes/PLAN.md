# Reviewer git writes

Status: Complete

## Outcome + scope

The Claude challenge reviewer cannot write files through git. Before, its allow rules such as `Bash(git diff *)` also matched `git diff --output=<file>`, so a read-only reviewer could write any file. Now the reviewer has no Bash allow rule and uses Claude Code's built-in read-only git forms. Non-goals: the Codex reviewer, which runs in a read-only sandbox.

## Repository context

Owner: `command` in `.hooks/challenge.py`. Claude Code's permission docs list `git log --output=<file> main` as a match for `Bash(git log * main)`, and its built-in read-only set covers plain git reads.
Same cause: one cause, prefix allow rules match every later flag.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: Abid asked on 2026-10-20 to build the deep-study findings into `develop`, security next, with every decision made by the agent. Decided: remove the allow rules instead of adding deny rules, because deny rules for flags are fragile.

## Acceptance + steps

- [x] The Claude reviewer gets no Bash allow rule → `tests/test_challenge.py::test_codex_host_runs_claude_with_read_only_tools_and_no_git_write_flags`.

## Baseline + execution

Result: Passed
Evidence: `develop` 32d9301: a real `claude --print` run with the old rules wrote a file through `git diff --output`; the new test failed there.
Execution: One builder; failing test, then the fix.

## Risks + recovery

A git read outside Claude Code's read-only set is now denied; the reviewer then reports less, and recovery is to name that read in the prompt.

## ux_reference

N/A — reviewer command change with no visual surface.

## Verification

Result: Passed
Evidence: Branch full suite 1804 passed, the same 8 environment failures as `develop`; Ruff, Pyrefly, Vulture and jscpd pass. A real `claude --print` run with the new rules denied `git diff --output` and wrote no file. The same run allowed `git diff`, `git log`, `git show`, `git status`, `git merge-base` and `git ls-files`. `tests/test_challenge.py` 28 passed.
E2E: Passed — the real reviewer CLI ran with the new rules in this cloud session, as above.

Delivery target: Merge
Delivery: Pending — PR into `develop` with the `hard-eng` CI check green.
