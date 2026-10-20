# Requirement registry

Status: Complete

## Outcome + scope

Each Hard Eng rule has one definition under a stable ID in `.agents/skills/he/references/requirements.md`; `check` fails when IDs repeat, dangle or lose their enforcer, test or skill link, or when definition text is copied into other Markdown. README, gates.md and AGENTS.md name IDs instead of restating seeded rules. Non-goals: moving every rule now, `DECISION.md` cleanup (second PR), proving a test really checks its rule, and catching paraphrased copies.

## Repository context

Owners: `validate_decisions` in `.hooks/plans.py` is the existing records check that `check` in `.hooks/hard-eng.py` runs on Stop, pre-push and CI; the new `validate_requirements` sits beside it. Enforcer messages live in `.hooks/hard-eng.py`, `gate_config.py`, `comments.py`, `untrusted_input.py` and `plans.py`. Setup ships every file under `.agents/skills`, so the registry reaches installed projects. The "Plan acceptance linked to tests" work resolves acceptance IDs through `requirement_tests`.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: Abid approved the design on 2026-10-20 ("Approve as recommended"): shipped registry, check shipped to installed projects, `DECISION.md` in a second PR. Push and PR need a separate approval.

## Acceptance + steps

- [x] Repeated ID, entry without proof, unknown or retired reference, check rule without enforcer or test, guidance rule without skill link and copied definition sentence each fail; a proven registry and a repository without a registry pass → `tests/test_requirements.py`.
- [x] Installed projects need no Hard Eng tests for `HE-` rules, while their own `REQ-` rules need tests → `tests/test_requirements.py`.
- [x] `requirement_tests` returns path, line and reported test name for Python docstrings and JavaScript test names → `tests/test_requirements.py`.
- [x] `check --quick` runs the registry check → `tests/test_comments.py::test_quick_check_runs_the_requirement_registry_guard`.
- [x] Seeded rules name their ID in the enforcer message and one existing test; the source repository passes its own registry check.
- [x] README, gates.md and AGENTS.md link seeded IDs instead of restating them; skill links resolve → `tests/test_skill_links.py`.

## Baseline + execution

Result: Passed
Evidence: Starting main suite with the locked environment: 1740 tests pass; the same 9 fail on main and on this branch because this machine lacks Dart, Xcode tools and process-limit support. Missing tools (gitleaks, osv-scanner, actionlint, zizmor, shellcheck, biome) and an unreachable Semgrep registry leave those gates to PR CI.
Execution: One builder; failing tests, the check, registry seeds, then doc links.

## Risks + recovery

Installed means `.hooks/hard-eng-source.json` exists or no root `setup.py` exists; a Python project with `setup.py` and a deleted marker would need Hard Eng's tests for `HE-` rules, and rerunning setup restores the marker. A project that already uses `HE-` or `REQ-` style tokens in tracked text gets unknown-ID failures once it adds a registry; without a registry the check does nothing. Recovery: rename the token or register it.

## ux_reference

N/A — gate and documentation change with no visual surface.

## Verification

Result: Passed
Evidence: Full suite 1740 passed, 9 failed, identical to the main baseline; line coverage 90%, `plans.py` 95%. Ruff format, lint, complexity and annotations, Pyrefly, Vulture and jscpd (0 clones) pass. The source repository passes its own registry, comment, switch-off and decision checks. Mutating the copy, retired, installed and sentence-length logic each fails `tests/test_requirements.py`. Remaining gates run in PR CI.
E2E: N/A — the check runs inside the existing `check` command, proven by the quick-check test; no new user journey.
