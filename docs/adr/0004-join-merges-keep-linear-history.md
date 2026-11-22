# 0004 — Join merges keep linear history

Status: Accepted
Applies to: `.hooks/ship_record.py`, `.hooks/ship_actions.py`, `.hooks/join_merge.py`, `.hooks/merge_guard.py`, `AGENTS.override.md`

## Context

`develop` requires linear history on GitHub. The hotfix route must join `main` into `develop` with a merge commit, which that rule refuses. The maintainer's step of lifting the rule, merging and restoring it was done by hand for PRs 650, 654 and 668.

## Decision

- Keep GitHub's `required_linear_history` on `develop`.
- `ship --stage merge` does the join merge. It lifts only that field, merges the checked head, restores the saved protection in a `finally`, and fails if the protection read back differs from the saved copy.
- A typed `gh pr merge` for a join is refused by the merge guard.
- Rejected: turn the GitHub setting off for good and let Hard Eng's merge guard own the rule. The guard sees only agent commands on machines that run Hard Eng. The GitHub rule also blocks merges from the web page, from apps and from auto-merge; an app's auto-merge merged a release PR the wrong way on 2026-11-14.

## Consequences

A join takes one command. The rule is off for seconds and only for a checked join. The maintainer's standing approval of 2026-11-20 covers that lift. The step refuses a protection it cannot copy (review or push restrictions, signatures, unknown fields) instead of writing a partial body.

## Evidence

Maintainer chat, 2026-11-20: "ok" to keeping the rule and building the step into ship; "yes" to the standing lift for joins. Pending: the first real join after release 658 proves the protection round trip.
