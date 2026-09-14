# Prevent concurrent uv cache mutation

Status: Complete

## Outcome + scope

Prevent parallel gate subprocesses from concurrently mutating uv's shared interpreter and tool cache. Preserve concurrent execution for independent native commands, check exit codes and latest package selection. No retry wrapper or disabled checks.

## Repository context

.hooks/tool_setup.py owns managed native commands. .hooks/hard-eng.py runs them concurrently. The existing runner test file is near its enforced700-line limit, so tests/test_tool_execution.py covers real child-process cache exclusion; the existing native overlap test stays unchanged. No new dependency.

## Decisions + authorization

Blockers: None

Source repair, testing and merge are authorized. One builder owns the isolated checkout. The unrelated publication-privacy work remains untouched. This is the bounded baseline repair before consumer delivery resumes.

## Acceptance + steps

- [x] Parallel uv and uvx gate subprocesses cannot overlap within a runner; other native checks retain two-worker concurrency.
- [x] Failures remain failures and latest-tool arguments remain unchanged.
- [x] Focused concurrency tests and repaired baseline gate pass; final Complete gate follows before shipping.

## Baseline + execution

Result: Passed
Evidence: Main CI34826519864 at73c5ca6767fa13869690849b0ac4e8cc36a68aba failed complexity with an interpreter-cache rename ENOENT during concurrent uv invocations. Security separately reported Semgrep analysis timeouts. Earlier PR CI34826265186 and initialized local Complete gate passed. The temporary pre-push checkout also lacks source submodules, a separately recorded limitation.

Current repaired baseline: Draft gate passed all17 checks,477 regression tests and four performance tests, including Semgrep with no timeouts. Original failed evidence above is retained.

## Risks + recovery

Serialize only uv-backed subprocess execution within a runner; native commands remain parallel. This may reduce overlap between Python tools but avoids a shared cache race without fresh per-check caches or duplicate downloads. Independent external processes are outside this runner's scheduling boundary. Semgrep timeout detection remains enabled.

## ux_reference

N/A — gate scheduling has no application UI.

## Verification

Result: Passed
Evidence: Four real child-process regressions failed before the lock with concurrent cache-write conflicts. All92 focused tests passed after the lock, covering both uv entrypoints, success and failure propagation, and existing native overlap. Latest-tool command arguments are unchanged. Full repaired-baseline gate passed; final Complete gate follows. The fixture proves scheduling exclusion, not reproduction of uv's internal implementation.

Delivery target: Merge
Final Complete gate passed all17 checks,477 regressions and four performance tests. Ready for ship — local implementation and verification complete; delivery not performed.

Delivery: Pending — PR CI, merge, exact main CI and native delivered verification.
