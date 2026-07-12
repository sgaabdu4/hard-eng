# Dart Decimate

1. Runner → `npx --yes dart-decimate@latest`; no project install.
2. Diagnose changed → `npx --yes dart-decimate@latest html . --compare <base>`; agent JSON → `npx --yes dart-decimate@latest json . --compare <base>`.
3. Diagnose target → `npx --yes dart-decimate@latest inspect . --file <path> --format json` or `npx --yes dart-decimate@latest inspect . --symbol <file>:<symbol> --format json`; rule → `npx --yes dart-decimate@latest explain <issue-type> --format json`.
4. Changed/pre-push/PR gate → `npx --yes dart-decimate@latest audit . --base <base> --format json --summary --gate new-only`.
5. Full/new repo → `npx --yes dart-decimate@latest json .`.
6. Exit `1`, `2`, or `8` = `FAIL`.
