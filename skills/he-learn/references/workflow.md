# Learning Workflow

1. Resolve affected Git repository → reject global `~/.agents` as destination for repository-specific learning.
2. Read source evidence → reject duplicate, one-off, inferred-only, personal, unrelated, or preference-only candidate.
3. Recurrence claim → `repeated-failure-learning`; otherwise verify engineering correction/false passing check/systemic boundary gap/manual waste.
4. Run `learning_state.py start --repo <repo> ...` → personal/one-off = no record/helper; `helper=he-learn` = spawn exactly one helper; `helper=none` = never spawn another.
5. Select narrowest durable owner:

   `remove cause → reuse/repair owner → invariant/type → regression test → scanner/hook → CI → script/tool`

6. Mechanically detectable gap → executable prevention + violating fixture + valid fixture + actual-seam proof; skill creation = forbidden.
7. No complete deterministic prevention + same root ≥2 → record `deterministic_limit` → create one canonical `<repo>/.agents/skills/<learning-id>/` skill → run `~/.agents/setup.sh repo-install <repo>`.
8. Place proof before the expensive boundary; parallelize independent cheap checks + cancel dependent work on failure.
9. Classify urgency:
   - continued work risks protected boundary → pause affected product path + repair/decision now;
   - all other learning → assign destination + keep product lifecycle moving; one depth-1 `he-learn` helper may execute this workflow.
10. Destination repair uses affected-repository direct/`he` route + its own approvals; source PLAN remains available and unpaused.
11. Run affected regression + `learning_state.py validate --closure --repo <repo>` + `~/.agents/setup.sh repo-check <repo>`.
12. Resolve = prevention revision + proof; deferred = owner + next action; no candidate = `PASS: no learning action`.
