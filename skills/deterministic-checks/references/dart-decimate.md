# Dart Decimate

1. Roots = package (`pubspec.yaml`) + containing Git repository.
2. Changed/pre-push/PR → `python3 "$HOME/.agents/skills/deterministic-checks/scripts/dart_decimate_gate.py" --package <package-root> --base <base>`.
3. Full/new repo → same command + `--full` instead of `--base`.
4. Runner validates package/base → invokes latest `npx` at repository root → Git paths stay repository-relative.
5. Grouped security error + every occurrence outside current-side changed lines → evidence preserved + `hard_eng_gate.result=pass`; changed/untracked/invalid/ambiguous occurrence → upstream failure preserved.
6. Raw `audit .` from nested package = forbidden; it can double-prefix tracked paths.
7. Diagnose changed → `npx --yes dart-decimate html <repo-root> --compare <base>`; agent JSON → `npx --yes dart-decimate json <repo-root> --compare <base>`.
8. Diagnose target → `npx --yes dart-decimate inspect <repo-root> --file <repo-relative-path> --format json`; symbol/rule use same repository-root contract.
9. Upstream exit `1|2|8` = `FAIL` unless rule 5 proves inherited-only; no finding/path filtering.
