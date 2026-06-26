---
name: treehouse
description: Use for Treehouse CLI, tree house/treehouse, reusable worktrees, leases, status, return, or worktree isolation.
---

# Treehouse

Treehouse = local CLI for reusable git worktrees. It is not a planner; use
`grill-me` when scope is unclear.

Commands:
- Inspect: `treehouse status`
- Lease for Codex: `treehouse get --lease --lease-holder "<label>"`; stdout is
  the worktree path. Run from the target repo; it creates or reuses an isolated
  worktree. The agent must run `"$HOME/.agents/scripts/ensure-worktree-ready.sh"
  <path>` before continuing; do not ask the user to run it. Stop if it fails.
  Continue there and read `AGENTS.md`.
- If user says `treehouse <name>`, use `<name>` as the lease holder label; it is
  not a Treehouse branch argument.
- Stale check: `treehouse prune` is dry-run; deletion needs approved `--yes`
- Release: `treehouse return <path>` only after needed work/processes are clear

Approval needed: `return --force`, `destroy`, `prune --yes`,
`prune --prune-orphans`, `update`, install. If missing, `.agents/scripts/setup.sh`
owns install/update.
