# Fallow

1. Manifest argv = pinned repository `node_modules/.bin/fallow audit --max-crap 30 --format json` (changed files against the merge base: dead code + new clones + complexity + CRAP ≥ 30; `--coverage coverage/coverage-final.json` auto-detected; per-analysis `--dead-code-baseline|--health-baseline|--dupes-baseline` allowed) → every gate executes the manifest family through `project_gate.py`; verdict `fail` = gate FAIL, `pass|warn` = PASS.
2. Audit scope = files changed against the merge base; inherited debt never fails (`gate: new-only`); global `--baseline`/`--changed-since`/`--diff-*`/`--file`/`--workspace` scoping flags = forbidden.
3. Non-audit combined mode (`--fail-on-issues`) = superseded; manifest command without `audit` = manifest FAIL.
4. Diagnose-only, never gate proof → no concurrent gate + `npx --yes fallow@latest inspect --file <path> --format json` or same command + `--symbol <file>:<export>`.
5. Gate validates one audit JSON report (`kind=audit` + `verdict` + `summary` + `attribution`); `verdict=fail` names attribution counts + first introduced finding = `FAIL`; malformed/non-audit report = `FAIL`.
6. Repository dependency version + lockfile = canonical runtime; package-runner download in a gate = forbidden.
7. Execution = `project_gate.py` shared source lock; concurrent Fallow allowed + same-worktree React Doctor audit overlap forbidden.
