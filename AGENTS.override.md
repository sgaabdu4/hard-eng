# Building Hard Eng

These instructions apply only to work on this source repository. Do not install this file into target projects. Read `AGENTS.md` for the shared engineering rules; the rules below govern this rebuild.

- Before adding files, dependencies or machinery, state the current requirement and why the existing code or a direct command is insufficient. Keep each implementation minimal.
- Skill creation and revision = follow [Writing Great Skills](.agents/skills/writing-great-skills/SKILL.md), including review of existing skill packages. Use it as the authoring guide instead of Skill Creator; leave the bundled Skill Creator package installed.
- Tick a box only after its behavior is implemented and meaningfully verified. Keep external or unsupported acceptance gaps explicit.
- Review the diff for unnecessary additions and report all changes, actual tests and remaining gaps at the end.
- Keep source-repository instructions separate from the scaffold distributed to target projects.
- Do not commit, push, install globally or change other projects without explicit approval.
- Before merging a PR, after its CI passes: `python3 release_canary.py <PR head SHA> --post-status` tries the release on every installed project with each project's own updater and CI check. A failure in project code → fix that project in its own PR and merge it; change Hard Eng only for a fault in Hard Eng's own code. A project that already fails on the current release does not block the merge; fix it the same way. Rerun with `--project OWNER/NAME`, then the full run. The posted commit status is the record; do not commit the result to a plan. Results and project names stay on this machine.
