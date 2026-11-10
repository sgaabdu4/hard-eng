# Schedule, roles + models

Load in every run, for the schedule check, and to start a worker. Use the section for the host that runs the coordinator. Unattended runs cannot answer prompts: allow the script, git and network access in that host's project permissions, then prove it with one manual run of the same command.

## T3 Code

- Start = a new thread on the project's main checkout (Local), never a new worktree, on the `coordinator` role's model; run the skill once.
- Schedule = one interval task bound to this thread, titled `timer`, every `timing.everyMinutes`. Its prompt is only "Run the trello-coordinator skill.". Never set it to `enabled: false`.
- Schedule check = in every run, after the worktree check and before `probe`: call `list_scheduled_tasks` and use only tasks bound to this thread. Call it in scheduled runs too, even though the tool text says not to. Only this step and the [claim stop](#another-machine-holds-the-claim) change `timer`. Do these steps in order:
  1. An interval task with that prompt and another title, or no title, came from an older release → give it the title `timer`. Two or more interval tasks with that prompt → keep one as `timer` and delete the others with `delete_scheduled_task`.
  2. No `timer` → create it. `timer` turned off, or its `everyMs` is not `timing.everyMinutes` × 60000 → set `enabled: true` and that `everyMs` now, with its `scheduledTaskId`. Its next run then comes one interval from now, not at once.
  3. A task titled `wake` or `alarm` came from an older release → delete it with `delete_scheduled_task`. After deleting `wake`, tell the owner once to delete the board's Trello Automation rule that sends each comment to a URL.
  4. A run that created `timer` or changed its `everyMs` → tell the owner once how often the coordinator now runs.
- Workers = `delegate_task` with `target.providerInstanceId` = the role's `provider` (none set → the coordinator's own provider) and `target.model` = its `model`, `isolation: "worktree"`, `clientRequestId` `card<N>-r<round>`. Follow-ups = `t3_thread_send` to the worker's thread. Mixed Claude + GPT roles work here.
- Builder after a planner on the same card = `delegate_task` without `isolation`; the brief names the planner's worktree path from `handover.md` and says to work only there. Start it only after the planner has ended.
- Stalls = read worker threads; follow each task's own wake-up instead of polling. Cancel = `task_cancel`.

### Another machine holds the claim

`check` printed `heldElsewhere` → the coordinator runs on another machine now. Before you end the run, delete this host's `timer` (T3 Code: `delete_scheduled_task`; Claude Code: stop the `/loop` or remove the OS timer; Codex: remove the OS timer). Then tell the owner once, with the `heldSince` time. This host stays off until the owner orders a move back.

Move to a new machine = only on the owner's order, on the new machine, in this order:

1. Save the key and token there ([missing key or token](#missing-key-or-token)).
2. Run `takeover`; it prints `tookOver`.
3. Set up this host's schedule from its section in this file (T3 Code: run the skill, and its schedule check creates `timer`).

The old machine stops by itself at its next `check`. A dead machine needs the same three steps. The posted log does not hold every comment the old machine posted, so some can look like the owner's. Before you answer, read every card with a comment from the owner's account after `previousSaved` when `takeover` printed `memoryRestored: true`, else after `previousSince`.

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

- Missing key or token = no popup here: stop and tell the person the Key or Token steps above, with this last step in place of the paste: save the value alone in a file outside the repository, do not paste it into the chat, and give the file's path. When the person gives a path: `save-secret <name> <file>`, then `probe`. After `probe` passes, the person deletes each such file. `save-secret` refuses a file → say what was wrong and ask for a new file.

## Codex

- Schedule = an OS timer runs `codex exec "Run the trello-coordinator skill." < /dev/null` from the repository root; Codex has no built-in schedule.
- Workers = Codex subagents with the role's model, continued from handover notes across runs. OpenAI models only. Missing key or token = as in Claude Code.

## Roles + models

- `trello.json` `roles` = the coordinator's model per role, each with a `why`, written for the host that runs the coordinator; they override the project's general model-role rule for coordinator workers. No `roles` → use the default split with this host's own models. Default split: coordinator = strongest model, open-ended routing and judgment on every card; planner + reviewer = strongest model, judgment; builder = mid model, carries out a clear plan; lookup = fastest model, reads and reports; computerUse = the host's computer-use model, needed to check signed-in screens.
- A role's model unavailable on this host → say so and stop that role's work; never substitute another model. Moving the coordinator to another host = edit `roles` for that host first.
- Model change = edit `trello.json`; running workers finish on their old model.
- Timing and chase hours come from `trello.json` `timing`.
