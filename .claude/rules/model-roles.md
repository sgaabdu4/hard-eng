# Subagent models by role

- Using subagents is optional; decide per task. These rules apply only when you use them.
- Delegate only read-only, parallel or noisy work: search, tests, logs, review. Keep edits in one thread; subagents add cost, and step-by-step coding on shared files gains nothing.
- Planning, research needing judgment, investigation and review subagents run on Opus: `model: "opus"`.
- Implementation subagents (independent parts of an agreed plan, mechanical edits), one writer at a time on shared files, run on Sonnet: `model: "sonnet"`.
- Narrow lookup subagents (finding files or code, pulling one fact from a doc, summarizing logs or CI output, simple browser checks) run on Haiku: `model: "haiku"`. They report back and never write code or make judgment calls.
- Workflow scripts follow the same split in every `agent()` opts object. Never leave a subagent on the default model.
- Don't stop or restart running agents just to change their model.
- SendMessage a finished subagent only when the follow-up needs the context it gathered; otherwise start a new one. Review always uses a new one.
