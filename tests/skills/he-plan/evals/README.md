# he-plan Evals

This suite tests `/he:plan` readiness behavior around Grill Me handoff, task
comment visibility ambiguity, and not-ready exits that must ask the next visible
question instead of parking user-answerable blockers behind `CONCERNS`.

## Files

- `evals.json` - model eval cases and fixture files
- `eval-output-schema.json` - required Codex JSON output shape
- `validate-evals.mjs` - deterministic suite and fixture-shape checks
- `run-mini-evals.mjs` - model-backed runner used by `--include-evals`

## Fixture Rules

Each eval needs a unique integer `id`, non-empty `prompt` and
`expected_output`, and at least four `expectations`. Optional `files[]` entries
must be objects with `path` and string `content`; paths must be relative,
non-empty, and stay inside the generated eval target.

The suite must keep coverage for Grill Me, comments, visibility, delegate,
admin, and not-ready behavior.

## Local Check

```bash
node tests/skills/he-plan/evals/validate-evals.mjs
```

This runs in the default deterministic repo gate and blocks duplicate eval ids,
malformed `files[]` fixtures, missing expectations, and missing coverage terms.

## Model Runs

```bash
node tests/skills/he-plan/evals/run-mini-evals.mjs
node tests/skills/he-plan/evals/run-mini-evals.mjs 1 4
```

The runner copies the local `he-plan`, `workflow-help`, `treehouse`, and
`grill-me` skill bundles into an isolated target, writes each case's fixture
files, runs Codex on `gpt-5.4-mini`, and writes JSON results plus logs under
`/tmp/he-plan-eval-run` by default. It is part of the quick `--include-evals`
lane, not `--include-session-evals`.

Useful environment overrides:

- `HE_PLAN_EVAL_MODEL` - model name, default `gpt-5.4-mini`
- `HE_PLAN_EVAL_CODEX_BIN` - Codex executable, default `codex`
- `HE_PLAN_EVAL_ROOT` - run/result root, default `/tmp/he-plan-eval-run`
- `HE_PLAN_EVAL_RUN_ID` - stable run id for repeatable output paths
- `HE_PLAN_EVAL_TIMEOUT_MS` - per-case child timeout, default `900000`
