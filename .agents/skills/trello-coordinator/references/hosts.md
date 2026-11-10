# Schedule, roles + models

Load in every run, for the schedule check and the pause check, and to start a worker. Use the section for the host that runs the coordinator. Only T3 Code wakes on a board comment and slows its timer when the board is quiet; on other hosts the timer always runs and `idle` changes nothing. Unattended runs cannot answer prompts: allow the script, git and network access in that host's project permissions, then prove it with one manual run of the same command.

## T3 Code

- Start = a new thread on the project's main checkout (Local), never a new worktree, on the `coordinator` role's model; run the skill once.
- Schedule = three tasks bound to this thread. Give each task its name below as its `title`. Each prompt is only "Run the trello-coordinator skill."; never put webhook request text in a prompt.
  - `timer`: interval `timing.everyMinutes`; slowed = interval `chaseHours`. Never set it to `enabled: false`. An older untitled interval task bound to this thread is `timer`: give it the title.
  - `wake`: `{type: "webhook", filters: [{path: "body.user", op: "notEquals", value: <account>}], dedupe: {coalesceKey: "{{body.board}}"}}`, where `<account>` = the `account` that `probe` prints. T3 refuses fixed text as the key; every request carries the same `board` value, so comments close together start one run. A new comment by anyone else starts a run. Our own comments, and the owner's (same account), never start one.
  - `alarm`: `{type: "once", runAt: <nextDue>}`. The pause check replaces it each time.
- Schedule check = in every run, after the worktree check and before `probe`: call `list_scheduled_tasks` and use only tasks bound to this thread. Call it in scheduled runs too, even though the tool text says not to. Only this step and the pause check change `timer`.
  - No `timer` → create it. `timer` turned off, or its `everyMs` is not `timing.everyMinutes` × 60000 → set `enabled: true` and that `everyMs` now, with its `scheduledTaskId`. Its next run then comes one interval from now, not at once. So a run that stops after this step leaves `timer` at full speed.
  - No `wake` → run `probe` first if it has not passed in this session, then create `wake` with the account that `probe` printed. It returns a `webhookUrl` → give the owner that URL and the Trello steps below, once. No `webhookUrl` = T3 Connect remote access is off → tell the owner once; `timer` then never slows.
  - The first manual run sets these up; tell the owner once.
- `check` printed `skipped` → no pause check; `timer` stays at full speed.
- Pause check = the step just before `finish`, in every run that `check` did not skip. Pause only when all are true: (1) `check` succeeded and printed `idle: true`; (2) this run posted nothing, moved no card and changed no date; (3) no worker of yours is running, since a worker's end starts a run; (4) `wake` shows a `lastRunStatus` other than `never`, which proves Trello reaches it.
  - Pause = delete each `alarm` bound to this thread, then create a new `alarm` at this run's `nextDue`. Leave out `clientRequestId`, so T3 gives the new `alarm` a fresh id. When T3 returns a future `nextRunAt` for it, set `timer`'s `everyMs` to `chaseHours` × 3600000, with its `scheduledTaskId`. No future `nextRunAt` → leave `timer` at full speed.
  - Not all four true → do not pause. `timer` stays at full speed from the schedule check.
- `nextDue` is at most `chaseHours` away, and a slowed `timer` still runs every `chaseHours`. So while paused, the coordinator still sees card moves and new cards within `chaseHours`, even when an `alarm` run fails. While paused, project health (error tracker, CI, release state, background jobs) waits for the next run, at most `chaseHours`. A slowed `timer` is normal: do not report it.
- Trello steps for `wake`, for the owner:
  1. Open the board, click Automation, then Rules, then Create rule.
  2. Add the trigger "when a comment is posted to a card by …"; choose "anyone except me" if offered, else "anyone".
  3. Add the action "post to url" (Content tab), paste the URL, choose "with payload" and enter `{"user": "{username}", "board": "board"}`. Save.
  - Tell the owner with the steps: each comment uses one Automation run, and Trello's free plan allows 250 a month for the whole workspace. When the rule stops or its quota runs out, a comment waits for the next `alarm` or `timer` run.
- Workers = `delegate_task` with `target.providerInstanceId` = the role's `provider` (none set → the coordinator's own provider) and `target.model` = its `model`, `isolation: "worktree"`, `clientRequestId` `card<N>-r<round>`. Follow-ups = `t3_thread_send` to the worker's thread. Mixed Claude + GPT roles work here.
- Builder after a planner on the same card = `delegate_task` without `isolation`; the brief names the planner's worktree path from `handover.md` and says to work only there. Start it only after the planner has ended.
- Stalls = read worker threads; follow each task's own wake-up instead of polling. Cancel = `task_cancel`.

### Another machine holds the claim

`check` printed `heldElsewhere` → the coordinator runs on another machine now. Delete this host's `timer`, `wake` and `alarm` (T3 Code: `delete_scheduled_task`; other hosts: remove the OS timer), end the run, and tell the owner once, with the `heldSince` time. This host stays off until the owner orders a move back.

Move to a new machine = only on the owner's order, on the new machine, in this order:

1. Save the key and token there ([missing key or token](#missing-key-or-token)).
2. Run `takeover`; it prints `tookOver`.
3. Run the skill; the host's schedule check creates `timer` and `wake` there.

The old machine stops by itself at its next `check`. A dead machine needs the same three steps; comments posted since its last `finish` can look like the owner's, so read those cards before answering.

### Missing key or token

Ask with `request_secret`, `delivery: "file"`, one value at a time, key first. Then `save-secret <name> <file>` with the file path given, and `probe`. Copy each popup text exactly; fill `<account>` from `trello.json`.

- Key: label `Trello API key`; placeholder `32 letters and numbers`; reason:
  > The Trello coordinator needs your Trello API key. It is saved only on this computer, in a file git never uploads.
  > 1. Open https://trello.com/apps/admin and sign in to Trello as <account>. If Trello asks you to accept the Joint Development Agreement, accept it.
  > 2. Already have an app on that page? Click its name. If not, click New, choose "My app doesn't use Power-Up capabilities", fill in Name (for example Coordinator), Workspace, Email, Support Email and Author, then click Create.
  > 3. Click the Trello Auth tab. If no key shows, click Generate a new API Key.
  > 4. Copy the API key and paste it here.
- Token: label `Trello token`; placeholder `Long code from the Allow page`; reason:
  > Now the token. With it, the coordinator can read and write your Trello boards, so keep it secret. It is saved only on this computer.
  > 1. Go back to the Trello Auth tab from the last step.
  > 2. Click the word Token to the right of the API key.
  > 3. Check that the page shows <account>, then click Allow.
  > 4. Copy the long code on the next page and paste it here.
- `check` or `probe` prints `tokenRefused`: the token is revoked or expired. `firstReport: true` → ask for a new token only, with the Token steps above, then `save-secret TRELLO_TOKEN` and `probe`. `firstReport: false` → the owner already knows; say nothing.
- `save-secret` refuses the paste → ask again with the same text and one line saying what was wrong. `probe` names another account → stop and say which account the token belongs to.

## Claude Code

- In a session = `/loop <everyMinutes>m Run the trello-coordinator skill.`; it stops when the session closes.
- Unattended = an OS timer (launchd or cron) runs `claude -p "Run the trello-coordinator skill."` from the repository root; each run is a new session, so workers continue from their handover notes.
- Workers = subagents with the role's `model` in their own worktree; follow-ups = message the same subagent while the session lives. Claude models only.

- Missing key or token = no popup here: stop and give the same steps, then the two lines to add to `.env.trello.local` in the main checkout.

## Codex

- Schedule = an OS timer runs `codex exec "Run the trello-coordinator skill." < /dev/null` from the repository root; Codex has no built-in schedule.
- Workers = Codex subagents with the role's model, continued from handover notes across runs. OpenAI models only. Missing key or token = as in Claude Code.

## Roles + models

- `trello.json` `roles` = the coordinator's model per role, each with a `why`, written for the host that runs the coordinator; they override the project's general model-role rule for coordinator workers. No `roles` → use the default split with this host's own models. Default split: coordinator = strongest model, open-ended routing and judgment on every card; planner + reviewer = strongest model, judgment; builder = mid model, carries out a clear plan; lookup = fastest model, reads and reports; computerUse = the host's computer-use model, needed to check signed-in screens.
- A role's model unavailable on this host → say so and stop that role's work; never substitute another model. Moving the coordinator to another host = edit `roles` for that host first.
- Model change = edit `trello.json`; running workers finish on their old model.
- Timing and chase hours come from `trello.json` `timing`.
