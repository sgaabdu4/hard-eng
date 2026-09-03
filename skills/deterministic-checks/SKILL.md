---
name: deterministic-checks
description: Run deterministic project gates and worktree readiness. Use before non-trivial mutations or commits, and when build, test, lint, or CI commands must pass.
---

# Deterministic Checks

- Owner = exact commands + analyzers/linters/scanners + hooks + CI wiring/results.
- Project command = `python3 "$HOME/.agents/skills/deterministic-checks/scripts/bounded_run.py" --timeout <seconds> --cwd <owner-root> -- <argv>`.
- Gate cwd = impacted owner package root via `--cwd`; repository-root execution over unrelated owners = `FAIL`.
- GitHub delivery receipt = `python3 "$HOME/.agents/skills/deterministic-checks/scripts/github_delivery.py" --repo <owner/repo> --run-id <id> --expected-repository <owner/repo> --sha <sha> --workflow <name> --workflow-id <id> --workflow-path <path@ref> --event <event> --ref <branch> --run-attempt <n> --check-suite-id <id> [--reusable-workflow '<path>::<sha>[::<ref>]'] --require-job <job> --require-step '<job>::<step>'`.
- Affected-full selection + parallel execution = [Affected-full gates](references/affected-full.md).
- Gate efficiency = one execution per exact tree + actor + required seam; reuse valid receipt/artifact; rerun only after tree/environment/mechanism change or invalid receipt; duplicate equivalent setup/build/gate = `FAIL`.
- Deadline = required + whole run; timeout/interrupt/terminal loss → TERM → grace → KILL entire command group; raw unbounded project command = `FAIL`.
- Test behavior/seam/assertion/mutation design = `test-quality`.
- Real browser/device scenario proof = `e2e`.

## Route

- Stack evidence + project gate owners → run every matching row on final tree.

| Scope | Required gates |
|---|---|
| Worktree mutation/publish | [Worktree readiness](references/worktree.md) |
| First paid or state-changing external/native attempt or retry | [Retry readiness](references/retry-readiness.md) |
| Lifecycle slice/full-gate proof | [Slice gate](references/slice-gate.md) |
| Pre-ship mutation strength, every feature | [Mutation receipt](references/mutation.md) |
| Copy-paste clones, Python/Dart, baseline + new-only | [Clones](references/clones.md) |
| Repository context | [PRODUCT/DESIGN](references/context-docs.md) |
| JS/TS | typecheck + tests + every configured formatter/linter gate + [Fallow](references/fallow.md) + declared boundary-contract gate; no formatter/linter owner → Biome format + lint |
| React/Next | JS/TS row + [React Doctor](references/react-doctor.md) + declared boundary-contract gate |
| Dart, non-Flutter | package-root `dart analyze` + `dart test` + [Dart Decimate](references/dart-decimate.md) + declared boundary-contract gate |
| Flutter | package-root `dart analyze` + `flutter test` + [Dart Decimate](references/dart-decimate.md) + declared boundary-contract gate |
| Python | manifest-declared `python-format` + `python-lint` (Ruff) + `python-tests` + `python-types` |
| Security, any stack | push/ci `secrets` (gitleaks) full-tree scan; Python dependency manifest → `sast` (Bandit) + `deps-audit` (pip-audit) |

## Select Rules

- Project impact classifier = project-owned SSOT; repository layout hard-coding in global skills = forbidden.
- JS/TS tool selection = setup/gate-migration only; later gates run manifest-declared commands + never repeat selection.
- Any JS/TS formatter or linter command/config exists → preserve the whole current setup + continue silently; no migration advice + no added owner.
- No JS/TS formatter or linter command/config exists → add Biome as the integrated format/lint owner.
- Flutter + Riverpod → `building-flutter-apps` lint profile; other Flutter/Dart → existing or user-approved `analysis_options.yaml`.
- Python missing format/lint owner → Ruff (integrated format + lint).
- SSOT gate = canonical clock/format/route/schema/key/UI/permission/event/config owner → reject duplicate owner + raw use outside it.
- Detectable syntax/graph drift → lint/scanner; semantic drift → contract test; uncertain regex = forbidden.
- New rule requires accepted contract/repeated defect + closest owner + failing violation fixture + passing valid fixture + CI execution.
- Admission met for a structural/boundary rule → [Structural routes](references/structural-routes.md) per-language wiring.

## Enforce

- Commands + config + CI = project-owned SSOT; slice receipts resolve family argv from `hard-eng.gates.json`, never caller shell text.
- Declared `boundary-contracts` = mandatory for the marked project and its explicit `boundary_contracts.application_roots`; `local_package_roots` may opt in first-party packages. Relevant source and contract/config changes under those roots must cover it, and omission or failure blocks the gate. Scoped TypeScript/React roots require direct `zod@4`, one recognized lockfile resolving Zod 4, and the project-owned Zod boundary command. Unlisted packages and external dependencies stay out; other stacks keep their native contract tool.
- Independent shared-lock families = bounded parallel workers, at most four, with manifest order preserved in results; exclusive source-tree families such as React Doctor remain serialized.
- Security families = `secrets` + `sast` + `deps-audit`; push≡ci phases only + full-tree scan; commit phase + slice derivation = forbidden.
- Gate tree stays write-free: Ruff families = `--no-cache` + format `--check` + lint without `--fix`; pytest = `-p no:cacheprovider`; `secrets` = `--redact` + fail-on-findings + no baseline suppression.
- Dart Decimate + Fallow + React Doctor runtime = canonical `npx --yes <tool>@latest`; project-local install/wrapper/runtime copy = forbidden.
- Same-worktree gate concurrency = `project_gate.py` + `dart_decimate_gate.py` shared source lock + React Doctor exclusive source lock; aliases converge + linked worktrees stay independent + raw overlapping scanner execution forbidden.
- Interrupted/non-restored React Doctor = Git-private source quarantine + terminal process-group receipt → later gates fail before commands → reboot or receipt + exact manual worktree restoration auto-clears; automatic checkout/overwrite forbidden.
- CI action/tool pin = latest stable supported major from official primary source + migration/runner compatibility proof; stale major = `FAIL` unless exact compatibility blocker + explicit approval.
- External tool adapter = scope + validate + invoke; upstream output/verdict/exit = unchanged. Reinterpretation → `research` official versioned contract `PASS` + regression proof.
- Structured external-tool result = dedicated output file or machine-only stdout + whole-channel parse; first `{`/`[` inference from human logs forbidden; ANSI/warning/version/update/bracket prefix or trailing non-whitespace = ambiguous → `FAIL`.
- External CLI with tracked-config write potential = prefer no-write mode or isolated checkout; otherwise require exclusive single-writer ownership + immutable exact preimage of bytes/mode/index entries+flags/full status.
- Approved CLI output = preserve + validate; automatic restore = incidental out-of-approved-scope writes only + current state exactly matches captured CLI postimage; mismatch/concurrent drift → `FAIL` without overwrite; post-restore checkout = preimage + approved output.
- Background descendant after command exit = terminated + `FAIL` when command contract expected none.
- Nested timeout = internal deadline + worst in-flight attempt + shutdown headroom < outer deadline; cancellation/terminality proof crosses the actual adapter seam.
- Compatible real-tool proof = interpreter/compiler/runner behavior parsed or executed by that tool; source-text/substring/static intent check = wiring only.
- Paid/native retry = [Retry readiness](references/retry-readiness.md) PASS first; exact-line correction + blind full retry = `FAIL`.
- Missing/changing hook or CI wiring + Git fixture/self-test → read [hooks.md](references/hooks.md).
- Diagnostic/validation-only workflow path = external-write-free + zero-impact regression; changed path-to-mutation mapping = contract change.
- Native gates + scanners = complementary proof.
- Finding → fix owned cause/blast radius → rerun exact gate; quality JSON content + upstream exit both gate, so exit `0` cannot erase a reported finding.
- Gate trust = exit code + compact receipt (path + hash + verdict); loading gate sources or full evidence artifacts into main context to re-prove PASS = forbidden.
- Gate identity = bounded-run receipt line (exe + cwd + redacted argv count/digest + exit); focused subset/earlier run/different exe or cwd ≠ proof for another failed gate.
- Local vs CI toolchain divergence (resolved exe/runtime version) on same gate = `FAIL` until parity.
- Missing project manifest/family → [Gate migration](references/gate-migration.md); other tool/config/runtime error = `FAIL`.
- Remote CI PASS = delivered commit's required universal/affected-owner/aggregate jobs green; proven non-impacted scope may skip; missing/skipped/cancelled required scope = `FAIL`; workflow-level green alone = insufficient.
- Forbidden = `--no-verify` + `|| true` + `continue-on-error` + silent skip + severity downgrade + baseline refresh to manufacture green.
- Fallow + React Doctor + Dart Decimate = one full owner scan + zero findings; changed/staged/baseline/introduced-only mode + inherited exception = forbidden.
- Scanner silently strips unknown flags → argv text ≠ mode proof; React Doctor scan = `--help` preflight advertising every manifest flag + emitted full-scan report; unadvertised flag = `FAIL` before execution.
- New repo + existing repo = all findings block.

## Proof

| Result | Evidence |
|---|---|
| `PASS` | Matching commands + exits + reports; no unresolved finding |
| `CONCERNS` | Missing gate + exact gap |
| `FAIL` | Finding, crash, config error, skipped scope, or unapproved bypass |
