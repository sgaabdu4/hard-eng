# Session start no longer crashes in a Dart or Flutter project when python3 has no PyYAML

Status: Complete

## Outcome + scope

The SessionStart hook prints its status in a Dart or Flutter project when the hook's `python3` has no PyYAML. Before, it ended with a traceback and exit 1, and the session got no Hard Eng status. The gate line then says that the gates were not checked at session start and that `check` runs them. Non-goals: a YAML reader of our own for `pubspec.yaml`, a restart of the hook through uv (it would slow each session start), and the other findings of the round 4 audit, which get their own plan.

## Repository context

Owners: `gate_status` in `.hooks/agent_hooks.py` owns the gate line of session start. It is the only hook caller of `load_groups`.
Bug evidence: on 2026-11-10 an audit run in a Flutter project printed `ModuleNotFoundError: No module named 'yaml'` from `dependency_command` in `.hooks/project_setup.py`, reached through `require_swift_groups` and `flutter_apps`, with exit 1 and no hook output. A second run by the coordinator, with the hook command as the host runs it, gave the same result. `check` works in the same project, because it restarts itself through uv with PyYAML.
Same cause: the hook runs under the plain `python3`, and gate validation for Dart reads `pubspec.yaml` with PyYAML. Three imports sit on that path: two in `.hooks/project_setup.py` (`dependency_command`, `workspace_members`) and one in `.hooks/swift_setup.py` (`local_plugin_folders`). The one new `except` in `gate_status` covers all three. No earlier fix of this cause exists. The Stop hook does not call `load_groups` itself; it starts `check`, which has PyYAML.
Single source: the gate line has one owner, `gate_status`. No second copy of the new sentence exists.
Escaped bug: the crash is on the base branch since the commit of 2026-10-16 that added the Swift checks for Flutter apps. The test gate should have caught it: no test ran session start for a Dart project without PyYAML. The new test fails on `develop` 399ae2db with the same `ModuleNotFoundError`.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: Autonomous. On 2026-11-10 the maintainer told the builder to run the audit and fix rounds autonomously and to follow Hard Eng and Learn.
Decision: the hook does not restart through uv. That adds a process start to each session start, and hooks must not get slower. The new code runs only when the import fails.
Decision: only a missing `yaml` module gets the new line. Any other missing module still raises, because `check` cannot install it.
Decision: this fix ships alone, before the other round 4 fixes, so that installed Flutter projects get it with their next update. The update still starts in those projects today: `session_context` starts it before it reads the gate line.

## Acceptance + steps

- [x] Session start in a Flutter project with no `yaml` module returns a gate line that says the gates were not checked and names PyYAML → `tests/test_swift.py::test_session_start_survives_a_python_without_the_yaml_module`.

## Baseline + execution

Result: Passed
Evidence: the starting tree is `develop` 399ae2db. On that commit the `hard-eng` and `canary` CI checks passed on 2026-11-10, and the pre-push full check on the same tree passed that day with 20 gates and 2,411 tests.
Execution: this session, one builder.

## Risks + recovery

- In a Dart or Flutter project on a machine without PyYAML, session start says "not checked" each time. A broken gate file then shows first at Stop or at `check`, not at session start. Recovery: none needed; `check` validates the same file.
- Recovery for the change: revert its commit.

## ux_reference

N/A — one hook status line with no visual surface.

## Verification

Result: Passed
Evidence: the new test failed first on the unchanged code with `ModuleNotFoundError` raised from `.hooks/project_setup.py` through `flutter_apps`, and passes after the fix. The Swift and agent hook test files pass: 171 tests. Lint, format, types and the hot path scan pass on the two changed files. In a real Flutter project made with the scaffold, the hook command as the host runs it exits 0 with valid JSON and the new line; before the fix it exited 1 with a traceback and no output.
Speed: no timing run. The change adds one `except` clause, which runs only when the import fails.
E2E: N/A — no user journey; the hook command was run directly in a real Flutter project.
Retro: these items, each sorted by HE Learn's Retro rows.

- Bug found on the base branch: session start crashed in Dart and Flutter projects without PyYAML → mechanical: `tests/test_swift.py::test_session_start_survives_a_python_without_the_yaml_module`, at the test gate that should have caught it.
- Ran too late: the quick check refused the commit with no plan, because this hook file always needs one → None — the size rule did its job at the first check after the commit; the plan is in this change.

Delivery target: Merge
Delivery: Pending — PR into `develop` with the `hard-eng` CI check green, then the release into `main`.
