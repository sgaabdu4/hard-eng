# Fallow

1. Changed/pre-push/PR → `npx --yes fallow@latest audit --changed-since <base> --format json --quiet`.
2. Full/new repo → `npx --yes fallow@latest audit --gate all --format json --quiet`.
3. Diagnose → `npx --yes fallow@latest inspect --file <path> --format json` or same command + `--symbol <file>:<export>`.
4. Exit `1`/JSON `fail` = `FAIL`; warning/finding = unresolved.
5. Project-local install/wrapper/runtime copy = forbidden.
