# Grill Me Evals

This suite tests whether `grill-me` routes correctly, keeps interviews
one-question-at-a-time, survives compaction via `session_state.md`, and avoids
unneeded UI/design/prototype work.

## Files

- `evals.json` - task-level behavior evals
- `session-regression-evals.json` - focused regressions from real sessions
- `stage-routing-evals.json` - quick stage-owner coverage for every Grill Me
  stage/support module
- `trigger-evals.json` - should-trigger and should-not-trigger prompt set for
  description tuning.
- `validate-evals.mjs` - deterministic suite checks

## Coverage

- Greenfield full and greenfield lite
- Brownfield features
- Simple narrow features
- Understanding/codebase-understanding
- UI-needed vs UI-not-needed routing
- UI review receipt capture for React/Storybook and Flutter
  Widgetbook/simulator surfaces, including selected and rejected options
- Visual design/prototype gates
- Backend/API/schema/auth/stateful risk controls
- Existing `CONTEXT.md`/ADR use, missing-doc silence, glossary capture, and
  docs-aware final synthesis.
- Compaction, missing state, unanswered Q, and answer-recording recovery
- Final synthesis for build-plan and understand-only sessions, including
  next-step handoff after `plan.md` is written.
- Trigger near-misses where other skills should win

## Local Check

```bash
node tests/skills/grill-me/evals/validate-evals.mjs
```

This validates eval shape, coverage terms, trigger balance, ASCII-only loaded
skill files, loaded-skill size, and required stage-routing coverage.

## Model Runs

Quick invocation/stage gate:

```bash
node tests/skills/grill-me/evals/run-trigger-evals.mjs
node tests/skills/grill-me/evals/run-stage-routing-evals.mjs
```

All three model-backed runners default to `gpt-5.6-luna`; the two quick runners
should stay fast enough for `--include-evals`.

Long session/regression gate:

```bash
node tests/skills/grill-me/evals/run-mini-evals.mjs
```

This runs task-level conversations and focused session regressions. It is
intentionally allowed to take long because Grill Me asks one question at a time
until alignment. The full-repo gate exposes it through
`--include-session-evals`, not the quick `--include-evals` path. Use
`GRILL_ME_EVAL_TIMEOUT_MS` to raise or lower the per-case timeout.
