# Build

Build is one Implement ⇄ Verify loop at vertical-slice granularity. There is no
separate Verify stage. Obey the exact state cursor and finish the current proof
boundary before moving forward. For a Plan run, load only
`he plan-excerpt --run <id> --slice S<n>` during routine work.

## Support evidence

Codebase Memory is mandatory. The runtime observer must execute one bounded
`codebase-memory-mcp cli get_architecture|search_graph|trace_path|detect_changes
'<json>'` operation for the exact repository; it never opens or uses the
Codebase Memory MCP transport. `list_projects` and `index_repository` are setup
evidence, not structural proof. A fallback is legal only after one observed CLI
failure and a bounded diagnosis, then use the smallest `rg` query needed.

Use Context Mode when logs, output, documentation, diffs, APIs, or data would
otherwise be large. Record one bounded indexed search receipt, or exactly
`operation: not-applicable`, `status: not-applicable`, and
`reason_code: no-large-output`. Store only bounded receipts and digests; never
store raw output. Returning to Plan clears support receipts because the scope
must be rediscovered.

Before Ship, record a fresh CLI `detect_changes` receipt for the final Build
tree as `pass` or one observed, diagnosed `fallback`.

## Canonical owner and proof

Before the red proof or any owner change:

- identify the canonical behavior, domain, data, API, UI primitive, interaction,
  token/theme, fixture, and test-helper owners touched by the slice;
- search peers, callers, duplicates, clone groups, and similar UI states with
  the stack-native detector when available, otherwise bounded static evidence;
- record each relevant choice as reuse, extend, create feature-local owner,
  create shared owner, or not applicable with evidence; and
- prefer reuse or extension. Create the smallest project-local owner only when
  no suitable owner exists. A parallel local implementation cannot advance.

Use `test-quality` for behavior proof. Name the public seam and scenarios, then
add or identify the smallest failing behavior test before implementation. Mock
only external boundaries such as network, database, filesystem, clock, random,
process, or third-party services. Assert public behavior, not call choreography
or implementation structure. If red-first is genuinely impossible, prove the
test through a mutation or controlled make-it-fail result before editing the
owner.

## Implement ⇄ Verify slice loop

At `red`, submit `build.red-proven` with a stable ID, `kind: red`,
`result: fail-expected`, bounded name, command or artifact source, and SHA-256
evidence digest. The server binds the real candidate fingerprint.

At `implement`, change the canonical owner and every connected path in its
owned blast radius. Submit `build.implemented`; the server records the real
tree. Include the bounded root-owner receipt: owner digest, `root-fix` or
`full-migration`, no pass-through wrapper, no legacy/parallel owner, and one
digest covering direct callers, cross-package effects, schema/index,
cache/storage, tests/fixtures, routes/endpoints, docs/config/agent assets, live
wiring, and rollback. Do not add a wrapper, mode, duplicate path, or partial
compatibility surface.

At `verify`, run the smallest focused format, static, unit, integration, and UI
proof that can fail for the intended behavior. Then run every applicable
project-owned guardrail invalidated by the change:

- pass with `build.verify-passed`, `kind: verify`, and `result: pass`;
- fail with `build.verify-failed`, `kind: verify`, `result: fail`, and a SHA-256
  `hypothesis_digest`, then return directly to `implement` for the same slice.

Run security, performance, accessibility, privacy, migration/data-loss, or
other risk proof when requested or touched. Perform maintainability and actual
diff review after focused checks; run real UI E2E last when user-visible
behavior changed. A missing guard, unresolved SSOT choice, or failed artifact
returns to implementation inside Build. Rerun only invalidated proof.

Two repair attempts may share one unchanged hypothesis. Before a third, stop,
show the unresolved uncertainty or missing capability, ask the targeted user
question when it is a decision, checkpoint `clarification.required`, and wait
at `await-user-clarification`. Never blindly rerun or resume without the
explicit answer event.

At `review`, inspect actual hunks for accepted behavior, canonical ownership,
maintainability, security, accessibility, and connected ripple effects. Submit
fresh `build.review-passed` proof on the same tree as verification. Use
`build.next-slice` after a proven slice or `build.all-slices-proven` after the
final slice.

## Drift, findings, and human review

Unexpected tree movement uses `build.candidate-drift` and requires fresh
verification. A changed outcome, scope, acceptance rule, product behavior, or
design uses `build.plan-triggered`, shows the exact delta, and returns to Plan
for user approval.

For each required UI milestone, submit `build.visual-milestone` with the same
role, data, route, viewport, and environment as its baseline; the approved
direction digest; real coded screenshots; known gaps; and video when sequence
matters. Wait at `await-user-review`. An implementation defect stays in Build;
a plan change returns to Plan.

Admit a Learn finding only through [learn.md](learn.md). Ordinary Build never
launches another model, eval, review fleet, Imagegen call, subagent, daemon, or
retry loop. Final screenshots and video come from the real app.
