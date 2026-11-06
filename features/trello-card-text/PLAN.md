# Trello coordinator writes short, laid-out card text

Status: Complete

## Outcome + scope

Coordinator card comments came out as long plain paragraphs with no bold or bullets, and a non-technical reader found them hard to follow. The skill now asks for ~80% ASD-STE100 card text with a bold first line and bullets, and `comment` and `new` refuse a sentence over 25 words, a paragraph over 3 sentences, a comment over 2 lines without a bold first line, code formatting, or developer words such as PR, merged, deployed or staging. Non-goals: grammar checks, a full approved-word list, rewriting text for the coordinator, card titles.

## Repository context

Owners: `.agents/skills/trello-coordinator/scripts/trello_board/config.py` (text checks beside the privacy check), `commands.py` (`comment`, `new`), `SKILL.md` (core rule), `references/commands.md` (contract).
Same cause: N/A — no writing rule existed for card text; image lines, links and code fences are skipped.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: Abid on 2026-11-06: card text is not ~80% ASD-STE100, too many walls of text, no bold or bullets, "that needs fixing too"; then that the person using the board finds the cards and comments too hard to understand; merge after green checks for the coordinator work.
Decision: developer words are a fixed list of terms with no everyday meaning in a shop app ("branch" and "commit" stay allowed).
Decision: limits match the Plain STE output style: 20 words asked, 25 refused; at most 3 sentences per paragraph or list item.

## Acceptance + steps

- [x] A long sentence, a 4-sentence paragraph, a 3-line comment without a bold first line, code formatting or a developer word is refused by `comment` and `new` and nothing is sent; a bold lead with bullets, an image line and a question posts → `tests/test_trello_board.py::test_card_text_must_be_short_and_laid_out`.
- [x] Existing comment, privacy, dry-run and new-card behavior stays the same → `tests/test_trello_coordinator.py::test_comment_posts_new_and_blocks_private_data`, `tests/test_trello_board.py::test_new_card_gets_the_next_number_at_the_top`.

## Baseline + execution

Result: Passed
Evidence: develop passed required CI after PR 502 merged; the new test failed before the fix.
Execution: one session; failing test first.

## Risks + recovery

A refused comment delays a reply by one rewrite; the error names the rule. Recovery: revert this pull request.

## ux_reference

N/A — Trello card text only; no app screens change.

## Verification

Result: Passed
Evidence: `python3 .hooks/hard-eng.py check --plan-stage Complete` exit 0, 2273 tests; 69 coordinator and board tests passed.
E2E: N/A — a real board post needs the private key; the fake board is built from recorded API shapes.
Delivery target: PR
Delivery: Pending — PR into develop.
