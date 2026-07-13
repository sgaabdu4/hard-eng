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
| `write` | linked worktree OR clean primary + every literal `.worktreeinclude` path present |
| `publish` | prior `write` PASS + named branch + valid `.worktreeinclude` inputs |

## Provision

1. Before worktree creation, inspect ignored local state + project run/test/build owners.
2. Required non-rebuildable input → tracked root `.worktreeinclude` exact path; secrets = minimum explicit paths.
3. Rebuildable dependency/generated state → Codex local-environment setup or existing project setup owner.
4. Cache/log/database/build/editor/temp state → exclude unless evidence proves non-rebuildable input.
5. Linked worktree → continue; clean primary → continue; dirty primary → create worktree from `HEAD`.
6. Run `write` gate → run setup → run smallest app/test smoke proof.
7. Missing input/setup/smoke failure → fix provisioning owner → recreate/retry before feature mutation.

## Rules

- `.worktreeinclude` must exist in selected starting state before Codex creates the managed worktree.
- Dirty = staged + unstaged tracked + untracked.
- Existing linked worktree = continue; primary clean = continue; primary dirty = isolate from `HEAD` + preserve dirty state.
- Branch = current/named branch; prefix requirement = none.
- `write` = pre-mutation gate; `publish` accepts task-created dirt after prior `write` PASS.
- Every Git worktree = global `post-checkout` dispatcher + tracked `.worktreeinclude` literal `.env*` allowlist.
- Copier = main worktree source + ignored/untracked regular file + no overwrite + mode `0600`; symlink/glob/traversal = reject/skip.
- Repository `core.hooksPath` override → global dispatcher unavailable → integrate existing hook owner + prove copy.
- Tracked files never belong in `.worktreeinclude`; universal copy patterns = forbidden.
- Explicit path = required readiness input; missing path = block.
- Glob = exceptional project-owned family; smoke proof must prove required members.
- Detached Codex worktree = valid for planning/building; named task branch required before commit/push.
- Setup proof + smoke command/result + ignored-state classification → `PLAN.md` repository evidence.
