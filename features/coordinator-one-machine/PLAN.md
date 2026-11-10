# Coordinator runs on any one machine, never two

Status: Complete

## Outcome + scope

The trello-coordinator can start on any machine with the repository and its Trello key, but only one machine runs it at a time: a claim on the repository's `origin` names the machine, a second machine's `check` is skipped and its write commands are refused, and the coordinator's memory (posted-comment log, `handover.md`, worker notes, `state.json`) travels with the claim when `origin` is private. Non-goals: moving worker worktrees, threads or timers between machines; any automatic takeover; non-git stores.

## Repository context

Owners: `.agents/skills/trello-coordinator/scripts/trello_board/state.py` (run lease, posted log), `commands.py` (`guarded`, `check`, `finish`, write commands), `secrets.py` (`Place`, `git`); text in `SKILL.md:10`, `references/commands.md` (Secrets + state, command rows), `references/hosts.md`; tests in `tests/test_trello_board.py`, `tests/test_trello_coordinator.py`, fixture `tests/trello_fixtures.py`.
Bug evidence: `commands.md` says "shared by worktrees on one machine. One machine runs the coordinator". `state.take_lease` locks a file in the git common dir, so two clones of one repository each take a lease and both write to the board. A Trello card cannot hold the claim: the API has no all-or-nothing write.
Same cause: N/A — first cross-machine rule; the same-machine lease stays and keeps its tests.
Single source: the claim ref name, the memory file set and the take, save and takeover rules live in one new module `claim.py`; `commands.py` calls it; `commands.md` describes it once in Secrets + state. Searched the skill folder and `tests/` for `lease`, `one machine` and `posted.log`: the only other text is `SKILL.md:10`, reworded here.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: the maintainer asked on 2026-11-10 that the coordinator run on any one machine or server, never two at once, and approved keeping the coordinator's rules and memory in the private repository ("yes"). This plan is that change, landed before the consumer's read-only trial.
Decision: the claim is a parentless commit on `refs/trello-coordinator/claim` at `origin`, taken with `git push --force-with-lease=<ref>:<expected>`, which git applies all or nothing (local test 2026-11-10: two pushers at once, one winner in 5 of 5 rounds). It is not a branch, so it starts no workflow.
Decision: no silent takeover and no `release`. A quiet board can sleep for `chaseHours`, so any expiry could hand a live board to a second machine, and a released claim would go back to the old machine's own timer. `check` takes only an absent claim; after that only `takeover`, run on the user's order on the new machine, changes the holder.
Decision: a `check` skipped because another machine holds the claim prints `heldElsewhere: true`; that coordinator deletes this host's `timer` and `wake` and tells the user once. So the old machine stops itself after a takeover.
Decision: the memory goes into the claim commit only when `gh repo view --json visibility` says `PRIVATE`; any other answer or error means the commit holds the holder line only and the memory stays on the machine. A claim commit with no memory leaves the local memory untouched.
Decision: every write command compares `origin`'s claim with this machine's last claim commit (one `ls-remote`) and refuses on a mismatch; `check` and `finish` read and push the remote ref.
Decision: claim pushes use `git push --no-verify`, and no other push does; the maintainer said yes on 2026-11-10. The Hard Eng pre-push hook runs the full check on a snapshot of each pushed revision (`.hooks/ship_actions.py::pre_push`), and a claim commit holds no `.hooks/hard-eng.py`, so the hook cannot check it. Instead the claim code refuses any memory file that holds the loaded key or token, before it builds the commit. It does not use `config.SECRET`: that pattern matches any 32 hex characters, so a full commit hash in a worker note (one consumer's notes already hold one) would stop every `finish`.
Decision: claim commits use a fixed author and committer, never the user's identity. Every network git call has a time limit and `GIT_TERMINAL_PROMPT=0`.

## Acceptance + steps

- [x] Two clones of one remote: the first `check` takes the claim; the second prints `skipped` and its `comment` is refused → `tests/test_trello_coordinator.py::test_a_second_machine_is_skipped_and_cannot_write` (fails on `develop`: both clones run).
- [x] Two machines take an absent claim at once → exactly one wins → `tests/test_trello_board.py::test_one_machine_wins_an_open_claim`.
- [x] `takeover` on the user's order: the new machine holds the claim and gets the old machine's posted log and `handover.md` when `origin` is private; the old machine's `finish` reports the lost claim, its `check` prints `heldElsewhere` and its writes are refused → `tests/test_trello_coordinator.py::test_takeover_moves_the_claim_and_memory`.
- [x] A repository that is not private gets the holder line only; a takeover there leaves local memory untouched → `tests/test_trello_coordinator.py::test_a_public_remote_gets_no_memory`.
- [x] A memory file that holds the Trello key or token stops `finish` before any push; a full commit hash still travels → `tests/test_trello_coordinator.py::test_memory_with_a_key_is_never_pushed`.
- [x] Claim commits carry the fixed identity, not the repository's → `tests/test_trello_coordinator.py::test_a_second_machine_is_skipped_and_cannot_write`.
- [x] A `--dry-run` write works on a machine without the claim and sends nothing → `tests/test_trello_coordinator.py::test_a_second_machine_is_skipped_and_cannot_write`.
- [x] A failed private check never replaces the saved memory with a holder-only claim → `tests/test_trello_coordinator.py::test_a_failed_private_check_keeps_the_saved_memory`.
- [x] `takeover` prints when the old machine last saved, so the new one knows which cards to read again → `tests/test_trello_coordinator.py::test_takeover_moves_the_claim_and_memory`.
- [x] Reference rows match the commands → `tests/test_trello_coordinator.py::test_cli_matches_the_reference_contract`.
- [x] GitHub gives one winner and starts no workflow → N/A — tests cannot push to a real private repository; one-time proof on 2026-11-10 07:45Z: two pushers at once with `--force-with-lease=<ref>:` on a scratch ref, 3 rounds, one winner each; the loser got "cannot lock ref … reference already exists"; no workflow run after 07:45Z (`gh run list`); the scratch ref was deleted (`ls-remote` empty). Pushed from a repository with no hooks.
- [x] The real claim code on GitHub, with a pre-push hook that always fails → N/A — tests cannot reach a real private repository; one-time proof on 2026-11-10 12:40Z from two fresh repositories with that private `origin`, through a script that called `claim.py` directly: `is_private` True; A took the claim; B's check printed `heldElsewhere` and B's write was refused; A's save pushed memory and a second save pushed nothing; B's `takeover` restored A's `handover.md` and `posted.log`; then A's write was refused, A's save said another machine holds the claim and A's check printed `heldElsewhere`. The hook never ran; no workflow run after 12:28Z; the claim ref was deleted after (`ls-remote` empty). Each network step took 0.4 to 4 seconds.

## Baseline + execution

Result: Passed
Evidence: `python3 .hooks/hard-eng.py check --plan-stage Draft --base origin/develop` on `develop` 4b864c19 with only this plan added, 2026-11-10 07:41Z: secret scan passed, exit 0.
Execution: this session plans; one builder implements the tests first, then `claim.py` and the command wiring; a Reader pass on the changed reference text; the maintainer's Hard Eng gates before push.

## Risks + recovery

- A machine dies while holding the claim: the board stops until the user orders `takeover` on another machine. Recovery: `takeover`; the memory is the dead machine's last `finish`, so comments posted after it can look like the owner's. The coordinator reads those cards before it answers.
- `origin` cannot be reached: `check` reports an error and the run ends; Trello writes need the claim, so nothing posts. Recovery: the next run after the network returns.
- The repository becomes public later: the claim ref is readable by anyone. Recovery: the next `finish` stops sending memory; the maintainer deletes the ref's old commits by pushing a new one.
- A copied checkout (backup restore, migration or rsync) carries the old machine's `machine` and `claim-record` files, so both copies pass the claim. Recovery: move by a fresh clone; on a restored copy, delete those two files from the state folder before its first run, then run `takeover`.

## ux_reference

N/A — no app screens; coordinator script and reference text only.

## Verification

Result: Passed
Evidence: On 2026-11-10 the new tests failed first on the unchanged code: 10 failed (no claim module, no claim at `origin`, an unreachable `origin` still passed, `takeover` missing). Review of the build found that `config.SECRET` refused any 32 hex characters, and one consumer's real worker note holds a full commit hash, so every `finish` would fail; the hash case failed first, then passed with a key-and-token-only check. Reader pass 1 found three code defects (a failed private check pushed a holder-only claim over saved memory; `--dry-run` needed the claim; nothing told the new machine which cards to read again) and ten text issues; the three code cases failed first, then passed. Reader pass 2 found three text-code mismatches and five unclear sentences, and no meaning changed by accident; `takeover` now prints `memoryRestored`, which failed first. After the fixes: `tests/test_trello_board.py`, `tests/test_trello_report.py`, `tests/test_trello_coordinator.py` 151 passed; ruff format and lint passed; pyrefly 0 diagnostics; `biome ci` on `.agents/skills` passed; `commands.md` is under 36,000 bytes. The two GitHub proofs are in Acceptance.
E2E: N/A — the script has no user journey; the tests run the real `check`, `finish`, `takeover` and write commands against real git remotes and the fake board.
Retro: these items, each sorted by HE Learn's Retro rows.
- The broad key pattern would have stopped every save on a real consumer → caught by review against real data; mechanical: the full-hash case in `tests/test_trello_coordinator.py::test_memory_with_a_key_is_never_pushed`. None new.
- Reader pass 1 found three code defects in a reference-only review → caught by the Reader rule, which compares text with code; each fixed with a failing test first. None new.
- The Ready check refused two Acceptance lines with no test reference, and the Stop hook's types gate refused an untyped lambda in a test → caught by the gates. None new.
- User correction: "why in this mac … no 2 computers should be running coordinator at the same time" → judgement: a Mac-only rules file was proposed although the coordinator must move between machines; saved as a lasting decision in the maintainer's notes. None new in Hard Eng.

Delivery target: Merge
Delivery: Pending — PR into `develop` with `hard-eng` and `canary` green, then release.
