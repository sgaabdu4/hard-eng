# Let a look Fail that the evidence disproves be re-reviewed

Status: Complete

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
1. The dispute is `look <images> --dispute "<item>" --cite <path>:<from>-<to> [--cite ...] [--measured <key>]`; its flags live in the one `look` parser, so `look --help` lists them, and the existing `--host` flag picks the reviewer as in a normal run. `--plan` and `--all` are refused with `--dispute`. The item must equal one part of a Fail line of this head's record. The hook reads the cited bytes from the HEAD blob, never the working tree and never the project's prose. A fresh reviewer session gets the item, the image of its frame, the cited lines and the measured facts of the key, and nothing else. It answers `stands` or `disproved` and the line it relies on. Code checks that the line lies inside a cited range, or that `measured` was cited with a key; any other answer is `not done` and changes nothing.
2. Only `disproved` removes the item. `stands` keeps it. Each decided dispute is recorded under `disputes` in the look record, with the item, the cited ranges with the hash of the cited bytes, the verdict and the relied line. A head decides one dispute for each item, so a rerun cannot pick another result.
3. A dispute is refused on an item with a `— code:` reason and on an owner line (a rule line from a measure, test or plan owner), because code or an owner decides those. It is refused with no cite, with a missing file, a missing line, a symlink, a submodule or a range over 120 lines, and with more than 6 cites. No line in a plan, a PR or a project file clears a Fail; a plan line that says declined changes nothing.
4. The disputed item is removed from every stored rule line that holds it (the same item can stand under two rules), so the next head's `earlier_findings` never sends it back. A rule line with no part left becomes a Pass line that names the evidence. The outcome is `findings` while any Fail line remains, else `clean`. A clean record that rests on a disproved dispute carries to a later head, in the per-image carry and in the whole-record carry, only while the hash of each cited range still matches at that head; otherwise the reviewer sees the image again. A record that carries one image while it reviews another keeps the disproved disputes of the record it carries from, marked `carried_from`; a carried dispute counts for the carry check but not as a dispute decided by this head, so the same item can be disputed again after a new review.
5. A claim about a keyed element must be a measured item. A judgement or untagged item that holds one of the words `square`, `squared`, `sharp` (radius), `centred`, `centered`, `not centred`, `uncentred`, `off-centre` (alignment) or `touch`, `touches`, `touching`, `no gap` (gap) and the exact key of a measured element for that kind is refused by form. The refusal names the key and the item to write, and does not choose a direction for the reviewer: it says to open the note with the claim only for that claim. Near misses that stay judgement: the word with no key, a key with no word, `rounded`, `filled`, a size, colour or weight claim.
6. A claim reads only when the note after the kind tag opens with it: up to six plain words, then the claim word (`square corners`, `chips touch`, `the header line is centred`). A negation, a modal or `but` among those words (`isn't centred`, `should be centred`, `don't touch`) and any other note keep the old meaning of the kind, so a word inside a sentence never flips a claim. The verdict answers the claim, not a fixed question. A radius item that claims square: corners not all 0 are disproved (code Pass); all four 0 stays a reviewer Fail unless 0 is in no rounded token, where code Fails it. An align item that claims centred: a measured text that is not centred is disproved (code Pass); a measured centred text leaves the item with the reviewer. A gap item that claims touch: a measured gap above 0 is disproved (code Pass); a gap of 0 leaves the item with the reviewer. Without a claim, an align item claims that the text is not centred, a radius item is the token check and a gap item is the token check. Limit: a note that states some other observation (`too tight`) is still read as the token check.
7. The radius row holds all four corners (`corners`), and `px` is the largest corner. A control, and a text element with a fill or a border (a chip or badge), gets a row at 0 when all four corners are 0 and it has a name. A square row is never off-token: it carries no token verdict, adds no fault to `token_fault`, and is listed last; the coverage line counts it apart. Only the square claim can fail it. The verdict for a claim reads the corners of the keyed element only. A plain radius item on a square row passes, because a square corner is not a token fault.
8. The prompt asks for the claim forms of decision 5. This changes every image key, so each kept and carried clean verdict resets once.
9. The reviewer sessions move to `look_reviewer.py` with no behavior change, because `look.py` was at exactly 1000 lines and the dispute needs the same runner.
10. Each measured element has its own key: its name, and ` #1`, ` #2` in record order when several elements of one kind share a name, so a verdict never comes from another element. A name shared by two elements is no key on its own.
11. `look` loads the YAML runtime like the other commands (`ensure_python_runtime`, a restart under `uv run --with pyyaml` when `yaml` is missing; a missing `uv` is a printed refusal). A DESIGN.md front matter that cannot be read because PyYAML is missing is a refusal, never an empty token list. A DESIGN.md with no front matter still gives no tokens, with no YAML needed. `ship` loads the same runtime, because its look proof reads the tokens of carried records.
12. A code Fail on a square claim is stored with its claim word (`[radius] square — code: ...`), so the next head decides it again with the same claim. A curly apostrophe counts as a straight one, and `off` counts as a negation, in the claim phrase.

## Acceptance + steps

- [x] The reviewer sessions run from their own module with the same behavior → `tests/test_look.py::test_look_falls_back_to_a_fresh_same_agent_session`
- [x] A claim form about a keyed element is refused as a judgement item and accepted as a measured item; each near miss stays, and the four genuine judgement Fails (a label larger than its neighbours, a second filled primary button, a warning with no next step, unselected chips filled) are not touched → `tests/test_look_claims.py::test_a_claim_about_a_keyed_element_must_be_a_measured_item`
- [x] A claim that text is centred is disproved by a measured start and left with the reviewer when it is centred; `not centred`, `isn't centred` and `should be centred` keep the old meaning → `tests/test_look_claims.py::test_a_centred_claim_is_checked_in_its_own_direction`
- [x] A square claim is disproved by a measured radius, kept when all corners are 0 (code Fails it only when 0 is no token), and `should be square` keeps the token meaning → `tests/test_look_claims.py::test_a_square_claim_is_checked_against_the_corners_of_its_element`
- [x] A square row is never off-token, is listed last, an unnamed one is skipped, and the coverage line counts it apart → `tests/test_look_claims.py::test_a_square_row_has_a_key_and_no_value_row_is_listed`
- [x] A square control adds no token fault → `tests/test_look_proof_kinds.py::test_a_radius_outside_the_tokens_leaves_design_system_to_the_reviewer`
- [x] A real page: square chips, a link, a button and a table cell are recorded at 0 with all corners, an unnamed input is not, and each claim verdict comes from that element's own corners → `tests/test_ui_corner_facts.py::test_square_chips_are_recorded_and_decided_from_their_own_corners`
- [x] A `stands` answer (scripted reviewer: proves the mechanism only) keeps the item and records the dispute → `tests/test_look_dispute.py::test_a_scripted_stands_answer_keeps_the_item_and_records_the_dispute`
- [x] Three Fails that cited evidence disproves leave the record and the head turns clean (scripted reviewer; the real reviewer is the live run) → `tests/test_look_dispute.py::test_a_disproved_item_leaves_the_record_and_the_head_turns_clean`
- [x] A disproved item does not return on a new head → `tests/test_look_dispute.py::test_a_disproved_item_does_not_return_on_a_new_head`
- [x] An item under two rules is disproved under both → `tests/test_look_dispute.py::test_an_item_under_two_rules_is_disproved_under_both`
- [x] A clean record that rests on a dispute carries only while the cited bytes hold → `tests/test_look_dispute.py::test_a_clean_record_that_rests_on_a_dispute_carries_only_while_the_cited_bytes_hold`
- [x] The PR proof accepts a record that a dispute cleaned → `tests/test_look_dispute.py::test_the_pr_proof_accepts_a_record_that_a_dispute_cleaned`
- [x] The reviewer gets only the item, the image, the HEAD bytes of the cited lines and the measured facts → `tests/test_look_dispute.py::test_the_dispute_prompt_holds_only_the_item_the_image_and_the_cited_bytes`
- [x] A dispute with a missing file, a missing line, no cite, an untracked file, a file edited only in the working tree, a symlink, `--plan` or `--all`, a code item or an owner line is refused and changes nothing → `tests/test_look_dispute.py::test_a_dispute_that_cites_nothing_real_is_refused` and `tests/test_look_dispute.py::test_a_dispute_on_a_code_item_or_an_owner_line_is_refused`
- [x] An answer that relies on an uncited line is not done and changes nothing → `tests/test_look_dispute.py::test_an_answer_that_relies_on_an_uncited_line_changes_nothing`
- [x] One decided dispute for each item and head, and a plan line that says declined changes nothing → `tests/test_look_dispute.py::test_a_head_decides_one_dispute_for_each_item_and_a_plan_line_clears_nothing`
- [x] `look` loads the YAML runtime first, refuses clearly when it cannot, and never reads a front matter as no tokens without PyYAML → `tests/test_look_no_token_verdicts.py::test_the_prompt_describes_no_check_against_the_token_lists`
- [x] Two elements with one name get their own keys and their own verdicts → `tests/test_look_claims.py::test_two_elements_with_one_name_get_their_own_keys_and_verdicts`
- [x] A touch claim is disproved by a gap above 0 and stands at 0; `should touch` and `don't touch` keep the token meaning → `tests/test_look_claims.py::test_a_touch_claim_is_checked_against_the_gap_of_its_pair`
- [x] A record that carries one image and reviews another keeps the disputes it rests on → `tests/test_look_dispute.py::test_a_record_that_carries_one_image_keeps_the_disputes_it_rests_on`
- [x] `ship` loads the YAML runtime → `tests/test_tool_environment.py::test_ship_loads_the_yaml_runtime_before_it_runs`
- [x] A code-failed square claim is failed again on the next head → `tests/test_look_claims.py::test_a_square_claim_is_checked_against_the_corners_of_its_element`
- [x] A curly apostrophe or `off centred` never flips a claim → `tests/test_look_claims.py::test_a_curly_apostrophe_or_off_centred_never_flips_a_claim`
- [x] The look command lists the dispute flags, routes a dispute and uses its `--host` flag → `tests/test_look_dispute.py::test_the_look_command_routes_a_dispute_and_lists_its_flags` and `tests/test_look_dispute.py::test_a_dispute_uses_the_host_flag_of_the_look_command`
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
6. Every image key changes once (decision 8), so earlier clean verdicts do not carry. A page that has square controls now lists their rows last in the radius facts, so a long page can cut other keys sooner. A page with repeated names gets ` #n` keys, so a reviewer must copy the number. `look` imports `tool_setup` first, about 60 ms.
7. Recovery: revert the merge on `develop` with a new PR.
Not checked: any installed project.

## ux_reference

N/A — hook code and tests; no visible UI.

## Verification

Result: Passed
Evidence: Each new test failed before its fix and passes now. The claim tests, the dispute tests, the runtime tests and the corner browser test were red first; the dispute tests also fail under a mutation that drops the owner, code, decided, host, all-lines or carry check. The focused look and UI tests (483) passed once at the end of the claim work, and `check --static`, format, lint, annotations and types pass at the final head; `hot-paths` on the touched files gave 0 findings. `challenge` ran three times: round 1 gave four findings (a per-image carry that dropped the disputes, `ship` without the YAML runtime, a code-failed square item that lost its claim on the next head, curly-apostrophe and `off` negations), round 2 gave one (a carried dispute that blocked a new dispute of the same item), and round 3 printed `clean`; each finding was reproduced by its reviewer and fixed with a red test. Measured replay, not live: the three faults of the second release proof (no YAML, one key for several chips, `chips touch` and `square corners` decided by a token question) are each a test row. The scripted reviewer proves only the mechanism of the dispute; the cases of the brief are tested as follows. Code-decided: square chips at 0 px (Fail when 0 is no token, stays with the reviewer when it is), the header line centred on a measured start (disproved), square corners at 6 px (disproved), chips touch at 0 px (stands) and at 8 px (disproved). Scripted reviewer: the warning with no next step stays after a `stands` answer; the optional-field asterisk, the danger button on its token and the balance item (cited plan line `Single source`) leave the record after a `disproved` answer with a cited line. The balance case can be decided only by a reviewer reading the plan line; no live run of it was made. Not decided by this design: a size, weight, gap, colour or tap claim with no number other than the forms above.
E2E: N/A — hook code with no app journey; the live `look` and the live dispute on a fixture page are the proof.
Real service: Passed — the Claude reviewer CLI, no `--host` flag, system python3 with no PyYAML (so the new runtime load ran). Live look on a fixture page with square joined chips: `findings`; code decided the corner, gap and colour items, and the two `chips touch` items stayed with the reviewer because the measured gap is 0 px. Two live disputes there (a cited CSS line, then a cited DESIGN.md line with the measured key of the chip pair) both ended `stands`. Then a live look on a list page whose DESIGN.md says a row may hold a filled danger button and that its action sits at the far end of the row. Of four reviews of that one commit, two raised a Fail that the quoted line contradicts: two filled danger buttons leave no single focus, and the action sits too far from its label. The dispute of each item, citing that DESIGN.md line, ended `disproved` with the line named as the one relied on; it was run twice for each item on two copies of the same record, and all four runs gave the same outcome. The other items of those lines stayed as Fails, as designed, because one dispute decides one item. Live runs also gave `stands` for a Fail that was right (an empty field with no prefill, three runs, citing the markup `required` attribute). The first dispute attempts on that page were refused because the first item of a line that opens with a sentence never matched; this live fault is fixed with a red test first (`tests/test_look_dispute.py::test_the_first_item_of_a_line_that_opens_with_a_sentence_can_be_disputed`).
Retro: A verdict answered one fixed question for each kind (is the gap a token, is the text not centred), so a claim that said the opposite got the wrong answer, and a measurable claim with no number never reached code. The kind tag did not carry the direction of the claim; the claim phrase now does, and a negation, a modal or any other note keeps the old meaning. A name key pooled several elements. Prevention: `tests/test_look_claims.py::test_a_centred_claim_is_checked_in_its_own_direction`, `tests/test_look_claims.py::test_a_touch_claim_is_checked_against_the_gap_of_its_pair`, and `tests/test_look_claims.py::test_two_elements_with_one_name_get_their_own_keys_and_verdicts`. A live dispute also found that an item written after an opening sentence never matched, because every test line began with an item; the fixture now holds a line that opens with a sentence. Escaped bug: found on the base branch by the release proofs; the gate that should have caught each was the tests gate, and each red test of this PR fails on `develop` `5c515d97`.
Not checked: the Codex reviewer (not used); the balance case with a real reviewer; any installed project; a page with more than one chip of the same name in a live run.

Delivery target: Merge

Delivery: Pending — required remote proof.
