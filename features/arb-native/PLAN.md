# Count a Flutter localization file as a native change

Status: Complete

## Outcome + scope

A change to a Flutter `.arb` localization file, with `.dart` screens, needs a native Before and After pair, as the `.dart` files alone do. It no longer asks for a measured browser capture, so an installed Flutter project can push. A web change with an `.arb` file still needs a browser capture. Non-goals: the whole-screen audit source list (`NATIVE_SUFFIXES`), which holds source files and no `.arb` file; a hook that tells a Flutter web build from a device build.

## Sources + coverage

Sources: the maintainer's request of 2026-11-24 to ship this fix to `main` as a hotfix, read in full. The `develop` commits of the same fix (`fd56959f`, `de947987`, `b752cf87`, `31cc9b3e`), read in full.
Reviewer: N/A — a one-word fix with a stated set of cases that must keep failing.
Deliverables: None

- A Flutter change with an `.arb` file passes ship with a native pair: In scope — A Flutter change with an `.arb` file passes ship with a native pair
- A web change with an `.arb` file still needs a browser capture: In scope — A web change with an `.arb` file still needs a browser capture
- The local Complete check takes an `.arb` file as native: In scope — The local Complete check takes an `.arb` file as native

## Repository context

Owners: `.hooks/ui_proof.py` (`NATIVE`, `is_native`) owns the native file set. `is_visible` already listed `.arb` as visible, so the native set was the only part that did not know it.
Same cause: searched `NATIVE`, `is_native` and `.arb` in `.hooks` and `tests`; one owner, no other copy of the set. `NATIVE_SUFFIXES` lists source files for the whole-screen audit; an `.arb` file holds no widget source, so it stays as it is.
Single source: the set stays in `NATIVE`.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: Autonomous — the user asked on 2026-11-23 to fix every Hard Eng fault found in the rollout; standing rule: merge each task PR once its checks pass.

## Acceptance + steps

- [x] A localization file alone, and with `.dart` files, is native; with a `.tsx` file it is not → `tests/test_ui_native_set.py::test_a_localization_file_alone_is_a_native_change`
- [x] A Flutter change with an `.arb` file passes ship with a native pair → `tests/test_ui_native_set.py::test_a_flutter_change_with_a_localization_file_needs_only_the_native_proof`
- [x] A web change with an `.arb` file still needs a browser capture → `tests/test_ui_native_set.py::test_a_web_change_with_a_localization_file_still_needs_a_browser_capture`
- [x] The local Complete check takes an `.arb` file as native → `tests/test_ui_native_set.py::test_the_local_complete_check_takes_a_localization_file_as_native`

## Baseline + execution

Result: Passed
Evidence: On `origin/main` at 8180972d, `ui_proof.NATIVE` is `(".dart", ".swift")`; the new tests fail there (red commit `2b8b3b3b`, exit 1).
Execution: Two cherry-picks from `develop` (`fd56959f` tests, `de947987` fix), tests first.

## Risks + recovery

A translation-only `.arb` change of a Flutter web build passes with a native screenshot and no browser capture. `is_native` already treats every `.dart` change of such a build the same way, and no hook tells a Flutter web build from a device build. Recovery: revert the commits.
Not checked: a real Flutter project push.

## ux_reference

N/A — no screen changes; Hard Eng has no app UI.

## Verification

Result: Passed
Evidence: Red first: `tests/test_ui_native_set.py` failed on `origin/main` code at the red commit (exit 1) and passed with the one-word fix (4 passed). The Ready check on e76752e4 passed: 7658 tests, and every static and native check, including format, lint, complexity, annotations, types, dead-code, duplicates and security. The first Ready run failed the duplicates check because the new test copied a Flutter fixture of `tests/test_local_ui_proof.py`; both files now share `flutter_app_root`. `challenge` at e76752e4 printed `Review by a fresh claude session at e76752e48f45: clean` (Codex was over its usage limit; agy refused its argument form). Full check: the `check --plan-stage Complete` run on the final head and the CI runs of the PR.
E2E: N/A — the proof is the ship and Complete check tests above; no journey of an app is changed.
Real service: N/A — no outside service is called.
Retro: (1) Fault on the base branch, a Flutter `.arb` file with `.dart` screens asked for a browser capture → `tests/test_ui_native_set.py::test_a_localization_file_alone_is_a_native_change`. (2) The duplicates check failed on the copied Flutter fixture, so both test files share `flutter_app_root` → `tests/test_ui_native_set.py::test_the_local_complete_check_takes_a_localization_file_as_native`. (3) A review found the Complete plan had no `Retro:` line; this line is the fix, and the Complete check reads it.

Delivery target: Merge
Delivery: Pending — CI, the merge into `main`, then the join of `main` into `develop`.
