# Fallow

1. Every gate → `npx --yes fallow@latest --fail-on-issues --format json --quiet`.
2. One full combined scan = dead code + duplication + health; cache stays enabled.
3. Changed/diff/file/workspace/baseline/regression/audit gate mode = forbidden.
4. Diagnose → `npx --yes fallow@latest inspect --file <path> --format json` or same command + `--symbol <file>:<export>`.
5. Nonzero/finding/incomplete/skipped = `FAIL`; fix root cause + rerun full scan.
6. Project-local install/wrapper/runtime copy = forbidden.
