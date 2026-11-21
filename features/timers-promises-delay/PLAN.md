# Distinguish node:timers/promises setTimeout delays from zero-delay callbacks

Status: Complete

## Outcome + scope

`next-frame-call-javascript` in `.agents/skills/he/semgrep/performance.yaml` stops flagging real delays (`>= 17 ms` or a runtime delay variable) passed to `setTimeout` imported from `node:timers/promises` or `timers/promises` (ESM `import` or CommonJS `require`), while continuing to refuse zero/sub-frame delays (`setTimeout()`, `setTimeout(0)`, `setTimeout(16)`, `setTimeout(ZERO)`) and continuing to refuse callback-style `setTimeout(fn)` / `setTimeout(fn, 0)` / `setTimeout(fn, <17)` everywhere else. Non-goals: changing the 17 ms threshold or the Dart deferral rule.

## Sources + coverage

Sources: N/A — post-release fault fix authorized by the user in chat on 2026-11-21 ("Don't ask me again to work autonomously"); no external source document.

## Repository context

Owners: `.agents/skills/he/semgrep/performance.yaml` (`next-frame-call-javascript`); `tests/fixtures/performance/timers.ts.txt`, `timers.js.txt`, `timers_promises.ts.txt`, `timers_promises.js.txt`; `tests/test_hot_paths.py::test_each_rule_finds_exactly_the_annotated_lines`.
Same cause: the single-argument callback pattern `setTimeout($F)` matched `setTimeout(delay)` from `node:timers/promises` because both share the name `setTimeout` with opposite parameter order (`(callback, delay)` vs `(delay, value)`).
Single source: `.agents/skills/he/semgrep/performance.yaml` is the only rule definition; no duplicate rule exists.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: Autonomous — user authorized autonomous execution of the post-release follow-ups on 2026-11-21.

## Acceptance + steps

- [x] `setTimeout` imported from `node:timers/promises` or `timers/promises` passes for delays `>= 17 ms`, runtime delay variables, and second-argument return values such as `setTimeout(200, 0)`, while still failing for `setTimeout()`, `setTimeout(0)`, `setTimeout(ZERO)`, `setTimeout(16)` and `setTimeout(10, "value")` → `tests/test_hot_paths.py::test_each_rule_finds_exactly_the_annotated_lines`.
- [x] Callback-style global `setTimeout(fn)`, `setTimeout(fn, 0)` and `setTimeout(fn, 16)` remain refused and real delays `>= 17 ms` remain allowed → `tests/test_hot_paths.py::test_each_rule_finds_exactly_the_annotated_lines` and `tests/test_hot_paths.py::test_the_annotated_chunks_cover_every_fixture_and_every_rule`.

## Baseline + execution

Result: Passed
Evidence: `develop` head `f5e7cb0c` passed `Hard Eng` and `Canary` CI; adding `tests/fixtures/performance/timers_promises.ts.txt` reproduced the false positive and missed `setTimeout()` before the rule edit (`test_each_rule_finds_exactly_the_annotated_lines[1]` failed on `timers_promises.ts`).
Execution: Single builder in linked worktree `wt/fix-timers-promises` off `origin/develop`.

## Risks + recovery

A file that imports `setTimeout` from `node:timers/promises` and also calls `globalThis.setTimeout(fn)` still triggers the `$G.setTimeout($F)` branch. Recovery: revert the commit in `.agents/skills/he/semgrep/performance.yaml` and remove the two fixture files.

## ux_reference

N/A — Semgrep rule and test fixtures only; no visible UI.

## Verification

Result: Passed
Evidence: Failing-first reproduction confirmed `timers_promises.ts.txt` failed before the edit; after editing `.agents/skills/he/semgrep/performance.yaml`, `uv run --with pytest pytest tests/test_hot_paths.py -k "test_each_rule_finds_exactly_the_annotated_lines or test_the_annotated_chunks_cover_every_fixture_and_every_rule"` passed (5 passed in 23.43 s), and `hard-eng.py check --quick --base origin/develop --plan-stage Complete` passed.
E2E: N/A — static Semgrep rule change with no user journey.
Real service: N/A — local Semgrep rule and fixtures call no outside service.
Retro: Always distinguish Node promise-based APIs that reuse browser global names with reversed argument order when writing single-argument Semgrep patterns.

Delivery target: Merge
Delivery path: PR into develop.
Delivery: Pending — PR checks green, independent review complete, and merged into develop.
