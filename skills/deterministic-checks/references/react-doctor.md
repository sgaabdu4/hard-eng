# React Doctor

1. Every gate → `npx --yes react-doctor@latest . --scope full --blocking warning --no-respect-inline-disables --no-telemetry --json -y`.
2. Default parallel workers stay enabled; one full scan replaces staged + changed + full repeats.
3. Staged/changed/files/lines/base/project/category/time-budget narrowing = forbidden.
4. Diagnose → latest command + `why <file:line>`; rule → latest command + `rules explain <rule> --json`.
5. Nonzero/finding/incomplete/skipped = `FAIL`; fix root cause + rerun full scan.
6. Project-local install/wrapper/runtime copy = forbidden.
