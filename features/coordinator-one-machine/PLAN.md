# Coordinator runs on any one machine, never two

Status: Draft

## Outcome + scope

The trello-coordinator can start on any machine with the repository and its Trello key, but only one machine runs it at a time: a claim on the repository's `origin` names the machine, a second machine's `check` is skipped and its write commands are refused, and the coordinator's memory (posted-comment log, `handover.md`, worker notes, `state.json`) travels with the claim when `origin` is private. Non-goals: moving worker worktrees, threads or timers between machines; any automatic takeover; non-git stores.

## Repository context

Owners: `.agents/skills/trello-coordinator/scripts/trello_board/state.py` (run lease, posted log), `commands.py` (`guarded`, `check`, `finish`, write commands), `secrets.py` (`Place`, `git`); text in `SKILL.md:10`, `references/commands.md` (Secrets + state, command rows), `references/hosts.md`; tests in `tests/test_trello_board.py`, `tests/test_trello_coordinator.py`, fixture `tests/trello_fixtures.py`.
Bug evidence: `commands.md` says "shared by worktrees on one machine. One machine runs the coordinator". `state.take_lease` locks a file in the git common dir, so two clones of one repository each take a lease and both write to the board. A Trello card cannot hold the claim: the API has no all-or-nothing write.
Same cause: N/A — first cross-machine rule; the same-machine lease stays and keeps its tests.
Single source: the claim ref name, the memory file set and the take/save/release rules live in one new module `claim.py`; `commands.py` calls it; `commands.md` describes it once in Secrets + state. Searched the skill folder and `tests/` for `lease`, `one machine` and `posted.log`: the only other text is `SKILL.md:10`, reworded here.

## Decisions + authorization

Blockers: the Hard Eng pre-push hook runs the full check on every pushed revision (`.hooks/ship_actions.py::pre_push`). A claim commit holds no `.hooks/hard-eng.py`, so the hook cannot check it and the push fails. Pending the maintainer's choice: push the claim with `--no-verify` (claim pushes only; the claim code refuses any file that holds the key, the token or a key-like value), or a hook exemption for the claim ref.
Handoff: Clarification
Authority: the maintainer asked on 2026-11-10 that the coordinator run on any one machine or server, never two at once, and approved keeping the coordinator's rules and memory in the private repository ("yes"). This plan is that change, landed before the consumer's read-only trial.
Decision: the claim is a parentless commit on `refs/trello-coordinator/claim` at `origin`, taken with `git push --force-with-lease=<ref>:<expected>`, which git applies all or nothing (local test 2026-11-10: two pushers at once, one winner in 5 of 5 rounds). It is not a branch, so it starts no workflow.
Decision: no silent takeover and no `release`. A quiet board can sleep for `chaseHours`, so any expiry could hand a live board to a second machine, and a released claim would go back to the old machine's own timer. `check` takes only an absent claim; after that only `takeover`, run on the user's order on the new machine, changes the holder.
Decision: a `check` skipped because another machine holds the claim prints `heldElsewhere: true`; that coordinator deletes this host's `timer` and `wake` and tells the user once. So the old machine stops itself after a takeover.
Decision: the memory goes into the claim commit only when `gh repo view --json visibility` says `PRIVATE`; any other answer or error means the commit holds the holder line only and the memory stays on the machine. A claim commit with no memory leaves the local memory untouched.
Decision: every write command compares `origin`'s claim with this machine's last claim commit (one `ls-remote`) and refuses on a mismatch; `check` and `finish` read and push the remote ref.
Decision: claim commits use a fixed author and committer, never the user's identity. Every network git call has a time limit and `GIT_TERMINAL_PROMPT=0`.

## Acceptance + steps

- [ ] Two clones of one remote: the first `check` takes the claim; the second prints `skipped` and its `comment` is refused → `tests/test_trello_coordinator.py::test_a_second_machine_is_skipped_and_cannot_write` (fails on `develop`: both clones run).
- [ ] Two machines take an absent claim at once → exactly one wins → `tests/test_trello_board.py::test_one_machine_wins_an_open_claim`.
- [ ] `takeover` on the user's order: the new machine holds the claim and gets the old machine's posted log and `handover.md` when `origin` is private; the old machine's `finish` reports the lost claim, its `check` prints `heldElsewhere` and its writes are refused → `tests/test_trello_coordinator.py::test_takeover_moves_the_claim_and_memory`.
- [ ] A repository that is not private gets the holder line only; a takeover there leaves local memory untouched → `tests/test_trello_coordinator.py::test_a_public_remote_gets_no_memory`.
- [ ] A memory file that holds the Trello key, the token or a key-like value stops `finish` before any push → `tests/test_trello_coordinator.py::test_memory_with_a_key_is_never_pushed`.
- [ ] Claim commits carry the fixed identity, not the repository's → asserted in `test_a_second_machine_is_skipped_and_cannot_write`.
- [ ] Reference rows match the commands → `tests/test_trello_coordinator.py::test_cli_matches_the_reference_contract`.
- [x] Real GitHub, private repository, 2026-11-10 07:45Z: two pushers at once with `--force-with-lease=<ref>:` on a scratch ref, 3 rounds, one winner each; the loser got "cannot lock ref … reference already exists"; no workflow run after 07:45Z (`gh run list`); the scratch ref was deleted (`ls-remote` empty). Pushed from a repository with no hooks.

## Baseline + execution

Result: Passed
Evidence: `python3 .hooks/hard-eng.py check --plan-stage Draft --base origin/develop` on `develop` 4b864c19 with only this plan added, 2026-11-10 07:41Z: secret scan passed, exit 0.
Execution: this session plans; one builder implements the tests first, then `claim.py` and the command wiring; a Reader pass on the changed reference text; the maintainer's Hard Eng gates before push.

## Risks + recovery

- A machine dies while holding the claim: the board stops until the user orders `takeover` on another machine. Recovery: `takeover`; the memory is the dead machine's last `finish`, so comments posted after it can look like the owner's. The coordinator reads those cards before it answers.
- `origin` cannot be reached: `check` reports an error and the run ends; Trello writes need the claim, so nothing posts. Recovery: the next run after the network returns.
- The repository becomes public later: the claim ref is readable by anyone. Recovery: the next `finish` stops sending memory; the maintainer deletes the ref's old commits by pushing a new one.

## ux_reference

N/A — no app screens; coordinator script and reference text only.

## Verification

Result: Pending
Evidence: Pending
E2E: N/A — the script has no user journey; the tests run the real `check`, `finish`, `release` and `takeover` commands against real git remotes and the fake board.
Retro: Pending

Delivery target: Merge
Delivery: Pending — PR into `develop` with `hard-eng` and `canary` green, then release.
