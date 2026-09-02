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
| Lifecycle | `he` `he-plan` `he-build` `he-ship` `he-learn` | route/state selected → feature setup green (base branch resolved from `origin/main|develop`, `feature/<slug>` worktree created, ignored env inputs listed and copied after one batched question) → one lean Feature Brief approved before full-gate debt → complete end-to-end behavior first → slices converge sequentially or as parallel ticket worktrees behind one integration gate → green artifact delivered → proven process gap prevented |
| Repository learning | `he-learn` `repeated-failure-learning` | each verified process miss is recorded in the affected repository → deterministic prevention is preferred → a repository skill is added only for a repeated root cause that deterministic checks cannot fully prevent |
| Evidence | `question-me` `research` `diagnosing-bugs` `repeated-failure-learning` `e2e` `sentry` | material intent, need + solution-ladder admission, primary + analogous external evidence before dependent implementation, root-cause admission, request-bound browser/device proof with exact reviewed delivery media, and existing-UI prototypes bound to accepted requirements + the real current screen + production render provenance |
| Review and design | `code-review` `adversarial-review` `security-review` `test-quality` `codebase-design` `atomic-ui` `writing-great-skills` | actual diff, independent cross-model challenge, risk screen, behavior tests, module boundaries, UI ownership, skill quality |
| User replies | `plain-english` + `output-styles/plain-english.md` | answer first + ordinary words + brief blocks + Mermaid only when it makes the answer easier to understand |
| Gates | `deterministic-checks` | migrates missing project gate wiring before product mutation → at setup preserves any configured JS/TS formatter or linter silently, or chooses Biome only when neither exists → proves compatible real-tool seams before paid/native retries → runs the one manifest-owned commit, push, or CI phase → checks staged files at commit and runs affected-full gates before delivery → keeps local and CI command sets identical → runs independent read-only families in bounded parallel workers while exclusive scanners stay protected |
| Repository setup | `bin/hard-eng` + `runtime/repository_native/` | unmarked repository passes through unchanged → marked repository uses one healthy global Hard Eng OR one verified ignored fallback → partial global state + unsafe provider conflicts stop before any write → fallback = composed `AGENTS.override.md` for Codex + `CLAUDE.local.md` import for Claude Code + `.github/instructions/hard-eng.instructions.md` for Copilot + native hooks, skills, agents, and output-style links → generated files self-heal on rerun and refuse hand edits → a later healthy global removes the stale fallback → shared wiring commits one release pin + bootstrap + guard shim + hook entries + rule surfaces so every fresh clone downloads and verifies exactly that release at session start, denies tool calls until it has, and defers to a healthy global guard on developer machines |
| Terminal setup | private `package.json` bin → `install.sh` → `runtime/repository_native/installer.py` | `npx -y github:sgaabdu4/hard-eng --global` installs the newest verified release, updates an older release in one swap with rollback, or repairs a development checkout → per-agent ready/skipped report → `npx -y github:sgaabdu4/hard-eng --repo` runs only at a Git root + creates and stages missing repository rules and release policy + prepares Codex, Claude, and Copilot together under one lock with journaled rollback → `--ignore` keeps those untracked owner files private instead → `--repo --shared` pins the newest allowed release and stages the committed bootstrap, shim, hook entries, and rule surfaces (rerun to move the pin) → machine-specific wiring is always privately ignored + existing tracked files remain unchanged except the shared generated set |
| Continuity | `handoff` | terse complete session resume; user-invoked only |
| Stack guides | `appwrite-backend` `building-flutter-apps` `vercel-react-best-practices` | vendor-pinned stack practice, updated only through the lock |

## Delivery

- `npx -y github:sgaabdu4/hard-eng --global|--repo` = one GitHub entry through the private package's only bin; global mode installs the newest verified immutable release at `~/.agents`, updates an older release by staging + swap + `setup.sh install` + rollback on failure, or repairs a development checkout, then reports every agent as ready or skipped (CLI not installed); repository mode runs at the exact Git root + creates missing `AGENTS.md`, `CLAUDE.md`, and `hard-eng.gates.json` + stages untracked owner files by default or privately ignores them with `--ignore` + always privately ignores machine-specific wiring + reuses a healthy global launcher or prepares one verified local fallback for Codex, Claude, and Copilot together; `--repo --shared` pins one release and stages the generated files every clone needs, and `scripts/rollout-shared.py` does that per repository from a fresh clone, commits, and pushes the default branch or opens a pull request → `.github/workflows/rollout-shared.yml` runs the identical rollout from GitHub Actions instead of a laptop, one repository at a time behind `HARD_ENG_ROLLOUT_TOKEN` + the afenso git identity + a 40 second pause between repositories, and uploads a JSON report artifact; one flock lock per target + journaled rollback leave no partial state behind.
- `setup.sh install|check|update` = pinned repository checks + npm runtime + binaries + Context Mode plugin for Codex, Claude Code, and Copilot CLI + user-scope codebase-memory MCP registration + `~/.codex/AGENTS.md` symlink + `~/.claude/CLAUDE.md` import stub + `~/.claude/output-styles` symlink with the canonical plain-English style selected + `~/.copilot/copilot-instructions.md` symlink, no-authorship, and Context Mode wiring when the Copilot CLI is installed (home created when missing; exact skip message otherwise) + `CODEX_HOME`, `CLAUDE_CONFIG_DIR`, and `COPILOT_HOME` honoured for every agent home + global Git-hook dispatcher compared by resolved path + one fast shared guard for Codex, Claude Code, and Copilot + one managed PATH block. + development contracts run only inside a Git checkout (release installs skip them)
- `hard-eng prepare|status|uninstall` = tracked or privately ignored `hard-eng.gates.json` admission + healthy-global selection OR GitHub-attested immutable release under ignored `.agents/hard-eng/` + generated `AGENTS.override.md` (repository rules first, Hard Eng rules second, fail closed above the Codex 32 KiB project document limit) + `CLAUDE.local.md` import + `.github/instructions/hard-eng.instructions.md` + native hooks/skills/agents/output-style links + `generated` digests that heal untouched drift and refuse hand edits + uninstall that strips only Hard Eng hook entries from user-modified hook files; no marker = exact pass-through; partial global state = fail closed; tracked repository bytes remain unchanged; the guard answers Copilot in its own hook format when Copilot invokes the Claude hook entry. + native hook trust: Codex runs repository hooks only in trusted projects after its hook review (`codex exec` needs `--dangerously-bypass-hook-trust` until reviewed), Copilot runs repository hooks only inside `trustedFolders` while the global user-level hook runs everywhere, Claude Code runs them in every mode including `-p` + shared mode: `prepare --shared` and `update --shared` select + pin the newest allowed release by tag + SHA-256 digests in `hard-eng.gates.json`; `prepare` in a pinned repository verifies the private cache by tree digest or runs the committed `.hard-eng/bootstrap.sh` (HTTPS release download, pin digest check, tarfile data filter, no working-tree writes); `.hard-eng/hook.sh` runs the cached guard, exits 0 when `.agents/hard-eng/global-guard` lists the agent, and otherwise denies pretooluse until the cache exists; committed hook files merge Hard Eng session-start + pre-tool entries with git-root command paths and keep foreign entries; tracked generated files are admitted only from the shared set and healed only when they carry the Hard Eng marker; `uninstall --shared` removes the generated files, strips Hard Eng hook entries, and drops the pin
- `setup.sh learning-install|learning-check` = canonical global learning-agent links for Codex, Claude Code, and Copilot CLI.
- `~/.agents/setup.sh repo-install <repository>|repo-check <repository>` = repository learning validation + canonical `.agents/skills` ownership + Claude `.claude/skills` discovery links; Codex and Copilot use the canonical repository skills directly.
- Agent guard = blocks known irreversible destructive Git/database/file actions + secret exposure + raw lifecycle-control writes + configured Direct file writes or mechanically classified connector changes outside the current receipt; external reads + opaque shell effects + subagents + recoverable actions inside the recorded Direct scope continue; route/research/lifecycle drift still fails the next repository checkpoint; a write or `git init` in a repository without gate wiring surfaces one per-session Claude Code routing notice without blocking.
- Feature folder = one living `PLAN.md` while nonterminal + script-owned `tickets/T-*.md` after an epic decomposes; any other Markdown file, a symlinked plan, or a second nonterminal Feature Brief blocks lifecycle and supported write paths.
- Execution evidence = current `research.json` + exact `authorization.json`, approved once by the user's plain reply and valid for that brief until reopened, no session or expiry; configured Direct work records one Git-private receipt whose intended paths + exact named connector action digests/effects gate live known writes, widened anytime by re-running `start-direct`, unaffected by commits; repository-identity mismatch still blocks; irreversible destructive actions keep the separate one-use exact `protected-action.json`, authorized by the user's plain yes and consumed once.
- Publish gate = `scripts/git-hooks/publish-gate.sh`; pre-commit = one manifest-owned staged format/lint scan + enforcement-owner check; pre-push and CI = the same manifest-owned full phase with typecheck + format + lint + tests + pinned Fallow + Python types + Python format/lint + full contracts + managed-skill + design + file-size ratchet + full-tree secrets scan + enforcement checks; unchanged exact-tree contract proof is reused only while repository and runtime identities match.
- Lifecycle screenshots, recordings, and UX references = local display/proof; Git delivery only when explicitly accepted as product assets.
- Managed skills = `.skill-lock.json` + pinned `npx skills@1.5.22` through `scripts/update-managed-skills.sh`.
- Daily CI = model-free `03:30 UTC` locked-skill update; direct default-branch commit when changed.
- Main release = every eligible successful canonical `main` push publishes one immutable `v0.1.0-alpha.g<source-sha>` GitHub prerelease for the exact pushed commit + deterministic source archive/manifest + verified asset hashes + GitHub release attestation; eligibility requires source `.github/workflows` to match current `main`; an older workflow-different source fails before publication because the built-in Actions token cannot receive workflow-write access; the managed-skill updater reads back remote `main` and dispatches that exact commit through the release workflow; pull requests + manual runs + untrusted dispatches + failed/cancelled/skipped required CI publish nothing.

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
- Installation + pins = `install.sh` + `scripts/install-contract-check.py` + `setup.sh` + `scripts/setup/manifest.json` + `.skill-lock.json`.

## Unknowns

- Baseline token/time/defect data = collect across comparable completed tasks.
