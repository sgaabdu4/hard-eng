# no-mistakes Axi Workflow

`no-mistakes axi` is the agent-facing interface. It prints machine-readable
TOON to stdout and progress to stderr.

## Modes

- Validate-only: bare `/no-mistakes`, optionally with skip flags. The user's
  changes are already committed, so validate and report.
- Task-first: do the requested work, commit only that scope on a feature branch,
  then validate the committed branch.
- Translate user flag requests into `axi run` flags yourself. Example: "skip
  lint" means pass `--skip=lint`. Use `no-mistakes axi run --help` when unsure.

## Preconditions

- Start with `no-mistakes axi`
- If the current branch already has an active run, resume it or abort only when
  the user has approved aborting.
- If another branch has an active run, leave it alone
- If the repo is not initialized, follow the tool's `no-mistakes init` guidance;
  Hard Eng setup repairs the local gate hook automatically; after a manual init,
  run `node "$HOME/.agents/integrations/no-mistakes/scripts/repair-gate-hook.mjs" .`
  when Node is available so `notify-push` uses `GATE_DIR` instead of the caller's
  `pwd`. The managed wrapper skips that repair with a warning when Node is not
  on `PATH`.
- Ship inventory treats the `no-mistakes` remote as initialized only when it
  resolves to a local bare Git repository whose executable `post-receive` hook
  invokes `notify-push --gate`; a remote name or URL alone is not proof.
- If the command is missing or unhealthy, run `no-mistakes doctor`
- If setup reports `Directory not empty`, keep the existing repo state and follow
  the tool's recovery guidance instead of deleting or recreating it.
- Before starting, responding, or trusting a push dry-run, run
  `"$HOME/.agents/scripts/ensure-worktree-ready.sh" .` from the active checkout.
  The agent owns this preflight; do not ask the user to run it. This is required
  inside no-mistakes internal worktrees too; an explicit refspec dry-run is not
  proof unless project hooks are active.
- The managed wrapper repeats `ensure-worktree-ready.sh --check
  --require-pre-push` and `check-project-quality-gates.mjs --require-push-gate`
  before `axi run` and `rerun`, then synchronizes the proven effective
  pre-push hook into the local no-mistakes bare gate repository. The gate
  scanner follows a dispatcher source only when its declared path exactly
  matches the executable `exec` target. When
  `/he:ship` is active, its stage contract also owns the non-skippable format
  check and project inventory before this workflow starts.
- Commands launched by a Git hook against a fixture or foreign repository must
  clear the variables reported by `git rev-parse --local-env-vars` first.
  Otherwise inherited `GIT_DIR` or `GIT_WORK_TREE` can redirect cleanup into
  the active no-mistakes gate repository.
- `HARD_ENG_NO_MISTAKES_SKIP_PREFLIGHT=1` bypasses both wrapper preflight
  checks and gate-hook dispatcher synchronization; use it only for an explicit
  preflight bypass.
- Never run the pipeline from the default branch for new shipping work

## Intent

Pass `--intent` every time you start a run.
The intent is the user's objective, not a diff summary.
Include constraints, tradeoffs, and decisions the review step cannot infer from
code alone.

```sh
no-mistakes axi run --intent "<what the user set out to accomplish>"
```

## Gates

When output contains `gate:`, the pipeline is waiting for a decision.
Read the actual `findings` table columns.
`axi run` and `axi respond` can take several minutes.
Do not cancel or restart because they look quiet.
Check progress from another call with `no-mistakes axi status`.
Common actions:

- `auto-fix`: safe for the agent to send to the pipeline with `--action fix`
- `no-op`: informational, approve when no action is needed
- `ask-user`: stop and relay the finding verbatim unless the user gave clear
  unattended consent.

Use the pipeline to apply fixes:

```sh
no-mistakes axi respond --action fix --findings <id1,id2>
no-mistakes axi respond --action approve
no-mistakes axi respond --action skip
```

Do not manually edit code while the active gate is waiting.
If you spot an extra issue during a gate, fold it in with `--add-finding` and
`--action fix`.
Use `--step <name>` only when you need to respond to a specific non-current
step.
If the user gave clear unattended consent, `--yes` may drive actionable gates
without stopping for each `ask-user` finding.

Proof-scanner review findings have a loop limit. Authorize at most one bounded
scanner/parser fix for the current gate. If the next review surfaces another
runner family, command parser, package-script, or ecosystem bypass, stop and
report a design-loop/breadth issue instead of continuing auto-fix.
For package-manager scope findings, do not model workspace/fanout semantics in
the proof scanner. `--prefix`, `--workspace`, `--workspaces`, `--filter`,
`--dir`, `--cwd`, recursive/fanout flags, and equivalent package-manager env
overrides must fail closed unless a later owner adds explicit trusted resolution
and regression coverage.
Before rerunning after any proof-scanner finding, do a local adversarial sweep of
the scanner family instead of using no-mistakes as the analyzer. Cover package
scope flags/env and package-script passthrough, Node preload/config paths such as `NODE_OPTIONS`, Mocha preload/config paths, Maven/Gradle/Make skip or dry-run flags, Go execution or source override flags such as `-exec`, `-overlay`, and `-modfile`, and URI-style path values such as `file://` and `data:`.

## Outcomes

- `checks-passed`: validation and checks are green, PR is ready for human review
- `passed`: the pipeline completed after merge or close
- `failed` or `cancelled`: inspect the failing step, fix root cause, commit the
  fix, and rerun or explain the blocker.

If the CI log says `all CI checks passed - still monitoring until merged or
closed` while GitHub PR checks are green and findings are empty, treat the run
as PR-ready: do not wait for human merge, and do not abort solely because the
status still says `ci,running`.

## GitHub Actions Cost

For GitHub Actions or `gh` CI failures, inspect all failing checks/logs before
editing. Fetch independent run/job logs in parallel where possible, batch fixes
into one local verify loop, and rerun only the needed workflows/checks. Do not
push one speculative commit per failing check.

## Inspecting state

```sh
no-mistakes axi
no-mistakes axi status
no-mistakes axi logs --step <name> --full
no-mistakes axi abort
no-mistakes rerun
```

Abort only when the user has approved cancelling the current-branch active run.

## Reading output

- Output is TOON: `key: value` pairs, tables, and `help` lines
- Follow `help` lines instead of guessing the next command
- Errors are printed as `error: ...` with recovery guidance
- Exit codes: `0` success or normal gate, `1` failed or cancelled final
  outcome, `2` bad usage.

## Reporting

At the end, include:

- PR link when one exists
- Pipeline findings and fixes, especially fixes your original change missed
- Verification commands and their pass/fail status
- Any skipped checks and residual risk
