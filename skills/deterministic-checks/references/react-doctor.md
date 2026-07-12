# React Doctor

1. Staged/pre-commit → `npx --yes react-doctor . --staged --blocking warning --no-telemetry -y`.
2. Changed/pre-push/PR → `npx --yes react-doctor . --scope changed --base <base> --blocking warning --no-telemetry --json --json-out <report.json> -y`.
3. Full/new repo → `npx --yes react-doctor . --scope full --blocking warning --no-telemetry --json --json-out <report.json> -y`.
4. Diagnose → `npx --yes react-doctor why <file:line>`; rule → `npx --yes react-doctor rules explain <rule> --json`.
5. Nonzero/incomplete/skipped/diagnostic = `FAIL`; no project install.
