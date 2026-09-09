# Building Hard Eng

These instructions apply only to work on this source repository. Do not install this file into target projects. Read `AGENTS.md` for the shared engineering rules; the rules below govern this rebuild.

- Complete the remaining `DECISION.md` requirements continuously under the user's 2026-09-09 authorization. Explain each concrete change and its verification; do not stop for per-item approval.
- Before adding files, dependencies or machinery, state the current requirement and why the existing code or a direct command is insufficient. Keep each implementation minimal.
- Tick a box only after its behavior is implemented and meaningfully verified. Keep external or unsupported acceptance gaps explicit.
- Review the diff for unnecessary additions and report all changes, actual tests and remaining gaps at the end.
- Keep source-repository instructions separate from the scaffold distributed to target projects.
- Do not commit, push, install globally or change other projects without explicit approval.
