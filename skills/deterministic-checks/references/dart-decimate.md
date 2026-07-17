# Dart Decimate

1. Roots = package (`pubspec.yaml`) + containing Git repository.
2. Changed/pre-push/PR → `python3 "$HOME/.agents/skills/deterministic-checks/scripts/dart_decimate_gate.py" --package <package-root> --base <base>`.
3. Full/new repo → same command + `--full` instead of `--base`.
4. Runner validates package/base → invokes latest `npx` at repository root → Git paths stay repository-relative.
5. Security error count = introduced errors + non-security error count = pre-existing errors + every security occurrence unchanged → `hard_eng_gate.result=pass`; all findings stay visible.
6. Changed/untracked/invalid occurrence OR count/ID/candidate ambiguity → explicit `hard_eng_gate.result=fail`; upstream failure preserved.
7. Raw `audit .` from nested package = forbidden; it can double-prefix tracked paths.
8. Diagnose changed → `npx --yes dart-decimate html <repo-root> --compare <base>`; agent JSON → `npx --yes dart-decimate json <repo-root> --compare <base>`.
9. Diagnose target → `npx --yes dart-decimate inspect <repo-root> --file <repo-relative-path> --format json`; symbol/rule use same repository-root contract.
10. Upstream exit `1|2|8` = `FAIL` unless rule 5 proves inherited-only; no finding/path filtering.
