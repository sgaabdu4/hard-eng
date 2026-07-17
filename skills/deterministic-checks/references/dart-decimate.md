# Dart Decimate

- Git root = diff/base attribution; package root = requested `pubspec.yaml` owner.
- Nested package → Git-root execution + exact repo-relative `--workspace`; root package → whole repository.
- Changed/pre-push/PR → `python3 "$HOME/.agents/skills/deterministic-checks/scripts/dart_decimate_gate.py" --package <package-root> --base <base>`.
- Full/new repo → same command + `--full`.
- Runner = scope/base validation + latest `npx` + lossless upstream evidence.
- Exit `1` + unique aggregate partition + every security occurrence tracked/unchanged → inherited-only correction `PASS` receipt.
- Missing per-finding attribution + ambiguous aggregate → `PER_FINDING_ATTRIBUTION_UNAVAILABLE` `FAIL` receipt; changed/untracked occurrence → `FAIL`.
- Malformed JSON + upstream exit `2|8` → unchanged `FAIL`; finding arrays = retained.
- Diagnose → Git root + matching `--workspace <repo-relative-package-root>` + target file/symbol.
- Raw nested-root call → forbidden; root-only call for nested scope → forbidden.
- Finding outside workspace → tooling-scope `FAIL`; never edit unrelated product code.
- Config = project policy; `--workspace` = analysis scope.
