# Update native Flutter analyzer configuration

Status: Complete

## Outcome + scope

Upgrade older ordinary version declarations for both managed analyzer plugins to the installed canonical profile. Support the native version mapping without discarding its other settings; preserve custom package sources and newer or nonstandard constraints. Accept Flutter's native build/platform exclusions without hiding handwritten Dart source.

## Repository context

The existing migrate_dart_plugins helper only recognizes the Flutter plugin's string form. A native version mapping stays outdated, and the companion Riverpod plugin is never compared. The same helper serves setup and the stale-version validation check. Native Flutter pub get also restores build/platform exclusions which the existing validator rejects; the stable Flutter source confirms this automatic migration.

## Decisions + authorization

Blockers: None
Autonomous source repair, regression proof and PR/main delivery are authorized. Change the existing configuration owners and their test matrix. Move the exclusion implementation into the existing native setup owner to retain the source file limit; keep the current validator entrypoint. The modern plugin profile is the target, including migration of old major declarations; do not add legacy custom_lint support. The installed updater's application gate must reject incompatible candidates. No new dependency, file or configuration engine is needed.

## Acceptance + steps

- [x] Old exact/caret versions migrate in string and mapping forms for both managed plugins.
- [x] Mapping settings and custom sources remain intact; current/newer/nonstandard constraints remain unchanged.
- [x] Repeated setup is stable and stale-version validation rejects the formerly missed declarations.
- [x] Flutter's native platform/build exclusions pass while handwritten or unsafe excluded Dart files still fail; pure-Dart and arbitrary source exclusions stay blocked.
- [x] Native source checks and focused adversarial review pass before shipping.

## Baseline + execution

Result: Passed
Evidence: The starting tree f8f77b08d35531b348598e3a41dddf76f7ae9779 is identical to b235ad173a1f2dd7e668579774c0e8d048751eb1, verified with git diff --exit-code. That tree passed the native Complete gate with 618 tests and four performance cases, native isolated pre-push in 170.20 seconds, and current main CI in 132 seconds. Reuse that matching source proof; first extend the existing regression to reproduce the missed declarations.

Baseline repair: the native Flutter probe then demonstrated that pub get re-adds build/platform exclusions, causing the old validator to fail. This confirmed compatibility failure reopens the affected readiness decision; repair it alongside the reproduced plugin cases before completing the source gate.

## Risks + recovery

Do not overwrite path, git or custom hosted sources. Preserve diagnostic settings while updating only an ordinary version field. Keep installed canonical versions aligned with published packages; no registry polling on every command.

## ux_reference

N/A — this changes CLI setup and validation only.

## Verification

Result: Passed
Evidence: The native Draft gate passed all 633 tests, four performance cases and every configured static/security check. Astra identified an overlap between generated-file globs and ignored Flutter build output; the reproducing regression failed before the repair and passed afterward. Fable reviewed the final configuration owner and callers: its older-major compatibility concern is resolved by the explicit modern-only scope, version-specific migration diagnostic and documented candidate gate; its stale README finding is corrected. The extended configuration matrix passes 43 cases, including older-major declarations. Final affected lint/type checks pass. Required pre-push and hosted checks remain delivery proof.
E2E: Passed — a synthetic project created by the installed stable Flutter SDK retained its native platform/build exclusions through setup. Both old plugin declarations upgraded to the canonical versions while mapping diagnostics survived; subsequent native flutter pub get preserved the analyzer configuration byte-for-byte. Repeated fixture setup and stale-version rejection also passed. Published consumer update acceptance follows delivery and is not claimed here.

Delivery target: Merge
Delivery: Pending — PR/main checks and delivered verification remain required.
