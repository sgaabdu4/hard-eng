# Start the code review skill for a pasted diff

Status: Complete

## Outcome + scope

A request to review a diff that the user pastes into the conversation starts the code review skill. Non-goals: other skill descriptions, the review method beyond one clause on the pasted diff, a Codex model run.

## Sources + coverage

Sources: N/A — the request is the weekly reference repository watch; its only source is one reference repository's change that makes its review skill start for a pasted diff, read in the diff.

## Repository context

Owners: `.agents/skills/code-review/SKILL.md` (the description that each host loads) and `.agents/skills/code-review/references/review.md` (the Diff rule); `tests/test_skill_routing.py` owns the sample requests.
Same cause: N/A — no earlier fix of this cause. The other descriptions name their inputs in plain words; no other skill takes pasted text as its main input.
Single source: the description has one owner, `code-review/SKILL.md`. Searched the repository for its first words: the only other copies are the installed copies inside the two skill submodules, which a Hard Eng update replaces.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: Autonomous — the scheduled reference repository watch asks for each adapt item as its own small PR into develop.

## Acceptance + steps

- [x] The request "Review this diff before I merge it" ranks the code review skill first → `tests/test_skill_routing.py::test_every_request_picks_its_own_skill` failed with "ranked security-review first" before the edit and passes after it.
- [x] A real model starts the skill for a pasted diff → N/A — no test starts a model; in a sealed copy of the skills, Claude Code got that request with a 9-line pasted diff. Old description: the skill started in 0 of 3 runs. New description: 3 of 3 runs.
- [x] The review method says what to read for a pasted diff → N/A — prose that a review applies; the Reader check below covers its clarity.

## Baseline + execution

Result: Passed
Evidence: 2026-11-16, develop f0eba5ff: this branch starts at that commit, whose tree passed the `hard-eng` and `canary` checks on PR 642. The three runs with the old description are the failing baseline of the behavior.
Execution: One builder, this session.

## Risks + recovery

The description is always loaded, so it costs tokens in each session: the change adds two words. A revert restores the old text.

## ux_reference

N/A — skill text and a test row; no visible UI.

## Verification

Result: Passed
Evidence: `tests/test_skill_routing.py` and `tests/test_skill_links.py`: 17 passed, which includes the check that no two descriptions are too alike. The model runs are in the second acceptance line. The Complete check passed on this branch.
Reader: a reader that did not write the text compared the old and new skill text. It quoted the new Diff clause (which state of the files to read, and no base for a pasted diff); the clause was reworded to answer both.
E2E: N/A — no user journey changes.
Real service: N/A — the change calls no outside service.
Retro: None — no failed check or correction.
Delivery target: Merge
Delivery: Pending — `hard-eng` and `canary` pass on the PR to develop.
