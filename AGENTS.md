# Agent Rules

## Stop
- Material uncertainty/conflict → evidence → 1 question → wait; non-trivial mutation requires unknowns resolved.
- Material correction changing scope/owner/accepted state → reconcile → show delta → confirm → mutate; clear bounded correction → continue.
- Selected `$he` goal/PLAN/state mismatch → pause; owner choice is never silent.
- Destructive action/external write/commit/push/merge/publish → exact scoped approval.
- Secret/credential exposure → stop + report.

## Engineering
- Non-trivial mutation → `$deterministic-checks` worktree `write` PASS; commit/push → `publish` PASS.
- Existing linked worktree/branch → continue; clean primary/main → direct; requested worktree → create.
- Dirty primary + unrelated user work + no choice → ask once: current checkout OR new worktree; automatic worktree/branch = forbidden.
- Worktree input = required ignored files via `.worktreeinclude`; rebuildable via setup; broad ignored-copy = forbidden.
- Approved PLAN handoff → `$he` Transfer; baseline commit/recreated PLAN/manual rebind = forbidden.
- KISS = fewest complete concepts; YAGNI = no speculation; DRY = fact once; SSOT = canonical owner.
- Correctness = root + blast radius; fix = owner + connected caller/schema/key/test/route/doc/config/live wire.
- Replacement = full migration + delete legacy/alias/compatibility/dual paths; patchwork/pass-through wrappers = forbidden.
- Preserve security/trust/privacy/accessibility/schema/data-loss protections.
- File ≤700 lines → else split; indivisible generated/schema or focused parser/scanner/dense contract test → reason + deterministic proof.
- Goal/automatic continuation = explicit user request; else turn-bounded.
- Completed long task + new problem → recommend fresh task + context-cost reason.

## Route
- Default = direct.
- Route scope = current request only; unrelated/terminal goal/PLAN/state ≠ routing input.
- Direct eligibility = bounded outcome + owner + no unresolved product/UX/architecture decision or staged coordination.
- Direct examples = UI height/spacing/color/copy + contained fix/refactor/test/doc/config/read-only.
- Direct flow = evidence → worktree `write` PASS → owner edit → focused gates → visible UI proof → report.
- Direct autonomy = clear outcome + no material unknown → choose + finish; workflow/continuation permission question = forbidden.
- Direct forbids PLAN/context-doc initialization; missing/invalid `PRODUCT.md` or `DESIGN.md` alone ≠ escalation/blocker.
- `$he` eligibility = explicit lifecycle request OR material cross-boundary capability needing durable decisions + staged PLAN.
- Size/count/`feature` label ≠ `$he`; new product/UX decision during direct → pause + `$he`.
- After `$he` selection only: missing/invalid root PRODUCT/DESIGN → repository gate before lifecycle advance.
- Bug/flake/failure/regression → `$diagnosing-bugs`; Sentry evidence → `$sentry`.
- Tests/QA/TDD → `$test-quality`; real UI proof → `$e2e`.
- Requested/produced visual proof → `$e2e` actual-media receipt PASS before goal/build/ship/final PASS.
- Commands/gates/CI → `$deterministic-checks`; module/API/ownership/wrapper/test-seam → `$codebase-design`.
- Existing UI owner/layout/style → `$atomic-ui` direct; reusable design SSOT/new product UX → `$atomic-ui` + eligible `$he`.
- Security → `$security-review`; branch/PR/WIP → `$code-review`; repeated root/approach ≥2 → `$repeated-failure-learning` → `$he-learn`.
- `$he` = sole lifecycle router + state gate.
- Stage owners = `$he-plan` → `$he-build` (Implement ⇄ Verify) → `$he-ship`.
- Explicit lifecycle persistence → `$he` Continuity goal contract.
- Lifecycle continuity = `PASS` + route + no boundary → checkpoint + same-turn owner; final answer/`continue?` = forbidden.
- Lifecycle pause = `CONCERNS|FAIL` + material question + explicit scope end + external approval/wait boundary.
- Finding + accepted outcome + no new material decision → current owner fix ⇄ verify; PLAN reopen = forbidden.
- PLAN reopen = changed user decision invalidates intent; unchanged downstream proof auto-revalidates without generic approval.
- Proven process gap → `$he-learn` overlay; lifecycle unchanged; prevention = current stage owner.
- Cross-repository prevention = source pause + bounded destination repair; nested lifecycle only if destination qualifies.
- Missing required stage → stop + report; replacement improvisation = forbidden.
- Subagents = current user prompt explicitly requests; omitted count → ≤4 direct + depth=1; background/unsolicited/nested otherwise = forbidden.
- Unsolicited model evals/Imagegen/daemons/cron/watchdogs/blind retries = forbidden.
- `$he-build` bounded final audit via read-only `codex exec` = allowed after deterministic green; finding-driven fix ⇄ verify ≠ blind retry.
- Hard Eng audit = PLAN `risk_tier`; standard → 1 Sol-medium; critical → 2; payment/auth/security/privacy/destructive-data/uncertainty → critical.
- Audit finding → owner fix ⇄ same-tier clean; repeated root/user decision → pause; workers ≤8; convergence-only = forbidden.

## Tools
- External-contract-dependent plan/code/review/claim → `$research` primary-source `PASS`; memory/local code/types/tests/secondary ≠ proof.
- Current facts/library docs → `$research`; Context7 = CLI in library-doc branch only.
- Sentry remediation → `$sentry` CLI only.
- Codebase Memory = topology/callers/dependencies/routes/architecture/impact; CLI `codebase-memory-mcp cli <tool> '<bounded-json>'`.
- Memory start = `list_projects` → project → stale/missing `index_repository` → `get_graph_schema`.
- Memory tools = symbol `search_graph`; calls `trace_path`; diff `detect_changes`; arch `get_architecture`; source `get_code_snippet`; text `search_code`; Cypher `query_graph`; ADR `manage_adr`; traces `ingest_traces`; status `index_status|delete_project`; raw `--raw | jq`.
- CLI failure → report once → bounded `rg`; noisy supported CLI → `rtk`; exact/raw/unsupported → native.
- Context Mode = large/unknown output; `ctx_execute` derive; `ctx_execute_file` file/build; `ctx_batch_execute` 3+ commands; `ctx_index` reused docs; `ctx_search` batch questions.
- Output ≤8K; raw only for bounded exact evidence. Browser = reuse + batches + targeted evidence; full snapshot only visual/debug proof.
- GitHub = authenticated `gh` CLI; scopes `repo,workflow,read:org,gist,admin:public_key,delete_repo`; capability ≠ approval.
- Exact text/path → `rg`; file mutation → `apply_patch`.
- Project script/gate/build/test/dev → `$deterministic-checks` bounded runner + explicit whole-run timeout; raw unbounded launch = forbidden.

## Proof
- Read before claim/edit; validation breadth ≥ blast radius; recurring violation → narrow deterministic check.
- Evidence = `Verified | Inferred | Unknown`.
- Final = `PASS | CONCERNS | FAIL` + why/risk/proof/gaps.
- Commit/push/merge/publish requires its approval boundary.

## Markdown
- Agent-facing `.md` = terse directives; paragraph prose = forbidden.
- Syntax = mapping `=`; composition `+`; routing `→`; sequence `→ ⇄`; symbols remain unambiguous to weak/local models.
- `README.md` = human writing.
- Canonical docs = accepted current state only; omit before/rejected/migration history.
