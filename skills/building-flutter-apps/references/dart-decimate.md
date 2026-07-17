# Dart Decimate

## Read first

1. Dart Decimate = required graph/code-health gate after every Flutter/Dart write batch.
2. Dart Decimate + `dart analyze` = complementary required gates; neither replaces the other.
3. Invocation = `npx --yes dart-decimate`; permanent/global/project install = unnecessary.

## Workflow

1. Existing Git project → base = remote default branch; missing remote default → configured upstream.
2. Valid base → run shared repository-root gate:

```bash
python3 "$HOME/.agents/skills/deterministic-checks/scripts/dart_decimate_gate.py" --package <package-root> --base <base-ref>
```

3. New Git project or no valid base → run:

```bash
python3 "$HOME/.agents/skills/deterministic-checks/scripts/dart_decimate_gate.py" --package <package-root> --full
```

4. Finding → inspect target + rule before editing:

```bash
npx --yes dart-decimate inspect <repo-root> --file <repo-relative-path> --format json
npx --yes dart-decimate inspect <repo-root> --symbol <repo-relative-file>:<symbol> --format json
npx --yes dart-decimate explain <issue-type> --format json
```

5. Nested package + linked/shared source → runner validates package but scans Git root; repository-relative diff attribution remains exact.
6. Raw `audit .` from nested package = forbidden; no path filtering or prefix stripping.
7. Exit `1|2|8` or JSON `verdict: fail` → gate `FAIL`; fix owned cause + connected callers → rerun exact gate.
8. Exit `0` + no unresolved finding → gate `PASS`; cite command + base/full scope in Pre-Flight.

## Git pre-push

1. Every Git checkout governed by this skill = [pre-push template](../templates/flutter/tool/dart_decimate_pre_push.sh) wired.
2. Existing pre-push hook → preserve it + invoke the template with `"$@"` after existing checks.
3. Missing pre-push hook → install the template at `git rev-parse --git-path hooks/pre-push` + mode `0755`.
4. `core.hooksPath` override = forbidden; preserve global/project hook dispatch.
5. Push = blocked on Dart Decimate exit `1|2|8`.

## Boundaries

- Existing project = new-only audit; inherited findings remain visible but do not excuse introduced findings.
- New/full project = full JSON scan.
- Auto-fix = preview only unless user explicitly approves the mutation.
- HTML = diagnosis only: `npx --yes dart-decimate html . --compare <base-ref>`.
