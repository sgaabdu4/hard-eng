# Agents Routing Evals

This eval suite owns route-change coverage for global agent routing.

Use it for changes that affect:

- `AGENTS.md` skill routing
- `workflow-help`
- Hard Eng stage order and readiness
- `grill-me` planning handoff
- no-mistakes and Ship routing
- vendor skill read-only policy
- specialist skill route choices

Do not add duplicate route eval folders under individual runtime skills unless a skill has behavior that cannot be represented by this shared route-policy harness.

The runner reads the `gpt-5.6-luna` model contract from `evals.json`. Use
`AGENTS_ROUTING_EVAL_TIMEOUT_MS`, `AGENTS_ROUTING_EVAL_CONCURRENCY`, and
`AGENTS_ROUTING_EVAL_OUT_DIR` to change runtime limits or output location.

Run targeted cases with:

```sh
AGENTS_ROUTING_EVAL_CASES=workflow_help_front_door node tests/agents-md-routing/evals/run-evals.mjs
```
