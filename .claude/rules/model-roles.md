# Subagent models by role

- Using subagents is optional; decide per task. These rules apply only when you use them.
- Planning, research, investigation and review subagents run on Opus: `model: "opus"`.
- Implementation subagents (writing or changing code, mechanical edits, carrying out an agreed plan) run on Sonnet: `model: "sonnet"`.
- Workflow scripts follow the same split in every `agent()` opts object. Never leave a subagent on the default model.
- Don't stop or restart running agents just to change their model.
