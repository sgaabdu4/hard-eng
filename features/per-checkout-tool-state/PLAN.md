# Per-checkout tool state

Status: Complete

## Outcome + scope

Each local checkout keeps its own mutable tool files: the mise data, cache and state folders, the Bun `node` shim and the mise launcher. A check in one checkout can no longer run a shim or tool file that another checkout, on another Hard Eng revision, rewrote during the run. Generated files are replaced atomically.
Non-goals: CI keeps its one folder under `RUNNER_TEMP`, because a job has one checkout and workflows cache that path. No cleanup of the old shared folder; the system clears old temporary files.

## Repository context

Owner: [tool_setup.py](../../.hooks/tool_setup.py) `provision_batch`, `bun_node` and `mise_launcher`; `mutation.py` reaches the same code through `provision_batch`.
Evidence: Issue 314. Two checkouts on different revisions wrote different content to the shared `bun-node/node` during one check; a build then passed in 0.4 seconds without doing work, and a mise shim was reported as not valid.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: The owner asked for fully separate state per checkout, a Codex adversarial review loop, a PR merged by rebase and a rollout to every installed checkout.
Decisions: The folder key is a hash of the checkout root that `hard-eng.py` already uses (`.hooks` parent, resolved). Only the Bun install cache stays shared: Bun stores packages by name, version and integrity and moves finished entries into place, and its installs clone from it, so per-checkout tools cost little disk. The new folders sit under `hard-eng-tools/checkouts/`, which older revisions never read or prune.

## Acceptance + steps

- [x] Two checkouts on different revisions provisioning at once get separate shims, keep their own content, install their own launcher and never use the old shared shim or launcher → `test_checkouts_on_different_revisions_keep_their_own_shims`, red before.
- [x] A reader never sees a partly written shim while it is rewritten → `test_a_running_check_never_reads_a_partly_written_shim`, red with a direct write.
- [x] Full `python3 .hooks/hard-eng.py check` passes.

## Baseline + execution

Result: Passed
Evidence: The base commit passed required CI on main.
Execution: Red tests, fix, full check, Codex loop, PR, merge, rollout.

## Risks + recovery

Each checkout downloads its own non-npm tools once (about 250 MB plus a 170 MB mise cache). Recovery is reverting this branch.

## ux_reference

N/A — tool storage only; no product appearance.

## Verification

Result: Passed
Evidence: The checkout test failed on the old code (one shared shim path for both checkouts and the old folder) and passes now. The atomic-write test failed with a direct write and passes now. All 24 tool setup tests pass.
E2E: Passed — real subprocess provisioning from two copied checkouts with a fake registry.

Delivery target: Merge
Delivery: Pending — PR CI, merge.
