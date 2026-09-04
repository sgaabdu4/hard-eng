# Feature Brief: Build Loop Records

<!-- hard-eng-state:v1 -->
- state_version = 1
- plan_id = build-loop-records-5a7f9509
- lifecycle_status = shipped
- approval_status = approved
- approval_fingerprint = sha256:3b45e295fad68e40841cba700b957a66a8329f0ebddb9cdcf0f12311ff086c64
- approval_provenance = ready-to-build
- green_artifact = sha256:3f5ff3d649406db9ebc3e867725c566a65d1b248690cbf96e306257eaae8b001
- active_slice = none
- completed_slices = S-1,S-2,S-3,S-4,S-5,S-6,S-7,S-8,S-9,S-10
- next_action = Shipped: main at da2dbf2 (feature 8dba688 + CI fix), https://github.com/sgaabdu4/hard-eng/actions/runs/33928179624 green; first nightly mutation run proves the pull-request setting at 02:17 UTC.
- replan_reason = none
- walkthrough = no
<!-- /hard-eng-state -->

## Outcome
- The build stage is machine-checked end to end: every slice must leave records for its edge cases mapped to success and failure tests, its green test run, a fresh-eyes review loop with a findings ledger, and an end-to-end verification run by a separate agent with fake outside services and before/after evidence; the slice gate refuses a slice without them; new push-time checks catch copy-paste clones (baseline, new clones only) and complex under-tested TypeScript functions; mutation testing scores only functions with no current ledger row, nightly in GitHub Actions on public repositories with a pull request for survivors, and on the developer machine before push on private ones, recorded in a committed ledger that the push gate and CI only read; ticket mode has a machine-checked board; build closes with one question (walkthrough video?) and prints a ship handoff block with worktree, branch, plan, and prompt.

## Non-goals
- Strict test-first; edge cases are listed after the first working path, then tested.
- Judging review or verification quality; checks prove records exist, are specific, and are bound to the tree.
- A CRAP score for Dart or Python; TypeScript only via Fallow, exact when the test runner writes Istanbul coverage, estimated otherwise.
- Mutation testing for Dart/Flutter; no accepted runner.
- Nightly mutation runs on private repositories or on paid runners; there the run stays local before push.
- Replacing the explicit cross-provider adversarial review skill.

## Material decisions
- Slice records live in `features/<slug>/receipts/build-steps.json` via `plan_state.py record-build --slice S-n --step <step>`; steps = `edges` (list of edge cases, each with a success test and a failure test id), `green` (exact command + exit 0 + tree hash), `review` (rounds 1..3, each with reviewer findings; every finding closed as fixed|rejected-with-reason|replan; round 3 still open → stop and ask the user), `verify` (mode ui|logic, fakes used for every outside call, before and after evidence paths with hashes, edge cases exercised); records bind to the tree hash and go stale on change.
- Slice gate `run --slice` refuses when any of the four records is missing or stale for that slice; `--full` refuses when any completed slice lacks them; existing e2e/security/review free text stays but `review` must name the review record.
- Reviewer = fresh subagent with only the diff, the brief, the acceptance examples, and the slice edge list; never the author's chat; max three rounds; zero open findings ends the loop.
- Verifier = fresh subagent that drives the whole feature after the last slice: UI feature → real browser through the `e2e` skill with screenshots before and after per view; logic feature → recorded inputs and outputs before and after as JSON; every outside HTTP call goes through a fake the verifier records; a real outside call during verification = FAIL.
- TypeScript = the existing `fallow` family moves to `fallow audit` (dead code + new clones + complexity + CRAP `--max-crap 30`, changed files against the merge base, `--coverage coverage/coverage-final.json` when present, per-analysis baselines for old debt); Dart + Python = new `clones` family = jscpd 5 with `--baseline` + `--fail-on-new-clones` and the json reporter; both push + ci phases; no crap4ts.
- Mutation = scope is always functions with no current ledger row; public repository = nightly GitHub Actions job (`schedule`, default branch, free standard runner) that scores those functions, commits the rows with every survivor marked `needs-verdict`, and opens a pull request through `gh` with the `GITHUB_TOKEN`; the job exits without scoring when the repository is private; private repository = local run before push over the functions changed against the merge base (`origin/main|develop`); runner per `mutation.md` (`stryker` with `--incremental` + `--mutate <file>` and a committed incremental file for JS/TS; `mutmut run "<module>.<function>*"` for Python; Dart = none); results land in a committed `mutation-ledger.json` keyed by function name + source hash with totals and one row per survivor (fixed|equivalent|invalid|deferred + reason), and a mutant no test reaches counts as a survivor; a function whose ledger hash matches its current source is never scored again; the `publish` push phase and CI carry a `mutation-ledger` family that refuses when a changed function has no current row on a private repository and passes on a public one (the nightly job records it); a `needs-verdict` row older than seven days fails the family; no mutation run inside push or pull-request CI; the per-feature `receipts/mutation.json` receipt and the `he-ship` mutation refusal are removed.
- Speed = slice gate runs independent families in parallel with one bounded timeout, changed-function scoping for mutation and changed-file scoping for clones/crap, baseline files so old debt never blocks, records reused when the tree hash is unchanged.
- Ticket mode = `ticket_state.py board` output printed by `inspect`; a worker may claim only a ticket whose dependencies are shipped; orchestrator session never edits product files (enforcement check on claimed ticket paths); up to four workers.
- Build closing = one question after the full gate: walkthrough video yes|no (recorded in the brief as `walkthrough = ...`); yes → `product-walkthrough-video` skill output listed in the verify record.
- Handoff at `green` = `inspect` prints `handoff=ship` with root, branch, plan, and a paste-ready ship prompt; a generated human-readable `features/<slug>/BUILD.md` summarises every slice's records for review.
- External claim check = every backticked tool name in the brief's Material decisions and in the code-study `external_contract` answer must match a research source row (HTTPS url + version) recorded after the plan's init time; memory files and repository notes never count; `validate`, `approve`, and the gate-manifest change check refuse with the first uncited tool; the tool list = manifest families + a fixed vendor list (fallow, jscpd, stryker, mutmut, react-doctor, dart-decimate, biome, ruff, pyright, gitleaks, tsc, playwright, jira, azure devops, gh).
- ux_reference = n/a: no user-facing screen, only scripts and gates
- ux_reference_sources = n/a: no UX reference

## Acceptance examples
- Given a slice with code changes but no `edges` record, when the slice gate runs, then it fails naming `edges` for that slice and writes no receipt.
- Given an `edges` record where one edge case lacks a failure test id, when `record-build` runs, then it refuses naming that edge case.
- Given a review record with an open finding after round 3, when the slice gate runs, then it fails and `inspect` prints the open finding as the next action for the user.
- Given a verify record whose fake log shows one real outside host, when `record-build verify` runs, then it refuses naming the host.
- Given a Dart repository with an old clone and a baseline, when a push adds a new clone, then the `clones` family fails naming the new pair; unchanged old clones pass.
- Given a TypeScript function whose CRAP score reaches 30, when the `fallow` family runs on a change touching it, then the push fails naming the function.
- Given a private repository branch that changed one function with no ledger row, when the push gate runs, then it refuses naming that function; after a local mutation run records the row with every survivor dispositioned it passes.
- Given a public repository, when the nightly job finds functions with no current ledger row, then it scores only those, commits their rows with survivors marked `needs-verdict`, and opens a pull request; on a private repository the same job exits without scoring.
- Given a function whose ledger row hash matches its current source, when the local mutation run starts, then that function is skipped and its row is kept.
- Given a plan at `green`, when `inspect` runs, then it prints `handoff=ship` with root, branch, plan, and prompt, and `BUILD.md` exists listing every slice record.
- Given a brief whose decisions name `fallow` while the research record has no fallow source, when `validate` runs, then it fails naming fallow; after `record-research` with the docs url and version it passes.
- Given a manifest change adding a `clones` family, when the gate-manifest check runs without a jscpd research row, then it fails naming jscpd.
- Given four tickets where T-3 depends on T-1 still building, when a worker claims `--next`, then T-3 is not offered.

## Affected canonical areas
- `skills/he/scripts/plan_state.py` + new `build_steps.py` + `plan_handoff.py` + `plan_sections.py` (walkthrough row).
- `skills/deterministic-checks/scripts/slice_gate.py` + `project_gate.py` + references (`slice-gate.md`, `mutation.md`, `fallow.md`, new `clones.md`).
- `skills/he-build/SKILL.md` + `references/workflow.md`; `skills/he-ship/SKILL.md` (mutation entry removed); new `skills/deterministic-checks/scripts/mutation_ledger.py` + `mutation-ledger.json` + `.github/workflows/mutation-nightly.yml` (template in `mutation.md`); `skills/he/scripts/ticket_state.py`; `hard-eng.gates.json`; `scripts/git-hooks/publish-gate.sh`; regressions beside each script; `PRODUCT.md`.

## Risk and rollback
- risk_level = standard
- critical_overlay = none: no payment, auth, privacy, or destructive data path
- rollback = revert the commits; receipts are additive and gates read the manifest, so removing the new families restores the old push.
- deferred = the nightly pull request needs the repository setting that lets GitHub Actions create pull requests; proven at the first nightly run on `sgaabdu4/hard-eng`; JS/TS ledger rows from Stryker's incremental report wait for a `research` PASS on that report's file format, so a repository with no `[tool.mutmut]` prints `runners=none` and the family passes until then
- blocked_on = none: no user action pending
- tickets = none: yes pls as part of this and then can we implement
- tracker = not-probed

## Vertical slices
- S-1 = build-step records (`edges`, `green`, `review`, `verify`) recorded through `plan_state.py record-build`, bound to the tree, and required by the slice gate; depends_on = none: first record owner
- S-2 = reviewer loop: fresh subagent packet, findings ledger, three-round cap, open finding surfaces in `inspect`; depends_on = S-1
- S-3 = verifier stage: fresh subagent end-to-end run with fakes, before/after evidence for ui and logic modes, real outside call refused; depends_on = S-1
- S-4 = `fallow` family becomes `fallow audit` with CRAP and baselines, new `clones` family (jscpd) for Dart and Python in `project_gate.py`, wired here and documented, with parallel family runs in the slice gate; depends_on = none: gate families stand alone
- S-5 = mutation runner setup: mutmut in-process test seam, `mutation.md` run sequence, survivor verdict payload; the per-feature pre-ship receipt and `he-ship` refusal it first added are replaced by S-10; depends_on = S-4
- S-6 = ticket board in `inspect`, dependency-aware claim, orchestrator write guard; depends_on = S-1
- S-7 = build closing question, `BUILD.md` summary, and `handoff=ship` block at green; depends_on = S-2, S-3, S-5
- S-8 = he-build, he-ship, and deterministic-checks docs name every record and family; depends_on = S-7
- S-9 = external claim check: tool names in the brief and code-study must cite a fresh research source; validate, approve, and manifest changes refuse otherwise; depends_on = none: planning-time check stands alone
- S-10 = mutation ledger: a run over functions with no current ledger row writes `mutation-ledger.json` rows with survivor verdicts, the nightly workflow does that on public repositories and opens a pull request, the local run does it before push on private ones, the push gate and CI `mutation-ledger` family refuse a private-repository changed function without a current row and any stale `needs-verdict` row, and the pre-ship receipt plus `he-ship` refusal are removed; depends_on = S-5
- proof = regressions for build_steps, slice_gate, project_gate, ticket_state, plan_steps (claim check), plus full push gate and CI.
