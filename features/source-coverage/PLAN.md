# A plan lists its sources and gives each named item a status

Status: Complete

## Outcome + scope

A plan built from material that the user gave cannot be Ready until each person, team, screen, rule and outcome that the material names has a status. Non-goals: a check of truth or completeness; a change of the acceptance line format; a new plan stage.

## Sources + coverage

Sources: the first note that the owner pasted on 2026-11-14 (the gap report), read in full; the second note that the owner pasted on 2026-11-14 (more from the same case), read in full.
Reviewer: a second reader read both notes and this plan, not the notes of the builder. It made its own list first, then gave 18 findings. A second pass gave 9 more and a third pass gave 3. Each one is repaired or recorded: 2 new rows, 4 new acceptance lines, 5 new `Proposal` rows with the place of their yes, 5 rows that now point at the line that proves them, the word "rule" in place of "business rule", and the head teacher in the agent case. Recorded as limits: no check proves that a reader ran (Decision 10), and the agent case has no screen item (Decision 7).
Deliverables: None

- Rule, first note: no client data here, because this repository is public: In scope — The new texts and fixtures hold no client data
- Example, first note: a recorded call, documents and spreadsheets from a client: In scope — names a call record, documents and sheets
- Outcome, first note: the template has a field for the source material and its coverage: In scope — The plan template holds the part
- Rule, first note: each source is listed with whether it was read in full: In scope — a source that is not read in full
- Rule, first note: one row for each person or role, team, screen, rule and requested outcome: In scope — A real agent that plans from two source files writes the rows
- Rule, first note: the statuses In scope, Later and Out, which the second note replaces with four: In scope — an `Out` row
- Rule, first note: In scope points to its acceptance line: In scope — a row that points to no acceptance line
- Rule, first note: Later names who decided, the user or the client, with the source place, which the second note narrows to the client: In scope — a row that names no decider
- Rule, first note: a not-applicable entry only when the task has no source beyond the request: In scope — a reasoned not-applicable entry
- Outcome, first note: the Ready check fails when the part is missing or a row has no status: In scope — A Ready plan fails on a gap
- Rule, first note: the check is of form only and claims no truth: In scope — the check reads the form only
- Rule, first note: the table comes from the sources, not from the agent's notes: In scope — A real agent that plans from two source files writes the rows
- Rule, first note: for large source material a new reviewer builds its own list, which the second note makes required: In scope — no second reader for more than one source
- Rule, first note: an exclusion that the agent proposes is a question, never the client's decision: In scope — refuses a decision that no source holds
- Rule, first note: no claim that the plan covers the request while a row is open: In scope — no coverage claim while a row is open
- Outcome, first note: a failing test first for the new check: In scope — Each new test failed before its code
- Rule, first note: this repository's rules for size: In scope — The skill and rule files keep their size limits
- Rule, first note: this repository's rules for wording and release: In scope — Wording and release follow this repository's rules
- Rule, first note: the change is as small as possible: In scope — The change adds one module
- Rule, second note 1: the second reader is a required step before Ready for large source material: In scope — no second reader for more than one source
- Rule, second note 1: the second reader reads the sources and the plan, not the agent's notes: In scope — a second reader reads the sources and the plan
- Rule, second note 2: four statuses: In scope — an `In scope` row, a `Later` row and an answered `Proposal` row
- Rule, second note 2: Later is decided by the client, with the source place: In scope — a row that names no decider
- Rule, second note 2: a Proposal is ours, no source decides it, and it needs a yes: In scope — a proposal with no answer
- Rule, second note 2: an Open question is for the client or the user: In scope — an open question
- Outcome, second note 2: Ready fails while a row is Open or a Proposal has no answer: In scope — A Ready plan with an open row stays refused
- Rule, second note 3: each acceptance line built on a rule cites its source or is marked as a proposal: In scope — an acceptance line built on a rule names its source or the rule is a proposal
- Rule, second note 4: a coverage claim later shown false makes the approval void, and the plan says so: In scope — an approval after a false coverage claim is void
- Outcome, second note 4: the rule is in the authorization rules: In scope — The authorization rules say
- Outcome, second note 5: the plan lists each deliverable made outside the repository for the client: In scope — its `Reviewer:` and `Deliverables:` lines
- Rule, second note 5: no such deliverable is made before the coverage table has no open row: In scope — no deliverable for the client is made while a row is open
- Example, second note 5: walkthrough videos had no gate: In scope — The walkthrough video skill sends a client video
- Rule, the user decides a `Later` row when the work is for the user: Proposal — the second note names the client, and a project with no client has only the user, so the check accepts both words; yes — user, chat of 2026-11-11 ("you make the decisions needed") and `AGENTS.md` (the design of this codebase is the agent's call)
- Rule, a source that is not read in full fails the check until the user excludes the part, and the plan waits with a Clarification handoff: Proposal — the first note asks only to record the read state; yes — user, chat of 2026-11-11 ("you make the decisions needed") and `AGENTS.md` (the design of this codebase is the agent's call)
- Rule, the check also binds a Draft with an approval handoff and an edited Complete plan, and an older Complete plan stays valid: Proposal — the first note names the Ready check only; yes — user, chat of 2026-11-11 ("you make the decisions needed") and `AGENTS.md` (the design of this codebase is the agent's call)
- Rule, each plan with a source has a `Reviewer:` line and a `Deliverables:` line: Proposal — one fixed form for each plan, with a not-applicable entry or `None` for a small task; yes — user, chat of 2026-11-11 ("you make the decisions needed") and `AGENTS.md` (the design of this codebase is the agent's call)
- Rule, after a void approval the build stops, the plan goes to Draft and the agent asks again: Proposal — the second note says only that the approval is void and that the plan says so; yes — user, chat of 2026-11-11 ("you make the decisions needed") and `AGENTS.md` (the design of this codebase is the agent's call)
- Rule, the check requires the second reader when the plan lists more than one source, and with no reader the plan waits with a Clarification handoff: Proposal — the check cannot measure the size of a source, so the count of sources is its form; yes — user, chat of 2026-11-11 ("you make the decisions needed") and `AGENTS.md` (the design of this codebase is the agent's call)
- Rule, an open row or a proposal with no answer passes a Draft when Blockers holds its question: Proposal — a Draft must be able to hold the question that it asks; yes — user, chat of 2026-11-11 ("you make the decisions needed") and `AGENTS.md` (the design of this codebase is the agent's call)
- Rule, the user or the client can answer a proposal: Proposal — the first note sends the question to the user, and the second note names the client or the user for an open question, so the check accepts both; yes — user, chat of 2026-11-11 ("you make the decisions needed") and `AGENTS.md` (the design of this codebase is the agent's call)

## Repository context

Owners: `.hooks/plan_coverage.py::coverage_errors` (new); `.hooks/plans.py::readiness_errors`; `.agents/skills/he-plan/templates/PLAN.md`; `.agents/skills/he/references/requirements.md` (HE-SOURCE-COVERAGE); `.agents/skills/he/references/workflow.md` (Participation); `.agents/skills/he-plan/SKILL.md`; `.agents/skills/product-walkthrough-video/SKILL.md`; `tests/agent_fixtures.py::source_coverage_failures`.
Same cause: the cause is a plan field that did not exist, so no check could see the gap. Searched the plan template and `plans.py` for a field that maps source material: none. Earlier rules of the same kind are the `Same cause:` and `Single source:` fields (helped: each made a silent step a checked field).
Single source: the rule text lives only in the HE-SOURCE-COVERAGE entry; the template and the skill name the ID. The row form lives only in `plan_coverage.ROWS`, which each refusal prints.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: Autonomous. The owner pasted the two notes on 2026-11-14 as the request, and gave full authority for design, merge and release.
Decisions:

1. The part is a section of its own, and the check reads it with the readiness checks. It is not in the list of required sections, so a plan from before the rule still parses.
2. The check binds a Ready plan, a Draft plan with `Handoff: Approval` and an edited Complete plan. The reported plan passed the Draft check before its approval, so the approval handoff must wait for the part. An unchanged Complete plan stays valid, and so does a Complete plan last edited before the installed update.
3. An `In scope` row points to its acceptance line with words copied from that line. A line number breaks when a line is added.
4. The rule text is a new entry of the rule list. The skill file is at its size limit and names only the ID.
5. One agent case with real source files proves the behavior. A check of form cannot prove that an agent builds the rows from the sources.
6. The read state check reads words only. A source entry passes with `read in full` or with `excluded by the user`, and `not read in full` fails. The check does not parse one entry that holds two parts in two states; the rule text makes each unread part a blocker.
7. The judge of the agent case looks for the words of each role, rule and outcome in a coverage row. It cannot judge the meaning of a row, and it cannot tell a real second reader from a written claim. It has no screen item, because the case is a command-line tool. It takes a `Later` row whose item is the parent summary or the head teacher as the decision of the client, because both real agents wrote such a row for the head teacher. It does not read what else the words of that row put off. The action log of each real run shows whether a reader started.
8. Four statuses replace the three of the first note. `Out` is gone: an exclusion that the client decided is a `Later` row with its decider (the user decides when the work is for the user), and an exclusion by the agent is a `Proposal` row.
9. An `Open` row and a `Proposal` row with no answer pass a Draft only when the Blockers block, down to the `Handoff:` line, holds the question or the proposal of that row in the same words. Another question in Blockers does not cover them, also not one about the same item. The check finds the words only: it cannot tell a question from a sentence that holds the same words as an assumption. That is a limit of a check of form, and the rule text tells the agent to ask the user. A Ready plan has no blockers, so it fails on both.
10. The check requires a second reader when the `Sources:` line holds more than one source. It cannot measure one source, so the rule text requires the reader for one large source. For more than one source, the check refuses a `Reviewer:` line that starts with a not-applicable entry, `None` or `Pending`. It refuses `Pending` for one source too. It cannot tell a real result from written words.
11. No check reads whether an acceptance line built on a rule names its source. The second reader lists each such line, and the `Proposal` status is its form.
12. The void approval rule lives in the Participation rules of the workflow file, the owner of authorization. No check can read a claim made in chat.
13. The gate for a client deliverable is the `Deliverables:` line with its rule, and the video skill points to it. No check can see a file made outside the repository.
14. "As small as possible" has no check of its own. The diff review judges it.
15. Each `Proposal` row of this plan has its yes from two places: the owner's chat instruction of 2026-11-11 to make the needed decisions, and the project rule that gives the agent the design of this codebase. The final report lists these choices for the owner.
16. No new-project flow of `release_canary.py` (`install_new`) writes a plan, so none reaches the new refusal.
17. A decider is the word `user` or `client`, then a comma and a place. A name can follow the word in brackets, because a real agent wrote the decider with a name in brackets. The check does not read the meaning of the words in the brackets or of the place. A row that denies its own decision in those words still passes. That is a limit of a check of form.

## Acceptance + steps

- [x] A Ready plan with a filled part passes: an `In scope` row, a `Later` row and an answered `Proposal` row; a part that the user excluded; one small source with no second reader; a decider with a name beside it; a reasoned not-applicable entry for a task with no source → `tests/test_plan_coverage.py::test_a_ready_plan_passes_with_each_named_item_given_a_status`
- [x] A Ready plan fails on a gap: no part, no one `Sources:` line, a source that is not read in full, no `Reviewer:` line, no second reader for more than one source, a pending reader for one source, no `Deliverables:` line, not at least one row, a row with no status, an `Out` row, a row that points to no acceptance line, a row that names no decider, a proposal with no answer, an open question, rows under a not-applicable `Sources:` line → `tests/test_plan_coverage.py::test_a_ready_plan_fails_on_a_gap_in_its_coverage_part`
- [x] A Ready plan with an open row stays refused when Blockers holds its question → `tests/test_plan_coverage.py::test_a_ready_plan_with_an_open_row_stays_refused_with_its_question_in_blockers`
- [x] A Complete plan from before the rule stays valid → `tests/test_plan_coverage.py::test_a_complete_plan_from_before_the_rule_stays_valid`
- [x] An approval handoff waits for the part and for each open question and each proposal with no answer to be in Blockers, another question in Blockers does not cover them, and a Draft with a question does not → `tests/test_plan_coverage.py::test_an_approval_handoff_waits_for_the_coverage_part_and_for_each_question_to_be_asked`
- [x] The agent case judges the rows from both source files and refuses a decision that no source holds → `tests/test_plan_coverage.py::test_the_agent_case_judges_coverage_against_the_source_files`
- [x] The plan template holds the part with its `Reviewer:` and `Deliverables:` lines. The rule text names a call record, documents and sheets as sources. It says: the check reads the form only; no coverage claim while a row is open; a second reader reads the sources and the plan; an acceptance line built on a rule names its source or the rule is a proposal; no deliverable for the client is made while a row is open → HE-SOURCE-COVERAGE
- [x] The authorization rules say that an approval after a false coverage claim is void, and that the plan says so → N/A — a prose rule in the Participation part of `.agents/skills/he/references/workflow.md`; no check can read a claim made in chat
- [x] The walkthrough video skill sends a client video to the `Deliverables:` line → N/A — one prose line in `.agents/skills/product-walkthrough-video/SKILL.md`; no check can see a file made outside the repository
- [x] Each new test failed before its code for the named cause → N/A — a passing test cannot show its first failure; the build ran the new tests against the earlier check, and 13 failed
- [x] The change adds one module with its call line and its import-order entry, one rule entry, one template section, one hint in the acceptance line of the template, one workflow bullet, one line in the video skill and two reworded lines in the plan skill → N/A — no check measures "small"; the diff review judges it
- [x] Wording and release follow this repository's rules: a reader that did not write the text checks the prose, and Verification names the delivery through `develop` → N/A — review and delivery steps; Verification holds the reader result and the delivery target
- [x] The new texts and fixtures hold no client data → N/A — a search of the outgoing text with the private word list found nothing, and it runs again before the push; the fixture is an invented school
- [x] The skill and rule files keep their size limits → `tests/test_skill_links.py::test_distributed_skills_fit_the_codex_skill_limit`
- [x] A real agent that plans from two source files writes the rows and marks only the client's own decision as `Later` → N/A — a model run, not a unit test; the proof is the `source-coverage` case of `tests/agent_checks.py`

## Baseline + execution

Result: Passed
Evidence: the starting code is the base branch at 9fffedd2, and the Hard Eng check run of that commit passed.
Execution: one builder, test first; a reader that did not write the text checks the prose; one agent run for each client at the end.

## Risks + recovery

- An open Draft plan with an approval handoff must add the part after the update. A count on 46 installed projects found 8 open Draft plans and no Ready plan. The 4,290 Complete plans stay valid.
- The check reads the form only. An agent can still leave an item out of the rows.
- Recovery: revert the commit; no data step.

## ux_reference

N/A — no screen changes; the change adds one plan section and its refusal texts.

## Verification

Result: Passed
Evidence: each new test failed before its code for the named cause and passes now. The static gates and the focused tests passed on the final commit. On the final code, one Claude run and one Codex run of the `source-coverage` case passed: each plan has a row for each named item, marks as `Later` only what the head teacher decided about the parent summary, holds its open questions in its Blockers block, and stays a Draft. The session record of each run shows a real second reader start. The first Claude run failed on a `Later — client (head teacher), …` row, which the check now accepts, and on the rule of the judge that a check counts only as a command of its own. One Codex run wrote the name with no brackets, so the template and the rule text now show the form.
Review: the independent challenge ran on the final commit. Its earlier runs gave four findings, each repaired with its own test: a blocker that did not hold the question of the row, a pending reader for one source, a decider with a name in brackets, and any words after the decider word. Two more are recorded as limits in Decisions 9 and 17. A last review before the push found that the check read only the first line of Blockers, and real agents write their questions in a list below it; that is repaired with its own test.
Retro: (1) The second reader of this plan found rows that pointed at a wrong line and own rules with no `Proposal` row → HE-SOURCE-COVERAGE, the rule that this change adds. (2) The builder changed the check before its new tests for the second note → None — the test-first rule exists; the new tests then ran against the earlier check and failed. (3) The challenge found the two blocker gaps and the pending reader → `tests/test_plan_coverage.py::test_an_approval_handoff_waits_for_the_coverage_part_and_for_each_question_to_be_asked` and `tests/test_plan_coverage.py::test_a_ready_plan_fails_on_a_gap_in_its_coverage_part`. (4) A real agent wrote a decider with a name and the check refused it → `tests/test_plan_coverage.py::test_a_ready_plan_passes_with_each_named_item_given_a_status`. (5) The lint gate refused a joined string in a list → None — the gate ran before the commit, at the right time.
Reader: a reader that did not write the text made three passes over the rule entry, the template lines, the workflow bullet, the two skill lines and the refusal texts. It gave 28 findings, then 14, then 7. Each one is reworded, with one difference: no text gives a size for a "large" source; the entry gives two examples.
E2E: N/A — no user journey of the product changes; the agent case runs a real planning session.

Delivery target: Merge
Delivery: Pending — the pull request into `develop`, its checks, the release pull request into `main` and the release run.
