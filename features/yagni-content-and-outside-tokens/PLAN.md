# HE-YAGNI names operator content as stored data; one clear finding for a token file outside the app

Status: Ready

## Outcome + scope

HE-YAGNI says content that operators own and change (message text, dates, send windows, prices, audiences) is a current requirement for stored data, not code. The UI token reader reports one finding at a CSS `@import` that points to an existing CSS file outside the app, and drops the undefined-token and `DESIGN.md` weight findings that the missing file caused. The shared rules line for a failing check says that Hard Eng is strict and is broken only when no project change passes. Non-goals: following or accepting the outside import; the planning case that the issue suggests; package import forms.

## Sources + coverage

Sources: N/A — the request is public issue 635 (read in full) and two maintainer instructions, one about the outside-import finding and one about the failing-check line; no other source.

## Repository context

Owners: `.agents/skills/he/references/requirements.md` (HE-YAGNI, HE-UI-SOURCE); `.hooks/ui_rules.py` (`ui_findings`, `_css_files`, `_css_import_targets`); `tests/test_ui_outside_tokens.py`; `.hooks/ui_css_imports.py`.
Same cause: N/A — no earlier fix of this cause. A probe showed that the second caller of `_css_files`, `design_weight_findings` in `.hooks/ui_audit_rules.py`, also reported a missing weight for tokens held outside the app; it now returns the import finding instead. `ui_whole.py` and `ui_tokens.py` never read `@import` targets, so they have no such noise.
Single source: HE-YAGNI sentence has one owner, the registry entry; the README table holds a short summary of the rule that stays unchanged. The "outside the app" test reuses `_package_dir`, the owner that `_css_files` uses. The CSS import graph moved from `ui_rules.py` to `ui_css_imports.py` (the file passed 1000 lines), and `ui_audit_rules.py` imports it from there. The failing-check line has one copy, in the shared `AGENTS.md`; a search for its other phrases found no other copy outside the submodules.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: Autonomous — the user asked to look at the open Hard Eng issues on 2026-11-23, and the user's standing rule: merge each task PR into develop once its checks pass.

## Acceptance + steps

- [ ] An app whose CSS imports a token file outside the app gets one finding at the import line, naming file and target, and no undefined-token findings → `tests/test_ui_outside_tokens.py::test_a_token_file_outside_the_app_is_one_finding_at_its_import`; the target above the repository folder → `test_an_import_above_the_repository_is_outside_the_app`.
- [ ] The same tokens inside the app, and package imports such as `@import "tailwindcss"`, give no finding → `tests/test_ui_outside_tokens.py::test_the_same_tokens_inside_the_app_pass`; a folder in the app's own `node_modules` is not outside → `test_a_relative_import_into_node_modules_is_not_outside_the_app`.
- [ ] The finding appears once for a package, whichever file is a candidate, and a comment above the import does not shift its line → `tests/test_ui_outside_tokens.py::test_the_outside_import_finding_is_one_per_app_and_keeps_its_line`.
- [ ] The finding fires with no `@theme` in the app, with `tailwind.config.*`, and when the outside file holds no token → `tests/test_ui_outside_tokens.py::test_an_outside_import_is_a_finding_whatever_the_app_theme_holds`.
- [ ] A changed `DESIGN.md` with tokens outside the app gets the import finding, not a missing-weight finding → `tests/test_ui_outside_tokens.py::test_an_outside_import_replaces_the_design_weight_finding_it_causes`.
- [ ] HE-YAGNI holds the content sentence and `tests/test_skill_links.py` passes → `tests/test_skill_links.py` and `tests/test_requirements.py` results.
- [ ] The failing-check line says that Hard Eng is strict and broken only when no project change passes, and the shared rules stay within the released size → `tests/test_agent_hooks.py::test_shared_agent_rules_stay_within_the_released_size`.
- [ ] The affected check is not slower → N/A — timing, no test can prove it; compiled runs on each version are in Verification.

## Baseline + execution

Result: Passed
Evidence: 2026-11-23, `python3 .hooks/hard-eng.py check --plan-stage Draft --base origin/develop` on develop 4290fb2d plus this plan: exit 0. No package read the plan-only change, so it ran the secret scans only, and both passed.
Execution: One builder, this session; one independent review on the final head.

## Risks + recovery

A project that imports shared tokens from outside the app now gets a finding at the import. The fix is to move the tokens into the app. Revert the commit to undo. The new refusal reaches no new-project flow of `release_canary.py` (`install_new`): the flows install a Python scaffold, a greenfield project or a pinned Python library, none of the steps adds a CSS file, and the starters hold no `@import`.

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
