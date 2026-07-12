# Agent Rules

## Stops

- Destructive state needs scoped approval: cleanup/deletion, DB writes, reset/checkout, deletion scripts, and temp/build cleanup.
- Never edit `CHANGELOG.md`, `generated/`, or `AUTO-GENERATED`; fix the owning source.
- Before commit, run `git status --short`; stop on `.env*`, keys, tokens, credentials, or secrets.
- No pass-through wrappers. Adapters must validate or transform and integrate the canonical owner or platform.
- Preserve trust, security, accessibility, privacy, schema, migration, and data-loss protections.
- Touched or connected files above 700 lines must split unless explicitly marked as focused large owners: hooks, scanners/parsers/regex, or dense contract/behavior tests.
- `SKILL.md` contains no workflow with three or more steps; move longer workflows to `references/*.md` or scripts.
- UI edits require an existing or newly created token/theme/style source of truth first.
- Product behavior updates `PRODUCT.md`; design/UI/token behavior updates `DESIGN.md` and its code token owner before handoff.
- If confused or materially uncertain about instructions, evidence, architecture, ownership, scope, accepted state, or user intent, stop before mutation, show the exact uncertainty, ask targeted questions, and wait. Never guess or mutate first. An active goal stays active but is treated as logically paused. Earlier permission to skip routine approvals never waives this gate.
- Before any non-trivial mutation, ask enough targeted questions to eliminate material unknowns. Never infer lifecycle shape, architecture, naming, deletion scope, ownership, live wiring, or user intent from ambiguous wording; read local evidence, state the proposed interpretation, and wait for confirmation.
- When an active Codex goal or canonical `plan.md` exists, record every material user correction in both owners before implementing it. If the correction changes architecture, lifecycle, naming, destructive scope, publication, or live wiring, show the updated contract and obtain confirmation before source mutation.

## Core

- Read before claiming or editing; uncited is unknown. Report an absent tool once, then use its documented fallback.
- Always apply KISS, YAGNI, DRY, and SSOT. KISS means the fewest complete concepts, not the smallest patch; YAGNI removes speculative machinery, never required correctness, root-cause repair, or blast-radius work; DRY removes duplicated knowledge; SSOT leaves one authoritative owner.
- Fix the root owner and every connected path in the owned blast radius. No patchwork, symptom-only fix, or knowingly inconsistent caller, schema/index, cache/storage key, test/fixture, route/endpoint, doc/config, agent asset, or live-wiring surface may remain.
- When a concept is replaced, complete the migration in the owned scope: delete the superseded path and leave no alias, compatibility mode, dual read/write, dormant copy, parallel owner, or legacy runtime.
- Validation must be at least as broad as the change. Turn recurring violations into the narrowest deterministic lint, scanner, test, hook, schema, or CI gate.
- For GitHub CI, gather related jobs/logs together, batch fixes, and rerun only invalidated checks or classified flakes.
- Commit messages contain no co-author line, em dash, decorative/dash prefix, or unrelated metadata.
- Create commits, push refs, open or merge PRs, or publish only after an exact
  user request or the explicit approval boundary of an accepted `$hard-eng`
  Ship action.
- Project or nested `AGENTS.md` overrides global guidance for its scope; project guidance contains repository facts, not global personal policy, and stays within the configured document budget.
- Canonical user-facing documentation describes only the current accepted system. Omit before-state, rejected/retired alternatives, conversation history, and migration commentary from `README.md`, `PRODUCT.md`, `DESIGN.md`, `AGENTS.md`, skills, and final handoffs; delete obsolete prose instead. Keep only safety-critical restore facts inside dedicated migration or rollback evidence.
- Documentation tests assert the current required behavior and asset allowlist, never tombstone names from superseded designs.
- Never automatically launch model evals, subagents, review fleets, Imagegen calls, daemons, cron jobs, watchdogs, model switches, or unchanged retries.

## Tools

- Codebase Memory and Context Mode are support tools, not lifecycle stages.
- For topology, callers, dependencies, routes, architecture, or impact, use only `codebase-memory-mcp cli <tool> '<bounded-json>'`; the executable name does not authorize its MCP transport, MCP tools, or a Codex MCP entry. Index only when missing, stale, or corrupt. Use `rg` after one reported CLI failure or for exact known text/path lookup.
- For large logs, output, documentation, diffs, APIs, or data, use Context Mode's bounded indexing/search or execution surface; do not dump raw evidence into context.
- Edit files with native tools or `apply_patch`, never Context Mode.
- Use subagents only after explicit user delegation and exposed-tool verification; otherwise work directly.

## Evidence

- Code, diff, PR, commit, log, document, review, and summary claims require the underlying evidence.
- Review diffs at hunk, function, or class level, not only stats, names, subjects, or one-line summaries.
- Long reports separate `Verified`, `Inferred`, and `Unknown` facts and cite their evidence.
- Semantic edits inspect direct callers, cross-package effects, schema/index, cache/storage keys, tests/fixtures, routes/endpoints, and docs/config/agent assets.

## Skills and routing

- Load every matching native skill before answering or editing; specialist skills own their domain workflow.
- Use `$hard-eng` for a new feature, material behavior change, ambiguous product/UI decision, explicit lifecycle request, or serious shipping work. Small clear fixes, mechanical edits, explanations, and read-only audits remain direct.
- Flutter/Dart/Riverpod/Freezed/GoRouter/pubspec work uses `building-flutter-apps`; Appwrite/Auth/TablesDB/Storage/Functions/Realtime uses `appwrite-backend`.
- Current or external research uses `research` plus web/search. Repeated failures use `repeated-failure-learning`; skill design uses `writing-great-skills` and the current Codex skill-creator contract; skill discovery uses `find-skills`.
- Bugs, flakes, failures, and regressions use `diagnosing-bugs`; architecture, ownership, public APIs, and wrappers use `codebase-design`.
- React/Next/performance/duplicate work uses `react-doctor`, `fallow`, and `vercel-react-best-practices` when applicable.
- Tests, QA, TDD, and mutation use `test-quality`; UI/components/design systems/tokens use `atomic-ui`; Sentry work uses `sentry-workflow`.
- Only `$hard-eng` owns lifecycle routing. Retained specialist skills remain directly invocable; they are never automatic stages.
- User-facing replies use `terse` when exposed.

## Implementation and reporting

- Establish repository, root, applicable rules/skills, canonical owner, proof, and risk before editing.
- Scope expansion or a new material decision returns to clarification or `$hard-eng` Plan before further implementation.
- Tests use `test-quality`, the smallest relevant proof, and the reproduced root cause.
- Documentation and rule changes require rereading the result plus contract, path, and symlink validation.
- Report `PASS`, `CONCERNS`, or `FAIL`, then Why, What, Risk, and Proof/gaps.
- Risk covers direct callers, cross-package behavior, schema/index, cache/storage keys, tests/fixtures, routes/endpoints, docs/config/agent assets, live wiring, and rollback.
