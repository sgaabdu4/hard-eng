# Distinguish node:timers/promises setTimeout delays from zero-delay callbacks

Status: Complete

## Outcome + scope

`next-frame-call-javascript` in `.agents/skills/he/semgrep/performance.yaml` stops flagging real delays (`>= 17 ms` or a runtime delay variable) passed to `setTimeout` imported from `node:timers/promises` or `timers/promises` (ESM `import` or CommonJS `require`), while continuing to refuse zero/sub-frame delays (`setTimeout()`, `setTimeout(0)`, `setTimeout(16)`, `setTimeout(ZERO)`) and continuing to refuse callback-style `setTimeout(fn)` / `setTimeout(fn, 0)` / `setTimeout(fn, <17)` everywhere else. Non-goals: changing the 17 ms threshold or the Dart deferral rule.

## Sources + coverage

Sources: N/A — post-release follow-up fix for the `node:timers/promises` false positive; no external source document.

## Repository context

Owners: `.agents/skills/he/semgrep/performance.yaml` (`next-frame-call-javascript`); `.hooks/hot_paths.py` (`hidden_deferral`, `refuse_hidden_deferrals`); `tests/fixtures/performance/timers.ts.txt`, `timers.js.txt`, `timers_promises.ts.txt`, `timers_promises.js.txt`, `timers_promises_alias.ts.txt`; `tests/test_hot_paths.py`.
Same cause: the single-argument callback pattern `setTimeout($F)` and the partial-parse fallback read the second argument as delay, matching `setTimeout(delay)` from `node:timers/promises` because both share the name `setTimeout` with opposite parameter order (`(callback, delay)` vs `(delay, value)`).
Single source: `.agents/skills/he/semgrep/performance.yaml` is the Semgrep rule owner and `.hooks/hot_paths.py` is the partial-parse fallback owner.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: Human-loop — post-release follow-up authorized in chat on 2026-11-21.

## Acceptance + steps

- [x] `setTimeout` imported from `node:timers/promises` or `timers/promises` (unaliased or aliased, ESM or CommonJS) passes for delays `>= 17 ms`, runtime delay variables, and second-argument return values such as `setTimeout(200, 0)`, while still failing for `setTimeout()`, `setTimeout(0)`, `setTimeout(undefined, ...)`, `setTimeout(ZERO)`, `setTimeout(16)` and `setTimeout(10, "value")` → `tests/test_hot_paths.py::test_each_rule_finds_exactly_the_annotated_lines` and `tests/test_hot_paths.py::test_hidden_deferral_respects_timers_promises_argument_order`.
- [x] Callback-style global `setTimeout(fn)`, `setTimeout(fn, 0)` and `setTimeout(fn, 16)` remain refused (including alongside an aliased `timers/promises` import) and real delays `>= 17 ms` remain allowed → `tests/test_hot_paths.py::test_each_rule_finds_exactly_the_annotated_lines` and `tests/test_hot_paths.py::test_the_annotated_chunks_cover_every_fixture_and_every_rule`.

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
Evidence: Failing-first reproduction confirmed `timers_promises.ts.txt` failed before the edit; after editing `.agents/skills/he/semgrep/performance.yaml` and `.hooks/hot_paths.py`, `uv run --with pytest pytest tests/test_hot_paths.py -k "test_each_rule_finds_exactly_the_annotated_lines or test_the_annotated_chunks_cover_every_fixture_and_every_rule or test_hidden_deferral_respects_timers_promises_argument_order"` passed, and `hard-eng.py check --quick --base origin/develop --plan-stage Complete` passed.
Review declined: constant-propagated identifier delay such as `const ZERO = 0; await setTimeout(ZERO)` inside a Semgrep `PartialParsing` gap :: the regex fallback in `.hooks/hot_paths.py` has never evaluated constant bindings for callback `setTimeout(fn, ZERO)` either; full constant propagation belongs to Semgrep, which covers `timers_promises.ts.txt` when parsed.
Review declined: indented function-local CommonJS `require("node:timers/promises")` inside a Semgrep `PartialParsing` gap :: the fallback only matches top-level CommonJS imports so a local helper import never weakens global `setTimeout(fn, 0)` checks anywhere in the file, including within the 3 context lines; full lexical scope belongs to Semgrep.
Review declined: `import ... from "node:timers/promises"` text inside a template literal string in a file that also has a Semgrep `PartialParsing` gap over a global `setTimeout(fn, 0)` :: the regex fallback only strips comments (`code_without_comments`), not string or template literals, and building a JS string/template parser in the fallback exceeds the scope of a partial-parse safety net.
E2E: N/A — static Semgrep rule change with no user journey.
Real service: N/A — local Semgrep rule and fixtures call no outside service.
Retro: Always distinguish Node promise-based APIs that reuse browser global names with reversed argument order when writing single-argument Semgrep patterns.

Delivery target: Merge
Delivery path: PR into develop.
Delivery: Pending — PR checks green, independent review complete, and merged into develop.
