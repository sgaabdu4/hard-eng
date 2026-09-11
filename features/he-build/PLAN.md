# Implement the build loop and ready-for-ship handoff

Status: Complete

## Outcome + scope

Add a compact he-build skill that consumes a Ready + authorized plan, coordinates implementation and verification, integrates independent work, and ends with an explicit Ready for ship handoff in the same plan. Reuse existing testing, research, review, E2E and Complete gate owners. Ship execution is separate and will be designed later. No new gate framework, BUILD.md, state schema, mandatory mutation/CRAP, fixed agent chain or automatic commits.

## Repository context

HE currently routes implementation through references/workflow.md. HE Plan owns readiness and authorization; .hooks/plans.py checks completion declarations and .hooks/hard-eng.py runs configured checks. E2E owns runtime proof and defect reopening; Research owns diagnosis; Code Review owns actual-diff review. The skill installer discovers packages from .agents/skills. The completed e2e-walkthrough plan and root planning work are separate efforts and remain intact.

## Decisions + authorization

Blockers: None

The user approved the proposed build loop, existing-gate enforcement, same-plan completion and Ready for ship boundary, then explicitly requested implementation and sandbox testing. Continue under the existing autonomous rebuild authorization. One source builder; sandbox actors may exercise the approved parallel-work scenario in disposable repositories. No source commit, push, global installation or other-project changes. Build completion is not permission to ship.

## Acceptance + steps

- [x] Add one concise he-build entrypoint; route implementation from HE and preserve conditional owners and invocation behavior.
- [x] Build consumes the Ready plan, preserves progress, verifies complete behaviors and coordinates independent work with explicit ownership/dependencies and combined verification.
- [x] Reuse Complete-stage enforcement; incomplete criteria, failing tests and failed integration cannot yield Ready for ship. Blockers stay explicit and do not erase completed work.
- [x] Record Ready for ship in the existing plan only after actual local build proof and the final gate; no delivery action or second state file is introduced.
- [x] Exercise disposable bug/fix, independent parallel work, failed integration/recovery and unavailable-prerequisite cases, including actual native agent behavior and gate failures.
- [x] Validate metadata, routes, installer discovery, actual diff and native source checks; report behavioral and host limits honestly.
- [x] Expanded sandbox follow-up: native actors exercise missing readiness, unresolved scope, partial resume, false completion evidence, shared-resource contention, misleading worker handoff, post-pass changes and unavailable final checks; assert observed behavior and preserve failures.
- [x] Expanded E2E follow-up: verify a real local web journey and durable readback/restart behavior; test planning/review/shipping-only and unavailable-runtime boundaries; repair only observed skill gaps and rerun original plus adjacent cases.
- [x] Repair the observed invalid-Ready entry gap: check readiness evidence instead of trusting the label, preserve the starting baseline outcome, and rerun the frozen invalid input plus valid nearby shared-writer and authorized-Exception continuations.

## Baseline + execution

Result: Passed
Evidence: Fresh `uv run python .hooks/hard-eng.py check --plan-stage Draft` exited 0 before skill implementation; all 17 native gates passed. Log: `/tmp/he-build-baseline-20260910.log`.

One builder updates the skill and HE routing. Reuse existing plan tests and disposable Python fixtures with the actual runner. Native actors use the existing agent runtime; no new persistent test harness or project dependency is needed. Parallel sandbox workers have separate owners and no source-repository write authority.

Expanded guard-repair baseline: before changing the two HE Build bullets, `uv run python .hooks/hard-eng.py check --plan-stage Ready` exited 0 with all 17 gates, 310 tests and 4 performance tests passing. Evidence: `/tmp/he-build-edgecases-20260910/e2e/evidence/source-before-guard-ready.log`.

## Risks + recovery

Declarations cannot prove truthful evidence. Test real CLI failures and actor outcomes rather than matching wording alone. Shared resources can conflict even with disjoint source files; integration must inspect actual changes and effects. Preserve unrelated source work and limit any correction to the failing owner. If a native capability is unavailable, report that boundary instead of substituting a simulated agent result.

## ux_reference

N/A — this is agent guidance and existing CLI gate routing; no product UI changes.

## Verification

Result: Passed
Evidence: Initial sandbox receipts are under `/tmp/he-build-sandboxes-20260910/evidence/`. The previous integrated source passed `uv run python .hooks/hard-eng.py check --plan-stage Complete`: all 17 gates, including 310 tests and the separate 4-test performance suite (`source-complete.log`). Expanded testing covers the 16 scenarios below under `/tmp/he-build-edgecases-20260910/`, including fresh native reruns of invalid readiness, valid shared-writer readiness and authorized baseline Exception after the two-bullet skill repair. Final integrated source gate receipt follows below.

- Native bug actor reproduced CLI `2 3 -> -1`, added function/CLI regressions that failed, fixed the inventory owner, preserved positive/equal cases, and passed all 4 tests plus Complete. Independent parent Complete rerun exited 0 (`bug-parent-complete.log`); actual actor receipt: `bug-final.md`, execution: `bug-events.jsonl`.
- Native blocked actor verified local payload preparation but kept the plan Draft, Verification Pending and required delivery unchecked when the real destination resolver failed. It recorded the exact prerequisite and authorized resume boundary without inventing transport/readback proof. Parent Complete rejection exited 1 (`blocked-parent-complete.log`); actor receipt: `blocked-final.md`.
- A disposable copy rejected an unchecked criterion (`negative-unchecked.log`, exit 1), then rejected the deliberately restored inventory defect with two real regression failures (`negative-regression.log`, exit 1). Restoring the owner passed Complete (`negative-restored.log`, exit 0).
- Two actual workers overlapped: exporter `19:03:22–19:04:30 UTC`, formatter `19:03:23–19:05:28 UTC`, on 2026-09-10. They changed only their named module/test owners. Parent independently reran 2 exporter and 3 formatter tests successfully; the real combined CLI regression still failed with `KeyError: 'total'` (`parallel-integration-before.log`). A fresh native coordinator independently reproduced that failure, fixed only the receipt consumer, preserved worker tests and the integration regression, and passed all 6 tests plus Complete. Parent reran Complete successfully (`parallel-parent-complete.log`) and the real CLI printed `USD $1.25`. Receipt: `parallel-final.md`; execution: `parallel-events.jsonl`.
- Native explanation-only actor read HE/workflow and the inventory owner, answered the calculation, and did not load HE Build, run gates or alter fixture files. Content hashes match the starting copy; receipt: `explanation-final.md`, execution: `explanation-events.jsonl`.
- Existing installer and plan regression checks passed: `uv run pytest tests/test_setup.py::test_install_preserves_project_and_repeats tests/test_plans.py -q`, 24 passed (`installer-plan-tests.log`). The installer check now verifies he-build package bytes and the installed Claude skill link using the existing test.
- Native skill metadata validation passes for he-build and HE. All 10 he-build relative links resolve, including the existing Plan checks anchor. Actual source diff review found no additional runtime machinery, metadata, dependency, gate relaxation or shipping action.

Limits: These are controlled Python fixture contracts using copied native HE gates and real Codex actors, not production stack coverage. The unavailable-destination case proves honest blocking, not remote delivery. Claude package linking is tested by the installer; Claude/Copilot runtime invocation is not tested. No source commit, push, global installation or other-project change is part of this work.

### Expanded sandbox verification — 2026-09-10

The user explicitly requested parallel subagents and broader edge cases. Two subagents own isolated readiness and coordination suites; the coordinator owns browser/runtime and non-trigger cases. These are finite scenarios derived from the skill's rules, not a claim to every possible application defect. Fixtures, native actor execution logs and receipts are under `/tmp/he-build-edgecases-20260910/`.

| Case | Actual outcome |
| --- | --- |
| Invalid Ready label | Initial shared-writer trial exposed a separate entry failure: Status Ready concealed pending baseline/no evidence and non-final blocker declarations; the actor implemented and rewrote the failed starting baseline as Passed. Original failure remains in `integration/case1-shared-writer/evidence/native-actor.log`. With updated HE Build and the full installed planning routes, the frozen invalid input was repaired through planning; Ready passed at event 41 before the regression was added at 42 and production edit at 46. The real regression failed before the fix; five tests, Complete and exact persisted readback then passed. Failed starting checks and clean-state race evidence remain in the plan. `readiness/invalid-ready/evidence/full-routes-events.jsonl` + `full-routes-final.md`. An earlier replay omitted planning dependencies and is retained but excluded from acceptance. |
| Missing plan | Native actor created the sole plan and passed Ready before test/code edits, then reproduced and fixed the inventory defect. Four tests, CLI and Complete passed. Parent verified readiness-before-edit chronology in the actual event stream. `readiness/RESULTS.md` + `readiness/evidence/missing-events.jsonl`. |
| Draft plan | Native actor corrected plan declarations and passed Ready before implementation, then reproduced/fixed the defect and passed Complete. Parent verified readiness-before-edit chronology in the event stream. `readiness/evidence/draft-events.jsonl`. |
| Unresolved scope decision | Actor changed only the plan to Draft, preserved accepted code/tests/completed work and recorded the reject-versus-clamp user choice with resume conditions. Existing runtime and Draft checks passed. `readiness/evidence/scope-final.md`. |
| Partial Ready resume | Actor preserved an untracked working note byte-for-byte, added real function/CLI regressions, fixed the shared owner and passed Complete. Parent independently matched the preserved note hash. `readiness/evidence/resume-final.md`. |
| Forged Complete evidence | Real suite and Complete initially failed despite checked boxes and stale claims. Actor returned to Draft, fixed the owner and passed current CLI/tests/Complete while retaining the authorized starting-baseline Exception and its failed-state evidence. `readiness/evidence/forged-final.md` + `independent-forged-gate.log`. |
| Shared-writer contention | With the updated skill and a valid seven-test Ready baseline, the real coordinator exited 0 but lost the exporter record. A fresh actor added a failing subprocess/persisted-JSON regression and serialized the conflicting writes. Independent verification passed eight tests, Complete and exact readback of both records plus the original sentinel. Worker modules, focused tests and gate configuration remained byte-identical. `integration/case1-shared-writer/evidence/independent-skill-rerun-final.log`. |
| Misleading/incomplete worker handoff | Focused worker passes concealed a real CLI integration failure and a missing required catalogue handoff. Actor repaired the receipt owner and passed six tests/runtime, but kept Draft while the handoff/verifier remained unavailable. `integration/case2-worker-handoff/evidence/independent-final.log`. |
| Source changed after Complete | A later broken field lookup invalidated the preserved earlier pass. Actor reproduced current failure, repaired the consumer and reran actual CLI/tests/Complete; six tests passed and the CLI printed `USD $1.25`. Historical receipts remained intact. `integration/case3-stale-complete/evidence/independent-final.log`. |
| Final verifier unavailable | Five focused and six integrated tests plus CLI passed, but the native Complete gate failed on its configured missing verifier. Actor retained the gate configuration and moved to Draft/Blocked. `integration/case4-final-gate/evidence/independent-final.log`. |
| Valid authorized baseline Exception | With the updated skill, a current Ready check passed while retaining the actual historical baseline Exception. Actor completed the remaining CLI validation, passed six tests and Complete, and preserved the entire baseline section byte-for-byte. Parent independently reran Complete. `e2e/evidence/exception-resume-events.jsonl` + `exception-resume-parent-complete.log`. |
| Planning-only request | Native actor updated only PLAN.md, preserved implementation/tests byte-for-byte, passed Draft and Ready and stopped with implementation verification Pending. No HE Build load. `e2e/evidence/planning-final.md` + `planning-events.jsonl`. |
| Review-only request | Native actor used review routes, ran the four existing regressions, reported no findings and changed no files. No HE Build load. `e2e/evidence/review-final.md` + `review-events.jsonl`. |
| Shipping assessment only | Native actor identified the absent remote/delivery target and reported needed inputs. No build invocation, file change or publication. `e2e/evidence/shipping-final.md` + `shipping-events.jsonl`. |
| Browser persistence and recovery | Native actor reproduced a real Chromium save followed by lost data after restart, fixed the server owner and passed browser/durable-state regressions. Parent independently passed Complete. Tests cover trimmed JSON, reload, independent browser context, server restart, blank browser/API rejection, read-only denial, unavailable storage, actual filesystem replacement failure, cleanup, retry and durable recovery. Success/error screenshots were inspected. `e2e/evidence/web-events.jsonl`, `web-parent-complete.log`, `e2e/web-persistence/web-after.png` and `web-after-error.png`. |
| Required browser unavailable | Native actor preserved the selected missing executable, completed independent API proof and kept Draft/Pending with an exact resume condition. Parent browser run and Complete check each exited 1. A tool invocation dropped the selected-runtime environment and used default Chromium; the actor detected and explicitly excluded that pass instead of treating it as acceptance. `e2e/evidence/browser-unavailable-events.jsonl`, `browser-unavailable-parent-browser.log` and `browser-unavailable-parent-complete.log`. |

Cross-review: a separate subagent inspected the actual browser tests, server changes, event receipts and both screenshots, plus the unavailable-browser evidence. It found no confirmed false pass or missing required proof. Failed-save assertions preserve the accepted API/disk value while the form retains the unsaved draft for retry; UI rollback was not an accepted requirement.

All 16 expanded scenarios have observed outcomes, including expected blocks where required proof is unavailable. This does not establish physical-device or Claude/Copilot runtime coverage, or exhaustive coverage of every future application. No delivery has occurred.

Final integrated source verification: `uv run python .hooks/hard-eng.py check --plan-stage Complete` exited 0 after the skill repair and expanded acceptance reconciliation. All 17 gates passed, including 310 tests and the separate 4-test performance suite. Receipt: `/tmp/he-build-edgecases-20260910/e2e/evidence/source-final-complete.log`. Final source review found only the compact skill, HE routing, the existing installer-test extension and this evidence plan for the build work; no new runtime machinery, dependency or gate relaxation was introduced.

Ready for ship — local implementation and verification complete; delivery not performed.
