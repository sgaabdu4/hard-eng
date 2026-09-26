# Run setup from the verified revision it installs

Status: Complete

## Outcome + scope

`setup.sh` from main runs the install step of the CI-verified revision it checks out, so the entry command and installer always agree. Non-goals: changing the updater, the verified-revision lookup or `setup.py`.

## Repository context

Owners: `setup.sh` resolved the verified revision with main's code, then called that revision's `update(Path.cwd(), repair=True)` with main's arguments. After #190 added `repair`, every merge left a window until CI passed where the newest verified revision still had `update(root)`, so rerunning setup in an installed repository failed with a TypeError (seen re-sweeping a consumer repository after #190–#192).

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: The user asked for this fix on branch `fix/setup-installer-interface`, one PR watched to green CI, and no merge.

Design: `setup.sh` without arguments is a thin bootstrap. It clones main, resolves the verified revision with main's own lookup, checks it out, then runs that revision's `setup.sh` with the checkout path. With that argument, `setup.sh` runs only the install step against the given source. Each revision's install call therefore travels with its own installer. Option-by-option feature detection was rejected: it covers only `repair`, and every later option or `setup.py` argument change would reopen the same race.

## Acceptance + steps

- [x] Rerunning main's setup in an installed repository succeeds when the verified revision's installer has no `repair` option → `test_setup_runs_the_verified_revisions_own_install_step` fails with the current `setup.sh` and passes after the change.
- [x] `setup.sh` stays valid POSIX shell → the `shellcheck` gate passes.

## Baseline + execution

Result: Passed
Evidence: `python3 .hooks/hard-eng.py check --plan-stage Draft` on main f0c7bb3 passed all 18 checks with 990 tests. With main's `setup.sh`, the new regression failed with "TypeError: update() got an unexpected keyword argument 'repair'".
Execution: One builder: regression test first, then the `setup.sh` split.

## Risks + recovery

Verified revisions published before this change ignore the checkout argument and bootstrap themselves again, calling their own installer with their own arguments; that only costs a second clone until this change is verified. Recovery: revert the `setup.sh` change.

## ux_reference

N/A — installer entry command with no product UI.

## Verification

Result: Passed
Evidence: `python3 .hooks/hard-eng.py check --base origin/main --plan-stage Complete` passed; the full suite passed with 991 tests.
E2E: N/A — the regression runs the real `setup.sh` end to end against local Git sources and a faked verified-revision lookup.

Delivery target: PR
Delivery: Pending — PR CI green; merge is not authorized.
