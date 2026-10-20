# Building Hard Eng

These instructions apply only to work on this source repository. Do not install this file into target projects. Read `AGENTS.md` for the shared engineering rules; the rules below govern this rebuild.

- Complete the remaining `DECISION.md` requirements continuously under the user's 2026-09-09 authorization. Explain each concrete change and its verification; do not stop for per-item approval.
- Before adding files, dependencies or machinery, state the current requirement and why the existing code or a direct command is insufficient. Keep each implementation minimal.
- Skill creation and revision = follow [Writing Great Skills](.agents/skills/writing-great-skills/SKILL.md), including review of existing skill packages. Use it as the authoring guide instead of Skill Creator; leave the bundled Skill Creator package installed.
- Tick a box only after its behavior is implemented and meaningfully verified. Keep external or unsupported acceptance gaps explicit.
- Review the diff for unnecessary additions and report all changes, actual tests and remaining gaps at the end.
- Keep source-repository instructions separate from the scaffold distributed to target projects.
- Do not commit, push, install globally or change other projects without explicit approval.
- Branches: every PR targets `develop`. Only a `develop` → `main` PR releases.
- Before merging `develop` into `main`, after its CI passes, on the maintainer's Mac: `uv run python release_canary.py <develop head SHA> --post-status`. It installs the release in a fresh scaffold for each stack, a greenfield uv project, a pinned public brownfield project and every installed project. Each target must pass its checks, then one Claude and one Codex session must change it and end with a passing Hard Eng Stop check. The run fails if commit messages, the diff or PR text name a private repository. A failure in project code → fix that project in its own PR and merge it; change Hard Eng only for a fault in Hard Eng's own code. A project that already fails on the current release does not block the merge; fix it the same way. Rerun with `--project OWNER/NAME`, `--kind` or `--agent`, then the full run. Results, logs and project names stay on this machine; the `canary` status holds counts only and is the record, so do not commit the result to a plan.
