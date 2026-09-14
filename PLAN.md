# Adopt modern Flutter skill guidance

Status: Complete

## Outcome + scope

Pin the existing building-flutter-apps submodule to verified v5.10.1 at b3cf78658bd92d8eeb41a4cc6d4e4878664ba313. Supported installs must distribute modern-only Dart guidance and the corrected examples. No copied skill files, new dependency or compatibility branch.

## Repository context

.agents/skills/building-flutter-apps links into the existing submodule. The released analysis profile uses strict-inference, no_dynamic_casts and no_raw_types with flutter_skill_lints 0.11.0. The v5.10.0 Axis.center example was caught during review and corrected upstream before adoption.

## Decisions + authorization

Blockers: None

The user requires current-only Dart and removal of obsolete material; existing authorization covers source fixes, verification, PR, main delivery and completed-branch cleanup. The owning skill task requested v5.10.1 adoption. Remote tag and main independently resolve to the exact revision above. One builder owns the pin update.

## Acceptance + steps

- [x] Pinned skill version and analysis profile match v5.10.1; no obsolete strict-casts or strict-raw-types remain in the skill.
- [x] Supported installer tests copy the pinned skill; skill metadata and relevant reference links validate.

## Baseline + execution

Result: Passed
Evidence: Unchanged Hard Eng 8fa6e0f9b4e523ddb8722e19b304a9c82500c389 passed all 17 gates, 470 regression tests and four performance tests; PR69 CI34819951955, main CI34820180481 and native delivered passed. Both source and submodule worktrees were clean before adoption.

## Risks + recovery

The released skill requires Dart3.13+/Flutter3.47+ and published flutter_skill_lints0.11.0, whose availability was independently checked. Root source migration already removes obsolete language flags. Revert only the pin if required, preserving project-owned settings and pending consumer work.

## ux_reference

N/A — a skill dependency pin has no visual application surface.

## Verification

Result: Passed
Evidence: Pre-edit Ready gate passed (/tmp/he-flutter-modern-ready.log). Reviewed the upstream skill diff and corrected example against the installed Flutter Axis enum. All 61 installer tests passed (/tmp/he-flutter-modern-setup.log), including byte-for-byte installed skill content and preserved project instructions. Native skill metadata validation passed; all 106 relative links in the entrypoint and changed references resolve. No obsolete flags or Axis.center remain in the skill's Markdown/YAML. Final Complete gate follows.

Delivery target: Merge
Final Complete gate passed all 17 checks, 470 regressions and four performance tests (/tmp/he-flutter-modern-complete.log). Ready for ship — local implementation and verification complete; delivery not performed.

Delivery: Pending — PR CI, exact main CI, native delivered and completed-branch cleanup.

Outstanding coordinated work: Frontline baseline delivery and supported adoption; broader efficiency/complexity audit including recurring Semgrep timeouts. StaffToDo's delivered revision passed main workflows, but its default run skipped live runtime smoke.
