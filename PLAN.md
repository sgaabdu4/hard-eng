# Adopt the corrected Flutter lint profile

Status: Complete

## Outcome + scope

Fresh and updated Flutter projects use the released flutter_skill_lints ^0.11.2 profile. Upgrade known old0.11.0/0.11.1 declarations through the existing migration while preserving current, newer, custom and absent declarations.

## Repository context

The linked building-flutter-apps skill still points to a441039 and its ^0.11.0 template. project_setup.migrate_dart_plugins handles only0.0–0.10. Canonical skill5.10.2 at98b6e42 and lint0.11.2 at6b43340 are released with passing exact-commit CI and trusted publication.

## Decisions + authorization

Blockers: None

The user authorized using corrected latest releases, repairing adoption and delivering source changes. One builder advances the existing submodule, extends the existing known-old pattern and updates the existing Dart configuration tests. No new file, dependency, resolver or compatibility layer. Canonical skill metadata, references and hosted fixture were reviewed under Writing Great Skills.

## Acceptance + steps

- [x] The linked canonical template requires ^0.11.2 and retains riverpod_lint ^3.1.9.
- [x] Exact and caret0.11.0/0.11.1 declarations migrate automatically with existing older pins.
- [x] Current/newer/custom/absent declarations and project analysis settings remain intact; repeating configuration is idempotent.
- [x] Existing configuration, installer and update suites pass; final integration follows below.

## Baseline + execution

Result: Passed
Evidence: Starting sourceb682126 passed17 gates,504 tests,four performance checks and exact main CI34864008477. The published lint0.11.2 has successful Dart CI34865292958,Hard Eng CI34865292902 and publication34865785889 at6b43340087f7a03f8460cb0872d93e4e8d5928fb. Canonical skill98b6e42f5c87b27340a19c9172d7d415d3352a7e has successful settlement CI34866797134. Its release owner reports a separate successful local compatibility fixture against hosted packages. The adoption gap is identified in the existing source owners.

## Risks + recovery

Restrict migration to known old exact/caret declarations, using the canonical template as the only replacement-version owner. Retain included rules and project settings. Existing candidate validation and rollback remain required. Do not treat package publication as consumer installation proof.

## ux_reference

N/A — dependency declarations and installer migration have no visible interface.

## Verification

Result: Passed
Evidence: The four exact/caret0.11.0/0.11.1 regression cases fail against the original migration and pass after the bounded pattern change.119 configuration, installer and update tests pass; Ruff formatting/lint and Pyrefly pass. The linked canonical skill, exact settlement CI and separate compatibility-run handoff were reviewed. Final integrated result follows below.

Delivery target: Merge
Ready for ship — final Complete gate passed17 checks,510 tests and four performance checks. The full test suite completed in115.37seconds; no suppressed checks or project changes.
Delivery: Pending — PR/main CI, native delivery verification and consumer adoption confirmation.
