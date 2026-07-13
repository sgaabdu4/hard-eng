# hard-eng

![Hard Eng workflow](assets/readme/hard-eng-hero.png)

> **Alpha:** Hard Eng is being rebuilt from scratch. Planning, local build convergence, and shipping are implemented; conditional learning remains under rebuild.

Hard Eng has one entrypoint:

- `$he plan <feature>`
- `$he resume`
- `$he status`
- `$he build`
- `$he ship`
- `$he learn` *(pending rebuild; not yet invokable)*

`$he → he-plan → he-build (Implement ⇄ Verify) → he-ship → he-learn (pending)`

Run `./setup.sh` once after cloning. It installs pinned npm CLIs, installs checksum-verified pinned `jq` and `rtk` release binaries, installs the global worktree hook dispatcher, and validates the complete local system. Run `./setup.sh check` for a read-only readiness check. Managed skills remain pinned; setup never invokes `npx skills` or rewrites `.skill-lock.json`.

`$he` discovers the active `PLAN.md`, validates its repository state, and routes the next stage. `he-plan` uses `research` to establish current state, then `question-me` for decisions evidence cannot answer. Specialists never own lifecycle state. Context7 is CLI-only and limited to current library documentation.

Every repository must have one root `PRODUCT.md` and `DESIGN.md`. Hard Eng checks both before planning advances. If either is missing or invalid, it researches the repository, asks you only for intent the evidence cannot establish, creates the files with your approval, and validates them. Repositories without a visual surface still use `DESIGN.md` to record that boundary and its revisit trigger.

Before changing code, Hard Eng checks the current checkout. It keeps working in an existing linked worktree. A clean primary checkout can continue on its current branch; a dirty primary checkout moves the task into a new isolated worktree. Hard Eng does not require a branch-name prefix.

If planning itself created the dirt, Hard Eng transfers the approved `PLAN.md` and only the exact task-owned changed context or planning files into the same-HEAD linked worktree. The destination becomes the sole fresh PLAN owner; the source PLAN becomes stale. This needs no baseline commit, recreated plan, or manual state edit. Unrelated user changes remain untouched in the original checkout.

Hard Eng records the branch, base revision, dirty state, and local setup needs; copies explicitly allowlisted ignored environment files through the repository's `.worktreeinclude`; rebuilds dependencies or generated state through the project setup owner; and runs a smoke check before feature work. The machine-level Git dispatcher applies the same environment-file rule to ordinary `git worktree add` checkouts while preserving traditional repository hooks. Codex-managed detached worktrees are valid while working, but committing or pushing requires a named task branch.

Install the dispatcher once with `~/.agents/scripts/git-hooks/install.sh install`. Each repository then lists the exact ignored environment files it needs in a tracked root `.worktreeinclude`, such as `.env` and `.env.local`. New worktrees copy only those files from the main worktree, never overwrite existing files, and store copied secrets with owner-only permissions.

Use `$he plan <feature>` for a new feature or intentional product-behavior change. Planning moves through repository evidence, feature outcomes, flows, UX, contracts, technical design, testing, rollout, delivery slices, consistency, and final approval. Each stage asks only decisions that evidence cannot settle; it does not advance until you approve the result or explicitly approve a justified skip.

## Build until green

After final plan approval, use `$he build` or simply ask Codex to continue. Hard Eng resumes the first incomplete vertical slice and runs one observable behavior at a time through TDD: RED, GREEN, REFACTOR, focused deterministic checks, review, automatic authorized fixes, and verification again. Findings that need a product decision or unavailable external authority are recorded in `PLAN.md` instead of guessed.

When every slice is complete, Hard Eng runs the full applicable test, lint, scanner, code-review, security, design, performance, documentation, and runtime gates. A readiness score shows progress, but no weighted score can hide a failed gate: every applicable axis must pass and every required finding must be resolved.

User-visible work finishes with the complete planned browser or device journey. Existing interfaces receive comparable before-and-after screenshots; final states receive viewport or device screenshots; the primary temporal flow receives a video; console, network, and durable backend state are also checked. Non-visual work records equivalent logs, traces, or command evidence.

The last local gate sends the exact bounded review packet to one ephemeral, read-only independent audit using `gpt-5.6-sol` with medium reasoning. The packet contains the validated base-to-HEAD commit range, separate committed/cached/unstaged diffs, untracked files, applicable repository rules, and bounded unchanged callers/tests. Credential paths/content fail closed. The child starts in an empty temporary Git repository with all tools disabled; its enforced permission profile also denies reads from the source checkout and controller homes. The parent receives live stage/heartbeat events, enforces idle and wall-time budgets, and reports token usage. Decision questions return as structured unknowns; the child never waits silently for input. Any accepted finding returns to the fix-and-verify loop. Only an unchanged snapshot with readiness 100, current evidence, no open items, and a clean final audit becomes ready for `$he ship`. Build never commits, pushes, opens a PR, or waits on CI.

## Ship the proven artifact

`$he ship` reads the repository’s delivery policy, synchronizes with the target branch, and compares the resulting content snapshot with the green build. Any changed content, conflict, review finding, or actionable CI failure returns to `he-build` for another final Implement ⇄ Verify round.

An unchanged artifact passes the repository publish gate, commits without bypassing hooks, proves the commit contains the exact green snapshot, then follows the approved direct-push or PR path. Dry-run push, remote SHA, required CI, review, and merge policy are verified before the PLAN becomes `shipped`. Existing exact authorization is reused; Hard Eng asks only when the target or external-write scope is genuinely missing.

Typical starts:

- New material feature: `$he plan add account recovery with email and passkey paths`
- Resume after compaction or a new task: `$he resume`
- Inspect progress without changing anything: `$he status`
- Continue an approved plan through the build loop: `$he build`
- Small clear fix without a new product decision: describe the fix directly; Hard Eng planning is not required.

Existing bugs and production incidents stay direct: for example, `fix all Sentry issues` starts with the Sentry workflow, not a new Hard Eng plan. If investigation uncovers a genuinely new product decision, the work escalates to `$he plan` at that point.
