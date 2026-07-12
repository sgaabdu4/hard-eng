# Ship

Ship is the only local delivery gate. It is deterministic and model-free.
Enter only from `Ship:preflight`; an unbound task must confirm intent and
return through Build proof first.

Before running Ship, record Codebase Memory as `pass` or one diagnosed
`fallback` for the exact `detect_changes` operation; it is never
`not-applicable`. Record Context Mode as `pass`, one
diagnosed `fallback`, or the exact `not-applicable` disposition documented in
[build.md](build.md). Then run:

```text
he ship --repo <checkout> --run <run-id> [--allow-untracked <relative-file>] --json
```

List every candidate untracked file explicitly. Never include `.env*`, keys,
credentials, secrets, private media, or unknown paths.

The command runs the ordered preflight, then the one `he check --all` registry.
Each registry check declares ID, owner, argv, trigger/risk, timeout, network
policy, mutability, candidate impact, evidence parser, and rerun rule. Commands
come from project rules/CI/package owners; Hard Eng does not invent a second
project config. Node, Flutter, Dart, Go, declared Python, and Rust owners are
inventoried; a diff-only registry fails. Timed-out process groups are killed so
descendants cannot continue mutating the candidate. Output is reduced to status
and digests. Hard Eng adds no model, daemon, legacy tool, network installer,
semantic auto-fix, or blind retry. A changed tree or failure returns to Build.

The registry is not an OS filesystem/network sandbox. It rejects known
model/daemon/legacy/installer commands, passes a minimal non-credential
environment, and detects candidate mutation by fingerprint. Repository-owned
check code remains inside the repository’s trust boundary and must declare any
external side effects in project rules.

On PASS, submit `ship.candidate-green` with the short-lived signed
`check_receipt` and evidence:

- non-user-visible: `{applicability: not-applicable, reason: <specific>}`;
- user-visible: final real-app evidence with the same scenario fields as the
  baseline, screenshots, required E2E video or explicit unavailable reason,
  approved-direction digest, and known gaps.

The server re-fingerprints the tree, rejects stale/forged/replayed receipts,
and stores only bounded preflight/check/candidate/evidence digests. A
user-visible candidate waits at `await-candidate-approval`. Present the compact
before/after evidence pack, checks, known gaps, and exact fingerprint. Submit
`ship.candidate-approved` only after explicit user approval of that fingerprint
and evidence digest.

Publication remains blocked until approval. First submit
`external-action.prepared` with the candidate fingerprint, idempotency key,
bounded reconciliation command, and intended `mode`/origin ref (plus PR number
for PR mode). The server overwrites caller preparation claims. It binds the
exact origin URL; direct-main additionally requires candidate HEAD and live
`origin/main` equality and captures classic branch protection plus effective
GitHub rules before any action.

Perform the approved action once. Submit `ship.published-current` with the same
key, bounded observed result, exact commit/parent/tree, and caller placeholders
for external facts. The server verifies the local commit, first parent, and
candidate tree; then uses live `git ls-remote` for the target ref. For GitHub it
reads exact-commit check runs. PR mode also reads the exact open, non-draft PR
head and every paginated review thread, failing if any thread is unresolved.
Direct-main compares the post-push protection/effective-rules digest with the
captured pre-push digest. Unsupported providers fail closed; local filesystem
remotes are accepted only for non-main branch fixtures.

The server replaces CI, PR, protection, remote, and rollback assertions, stores
only bounded evidence, and stops at `await-publication-approval`. Present the
exact commit and observation digest. Submit `ship.publication-approved` only
after explicit user approval; the server repeats every live observation and
cancels on concurrent movement before marking Complete.
