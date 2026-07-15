# Agent Rules

## Stop
- Material uncertainty/conflict → inspect evidence → ask 1 targeted question → wait.
- Non-trivial mutation → resolve all material unknowns first.
- Material correction changing scope/owner/accepted state → reconcile → show delta → confirm → mutate; clear bounded correction → continue.
- Selected `$he` goal/PLAN/state mismatch → pause; never choose an owner silently.
- Destructive action/external write/commit/push/merge/publish → exact scoped approval.
- Secret/credential exposure → stop + report.

## Engineering
- Non-trivial mutation → `$deterministic-checks` worktree `write` PASS; commit/push → `publish` PASS.
- Checkout = existing linked worktree/branch → continue; clean primary/main → direct allowed; user-requested worktree → create.
- Dirty primary + unrelated user changes + no prior choice → ask once: current checkout OR new worktree; automatic worktree/branch = forbidden.
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
- Default = direct.
- Route scope = current request only; unrelated/terminal goal/PLAN/state ≠ routing input.
- Direct eligibility = clear bounded outcome + existing owner + no unresolved product/UX/architecture decision + no required persistent staged coordination.
- Direct examples = UI height/spacing/color/copy + contained fix/refactor/test/doc/config + read-only work.
- Direct flow = specialist evidence → worktree `write` PASS → owner edit → focused gates → UI runtime proof when visible → report.
- Direct autonomy = clear outcome + no material unknown → choose local implementation + finish; workflow/continuation permission question = forbidden.
- Direct forbids PLAN/context-doc initialization; missing/invalid `PRODUCT.md` or `DESIGN.md` alone ≠ escalation/blocker.
- `$he` eligibility = explicit lifecycle request OR material new capability/cross-boundary product change requiring durable decisions + staged PLAN state.
- Code size/file count/`feature` label alone ≠ `$he`; new product/UX decision discovered during direct work → pause + `$he`.
- After `$he` selection only: root `PRODUCT.md` + `DESIGN.md` missing/invalid → repository gate before lifecycle advance.
- Bug/flake/failure/regression → `$diagnosing-bugs`; Sentry runtime evidence → `$sentry`.
- Tests/QA/TDD/mutation → `$test-quality`; real browser/device UI proof → `$e2e`.
- Requested/produced visual proof → `$e2e` actual-media receipt PASS before goal/build/ship/final PASS.
- Commands/analyzers/scanners/hooks/CI gates → `$deterministic-checks`.
- Module/API/ownership/abstraction/wrapper/test-seam design → `$codebase-design`.
- Existing UI owner/layout/style change → `$atomic-ui` direct; reusable token/theme/component/design-SSOT or new product/UX decision → `$atomic-ui` + `$he` when `$he` eligibility holds.
- Defensive application security review → `$security-review`; branch/PR/WIP verdict → `$code-review`.
- Same root cause or failed approach ≥2 times → `$repeated-failure-learning` evidence → `$he-learn`.
- `$he` = sole lifecycle router + state gate.
- Stage owners = `$he-plan` → `$he-build` (Implement ⇄ Verify) → `$he-ship`.
- Lifecycle continuity = `PASS` + valid `route_target` + no user/external boundary → checkpoint + same-turn next owner; final answer/`continue?` = forbidden.
- Lifecycle pause = `CONCERNS|FAIL` + material question + explicit scope end + external approval/wait boundary.
- Finding + accepted outcome + no new material decision → current owner fix ⇄ verify; PLAN reopen = forbidden.
- PLAN reopen = changed user decision invalidates accepted intent; unchanged downstream proof revalidates automatically without generic approval.
- Learning overlay = proven process gap at any stage → `$he-learn`; lifecycle unchanged; prevention mutation → current stage owner.
- Cross-repository prevention = source pause + bounded destination repair; nested lifecycle only when destination independently meets `$he` eligibility.
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
- Project script/gate/build/test/dev command → `$deterministic-checks` bounded runner + explicit whole-run timeout; raw unbounded launch = forbidden.
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
