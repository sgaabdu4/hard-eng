# Build

Implement and Verify are one loop, not separate stages. Obey the state cursor.
For a Plan run, load only `he plan-excerpt --run <id> --slice S<n>`; never load
the full plan during routine Build. Re-read project rules and use Codebase
Memory for owners/callers/impact and Context Mode for large evidence. Request a
bounded support receipt with `support.recorded`; never store raw output.

Codebase Memory is mandatory and cannot be `not-applicable`. Ask for one actual
bounded `get_architecture`, `search_graph`, `trace_path`, or `detect_changes`
operation with only the required selectors. The state server resolves the
exact repository project, indexes it if absent, executes the operation, and
replaces any caller evidence digest. `list_projects` or `index_repository`
alone is health/setup evidence and cannot pass Plan or Build. A fallback is
legal only after the server observes the command fail; provide one bounded
diagnosis before using `rg`.

Use Context Mode whenever output, logs, docs, or data would otherwise be large.
Index the exact evidence first, then request a `search` receipt with one bounded
source label/query/limit. The server repeats that exact-project search and
rejects missing or empty indexed evidence. Otherwise record exactly `operation:
not-applicable`, `status: not-applicable`, and `reason_code: no-large-output`.
The server strips parameters and raw output from state. Setup doctor health is
separate and cannot satisfy a lifecycle receipt.

The state tool rejects Plan readiness and the first Build red proof until both
support-tool dispositions have been recorded. A return to Plan clears them so
changed scope must be rediscovered.

Before entering Ship, request Codebase Memory `detect_changes` against the final
Build tree as `pass` or one server-observed diagnosed `fallback`.

## Slice contract

At `red`, create the smallest public behavior seam and prove the intended
failure. Submit `build.red-proven` with a proof containing:

- stable `id`, `kind: red`, `result: fail-expected`, and bounded `name`;
- `source: {kind: command|artifact, reference: <short label>}`; and
- SHA-256 `evidence_digest`. The server binds the real candidate fingerprint.

At `implement`, edit the canonical owner only. Submit `build.implemented`; the
server records the real tree. At `verify`, run focused format/static/unit or
integration/UI proof:

- pass: `build.verify-passed` with `kind: verify`, `result: pass` proof;
- fail: `build.verify-failed` with `kind: verify`, `result: fail` proof and a
  SHA-256 `hypothesis_digest`, then repair the same slice.

Two failed repair attempts may share one unchanged hypothesis. A third is
blocked; report the missing decision or capability. Never blindly rerun.

At `review`, inspect the actual diff once for accepted behavior, canonical
ownership, maintainability, security, accessibility, and ripple effects.
Submit `build.review-passed` with `kind: review`, `result: pass`. Proof must be
fresh on the same tree as verification. Use `build.next-slice` after a proven
slice or `build.all-slices-proven` after the final slice.

## Drift and human review

If the tree changes outside the expected boundary, submit
`build.candidate-drift` with a short reason; fresh verification is required.
If acceptance, scope, product behavior, or design changes, submit
`build.plan-triggered` with the revised intent digest and reason. Do not keep
building against an invalid plan.

For a required UI milestone, submit `build.visual-milestone` with a run-owned
evidence pack: common role/data/route/viewport/environment, approved-direction
digest, comparable baseline or explicit greenfield reason, coded screenshots,
known gaps, and video when the flow requires it. Wait at
`await-user-review`. Record `approved`, `implementation-defect`, or
`plan-change`; the last two return to Build or Plan respectively.

Never invoke a retired review pipeline, another model, a review fleet, or
Imagegen during ordinary Build. Final user-visible screenshots/video come from
the real app, not the Plan mock or generated pixels.
