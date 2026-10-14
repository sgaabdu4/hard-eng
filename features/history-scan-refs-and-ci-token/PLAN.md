# History scan refs and docs-only CI token

Status: Draft

## Outcome + scope

1. Without a usable base, the `secrets-history` gate scans branches, remote branches, tags and `HEAD`, not every local ref. Private tool refs (for example checkpoint refs) no longer fail the check with commits that can never be pushed (issue sgaabdu4/hard-eng#297).
2. The docs-only CI step gives mise a token it reads, so tool installs no longer hit GitHub's unauthenticated rate limit. Existing workflows get the line at update.
Non-goals: no gate configuration change; no change to the based `base..HEAD` scan; no other workflow steps.

## Repository context

Owners: [gitleaks_scan.py](../../.hooks/gitleaks_scan.py) `new_commits_command` (already rewrites `--log-opts=--all` for a known base); [hard-eng.yml](../../.github/workflows/hard-eng.yml) docs-only step; [ci_setup.py](../../.hooks/ci_setup.py) `configure_ci` migrations (`migrate_impact_token` is the model).
Evidence: gitleaks 8.30.1 with `--log-opts=--all` reported a leak in a commit reachable only from `refs/checkpoints/x`; `--log-opts=--branches --remotes --tags HEAD` skipped it and still caught a leak in a detached `HEAD` commit; without `HEAD` the detached commit was missed. A consumer's docs-only CI step failed: mise called the GitHub API unauthenticated (`0/60 (core)`, HTTP 403) because the step sets only `GH_TOKEN`; the required-checks step sets `GITHUB_TOKEN` too and installs the same tools.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: The user asked to fix every open Hard Eng issue and the noted problems in one PR, with a Codex adversarial review loop (gpt-6-astra) before the PR. Commit, push and merge follow this repository's merge-when-green practice.
Decisions: Rewrite at run time in `new_commits_command`, like the based scan, so every install is fixed at update with no gate configuration migration. A project's own `--log-opts` stays unchanged. The workflow migration adds the token only to the docs-only step that lacks it; the impact step runs only Python and `gh`, so `GH_TOKEN` is right there.

## Acceptance + steps

- [ ] No base, an all-zero base or an unresolvable base scans `--branches --remotes --tags HEAD`; git lists a detached `HEAD` commit and omits a commit reachable only from a private ref → `test_history_scan_covers_only_commits_a_known_base_lacks`, `test_full_history_scan_skips_private_refs_and_keeps_detached_head`, red before. The first test's old "unknown base keeps the command unchanged" assertion is replaced: it protected the full scan, which the new list still gives for every pushable commit.
- [ ] Every template step that runs mise sets `GITHUB_TOKEN` → `test_every_template_step_that_runs_mise_has_a_token_mise_reads`, red before.
- [ ] An installed workflow whose docs-only step lacks `GITHUB_TOKEN` gains it once at update; a current one is unchanged → `test_docs_only_step_gains_the_token_mise_reads`, red before.
- [ ] Full `python3 .hooks/hard-eng.py check` passes.

## Baseline + execution

Result: Pending
Evidence: Pending
Execution: Red tests first, then the fixes at the owners above, then the Codex adversarial review loop, then PR.

## Risks + recovery

A project that relies on scanning stash or other private refs loses that coverage; those commits cannot reach the remote by a normal push. Recovery is reverting this branch.

## ux_reference

N/A — gate command and CI workflow only; no product appearance.

## Verification

Result: Pending
Evidence: Pending
E2E: Pending

Delivery target: Merge
Delivery: Pending
