<p align="center">
  <img src="docs/images/hard-eng-hero.png" alt="hard-eng workflow hero" width="920">
</p>

# Hard Eng

Hard Eng is a stateful agentic engineering workflow for local coding agents. It installs one shared rule, skill, hook, and MCP surface into the agent homes on a machine, then routes real work through `/he:plan`, `/he:implement`, `/he:verify`, `/he:ship`, and `/he:learn`.

When the plan breaks, Hard Eng returns to state, names the owner, reruns the guard, and stays hard

<a id="tested-scope"></a>
> Tested scope: this repo has only been tested on Codex running on macOS. Other linked runtimes are installed by the scripts, but Codex on macOS is the validated path today.

<a id="maturity"></a>
> Maturity: Hard Eng is pre-1.0 and not version 1 yet. Treat `0.x` releases as alpha workflow releases: skills, installer prompts, state schema, guards, and tags can still change before `v1.0.0`.

[![Workflow](https://img.shields.io/badge/workflow-stateful-0891b2)](#he-workflow)
[![Version](https://img.shields.io/badge/version-0.1.0--alpha.1-f59e0b)](#versioning)
[![Platform](https://img.shields.io/badge/tested-Codex%20%2B%20macOS-111827)](#tested-scope)
[![Gates](https://img.shields.io/badge/gates-hooks%20%2B%20no--mistakes-16a34a)](#shipping-and-safety)

## Install

Download the setup script first, then run one mode.

```sh
curl -fsSLO https://raw.githubusercontent.com/sgaabdu4/hard-eng/main/scripts/setup.sh
bash setup.sh --full
```

Use the lighter install when you only want the shared rules, skills, configs, and local repo hooks:

```sh
curl -fsSLO https://raw.githubusercontent.com/sgaabdu4/hard-eng/main/scripts/setup.sh
bash setup.sh --skills-only
```

Existing clone:

```sh
cd "$HOME/.agents"
./scripts/setup.sh --full
```

| Mode | Use it when | Installs |
| --- | --- | --- |
| `--full` | You want the automatic workstation path. | prerequisites when allowed, MCP tools, all Hard Eng skills, configs, Git hooks, watchdog, [`Treehouse`](https://github.com/kunchenguid/treehouse), `no-mistakes`, optional cron, worktree readiness |
| `--skills-only` | You only want the agent surface. | repo clone/update, pinned skill submodules, selected linked skills/configs, local hooks |
| `--prereqs-only` | You are repairing setup dependencies. | prerequisite tools only |
| `--uninstall --yes` | You want to remove what Hard Eng installed. | managed links, skills, hooks, cron blocks, watchdog, managed bins, cache, shell PATH block |

`--full` links every Hard Eng skill automatically. Default interactive setup and `--skills-only` ask which local skills to link: `all`, `none`, or a comma-separated list such as `he-plan,he-implement,he-verify,he-ship`. The choice is saved in `~/.config/hard-eng/skills.json`; `HARD_ENG_SKILLS=all|none|skill-a,skill-b` overrides it for one run. Deselected Hard Eng-managed symlinks are removed, but user-owned skill folders are preserved.

External skills are intentionally separate from this repo. Add them with the upstream `npx skills` workflow at global or project scope, then keep project-specific choices in that project's agent config instead of vendoring every skill here.

`--skills-only` intentionally skips cron, watchdog, Treehouse, `no-mistakes`, MCP npm installs, prerequisite repair, and worktree repair.

Lavish is installed as a local narrow skill wrapper backed by a pinned upstream submodule. Its CLI is invoked per UI decision session with `npx -y lavish-axi`, not as a general global workflow tool.

## Versioning

Current version: `0.1.0-alpha.1` from [VERSION](VERSION). The matching Git tag is `v0.1.0-alpha.1`.

Hard Eng follows SemVer-style tags with `vMAJOR.MINOR.PATCH` and prerelease suffixes while it is pre-1.0. Do not treat `0.x` as stable API: workflow commands, `he-state.json`, installer prompts, skill routing, and guardrails can still change until `v1.0.0`.

## Uninstall

From the repo:

```sh
./scripts/uninstall.sh --yes
```

From a downloaded setup script:

```sh
bash setup.sh --uninstall --yes
```

Uninstall removes Hard Eng-managed links, skill symlinks, local hooks, cron blocks, watchdog LaunchAgent/plist, managed Codex bin files, `~/.cache/hard-eng`, `~/.config/hard-eng/skills.json`, and the managed shell PATH block. It does not remove shared tools such as Homebrew, Git, Node, Dart, Flutter, Treehouse, or `no-mistakes`.

## What Gets Linked

Agent instruction files are symlinks to `~/.agents/AGENTS.md`. Keep repo-specific overrides in project-level `AGENTS.md` files.

| Runtime | Linked config |
| --- | --- |
| Codex | `~/.codex/AGENTS.md`, `~/.codex/mcp-config.json`, `~/.codex/hooks.json`, `~/.codex/skills/*` |
| Claude | `~/.claude/AGENTS.md`, `~/.claude/CLAUDE.md` |
| Copilot | `~/.copilot/AGENTS.md`, `~/.copilot/skills/*` |
| Pi | `~/.pi/AGENTS.md`, `~/.pi/skills/*` |
| Pi agent | `~/.pi/agent/AGENTS.md`, `~/.pi/agent/skills/*` |

`~/.claude/CLAUDE.md` is reduced to:

```md
@AGENTS.md
```

## HE Workflow

Run one `/he:*` command per stage. Start each stage in a fresh thread with the prior `he-state.json` path; the state file is the source of truth, not the old chat transcript. The full HTML flow lives at [docs/project-workflow-gates.html](docs/project-workflow-gates.html).

<p align="center">
  <img src="docs/images/project-workflow-gates.png" alt="Full Hard Eng workflow gates" width="920">
</p>

`he-state.json` tracks:

- `steps[]`: every internal step and receipt
- `subStages[]`: every stage checklist item, with done/skipped status, evidence, and skip reason when allowed
- `entryGate`: stages 2-5 must point to the previous stage receipt with `decision: PASS`
- `findings[]`: failures, review findings, planning concerns, and the owner repair stage
- `guardrails[]`: deterministic scripts, tests, lints, scanners, hooks, evals, command status, evidence, and whether they block push
- `context.product`, `context.design`, `context.tokenOwner`: `PRODUCT.md`, `DESIGN.md`, and token/design-system owner paths
- `planReadiness`: Grill Me stage map, full visible question text, alignment receipt, UI review proof, `planReadiness.uiReview.lavish`, artifact status, and explicit approval
- `agentWork[]`: parallel subagents and evals, with model, purpose, status, and evidence

Every stage ends with a compact receipt: `Stage`, `State`, `Decision`, `Owner/proof`, `Artifacts`, `Blocker`, and `Next`. `he-state.mjs validate` must pass before any ready-yes handoff.

Hard Eng is intentionally fail-closed:

- `next.ready: true` fails while any step, sub-stage, blocking finding, push-blocking guardrail, or agent work is unresolved
- Required stage gates cannot be skipped: Plan context/owner-proof/artifact-choice/risk-route/state validation, Implement owner read/change/guardrails, Verify tests/guardrails, Ship git status/hook readiness/quality gates/no-mistakes, Learn durable-owner/proof
- Later stages require `entryGate.decision = PASS` from the prior stage, so a fresh thread can resume from state without trusting the old transcript
- Plan requires passed context and state-validation guardrails; Implement requires a passed `find-deterministic-owner.mjs --json` guardrail; Verify requires the quality gate; Ship requires git status, worktree readiness, quality gate, and a passed `no-mistakes axi run --intent ...` receipt
- Plan readiness requires `unlimited_until_aligned`, no open questions or unknowns, user-confirmed no-guesswork alignment, and no parked artifacts
- Subagents recorded in state must use `gpt-5.5`; evals must use `gpt-5.4-mini`

| Stage | Command | What it does | Invokes automatically | Exit |
| --- | --- | --- | --- | --- |
| 1. Plan | `/he:plan` | Decides scope, owner, blast radius, proof path, risk route, product/design context, sub-stage readiness, and `PASS`/`CONCERNS`/`FAIL`. | Treehouse/worktree readiness; `check-project-context-gates.mjs --require-all`; `grill-me` for unclear outcome, scope, proof, risk, UI flow, or visual direction; Impeccable Live on the real app route with current tokens/components first; current-design-system mock only when the real surface cannot exist yet; Lavish only for UI option comparison and decisions through `npx -y lavish-axi poll`; `to-prd` or `to-issues` only when that artifact is needed. | `Next: ready for /he:implement: yes/no` |
| 2. Implement | `/he:implement` | Requires prior Plan `PASS`, changes the canonical owner, and wires deterministic guardrails. | `find-deterministic-owner.mjs --json`; `codebase-design` when ownership is unclear; existing scripts/tests/hooks before fresh reasoning; touched-area skills; SSOT scanners for duplicate-prone values or policy concepts. | `Next: ready for /he:verify: yes/no` |
| 3. Verify | `/he:verify` | Requires prior Implement `PASS`, then runs the proof loop until every required test, review, guardrail, and E2E check is clean or explicitly blocked. | `test-quality`, security/perf when touched, thermo review, E2E last, and subagents for independent proof. | `Next: ready for /he:ship: yes/no` |
| 4. Ship | `/he:ship` | Requires prior Verify `PASS`, then runs status/secrets checks, hook readiness, quality gates, `no-mistakes`, PR evidence repair, and CI follow-through. | `git status --short`, `ensure-worktree-ready.sh --check --require-pre-push`, `check-project-quality-gates.mjs --require-push-gate`, `no-mistakes axi run --intent ...`. | `Next: ready for /he:learn: yes` or `Next: loop complete: yes` |
| 5. Learn | `/he:learn` | Requires a learning finding, then adds a durable guard and proves it. | `repeated-failure-learning`; `skill-creator` only when a skill/stage contract is the owner. | `Next: loop complete: yes/no` |

Grill Me stays inside Plan. It owns `session_state.md`, its stage map, and the one-question loop. It asks as many one-by-one questions as needed until the user and AI are aligned with no guesswork. UI uncertainty goes through product, UI flow, visual design, prototype tech, prototype, backend tech, and vertical-slice stages as needed. If UI flow or visual design runs, Plan cannot pass until the real app route has been reviewed through Impeccable Live using the current design system and shared components, or a current-design-system mock is explicitly recorded as fallback because the real surface cannot exist yet. Lavish then presents multiple UI options for decision only, `npx -y lavish-axi poll` returns the user's decision, selected choices/components are saved, requested tweaks are recorded, and the user approves it. Parked questions, artifacts, UI decisions, or unknowns mean `Next: ready for /he:implement: no`.

Plan also gates context docs. Product behavior changes update `PRODUCT.md`; design, UI, component, or token changes update `DESIGN.md` and the token owner. `he-state.json` records those paths before `/he:implement` is ready.

Verify is the main fix loop. If any proof fails, `/he:verify` records a finding, routes code changes back through `/he:implement`, then reruns only the affected proof. `/he:ship` starts only after the verify loop is clean and work is committed.

React/Next guardrails include React Doctor, Fallow audit/dupes, lint, and typecheck. Flutter guardrails include package-root `dart analyze` with `flutter_skill_lints` and tests when present. Missing repeatable checks become scripts, tests, hooks, or evals.

SSOT guardrails are also deterministic. `scripts/check-ssot-guardrails.mjs` requires every root `scripts/check-*.mjs` scanner to be registered to an owner file in `ssot-guardrails.json`, and it blocks configured duplicated literals from drifting outside their source of truth. The installer wires this check into pre-commit and pre-push.

## Specialist Routing

| Need | Use |
| --- | --- |
| Choose the next workflow, skill, or stage | `workflow-help` |
| Clarify ambiguous work before building | `grill-me` |
| Diagnose hard bugs, flakes, regressions | `diagnosing-bugs` |
| Decide module ownership or abstraction shape | `codebase-design` |
| Turn resolved context into a spec | `to-prd` |
| Split a plan into vertical-slice issues when slices are missing or should be published as work items | `to-issues` |
| Design or repair tests | `test-quality` |
| UI systems, tokens, product polish, or UI option decisions | `atomic-ui` + `impeccable`; use Lavish only to compare UI options and record decisions |
| React app or Next.js implementation/review | `react-doctor` + `fallow`; include `fallow dupes` / clone-group checks for duplication; use `vercel-react-best-practices` for performance/composition |
| Flutter/Dart app work | `building-flutter-apps` |
| Appwrite backend work | `appwrite-backend` |
| Sentry or observability work | `sentry-workflow` |
| User-like UI regression proof | `e2e` |
| Latency or efficiency work | `performance-rescue` |
| Security, auth, secrets, or data exposure | `security-review` |
| Strict maintainability review | `thermo-nuclear-code-quality-review` |
| Direct no-mistakes validation details | `no-mistakes` |

## Inspiration And Upstreams

Hard Eng borrows ideas from good public agent-workflow projects, but keeps this
repo's state, hooks, and local rules as the source of truth.

| Project | GitHub | What Hard Eng takes |
| --- | --- | --- |
| Compound Engineering | [`EveryInc/compound-engineering-plugin`](https://github.com/EveryInc/compound-engineering-plugin) | Plan/review/execute loop shape, subagent-friendly stages, and compounding workflow mindset. |
| BMAD Method | [`bmad-code-org/BMAD-METHOD`](https://github.com/bmad-code-org/BMAD-METHOD) | Structured planning, role separation, and readiness before build. |
| Matt Pocock skills | [`mattpocock/skills`](https://github.com/mattpocock/skills) | Grill Me-style human alignment and senior-engineer taste; Hard Eng makes it stateful with stage receipts, context gates, and loop enforcement. |
| DESIGN.md | [`google-labs-code/design.md`](https://github.com/google-labs-code/design.md) | Persistent product/design context and token-owned design memory. |
| Treehouse | [`kunchenguid/treehouse`](https://github.com/kunchenguid/treehouse) | Isolated reusable worktrees before feature planning/coding. |
| Lavish | [`kunchenguid/lavish-axi`](https://github.com/kunchenguid/lavish-axi) | Browser-based UI option comparison, polling, and saved decision receipts only. |
| no-mistakes | [`kunchenguid/no-mistakes`](https://github.com/kunchenguid/no-mistakes) | Final safety gate, PR evidence, and push discipline. |
| Impeccable | [`pbakaus/impeccable`](https://github.com/pbakaus/impeccable) | PRODUCT/DESIGN context loading and token-first UI review. |
| React Doctor | [`millionco/react-doctor`](https://github.com/millionco/react-doctor) | React/Next diagnostics before ship. |
| Fallow skills | [`fallow-rs/fallow-skills`](https://github.com/fallow-rs/fallow-skills) | JS/TS code-health, duplicate, and risk checks. |
| Vercel agent skills | [`vercel-labs/agent-skills`](https://github.com/vercel-labs/agent-skills) | React/Next performance and composition guidance. |
| Anthropic skills | [`anthropics/skills`](https://github.com/anthropics/skills) | Skill packaging and reusable agent capability patterns. |
| Tavily skills | [`tavily-ai/skills`](https://github.com/tavily-ai/skills) | Web research and URL extraction workflow patterns. |
| Sentry AI skills | [`getsentry/sentry-for-ai`](https://github.com/getsentry/sentry-for-ai) | Sentry-first issue routing and observability workflows. |
| Sentry CLI | [`getsentry/cli`](https://github.com/getsentry/cli) | CLI-backed Sentry inspection. |

Local rules win:

- Steal: help/front-door routing, readiness checks, next-action clarity, sharper vertical slices, and visible loop structure
- Do not steal: personas, menu codes, generated story state, or planning ceremony that slows implementation
- Local delivery stays stricter: code evidence, state receipts, owner-first implementation, deterministic guardrails, E2E proof, thermo review, and `no-mistakes`

## Repo Layout

| Path | Role |
| --- | --- |
| `AGENTS.md` | Global rules: tool routing, blast-radius checks, verification gates, writing style, and skill budgets. |
| `skills/` | The active skill surface. Local skills are real folders; upstream skills are symlinks. |
| `vendor/skill-upstreams/` | Git submodules for read-only upstream skills. |
| `hooks/` | Safety hooks for command blocking, secret protection, and Codex session behavior. |
| `codex/hooks.json` | Codex hook wiring. |
| `codex/bin/` | Token-free Codex watchdog and health scripts installed under `~/.codex/bin`. |
| `mcp-config.json` | Shared MCP defaults for `context-mode` and `codebase-memory-mcp`. |
| `agents/` | Subagent role prompts. |
| `scripts/` | Install, uninstall, submodule update, cron, and compatibility helpers. |
| `tests/` | Contract checks for symlinks, hooks, env behavior, README links, workflow state, and repo policy. |

## Setup Switches

| Variable | Effect |
| --- | --- |
| `HARD_ENG_ENABLE_CRON=1` | Install the optional auto-sync cron during setup. |
| `HARD_ENG_SKIP_PREREQ_INSTALL=1` | Skip prerequisite repair. |
| `HARD_ENG_ALLOW_HOMEBREW_BOOTSTRAP=1` | Allow setup to run the upstream Homebrew bootstrap when Homebrew is missing. |
| `HARD_ENG_SKIP_FLUTTER_INSTALL=1` | Skip Flutter SDK installation. |
| `HARD_ENG_FLUTTER_HOME=/path/to/flutter` | Install or detect Flutter at a custom path. |
| `HARD_ENG_SKIP_SHELL_PATH_UPDATE=1` | Do not write the managed `~/.zshenv` PATH block. |
| `HARD_ENG_SETUP_TREEHOUSE=0` | Answer no to the setup-time Treehouse question. |
| `HARD_ENG_SKIP_TREEHOUSE=1` | Skip installing or updating Treehouse during setup. |
| `HARD_ENG_SETUP_NO_MISTAKES=0` | Answer no to the setup-time `no-mistakes` question. |
| `HARD_ENG_SKILLS=all\|none\|he-plan,he-verify` | Override the saved local Hard Eng skill selection for one install. |
| `HARD_ENG_SKILL_CONFIG=/path/to/skills.json` | Store the selected local Hard Eng skills somewhere other than `~/.config/hard-eng/skills.json`. |
| `HARD_ENG_SKIP_NPM_INSTALL=1` | Skip MCP tool installation. |
| `HARD_ENG_SKIP_NO_MISTAKES=1` | Skip installing and initializing `no-mistakes`. |
| `HARD_ENG_SKIP_NO_MISTAKES_INIT=1` | Install `no-mistakes` but skip repo initialization. |
| `HARD_ENG_NO_MISTAKES_REPOS=/repo/a:/repo/b` | Initialize extra repos for `git push no-mistakes`. |
| `HARD_ENG_SKIP_WORKTREE_READY=1` | Skip shared worktree readiness checks during setup. |
| `HARD_ENG_WORKTREE_READY_INSTALL=1` | Allow readiness repair to run `npm ci` when a hook manager needs it. |

## Updating Skills

Initialize or repair pinned submodules:

```sh
./scripts/update-submodules.sh --init
```

Bump upstream skill pins:

```sh
./scripts/update-submodules.sh --remote
git status --short
git add .gitmodules vendor/skill-upstreams
git commit -m "Update skill submodules"
git push origin main
```

`--remote` refuses to run when tracked files or the index are dirty.

## Optional Cron Sync

Enable local auto-sync:

```sh
HARD_ENG_ENABLE_CRON=1 ./scripts/install.sh
```

Set a custom schedule:

```sh
HARD_ENG_CRON_SCHEDULE="*/30 * * * *" ./scripts/install-cron.sh
```

Cron runs `scripts/auto-sync.sh`. It updates Treehouse and `no-mistakes`, pulls `main`, bumps submodules, scans for private paths and secret-like values, commits changed pins, and pushes `main`.

## Shipping And Safety

Default shipping path: use `he-ship`, which runs [`no-mistakes`](https://github.com/kunchenguid/no-mistakes) after local verification is clean, work is committed, and a repo has been initialized with `no-mistakes init`. Before trusting a push dry-run, run `scripts/ensure-worktree-ready.sh`; it rejects private or no-mistakes-owned hook paths and repairs known portable hook managers.

Run:

```sh
git status --short --branch
git diff --check
node tests/agents-md-contract.test.mjs
node tests/codex-hooks-contract.test.mjs
node tests/git-hooks-contract.test.mjs
node tests/he-state.test.mjs
node tests/project-quality-gates.test.mjs
node tests/security-pretooluse-env.test.mjs
node tests/protect-secrets-env.test.mjs
```

Scan for local paths and secret-like values:

```sh
rg -n --hidden --glob '!.git/**' --glob '!**/.git/**' -F "$HOME" .
rg -n --hidden --glob '!.git/**' --glob '!**/.git/**' '(github_pat_[A-Za-z0-9_]+|gh[pousr]_[A-Za-z0-9_]+|sk-[A-Za-z0-9_-]{20,}|AKIA[0-9A-Z]{16}|-----BEGIN (RSA |DSA |EC |OPENSSH )?PRIVATE KEY-----)' .
```

Never commit secrets, personal paths, runtime logs, local MCP state, generated caches, private repo data, or machine-local lock state.

## Ethos

Inspired by David Goggins' Stay Hard mindset: when the plan gets wrecked, there is one useful move left. Face the proof, fix the owner, rerun the guard, and keep going until the repo is harder to break than it was yesterday

[Watch the short operating reminder](docs/media/stay-hard.mp4)
