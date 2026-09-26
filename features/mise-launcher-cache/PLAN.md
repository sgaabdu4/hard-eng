# Install the mise launcher once per version

Status: Complete

## Outcome + scope

Gate provisioning keeps resolving the newest published mise on every check, but installs each version once into Hard Eng's tool directory, shares it safely between concurrent checks and removes superseded or interrupted installations that no check holds. Non-goals: the CI bootstrap launcher, gate commands' own `pnpm dlx` use, pinned versions, longer expiry and deleting existing caches.

## Repository context

Owners: `.hooks/tool_setup.py` `provision_batch` launched mise through `pnpm dlx --package=@jdxcode/mise@latest` with `PNPM_CONFIG_DLX_CACHE_MAX_AGE=0`. pnpm 12 then creates a fresh `pnpm/cache/dlx/<hash>/<id>` directory on every install call and never removes earlier ones; the package's preinstall copies a 112 MB platform binary into each. A local tool directory held 601 such copies (62 GB) on 26 September 2026 after being cleared the previous day. Consumers receive `.hooks/` through the verified updater (`.hooks/update.py`, `setup.sh`), so no template or generated copy exists.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: The user requested the investigation and a durable Hard Eng fix with regression coverage and repository checks; standing instruction: merge when green. Existing caches and consumer repositories stay untouched.

## Acceptance + steps

- [x] Unchanged latest version → repeated provisioning installs once and reuses it → `tests/test_tool_setup.py` counts one install across runs.
- [x] Concurrent provisioning of one version → a single install; every caller receives the verified launcher → concurrent test.
- [x] Newly published version → installed on the next check; superseded versions not in use are removed, in-use ones kept → retention test.
- [x] Failed, unverifiable or interrupted install → no version directory left, next run installs cleanly → failure tests.
- [x] Existing provisioning, CI directory and failure tests keep passing with the new launcher.
- [x] Real pnpm: two consecutive provisioning runs create one ~110 MB installation, not two → native measurement.

## Baseline + execution

Result: Passed
Evidence: `uv run --locked pytest -q tests/test_ci_setup.py tests/test_runner.py tests/test_tool_execution.py` → 171 passed on 897f84b. `pnpm add --dir <staging> --config.ignore-scripts=false --allow-build=@jdxcode/mise @jdxcode/mise@<version>` produced a 113 MB relocatable installation whose binary reported the requested version after the directory was renamed.
Execution: Single builder; one behavior in `tool_setup.py` plus its tests.

## Risks + recovery

A registry outage still fails provisioning, as before. Per-version lock files stay after pruning so a waiting check never locks a replaced file; they are empty. Existing `pnpm/cache/dlx` copies are left for a separate, user-run cleanup.

## ux_reference

N/A — CLI tool provisioning has no product UI.

## Verification

Result: Passed
Evidence: `tests/test_tool_setup.py` (6 tests) drives real provisioning processes against a fake registry: three unchanged runs install once; four concurrent runs install once and all succeed; 2026.9.12 and 2026.9.13 replace unheld launchers while a held 2026.9.11 survives until released, and unrelated `pnpm/cache/dlx` data stays; failed and unverifiable installs leave nothing and the next run succeeds; a SIGKILLed install's staging directory is removed by the next run. The 177 provisioning, CI setup, runner and tool execution tests pass. Real pnpm 12.6.0 in a scratch directory, three runs each: the old launcher grew the cache 114 → 221 → 329 MB; the new one kept one 113 MB installation (warm provisioning 3.4–3.7 s versus 5.2–5.4 s).
E2E: Passed — `hard-eng.py check --base origin/main --plan-stage Ready` provisioned its native tools through the new launcher and every gate passed.

Delivery target: Merge
Delivery: Pending — PR, required CI and main verification.
