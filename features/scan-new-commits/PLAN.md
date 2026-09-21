# Scan only new commits for secrets when the base is known

Status: Complete

## Outcome + scope

When `check` receives a `--base` that Git resolves to a commit, the `secrets-history` gate's `--log-opts=--all` becomes `--log-opts=<base sha>..HEAD`, so gitleaks scans only the commits the base lacks, and the check prints which commit the scan starts after. Without a base, with an all-zero or unresolvable base, or with a project's own `--log-opts`, the command is unchanged and the full history is scanned as before. It applies to every project at its next update, with no gate configuration change. No new file other than this plan.

## Repository context

Owners: `.hooks/gitleaks_scan.py` (gitleaks commands) and `.hooks/gate_config.py` `load_groups`, which already receives the base. A trial on a real monorepo measured the full-history scan at about 90 seconds (4,195 commits, 1.26 GB) on every run, which made a docs-only check take 111 seconds while four other projects took 5 to 9. CI, pre-push and the updater's candidate check all pass a base, so each commit is scanned when it enters through a pull request or a push to the base branch.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: The user asked to build the scan-only-new-commits change after seeing the trial measurement and the trade-off. The resolved commit id, not the caller's text, goes into the command, so a base cannot inject gitleaks or Git options. Accepted trade-off: a commit already in the base's history is not rescanned on later based checks, so a newly added gitleaks rule reaches old history only through a check without `--base`. Merge awaits the user's go-ahead.

## Acceptance + steps

- [x] A resolvable base scopes the scan to `base..HEAD` and reports it; no base, an all-zero base, an unresolvable base, an option-shaped base and a project's own `--log-opts` leave the command unchanged → `test_history_scan_covers_only_commits_a_known_base_lacks`.
- [x] Full check passes.

## Baseline + execution

Result: Passed
Evidence: main at 9a9cc91, whose push CI passed for PR 136.
Execution: Single session on `feature/scan-new-commits`.

## Risks + recovery

A secret committed and removed on a branch before its first based check is still caught, because the whole branch range is scanned. A secret in history older than the base is no longer reported by a based check. Recovery is reverting this branch.

## ux_reference

N/A — one gate's command arguments and one line of check output; no product appearance.

## Verification

Result: Passed
E2E: Passed — with the real gitleaks in a scratch repository holding a token committed and removed before the base: the based check scanned 1 commit and passed; the check without a base found the old token; after a second token was committed and removed after the base, the based check failed on it; an all-zero base scanned the full history and found both.
Evidence: The new test passes. The full check result is recorded in the delivery line below.

Delivery target: PR
Delivery: Pending — `hard-eng.py check --base origin/main` exit 0: all 17 checks, 794 tests and 4 performance checks passed. PR CI and merge remain unverified.
