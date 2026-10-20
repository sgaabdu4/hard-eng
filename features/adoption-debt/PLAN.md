# Adoption debt

Status: Complete

## Outcome + scope

Hard Eng installed on existing code can pass its check on the first change. Before this, old code failed many gates (13 on a real open-source Python library), so the Stop check never passed and the agent had to repair the whole codebase first. Now `python3 .hooks/hard-eng.py adopt` records the findings that the existing code has into `hard-eng.debt.json`, once, at install. Later, a gate with debt fails on any new finding, and also when a recorded finding is fixed but still listed. The file can only shrink. Non-goals: debt for tests, lockfiles and secrets (these must pass before adoption), and debt for report types that have no fingerprint reader.

## Repository context

Owners: the new `.hooks/debt.py` holds fingerprints, judgement, recording and the shrink rule. `.hooks/hard-eng.py` calls it from `run_gate`, `check` and the new `adopt` command. `.hooks/release_canary.py` runs `adopt` for the brownfield kind. Rules: `AGENTS.md` (Verification), `.agents/skills/he/references/gates.md` and `requirements.md` (HE-DEBT-SHRINK-ONLY).
Same cause: one cause, no record of what the code held before install, made every old finding look new. Searched the other gate paths for the same case: `exceptions` covers a whole check after review, not old lines, and the Swift and Dart gates use the same `run_gate` path, so the one fix covers them.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: Abid's standing approval (2026-10-20) to decide and merge into `develop`; the coordinator asked for a shrink-only debt list.
Decided: debt is recorded only by the change that installs Hard Eng (the base has no `.hooks/hard-eng-source.json`). Line numbers, counts and the checkout path are made neutral, so a moved line stays the same finding. A later `adopt` only drops lines. Failing tests, lockfiles and secrets refuse adoption. The rule stays "repair, do not suppress" for every new finding.

## Acceptance + steps

- [x] Old findings pass, new ones fail, fixed ones must be dropped → `tests/test_debt.py::test_old_findings_pass_new_ones_fail_and_fixed_ones_must_be_dropped`.
- [x] A later adoption only drops lines → `tests/test_debt.py::test_a_later_adoption_only_drops_lines`.
- [x] Tests, lockfiles and secrets never become debt → `tests/test_debt.py::test_tests_lockfiles_and_secrets_never_become_debt`.
- [x] Report findings count beside the output → `tests/test_debt.py::test_report_findings_count_beside_the_output`.
- [x] The debt file appears only with the install and never grows → `tests/test_debt.py::test_debt_appears_only_with_the_install_and_never_grows`.

## Baseline + execution

Result: Passed
Evidence: `develop` with Hard Eng installed on a real open-source Python library: 13 gates failed before any change, so the check could not pass. Each new test failed before its code.
Execution: One builder; code, then docs and canary, then output fixes.

## Risks + recovery

A tool whose output changes between runs (for example a timing line) can show as a new finding; the runner chatter filter removes the known ones. Delete `hard-eng.debt.json` in the install change, or revert the commits, to undo.

## ux_reference

N/A — command-line checks with no visual surface.

## Verification

Result: Passed
Evidence: Real brownfield run in the cloud: `adopt` recorded 13 gates and the check passed. A new unannotated function failed annotations and types; annotating it passed. A fixed old dead-code finding failed until `adopt` dropped it. Branch full suite: only the 6 environment failures that `develop` has (no Dart or Swift in this container). Independent review not done: Codex is not installed in cloud sessions.
E2E: N/A — the brownfield run above uses the real installer and the real tools.

Delivery target: Merge
Delivery: Pending — PR into `develop` with the `hard-eng` CI check green.
