# Judge each gate against every configured group before it runs

Status: Complete

## Outcome + scope

A run with a base judges the settings of a gate against every configured group, not only the changed ones, so a parent ignore of a child group root is accepted exactly as in the full settings judge. Non-goals: the Fallow rules, the `health.ignore` rule.

## Sources + coverage

Sources: N/A — the request is a fault traced by an investigator on `origin/develop` df030688; no user source.

## Repository context

Owners: `.hooks/gate_runner.py` (`prepared_command`, `prepare_command`), `.hooks/resolved_settings.py::judge_before_run`, `.hooks/dependency_graph.py::child_groups`.
Same cause: the earlier fix 00cf25ef passed every configured group to the types gate only (`nested_package_patterns`). Searched every caller of `validate_resolved`, `judge_before_run`, `child_groups` and `biome_children`. One more call had the harmful narrowing: `judge_before_run` in `prepared_command`; it now takes the helper `every_group`, which the types gate call also uses. `biome_children` in `prepare_command` also sees only the changed groups, but there the narrowing makes the parent format gate check the child files too, which is a wider check, not a refusal; an independent review showed that passing every group would drop child files from a run where the child gate does not run, so it stays. `judge_settings` already passes `load_groups(ROOT)`; `python_setup.py` reads `configured_packages(root)`; `dart_boundaries.py` is the types gate fixed before.
Single source: `every_group` in `.hooks/gate_runner.py` is the one place that picks the configured groups; the types gate call uses it too.
Consistency note: `fallow_table.py` (the judge of the printed config) lists `health.ignore` as "patterns", like `ignorePatterns`, so a pattern that names a child group root is allowed there. `fallow_settings.py` (the whole-project check of the settings files, called from `whole_project.py`) refuses any `health.ignore`. Both run in the full check and the file check is stricter, so the child-root allowance for `health.ignore` never takes effect. The two are consistent in outcome but overlap; no reason for the allowance was found in the code. No code change: removing the table entry would change the printed-config judge, which the maintainer did not ask for.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: Autonomous — maintainer request to fix this fault.

## Acceptance + steps

- [x] A run of the root group alone accepts a root `ignorePatterns` entry that names the child group root, and still refuses it when the child has no Fallow gate → `tests/test_unrecognised_forms.py::test_the_run_judges_the_root_gate_against_every_configured_group`: fails on develop with "does not check packages/child/src/b.ts", passes after.

## Baseline + execution

Result: Passed
Evidence: 2026-11-19, develop df030688: the first test fails with the refusal above; the full settings judge accepts the same settings.
Execution: One builder, this session.

## Risks + recovery

N/A — one helper and two call sites; a revert restores the old behavior.

## ux_reference

N/A — hooks only; no visible UI.

## Verification

Result: Passed
Evidence: the new test failed on develop df030688 with the refusal above and passes with the change; 57 tests of `tests/test_unrecognised_forms.py`, `tests/test_change_filtered_judges.py` and `tests/test_gate_limits.py` pass. Ruff format, lint, complexity and annotations, Pyrefly, Vulture and the duplicates scan report no finding. The Complete check ran once with `--base origin/develop` on this head.
Review: the first independent review at 3c18ce93 found one defect, the Biome change; it was removed (see Repository context). The reviews at 000bbe98 and 6ee30520 were clean.
E2E: N/A — no user journey changes.
Real service: N/A — the change calls no outside service.
Retro: (1) Escaped bug: the earlier fix covered the types gate only, and no test covered the Fallow judge with a base → the tests gate should have caught it; the new test now covers it. The same-cause search found no other narrowing that refuses a valid setting.
Delivery target: Merge
Delivery: Pending — `hard-eng` and `canary` pass on the PR to develop.
