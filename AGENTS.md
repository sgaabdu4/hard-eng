# Agent Rules

## Stop
- Material uncertainty/conflict → inspect evidence → ask 1 targeted question → wait.
- Non-trivial mutation → resolve all material unknowns first.
- User correction → pause → reconcile goal + plan/state → show delta → confirm → mutate.
- Goal/plan/state mismatch → pause; never choose an owner silently.
- Destructive action/external write/commit/push/merge/publish → exact scoped approval.
- Secret/credential exposure → stop + report.

## Engineering
- Non-trivial mutation → `$deterministic-checks` worktree `write` PASS; commit/push → `publish` PASS.
- Checkout = existing linked worktree OR clean primary; dirty primary (staged + unstaged + untracked) → isolated worktree; branch prefix = unrestricted.
- Worktree inputs = required ignored files via root `.worktreeinclude`; rebuildable state via setup; broad ignored-copy = forbidden.
- Approved PLAN handoff → `$he` Transfer; baseline commit/recreated PLAN/manual rebind = forbidden.
- KISS = fewest complete concepts.
- YAGNI = remove speculation; never omit correctness/root cause/blast radius.
- DRY = one fact once.
- SSOT = one canonical owner.
- Fix = root owner + every connected caller/schema/key/test/route/doc/config/live wire.
- Replacement → full migration; delete legacy/alias/compatibility/dual paths.
- Patchwork/pass-through wrappers = forbidden.
- Preserve security/trust/privacy/accessibility/schema/data-loss protections.
- Touched/connected file ≤700 lines; otherwise split before handoff. Exception = indivisible generated/schema-bound data (e.g. JSON) or focused parser/scanner/dense contract test → explicit reason + deterministic proof.

## Route
- Hard Eng lifecycle/new feature/material behavior/resume/status/plan/build/ship/learn → `$he`.
- Repository context = root `PRODUCT.md` + `DESIGN.md`; missing/invalid → `$he` repository gate before lifecycle advance.
- Bug/flake/failure/regression → `$diagnosing-bugs`; Sentry runtime evidence → `$sentry`.
- Tests/QA/TDD/mutation → `$test-quality`; real browser/device UI proof → `$e2e`.
- Requested/produced visual proof → `$e2e` actual-media receipt PASS before goal/build/ship/final PASS.
- Commands/analyzers/scanners/hooks/CI gates → `$deterministic-checks`.
- Module/API/ownership/abstraction/wrapper/test-seam design → `$codebase-design`.
- UI token/theme/component/design-SSOT work → `$atomic-ui`; new product/UX decision → `$he`.
- Defensive application security review → `$security-review`; branch/PR/WIP verdict → `$code-review`.
- Same root cause or failed approach ≥2 times → `$repeated-failure-learning` evidence → `$he-learn`.
- New product decision discovered during direct work → `$he`.
- `$he` = sole lifecycle router + state gate.
- Stage owners = `$he-plan` → `$he-build` (Implement ⇄ Verify) → `$he-ship`.
- Learning overlay = proven process gap at any stage → `$he-learn`; lifecycle unchanged; prevention mutation → current stage owner.
- Small clear fix/read-only audit/explanation → direct.
- Missing required stage → stop + report; never improvise a replacement.
- Background/unsolicited subagents/model evals/Imagegen/daemons/cron/watchdogs/blind retries = forbidden.
- `$he-build` bounded final audit via read-only `codex exec` = allowed after deterministic green; finding-driven fix ⇄ verify ≠ blind retry.

## Tools
- Current/external facts or library documentation → `$research`; Context7 = CLI only inside its library-doc branch.
- Sentry issue remediation → `$sentry`; transport = installed `sentry` CLI only.
- Codebase Memory = topology/callers/dependencies/routes/architecture/impact; CLI only: `codebase-memory-mcp cli <tool> '<bounded-json>'`.
- Start = `list_projects` → exact `name` as `project`; missing/stale/corrupt → `index_repository {"repo_path":"<abs>"}`; then `get_graph_schema`.
- Route = symbol `search_graph`; calls `trace_path`; diff `detect_changes`; architecture `get_architecture`; source `get_code_snippet`; text `search_code`; Cypher `query_graph`; ADR `manage_adr`; traces `ingest_traces`; status/removal `index_status|delete_project`; raw → `cli <tool> '<bounded-json>' --raw | jq`.
- CLI failure → report once → bounded `rg` fallback.
- Noisy supported CLI output → `rtk <command>`; exact/raw/unsupported output → native command.
- Large evidence → bounded Context Mode.
- Exact text/path → `rg`.
- File mutation → `apply_patch`.

## Proof
- Read before claim/edit.
- Validation breadth ≥ change blast radius.
- Recurring violation → narrow deterministic check.
- Evidence class = `Verified | Inferred | Unknown`.
- Final status = `PASS | CONCERNS | FAIL`; include why, risk, proof/gaps.
- No commit/push/merge/publish without its approval boundary.

## Markdown
- Agent-facing `.md` = terse directives; paragraph prose = forbidden.
- Syntax = mapping `concept = owner`; composition `A + B`; routing `condition → action`; sequence `A → B ⇄ C`.
- Symbols must remain unambiguous to weak/local models.
- `README.md` = human writing.
- Canonical docs = current accepted state only; omit before/rejected/migration history.
