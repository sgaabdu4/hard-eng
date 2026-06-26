# Grill Me Start Routing

1. Infer request profile, mode, and candidate active stage from `SKILL.md` first.
2. If mode/stage is clear, do not load `modules/modes.md`; use the matching shortcut.
3. Load `modules/modes.md` only when depth is unclear, the stage map is disputed, or a formal Stage Map must be written.
4. Load `modules/session-state.md` after a grill-me session starts, before every continuing turn, after compaction/resume, and before final synthesis.
5. Load `modules/orchestration.md` only after a grill-me session starts, when resuming a draft, managing files/handoffs, closing a stage, or writing the final plan.
6. Load `modules/domain-docs.md` only for existing-code/doc-backed sessions, fuzzy domain terms, ADR conflicts/candidates, or doc-update synthesis.
7. Load `modules/questions.md` only before asking an interview question.
8. Load only the active stage module after the stage is selected.
9. Load `modules/stage-handoff.md` only when writing a handoff.
10. Load `modules/final-plan.md` only when synthesizing `plan.md`.
