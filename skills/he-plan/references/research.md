# Research Stage

Decision inventory = root product/design truth + architecture/owners/callers + current flows/UI/contracts/data/auth + tests/CI/runtime/infra/dependencies/history/observability/rollout conventions.

1. Convert inventory → coverage matrix: inspect | rule out | inaccessible.
2. Delegate bounded current-state questions → `$research`.
3. Verify high-risk claims + negative assertions against native owners; external boundary research covers success + rejection + timeout/ambiguity + transaction scope + idempotency + retry/scheduling guarantees.
4. Compare `PRODUCT.md` + `DESIGN.md` against code/docs/history/assets → classify current, missing, stale, or contradictory.
5. Synthesize current behavior + reusable owners + blast radius.
6. Surface contradictions + limitations + blockers + user-only decisions; code evidence never becomes intended truth silently.

Complete = declared scope covered + citations/revision + every relied-on external guarantee proven or converted to constraint/spike/unknown + no material inaccessible system, contradiction, stale revision, or decision-changing unknown. Skip only when repository evidence cannot affect the requested decision.
