# Grill Me Evals

This suite tests whether `grill-me` routes correctly, keeps interviews
one-question-at-a-time, survives compaction via `session_state.md`, and avoids
unneeded UI/design/prototype work.

## Files

- `evals.json` - task-level behavior evals
- `session-regression-evals.json` - focused regressions from real sessions
- `trigger-evals.json` - should-trigger and should-not-trigger prompt set for
  description tuning.
- `validate-evals.mjs` - deterministic suite checks

## Coverage

- Greenfield full and greenfield lite
- Brownfield features
- Simple narrow features
- Understanding/codebase-understanding
- UI-needed vs UI-not-needed routing
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
skill files, and loaded-skill size.

## Model Runs

For full behavioral benchmarking, run each task eval with the current skill and
an old-skill snapshot, then grade each output against its `expectations`.
Use a static review page or `skill-creator` viewer only after outputs exist.
