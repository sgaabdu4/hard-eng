# The review asks for a send limit in unattended code, and the real run covers a refusal

Status: Complete

## Outcome + scope

A review of a change to unattended code follows the failure path to each send and reports a send with no limit. The real run of a changed call also causes each refusal that the code handles. Non-goals: a gate check that finds senders in code; a new plan line; a change of a project's provider accounts or deploy workflow; an audit of the senders that a project already has.

## Sources + coverage

Sources: the problem report that the owner pasted on 2026-11-14 about alarm emails with no limit, read in full.
Reviewer: a second reader read the report and this plan, not the notes of the builder. It made its own list first, then gave 18 findings. Repaired: rows for retries, for the limits of the refusal case, for the account wording, for the audit and for the agent case; the place of each yes, which was the report and is now the owner's standing words; a proof case for seed data and one for the refusal; the wording of the privacy line; the fixed branch of the update PR. The test data sentence of the rule named a production account and now names an account that a production app uses. Not repaired: the steps for the project stay in the reply, as the part of the answer that is outside Hard Eng.
Deliverables: None

- Outcome, decide whether Hard Eng should change, and where: In scope — The owner gets the decision for each point of the report
- Rule, the report: add nothing about the project's name, data or files: In scope — hold nothing about the project's name, data or files
- Rule, the report gives the problem and no fix: Proposal — each rule of this plan is the builder's own choice and has a `Proposal` row below; yes — user, chat of 2026-11-11 (the builder makes the decisions that the work needs and does not wait) and `AGENTS.md` (the design of this codebase is the agent's call)
- Role, the owners that the alarm emails after each failed run of the timed job: In scope — a timed job that emails its owners
- Rule, the report: no rule, check or review step asked how often automated code (timed jobs, retries, alarms) can send email, notifications or other paid or limited messages: In scope — The review method has one line for unattended sends
- Rule, the report: nothing asked what happens when that code fails on every run: In scope — a limit that holds when each run fails
- Rule, the report: no rule asked whether test or staging data can send real messages through a shared, limited provider: In scope — seed data with made-up addresses that a real send can reach
- Example, the report: the staging seed made test people with reserved test addresses, and each bounce counted against the limit: In scope — seed data with made-up addresses that a real send can reach
- Example, the report: the backend refused a duplicate row at commit, and the hand-made fake refused at create: In scope — cause each refusal that the changed code tells apart by its error
- Rule, the report: nothing checked that the fake came from real responses: Proposal — no machine check of a fake against the service, because that check needs the service in the gate; HE-REAL-SERVICE-RUN, merged on 2026-11-14 after the incident, makes each plan state the real run, and this change adds the refusal case; a form check cannot prove the run; yes — user, chat of 2026-11-11 (the builder makes the decisions that the work needs and does not wait) and `AGENTS.md` (the design of this codebase is the agent's call)
- Example, the report: several apps share one provider account with a daily limit, and a user of another app could not sign in: Proposal — project only: Hard Eng cannot see a provider account; the owner gets the step for the project, one account or one key with its own limit for each app and each environment; yes — user, chat of 2026-11-11 (the builder makes the decisions that the work needs and does not wait) and `AGENTS.md` (the design of this codebase is the agent's call)
- Example, the report: each PR deploy reseeds staging, so the failure came back after each PR run, also after a Hard Eng update PR: Proposal — project only: the deploy workflow belongs to the project; a Hard Eng update PR comes from the fixed branch `hard-eng/update`, so that workflow can skip the reseed for it; the send limit removes the harm of a failure that comes back; yes — user, chat of 2026-11-11 (the builder makes the decisions that the work needs and does not wait) and `AGENTS.md` (the design of this codebase is the agent's call)
- Rule, the send rule lives in the review method and has no plan line and no gate check: Proposal — a script cannot tell which code sends in each project and each language, and a plan line costs each plan of each project one more line for a rare case; yes — user, chat of 2026-11-11 (the builder makes the decisions that the work needs and does not wait) and `AGENTS.md` (the design of this codebase is the agent's call)
- Rule, the limit is a maximum number of sends for each period, its count lives outside the run, and a send that answers one outside event can have one send for each event ID that stays the same in a later run: Proposal — a count inside the run starts again at each run, which is the incident, and an ID that is new in each run limits nothing; yes — user, chat of 2026-11-11 (the builder makes the decisions that the work needs and does not wait) and `AGENTS.md` (the design of this codebase is the agent's call)
- Rule, a change to unattended code is followed to each send, also to a send in code that the change did not touch: Proposal — in the incident the alarm was older code, and the change that broke the job did not touch it; yes — user, chat of 2026-11-11 (the builder makes the decisions that the work needs and does not wait) and `AGENTS.md` (the design of this codebase is the agent's call)
- Rule, a retry inside a request that a person waits for is outside the send rule: Proposal — that retry ends with the request, so it cannot repeat with no person present; yes — user, chat of 2026-11-11 (the builder makes the decisions that the work needs and does not wait) and `AGENTS.md` (the design of this codebase is the agent's call)
- Rule, the real run causes each refusal that the code tells apart by its error, with test records only; a general server error is outside, and so is a refusal that can harm other users of the account, such as a rate limit: Proposal — an agent cannot cause a server error, and a rule that tells an agent to cause a refusal needs these limits; yes — user, chat of 2026-11-11 (the builder makes the decisions that the work needs and does not wait) and `AGENTS.md` (the design of this codebase is the agent's call)
- Rule, the provider account of a production app gets no send from test data or staging data; a sandbox, a capture mode and an account that no production app shares are allowed: Proposal — the limit belongs to the account, so the rule names the account, and the real run of a changed send call stays possible; yes — user, chat of 2026-11-11 (the builder makes the decisions that the work needs and does not wait) and `AGENTS.md` (the design of this codebase is the agent's call)
- Rule, this change holds no audit of the senders that a project already has, and no permanent agent case: Proposal — the audit is a step for the project, which the owner gets; a permanent case costs model time in each later run; yes — user, chat of 2026-11-11 (the builder makes the decisions that the work needs and does not wait) and `AGENTS.md` (the design of this codebase is the agent's call)

## Repository context

Owners: the HE-REAL-SERVICE-RUN entry and the new HE-SEND-LIMIT entry of the requirement registry; the review method of Code Review, which the independent review of each big change applies.
Same cause: the cause is a question that no stage asked. Plan, build and review each followed the good path of a change, and no text asked what unattended code sends when each run fails. Searched the skills for other questions about a failure that repeats: HE Plan asks for the failure and recovery outcomes of a flow, and the challenge assignment names a retry failure; none names a send. Earlier fix of the same kind: HE-REAL-SERVICE-RUN (helped: its agent case showed that agents do the real run). The fake that refused at the wrong call is the same cause as that rule's first incident, a fake with a wrong assumption, in the refusal path that one good run does not reach.
Single source: the send rule lives only in the HE-SEND-LIMIT entry, and the review method names the ID. The refusal case lives only in the HE-REAL-SERVICE-RUN entry.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: Autonomous. The owner pasted the report on 2026-11-14 as the request, and gave full authority for design, merge and release.
Decisions:

1. The fake of the incident was wrong about a refusal: the service refused at commit, the fake at create. The real run rule asked for one journey through each changed call, and a good run makes no duplicate. So the rule as merged did not reach this bug. It now tells the agent to cause each refusal that the code tells apart by its error, and to compare which call refuses.
2. A refusal that the code does not tell apart, such as a general server error, is out of the rule, because an agent cannot cause it. A refusal that can harm other users of the account, such as a rate limit, is never caused.
3. The send rule is a review rule. A script cannot find the senders of each project, and a wrong answer on a plan line passes a form check. The independent review reads the diff and the code around it, so it can follow a failure path. The limit of that choice: a small change has no independent review.
4. The rule also covers a sender that the change did not touch. In the incident the alarm was older code. A rule for new senders only does not reach it.
5. The limit of the review: it runs when a change touches unattended code or what starts it. A sender that no later change touches is never read. The owner gets a one-time audit step for the project.
6. Test data and staging data are in the same entry, because the same reviewer follows the same send. The entry allows a send to a sandbox or to an account that no production app shares, so the real run of a changed send call stays possible.
7. The shared provider account and the reseed on each PR deploy stay in the project. Hard Eng cannot see a provider account, and the deploy workflow is the project's file.
8. The independent review of the first candidate gave 3 findings, and each is repaired in the rule text: an event ID that is new in each run limits nothing; a change to code that sends also starts the test data question; a send in capture or sandbox mode is no finding.
9. No permanent agent case is added. The review cases ran on each client, before and after the rule text, from a script outside the repository. A permanent case costs model time in each later run, and the suite file is at its size limit.
10. The outside-service case of the agent suite already holds a refusal that the code tells apart: an unknown ID. So that case, run on the new text, shows if an agent causes the refusal on the real tool. Its judge stays as it is.

## Acceptance + steps

- [x] The rule for the real run tells the agent to cause each refusal that the changed code tells apart by its error, with test records only, and to compare which call refuses with the fake → HE-REAL-SERVICE-RUN
- [x] A real agent on each client causes the refusal of the fixture's real tool one time and names it on the `Real service:` line → N/A — a model run is not a suite test; the result of the outside-service case on each client goes into Verification
- [x] The review method has one line for unattended sends, and the rule entry asks for a limit that holds when each run fails → N/A — rule text with no suite test; the registry check refuses the entry when no skill links it, and the review cases in Verification show what reviewers do with it
- [x] A real reviewer on each client reports an alarm with no limit, in a change that adds the alarm to a timed job that emails its owners and in a change that only touches that job → N/A — a model run is not a suite test; the result of the review cases on each client, before and after the rule text, goes into Verification
- [x] A real reviewer on each client reports seed data with made-up addresses that a real send can reach → N/A — a model run is not a suite test; the result of the seed case on each client, before and after the rule text, goes into Verification
- [x] The new texts and the pull request text hold nothing about the project's name, data or files → N/A — a search of the outgoing text before the push and before the pull request, recorded in Verification
- [x] The owner gets the decision for each point of the report, with its limits and the steps for the project → N/A — a chat reply and the pull request text, not code

## Baseline + execution

Result: Passed
Evidence: the starting code is the base branch at 88e01e58, and the Hard Eng check run of that commit passed. Before the rule text, the three review cases ran 2 times on each client: Codex reported the alarm with no limit in 0 of 4 runs, and Claude in 2 of 4, both in the change that adds the alarm and none in the change that only touches the timed job.
Execution: one builder; the base runs of the review cases first, then the texts, a reader of the prose, the registry and skill text tests, the review cases on both clients and the independent review.

## Risks + recovery

- A reviewer can report a limit for a send that needs none, such as one receipt for each payment. The entry allows one send for each event ID for that case.
- Recovery: revert the commits of the pull request, newest first; no data step.

## ux_reference

N/A — no screen changes; the change is rule text.

## Verification

Result: Passed
Evidence: the registry check, the three skill text test files with 33 tests and the shipped format gate passed. Review cases, 2 runs for each case on each of 2 clients, each report read by hand. Before the rule text, on the base branch: 2 of 4 reviews reported the alarm with no limit in the change that adds the alarm, 0 of 4 in the change that only touches the job, and 3 of 4 reported the real sends from seed data. With the rule text: 4 of 4, 4 of 4 and 4 of 4. The control case has a limit of one alarm in 24 hours that starts again after one good run. 0 of 8 reviews reported it as an alarm with no limit. 2 of 8, one before and one after the rule text, reported that this limit does not hold when runs fail and pass in turn; the entry gave two answers for that case and now says that the maximum for the period always holds. 1 of 8 reported a race of two runs. The review cases ran before the last rewordings: the alarm cases before the test data sentence changed, and all cases before the repairs of the independent review. The sentences that the alarm cases rest on did not change. Refusal: the approval of the outside-service case names one test patient. Before the refusal sentence, 0 of 6 runs of that case named a refusal on the `Real service:` line. With the final text, 2 of 2 runs, one on each client, named the unknown-ID refusal there as not caused, with that reason. In a variant with an approval for an ID that does not exist, both agents caused the refusal on the real tool and recorded it. Both did the same with the old text, so the variant shows no effect of the rule: the wider approval alone was enough. A reader that did not write the prose read it 4 times and gave 17, then 6, then 3, then 4 points. Each is reworded, except three that stay on purpose: a cap for paid sends that have an event ID, how code tells one fault from the next, and an exception for sandbox mode in the safety sentence of the real run rule, which stays strict. A search of the outgoing text for private words found 0.
E2E: N/A — no user journey of an app changes.
Real service: N/A — the change calls no outside service; it changes rule text.
Retro: (1) The second reader of the plan found that each `Proposal` row named the report as the place of the yes, the second time in two plans → HE-SOURCE-COVERAGE, whose reader step caught it; the rows now name the owner's standing words. (2) The review cases started before the second reader of the plan had answered, and two rewordings of the test data sentence came after → the build step: start model runs after both readers, not only after the prose reader. (3) The word test in the run script judged 5 of 24 reports wrong → None — a script outside the repository, and each report was read by hand. (4) The first plan row for test data copied a sentence of the new entry → None — the registry check refused it before the commit. (5) The gap of the report itself: no review step asked about a send that repeats → HE-SEND-LIMIT, and the base runs of the review cases show the miss before the rule text. (6) The Stop check refused an acceptance line that named the guidance rule as its proof → None — the Stop check caught it before the commit, and the builder's plan helper now runs the same stage check.

Delivery target: Merge
Delivery: Pending — the pull request into `develop`, its checks, the release pull request into `main` and the release run.
