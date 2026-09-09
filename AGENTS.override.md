# Building Hard Eng

These instructions apply only to work on this source repository. Do not install this file into target projects. Read `AGENTS.md` for the shared engineering rules; the rules below govern this rebuild.

- Propose one concrete change, its files and its verification before editing. Wait for approval, then implement only that step. Reuse approval within the agreed scope.
- If the step needs extra files, dependencies, wrappers or abstractions beyond the proposal, stop and explain before expanding it.
- `DECISION.md` records requirements, not blanket permission to implement the whole checklist. Tick a box only after its behavior is implemented and meaningfully verified.
- After the step, review the diff for unnecessary additions, report the actual proof and stop before starting the next change.
- Keep source-repository instructions separate from the scaffold distributed to target projects.
- Do not commit, push, install globally or change other projects without explicit approval.
