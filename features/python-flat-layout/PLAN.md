# New Python projects keep a flat layout

Status: Complete

## Outcome + scope

The release canary on `develop` 5d85101 showed the new Python starter failing its own tests on macOS: "No module named 'main'". uv 0.12 makes `uv init --app` a package (`src/<name>/`, a `[build-system]`). Setup then sees a packaged project and adds no pytest `pythonpath`, so the starter's root `main.py` is not importable. `setup.sh --new python` now runs `uv init --app --no-package`, which gives the same flat layout on every uv version.

Non-goals: other canary failures (project-side failures, load timeouts, an agent run that broke a lint rule).

## Repository context

Owners: `new_project.py` (`SCAFFOLDS["python"]`). Test in `tests/test_new_project.py`.
Same cause: no other scaffold uses `uv init`; the release canary creates its greenfield target through `--new python`.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: On 2026-10-23 the user chose "Fix first, then release" for new-project failures in the canary.
Decided: pass `--no-package` rather than add a pytest path for packaged projects, because the starter is a flat application and uv 0.11 already made that layout.

## Acceptance + steps

- [x] The Python scaffold asks uv for an unpackaged project → `tests/test_new_project.py::test_python_locks_the_scaffold_and_adds_tested_starter_code`.

## Baseline + execution

Result: Passed
Evidence: On the maintainer's Mac with uv 0.12.19, `setup.sh --new python` made `src/he_py/`, a `[build-system]` and no pytest `pythonpath`. Both starter test files failed to import `main`. With uv 0.11 in the cloud, the same setup passes every gate.
Execution: One builder, this session.

## Risks + recovery

Recovery: revert this commit.

## ux_reference

N/A — no visible UI change.

## Verification

Result: Passed
Evidence: `python3 .hooks/hard-eng.py check --base origin/develop` in the cloud container; PR CI runs it with every toolchain; the release canary reruns on the maintainer's Mac before main.
E2E: N/A — no user journey; the canary is the end-to-end run.

Delivery target: Merge
Delivery: Pending — PR checks and merge.
