# Requirement registry

Status: Complete

## Outcome + scope

Each Hard Eng rule has one definition under a stable ID in `.agents/skills/he/references/requirements.md`; `check` fails when IDs repeat, dangle or lose their enforcer, test or skill link, or when definition text is copied into other Markdown. README, gates.md and AGENTS.md name IDs instead of restating seeded rules. Non-goals: moving every rule now, `DECISION.md` cleanup (second PR), proving a test really checks its rule, and catching paraphrased copies.

## Repository context

Owners: `validate_decisions` in `.hooks/plans.py` is the existing records check that `check` in `.hooks/hard-eng.py` runs on Stop, pre-push and CI; the new `validate_requirements` sits beside it. Enforcer messages live in `.hooks/hard-eng.py`, `gate_config.py`, `comments.py`, `untrusted_input.py` and `plans.py`. Setup ships every file under `.agents/skills`, so the registry reaches installed projects. The "Plan acceptance linked to tests" work resolves acceptance IDs through `requirement_tests`.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: Abid approved the design on 2026-10-20 ("Approve as recommended"): shipped registry, check shipped to installed projects, `DECISION.md` in a second PR. He then authorized push and PR, and asked that this work be rebuilt on `develop` through the Hard Eng workflow.

## Acceptance + steps

- [x] A proven registry passes → `tests/test_requirements.py::test_proven_registry_passes`.
- [x] A repository without a registry is not checked → `tests/test_requirements.py::test_project_without_registry_is_not_checked`.
- [x] A repeated ID fails → `tests/test_requirements.py::test_repeated_id_fails`.
- [x] An entry without a definition and proof line fails → `tests/test_requirements.py::test_entry_without_proof_line_fails`.
- [x] A reference to an unknown ID fails → `tests/test_requirements.py::test_reference_to_unknown_id_fails`.
- [x] A reference to a retired ID fails → `tests/test_requirements.py::test_reference_to_retired_id_fails`.
- [x] A check rule without a test fails → `tests/test_requirements.py::test_check_rule_without_test_fails`.
- [x] A check rule without an enforcing source fails → `tests/test_requirements.py::test_check_rule_without_enforcer_fails`.
- [x] A guidance rule without a skill link fails → `tests/test_requirements.py::test_guidance_rule_without_skill_link_fails`.
- [x] A copied definition sentence fails → `tests/test_requirements.py::test_copied_rule_sentence_fails`.
- [x] Installed projects need no Hard Eng tests for `HE-` rules → `tests/test_requirements.py::test_installed_project_does_not_need_hard_eng_tests`.
- [x] A project's own `REQ-` rule needs its own test → `tests/test_requirements.py::test_project_rule_needs_its_own_test`.
- [x] `requirement_tests` returns path, line and reported test name → `tests/test_requirements.py::test_requirement_tests_name_each_covering_test`.
- [x] `check --quick` runs the registry check → `tests/test_comments.py::test_quick_check_runs_the_requirement_registry_guard`.
- [x] Seeded rules name their ID in the enforcer message and one existing test → N/A — the repository's own `check` runs `validate_requirements` on itself in CI and fails if a seed loses either link.
- [x] README, gates.md and AGENTS.md link seeded IDs; the links resolve → `tests/test_skill_links.py::test_distributed_skill_links_resolve`.

## Baseline + execution

Result: Passed
Evidence: `origin/develop` full suite with the locked environment: 1733 passed, 8 failed. The 8 need Dart, Xcode or signal timing that this cloud machine lacks. gitleaks, osv-scanner, shellcheck, actionlint, zizmor and biome cannot install in cloud, and the Semgrep registry is unreachable; CI ran these.
Execution: One builder; failing tests, the check, registry seeds, then doc links.

## Risks + recovery

Installed means `.hooks/hard-eng-source.json` exists or no root `setup.py` exists; a Python project with `setup.py` and a deleted marker would need Hard Eng's tests for `HE-` rules, and rerunning setup restores the marker. A project that already uses `HE-` or `REQ-` style tokens in tracked text gets unknown-ID failures once it adds a registry; without a registry the check does nothing. Recovery: rename the token or register it.

## ux_reference

N/A — gate and documentation change with no visual surface.

## Verification

Result: Passed
Evidence: Branch full suite: 1748 passed, the same 8 failed as on `develop`; line coverage 89%, `plans.py` 95%. Ruff format, lint, complexity and annotations, Pyrefly, Vulture and jscpd (0 clones) pass. The repository passes its own registry, comment, switch-off, decision and attribution checks. Deliberately breaking the copy, retired, installed and sentence-length logic each fails `tests/test_requirements.py`. `hard-eng.py` stays at 999 lines: one `validate_records` call runs the decision, attribution and registry checks.
E2E: N/A — the check runs inside the existing `check` command, proven by the quick-check test; no new user journey.
