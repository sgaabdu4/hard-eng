# React Doctor

1. Staged/pre-commit → `npx --yes react-doctor@latest . --staged --blocking warning --no-telemetry -y`.
2. Changed/pre-push/PR → same latest command + `--scope changed --base <base> --blocking warning --no-telemetry --json --json-out <report.json> -y`.
3. Full/new repo → same latest command + `--scope full --blocking warning --no-telemetry --json --json-out <report.json> -y`.
4. Diagnose → latest command + `why <file:line>`; rule → latest command + `rules explain <rule> --json`.
5. Nonzero/incomplete/skipped/diagnostic = `FAIL`.
6. Project-local install/wrapper/runtime copy = forbidden.
