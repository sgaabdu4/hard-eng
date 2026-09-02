# Worktree Readiness

## Commands

```sh
python3 <agents-root>/skills/deterministic-checks/scripts/worktree.py --repo <repo-root> --intent read
python3 <agents-root>/skills/deterministic-checks/scripts/worktree.py --repo <repo-root> --intent repair
python3 <agents-root>/skills/deterministic-checks/scripts/worktree.py --repo <repo-root> --intent write
python3 <agents-root>/skills/deterministic-checks/scripts/worktree.py --repo <repo-root> --intent publish
<agents-root>/scripts/git-hooks/install.sh check
```

| Intent | PASS |
|---|---|
| `read` | readable Git checkout + identity evidence |
| `repair` | dirt limited to ignore/include + setup/test + configured post-checkout owner; current structural failures emitted as repair issues |
| `write` | linked worktree OR primary; dirty primary requires explicit `--checkout-choice current`; every literal `.worktreeinclude` path present + private; isolated setup receipt current |
| `publish` | prior `write` PASS + named branch + valid `.worktreeinclude` inputs + current isolated setup receipt + branch not behind its upstream |

Tracked `AGENTS.override.md` `checkout_policy = primary-only` → primary always selected + dirty primary allowed + linked worktree rejected.

## Provision

1. Before worktree creation, inspect ignored local state + project run/test/build owners.
2. Required local input → tracked root `.worktreeinclude` exact path; secrets = minimum explicit paths.
3. Required generated state without a ready setup owner → narrow project-owned glob + smoke proof; otherwise rebuild through setup.
4. Cache/log/database/build/editor/temp state → exclude unless evidence proves non-rebuildable input.
5. Linked worktree/current branch → continue; Feature Loop entry on a clean selectable primary → `he` setup creates `feature/<slug>` at `../<repo>.worktrees/<slug>` from the resolved `origin/main|develop` base; Direct/Diagnose work on a clean primary → stays in place; ad-hoc branch/worktree creation outside that owner = forbidden.
6. Dirty primary + unrelated user dirt → ask once: continue current OR create worktree; selected current → rerun `write --checkout-choice current`.
7. Ignored env inputs (`.env`, `.env.*`, `*.env`) absent from `.worktreeinclude` → `he` setup asks once → appends the chosen exact paths + stages the list + copies them private through the copier; declined = `none`.
8. Active Feature Brief + requested checkout change = continue current checkout OR stop for an explicit exact transfer decision; automatic move/recreation forbidden.
9. Feature Loop entry = `he` feature setup (base + worktree + inputs decisions → `write` PASS + gate manifest + memory index → receipt) → inspect/init/brief/Ready-to-build approval; full gates = build entry after approval.
10. Isolated build-entry `write` + tracked setup owner = validate Git-private receipt → stale/missing runs exact setup through bounded owner → unchanged tracked state + current receipt required.
11. Build-entry `write` failure = `repair` only the blocked setup/readiness owner → focused setup contract + rerun `write`; full gate/independent repair delivery waits until accepted behavior proof unless continuation is unsafe, corrupting, or unverifiable.
12. Missing input/setup/smoke proof after repair → recreate/retry before product mutation.

## Rules

- `.worktreeinclude` must exist in selected starting state before Codex creates the managed worktree.
- Feature Brief stays with its selected checkout; checkout change never silently recreates or copies lifecycle state.
- Branch = current/named branch; prefix requirement = none.
- Main branch = valid local choice; delivery still obeys repository policy + publish approval.
- `write` = pre-mutation gate; `publish` accepts task-created dirt after prior `write` PASS.
- `publish` fetches the upstream's remote itself, because a remote-tracking ref only answers what the last fetch asked; behind upstream → rebase onto it and rerun. No remote or no resolvable upstream = nothing to be behind.
- Planning-only PLAN init/edit = `read` PASS exception; production/tooling mutation still requires `write` PASS.
- `repair` = worktree-infrastructure mutation only; product/code dirt forbidden + completion requires normal `write` PASS.
- Every worktree = tracked `.worktreeinclude` ignored-input allowlist + one tracked setup owner; Git-hook + Codex-app creation paths converge at `write`.
- Copier = main worktree source + ignored/untracked regular file + no overwrite + mode `0600`; symlink/traversal = reject/skip.
- Repository `core.hooksPath` override + worktree input/setup → tracked executable `post-checkout` = exact global delegation:

```sh
#!/bin/sh
set -eu

global_hooks=$(git config --global --get core.hooksPath)
dispatcher="$global_hooks/post-checkout"
exec "$dispatcher" "$@"
```

- Global dispatcher = Git linked-new-worktree event only → copy allowlisted input → run tracked executable `scripts/worktree-setup.sh` → tracked tree clean; primary clone + ordinary checkout/restore = no setup.
- Codex-app worktree without dispatcher proof = `write` runs the same tracked setup owner; no second project setup path.
- Setup receipt = per-worktree Git-private + mode `0600` + repository path + public setup/dependency-input fingerprint; secret bytes/hashes forbidden.
- Current receipt skips setup; changed setup/dependency input invalidates it; setup drift + tracked post-setup drift fail closed.
- Literal included input = regular file + `write|publish` converges mode `0600` before PASS; secret bytes/hashes never enter the receipt.
- Ignored hook-manager runtime = rebuild through setup + tracked canonical `post-checkout` owner; `.worktreeinclude` copy = forbidden.
- Tracked files never belong in `.worktreeinclude`; universal copy patterns = forbidden.
- Explicit path = required readiness input; missing path = block.
- Glob = exceptional narrow project-owned family; every entry must match + smoke proof must prove required members.
- Detached Codex worktree = valid for planning/building; named task branch required before commit/push.
- Setup proof + smoke command/result + ignored-state classification → Feature Brief engineering evidence when one exists.
