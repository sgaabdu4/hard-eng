# Keep routine agent hooks quiet

Status: Complete

## Outcome + scope

Remove repeated learning prompts after ordinary prompts/tools, unnecessary integration probes at session start, and duplicate source-suite execution during verified updates. Preserve actual failure, completion, push and CI verification. Review active consumer tasks for concrete shared-flow defects.

## Repository context

agent_hooks.py owns native events and startup context; setup.py registers those events and detects integrations at installation. Successful tool calls repeat the same instruction, and startup scans source to request every integration. Existing owners can remove this overhead without a cache, dependency or new state.

## Decisions + authorization

Blockers: None

The user authorized fixing confirmed flow inefficiencies and reviewing active tasks. One builder owns this source change. Request real tool readiness proof when relevant. Preserve session updates, failure diagnostics, original Git baseline and full verification. No test-result cache or verification checks removed. Public evidence uses synthetic fixtures only.

## Acceptance + steps

- [x] Fresh installs register session, supported failure and stop events, with no successful prompt/tool callbacks.
- [x] Supported updates remove obsolete owned callbacks while preserving unrelated user hooks.
- [x] Startup avoids integration scans and unrelated tool calls; relevant use still requires real readiness proof.
- [x] Failure/completion behavior, unchanged-session honesty and verification gates remain intact.
- [x] Review active tasks, route concrete defects to existing owners and report remaining delivery limits.
- [x] Reuse the exact source revision's upstream CI proof during updates; retain candidate whitespace/compile/application checks, conflict protection and rollback.

## Baseline + execution

Result: Passed
Evidence: Unchanged implementation b4c508e passed all17 gates,502 regressions,four performance tests and exact main CI34850243972. Reuse matching baseline; validate Ready before production edits, then exercise installed registration/update and native hook responses plus the final gate.

## Risks + recovery

Preserve custom hooks; do not retain obsolete owned registrations. Startup guidance cannot prove native host trust or integration readiness. Full completion checks intentionally remain uncached. Consumer/plugin failures have separate owners and remain open until their proof arrives.

## ux_reference

N/A — native hook configuration and text output have no visual interface.

## Verification

Result: Passed
Evidence: Ready gate passed before implementation. Hook/setup/update suites passed139 tests and the hook change passed all17 gates with497 regressions and four performance tests. Native synthetic updater removed owned callbacks, preserved a custom callback and committed a clean target. Fixture preparation first exposed missing remote and manifest/gate configuration; these were corrected in the temporary fixture without changing production checks. Startup rejects integration scanning; existing failure/completion regressions remain. Removed275 repeated characters per ordinary tool call; no token/runtime benchmark claim. The reused updater regression failed on the duplicate source-suite call, then all78 updater/hook tests passed after its removal. Exact-source CI selection, candidate checks, conflict preservation and rollback remain. No cache or new state. Active-task review identified an external lint/fix regression; its existing owner is repairing it and has updated its own wrapper through the supported command. Consumer delivery and that package release remain separate open work. Final integrated gate follows on this combined change.

Final integrated proof: all17 gates passed,497 regressions and four performance tests; no new files, dependencies or persistent state. Ready for ship — local implementation and verification complete; delivery not performed.

Delivery target: Merge
Delivery: Pending — task PR, required CI, merge and exact main verification.
