# Hard Eng

Fast, evidence-backed engineering for OpenAI Codex, Claude Code, and GitHub Copilot CLI. Align once, build in verified slices, ship the proven artifact.

## Users

| User | Job | Pain | Desired outcome |
|---|---|---|---|
| Codex, Claude Code, or Copilot CLI operator | deliver repository changes | repeated alignment + approval prompts + context loss | autonomous delivery + protected stops only |
| Repository maintainer | preserve product/engineering truth | duplicate owners + shallow proof | current SSOT + regression-safe delivery |

## Problem

- Agents lose intent or burn time on repeated planning, questions, approvals, and context.
- Bureaucracy delays working-code evidence without adding protection.
- Cost = slow delivery + token waste + review fatigue + hidden regression risk.

## Purpose

- Shortest safe route from accepted outcome to verified code.
- Differentiator = one lean Feature Brief + one Ready-to-build approval + Implement ⇄ Verify slices.
- Reads + reversible local/external work + deploy/release/publish + push/merge continue without protected approval once intent + target are known.
- Only irreversible destructive loss stops for exact approval: permanent data/file/schema deletion + uncommitted-work loss + forced remote history loss + secret exposure.
- Critical scrutiny follows risky slices; routine work stays lean.
- Route + principle + lifecycle contract = `AGENTS.md` + `skills/`; restating them here forbidden.

## Core capabilities

| Capability | Owner | Observable outcome |
|---|---|---|
| Lifecycle | `he` `he-plan` `he-build` `he-ship` `he-learn` | route/state selected → one lean Feature Brief approved before build-readiness debt → complete end-to-end behavior first → slices converge → green artifact delivered → proven process gap prevented |
| Repository learning | `he-learn` `repeated-failure-learning` | each verified process miss is recorded in the affected repository → deterministic prevention is preferred → a repository skill is added only for a repeated root cause that deterministic checks cannot fully prevent |
| Evidence | `question-me` `research` `diagnosing-bugs` `repeated-failure-learning` `e2e` `sentry` | material intent, need + solution-ladder admission, primary + analogous external evidence before dependent implementation, root-cause admission, request-bound browser/device proof with exact reviewed delivery media, and existing-UI prototypes bound to accepted requirements + the real current screen + production render provenance |
| Review and design | `code-review` `security-review` `test-quality` `codebase-design` `atomic-ui` `writing-great-skills` | actual diff, risk screen, behavior tests, module boundaries, UI ownership, skill quality |
| Gates | `deterministic-checks` | migrates missing project gate wiring before product mutation → proves compatible real-tool seams before paid/native retries → runs the one manifest-owned commit, push, or CI phase → checks staged files at commit and runs affected-full gates before delivery → keeps local and CI command sets identical → runs independent read-only families in bounded parallel workers while exclusive scanners stay protected |
| Continuity | `handoff` | terse complete session resume; user-invoked only |
| Stack guides | `appwrite-backend` `building-flutter-apps` `vercel-react-best-practices` | vendor-pinned stack practice, updated only through the lock |

## Delivery

- `setup.sh install|check|update` = pinned repository checks + npm runtime + binaries + Context Mode plugin for Codex, Claude Code, and Copilot CLI + `~/.codex/AGENTS.md` symlink + `~/.claude/CLAUDE.md` import stub + `~/.claude/output-styles` symlink with the canonical plain-English style selected + conditional global Copilot instruction, no-authorship, and Context Mode wiring when `~/.copilot` exists + global Git-hook dispatcher + one fast shared guard for Codex, Claude Code, and Copilot + one managed PATH block.
- `setup.sh learning-install|learning-check` = canonical global learning-agent links for Codex, Claude Code, and Copilot CLI.
- `~/.agents/setup.sh repo-install <repository>|repo-check <repository>` = repository learning validation + canonical `.agents/skills` ownership + Claude `.claude/skills` discovery links; Codex and Copilot use the canonical repository skills directly.
- Agent guard = blocks only known irreversible destructive Git/database/file actions + secret exposure + raw lifecycle-control writes; unknown tools + complex shell commands + subagents + recoverable local/external actions continue; route/lifecycle drift fails the next repository checkpoint instead of blocking tool access.
- Feature folder = one living `PLAN.md` while nonterminal; a second Markdown file, a symlinked plan, or a second nonterminal Feature Brief blocks lifecycle and supported write paths.
- Execution evidence = current `research.json` + exact `authorization.json`; configured Direct work records one Git-private session/path receipt for the repository checkpoint, never for routine tool access; irreversible destructive actions use one-use exact `protected-action.json`.
- Publish gate = `scripts/git-hooks/publish-gate.sh`; pre-commit = one manifest-owned staged format/lint scan + enforcement-owner check; pre-push and CI = the same manifest-owned full phase with typecheck + format + lint + tests + pinned Fallow + Python types + full contracts + managed-skill + design + enforcement checks; unchanged exact-tree contract proof is reused only while repository and runtime identities match.
- Lifecycle screenshots, recordings, and UX references = local display/proof; Git delivery only when explicitly accepted as product assets.
- Managed skills = `.skill-lock.json` + pinned `npx skills@1.5.22` through `scripts/update-managed-skills.sh`.
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
| Efficient context | repeated context/approval tokens per comparable task | 0 unnecessary prompts |
| Working feedback | time from request to first verified end-to-end slice | downward trend |
| Execution efficiency | duplicate equivalent setup/build/gate/paid actor per exact tree + seam | 0 |
| Output efficiency | tokens not required for the decision, proof, risk, or next action | 0 |
| Comment discipline | new source comments expressible through code, tests, or canonical docs | 0 |
| Closure integrity | verified in-scope defects open at `done` | 0 |
| Retry efficiency | repeated failed mechanism after one external/native/paid failure | 0 |
| Instruction fidelity | explicit outcomes/constraints omitted or silently narrowed | 0 |
| Durable learning | verified process misses closed without repository-owned prevention or an assigned next action | 0 |

## Constraints

- Status = alpha.
- Runtime = native Codex + Claude Code + Copilot CLI; shared behavior = agent-agnostic canonical skills; runtime-specific files = wiring only.
- Delivery = minimum ceremony that preserves accepted outcome + protected boundaries + deterministic proof.

## Evidence

- Routing + approval contract = `AGENTS.md` + `skills/he/` + `skills/he-plan/`.
- Build convergence = `skills/he-build/`; delivery = `skills/he-ship/`; learning = `skills/he-learn/`.
- Repository learning state + three-runtime launch wiring = `skills/he-learn/scripts/learning_state.py` + `agents/he-learn/` + `setup.sh`.
- Enforcement = `scripts/check-skill-contracts.py` + `scripts/check-managed-skills.js` + `skills/deterministic-checks/`.
- Installation + pins = `setup.sh` + `scripts/setup/manifest.json` + `.skill-lock.json`.

## Unknowns

- Baseline token/time/defect data = collect across comparable completed tasks.
