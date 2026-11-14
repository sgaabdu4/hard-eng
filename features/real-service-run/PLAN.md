# A plan records the real run of each changed call to an outside service

Status: Ready

## Outcome + scope

Each plan holds a `Real service:` line, and the plan check refuses a plan that proves a changed call to an outside service only on a fake. Non-goals: a gate that calls an outside service; a check of a fake against the real service; a rule on error reports to a tracker; the removal of the old plans in the `features` folder, which ships as its own change.

## Sources + coverage

Sources: the escaped-bug report that the owner pasted on 2026-11-14, read in full; the owner's chat words of 2026-11-14 on old code in touched files, read in full.
Reviewer: a second reader read the report and this plan, not the notes of the builder. It made its own list first, then gave 10 findings, and a second pass gave 3 more. Each one is repaired or recorded: the row for the real write now points at the refusal line; the line form for a run after the deploy is removed, because the report asks for the run before release; 5 new `Proposal` rows; each `Proposal` row now names the report as the place of the yes; the owner line now names the reason for each choice; the removal of the E2E exemption has its acceptance line. Recorded as limits: the check cannot prove the run (Decision 4), and the weighing of skill guidance for gap 3 (Decision 3).
Deliverables: None

- Outcome, decide for each gap if it belongs in Hard Eng as a rule, a gate check or skill guidance, or in the project only: In scope — The owner gets the decision for each of the three gaps
- Gap 1, a test double of an outside service can drift from the real behaviour: In scope — tells the agent to correct the fake when the real reply differs
- Gap 1, nothing checks a double against the real service: Proposal — Hard Eng adds no automatic check of a fake against the real service, because that check needs credentials and a network call in the gate; the one real run and the fake repair take its place, and the owner gets a test idea for the project; yes — user, the report of 2026-11-14 ("Decide whether Hard Eng should change, and how") and `AGENTS.md` (the design of this codebase is the agent's call)
- Gap 2, a new or changed write path can ship with only mocked proof: In scope — A plan shaped like the incident
- Gap 3, a failed server command can go unreported to monitoring: Proposal — project only, with no Hard Eng rule, check or skill guidance: the catch is one test at the command entry point, which only the project can write, and the owner gets a rule text for the project; yes — user, the report of 2026-11-14 ("Decide whether Hard Eng should change, and how") and `AGENTS.md` (the design of this codebase is the agent's call)
- Rule, the report: a real write against the live backend before release, which the project had as a rule that no gate enforced: In scope — A plan shaped like the incident
- Example, the report: older code parsed a field of the reply, so a change can break code that reads a reply: In scope — the code that builds its request or reads its reply
- Rule, the report: the smallest deterministic check that would have caught this: In scope — A plan shaped like the incident
- Rule, the report: the check does not slow the gate: In scope — The check adds no measurable time to the gate
- Rule, the report: explain the choice and its limits: In scope — with the reason for each choice and its limits
- Example, the report: transaction state, fields that the server sets, and empty against missing values: In scope — names the transaction and the fields that the service fills in, tells an empty field apart from a missing field
- Rule, the owner's chat words: remove old code with no live reason in the files that a change touches: In scope — An unchanged Complete plan with no E2E line is refused
- Rule, each plan holds the line, and a change that calls no outside service gives a reason: Proposal — one fixed form for each plan, so a missing line is never a silent pass; yes — user, the report of 2026-11-14 ("Decide whether Hard Eng should change, and how") and `AGENTS.md` (the design of this codebase is the agent's call)
- Rule, a not-applicable reason that names a fake, a mock, a stub, a test double or an in-memory copy is refused: Proposal — a fake that covers the call is the reason of the incident, and it is never a reason to skip the real run; yes — user, the report of 2026-11-14 ("Decide whether Hard Eng should change, and how") and `AGENTS.md` (the design of this codebase is the agent's call)
- Rule, a `Required` or `Passed` text names the service first: Proposal — a text such as "all tests passed" names no service and no real run; yes — user, the report of 2026-11-14 ("Decide whether Hard Eng should change, and how") and `AGENTS.md` (the design of this codebase is the agent's call)
- Rule, a planned run is valid at Ready, and Complete needs the run: Proposal — the run needs the built code, so the plan can only promise it before the build; yes — user, the report of 2026-11-14 ("Decide whether Hard Eng should change, and how") and `AGENTS.md` (the design of this codebase is the agent's call)
- Rule, the line has no form for a run after the deploy: Proposal — the report asks for the run before release, and a first run on the released code is the incident again; yes — user, the report of 2026-11-14 ("Decide whether Hard Eng should change, and how") and `AGENTS.md` (the design of this codebase is the agent's call)
- Rule, the run uses only a test account that the user or the project's rules name, never production, and removes its records: Proposal — a rule that sends an agent to a real service needs these limits; yes — user, the report of 2026-11-14 ("Decide whether Hard Eng should change, and how") and `AGENTS.md` (the design of this codebase is the agent's call)
- Rule, the check binds a Ready plan, a Draft with an approval handoff and an edited Complete plan, and an older Complete plan stays valid: Proposal — the same reach as the other plan rules; yes — user, the report of 2026-11-14 ("Decide whether Hard Eng should change, and how") and `AGENTS.md` (the design of this codebase is the agent's call)
- Rule, only the user can decide to skip the real run: Proposal — without an exit an agent with no test account writes a false reason; yes — user, the report of 2026-11-14 ("Decide whether Hard Eng should change, and how") and `AGENTS.md` (the design of this codebase is the agent's call)

## Repository context

Owners: `.hooks/plan_runs.py` (new: the E2E check moved out of `.hooks/plans.py`, and the new line check); `.hooks/plans.py::readiness_errors`; the HE-REAL-SERVICE-RUN entry of the requirement registry; the plan template; the outside-services row of the test guide.
Same cause: the cause is a rule that lived only in prose: the test guide told the agent to run the journey one time against the real service, and no plan field held the run, so no check saw it. Earlier fix of the same kind: HE-SOURCE-COVERAGE (helped: a prose rule became a checked plan part). Searched the skills for other "before Complete" steps with no plan field: only this row and the E2E text, which has its field.
Single source: the rule text lives only in the HE-REAL-SERVICE-RUN entry; the test guide, the two skills, the plan checks reference and the template name the ID. The sentence in the test guide that held the rule is replaced by the ID. The line forms live only in `plan_runs.WORDS`, which each refusal prints.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: Autonomous. The owner pasted the report on 2026-11-14 as the request, and gave full authority for design, merge and release.
Decisions:

1. Gap 2 goes into Hard Eng as a form check on one plan line. The rule existed in the test guide, and the incident shows that a rule with no field is not kept. Other forms were weighed. A scan of the code for calls to an outside service needs a list of markers for each project and each language. A gate that calls the service needs credentials and a network. One plan line needs neither, so it is the smallest.
2. Gap 1 gets two sentences in the rule: compare each field of the real reply with the fake, and correct the fake when they differ. A machine check of a fake against the real service stays in the project, because it needs credentials and a network call. The test idea for the project is one set of contract tests that runs against the fake in the gate and against the test account by hand.
3. Gap 3 stays in the project. A line of skill guidance in Hard Eng was weighed: a reviewer would apply it by judgement in each project, with or without a tracker, and one incident does not pay for that text. The deterministic catch is one test at the command entry point, and only the project can write it. The owner gets a rule text and that test idea.
4. The check reads form only. It cannot see if the run was done, and it cannot see if a change calls an outside service. An agent can still write a false not-applicable reason, or a `Passed` text for a run that was not done. So the check does not prove that the incident is caught. It makes each plan answer the question, and it refuses the answers of the incident: no line, a fake as the reason, a text with no service. The agent case on real clients measures what agents do with the rule.
5. A change that the size rule rates small has no plan, so the check does not reach it. The rule text still applies. A list of outside-service markers in the gates file could close this later; it is not built now, because no measured case asks for it.
6. The fake words are refused in not-applicable reasons only. The first build also refused them in `Passed` texts. Then a real Codex run of the agent case wrote true evidence that ended with "The fake matches the observed id/mobile_no schema", and the first build refused that line. So a `Passed` text can name the fake, and the rule now asks the agent to say if the reply matched it. A false `Passed` text for a run on a fake stays inside the limit of Decision 4.
7. The word list is fake, mock, stub, test double and in-memory. The word "emulator" is not in it, because a device emulator can run against the real service.
8. The E2E check moves to the new module without a change of its refusals, because `.hooks/plans.py` is at the size limit. Its exemption for a Complete plan with no E2E line is removed in its own commit, on the owner's words of 2026-11-14 to remove old code in touched files. A survey of the installed projects on this machine found 0 of 15,784 Complete plans without the line.
9. The exemptions for the Surface, Same cause and Retro lines stay, because thousands of old Complete plans in the installed projects lack those lines.
10. The line has three forms and no form for a run after the deploy. A run that is possible only on the released service is a decision for the user, with the skip form.
11. The rule limits the run: only a test account that the user or the project's rules name, never production, payments only in test mode, and the records of the run removed. The run is by hand or a one-time command, so the rule that tests never call the real service stays true.
12. A reader that did not write the text compared the old and the new prose of the rule entry, the two skills, the test guide, the plan checks reference, the template and the refusal messages. It gave 21 findings, then 2 on a second pass. Each one is repaired: the safety limits of the run, the run outside the test suite, the wider trigger, the help text on each refusal and shorter sentences.
13. The independent review of the first candidate gave 4 findings. Two are repaired: a local tool is not an outside service, and a placeholder after the service name is refused. One is this record of the reader (Decision 12). One is declined below.

Review declined: an older Complete plan with no E2E line now fails when it is selected, in a project outside the survey :: by decision of the owner on 2026-11-14 to remove old code with no live user. The survey read each of 15,784 Complete plans in the installed projects on this machine and found 0 without the line. The refusal names the missing field, so the repair in such a project is one line.
Review declined: a `Passed` text such as "<service>: pending real service run" passes :: the check reads form only (Decision 4). No word rule separates that text from true evidence such as a pending payment, which an earlier pass of the same review asked to accept. A bare placeholder after the service name is refused.

## Acceptance + steps

- [ ] A plan shaped like the incident, with no real run, a fake as the reason or no service named, is refused at Ready and at Complete → `tests/test_plan_runs.py::test_a_plan_fails_when_its_real_service_run_is_missing_or_a_fake_is_the_reason`
- [ ] A plan with a real run, a planned run at Ready, a reason that the change calls no outside service, or the skip form of the user stays valid → `tests/test_plan_runs.py::test_a_plan_passes_with_its_real_service_run_stated`
- [ ] A Draft with an approval handoff waits for the line, and a Draft with a question does not → `tests/test_plan_runs.py::test_an_approval_handoff_waits_for_the_real_service_line`
- [ ] A Complete plan from before the rule stays valid until an edit → `tests/test_plan_runs.py::test_a_complete_plan_from_before_the_real_service_rule_stays_valid`
- [ ] The rule has one entry that names the code that builds its request or reads its reply, names the transaction and the fields that the service fills in, tells an empty field apart from a missing field, tells the agent to correct the fake when the real reply differs, and limits the run to a named test account → HE-REAL-SERVICE-RUN
- [ ] The judge of the agent case needs the run on the real tool and a plan line that records it → `tests/test_agent_checks.py::test_outside_service_needs_a_fake_backed_journey_and_one_real_run`
- [ ] A real agent on each client runs the real tool one time and records the run on the line → N/A — a model run is not a suite test; the result of the outside-service case on each client goes into Verification
- [ ] The E2E check keeps its refusals after the move → `tests/test_plans.py::test_runtime_journey_cannot_disappear_behind_nonvisual_ux`, `tests/test_plans.py::test_deployment_journey_keeps_delivery_open`
- [ ] An unchanged Complete plan with no E2E line is refused, because the exemption is removed → `tests/test_plan_runs.py::test_an_unchanged_complete_plan_with_no_e2e_line_is_refused`
- [ ] The check adds no measurable time to the gate → N/A — a timing is not a suite test; forced runs of the plan check on both versions go into Verification
- [ ] The new texts and fixtures hold no client data → N/A — a search of the outgoing text before the push, recorded in Verification
- [ ] The owner gets the decision for each of the three gaps, with the reason for each choice and its limits, and a rule text and a test idea for the project-only parts → N/A — a chat reply and the pull request text, not code

## Baseline + execution

Result: Passed
Evidence: the starting code is the base branch at 3445b551, and the Hard Eng check run of that commit passed.
Execution: one builder; the new tests first, then the module, the texts, the focused tests, the static gates, a second reader, the independent review and the agent case on both clients.

## Risks + recovery

- A true reason that names a fake as its subject, such as a change of the fake's own documents, is refused. The message says why, and the reason can name what the change calls.
- Each new plan in each installed project needs the line after the update. An older Complete plan stays valid.
- Recovery: revert the commits of the pull request, newest first; no data step.

## ux_reference

N/A — no screen changes; the change is a plan line, a check and rule text.

## Verification

Result: Pending
Evidence: Pending — the focused tests, the static gates, the timing, the review and the agent runs.
E2E: N/A — no user journey of an app changes; the plan check runs through its real command in the tests.
Real service: N/A — the change calls no outside service; the agent case runs a local tool that stands for one.
Retro: Pending — written at the task end.

Delivery target: Merge
Delivery: Pending — the pull request into `develop`, its checks, the release pull request into `main` and the release run.
