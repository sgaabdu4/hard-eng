# HE-YAGNI names operator content as stored data; one clear finding for a token file outside the app

Status: Draft

## Outcome + scope

HE-YAGNI says content that operators own and change (message text, dates, send windows, prices, audiences) is a current requirement for stored data, not code. The UI token reader reports one finding at a CSS `@import` that points to an existing CSS file outside the app, and drops the undefined-token findings that the missing file caused. Non-goals: following or accepting the outside import; the planning case that the issue suggests; package import forms.

## Sources + coverage

Sources: N/A — the request is public issue 635 (read in full) and a maintainer instruction about the outside-import finding; no other source.

## Repository context

Owners: `.agents/skills/he/references/requirements.md` (HE-YAGNI, HE-UI-SOURCE); `.hooks/ui_rules.py` (`ui_findings`, `_css_files`, `_css_import_targets`); `tests/test_ui_rules.py`.
Same cause: N/A — no earlier fix of this cause. The second caller of `_css_files`, `design_weight_findings` in `.hooks/ui_audit_rules.py`, is checked with a `DESIGN.md` fixture; its result is in Verification.
Single source: HE-YAGNI sentence has one owner, the registry entry; the README table holds a short summary of the rule that stays unchanged. The "outside the app" test reuses `_package_dir`, the owner that `_css_files` uses. No other copy found by search.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: Autonomous — the user asked to look at the open Hard Eng issues on 2026-11-23, and the user's standing rule: merge each task PR into develop once its checks pass.

## Acceptance + steps

- [ ] An app whose CSS imports a token file outside the app gets one finding at the import line, naming file and target, and no undefined-token findings → `tests/test_ui_rules.py::test_a_token_file_outside_the_app_is_one_finding_at_its_import`.
- [ ] The same tokens inside the app, and package imports such as `@import "tailwindcss"`, give no finding → `tests/test_ui_rules.py::test_the_same_tokens_inside_the_app_pass`.
- [ ] The finding appears once for a package, whichever file is a candidate, and a comment above the import does not shift its line → `tests/test_ui_rules.py::test_the_outside_import_finding_is_one_per_app_and_keeps_its_line`.
- [ ] HE-YAGNI holds the content sentence and `tests/test_skill_links.py` passes → `tests/test_skill_links.py` and `tests/test_requirements.py` results.
- [ ] The affected check is not slower → N/A — timing, no test can prove it; two compiled runs on each version are in Verification.

## Baseline + execution

Result: Pending
Evidence: Pending — the Draft check on develop 4290fb2d.
Execution: One builder, this session; one independent review on the final head.

## Risks + recovery

A project that imports shared tokens from outside the app now gets a finding at the import. The fix is to move the tokens into the app. Revert the commit to undo.

## ux_reference

N/A — no visible UI; hook and rule text only.

## Verification

Result: Pending
Evidence: Pending.
E2E: N/A — no user journey changes; the hook runs inside the tests through `validate_suppressions` on invented repositories.
Real service: N/A — the change calls no outside service.
Retro: Pending

Delivery target: Merge
Delivery: Pending — `hard-eng` and `canary` pass on the PR to develop.
