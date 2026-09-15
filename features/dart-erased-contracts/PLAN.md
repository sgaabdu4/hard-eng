# Recognize Dart declarations without executable coverage counters

Status: Complete

## Outcome + scope

Allow Dart LCOV validation to omit only source libraries whose declarations cannot
emit executable counters: abstract contracts and sealed redirecting-factory data
types. Allow Flutter's ignored generated `build/**` artifacts to be excluded from
analysis without allowing tracked handwritten Dart source to be concealed. Do not
weaken line coverage for declarations with executable bodies or add a consumer
exception. Clarify the existing Build handoff so one final Complete gate does not
create a redundant plan-recording or Ready-gate loop. Preserve a successful merge
command as a distinct fact when its immediate post-merge delivery verification is
still pending or fails.

## Repository context

`.hooks/reports.py` calls `.hooks/dart_coverage.py:erased_dart` before declaring
an omitted Dart production file a coverage failure. The existing analyzer AST
classifier accepted only abstract interface members, so ordinary abstract
contracts and sealed redirecting factories remained required even though native
LCOV emitted no counters. `project_setup.validate_dart_exclusions` already asks
Git for native platform roots; its Flutter root set was broader than the actual
generated build artifact need. Live acceptance also found that the Build skill's
post-gate record instruction could trigger a second full gate after a successful
Complete result. The existing canonical Appwrite skill submodule advances to
`cf49d984e3241632883bd0c8de5a863cbaa21f6a`, whose master CI passed its 58 native
tests; this change is a pointer-only integration owned by the coordinator.
`ship_actions.run` previously lost the successful `gh pr merge` outcome when its
next delivered verification encountered a pending required main check.

## Decisions + authorization

Blockers: None
The user authorized the generic source repair, native tests and Ready gate. The
classifier uses analyzer AST node kinds only; it does not inspect names, Freezed
annotations, or consumer-specific paths. The implementing agent owns commits,
publishing and delivery; the coordinator reviews only.

## Acceptance + steps

- [x] An abstract contract, including one with `implements`, is omitted only when
  every member is declarative.
- [x] A sealed class containing only a redirecting factory is omitted without
  treating its annotation as evidence.
- [x] Method bodies, factory bodies, default parameters, generative constructors,
  static non-constant fields and executable annotated classes remain mandatory.
- [x] An ignored Flutter `build/**` artifact is allowed while a tracked handwritten
  `build/**` Dart file and unsafe matches fail the existing native guard.
- [x] Existing Dart LCOV report validation remains the owner of omitted-file
  failures and uses no consumer-specific exception.
- [x] A native `dart test --coverage` fixture compiles and uses the contract and
  redirecting factory, omits their handwritten libraries from LCOV, and retains an
  imported uncalled executable library with a zero-hit counter.
- [x] Build guidance retains one final Complete gate after focused/runtime proof
  and does not direct a second Ready check or plan rewrite for its handoff.
- [x] The existing canonical Appwrite skill pointer uses the verified master
  revision without copying or editing its contents here.
- [x] A successful merge command followed by pending/failed delivered verification
  remains a nonzero delivery result while stating that the command succeeded.

## Baseline + execution

Result: Passed
Evidence: Native analyzer fixture and LCOV report contracts were exercised before
the integrated Ready check: 186 focused tests passed after the required source
submodule was initialized. The first typecheck in the new worktree found only
missing locked dependencies; `uv sync --locked` repaired that environment and
the configured Pyrefly command then reported 0 diagnostics.

One builder changes the existing classifier and exclusion validator; the existing
Dart fixture and configuration test own regression proof. The Ready gate is the
integration check.

## Risks + recovery

The parser runs against the consumer's analyzer package configuration. An absent,
incompatible or malformed parser result already returns no waiver. The new class
rule is restricted to abstract or sealed declarations and rejects default clauses,
generative constructors and non-empty bodies. Revert the two owner changes if a
native analyzer version cannot parse the supported AST types.

## ux_reference

N/A — coverage and analyzer configuration have no product UI or runtime screen.

## Verification

Result: Passed
Evidence: The native Dart coverage fixture runs `dart test --coverage` then `coverage:format_coverage`, compiles and uses both declaration forms, confirms their handwritten libraries are absent from native LCOV, and retains an imported uncalled executable counter at zero hits. It and the merge-delivery side-effect contract passed 31 tests in 36.05 seconds. `uv sync --locked` then `uvx pyrefly@latest check --check-unannotated-defs=true --min-severity info` previously reported 0 diagnostics. The earlier Complete run exposed only a Ruff import-order failure, now repaired. The final Complete check follows this exact combined tree, including the verified Appwrite pointer.
E2E: N/A — this source-only parser/configuration repair has no user interaction; the native Dart parser and LCOV fixture exercise the actual affected command boundary.

Delivery target: Merge
Delivery: Pending — PR merge, exact main CI, native delivered verification and any permitted cleanup remain required.
