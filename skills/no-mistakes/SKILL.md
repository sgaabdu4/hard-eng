---
name: no-mistakes
description: Use for no-mistakes validation, safe push, PR/CI gate, or `/no-mistakes` after committed code changes.
---

# no-mistakes

Use `no-mistakes` when the user asks to validate, gate, ship, push safely, open
or update a PR through the no-mistakes process, or invokes `/no-mistakes`.

Read `references/axi-workflow.md` before starting, resuming, or responding to a
pipeline run.

Read `references/pr-evidence.md` before finalizing any PR-backed run.

## Non-negotiables

- Run `no-mistakes axi` first and respect any active run state
- Before `axi run`, `axi respond`, or any push dry-run, the agent must run
  `"$HOME/.agents/scripts/ensure-worktree-ready.sh" .`; do not ask the user to
  run it. Stop if hooks cannot be activated.
- Work must be committed on a feature branch before `axi run` validates it
- Pass a rich `--intent` in the user's words, including product decisions that
  are not obvious from the diff.
- At gates, let the pipeline own its findings and fixes. Use `axi respond`
  instead of manually editing while the run is waiting.
- Escalate `ask-user` findings verbatim unless the user gave clear unattended
  consent such as `--yes`.
- For GitHub Actions/`gh` CI failures, inspect logs in parallel where possible,
  batch fixes locally, and rerun the fewest checks.
- On `checks-passed` or `passed`, report what was validated, what was found,
  and every pipeline fix applied.
- Before finalizing a PR-backed run, repair the PR evidence section so it has hosted screenshots, required 2x E2E video links, no local paths, and clear screenshot/video and no-mistakes status
- Only check GitHub review threads after external PR review has run or the user
  explicitly asks for comment handling.

## Common commands

```sh
no-mistakes axi
"$HOME/.agents/scripts/ensure-worktree-ready.sh" .
no-mistakes axi run --intent "<user goal and relevant decisions>"
no-mistakes axi respond --action fix --findings <ids>
no-mistakes axi respond --action approve
no-mistakes axi status
no-mistakes axi logs --step <name> --full
node "$HOME/.agents/skills/no-mistakes/scripts/repair-pr-evidence.mjs"
node "$HOME/.agents/skills/no-mistakes/scripts/repair-pr-evidence.mjs" --e2e-video-required --videos "<local or hosted 2x video>"
```

## Output notes

- Output is TOON; follow returned `help` lines instead of guessing
- `checks-passed` means checks are green and the PR is ready for human review
- `failed` or `cancelled` means inspect logs, fix, commit, then rerun
- `Directory not empty` is a recovery state; preserve data and follow tool help
- Use `--yes` only with user consent for unattended actionable gates
