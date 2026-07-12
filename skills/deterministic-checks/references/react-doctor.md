# React Doctor

1. Runner → `npx --yes react-doctor@latest`; no project install.
2. Staged/pre-commit → `npx --yes react-doctor@latest . --staged --blocking warning --no-telemetry -y`.
3. Changed/pre-push/PR → `npx --yes react-doctor@latest . --scope changed --base <base> --blocking warning --no-telemetry --json --json-out <report.json> -y`.
4. Full/new repo → `npx --yes react-doctor@latest . --scope full --blocking warning --no-telemetry --json --json-out <report.json> -y`.
5. Diagnose → `npx --yes react-doctor@latest why <file:line>`; rule → `npx --yes react-doctor@latest rules explain <rule> --json`.
6. Nonzero/incomplete/skipped/diagnostic = `FAIL`.
