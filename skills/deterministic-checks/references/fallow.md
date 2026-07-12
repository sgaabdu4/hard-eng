# Fallow

1. Changed/pre-push/PR → `npx --yes fallow audit --changed-since <base> --format json --quiet`.
2. Full/new repo → `npx --yes fallow audit --gate all --format json --quiet`.
3. Diagnose → `npx --yes fallow inspect --file <path> --format json` or `npx --yes fallow inspect --symbol <file>:<export> --format json`.
4. Exit `1`/JSON `fail` = `FAIL`; warning/finding = unresolved; no project install.
