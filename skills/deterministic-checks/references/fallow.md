# Fallow

1. Manifest argv = pinned repository `node_modules/.bin/fallow --fail-on-issues --format json --quiet` → every gate executes the manifest family through `project_gate.py`.
2. One full combined scan = dead code + duplication + health; cache stays enabled.
3. Changed/diff/file/workspace/baseline/regression/audit gate mode = forbidden.
4. Diagnose-only, never gate proof → no concurrent gate + `npx --yes fallow@latest inspect --file <path> --format json` or same command + `--symbol <file>:<export>`.
5. Gate validates combined JSON issue arrays + duplicate groups/families + health/styling findings; nonzero/finding/incomplete/skipped = `FAIL`.
6. Repository dependency version + lockfile = canonical runtime; package-runner download in a gate = forbidden.
7. Execution = `project_gate.py` shared source lock; concurrent Fallow allowed + same-worktree React Doctor audit overlap forbidden.
