# Agent Rules

## Stop
- Material uncertainty = evidence → `question-me` → wait; material = product outcome + UX behavior + default/policy + security/privacy + data loss + irreversible choice + delivery form/lifetime when it changes observable operation or durable surface.
- Reversible engineering detail = agent-owned; choose from repository evidence + verify.
- Accepted outcome or material risk contract change = show exact delta → confirm → update brief/state.
- File/owner/caller/schema/key/test/route discovery with unchanged outcome/risk = Implement ⇄ Verify; reapproval forbidden.
- Terminal PLAN cleanup = prove terminal state + exact path/hash → scoped destructive approval; active/nonterminal PLAN deletion forbidden.
- Destructive action/external write/commit/push/merge/publish = state target + effect → user's plain yes/approved suffices.
- Publish approval closure = stated action + its hooks + automatic workflows + downstream external writes; undisclosed automation = unapproved.
- Approval answers the immediately preceding proposed action only; unchanged steps/retries stay covered; changed target/effect → ask again.
- Secret/credential exposure = stop + never repeat/store + request rotation/revocation through safe channel.
- External UI/account action = verify app + environment + profile + account + tenant; mismatch/user stop → stop.

## Engineering
- Non-trivial mutation = `deterministic-checks` worktree `write` PASS; commit/push = `publish` PASS.
- Gate scope = affected-full: universal gates + full gate row per impacted owner; global/shared/toolchain/CI change or uncertainty → full repository.
- Gate concurrency = independent affected owners parallel; dependencies/shared state sequential; external mutation serial.
- Release actor = one per target + environment + revision; manual + CI overlap forbidden; alternate actor waits for terminal/cancelled receipt.
- Existing linked worktree/branch = continue; clean primary/main = direct; requested worktree = create.
- Dirty primary + unrelated user work + no choice = ask once: current checkout OR new worktree; automatic worktree/branch forbidden.
- Worktree input = required ignored files via `.worktreeinclude`; rebuildable via setup; broad ignored-copy forbidden.
- KISS = fewest complete concepts; YAGNI = no speculative scope; DRY = fact once; SSOT = canonical owner.
- Code comment = necessary non-obvious constraint only + a few words max; default = none.
- Correctness = root cause + blast radius + connected owner/caller/schema/key/test/route/doc/config/live wire.
- Preserve security + trust + privacy + accessibility + schema + data-loss protections.
- File ≤700 lines; generated/schema or focused parser/scanner/dense contract test exception = reason + deterministic proof.
- Context reset = default at slice green checkpoint + allowed at alignment boundary; accepted brief/state + evidence receipt = resume owner; new approval forbidden.
- Goal/automatic continuation = explicit user request.
- Terminal handoff + unrelated request = recommend fresh task + context-cost reason; never inherit PLAN + approval + scope.
- Commentary = material state change + blocker + approval boundary + proof + bounded elapsed-wait status; batch routine narration + omit unchanged polling.

## Route
- Default = Direct.
- Route scope = current request only; unrelated/terminal goal/PLAN/state excluded.

| Route | Trigger | Contract | Exit |
|---|---|---|---|
| Direct | bounded clear outcome + no material unresolved decision | evidence → edit owner → focused proof | applicable gates green |
| Feature Loop | new/changed observable capability needing alignment | lean Feature Brief → one Ready-to-build approval → vertical slices | accepted outcome proven |
| Diagnose | bug + flake + failure + regression | reproduce → root cause + blast radius → fix | regression proof green |
| Critical overlay | payment/auth/security/privacy/destructive-data/irreversible slice or material uncertainty | strengthen only affected slice + proof + review | critical risk contract proven |

- Size/file count/`feature` label alone = no route escalation.
- Direct examples = contained UI/copy/refactor/test/doc/config/read-only work.
- Feature alignment = `question-me` until aligned; arbitrary question limit = none.
- Brief shape + Ready-to-build approval mechanics + feature states = `he` + `he-plan` owners; destructive/external/Git/publish boundaries remain separate.
- Discovery during build = update implementation evidence + affected proof; unchanged outcome/risk continues automatically.
- Replan = accepted outcome change OR material risk contract change; reopen smallest affected brief section + downstream proof.
- Critical overlay = slice-scoped; safe slices keep standard flow.
- Process learning = record proven gap → continue delivery; block only when continued work risks protected boundary.
- Bug/flake/failure/regression → `diagnosing-bugs`; Sentry evidence → `sentry`.
- Tests/QA/TDD → `test-quality`; real UI proof → `e2e`.
- Requested/produced visual proof → `e2e` actual-media receipt PASS before goal/build/ship/final PASS.
- Commands/gates/CI → `deterministic-checks`; module/API/ownership/wrapper/test-seam → `codebase-design`.
- Existing UI owner/layout/style → `atomic-ui` direct; reusable design SSOT/new product UX → `atomic-ui` + Feature Loop.
- Security → `security-review`; branch/PR/WIP → `code-review`.
- Repeated process root ≥2 → `repeated-failure-learning` → `he-learn`; lifecycle unchanged.
- `he` = Feature Loop lifecycle router + state owner.
- Stage owners = `he-plan` → `he-build` (Implement ⇄ Verify) → `he-ship`; `he-learn` = non-blocking overlay unless protected boundary at risk.
- Explicit lifecycle persistence = `he` Continuity.
- Missing required stage = stop + report; replacement improvisation forbidden.
- Subagents = current user prompt explicitly requests; sanctioned exception = one depth-1 isolated media reader for `e2e` receipt review; omitted count → ≤4 direct + depth=1; background/unsolicited/nested otherwise forbidden.
- Unsolicited model evals/Imagegen/daemons/cron/watchdogs/blind retries forbidden.
- Review = actual diff + affected behavior + risk-targeted proof.
- Standard review = focused owner review; critical affected slice = specialist + independent review as risk requires.
- Review finding = implementation defect → fix + affected proof; outcome/risk discovery → replan; finding never authorizes mutation.

## Tools
- External-contract-dependent decision/code/review/claim → `research` primary-source PASS.
- Current vendor/library fact → `research`; memory/local code/types/tests/secondary source ≠ external proof.
- Sentry remediation → `sentry` CLI only.
- Codebase Memory = topology/callers/dependencies/routes/architecture/impact; CLI `codebase-memory-mcp cli <tool> '<bounded-json>'`.
- Memory start = `list_projects` → project → stale/missing `index_repository` → `get_graph_schema`.
- CLI failure = report once → bounded `rg`; noisy supported CLI → `rtk`; exact/raw/unsupported → native.
- Context Mode = large/unknown output; index reused docs; batch ≥3 independent reads; retain decisions + receipts, discard exploration.
- Analysis-only file/log/diff read = Context Mode sandbox; direct raw read = imminent edit target or bounded exact evidence only.
- Output ≤8K; raw only for bounded exact evidence; browser = reuse + batches + targeted proof.
- Shared session/preferences/account CLI = sequential; parallel work requires independent state + files.
- Ephemeral probe = `mktemp` owner + cleanup before final; durable receipt = repository/runbook-approved owner.
- GitHub = authenticated `gh` CLI; capability ≠ approval.
- Exact text/path = `rg`; file mutation = `apply_patch`.
- Project command/gate/build/test/dev = `deterministic-checks` bounded runner + explicit whole-run timeout.

## Proof
- Read before claim/edit; validation breadth ≥ blast radius.
- Evidence = `Verified | Inferred | Unknown`.
- Final = `PASS | CONCERNS | FAIL` + why + risk + proof + gaps.
- Remote PASS = required CI jobs green for the delivered commit; workflow-level green alone = insufficient.
- Commit/push/merge/publish = separate approval boundary.

## Markdown
- Agent-facing `.md` = terse directives; paragraph prose forbidden.
- Syntax = mapping `=` + composition `+` + routing `→` + loop `⇄`.
- Skill reference = canonical backticked name without runtime invocation sigil; cross-runtime portability required.
- `README.md` = human writing.
- `CLAUDE.md` = `@AGENTS.md` import stub only; repository override stub = `CLAUDE.local.md` → `@AGENTS.override.md`; instruction edits → `AGENTS.md`.
- Canonical docs = accepted current state only; rejected/migration history omitted.
