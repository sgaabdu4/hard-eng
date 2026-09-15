# Preserve ignored local files during scaffold updates

Status: Complete

## Outcome + scope

Reject scaffold updates that overlap existing ignored local files. Continue adding genuinely absent managed paths even when ignore rules match them. Change the existing updater and transaction test only.

## Repository context

The updater force-stages its explicit managed paths, but its Git status preflight omits ignored untracked files. A newly managed path can therefore overwrite local content without reporting a conflict. Git's native --ignored option supplies the missing check before candidate verification and again before applying the update.

## Decisions + authorization

Blockers: None
The user authorized canonical updater repairs and delivery. Preserve local instructions, unrelated staged work and working edits. No new dependency, wrapper or recovery state is needed. This plan is the existing workflow's required task record.

## Baseline + execution

Result: Passed
Evidence: Source main 77776e8 passed hosted hard-eng CI. A downstream real-Git review exposed the ignored-file collision outside the existing coverage.
One owner repairs the updater. Independent consumer work continues without adopting the affected update.

## Acceptance + steps

- [x] An ignored existing configuration file blocks the update without changing its contents, the current commit or unrelated staged and working edits.
- [x] A genuinely absent managed file is still installed despite a matching ignore rule.
- [x] Focused transaction regressions and the full source Ready gate pass.

## Risks + recovery

The guard must include ignored files only for the explicit update paths. Preserve both preflight checks to catch changes during verification. Revert the scoped change if existing safe update behavior fails.

## ux_reference

N/A — this transaction repair has no product UI.

## Verification

Result: Passed
Evidence: The real updater rejects an ignored local MCP configuration file before verification or mutation; its contents, HEAD, unrelated index entry and working edit are unchanged. The existing absent-ignored-path transaction still succeeds. The full source Ready gate passed. Final Complete/pre-push and hosted checks remain required for delivery.
E2E: Passed — the actual updater transaction ran against temporary Git repositories with both an ignored local collision and an absent ignored managed path, preserving unrelated staged work.

Delivery target: Merge
Delivery: Pending
