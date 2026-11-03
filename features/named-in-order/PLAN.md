# Recognize explicit ordered async work

Status: Complete

## Outcome + scope

Accept named `inOrder` and `inOrderSteps` helpers with explicit reason parameters. Require callers to give a literal reason with at least 20 characters and more than one word. Preserve unrelated loop and sibling-await findings. Keep the Dart self-chain exception. Do not exempt stop-or-timer poll loops. Add the narrow JavaScript reduce-chain rule only if every new corpus finding is a real sequential loop. Explain the shape in efficiency guidance. Repair the inherited-host regression by running its shared contract in-process.

## Repository context

Owners: `.agents/skills/he/semgrep/performance.yaml`, `tests/fixtures/performance/app.dart.txt`, `tests/fixtures/performance/app.ts.txt`, `.agents/skills/he/references/efficiency.md`, and `tests/test_challenge.py`.
Same cause: Existing scanner fixtures did not cover named ordered helpers or their required reasons. Reuse the exact-line scanner test. The inherited-host regression launched nested pytest with a 60-second process deadline; reuse the target test's shared body in-process and clear its opposing host marker there. A search found no other matching nested-pytest launch in the tests. Python and Swift rules, canonical skill repositories, production host detection and scanner execution remain unchanged.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: The maintainer approved named ordered helpers, literal-only reasons, the Dart self-chain exception, generic guidance, the in-process inherited-host test repair as its own commit, and verified feature and release delivery. The poll-loop exception is explicitly rejected. Public content contains synthetic fixtures and generic descriptions only.

## Acceptance + steps

- [x] Exempt the helper definitions by signature while retaining wrong-name, wrong-parameter and missing-reason loop findings. Proof: `tests/test_hot_paths.py::test_each_rule_finds_exactly_the_annotated_lines`.
- [x] Accept adjacent awaits in inline helper callbacks while retaining actual nested-loop findings. Proof: `tests/test_hot_paths.py::test_each_rule_finds_exactly_the_annotated_lines`.
- [x] Flag missing, empty, short, single-word, whitespace, variable, numeric and interpolated reasons in both languages; accept a 20-character multiword literal and both quote styles. Proof: `tests/test_hot_paths.py::test_each_rule_finds_exactly_the_annotated_lines`.
- [x] Keep R1 limited to self-chain awaits; retain sibling work and poll-loop findings. Proof: `tests/test_hot_paths.py::test_each_rule_finds_exactly_the_annotated_lines`.
- [x] Reverting only the rule changes makes the expanded fixture test fail. Proof: `tests/test_hot_paths.py::test_each_rule_finds_exactly_the_annotated_lines` reports 23 missing required findings and nine false findings with original rules.
- [x] Compare both corpus trees in both directions, preserve every fixed finding, and review each added finding. Proof: HE-HOT-PATH. Both trees lose zero current findings and add three real sequential promise chains. Detailed external proof remains private.
- [x] Preserve the Claude-host contract with an inherited opposing marker without launching nested pytest. Proof: `tests/test_challenge.py::test_review_tests_isolate_an_inherited_codex_host` and `tests/test_challenge.py::test_claude_host_runs_codex_read_only_without_user_plugins_and_closed_stdin`. Omitting shared-body marker cleanup reproduces the original ambiguity; all 36 challenge tests pass after cleanup.
- [x] Pass the full native gate and review the final public diff against the approved scope. Proof: HE-HOT-PATH and the native check pass; the outgoing diff contains only the approved rules, synthetic fixtures, efficiency guidance, plan and isolated test repair.

## Baseline + execution

Result: Passed
Evidence: The original six focused scanner tests passed before edits. Expanded fixtures passed with Semgrep 1.183.0. Reverting only the rules failed the exact-line assertion with five other focused tests passing. The source branch starts from the previously verified develop release. External corpus details remain outside this repository.
Execution: One implementation worker edits the existing rule, fixture and guidance owners and verifies the actual scanner behavior.

## Risks + recovery

Static patterns do not prove the truth of a written reason or recognize every hidden sequence. The existing callback-return coverage limit remains. Rule exceptions must not hide unrelated work. Reject any unverified corpus loss. Revert the scoped change if released scanner behavior regresses.

## ux_reference

N/A — Scanner rules and developer guidance have no visual interface.

## Verification

Result: Passed
Evidence: Six focused scanner tests pass. The rule-only negative control detects every new rule category and the new helper and self-chain exceptions. Both corpus comparisons preserve every fixed finding; all added promise-chain findings were reviewed. The in-process host regression reproduces the original ambiguity without marker cleanup, and all 36 challenge tests pass after cleanup. The final full native gate passes all 20 checks, 2,176 tests, five performance tests and 92.14% line coverage. Semgrep 1.183.0 reports zero source findings. The final public diff was reviewed against scope and privacy constraints. No native gate budget or production host logic changed. Independent review not done: this implementation worker did not start another agent. No delivery was performed.
E2E: N/A — No product journey changes. The fixture suite runs the real Semgrep scanner.

Delivery target: Merge
Delivery: Pending: Require feature checks and a guarded merge into develop, successful develop CI, then a develop-to-main release PR with a merge commit and successful main CI.
