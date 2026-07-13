# Worktree Readiness

## Commands

```sh
python3 <agents-root>/skills/deterministic-checks/scripts/worktree.py --repo <repo-root> --intent read
python3 <agents-root>/skills/deterministic-checks/scripts/worktree.py --repo <repo-root> --intent write
python3 <agents-root>/skills/deterministic-checks/scripts/worktree.py --repo <repo-root> --intent publish
```

| Intent | PASS |
|---|---|
| `read` | readable Git checkout + identity evidence |
| `write` | isolated worktree + every literal `.worktreeinclude` path present |
| `publish` | `write` PASS + named task branch |

## Provision

1. Before worktree creation, inspect ignored local state + project run/test/build owners.
2. Required non-rebuildable input → tracked root `.worktreeinclude` exact path; secrets = minimum explicit paths.
3. Rebuildable dependency/generated state → Codex local-environment setup or existing project setup owner.
4. Cache/log/database/build/editor/temp state → exclude unless evidence proves non-rebuildable input.
5. Create worktree → run `write` gate → run setup → run smallest app/test smoke proof.
6. Missing input/setup/smoke failure → fix provisioning owner → recreate/retry before feature mutation.

## Rules

- `.worktreeinclude` must exist in selected starting state before Codex creates the managed worktree.
- Tracked files never belong in `.worktreeinclude`; universal copy patterns = forbidden.
- Explicit path = required readiness input; missing path = block.
- Glob = exceptional project-owned family; smoke proof must prove required members.
- Detached Codex worktree = valid for planning/building; named task branch required before commit/push.
- Setup proof + smoke command/result + ignored-state classification → `PLAN.md` repository evidence.
