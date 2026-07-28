# React Doctor

1. Staged/pre-commit → `npx --yes --package react-doctor@0.9.2 react-doctor . --staged --blocking warning --no-telemetry -y`.
2. Changed/pre-push/PR → same pinned command + `--scope changed --base <base> --blocking warning --no-telemetry --json --json-out <report.json> -y`.
3. Full/new repo → same pinned command + `--scope full --blocking warning --no-telemetry --json --json-out <report.json> -y`.
4. Diagnose → pinned command + `why <file:line>`; rule → pinned command + `rules explain <rule> --json`.
5. Nonzero/incomplete/skipped/diagnostic = `FAIL`; no project install.
