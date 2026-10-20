# Cut DECISION.md to current status and open requirements

Status: Complete

## Outcome + scope

`DECISION.md` shrinks from about 97 KB to about 7 KB: scaffold purpose, current status, remaining acceptance gaps and the open requirements. Enforced rules point to the requirement registry. Dated verification history is removed; Git history and merged PRs keep it. Non-goals: adding new registry entries, changing code, and deleting feature plans that lose their only link (the plan-cleanup work owns that).

## Repository context

Owners: `DECISION.md`; the registry at `.agents/skills/he/references/requirements.md`. README, PRODUCT.md and DESIGN.md link only `DECISION.md#current-status`, which stays. `release_canary.py` lists `DECISION.md` as a source-only file, and `tests/test_setup.py` proves setup does not install it.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: Abid approved the registry design with `DECISION.md` cleanup as a second PR (2026-10-20), and told threads to make remaining decisions themselves.

## Acceptance + steps

- [x] Links into `DECISION.md` still resolve, including `#current-status` → N/A — README, PRODUCT.md and DESIGN.md keep the same anchor; `grep -rn "DECISION.md#"` finds only `#current-status`.
- [x] The repository passes its own registry check, so no registry definition is copied into `DECISION.md` → N/A — `check` runs `validate_records` on the repository in CI.
- [x] Setup still does not install `DECISION.md` → `tests/test_setup.py::test_install_preserves_project_and_repeats`.
- [x] The file holds no personal data and no names or paths of private projects → N/A — reviewed by reading the whole new file; it was written fresh, not copied from the dated history.

## Baseline + execution

Result: Passed
Evidence: The registry change, rebased on `develop` e62b742, passed 1771 tests with 8 environment failures (Dart, Xcode and signal timing are missing in cloud); its merge into `develop` 2c24999 passed the registry check and 254 focused tests. This change touches only Markdown. gitleaks, osv-scanner, shellcheck and actionlint cannot install in cloud; CI runs them.
Execution: One builder; rewrite the file, then verify links and records.

## Risks + recovery

Readers lose the dated narrative in the working tree. Recovery: `git show 2c24999:DECISION.md` restores the full history.

## ux_reference

N/A — documentation change with no visual surface.

## Verification

Result: Passed
Evidence: `plans.validate_records` and Complete plan validation pass on the branch; `tests/test_setup.py::test_install_preserves_project_and_repeats`, `tests/test_skill_links.py` and `tests/test_plans.py` pass (98 tests). Only `DECISION.md#current-status` is linked, and it exists. The new file is 6.6 KB.
E2E: N/A — documentation change with no user journey.

Delivery target: PR
Delivery: Pending — PR into `develop` with the `hard-eng` CI check green.
