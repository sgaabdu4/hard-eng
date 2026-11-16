# Whole-project pass: no switch-off inside a literal, and parent Dart excludes judged where they apply

Status: Ready

## Outcome + scope

HE-NO-SWITCH-OFF counts a switch-off only where a tool reads it: text inside a string, template or regex literal in Dart, JavaScript, TypeScript, Swift or Python is not a switch-off, in added lines and in the whole-project pass alike. A comment after a literal on the same line still fails, and a Gitleaks allow mark still fails inside a string, because Gitleaks reads the raw line. A Dart exclude written in a parent folder's own `analysis_options.yaml` and included by a child package is judged from the child folder, where the analyzer applies it: a pattern that matches nothing there passes, and one that hides a child file fails and names the parent file that holds it. Non-goals: Markdown prose that names a marker and unchanged Flutter starter comments; both have a project fix (reword the sentence; delete the two template comment lines).

## Sources + coverage

Sources: N/A — found by the sealed scan of the installed projects for the strict rollout (`features/strict-rollout/PLAN.md`): lint test samples in raw strings, a migration script regex, and a package example whose options include the root file were refused.

## Repository context

Owners: `pattern_switch_offs` and `security_hits` in `.hooks/comments.py` match each raw line; the literal-aware scanner that `comment_spans` uses lived in the same file, which is at its 1000-line limit, so the scanner moves to its owner `.hooks/source_scan.py`. `validate_dart_exclusions` lived in `.hooks/project_setup.py` while only Dart analysis calls it; it moves to `.hooks/dart_boundaries.py`, its only caller in the hooks.
Same cause: excuse markers already read comments only (`comment_map`), so they had no such fault. The changed-line check (`added_switch_offs`) and the whole-project pass share `pattern_switch_offs` and `security_hits`, so both get the fix. `validate_dart_typing` and `apply_dart_typing` pass the folder's own file and keep the strict rule.
Single source: one scanner (`scanned_spans`) gives comments and literals; one scan of a file serves every check in a run.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: Autonomous. AGENTS.md line 10 covers Hard Eng design calls; the user approved PRs for the strict rollout (2026-11-15 06:12), which these faults block.

## Acceptance + steps

- [ ] Switch-off text inside a Dart raw string, a Dart string, a template, a template expression's string, a JavaScript regex and Python strings passes in added and old lines → `tests/test_strict_refusals.py::test_switch_off_text_inside_a_literal_passes`.
- [ ] A switch-off comment after a literal still fails, and a Gitleaks allow mark inside a string still fails → `tests/test_strict_refusals.py::test_switch_off_after_a_literal_or_a_gitleaks_mark_in_one_fails`.
- [ ] Every earlier switch-off form still fails → `tests/test_strict_refusals.py::test_old_switch_offs_anywhere_in_the_project_fail`.
- [ ] A parent folder's exclude that matches nothing in the child passes; one that hides a child file fails and names the parent file; the child's own file keeps the strict rule → `tests/test_dart_exclusions.py::test_an_included_parent_exclude_is_judged_where_it_applies`.

## Baseline + execution

Result: Passed
Evidence: 2026-11-16, develop 80756642 passed CI. On it, the 6 literal cases and the parent exclude case fail; the 4 near-miss cases pass.
Execution: One builder, this session.

## Risks + recovery

A hit inside a literal that the scanner reads wrongly (an unclosed quote) would hide a real switch-off on later lines; the scanner is the one the comment rule already trusts. The literal check runs only on a line that already matches, and one cached scan per file serves the comment checks too. Recovery: revert the commits.

## ux_reference

N/A — check messages only; no visible UI.

## Verification

Result: Pending
Evidence: Pending
Review: Pending
E2E: N/A — no user journey changes.
Real service: N/A — the change calls no outside service.
Retro: Pending
Delivery target: Merge
Delivery: Pending — `hard-eng` and `canary` pass on the PR to develop.
