# Agent Rules

## Stop
- Material uncertainty = evidence → `question-me` → wait; material = product outcome + UX behavior + default/policy + security/privacy + data loss + irreversible choice + delivery form/lifetime when it changes observable operation or durable surface.
- Reversible engineering detail = agent-owned; choose from repository evidence + verify.
- Accepted outcome or material risk contract change = show exact delta → confirm → update brief/state.
- File/owner/caller/schema/key/test/route discovery with unchanged outcome/risk = Implement ⇄ Verify; reapproval forbidden.
- Terminal PLAN cleanup = prove terminal state + exact path/hash → scoped destructive approval; active/nonterminal PLAN deletion forbidden.
- Terminal lifecycle status noise = exact terminal slug PLAN + receipts in Git common `info/exclude`; linked-worktree sharing intentional; broad feature ignores + per-worktree config forbidden.
- Destructive action/external write/commit/push/merge/publish = state target + effect → user's plain yes/approved suffices.
- Uncommitted-work discard = `git checkout <path>`/`restore`/`reset --hard`/`clean`/`stash drop|clear|pop` → state exact paths + what is lost → plain yes; `git stash push` instead whenever keeping the work suffices.
- Publish approval closure = stated action + stated live effect (deploy target or explicit none) + its hooks + automatic workflows + downstream external writes; undisclosed automation = unapproved.
- Approval answers the immediately preceding proposed action only; unchanged steps/retries stay covered until an external/native/paid attempt fails; failure ends retry coverage; changed target/effect → ask again.
- Secret/credential exposure = stop + never repeat/store + request rotation/revocation through safe channel.
- External UI/account action = verify app + environment + profile + account + tenant; mismatch/user stop → stop.

## Engineering
- Non-trivial mutation = `deterministic-checks` worktree `write` PASS; commit/push = `publish` PASS.
- Missing project gate manifest/family → `deterministic-checks` `gate-migration` before first product mutation; migration scope = gate wiring only.
- Commit changing product truth = users/purpose/boundaries/capabilities/delivery → update root `PRODUCT.md` in the same commit; unchanged product truth = no read.
- Gate scope = affected-full: universal gates + full gate row per impacted owner; global/shared/toolchain/CI change or uncertainty → full repository.
- Gate concurrency = independent affected owners parallel; dependencies/shared state sequential; external mutation serial.
- Execution graph = dependency DAG → parallel read-only discovery + independent proof + one shared-state mutation owner; batch tool calls/results + collapse waits; never serialize independent work.
- Efficiency target = smallest correct maintainable outcome with minimum concepts + files + steps + tokens/context + wall time + paid compute; remove/reuse/batch/parallelize independent work before adding; correctness + protected boundaries fixed; product-performance claim requires measurement.
- Alignment latency = one dependency frontier per turn + every independent material decision batched; dependent options wait for upstream answer; one-by-one independent questioning forbidden.
- User-direction ledger = explicit outcome + constraints + examples + exclusions + corrections; later guidance supersedes only exact conflicts + every other item remains open until proven, `N/A`, blocked, or explicitly withdrawn.
- Before mutation/delegation/external action = reconcile the ledger against latest messages; summarization, compaction, or handoff may not narrow it.
- Pre-implementation check = accepted outcome + actual owner/flow/operations + callers/blast radius + simpler existing capability + required external contract; material unknown → `research` or `question-me`; analysis depth ≠ response length.
- Collection scope = enumerate candidates + prove the user-named inclusion predicate before delegation/mutation; guessed member = forbidden.
- Explicit terminal outcome = persistent completion contract across recoverable failures/retries/turns; persistence never authorizes a same-theory retry or bypasses a protected stop.
- Explicit `fix all|everything|done/no regressions` scope = closure ledger of user-reported + connected verified defects; `pre-existing` = provenance, never exclusion; terminal only at zero open items or exact authority blocker.
- Workflow topology change = inventory last-green required stages + ordering + cross-job outputs → diff every replacement lane → contract-test invariant presence/order before remote proof.
- Proof ladder = local/static + current primary contract → cheapest target-native nonpublishing diagnostic → one full/publisher actor; reuse exact-tree proof/artifact + every job/step proves one distinct required seam + duplicate equivalent setup/build/gate forbidden; independent cheap checks parallel + prerequisite failure cancels dependent paid work + retry waits for root cause and adjacent-assumption audit.
- Bug-fix implementation admission = preserved red-capable reproduction + observable violation still red + accepted behavior still needed + proven owner/mechanism + blast radius + discriminating regression seam; solution ladder = remove → reuse/repair existing owner → standard library/native platform → installed dependency → minimum new concept; stop at first complete rung; external/runtime/platform assumptions require `research` PASS before edit.
- External/native/paid failure = stop actor + recheck the original observable violation + report cause and approach fingerprint (mechanism + dependency/tool + mode/target); same approach/variant forbidden; any further external/native/paid attempt requires fresh user approval + retry-readiness PASS.
- Release actor = one per target + environment + revision; manual + CI overlap forbidden; alternate actor waits for terminal/cancelled receipt.
- Release recovery = failed external mutation/paused cutover preserves original release mode + target revision; same-revision correction retry explicitly forces that mode + terminal readback before closure; correction-only classifier non-entry ≠ completion.
- Existing linked worktree/branch = continue; clean primary/main = direct; requested worktree = create.
- Dirty primary + unrelated user work + no choice = ask once: current checkout OR new worktree; automatic worktree/branch forbidden.
- Worktree input = required ignored files via `.worktreeinclude`; rebuildable via setup; broad ignored-copy forbidden.
- Worktree build entry = Git hook OR Codex app → one tracked setup owner + Git-private receipt; `write` PASS requires current receipt + private included inputs.
- Hook/gate script git call = strip inherited `git rev-parse --local-env-vars` first; inherited `GIT_DIR`/`GIT_WORK_TREE` resolve the hook's checkout, not the requested one.
- KISS = fewest complete concepts; YAGNI = no speculative scope; dependency/control/workflow existence ≠ necessity; DRY = fact once; SSOT = canonical owner.
- User-facing language = concrete offer + experience + outcome; internal taxonomy/classification/rationale/meta-explanation forbidden in any user-facing surface or communication. Category confusion → rename + describe what the person gets/does; never explain `X is a Y` or `one of N types/ways`. Internal schemas/types/tests/technical docs may retain required taxonomy; do not surface it.
- Code comment = none by default; admit only when a necessary non-obvious constraint cannot be expressed by deletion + naming + types/API + structure + test + canonical docs; then one terse why/invariant comment; narration + restatement + history + TODO prose forbidden.
- Correctness = root cause + blast radius + connected owner/caller/schema/key/test/route/doc/config/live wire.
- Planning-first = Feature Loop evidence + lean brief + Ready-to-build approval precede build-readiness repair/full gates; planning-only PLAN mutation requires worktree `read` PASS; product mutation still requires `write` PASS.
- Outcome-first = after readiness/approval, complete the thinnest accepted persistence/API/UI path → targeted proof; unrelated tooling/debt, including `before commit/push`, waits until behavior works → full applicable gates.
- Build-entry exception = failed `write`/setup → smallest safety repair + focused proof + rerun `write`; other pre-behavior diversion forbidden unless continuation is unsafe, corrupting, or unverifiable.
- Preserve required security + trust + privacy + accessibility + schema + data-loss protections; new security control = concrete asset + plausible threat + impact/requirement → simplest sufficient maintainable control; speculative hardening = YAGNI.
- Credential/secret cutover = candidate probe → external write → actual-consumer preflight → fixed claim; unprobed write or pre-preflight "fixed" forbidden.
- File ≤700 lines; generated/schema or focused parser/scanner/dense contract test exception = reason + deterministic proof.
- Context reset = default at slice green checkpoint + allowed at alignment boundary; accepted brief/state + evidence receipt = resume owner; new approval forbidden.
- Goal/automatic continuation = explicit user request.
- Terminal handoff + unrelated request = recommend fresh task + context-cost reason; never inherit PLAN + approval + scope.
- Commentary = material state change + blocker + approval boundary + proof + bounded elapsed-wait status; batch routine narration + omit unchanged polling.
- Output tokens = shortest complete decision/answer + necessary evidence + next action; omit prompt restatement + internal process + praise + optional tangents + repeated summary; preserve explicit requested detail + material risk/blocker/proof.
- Answer = direct response to the question asked, in plain language, first; mechanism + evidence + jargon only after, only when they change the reader's decision; terse ≠ comprehensible.
- Domain term in user-facing text = admit only when no plain phrasing carries the same fact; then define on first use in one clause.

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
- Codebase Memory = topology/callers/dependencies/routes/architecture/impact; CLI `echo '<bounded-json>' | codebase-memory-mcp cli <tool>`; raw-JSON argument deprecated.
- Memory arguments = `project` is the repository root path; per-file impact = `search_code` + `pattern`; symbol/graph = `search_graph` + `query`.
- Memory start = repository root as `project` → stale/missing `index_repository` → `get_graph_schema`; `list_projects` = recovery only.
- CLI failure = report once → bounded `rg`; noisy supported CLI → `rtk`; exact/raw/unsupported → native.
- Context Mode = large/unknown output; index reused docs; batch ≥3 independent reads; retain decisions + receipts, discard exploration.
- Analysis-only file/log/diff read = Context Mode sandbox; direct raw read = imminent edit target or bounded exact evidence only.
- Output ≤8K; raw only for bounded exact evidence; browser = reuse + batches + targeted proof.
- Shared session/preferences/account CLI = sequential; parallel work requires independent state + files.
- Ephemeral probe = `mktemp` owner + cleanup before final; durable receipt = repository/runbook-approved owner.
- GitHub = authenticated `gh` CLI; capability ≠ approval.
- Exact text/path = `rg`; file mutation = `apply_patch`.
- Multi-repo shell probe = selected-repo cwd OR absolute repo-root paths; caller-cwd globs + relative Git-path output forbidden.
- Project command/gate/build/test/dev = `deterministic-checks` bounded runner + explicit whole-run timeout.

## Proof
- Read before claim/edit; validation breadth ≥ blast radius.
- Evidence = `Verified | Inferred | Unknown`.
- Final = `PASS | CONCERNS | FAIL` + why + risk + proof + gaps.
- `CONCERNS` = proven gap + impact + attempts + next executable action + owner/authority; missing next action = incomplete.
- Nonterminal `PASS` = lifecycle state + exact next action + single pending approval; missing = incomplete; continuation still = explicit user request.
- Speculation/capacity hypothesis → measure + research + optimize/preflight/redesign + verify; unknown bound ≠ blocker.
- Coverage claim = per-artifact verdict for every enumerated surface/screenshot/file/row; sampled or extrapolated coverage forbidden.
- Unopened/unreachable artifact = explicit `not checked`; empty/absent-subject artifact = `proves nothing`; neither counts toward PASS.
- Delivered visual/multi-surface proof = every artifact opened and read by the producing agent before delivery; producing an artifact ≠ inspecting it.
- Self-authored external contract + own test asserting it = one assumption restated, never conformance; `Verified` requires primary-source contract + that external program's own observed behavior.
- External-tool integration proof = receipt of tool + version + command + observed effect; installed version ≠ receipt version = unproven until re-run.
- Remote PASS = required CI jobs green for the delivered commit; workflow-level green alone = insufficient.
- `done|no regressions` claim = closure ledger empty + required CI/deploy terminal green; running/failed/skipped/unknown remote state = not done.
- Commit/push/merge/publish = separate approval boundary.

## Markdown
- Agent-facing `.md` = terse directives; paragraph prose forbidden.
- Syntax = mapping `=` + composition `+` + routing `→` + loop `⇄`.
- Skill reference = canonical backticked name without runtime invocation sigil; cross-runtime portability required.
- `README.md` = human writing.
- `CLAUDE.md` = `@AGENTS.md` import stub only; repository override stub = `CLAUDE.local.md` → `@AGENTS.override.md`; instruction edits → `AGENTS.md`.
- Canonical docs = accepted current state only; rejected/migration history omitted.
