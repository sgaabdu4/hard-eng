# Failing checks are rules to follow

Status: Complete

## Outcome + scope

Agents in installed projects met a strict Hard Eng finding, called it a Hard Eng fault and asked the user whether to weaken the rule. The shared rules invited that: they told agents to report a "fault" with no line between a broken tool and a strict check. Now the shared rules say a failing check means fix the project and never offer to weaken the check; only broken Hard Eng hooks, skills or setup get reported. A failing update is fixed on the update branch itself, as the update tool's steps say. An audit of recent commits found five skips that each had a valid reason but went too wide; each is narrowed back to its real case. Non-goals: the cache rule, and when an update shows new findings.

## Repository context

Owners: `AGENTS.md` (shared rules, size-capped), `.agents/skills/he/semgrep/performance.yaml` (whole-row SQL rules), `.hooks/hot_paths.py` (security scan options), `.agents/skills/he/templates/*.json` + `.hooks/project_setup.py` (security gate flags), `.hooks/gate_config.py` (freshness skip), `release_canary.py` + `.github/workflows/canary.yml` (release check).
Same cause: each skip fixed a real false alarm or timeout but was written wider than that case, and no test proved the wider case still failed.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: Abid on 2026-11-07: "yes pls" to adding the rule to Hard Eng's shared instructions, shipping it and installing it.
Authority: Abid on 2026-11-07: "yes pls" to fixing the five weakened checks and the unclear update wording in the same release.
Decision: the change rewrites the report-a-fault and update lines in place, so the file stays within its size cap.
Decision: each skip keeps its reason; only its reach narrows.

## Acceptance + steps

- [x] The shared rules stay within the installed size cap → `tests/test_agent_hooks.py::test_shared_agent_rules_stay_within_the_released_size`.
- [x] The shared rules say a failing check means fix the project and never offer to weaken it → N/A — rule wording; a text match would only mirror the line.
- [x] `SELECT *` from a user-defined table function is flagged again; built-in set functions stay allowed → `tests/test_hot_paths.py::test_each_rule_finds_exactly_the_annotated_lines`.
- [x] Generated and vendored files skip only Hard Eng's rules; registry security packs still scan them → `tests/test_hot_paths.py::test_generated_files_skip_only_hard_eng_rules`.
- [x] Security scans skip only installed Hard Eng files, anchored at the root; a project's own skills are scanned → `tests/test_hot_paths.py::test_security_scans_skip_only_the_installed_hard_eng_files`.
- [x] Templates and existing gate files carry no folder-name excludes → `tests/test_basic_mode.py::test_whole_project_security_scans_carry_no_unanchored_excludes`, `tests/test_setup.py::test_update_drops_the_folder_name_excludes_from_security_scans`.
- [x] An update that also changes a dependency file keeps the freshness check → `tests/test_updates.py::test_update_with_dependency_change_keeps_freshness`.
- [x] A release PR's canary fails unless develop's push run passed, and waits while it runs → `tests/test_release_canary.py::test_a_release_pr_waits_for_develops_push_run_to_pass`, `tests/test_release_canary.py::test_a_release_pr_waits_while_develops_push_run_is_running`.

## Baseline + execution

Result: Passed
Evidence: develop at the branch point (0c6860d7) passed required CI; `python3 .hooks/hard-eng.py check --plan-stage Draft --base origin/develop` passed on 2026-11-07.
Execution: one session plus four parallel builders in separate worktrees, one per skip; failing test first for each; commits combined on this branch; then the full check, PR into develop, release, install on one project.

## Risks + recovery

An agent could read "broken" too narrowly and never report a real Hard Eng crash. Installed projects may go red where the narrowed skips now find real problems; that is intended. Recovery: revert this pull request.

## ux_reference

N/A — no app screens change.

## Verification

Result: Passed
Evidence: `python3 .hooks/hard-eng.py check --plan-stage Complete --base origin/develop` result recorded in the pull request; each new test failed before its fix; agent cases `failed-baseline` and `repeat-failure` passed on Haiku with the new shared rules.
E2E: N/A — no user journey; the change is agent instruction text.
Delivery target: PR
Delivery: Pending — PR into develop.
