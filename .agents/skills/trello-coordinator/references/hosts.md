# Schedule, roles + models

Load to start or change the schedule, or to start a worker. Use the section for the host that runs the coordinator. Only T3 Code wakes on a board comment and pauses when the board is quiet; on other hosts the timer always runs and `idle` changes nothing. Unattended runs cannot answer prompts: allow the script, git and network access in that host's project permissions, then prove it with one manual run of the same command.

## T3 Code

- Start = a new thread on the project's main checkout (Local), never a new worktree, on the `coordinator` role's model; run the skill once.
- Schedule = three tasks bound to this thread, each with the prompt "Run the trello-coordinator skill." and never any webhook request text:
  - `timer`: interval `timing.everyMinutes`.
  - `wake`: `{type: "webhook", filters: [{path: "body.user", op: "notEquals", value: <account>}], dedupe: {coalesceKey: "board"}}`, where `<account>` = `probe`'s `account`. A board comment starts a run; our own comments do not.
  - `alarm`: `{type: "once", runAt: <nextDue>}`, only while `timer` is paused.
- Schedule check = every run, after `probe`, `list_scheduled_tasks`:
  - No `timer` → create it. Its `everyMs` differs from `timing.everyMinutes` → fix it with its `scheduledTaskId`; tell the owner once that a change belongs in `trello.json`.
  - No `wake` → create it. It returns a `webhookUrl` → give the owner that URL and the Trello steps below, once. No `webhookUrl` = T3 Connect remote access is off → tell the owner once; `timer` then never pauses.
  - The first manual run sets these up; tell the owner once.
- After `check`: `skipped` → change no task. `idle: false` and `timer` paused → turn `timer` on (`enabled: true`).
- Pause = at the end of a run, set `timer` to `enabled: false` only when all are true: `idle: true`; no worker of yours is running (a worker's end starts a run); `wake` has run at least once (`lastRunStatus` is set), which proves Trello reaches it. `nextDue` not empty → before the pause, create `alarm` or move its `runAt` to `nextDue`. A paused `timer` is expected: do not report it.
- Trello steps for `wake`, for the owner:
  1. Open the board, click Automation, then Rules, then Create rule.
  2. Add the trigger "when a comment is posted to a card by …"; choose "anyone except me" if offered, else "anyone".
  3. Add the action "post to url" (Content tab), paste the URL, choose "with payload" and enter `{"user": "{username}"}`. Save.
  - Each comment uses one Automation run; Trello's free plan allows 250 a month per workspace. Comments arrive while `timer` is paused and `wake` does not run → the rule or its quota stopped; tell the owner.
- Workers = `delegate_task` with `target.providerInstanceId` = the role's `provider` (none set → the coordinator's own provider) and `target.model` = its `model`, `isolation: "worktree"`, `clientRequestId` `card<N>-r<round>`. Follow-ups = `t3_thread_send` to the worker's thread. Mixed Claude + GPT roles work here.
- Builder after a planner on the same card = `delegate_task` without `isolation`; the brief names the planner's worktree path from `handover.md` and says to work only there. Start it only after the planner has ended.
- Stalls = read worker threads; follow each task's own wake-up instead of polling. Cancel = `task_cancel`.

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
