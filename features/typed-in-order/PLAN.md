# Recognize typed ordered helper definitions

Status: Complete

## Outcome + scope

Accept the typed TypeScript equivalents of the two approved JavaScript helper signatures. Preserve wrong-signature findings and all other rules. Repair the required shipped-format command to apply its existing formatter configuration explicitly.

## Repository context

Owners: `.agents/skills/he/semgrep/performance.yaml`, `tests/fixtures/performance/app.ts.txt`, and the existing shipped-format command in `hard-eng.gates.json`.
Same cause: The previous named-helper repair covered untyped JavaScript and Dart definitions, but omitted typed TypeScript definitions. The existing exact-line fixture test now covers both accepted typed definitions and typed wrong signatures. No new checker is needed.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: The maintainer approved this narrow rule repair, fixtures, corpus comparison, native gate and feature delivery to develop. Release delivery to main waits for independent review results.

## Acceptance + steps

- [x] Accept both matching typed definitions while retaining typed wrong-signature findings: `tests/test_hot_paths.py::test_each_rule_finds_exactly_the_annotated_lines`.
- [x] Reproduce the escaped false positives before repair: `tests/test_hot_paths.py::test_each_rule_finds_exactly_the_annotated_lines` fails with exactly two extra findings using the original rule.
- [x] Preserve every real finding in the external corpus: HE-HOT-PATH, before/after comparison removes only the two accepted typed-helper findings. No fixed finding is lost.
- [x] Pass the full native gate and review the public diff: HE-HOT-PATH and repository-native checks; all 20 checks pass, including 2,176 tests and five performance tests.
- [x] Preserve HE-NO-SWITCH-OFF while selecting the existing formatter configuration: the native command checks all 173 files unchanged; the isolated malformed-format control exits 1.

## Baseline + execution

Result: Passed
Evidence: The starting develop revision records six passing focused scanner tests in the named-helper plan. The new fixture reproduced exactly two false positives with the original rule. All six focused tests pass after this repair. The first full-gate attempt stopped at the missing-plan guard before native checks.
Execution: One builder changes the existing rule and fixture owners, then compares the corpus and runs native checks. Independent reviewers remain coordinator-owned.

## Risks + recovery

The exception must not accept a wrong parameter count or options shape. Exact-line negative fixtures remain enforced. Revert this scoped rule change if scanner behavior regresses.

## ux_reference

N/A — Static scanner rules have no visual interface.

## Verification

Result: Passed
Evidence: Six focused scanner tests pass. The red run proves the original defect. Corpus comparison removes only the two accepted helper findings. The first native run found 71 shipped-format errors because the command did not select its existing configuration; an explicit-config probe checked the same 173 files successfully without source edits, and malformed formatting still fails. Six test failures came from placing TMPDIR inside the ignored source checkout: scanner fixtures were ignored and outside-repository fixtures remained inside Git. The final private TMPDIR is outside the repository. All 20 native checks pass, including 2,176 tests, five performance tests, zero source security findings, and 92.14% line coverage. The public diff contains only the two typed exemptions, synthetic fixtures, this plan, and the prerequisite formatter-command repair. Independent reviews remain coordinator-owned and pending; no additional reviewer was started.
E2E: N/A — No product journey changes; the fixture test invokes the real scanner.

Delivery target: Merge
Delivery: Pending — feature PR and develop CI, then a develop-to-main release PR with a merge commit after the coordinator releases the review hold.
