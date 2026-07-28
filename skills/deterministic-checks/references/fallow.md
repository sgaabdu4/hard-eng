# Fallow

1. Changed/pre-push/PR → `npx --yes --package fallow@3.10.0 fallow audit --changed-since <base> --format json --quiet`.
2. Full/new repo → `npx --yes --package fallow@3.10.0 fallow audit --gate all --format json --quiet`.
3. Diagnose → `npx --yes --package fallow@3.10.0 fallow inspect --file <path> --format json` or same command + `--symbol <file>:<export>`.
4. Exit `1`/JSON `fail` = `FAIL`; warning/finding = unresolved; target-project install requires an explicit project owner.
