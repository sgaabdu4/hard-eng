# Mutation testing for root-level Python modules

Status: Complete

## Outcome + scope

Report-only Python mutation testing runs when the changed code is a module at the package root, such as `main.py`, instead of stopping with "Could not figure out where the code to mutate is". Tests that read other tracked files still find them in mutmut's copy.
Non-goals: no change to which lines are mutated, to the report, or to projects that configure mutmut themselves.

## Repository context

Owners: [mutation.py](../../.hooks/mutation.py) `python`.
Evidence: mutmut reads `source_paths` only from `[tool.mutmut]` in pyproject.toml or `[mutmut]` in setup.cfg, and otherwise guesses `lib/`, `src/` or a folder named after the checkout. A flat project, including this repository's root-level scripts, stopped there. mutmut then copies only the source paths, `tests/`, `test/` and lockfiles, so tests that read other tracked files failed in its copy.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: The user asked to fix this Hard Eng fault on a branch from main.
Decisions: When the project has no mutmut section, append one into the throwaway checkout mutation always runs in: `source_paths` lists the changed files' top-level paths, and `also_copy` lists every other tracked top-level path. A project's own mutmut section is kept unchanged.

## Acceptance + steps

- [x] A changed root-level module gets real survivors reported, like a `src/` package → `test_python_mutation_reports_real_survivors_on_changed_lines[price.py]`, red before with mutmut's "Could not figure out where the code to mutate is".
- [x] A project's own mutmut settings win, including a `[mutmut]` header with a trailing comment or indent → `test_mutmut_keeps_the_projects_own_source_paths`, red before for those headers (Codex review round 2).
- [x] The rest of setup.cfg stays byte for byte, so case-sensitive keys such as `DJANGO_SETTINGS_MODULE` survive, and an empty copy list is left out → `test_mutmut_settings_keep_the_rest_of_setup_cfg`, red before (Codex review round 1: ConfigParser lowercased the keys).
- [x] Full `python3 .hooks/hard-eng.py check` passes.

## Baseline + execution

Result: Passed
Evidence: The base commit passed required CI on main.
Execution: Red test, fix, focused tests, a real run on a root-level script change in this repository, full check, challenge, Codex loop, PR, CI, release canary, merge.

## Risks + recovery

Copying every tracked top-level path makes mutmut's copy larger; mutation is report-only and never blocks a push. Recovery is reverting this branch.

## ux_reference

N/A — report-only tooling; no product appearance.

## Verification

Result: Passed
Evidence: Each new test failed before its fix and passed after; 26 mutation tests passed. A real run on a change to this repository's root-level canary script now finds the code and runs the test suite in mutmut's copy. There, one shipping test fails only under mutmut's own pytest runner: the same suite passes in one process from the repository and from a copy laid out like mutmut's (1617 passed), so that is outside this change.
E2E: Passed — the parametrised test drives real mutmut through uv on a flat project.

Delivery target: Merge
Delivery: Pending — PR CI, release canary on the PR head, merge.
