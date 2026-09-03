# Feature Brief: Build Loop Records

<!-- hard-eng-state:v1 -->
- state_version = 1
- plan_id = build-loop-records-5a7f9509
- lifecycle_status = building
- approval_status = approved
- approval_fingerprint = sha256:6db10bc363b5dd5d06e008f53eded81666f9ec0a9d8e5540466738940c59150b
- approval_provenance = ready-to-build
- green_artifact = none
- active_slice = none
- completed_slices = S-1,S-2,S-3,S-4,S-5,S-6,S-7,S-8,S-9
- next_action = Re-green on the tree after mutation-seam shipped (50a33bd): full verify record, mutation receipt, full gate, green, ship
- replan_reason = none
- walkthrough = no
<!-- /hard-eng-state -->

## Outcome
- The build stage is machine-checked end to end: every slice must leave records for its edge cases mapped to success and failure tests, its green test run, a fresh-eyes review loop with a findings ledger, and an end-to-end verification run by a separate agent with fake outside services and before/after evidence; the slice gate refuses a slice without them; new push-time checks catch copy-paste clones (baseline, new clones only) and complex under-tested TypeScript functions; mutation testing runs on changed files before ship for every feature; ticket mode has a machine-checked board; build closes with one question (walkthrough video?) and prints a ship handoff block with worktree, branch, plan, and prompt.

## Non-goals
- Strict test-first; edge cases are listed after the first working path, then tested.
- Judging review or verification quality; checks prove records exist, are specific, and are bound to the tree.
- A CRAP score for Dart or Python; TypeScript only via Fallow, exact when the test runner writes Istanbul coverage, estimated otherwise.
- Mutation testing for Dart/Flutter; no accepted runner.
- Replacing the explicit cross-provider adversarial review skill.

## Material decisions
- Slice records live in `features/<slug>/receipts/build-steps.json` via `plan_state.py record-build --slice S-n --step <step>`; steps = `edges` (list of edge cases, each with a success test and a failure test id), `green` (exact command + exit 0 + tree hash), `review` (rounds 1..3, each with reviewer findings; every finding closed as fixed|rejected-with-reason|replan; round 3 still open → stop and ask the user), `verify` (mode ui|logic, fakes used for every outside call, before and after evidence paths with hashes, edge cases exercised); records bind to the tree hash and go stale on change.
- Slice gate `run --slice` refuses when any of the four records is missing or stale for that slice; `--full` refuses when any completed slice lacks them; existing e2e/security/review free text stays but `review` must name the review record.
- Reviewer = fresh subagent with only the diff, the brief, the acceptance examples, and the slice edge list; never the author's chat; max three rounds; zero open findings ends the loop.
- Verifier = fresh subagent that drives the whole feature after the last slice: UI feature → real browser through the `e2e` skill with screenshots before and after per view; logic feature → recorded inputs and outputs before and after as JSON; every outside HTTP call goes through a fake the verifier records; a real outside call during verification = FAIL.
- TypeScript = the existing `fallow` family moves to `fallow audit` (dead code + new clones + complexity + CRAP `--max-crap 30`, changed files against the merge base, `--coverage coverage/coverage-final.json` when present, per-analysis baselines for old debt); Dart + Python = new `clones` family = jscpd 5 with `--baseline` + `--fail-on-new-clones` and the json reporter; both push + ci phases; no crap4ts.
- Mutation = pre-ship step for every feature, scope = files changed since the approval base, runner per the existing mutation reference (Stryker / mutmut), survivors need a written disposition in the receipt; `he-ship` entry refuses without it.
- Speed = slice gate runs independent families in parallel with one bounded timeout, changed-file scoping for clones/crap/mutation, baseline files so old debt never blocks, records reused when the tree hash is unchanged.
- Ticket mode = `ticket_state.py board` output printed by `inspect`; a worker may claim only a ticket whose dependencies are shipped; orchestrator session never edits product files (enforcement check on claimed ticket paths); up to four workers.
- Build closing = one question after the full gate: walkthrough video yes|no (recorded in the brief as `walkthrough = ...`); yes → `product-walkthrough-video` skill output listed in the verify record.
- Handoff at `green` = `inspect` prints `handoff=ship` with root, branch, plan, and a paste-ready ship prompt; a generated human-readable `features/<slug>/BUILD.md` summarises every slice's records for review.
- External claim check = every backticked tool name in the brief's Material decisions and in the code-study `external_contract` answer must match a research source row (HTTPS url + version) recorded after the plan's init time; memory files and repository notes never count; `validate`, `approve`, and the gate-manifest change check refuse with the first uncited tool; the tool list = manifest families + a fixed vendor list (fallow, jscpd, stryker, mutmut, react-doctor, dart-decimate, biome, ruff, pyright, gitleaks, tsc, playwright, jira, azure devops, gh).
- ux_reference = n/a
- ux_reference_sources = n/a

## Acceptance examples
- Given a slice with code changes but no `edges` record, when the slice gate runs, then it fails naming `edges` for that slice and writes no receipt.
- Given an `edges` record where one edge case lacks a failure test id, when `record-build` runs, then it refuses naming that edge case.
- Given a review record with an open finding after round 3, when the slice gate runs, then it fails and `inspect` prints the open finding as the next action for the user.
- Given a verify record whose fake log shows one real outside host, when `record-build verify` runs, then it refuses naming the host.
- Given a Dart repository with an old clone and a baseline, when a push adds a new clone, then the `clones` family fails naming the new pair; unchanged old clones pass.
- Given a TypeScript function whose CRAP score reaches 30, when the `fallow` family runs on a change touching it, then the push fails naming the function.
- Given a completed feature with no mutation receipt, when `he-ship` starts, then it refuses naming mutation; after a run with every survivor dispositioned it passes.
- Given a plan at `green`, when `inspect` runs, then it prints `handoff=ship` with root, branch, plan, and prompt, and `BUILD.md` exists listing every slice record.
- Given a brief whose decisions name `fallow` while the research record has no fallow source, when `validate` runs, then it fails naming fallow; after `record-research` with the docs url and version it passes.
- Given a manifest change adding a `clones` family, when the gate-manifest check runs without a jscpd research row, then it fails naming jscpd.
- Given four tickets where T-3 depends on T-1 still building, when a worker claims `--next`, then T-3 is not offered.

## Affected canonical areas
- `skills/he/scripts/plan_state.py` + new `build_steps.py` + `plan_handoff.py` + `plan_sections.py` (walkthrough row).
- `skills/deterministic-checks/scripts/slice_gate.py` + `project_gate.py` + references (`slice-gate.md`, `mutation.md`, `fallow.md`, new `clones.md`).
- `skills/he-build/SKILL.md` + `references/workflow.md`; `skills/he-ship/SKILL.md` (mutation entry); `skills/he/scripts/ticket_state.py`; `hard-eng.gates.json`; `scripts/git-hooks/publish-gate.sh`; regressions beside each script; `PRODUCT.md`.

## Risk and rollback
- risk_level = standard
- critical_overlay = none
- rollback = revert the commits; receipts are additive and gates read the manifest, so removing the new families restores the old push.
- deferred = none
- blocked_on = none
- tickets = none
- tracker = not-probed

## Vertical slices
- S-1 = build-step records (`edges`, `green`, `review`, `verify`) recorded through `plan_state.py record-build`, bound to the tree, and required by the slice gate; depends_on = none
- S-2 = reviewer loop: fresh subagent packet, findings ledger, three-round cap, open finding surfaces in `inspect`; depends_on = S-1
- S-3 = verifier stage: fresh subagent end-to-end run with fakes, before/after evidence for ui and logic modes, real outside call refused; depends_on = S-1
- S-4 = `fallow` family becomes `fallow audit` with CRAP and baselines, new `clones` family (jscpd) for Dart and Python in `project_gate.py`, wired here and documented, with parallel family runs in the slice gate; depends_on = none
- S-5 = mutation before ship for every feature, changed-file scope, survivor dispositions, `he-ship` entry refusal; depends_on = S-4
- S-6 = ticket board in `inspect`, dependency-aware claim, orchestrator write guard; depends_on = S-1
- S-7 = build closing question, `BUILD.md` summary, and `handoff=ship` block at green; depends_on = S-2, S-3, S-5
- S-8 = he-build, he-ship, and deterministic-checks docs name every record and family; depends_on = S-7
- S-9 = external claim check: tool names in the brief and code-study must cite a fresh research source; validate, approve, and manifest changes refuse otherwise; depends_on = none
- proof = regressions for build_steps, slice_gate, project_gate, ticket_state, plan_steps (claim check), plus full push gate and CI.
