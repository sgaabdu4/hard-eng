# Agent Rules

## Stop
- Material uncertainty = evidence → batch questions → wait; material = product outcome + UX behavior + default/policy + security/privacy + data loss + irreversible choice.
- Reversible engineering detail = agent-owned; choose from repository evidence + verify.
- Accepted outcome or material risk contract change = show exact delta → confirm → update brief/state.
- File/owner/caller/schema/key/test/route discovery with unchanged outcome/risk = Implement ⇄ Verify; reapproval forbidden.
- Selected `$he` PLAN/state mismatch or unreadable canonical checkpoint = pause; deletion/ignore/recreation/bypass forbidden.
- Destructive action/external write/commit/push/merge/publish = exact target + exact scoped approval.
- Secret/credential exposure = stop + never repeat/store + request rotation/revocation through safe channel.
- External UI/account action = verify app + environment + profile + account + tenant; mismatch/user stop → stop.

## Engineering
- Non-trivial mutation = `$deterministic-checks` worktree `write` PASS; commit/push = `publish` PASS.
- Existing linked worktree/branch = continue; clean primary/main = direct; requested worktree = create.
- Dirty primary + unrelated user work + no choice = ask once: current checkout OR new worktree; automatic worktree/branch forbidden.
- Worktree input = required ignored files via `.worktreeinclude`; rebuildable via setup; broad ignored-copy forbidden.
- KISS = fewest complete concepts; YAGNI = no speculative scope; DRY = fact once; SSOT = canonical owner.
- Correctness = root cause + blast radius + connected owner/caller/schema/key/test/route/doc/config/live wire.
- Replacement = full migration + legacy/alias/compatibility/dual-path deletion; canonical explicit one-time state converter excluded.
- Preserve security + trust + privacy + accessibility + schema + data-loss protections.
- File ≤700 lines; generated/schema or focused parser/scanner/dense contract test exception = reason + deterministic proof.
- Context reset = allowed at alignment or slice boundary; accepted brief/state + evidence receipt = resume owner; new approval forbidden.
- Goal/automatic continuation = explicit user request.
- Completed long task + unrelated new problem = recommend fresh task + context-cost reason.

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
- Feature Brief = Outcome + Non-goals + Material decisions + Acceptance examples + Affected canonical areas + Risk and rollback + First vertical slice.
- Feature state = `planning | build-ready | building | green | shipped | cancelled`.
- Feature alignment = ask material questions in one batch where possible + dependent questions sequentially until aligned; arbitrary question limit = none.
- Ready-to-build approval = accepted brief only; destructive/external/Git/publish boundaries remain separate.
- Build = one vertical slice → Implement ⇄ Verify → checkpoint; no whole-plan reapproval between slices.
- Green = unchanged full gate + exact non-PLAN artifact fingerprint; drift → `building`.
- Discovery during build = update implementation evidence + affected proof; unchanged outcome/risk continues automatically.
- Replan = accepted outcome change OR material risk contract change; reopen smallest affected brief section + downstream proof.
- Critical overlay = slice-scoped; safe slices keep standard flow.
- Process learning = record proven gap → continue delivery; block only when continued work risks protected boundary.
- Bug/flake/failure/regression → `$diagnosing-bugs`; Sentry evidence → `$sentry`.
- Tests/QA/TDD → `$test-quality`; real UI proof → `$e2e`.
- Requested/produced visual proof → `$e2e` actual-media receipt PASS before goal/build/ship/final PASS.
- Commands/gates/CI → `$deterministic-checks`; module/API/ownership/wrapper/test-seam → `$codebase-design`.
- Existing UI owner/layout/style → `$atomic-ui` direct; reusable design SSOT/new product UX → `$atomic-ui` + Feature Loop.
- Security → `$security-review`; branch/PR/WIP → `$code-review`.
- Repeated process root ≥2 → `$repeated-failure-learning` → `$he-learn`; lifecycle unchanged.
- `$he` = Feature Loop lifecycle router + state owner.
- Stage owners = `$he-plan` → `$he-build` (Implement ⇄ Verify) → `$he-ship`; `$he-learn` = non-blocking overlay unless protected boundary at risk.
- Explicit lifecycle persistence = `$he` Continuity; `PASS` + route + no boundary → checkpoint + continue same turn.
- Missing required stage = stop + report; replacement improvisation forbidden.
- Subagents = current user prompt explicitly requests; omitted count → ≤4 direct + depth=1; background/unsolicited/nested otherwise forbidden.
- Unsolicited model evals/Imagegen/daemons/cron/watchdogs/blind retries forbidden.
- Review = actual diff + affected behavior + risk-targeted proof.
- Standard review = focused owner review; critical affected slice = specialist + independent review as risk requires.
- Review finding = implementation defect → fix + affected proof; outcome/risk discovery → replan; finding never authorizes mutation.

## Tools
- External-contract-dependent decision/code/review/claim → `$research` primary-source PASS.
- Current vendor/library fact → `$research`; memory/local code/types/tests/secondary source ≠ external proof.
- Sentry remediation → `$sentry` CLI only.
- Codebase Memory = topology/callers/dependencies/routes/architecture/impact; CLI `codebase-memory-mcp cli <tool> '<bounded-json>'`.
- Memory start = `list_projects` → project → stale/missing `index_repository` → `get_graph_schema`.
- CLI failure = report once → bounded `rg`; noisy supported CLI → `rtk`; exact/raw/unsupported → native.
- Context Mode = large/unknown output; index reused docs; batch ≥3 independent reads; retain decisions + receipts, discard exploration.
- Output ≤8K; raw only for bounded exact evidence; browser = reuse + batches + targeted proof.
- GitHub = authenticated `gh` CLI; capability ≠ approval.
- Exact text/path = `rg`; file mutation = `apply_patch`.
- Project command/gate/build/test/dev = `$deterministic-checks` bounded runner + explicit whole-run timeout.

## Proof
- Read before claim/edit; validation breadth ≥ blast radius.
- Evidence = `Verified | Inferred | Unknown`.
- Final = `PASS | CONCERNS | FAIL` + why + risk + proof + gaps.
- Commit/push/merge/publish = separate exact approval boundary.

## Markdown
- Agent-facing `.md` = terse directives; paragraph prose forbidden.
- Syntax = mapping `=` + composition `+` + routing `→` + loop `⇄`.
- `README.md` = human writing.
- Canonical docs = accepted current state only; rejected/migration history omitted.
