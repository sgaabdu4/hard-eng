# Worktree Readiness

## Commands

```sh
python3 <agents-root>/skills/deterministic-checks/scripts/worktree.py --repo <repo-root> --intent read
python3 <agents-root>/skills/deterministic-checks/scripts/worktree.py --repo <repo-root> --intent write
python3 <agents-root>/skills/deterministic-checks/scripts/worktree.py --repo <repo-root> --intent publish
<agents-root>/scripts/git-hooks/install.sh check
```

| Intent | PASS |
|---|---|
| `read` | readable Git checkout + identity evidence |
| `write` | linked worktree OR primary; dirty primary requires explicit `--checkout-choice current`; every literal `.worktreeinclude` path present |
| `publish` | prior `write` PASS + named branch + valid `.worktreeinclude` inputs |

Tracked `AGENTS.override.md` `checkout_policy = primary-only` → primary always selected + dirty primary allowed + linked worktree rejected.

## Provision

1. Before worktree creation, inspect ignored local state + project run/test/build owners.
2. Required local input → tracked root `.worktreeinclude` exact path; secrets = minimum explicit paths.
3. Required generated state without a ready setup owner → narrow project-owned glob + smoke proof; otherwise rebuild through setup.
4. Cache/log/database/build/editor/temp state → exclude unless evidence proves non-rebuildable input.
5. Linked worktree/current branch → continue; clean primary/main → direct allowed; automatic branch/worktree creation = forbidden.
6. Dirty primary + unrelated user dirt → ask once: continue current OR create worktree; selected current → rerun `write --checkout-choice current`.
7. Active Feature Brief + requested checkout change = continue current checkout OR stop for an explicit exact transfer decision; automatic move/recreation forbidden.
8. Run selected checkout Feature Brief `inspect` when one exists + `write` gate → run setup → run smallest app/test smoke proof.
9. Missing input/setup/smoke proof → fix owner → recreate/retry before feature mutation.

## Rules

- `.worktreeinclude` must exist in selected starting state before Codex creates the managed worktree.
- Feature Brief stays with its selected checkout; checkout change never silently recreates or copies lifecycle state.
- Branch = current/named branch; prefix requirement = none.
- Main branch = valid local choice; delivery still obeys repository policy + publish approval.
- `write` = pre-mutation gate; `publish` accepts task-created dirt after prior `write` PASS.
- Every Git worktree = global `post-checkout` dispatcher + tracked `.worktreeinclude` ignored-input allowlist.
- Copier = main worktree source + ignored/untracked regular file + no overwrite + mode `0600`; symlink/traversal = reject/skip.
- Repository `core.hooksPath` override → global dispatcher unavailable → integrate existing hook owner + prove copy.
- Tracked files never belong in `.worktreeinclude`; universal copy patterns = forbidden.
- Explicit path = required readiness input; missing path = block.
- Glob = exceptional narrow project-owned family; every entry must match + smoke proof must prove required members.
- Detached Codex worktree = valid for planning/building; named task branch required before commit/push.
- Setup proof + smoke command/result + ignored-state classification → Feature Brief engineering evidence when one exists.
