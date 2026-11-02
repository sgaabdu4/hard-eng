# Adoption loads PyYAML before it records debt

Status: Complete

## Outcome + scope

`adopt` restarts with PyYAML when the running Python lacks it, as `check` already does, so a gate that needs PyYAML runs and its real findings become debt. Non-goals: the debt format, which gates are recordable, and how `run_gate` reports a gate that raises.

## Repository context

Owners: `main` in `.hooks/hard-eng.py` calls `ensure_python_runtime` (`.hooks/tool_setup.py`) for `check` only; `adopt` reaches `run_gates` through `deliver` without it. The zizmor gate builds its configuration with PyYAML in `gitleaks_scan.zizmor_config`.
Cause (seen on 2026-11-02 with the release canary's pinned brownfield snapshot, pallets/itsdangerous 672971d, on a Mac whose `python3` is Python 3.15 without PyYAML): `adopt` ran zizmor's gate, which raised `No module named 'yaml'` before zizmor started. `run_gate` passed that text to the debt outputs, so `hard-eng.debt.json` recorded `"No module named 'yaml'": 1` for `./zizmor`. The next `check` restarted with PyYAML, zizmor ran and reported the workflow findings, and the gate failed on findings beyond the debt. Claude and Codex sessions in that project both stopped at the baseline check.
Same cause: afc1973 (#83) added `ensure_python_runtime` to `check` and setup (helped). Searched every caller of `run_gates`: only `check` and `adopt` run gates in process; the Stop hook, pre-push and CI start `hard-eng.py check` as a command, which restarts itself. This change covers the remaining entry point.
Escaped bug: the test gate should have caught it. The new test fails on develop b24b9fa with `Failed: adopted without PyYAML`. The public Canary job did not catch it because `release_canary.py` runs under `uv run`, whose Python has PyYAML.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: the maintainer asked for every release check to be tested and gave full authority to fix what fails.
Decided: reuse `ensure_python_runtime` at the start of `adopt`, before the check lock, so both entry points restart the same way. Not in `main`, which is at the 50-statement limit.

## Acceptance + steps

- [x] `adopt` restarts with PyYAML when the running Python lacks it → `tests/test_debt.py::test_adoption_restarts_with_pyyaml_like_the_check`.
- [x] Adoption still records what the fixed code fails with → `tests/test_debt.py::test_adoption_records_what_the_fixed_code_still_fails_with[True]`.

## Baseline + execution

Result: Passed
Evidence: on develop b24b9fa the new test failed with `Failed: adopted without PyYAML`; `tests/test_debt.py` otherwise passed.
Execution: One builder, this session. Failing test, then the restart at the start of `adopt`. A first version in `main` failed `lint` and `complexity` (51 statements), and its test lambdas failed `types`; both were fixed in code.

## Risks + recovery

`adopt` now needs `uv` when the running Python lacks PyYAML, as `check` already does. Revert the commit to restore the old dispatch.

## ux_reference

N/A — command behavior with no visual surface.

## Verification

Result: Passed
Evidence: `tests/test_debt.py`: 12 passed. Brownfield proof with Python 3.15 without PyYAML: the release canary's `install_new` for the itsdangerous snapshot, using this branch's setup, recorded 376 zizmor lines and no `No module named` line; a full `check` in that project then exited 0, with zizmor held by its debt.
E2E: Passed — the brownfield proof above runs the real install, `adopt` and `check` commands on the public snapshot.

Delivery target: Merge
Delivery: Pending — PR into `develop` with the `hard-eng` CI check green.
