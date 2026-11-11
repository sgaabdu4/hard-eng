# 0003 — The shared rules tell the agent that the codebase is its own

Status: Accepted
Applies to: `AGENTS.md`

## Context

Agents that followed the shared rules added new code beside old code. The rules said to fix causes at the existing owner and to make no optional improvement, so an agent left repeated code as it was and added one more copy. Published prompt guidance for coding agents reports that one ownership sentence makes an agent merge repeated code in about half of its tries, against under a tenth without it, at about 1.5 times the output.

## Decision

- `AGENTS.md` holds this sentence, word for word: "This codebase is yours: what it's for and how it's built are your call, and you'll keep building on it."
- The same line names the work that follows from it, in the code that the agent changes: fix faults at their cause, merge copies of that code, move code to its owner, one commit each.
- Optional improvements and extra infrastructure still need a request.
- A later edit that shortens `AGENTS.md` keeps the sentence and the three named actions. The file has a byte limit, so other text gives way first.

## Consequences

Each installed project gets the line with its next update. Agents make structural commits that nobody asked for in the code that a task changes, and they write more. The size rule still counts those lines, so a merge inside a small task can need a plan; the next round takes that.

The model check case `repeated-block` ran three texts on one hook code in each batch: the old text, the sentence alone, and the full line.

- Codex (`gpt-6.1-sol`) merged the repeated code in 0 of 10 runs with the old text, 0 of 10 with the sentence alone and 10 of 10 with the full line. The sentence alone changes nothing there; the named actions do.
- Haiku merged in 9, 9 and 8 of 10 runs when it wrote a plan, because the plan's `Single source:` line asks for the merge with each text.
- Haiku with a request for a quick change and no plan merged in 1 of 10 runs with the old text and 4 of 10 with the full line. Ten runs each do not prove that difference.
- Haiku made more commits with the full line: 2.3 for each run against 1.4. Codex showed no change.
- No run changed a file outside the task's files.
- Three guard cases (plan only, failed baseline, review only) showed no difference. The approved build case is inconclusive: the hot-path scan cannot run in the test sandbox, and a run that stops there fails. It passed in 7 of 9 runs with the old text and 4 of 9 with the full line; the last batch gave 3 of 5 for each.

## Evidence

Maintainer request, 11 November 2026. [Plan](../../features/audit-round-eight/PLAN.md), Decided (26), records the tests and the model check.
