# The CI lookup asks GitHub again after a server error

Status: Complete

## Outcome + scope

When CI asks GitHub if earlier checks cover a commit, a GitHub server error no longer decides the answer. The lookup asks two more times before it gives up. The rule for the real run also says now that the comparison covers the fields that the code reads. Non-goals: a change of the workflow file; a retry of a GitHub call that writes; a change of what counts as covered.

## Sources + coverage

Sources: N/A — the request is the only source: the builder found the fault on the release pull request of 2026-11-14 and told the owner that it repairs it in its own change.
Deliverables: None

## Repository context

Owners: `.hooks/ci_usage.py::reused_pull_request`, which `impact` and `check` both call through `.hooks/gate_runner.py::proven_elsewhere`.
Same cause: the cause is one lookup with one try that decides which path a job takes. On a release pull request the `impact` step asked GitHub, got the answer that earlier checks cover the commit, and chose the light step with no SDK tools. The `check` step then asked again, got HTTP 502, and started a full run that the light step cannot pass. Searched for other callers: `proven_elsewhere` is the only caller, and both steps go through it, so this one repair covers both. Earlier fix of the same kind: none found in the history of `reused_pull_request`.
Single source: the waits and the server error pattern live only in `.hooks/ci_usage.py`.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: Autonomous. The owner gave full authority for design, merge and release, and the builder told the owner on 2026-11-14 that it repairs this fault in its own change.
Decisions:

1. The retry sits in `reused_pull_request`, around the whole lookup. Each call inside it only reads, so a second try cannot write a thing two times. A retry inside the shared `gh` helper would also repeat calls that write.
2. Only a GitHub server error is asked again: an error text that holds `HTTP 5` and two more digits. Each other refusal, such as a different tree or a failed check, is a true answer and stays final.
3. Two more tries, after 2 and 6 seconds. The failed run recovered on a rerun minutes later; a longer wait would hold each job that meets a real outage.
4. Limit: after three server errors the lookup gives up as before. On the light step that still starts a full run that cannot pass, and a rerun of the job is the repair. A second fix that makes the light step stop with a clear message was weighed; it changes the message and not the result, so it is not built.
5. The local import of `os` in `_release_revision` is removed, because the module now imports `os` at the top.
6. The real run of this change showed that the rule for the real run asked too much: it told the agent to compare each field of the reply with the fake. A fake needs the fields that the code reads, not a copy of each field of the service. The rule entry now says that, and it frees the fake from the other fields.
7. A reader that did not write the rule text compared the earlier and the new sentences. It quoted three sentences: the list of fields to find had no limit of its own, "the code" did not say whose code, and the line for a passed run asked for a match of the whole reply. It also asked what "reads" means when the code passes the reply on. Each of the three is reworded, and the entry now says when a passed-on reply counts as read. A second read of the new text quoted three more sentences, each a matter of one term; they are reworded too. The same read confirmed that the limit to read fields now holds through the paragraph. The comparison covers the code of the whole project and not only the changed code, on purpose: tests of other code use the same fake.

Review declined: the test reply still lacks 8 fields of the real reply, and the plan records no values for them :: the lookup reads none of the 8 (`app`, `check_suite`, `details_url`, `external_id`, `html_url`, `node_id`, `pull_requests`, `url`). The rule now limits the comparison to the fields that the code reads (Decision 6). The one field that the code reads and the test reply lacked, `output`, is repaired.

## Acceptance + steps

- [x] A release pull request lookup that gets a GitHub server error two times asks again and reuses the passed checks; a third server error, or an error of another kind, runs the checks again → `tests/test_ci_usage.py::test_a_release_pr_lookup_tries_again_only_after_a_github_server_error`
- [x] Each earlier answer of the lookup stays the same → `tests/test_ci_usage.py::test_a_release_pr_reuses_the_passed_checks_of_the_base_commit`, `tests/test_ci_usage.py::test_a_release_pr_runs_the_checks_when_no_pass_covers_it`
- [x] The rule for the real run limits the comparison with the fake to the fields that the code reads → HE-REAL-SERVICE-RUN

## Baseline + execution

Result: Passed
Evidence: the starting code is the base branch at 9928a83a; pull request 625 passed each of its 25 checks on that same tree.
Execution: one builder; the failing test first, then the repair, the focused tests, the static gates and the independent review.

## Risks + recovery

- A job that meets a real GitHub outage waits 8 seconds more before it runs the checks again.
- Recovery: revert the commit; no data step.

## ux_reference

N/A — no screen changes; the change is one CI lookup.

## Verification

Result: Passed
Evidence: the new test failed first on the earlier code with the real message of the failed run: the lookup gave up after one HTTP 502. After the repair the lookup test file passed with 51 tests, and the focused set of 5 test files passed with 294 tests. After the change of the test reply, each of the 9 test files that use it passed. The six static gates, the duplicates gate and the shipped format gate passed, and the hot path scan found 0. The independent review of the first candidate was clean. The repair adds no time to a lookup that GitHub answers.
E2E: N/A — no user journey changes; the lookup runs inside CI jobs.
Real service: Passed — GitHub API: the changed lookup ran one time for the head of `develop`, in a copy of that commit, with the event of a release pull request. It made one check-runs call, got 11 runs and returned that head. Field by field against the test reply: in each of the 11 real runs the 7 fields of the test reply were present and filled; the status was `completed`, the conclusion was `success` or `skipped`, the two times and the commit were text and the id was a number, as in the test reply. The real reply has 9 more fields. The lookup reads one of them, `output`, which the test reply did not have; in each real run it held an empty title, summary and text, a count of annotations and their address. The test reply now holds `output` in that shape. The lookup reads none of the other 8 fields. Not compared: a run in progress, because none was in reach; the lookup stops at the status of such a run before it reads another field. The failed release run of 2026-11-14 printed "gh query failed: gh: Server Error (HTTP 502)", and the test uses that text.
Retro: (1) The fault escaped to the base branch: no test gave the lookup a GitHub server error → `tests/test_ci_usage.py::test_a_release_pr_lookup_tries_again_only_after_a_github_server_error`, which failed on the earlier code. (2) The first run of the new test failed for a wrong reason, a patch of a module name that did not exist yet → None — corrected before the repair, and the second run failed on the fault itself. (3) The review found that the first real run went through a helper and not through the changed lookup → HE-REAL-SERVICE-RUN, which the review applied; the lookup then ran for real, and the test reply got the `output` field of the real reply. (4) The same review then asked for each field of the reply in the test reply, which the first rule text did ask for → HE-REAL-SERVICE-RUN, whose entry now limits the comparison to the fields that the code reads. (5) This plan copied one sentence of the rule entry → None — the registry check of the Stop hook refused it before the push, and the sentence is reworded. (6) The review found no reader check for the new rule sentences → Writing Great Skills' Reader row, which the builder skipped for a change of four sentences; the reader then ran and its three quoted sentences are reworded (Decision 7). (7) One CI test shard failed on the new test: the test replaced the wait function of the whole process and counted its calls, and other threads on the CI machine also wait → `tests/test_ci_usage.py::test_a_release_pr_lookup_tries_again_only_after_a_github_server_error`, which now replaces only the lookup's own wait and compares the two wait times. A search found one other test that replaces the wait function of the process; it counts no calls, so it cannot fail in this way.

Delivery target: Merge
Delivery: Pending — the pull request into `develop`, its checks, the release pull request into `main` and the release run.
