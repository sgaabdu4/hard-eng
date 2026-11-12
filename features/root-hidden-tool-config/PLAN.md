# A hidden code file at the package root is tool configuration

Status: Complete

## Outcome + scope

The sources rule of a JavaScript package refused a push when the package root held a hidden settings file with code, such as `.dependency-cruiser.cjs` or `.eslintrc.js`. The printed step asked the project to list the file as a source and to test it. Such a file is tool configuration: a tool reads it at the root, and a test of it proves nothing. Now the rule leaves out a hidden file at the package root whose extension is a configuration extension. Non-goals: hidden files in other folders, other extensions, the list of tool names.

## Repository context

Owners: `.hooks/coverage_sources.py` (`root_tool_config` decides which root files are tool configuration; the source listing of setup and of check call it).
Same cause: the sources rule counted tool configuration at the package root as code. Earlier fix: commit 7390794f left out `<tool>.config.<ext>` names of listed tools (helped; it did not cover hidden files). Other places: searched `root_tool_config`, `TOOL_CONFIGS` and `CONFIG_EXTENSIONS` in `.hooks/`; the two callers are in `coverage_sources.py` and both get the fix through the one function.
Single source: N/A — one function owns the name test; no second copy exists.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: Autonomous. On 2026-11-11 and 2026-11-12 the maintainer told the builder to make the decisions and to fix a fault that the update of a real project shows. Merge after green checks.
Decision: accept each hidden root file with a configuration extension, not a list of tool names, because a tool reads a hidden root file and a list would miss the next tool.

## Acceptance + steps

- [x] Setup and check leave `.dependency-cruiser.cjs` and `.eslintrc.js` at the package root out of the sources → `tests/test_greenfield.py::test_setup_and_check_leave_root_tool_configs_out_of_the_sources`.
- [x] A hidden file in a folder below the root, a root file with no leading dot and a hidden file with a component extension still need listing → `tests/test_greenfield.py::test_runtime_files_beside_tool_configs_still_need_listing`.

## Baseline + execution

Result: Passed
Evidence: `develop` passed required CI at the branch point; the two new pass rows failed before the change and pass after it.
Execution: one session; failing rows first, the one-function fix, the focused tests, the independent review, the full check, PR, release.

## Risks + recovery

A project can keep runtime code in a hidden root file with a configuration extension; the rule no longer asks to list it. Such a file has a tool-style name and is rare. Recovery: revert this pull request.

## ux_reference

N/A — no app screens change.

## Verification

Result: Passed
Evidence: the focused run of `tests/test_greenfield.py` and three neighbor test files gave 184 passed. The result of `python3 .hooks/hard-eng.py check --plan-stage Complete --base origin/develop` is recorded in the pull request.
E2E: N/A — no user journey; the tests run the real setup and check on a project fixture.
Retro: (1) Hard Eng fault that the update of a real project showed: the sources rule asked a project to list and test a hidden settings file → two new pass rows in `tests/test_greenfield.py::test_setup_and_check_leave_root_tool_configs_out_of_the_sources` and three near-miss rows in `tests/test_greenfield.py::test_runtime_files_beside_tool_configs_still_need_listing`.
Delivery target: Merge
Delivery: Pending — the PR checks pass, `ship` passes its ready stage, the rebase merge into `develop` and the release merge into `main` are done, and the `main` run passes.
