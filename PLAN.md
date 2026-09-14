# Verify automatic update candidates before task completion

Status: Complete

## Outcome + scope

Allow automatic updates to verify changed project configuration before a task has completed, including when no task plan exists. Keep all application gates, transactional preservation and normal completion/shipping requirements.

## Repository context

The updater stages a detached candidate then invokes the normal check command, which infers Complete from non-Markdown changes. This requires completion evidence before the update can be applied. The existing runner owns both plan validation and native gates; separate those responsibilities only for the internal updater call.

## Decisions + authorization

Blockers: None

The user authorized auditing running tasks and correcting shared Hard Eng defects with strict YAGNI. One builder; touch the existing runner, updater, updater tests and README. No new file, dependency, persistent state or public bypass flag. Use synthetic fixtures in this public repository.

## Acceptance + steps

- [x] Candidate application gates run with Draft, Ready, Complete or absent task plans.
- [x] A failing application gate or missing remote base still rejects the update and preserves local files/index.
- [x] Normal check, completion and shipping plan requirements remain enforced.
- [x] The focused regression fails on the original boundary and passes after the correction.

## Baseline + execution

Result: Passed
Evidence: Matching source62aaa63 passed all17 gates,490 regressions,four performance tests, PR79 CI34843080857, main CI34843538127 and native delivered. Reuse this unchanged implementation baseline; validate the Ready plan before code edits and reproduce the candidate planning failure in the existing native fixture.

## Risks + recovery

Only the internal updater call omits task-plan validation; it cannot declare completion or ship. Application failures, managed conflicts, missing base and transaction rollback remain blockers. Host hook trust/activation remains separately unverified.

## ux_reference

N/A — candidate verification has no visual interface.

## Verification

Result: Passed
Evidence: The original native candidate failed with Draft requiring Complete before application execution. Native candidate tests now cover all plan states, actual passing/failing application commands, remote-base discovery and local index/file preservation without duplicating every failure across every plan state. Final Complete gate passed all17 gates,496 regressions and four performance tests. Review confirmed no CLI bypass flag, dependency or new file. Ready for ship — local verification complete; remote delivery remains pending.

Delivery target: Merge
Delivery: Pending — PR, exact main CI and native delivered proof remain required.
