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
Decisions: The folder key is a hash of the checkout root that `hard-eng.py` already uses (`.hooks` parent, resolved). A pre-push snapshot uses its owning checkout's folder, so pushes do not reinstall tools; the `node` shim sits in a folder named by its content hash, so two revisions in one checkout never share one shim file. Folders of deleted checkouts are removed unless a running check holds their lock. When the temporary folder has a hidden segment, tool folders and push snapshots use `/tmp` instead, because Biome skips its React rules below a hidden folder. Only the Bun install cache stays shared: Bun stores packages by name, version and integrity and moves finished entries into place, and its installs clone from it, so per-checkout tools cost little disk. The new folders sit under `hard-eng-tools/checkouts/`, which older revisions never read or prune.

## Acceptance + steps

- [x] Two checkouts on different revisions provisioning at once get separate shims, keep their own content, install their own launcher and never use the old shared shim or launcher → `test_checkouts_on_different_revisions_keep_their_own_shims`, red before.
- [x] A reader never sees a partly written file while it is rewritten → `test_a_running_check_never_reads_a_partly_written_file`, red with a direct write.
- [x] A push snapshot reuses its owner's tool folder; another checkout does not → `test_push_snapshots_reuse_their_checkout_tools`.
- [x] Deleted checkouts lose their tool folders unless a check holds them → `test_deleted_checkouts_lose_their_tools_unless_a_check_holds_them`.
- [x] A check skips a stale folder another check removed first → `test_a_check_skips_a_stale_folder_another_check_just_removed`, red before.
- [x] A hidden temporary folder never holds push snapshots or tool folders → `test_push_copies_and_tools_stay_out_of_a_hidden_temporary_folder`, red before.
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
Evidence: The checkout test failed on the old code (one shared shim path for both checkouts and the old folder) and passes now. The atomic-write test failed with a direct write and passes now. The hidden-folder test failed when the snapshot used the hidden folder. All 28 tool setup tests pass. Codex round 1 found that push snapshots got a new folder on every push; fixed with the owner key and pruning. Round 2 found that two checks pruning one stale folder could crash the second; fixed and tested. Round 3 raised only the older `node -r` shim handling, outside this change. The full check passed on the rebased branch (1712 tests).
E2E: Passed — real subprocess provisioning from two copied checkouts with a fake registry.

Delivery target: Merge
Delivery: Pending — PR CI, merge.
