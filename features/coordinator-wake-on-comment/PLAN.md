# Coordinator wakes on a board comment and pauses when the board is quiet

Status: Complete

## Outcome + scope

On T3 Code, a stakeholder comment starts a coordinator run through a webhook task; after `timing.idleStopMinutes` quiet minutes the interval timer pauses (slows to once every `chaseHours`), and a one-time alarm keeps chases, promises and due dates. The same change adds five coordinator rules from a review of a consumer coordinator's mistakes, and fixes three consumer bugs: on a long-lived branch, Complete plans written before the `Single source:` and `Retro:` fields failed once the project updated Hard Eng; the Stop hook counted different lint findings as one repeat; and the hot-path rules first ran at the Complete check. Non-goals: wake on hosts other than T3 Code, Trello REST webhooks, changing the consumer's own coordinator rules.

## Repository context

Owners: `.agents/skills/trello-coordinator/scripts/trello_board/report.py` (report fields), `board.py` (newest stakeholder comment from the fresh read), `commands.py` (`check` state), `config.py` (`timing`), `references/hosts.md` (schedule), `references/run.md`, `references/commands.md`, `SKILL.md`; tests in `tests/test_trello_report.py`, `tests/trello_fakes.py`, `tests/test_trello_coordinator.py`. Bug fixes: `.hooks/plans.py` (`newer_fields`, `touched_since_update`), `.hooks/failures.py` (`repeat_note`), `.hooks/hot_paths.py` (`scan_all`), `.hooks/hard-eng.py` (`hot-paths` paths), `.agents/skills/he-build/SKILL.md` (focused checks).
Bug evidence: the consumer's report reproduced as `plan needs one 'Single source:' field, found 0` on an untouched old plan. A reviewer ran two different ruff findings through `repeat_note` and got "seen 2 times". `gate_schedule.py` keeps `security` out of the Stop hook's quick gates, and HE Build's focused checks named no Semgrep run. Two other reported items were not Hard Eng faults: `landed_commit` keeps only Hard Eng's own update commit by design, and Semgrep's partial parse of `abstract: string;` is printed and does not fail the gate.
Evidence: T3 webhook tasks take `filters` and `dedupe.coalesceKey`. A live test on 2026-11-09 showed T3 refuses fixed text as the key ("Expected <filter>") and accepts `{{body.board}}`; with the Trello payload's fixed `board` value, a request from the filtered account started no run, two quick requests from another user started one run, and that run's prompt reached the busy thread after its turn ended. So a comment that lands between `check` and the pause check starts a run after the current run ends. Trello REST webhooks need a HEAD check that the T3 relay refuses, so the owner adds a Trello Automation rule that posts the commenter's username. Trello's free plan allows 250 Automation runs a month per workspace.
T3 facts, tested with throwaway tasks on 2026-11-09: a task that never ran shows `lastRunStatus` `never`, and `succeeded` after a run; turning a paused interval task on sets its next run one interval later, with no run at once; T3 refuses a one-time task whose time has passed; a one-time task due while its thread was busy still ran and showed `succeeded`; a spent one-time task stays enabled with no next run; with no `clientRequestId`, a new task gets a fresh id; changing an interval task's `everyMs` sets its next run one new interval from now, both slower and faster; a one-time task's prompt that came due during a busy turn reached the thread after that turn ended.
Same cause: the old hosts rule reset the timer on every run, so any self-pause was undone; it is replaced, not patched. The five rules come from 18 quoted mistakes in a consumer coordinator thread on 2026-11-08 and 2026-11-09.
Single source: the Hard Eng marker path `.hooks/hard-eng-source.json` had seven copies (`update.py`, `debt.py`, `hot_paths.py`, `plans.py`, `release_history.py`, `setup.py`, `release_canary.py`); all now use `gate_config.SOURCE_FILE`, which every hook already loads. `idleStopMinutes` lives in `config.TIMING_HOURS`, and the docs test reads its row from there; the wake fields live in `report.WAKE_FIELDS`, which the docs test and the report tests read; promise and chase due times come from `promise_due` and `oldest_unanswered`, which both the lists and `nextDue` use. Searched `.agents/skills/` and `tests/` for `everyMinutes`, `promiseHours`, `chaseHours`: no other copy.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: the maintainer approved the comment wake and quiet pause on 2026-11-09, relayed from another thread. In this thread the maintainer chose the alarm before a pause, asked for the five review rules in the same PR, and sent the plan-field bug report.
Decision: `idle` = quiet for `idleStopMinutes` and no `requests`, `owner`, `promises`, `silent` or `buried` item. Persistent lists (`testQueue`, `realCases`, `overdue`) do not keep the board awake.
Decision: `nextDue` is never later than `chaseHours` from now, so a paused coordinator still wakes daily. That covers card moves and new cards with no comment, real-case checks, and a stopped Trello rule.
Decision: a run pauses only when it posted nothing, moved no card and changed no date, so `nextDue` is never older than the run's own changes.
Decision: the token's own comments never count as heard, matching the wake filter; the owner's comments do not wake the coordinator.
Decision: `timer` pauses only after `wake` has run once, so a board whose Trello rule is not set up keeps its timer.
Decision: pause = `timer` slows to once every `chaseHours`; it is never turned off. Every run sets it back to full speed before `probe`, and only the step before `finish` slows it, after a new `alarm` returns a future time. A run that fails before its first step, or an `alarm` that never runs, still leaves a run within `chaseHours`.
Decision: an old plan is legacy when its newest commit's author date is before the newest commit that changed the Hard Eng marker. Known limit: a plan written on a branch after the base got the update, but before the branch merged that update in, still has to add the fields.
Decision: while paused, project health (error tracker, CI, release state, background jobs) is checked only when a comment, an alarm, a worker or the slow `timer` starts a run, so an outage can wait up to `chaseHours`. This follows from pausing; the maintainer is told in the PR.
Decision: an existing interval task bound to the coordinator thread becomes `timer`; if it is turned off, the next run's schedule check turns it on.

## Acceptance + steps

- [x] The board is idle only after the stop time, with nothing to answer → `tests/test_trello_report.py::test_the_board_goes_idle_only_after_the_stop_time` (59 minutes awake, 61 idle).
- [x] An unanswered request keeps a quiet board awake → `tests/test_trello_report.py::test_an_unanswered_request_keeps_a_quiet_board_awake`.
- [x] Our own comments never count as heard → `tests/test_trello_report.py::test_our_own_comments_never_count_as_heard`.
- [x] `nextDue` is the earliest future promise, chase or due date, never beyond `chaseHours` → `tests/test_trello_report.py::test_next_due_is_the_earliest_promise_chase_or_due_date`, `tests/test_trello_report.py::test_next_due_is_a_chase_and_never_beyond_chase_hours`.
- [x] A Complete plan untouched since the project's last Hard Eng update skips `Single source:` and `Retro:`; a later edit, committed or not, binds them → `tests/test_planning_handoffs.py::test_a_plan_untouched_since_the_hard_eng_update_skips_the_newer_fields`.
- [x] Two different lint findings are not one repeat failure → `tests/test_stop_checks.py::test_different_lint_findings_are_not_one_repeat`.
- [x] `hot-paths` scans only the files it names, so HE Build can run it as a focused check → `tests/test_hot_paths.py::test_a_focused_scan_reads_only_the_named_files`.
- [x] The reference lists every timing field and report field → `tests/test_trello_coordinator.py::test_cli_matches_the_reference_contract`.

## Baseline + execution

Result: Passed
Evidence: `develop` 1b3fe5bb, the rebase base, passed its push runs on 2026-11-09; the branch started from c2fa3c57, which passed Hard Eng and Canary the same day.
Execution: this session, one builder; Reader passes by fresh subagents.

## Risks + recovery

- Trello's free plan allows 250 Automation runs a month per workspace; past it, comments stop waking the coordinator. Recovery: `nextDue` is never more than `chaseHours` away, so the alarm still wakes it, and the owner was told the quota at setup.
- Not checked: whether Trello's "post to url" sends the payload as JSON, and whether `{username}` fills in for a comment trigger. The T3 side was tested with curl only; a request with no `user` field started no run, so a payload Trello sends without it never wakes the coordinator and `timer` stays at full speed. Either failing leaves `wake` without a working filter or never running; the 24-hour alarm and the rule that `wake` must have run before a pause keep the coordinator working.
- Not checked: whether T3 runs a one-time `alarm` late or drops it when its time passes while the Mac sleeps or T3 is closed. If it drops it, a promise or due date waits for the slow `timer`, at most `chaseHours`.
- Not checked: whether T3 holds an interval run that came due during a busy turn after its `everyMs` changed. If it does, a pausing run longer than `everyMinutes` gets one extra quiet run, which slows `timer` again; this repeats only while quiet runs keep taking longer than `everyMinutes`.
- The webhook URL holds its token; anyone with it can start a run, and the run reads the board itself. Recovery: delete and recreate `wake`.

## ux_reference

N/A — no app screens; coordinator skill text and its script only.

## Verification

Result: Passed
Evidence: On 2026-11-09 each new test failed first: no `idle` field; `found 0` for the old plan; "seen 2 times" for two lint findings. Then passed: `tests/test_trello_report.py`, `tests/test_trello_board.py`, `tests/test_trello_coordinator.py` (122); the plan, update, debt, hot path and canary tests (359); `tests/test_stop_checks.py` and `tests/test_failures.py` (37); the hot-path scan tests (3); `python3 .hooks/hard-eng.py hot-paths .hooks/plans.py` printed 0 findings. Reader pass 1 found six ways a paused coordinator could miss work; each was fixed. Reader pass 2 found that an alarm run which posted something left `timer` paused with no new alarm; every run now ends either paused with a fresh alarm or with `timer` on. Its eight reread sentences were reworded. Reader pass 3 found that a run which stopped early left `timer` paused with no alarm, and that the old order paused `timer` before the `alarm` was set; the schedule check now turns `timer` on first, and the pause sets `alarm` first. Its four reread sentences were reworded, and the end step is now named "Pause check" to match `run.md`. Reader pass 4 found that an `alarm` run which failed before its first step, or which skipped the task list, still left `timer` off with a spent `alarm`; a paused `timer` now slows instead of stopping. Its nine reread sentences were reworded, and `wake` is now made right after `probe`. Reader pass 5 found no gap longer than `chaseHours`; it found that T3's tool text uses "pause" for turning a task off, so `hosts.md` now says "slowed" and "Never set it to `enabled: false`", and its seven reread sentences were reworded. The skill format check, `biome ci` with `.agents/biome.json`, passed after it reformatted the `commands.md` table.
E2E: N/A — the script has no user journey; the fake board tests run the real `check` command. The wake itself needs a consumer run after release: the first run creates `wake`, and the owner adds the Trello rule.
Retro: these items, each sorted by HE Learn's Retro rows.
- User correction, five times: I ended turns on a finished-task notice ("No response requested") or did not answer, including a 10-hour release stall and "Did you check advisor?" → judgement: `references/run.md` now says a task notice means read the result and act in the same turn; the same rule covers coordinator workers.
- User correction: "I don't understand, explain pls" on the chase question → judgement: the question used internal words; the existing plain-question rule covers it. None new.
- `quietMinutes` first read 0, because card threads drop comments older than our last reply → caught by the new test; the newest stakeholder comment now comes from the fresh read. None new.
- The docs test skipped the `quietMinutes` table row, which had no space before `|` → caught by `test_cli_matches_the_reference_contract`. None new.
- The Complete check failed `shipped-format`: my new `commands.md` rows broke the table layout → caught by the gate; the formatter fixed it. None new.
- Reader passes 3 and 4 found three ways to leave the coordinator with nothing to start it: an early stop, a refused `alarm`, and an `alarm` run that failed at once → caught by the Reader rule; fixed before push by slowing `timer` instead of stopping it. None new.
- The `wake` shape in `hosts.md` came from the tool's schema text, and T3 refused its fixed group key → caught by a live call before push; the existing rule to prove a real call before relying on a tool covers it. None new.
- An earlier `git add -A` moved the `appwrite-backend` skill source pointer → caught by reviewing the branch's file list before push; reverted. None new.
- `pytest -n auto` failed without pytest-xdist → my command slip; outside cause. None.
- `tests/test_planning_handoffs.py::test_native_stop_only_pauses_ready_approval[False]` failed once with "No such file or directory" under a temporary folder, while other test runs were active; it passed alone and in 10 repeat runs → not reproduced, so no cause found. None until it recurs.
- Bug found on the base branch: old Complete plans failed the new fields on long-lived branches, the same class as the earlier `Same cause` break → mechanical: `tests/test_planning_handoffs.py::test_a_plan_untouched_since_the_hard_eng_update_skips_the_newer_fields`.
- Reported Stop hook repeat on different findings → mechanical: `tests/test_stop_checks.py::test_different_lint_findings_are_not_one_repeat`.
- Reported hot-path rules first running at the Complete check → ran too late: HE Build's focused checks now name `hot-paths <touched source files>`.

Delivery target: Merge
Delivery: Pending — PR into `develop` with `hard-eng` and `canary` green, then release.
