# Let a look Fail that the evidence disproves be re-reviewed

Status: Ready

## Outcome + scope

`look` gets one way out of a reviewer Fail that code or written rules disprove: a command that names the Fail item and cites file and line ranges in the repository at HEAD, then asks a fresh reviewer one question. A measurable claim about a keyed element can no longer pass as a judgement item, so code checks it against the measured fact. Square corners get a measured fact, and the centring check reads the direction of the claim. Non-goals: a new reviewer host flag, an environment switch, any line that a project writes clearing a Fail on its own, a size, weight, gap, colour or tap claim with no number (the real lines prove only the corner and centring claims), and any change outside look.

## Sources + coverage

Sources: N/A — the request is the only source: the coordinator's brief of 2026-11-25 and its two later faults (the radius record, the centring direction).

## Repository context

Owners: `look_answer.py` (item form and refusal), `look_facts.py` (facts, kinds and verdict), `look_records.py` (item decision, earlier findings), `look.py` (prompt, findings note), `ui_measure.py` (measure script and kind table), `look_reviewer.py` (new: the reviewer sessions that moved out of `look.py`, which was at the 1000 line limit), `look_dispute.py` (new: the dispute command), `browser.py` (the `look` entry that routes `--dispute`).
Same cause: the form decides what a Fail item is, but not what an item claims, so a claim about a keyed element passed as a judgement item and a kind tag decided a fixed question whatever the claim said. The earlier fix (keys) fixed the element; this fixes the state that the item claims. Other places searched: `look_records.earlier_split` and `sort_parts` (both call the one `decide_item`), `token_fault` (reads `radii` rows), `owner_lines`.
Single source: the claim forms live once in `look_facts.py` and `look_answer.py` reads them; the fact rows stay built by `FACTS`. The reviewer sessions live once in `look_reviewer.py`; `look.py` and `look_dispute.py` both call them. The dispute reads the item from the record, the rule lines come from the one `fail_parts`.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: Autonomous — the coordinator's brief of 2026-11-25 and its two added faults; standing rule: ask the advisor, not the user.
Decisions made here, each with a reason:
1. The dispute is `look <images> --dispute "<item>" --cite <path>:<from>-<to> [--cite ...] [--measured <key>]`. The item must equal one part of a Fail line of this head's record. The hook reads the cited bytes from the HEAD blob, never the working tree and never the project's prose. A fresh reviewer session gets the item, the image of its frame, the cited lines and the measured facts of the key, and nothing else. It answers `stands` or `disproved` and the line it relies on. Code checks that the line lies inside a cited range, or that `measured` was cited with a key; any other answer is `not done` and changes nothing.
2. Only `disproved` removes the item. `stands` keeps it. Each decided dispute is recorded under `disputes` in the look record, with the item, the cited ranges with the hash of the cited bytes, the verdict and the relied line. A head decides one dispute for each item, so a rerun cannot pick another result.
3. A dispute is refused on an item with a `— code:` reason and on an owner line (a rule line from a measure, test or plan owner), because code or an owner decides those. It is refused with no cite, with a missing file, a missing line, a symlink, a submodule or a range over 120 lines, and with more than 6 cites. No line in a plan, a PR or a project file clears a Fail; a plan line that says declined changes nothing.
4. The cited item is removed from the stored rule line, so the next head's `earlier_findings` never sends it back. A rule line with no part left becomes a Pass line that names the evidence. The outcome is `findings` while any Fail line remains, else `clean`.
5. A claim form names the state it claims, so code compares the claim with the fact. Exact forms (case-insensitive): corners `square`, `squared`, `sharp` (kind radius); centred `centred`, `centered` (kind align, claims centred); not centred `not centred`, `not centered`, `uncentred`, `off-centre` (kind align, claims not centred). A judgement or untagged item that holds one of these words and the exact key of a measured element for that kind is refused by form, and the refusal names the key and the item to write. Near misses that stay judgement: the word with no key, a key with no word, `rounded`, `filled`, a size, gap, colour or weight claim.
6. The claim reads from the note after the kind tag. A radius item that claims `square`: corners not all 0 are disproved (code Pass); all four 0 stays a reviewer Fail unless 0 is in no rounded token, where code Fails it. An align item that claims centred: a measured text that is not centred is disproved (code Pass); a measured centred text leaves the item with the reviewer. An align item with no claim word keeps its old meaning, a claim that the text is not centred. A radius item with no claim word keeps its old meaning, the token check.
7. The radius row holds all four corners (`corners`), and `px` is the largest corner. A control, and a text element with a fill or a border (a chip or badge), gets a row at 0 when all four corners are 0. A row at 0 carries no token verdict and adds no fault to `token_fault`, so no project fails for a square control. The verdict for a claim reads the corners of the keyed element only.
8. The prompt asks for the claim forms of decision 5. This changes every image key, so each kept and carried clean verdict resets once.
9. The reviewer sessions move to `look_reviewer.py` with no behavior change, because `look.py` was at exactly 1000 lines and the dispute needs the same runner.

## Acceptance + steps

- [x] The reviewer sessions run from their own module with the same behavior → `tests/test_look.py::test_look_falls_back_to_a_fresh_same_agent_session`
- [x] A claim form about a keyed element is refused as a judgement item and accepted as a measured item; each near miss stays → `tests/test_look_claims.py::test_a_claim_about_a_keyed_element_must_be_a_measured_item`
- [x] A claim that text is centred is disproved by a measured start, and left with the reviewer when it is centred; a not-centred claim keeps its meaning → `tests/test_look_claims.py::test_a_centred_claim_is_checked_in_its_own_direction`
- [x] A square claim is disproved by a measured radius, kept when all corners are 0, and kept when 0 is a token → `tests/test_look_claims.py::test_a_square_claim_is_checked_against_the_corners_of_its_element`
- [x] A square chip group is recorded with its corners at 0 and fails in code; the same group at 6 px passes → `tests/test_ui_corner_facts.py::test_square_chips_are_recorded_and_decided_from_their_own_corners`
- [x] A square control adds no token fault → `tests/test_look_claims.py::test_a_square_control_adds_no_token_fault`
- [x] The five Fails that the evidence confirms stay after a dispute, and each dispute is recorded → `tests/test_look_dispute.py::test_a_fail_that_stands_stays_and_the_dispute_is_recorded`
- [x] Three Fails that cited evidence disproves leave the record, and the head turns clean → `tests/test_look_dispute.py::test_a_disproved_item_leaves_the_record_and_the_head_turns_clean`
- [x] A disproved item does not return on a new head → `tests/test_look_dispute.py::test_a_disproved_item_does_not_return_on_a_new_head`
- [x] The reviewer gets only the item, the image, the cited bytes and the measured facts → `tests/test_look_dispute.py::test_the_dispute_prompt_holds_only_the_item_the_image_and_the_cited_bytes`
- [x] A dispute with a missing file, a missing line, no cite, an untracked file, a symlink, a code item or an owner line is refused and changes nothing → `tests/test_look_dispute.py::test_a_dispute_that_cites_nothing_real_is_refused` and `tests/test_look_dispute.py::test_a_dispute_on_a_code_item_or_an_owner_line_is_refused`
- [x] An answer that relies on an uncited line is not done and changes nothing → `tests/test_look_dispute.py::test_an_answer_that_relies_on_an_uncited_line_changes_nothing`
- [x] One decided dispute for each item and head, and a plan line that says declined changes nothing → `tests/test_look_dispute.py::test_a_head_decides_one_dispute_for_each_item_and_a_plan_line_clears_nothing`
- [x] The look command lists the dispute flags and routes a dispute → `tests/test_look_dispute.py::test_the_look_command_routes_a_dispute_and_lists_its_flags`
- [x] The findings note names the dispute route → `tests/test_look_facts.py::test_a_findings_run_ends_with_the_line_about_the_rules`

Steps:

1. Commit this plan.
2. Move the reviewer sessions (no behavior change).
3. Red tests, then the claim forms, the corners and the centring direction.
4. Red tests, then the dispute.
5. Static gates, `challenge` to a clean headline, `check --plan-stage Complete --base origin/develop` once.
6. One live `look` on a fixture page, then one live dispute of a Fail on it; PR to `develop`.

## Baseline + execution

Result: Passed
Evidence: the focused look tests (219) passed on `origin/develop` `5c515d97` before any edit; the full Complete gate passed on the previous head of this branch family.
Execution: One builder in `fix/judgement-recheck`.

## Risks + recovery

1. A reviewer can answer `disproved` with a wrong line and be asked again; a project can repeat a `not done` run. The head decides one dispute only once a decided answer exists.
2. A disproved item removes its whole Fail part; a part that holds two claims loses both. The prompt and the form ask for one claim for each item.
3. A key phrase in an item can be a coincidence, so a claim about another element can be refused by form; the refusal names the key, and the reviewer words the item again.
4. A `[size]` item still means the 11 px floor only; a claim that one label is larger than its neighbours stays a judgement item and cannot be decided by code.
5. A reviewer that answers `disproved` on a cited line that does not mean what it says is a reviewer fault; the record keeps the hash of the cited bytes and the relied line for a later audit.
6. Every image key changes once (decision 8), so earlier clean verdicts do not carry.
7. Recovery: revert the merge on `develop` with a new PR.
Not checked: any installed project.

## ux_reference

N/A — hook code and tests; no visible UI.

## Verification

Result: Pending
Evidence: Pending.
E2E: N/A — hook code with no app journey; the live `look` and the live dispute on a fixture page are the proof.
Real service: Required — the Claude reviewer CLI: one live `look` on a fixture page, then one live `look --dispute` of a Fail on it, with no `--host` flag.
Retro: Pending.

Delivery target: Merge

Delivery: Pending — required remote proof.
