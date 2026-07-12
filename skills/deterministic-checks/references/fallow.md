# Fallow

1. Runner → `npx --yes fallow@latest`; no project install.
2. Changed/pre-push/PR → `npx --yes fallow@latest audit --changed-since <base> --format json --quiet`.
3. Full/new repo → `npx --yes fallow@latest audit --gate all --format json --quiet`.
4. Diagnose → `npx --yes fallow@latest inspect --file <path> --format json` or `npx --yes fallow@latest inspect --symbol <file>:<export> --format json`.
5. Exit `1`/JSON `fail` = `FAIL`; warning/finding = unresolved.
