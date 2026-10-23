# A broken npm tool install is repaired or named

Status: Complete

## Outcome + scope

Issue 390: Biome 2.6.0 and 2.6.1 were published with no platform binary packages; 2.6.2 fixed it 40 minutes later. The two-day release age limit picked 2.6.1, so the install had no native binary. Every Biome gate then failed in about 1 s with a module-not-found error that looked like a code fault. After provisioning, run each installed npm tool with `--version`. A tool that fails gets uninstalled and reinstalled once at the newest release, with no age limit. If it still fails, the stage stops with `tool install broken: <tool> <version> missing <package>`. A quick check that finds a broken installed tool repairs it the same way. Non-goals: aqua tools, which install one checked binary; picking an older release.

## Repository context

Owner: `.hooks/tool_setup.py` `provision_latest` and `use_installed_tools`.
Test: `tests/test_tool_setup.py` uses a fake mise whose age-limited release is broken.
Same cause: closed issue 286 suspected the age override; the registry shows the platform packages for 2.6.0 and 2.6.1 do not exist, so no age setting could install them.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: Autonomous. The user approved the push, the PR, the merge and the remaining decisions.

## Acceptance + steps

- [x] An age-limited release without its platform binary is replaced by the newest release → `tests/test_tool_setup.py::test_a_release_without_its_platform_binary_is_replaced_by_the_newest`.
- [x] A tool still broken after the reinstall stops the stage and names the missing package → `tests/test_tool_setup.py::test_a_tool_still_broken_after_reinstall_names_what_is_missing`.
- [x] A quick check repairs a broken installed tool → `tests/test_tool_setup.py::test_quick_check_repairs_a_broken_installed_tool`.

## Baseline + execution

Result: Passed
Evidence: develop `6a02cfb` is the base.
Execution: One builder.

## Risks + recovery

The probe adds about 1 s per check when many npm tools are selected; the probes run in parallel. Until the fixed release is older than two days, each full check reinstalls it once. Recovery is reverting this branch.

## ux_reference

N/A — tool provisioning; no product appearance.

## Verification

Result: Passed
Evidence: The three new tests failed before the fix and pass after it. With real mise and Bun, a forced Biome 2.6.1 install printed `tool install broken: biome 2.6.1 missing @biomejs/cli-linux-x64/biome`, then was replaced by 2.6.2, which runs. A forced broken retry stopped with the same message for 2.6.0.
All other local gates pass. The full suite has 6 Dart and Swift failures that also fail on develop, because the cloud sandbox lacks Dart and Swift.
E2E: Passed — real mise and Bun installed the broken release.
Independent review not done: Codex is not installed in the cloud sandbox, so `challenge` cannot run.

Delivery target: Merge
Delivery: Pending — PR checks into develop.
