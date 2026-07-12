# Recovery

Fail closed on corruption, stale revision, plan/candidate drift, conflicting
lease, replay mismatch, or an unreconciled external action. Use `he doctor` for
read-only facts. Never infer a run from cwd, recency, branch, transcript, or
"only active run". Fresh tasks resume only the user-selected run; takeover
requires explicit approval at the current revision.

For ordinary candidate drift, do not fake the old fingerprint or repeat stale
proof. Submit `build.candidate-drift` with a bounded reason; the server binds
the real tree and returns to focused verification. Accepted plan drift returns
to Plan and requires a section-diff review plus explicit re-approval.

An interrupted external action must retain its precondition fingerprint,
idempotency key, observed result, and reconciliation command. Publication also
retains its server-observed mode/ref/remote/protection preparation receipt.
Inspect external state once, then either record observed success or obtain
approval for the exact safe recovery. Never delete a lock, state file,
worktree, ref, or temporary artifact merely because it appears stale.
