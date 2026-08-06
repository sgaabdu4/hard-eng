# Hard Eng

Fast, evidence-backed engineering for OpenAI Codex, Claude Code, and GitHub Copilot CLI. Align once, build in verified slices, ship the proven artifact.

## Users

| User | Job | Pain | Desired outcome |
|---|---|---|---|
| Codex or Claude Code operator | deliver repository changes | repeated alignment + context loss | one approval + resumable slices |
| Repository maintainer | preserve product/engineering truth | duplicate owners + shallow proof | current SSOT + regression-safe delivery |

## Problem

- Agents lose intent or burn time on repeated planning, questions, approvals, and context.
- Bureaucracy delays working-code evidence without adding protection.
- Cost = slow delivery + token waste + review fatigue + hidden regression risk.

## Purpose

- Shortest safe route from accepted outcome to verified code.
- Differentiator = one lean Feature Brief + one Ready-to-build approval + Implement ⇄ Verify slices.
- Critical scrutiny follows risky slices; routine work stays lean.
- Route + principle + lifecycle contract = `AGENTS.md` + `skills/`; restating them here forbidden.

## Core capabilities

| Capability | Owner | Observable outcome |
|---|---|---|
| Lifecycle | `he` `he-plan` `he-build` `he-ship` `he-learn` | route/state selected → one lean Feature Brief approved before build-readiness debt → complete end-to-end behavior first → slices converge → green artifact delivered → proven process gap prevented |
| Evidence | `question-me` `research` `diagnosing-bugs` `repeated-failure-learning` `e2e` `sentry` | material intent, need + solution-ladder admission, primary + analogous external evidence before dependent implementation, root-cause admission, real browser/device proof |
| Review and design | `code-review` `security-review` `test-quality` `codebase-design` `atomic-ui` `writing-great-skills` | actual diff, risk screen, behavior tests, module boundaries, UI ownership, skill quality |
| Gates | `deterministic-checks` | migrates missing project gate wiring before product mutation → proves compatible real-tool seams before paid/native retries → runs affected-full gates with manifest-bound argv + full zero-finding latest quality analyzers |
| Continuity | `handoff` | terse complete session resume; user-invoked only |
| Stack guides | `appwrite-backend` `building-flutter-apps` `vercel-react-best-practices` | vendor-pinned stack practice, updated only through the lock |

## Delivery

- `setup.sh install|check|update` = pinned repository checks + npm runtime + binaries + Context Mode plugin for Codex, Claude Code, and Copilot CLI + `~/.codex/AGENTS.md` symlink + `~/.claude/CLAUDE.md` import stub + `~/.claude/output-styles` symlink with the canonical plain-English style selected + conditional global Copilot instruction, no-authorship, and Context Mode wiring when `~/.copilot` exists + global Git-hook dispatcher + shared agent guard hooks for Codex, Claude Code, and Copilot, which also format at the end of a turn whatever that turn edited + one managed PATH block.
- Publish gate = `scripts/git-hooks/publish-gate.sh`; pre-commit = worktree + format + lint + managed-skills + design; pre-push = typecheck + format + lint + tests + Fallow + full contracts.
- Lifecycle screenshots, recordings, and UX references = local display/proof; Git delivery only when explicitly accepted as product assets.
- Managed skills = `.skill-lock.json` + pinned `npx skills@1.5.16` through `scripts/update-managed-skills.sh`.
- Daily CI = model-free `03:30 UTC` locked-skill update; direct default-branch commit when changed.

## Boundaries

- Not a plugin: delivery = native symlink/import from this canonical repository.
- Not a harness: no background daemons, eval fleets, or model schedulers.
- Not a zero-risk claim.
- Feature state = repository `features/<feature-slug>/PLAN.md`.
- Managed skills = pinned vendor owners remain immutable.

## Success

| Outcome | Metric | Target |
|---|---|---|
| Fast alignment | approval rounds before standard build | 1 |
| Decision latency | user round trips per independent dependency frontier | 1 |
| Useful questions | questions tied to material decision | 100% |
| Stable build | replans caused only by outcome/risk change | 100% |
| Safe delivery | applicable deterministic/protected-boundary gates | 100% PASS |
| Regression control | escaped defect in changed behavior | downward trend |
| Efficient context | repeated context/approval tokens per comparable task | downward trend |
| Working feedback | time from request to first verified end-to-end slice | downward trend |
| Execution efficiency | duplicate equivalent setup/build/gate/paid actor per exact tree + seam | 0 |
| Output efficiency | tokens not required for the decision, proof, risk, or next action | 0 |
| Comment discipline | new source comments expressible through code, tests, or canonical docs | 0 |
| Closure integrity | verified in-scope defects open at `done` | 0 |
| Retry efficiency | paid/native/external attempts after one failure without fresh approval + changed proven mechanism | 0 |
| Instruction fidelity | explicit outcomes/constraints omitted or silently narrowed | 0 |

## Constraints

- Status = alpha.
- Runtime = native Codex + Claude Code; shared behavior = agent-agnostic canonical skills; runtime-specific files = wiring only.
- Delivery = minimum ceremony that preserves accepted outcome + protected boundaries + deterministic proof.

## Evidence

- Routing + approval contract = `AGENTS.md` + `skills/he/` + `skills/he-plan/`.
- Build convergence = `skills/he-build/`; delivery = `skills/he-ship/`; learning = `skills/he-learn/`.
- Enforcement = `scripts/check-skill-contracts.py` + `scripts/check-managed-skills.js` + `skills/deterministic-checks/`.
- Installation + pins = `setup.sh` + `scripts/setup/manifest.json` + `.skill-lock.json`.

## Unknowns

- Baseline token/time/defect data = collect across comparable completed tasks.
