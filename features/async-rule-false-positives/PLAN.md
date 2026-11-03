# Correct async performance rule false positives

Status: Complete

## Outcome + scope

Correct callback scope and dependency matching in the Dart and JavaScript performance rules. Exempt stepped batch joins and awaited throw guards. Keep memo fills flagged. Preserve callback-return exceptions and all Python and Swift rules. Isolate challenge-test host markers without changing production detection.

## Repository context

Owners: `.agents/skills/he/semgrep/performance.yaml`, `tests/fixtures/performance/app.dart.txt`, `tests/fixtures/performance/app.ts.txt`, `tests/test_hot_paths.py`, and `tests/test_challenge.py`.
Same cause: The existing fixture test lacked callback-boundary, nested dependency, batch join and throw-guard cases. Search covered every await-loop and sequential-await rule. This change repairs the demonstrated Dart and JavaScript cases; Python and Swift rules remain outside scope. Challenge tests set one host marker without clearing the inherited other marker. The existing branch fixture now isolates both markers; the one independent reviewer test clears its unused marker directly.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: The maintainer approved the scoped rule fixes, challenge-test isolation repair and verified feature and release PRs. Public content uses synthetic fixtures and generic descriptions. Canonical skill repositories and formatting remain unchanged.

## Acceptance + steps

- [x] Match complete Dart await statements and uses inside callbacks; retain independent sibling findings. Proof: `tests/test_hot_paths.py::test_each_rule_finds_exactly_the_annotated_lines`.
- [x] Recognize JavaScript result uses inside callback bodies; retain independent callback findings. Proof: `tests/test_hot_paths.py::test_each_rule_finds_exactly_the_annotated_lines`.
- [x] Exclude awaits inside nested async callbacks while retaining actual loop awaits and loops inside callbacks. Proof: `tests/test_hot_paths.py::test_each_rule_finds_exactly_the_annotated_lines`.
- [x] Exempt only join awaits in stepped loops and awaits that guard a throw; retain ordinary loop awaits and memo fills. Proof: `tests/test_hot_paths.py::test_each_rule_finds_exactly_the_annotated_lines`.
- [x] Prove the fixture regression with original rules, pass the full native gate, and review both directions of the external corpus comparison. Proof: HE-HOT-PATH and the native check. Detailed external evidence remains outside this repository.
- [x] Challenge tests choose their declared host even when the caller supplies the other host marker. Proof: `tests/test_challenge.py::test_review_tests_isolate_an_inherited_codex_host`.

## Baseline + execution

Result: Passed
Evidence: Fresh origin/develop checkout passed shipped-format with Biome 2.6.4 on all 173 files. Both latest base-branch CI runs also passed shipped-format with 2.6.4. An earlier scratch checkout's identical 71 diagnostics do not reproduce in the fresh checkout; no format repair was made. Original rules with expanded fixtures failed the exact-line assertion, with five other focused tests passing. Updated rules passed all six focused tests with Semgrep 1.183.0. The new host-isolation regression failed before the fixture repair with the expected ambiguous-host error.
Execution: One implementation worker applies the approved design and verifies scanner behavior at the existing fixture test.

## Risks + recovery

The Dart expression matcher can miss pairs with unmatched bracket characters inside strings. Callback-return exceptions retain their known coverage limit. The latest main CI run failed a Swift coverage test without swiftc. No sibling skip guard exists; that test remains unchanged under the maintainer's conditional scope. Current PR checks must pass before merge. Revert the scoped commit if scanner behavior regresses.

## ux_reference

N/A — Scanner rules and synthetic fixtures have no visual interface.

## Verification

Result: Passed
Evidence: All six focused scanner tests passed. Reverting only the rule file restored the exact-line failure with five tests passing. All 36 challenge tests pass in the normal environment; the added inherited-host regression failed before the cleanup repair and passed afterward. The final full native gate passed all 20 checks, 2,176 tests, five performance tests and 92.15% line coverage. Semgrep 1.183.0 reported zero source security findings. Shipped-format passed with Biome 2.6.4. External corpus checks passed; their detailed evidence stays local. Independent review not done: this implementation worker did not start another agent.
E2E: N/A — No product journey changes. The fixture suite executes the real Semgrep scanner.

Delivery target: Merge
Delivery: Pending: Require the current PR checks and guarded merge into develop. Release uses the repository's develop-to-main path.
