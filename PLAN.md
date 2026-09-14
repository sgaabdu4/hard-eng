# Migrate Dart configuration to current lints

Status: Complete

## Outcome + scope

Install/update removes strict-casts and strict-raw-types and enables no_dynamic_casts and no_raw_types, retaining strict-inference. Validation rejects obsolete keys in root, nested and included analysis options, including keys set to false. Preserve unrelated project settings. Remove accumulated obsolete task history from this plan.

## Repository context

setup.py configures Dart using the runner's shared defaults. .hooks/hard-eng.py already traverses included and nested options. tests/test_dart_config.py owns preservation, migration and rejection coverage. No new helper, compatibility branch, dependency or test file.

## Decisions + authorization

Blockers: None

The user explicitly requires migration to the new rules and removal of unnecessary or legacy material. Existing authorization covers source fixes, full verification, PR, merge to origin/main and completed-branch cleanup. One builder owns the change; no other project's implementation is edited.

## Acceptance + steps

- [x] Setup removes both obsolete keys, keeps the current required lints and preserves unrelated settings.
- [x] Repeated setup produces the same migrated configuration.
- [x] Root, included and nested obsolete settings fail, including false-valued keys.
- [x] Missing either current lint still fails.
- [x] Existing regression owners cover the change without new test machinery.

## Baseline + execution

Result: Passed
Evidence: Unchanged source 646037b627441bee523276f2bd1e464eb7c8df62 passed all 17 checks, 470 regressions and four performance tests, PR68/main CI and native delivery. Pre-edit Ready check passed at /tmp/he-dart-modern-ready.log. Main CI for PR68 first encountered a Semgrep timeout and passed an unchanged retry; that reliability issue remains open.

## Risks + recovery

This profile requires Dart 3.13+. Included configuration containing obsolete keys must be updated at its owner. The separate Flutter skill repository's migration task has received the modern-only requirement; its delivered submodule revision is still pending. Revert only this scoped change if necessary.

## ux_reference

N/A — installer and CLI policy changes have no visual application surface.

## Verification

Result: Passed
Evidence: Four existing regression cases failed against the original validator (/tmp/he-dart-modern-red.log). All 71 setup/configuration cases pass after repair (/tmp/he-dart-modern-tests-final.log), including migration, preservation, repeatability, included/nested rejection and missing-lint rejection. A legacy-only configuration migrated through the real installer and passed native Dart 3.13.3 analysis. The first Complete run rejected installer complexity; reusing dart_rule_settings removed duplicated validation and native lint now passes. Final Complete rerun follows.

Delivery target: Merge
Final Complete gate passed all 17 checks, 470 regression tests and four performance tests (/tmp/he-dart-modern-complete-final.log). Ready for ship — local implementation and verification complete; delivery not performed.

Delivery: Pending — PR CI, exact main CI, native delivered and branch cleanup remain required.

Outstanding coordinated work: Frontline's baseline delivery and supported source adoption; the broader efficiency/complexity audit, including recurring Semgrep timeouts; the separately owned Flutter skill reference update. StaffToDo's prior revision passed main workflows and delivery, but its default run skipped live runtime smoke. These are not completed by this source change.
