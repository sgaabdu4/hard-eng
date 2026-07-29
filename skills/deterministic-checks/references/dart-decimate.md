# Dart Decimate

- Git root = one process; package root = requested `pubspec.yaml` owner.
- Nested package → Git-root execution + exact repo-relative `--workspace`; root package → whole repository.
- Every gate → `python3 "$HOME/.agents/skills/deterministic-checks/scripts/dart_decimate_gate.py" --package <package-root> --timeout <seconds>`.
- Runner = package/Git-root validation + shared source lock + bounded `npx --yes dart-decimate@latest json <git-root>` + exact-tree proof + unchanged upstream exit.
- Execution = one process per affected Git root; repeated full-root scan per nested package = forbidden.
- Project-local Dart Decimate adapter/runtime/copy = forbidden.
- Audit/changed/base/baseline/regression mode = forbidden.
- Nonzero/finding/incomplete/skipped = `FAIL`; fix root cause + rerun full scan.
- Diagnose → Git root + matching `--workspace <repo-relative-package-root>` + target file/symbol.
- Raw nested-root call → forbidden; root-only call for nested scope → forbidden.
- Finding outside workspace → tooling-scope `FAIL`; never edit unrelated product code.
- Config = project policy; `--workspace` = analysis scope.
