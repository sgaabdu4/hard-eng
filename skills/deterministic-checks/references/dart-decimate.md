# Dart Decimate

1. Diagnose changed → `npx --yes dart-decimate html . --compare <base>`; agent JSON → `npx --yes dart-decimate json . --compare <base>`.
2. Diagnose target → `npx --yes dart-decimate inspect . --file <path> --format json` or `npx --yes dart-decimate inspect . --symbol <file>:<symbol> --format json`; rule → `npx --yes dart-decimate explain <issue-type> --format json`.
3. Changed/pre-push/PR → `npx --yes dart-decimate audit . --base <base> --format json --summary --gate new-only`.
4. Full/new repo → `npx --yes dart-decimate json .`.
5. Exit `1|2|8` = `FAIL`; no project install.
