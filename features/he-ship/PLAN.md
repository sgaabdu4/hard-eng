# Implement verified PR delivery and safe cleanup

Status: Complete

## Outcome + scope

Add HE Ship after HE Build's local Ready-for-ship handoff. Enforce mechanically verifiable delivery requirements through the existing CLI and configuration. The current follow-up closes one observed gap: a Deploy plan with no configured deployment verifier must fail before build completion or merge, instead of first failing after deployment. Keep the existing configuration, runner and plan; add no dependency or alternate workflow. Global installation and remote repository-setting changes remain outside scope.

## Repository context

The source now has native shipping, plan validation and configured deployment commands. Plan validation checks that shipping configuration exists, but does not reject an empty delivery list for Deploy. Shipping checks that list only at the delivered stage. Move this configuration prerequisite to readiness while keeping runtime deployment execution at delivered. Earlier implementation evidence below is historical.

## Decisions + authorization

Blockers: None

The user authorized fixing observed Hard Eng enforcement defects through source PR/main delivery, with YAGNI and preserved project customizations. Task mode: Autonomous. This narrow follow-up uses one implementation owner, existing fixtures and source gates. It does not authorize production data changes, global trust changes or remote protection changes.

## Acceptance + steps

- [x] Ready/Complete plans selecting Deploy reject missing deployment commands while Merge remains valid without them.
- [x] Ship readiness rejects an unconfigured Deploy plan before provider calls or merge, while configured deployment commands still execute only after confirmed delivery.
- [x] Add a terse HE Ship skill with conditional proof/recovery routes; make HE Plan/Build retain UI baseline evidence and establish task isolation at the appropriate starting stage.
- [x] Preserve local Complete as build completion; retain required pending delivery explicitly in the same plan without falsely ticking remote proof or creating another status schema.
- [x] Native shipping checks reject wrong repository/branch/PR, stale or missing required checks, missing before/after UI evidence, unconfirmed merge and missing configured delivery proof.
- [x] Native cleanup checks preserve dirty, untracked, unmerged, reused or active work; remove only the verified task's worktree and branches after in-scope shipping is proven.
- [x] Enforce the configured PR/base-branch policy through the existing pre-push boundary and preserve existing native checks on the actual pushed commit.
- [x] Measure verification cost and implement only evidence-backed efficiency improvements at the existing runner/CI owner; enforce configured budgets without weakening correctness checks.
- [x] Exercise real Git/CLI/native-agent sandbox journeys and provider-contract failure cases, including UI evidence, stale state, interruption, partial delivery and safe cleanup; clearly distinguish simulated provider responses from hosted proof.
- [x] Validate installed-package discovery, metadata/links, actual diff, native regressions and the final integrated source gates. Report remaining host/provider limits honestly.

## Baseline + execution

Result: Passed
Evidence: The current follow-up baseline `uv run python .hooks/hard-eng.py check --plan-stage Draft` passed all 17 gates, including 565 tests, four performance tests and 87.53% line coverage. Native Ready plan validation passed before implementation. The earlier implementation receipts below are historical.

One source coordinator owns integration and shared files. Independent bounded implementation/testing may be delegated after the interfaces and Ready baseline are settled. Reuse existing native fixtures and Python tools. A focused shipping module is needed because the current runner has no PR/delivery-state checks; configuration remains in the existing file. No new dependency or general workflow engine is planned.

Implementation contract: `hard-eng.py ship` exposes read-only readiness/delivery verification and explicitly selected merge/cleanup actions. The first provider is GitHub through the installed `gh` CLI; missing configuration/provider access fails rather than being simulated in production. The existing gate file owns the base branch, required check names, UI path patterns, CI/pre-push budgets and project delivery commands. A same-plan `Delivery target` declaration distinguishes PR, Merge and Deploy without altering local Complete semantics. PR evidence uses labeled before/after GitHub attachments; presence/availability/type is mechanical, visual relevance remains E2E judgment. Cleanup compares actual PR/head/remote state and preserves dirty, locked, current/main or changed task worktrees; Git writes are serialized and guarded against changed refs.

The source's last four successful hosted Hard Eng runs lasted 58, 58, 65 and 73 seconds (read-only GitHub query, runs 34410370552, 34417742396, 34418427326 and 34450562437). A 180-second initial source CI/pre-push budget leaves setup/environment margin while making excessive duration fail explicitly; benchmark after implementation and revise only from measured evidence. This is a project budget, not a universal latency claim. Existing latest-tool freshness and required coverage remain intact.

## Risks + recovery

GitHub/CI data can be absent, stale or racing; return uncertainty rather than a pass. Readiness and cleanup must bind to the actual task and remote result. UI artifact existence does not prove visual quality; direct inspection stays with E2E. Provider fixtures cannot prove live hosted integration. Cleanup must not destroy a running/shared checkout or independent changes. Conflicting source work is preserved.

## ux_reference

N/A — the delivered feature is a CLI and skill workflow; UI sandbox captures verify the evidence contract rather than redesigning a product interface.

## Verification

Result: Passed
Evidence: Three focused cases reproduced acceptance of an unconfigured Deploy plan before the fix. After moving the existing configuration prerequisite earlier, all 107 plan/shipping/action tests pass, including configured readiness without executing deployment and existing old-revision rejection during actual delivery. The integrated Complete gate passed all 17 checks, including 569 tests and four performance checks. The initial integrated run caught a complexity-limit violation; extracting shipping policy validation from plan selection fixed it without weakening the limit. Final diff review found no additional defect. Remote follow-up delivery remains pending; older implementation receipts below do not establish its result.

Ready for ship — local implementation and verification complete; delivery not performed.

Implemented at existing owners:

- HE Ship has a short entrypoint and one conditional native-contract reference. HE Plan/Build preserve matching UI baseline/final evidence; the workflow retains local Complete and explicit pending delivery in the same plan.
- The native `ship` command checks repository/PR/head identity, required current check runs, CI duration, configured UI attachments, confirmed remote merge and project-owned deployment proof. Merge is head-matched. Unknown, pending, stale and overlapping newer CI runs fail closed.
- Cleanup verifies delivery first, retains the plan in the persistent checkout, and guards task identity, refs, dirty/untracked/ignored content, locks, submodules and fetch/push endpoints. Remote deletion uses an exact lease; local deletion uses the expected ref. Partial failures retain recoverable state. Git child commands avoid generating bytecode during cleanup.
- The existing pre-push boundary rejects configured base updates and still runs checks on the actual pushed revision. It deduplicates identical revisions in one push and enforces the configured duration budget. CI avoids duplicate feature-branch push/PR jobs and uses the measured 180-second source budget; required checks and latest-tool policy remain.
- No dependency, generic workflow engine, second status file, source size exception or remote protection change was added. The actual diff was reviewed against the accepted scope; earlier HE Build and other source work remain preserved.

| Proof surface | Actual result and evidence |
| --- | --- |
| Focused shipping regression | 40 core verifier and 20 action tests passed in 10.00 seconds, including stale/overlapping runs, identity and merge proof, attachment failures, deployment failures, guarded cleanup and pushed-revision checks. Log: `/tmp/he-ship-final-focused-20260911.log`. |
| Native Git and agent journeys | Disposable linked worktrees and real bare Git remotes under `/tmp/he-ship-sandboxes-20260910`; native Codex actors used installed skills/hooks. Readiness passed; stale CI, unknown provider state and queued newer CI were rejected. Interrupted merge recovery inspected the already-merged result and did not merge twice. Failed deployment blocked cleanup, and recovery subsequently completed cleanup. Actor logs and receipts are under `evidence/actors`. |
| Real UI and runtime | `/tmp/he-ship-ui-20260911`: Chromium captured and visually inspected matching before/after states for a weekly-task interaction. A real task push passed; a direct base push was rejected with the receiver unchanged. Missing PR attachments failed. A native actor rejected HTTP 200 reporting the old deployed revision, then a fresh actor accepted the actual merged revision and cleaned the task. The served copied artifact and interaction remained valid after cleanup. Screenshots and actor receipts are in `evidence/`. |
| Trigger boundary | A native explanatory actor answered a question about runtime-verifier scope without issuing shipping/provider actions (`/tmp/he-ship-ui-20260911/evidence/explain-actor.jsonl`). |
| New PR and authority boundary | A fresh non-UI sandbox began with no PR; the native actor created exactly one scoped PR and passed Ready at `8faf3e2621ff02d7033d80c5da0c4c5edc34d9b5`. No merge or delivery action followed its PR-only request. Receipt: `/tmp/he-ship-sandboxes-20260910/evidence/actors/create-pr-create.codex.jsonl`. |
| Fresh final cleanup | With the current source, PR #109 passed Ready and merge at `b29f1e6e7bb31fc1679dde0a8a7ed81399d4a9c4`. A fresh native actor completed cleanup on its first attempt, removing only `feature/ship-cleanup-current` and its worktree while preserving the coordinator/main and its existing cache. No cache-removal retry was needed. Receipt: `/tmp/he-ship-sandboxes-20260910/evidence/actors/cleanup-current-cleanup.codex.jsonl`. |
| Review regressions | Independent review exposed overlapping-run selection, mutable remote endpoints and ignored submodule state. Fixes have focused regressions; same-plan completion was proven in the native cleanup journey. The last review found a second configured push URL was overlooked. `/tmp/he-ship-multiple-push-red.log` reproduces destructive acceptance before repair; the final regression verifies both remotes and the task are preserved. Cleanup now reads all push URLs and requires exactly the captured endpoint. |
| Integrated source | `uv run python .hooks/hard-eng.py check --plan-stage Ready` passed all 17 gates in 46.38 seconds: 369 tests (37.32 seconds), four performance tests, 83.67% line coverage, zero type diagnostics and no reported security/dependency findings. Log: `/tmp/he-ship-integrated-20260911.log`. |
| Final Complete gate | `uv run python .hooks/hard-eng.py check --plan-stage Complete` passed all 17 gates in 44.32 seconds after the multiple-push-URL correction: 370 tests (36.71 seconds), four performance tests (1.50 seconds), 83.67% line coverage. Log: `/tmp/he-ship-final-complete-2-20260911.log`. Source HEAD remains `dd394b89b377b8077a87289b6e611995272ff558`; no source commit or push was performed. |
| Skill package and installation | Native skill metadata validation passed for HE, HE Plan, HE Build and HE Ship; all 46 inspected relative links resolved. Fresh sandbox installations loaded the shipping package and hooks, and installer inclusion/regressions pass in the integrated suite. |

Observed failures were retained and corrected, rather than counted as successful proof: the sandbox adapter initially supplied invalid timing and runtime metadata; a cleanup hook recreated Python bytecode; cleanup also needed to remove its unchanged remote-tracking ref. Fixture corrections were separated from production fixes and the affected journeys were rerun.

An extra broad `ruff .` invocation also scanned separately owned canonical skill-source packages and reported existing lint/format findings there. No such files were changed. The configured source scope (`setup.py`, `.hooks`, `tests`) passes lint and format; the final gate uses that existing declared scope.

Limits: GitHub PR/check/attachment responses and server merge coordination were simulated, while Git transport, native hooks/agents, browser interaction and HTTP revision checks were real. These runs do not prove hosted GitHub upload/CI/merge/deployment integration. The initial provider supports same-origin GitHub PRs; fork PRs, differing push endpoints and initialized submodules require repository-owned handling. Runtime verifiers remain trusted project code, and active-task ownership/visual relevance require agent judgment. Local hooks do not replace server protection. Temporary sandbox evidence is local and has not been published.

Delivery target: Merge
Delivery: Pending — source PR/main checks and guarded cleanup remain. Earlier delivery restrictions and results above describe the original implementation run.

The owned temporary HTTP server was stopped after verification; its source, captures and receipts remain available in the sandbox.
