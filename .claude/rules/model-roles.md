# Subagent models by role

- Using subagents is optional; decide per task. These rules apply only when you use them.
- Model, effort and Codex service-tier defaults live in `.agents/models.json` under `hosts.<host>` (with optional machine-local overlay at `~/.config/hard-eng/models.json` or `$XDG_CONFIG_HOME/hard-eng/models.json`).
- Role split:
  - `reasoning`: planning, research needing judgment, investigation and review subagents.
  - `implementation`: writing or changing code, mechanical edits and carrying out an agreed plan.
  - `lookup`: finding files or code, pulling one fact from a doc, summarizing logs or CI output, simple browser checks (report back only; never write code or make judgment calls).
- Default subagents to the main thread's own host. Cross over to another host only along `subagent_overflow` when hitting quota or rate limits, and return to the primary host once quota resets.
- Workflow scripts follow the same role split in every `agent()` opts object. Never leave a subagent on an unpinned default.
- Don't stop or restart running agents just to change their model.
- Same-task follow-up → message the finished subagent; unrelated task → new subagent.
