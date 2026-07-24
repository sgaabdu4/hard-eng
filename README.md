# hard-eng

<p align="center">
  <img src="assets/readme/hard-eng-hero.png" alt="Hard Eng: plan with one Feature Brief, build in an implement-verify loop, ship, and learn from evidence" width="100%">
</p>

<p align="center">
  <strong>Fast, evidence-backed engineering for OpenAI Codex.</strong><br>
  Align once. Build in verified vertical slices. Put extra scrutiny only where the risk is.
</p>

> [!IMPORTANT]
> **Alpha:** Hard Eng is evolving quickly. Its contract is stable on the essentials: explicit intent, root-cause fixes, deterministic proof, and protected approval boundaries.

## Start here

Most work needs no command. Give Codex a clear outcome and it chooses the lightest safe route.

```text
$he plan <feature>  Create a lean Feature Brief and reach Ready-to-build
$he resume          Continue from the accepted brief or next slice
$he status          Read progress without changing state
$he build           Implement and verify the approved slices
$he ship            Deliver the exact green artifact
$he learn           Process an evidence-backed workflow improvement
```

## Route matrix

| Route | Use it when | What happens |
| --- | --- | --- |
| Direct | The outcome is bounded and clear | Inspect, edit the canonical owner, run focused gates, report |
| Feature Loop | A new or changed capability needs product alignment | One lean Feature Brief, one Ready-to-build approval, then verified vertical slices |
| Diagnose-first | A bug, flake, failure, or regression exists | Reproduce, find root cause and blast radius, then fix and prove |
| Critical overlay | A slice touches payment, auth, security, privacy, destructive data, irreversible behavior, or material uncertainty | Strengthen the contract, evidence, and independent review for that slice only |

Calling work a “feature,” touching many files, or finding an old context document does not automatically add process. Direct is the default. The Feature Loop exists when an observable capability needs alignment; the Critical overlay follows risk instead of making an entire project heavy.

## The Fast Feature Loop

### 1. Align once

Hard Eng reads the repository, researches current external facts when needed, and creates one lean, living Feature Brief:

- **Outcome**
- **Non-goals**
- **Material decisions**
- **Acceptance examples**
- **Affected canonical areas**
- **Risk and rollback**
- **First vertical slice**

Questions are batched where possible. Once the brief contains no unresolved material choice, Codex asks for one Ready-to-build approval. That approval covers the accepted feature outcome—not destructive actions, external writes, commits, pushes, merges, or publication.

There is no arbitrary limit on material questions. Independent choices are batched; dependent choices are asked in sequence until the accepted outcome and risk contract are genuinely aligned. Already-settled answers are not asked again.

The brief has six plain states: `planning`, `build-ready`, `building`, `green`, `shipped`, and `cancelled`.

### Migrating a legacy v4 plan

Legacy v4 plans have one explicit, one-time conversion path:

```bash
python3 <skill-dir>/scripts/plan_state.py migrate-v4 --repo <repo> \
  --plan features/<slug>/PLAN.md \
  --expect-token sha256:<full-document-byte-hash>
```

The token is the SHA-256 hash of the exact original document bytes. Conversion archives those original bytes with their file mode beside the PLAN, then atomically replaces the canonical PLAN with the lean format. An unapproved planning plan maps to `planning` with approval pending. An approved `build-ready` or `building` plan keeps its lifecycle state, active and completed slices, next action, and approval provenance; the full legacy content remains readable in the migrated brief.

`inspect` never converts a plan automatically. Valid terminal v4 plans (`shipped` or `cancelled`) are ignored by active-plan discovery and explicit migration rejects them. Malformed or unsupported state, a stale token, a path outside the canonical repository location, or an archive mismatch leaves the PLAN unchanged. If an interruption occurs after the exact archive is written but before replacement, retrying with the same bytes and mode safely resumes; any mismatch fails.

This converter is a canonical state-preservation seam, not a second active workflow. New and migrated work both continue only through the lean Feature Brief.

### 2. Build in working slices

Each slice delivers observable behavior through an Implement ⇄ Verify loop. Tests and deterministic checks run near the change, so feedback comes from working code early instead of from a large speculative plan.

Discovering another caller, file, owner, schema, route, test, or configuration is normal engineering evidence. Codex updates the implementation and affected proof without reopening the brief. Replanning happens only when evidence changes the accepted outcome or the material risk contract.

### 3. Review what actually changed

Review is anchored to the actual diff, affected behavior, blast radius, and risk-targeted evidence. Standard work gets focused owner review. A critical slice adds the relevant specialist and independent review when its risk requires it, while unrelated safe slices retain the standard flow.

Findings return to Implement ⇄ Verify. An implementation defect is fixed and re-proved; a genuine outcome or risk-contract discovery reopens only the smallest affected part of the brief.

### 4. Ship the proven artifact

Shipping verifies the working artifact before delivery and verifies that committed `HEAD` still matches it after hooks, then runs publish gates and crosses only the Git or deployment boundary the user explicitly approved. Build does not silently commit, push, open a pull request, merge, publish, or perform another external write.

## The question contract

Codex asks only when the answer materially changes:

- product outcome or user-visible behavior;
- UX choice;
- policy or default;
- security or privacy;
- data-loss exposure;
- an irreversible decision.

Reversible engineering details belong to the agent. It chooses from repository evidence, keeps the design simple, and verifies the result. A new file or test is not a reason to ask permission again.

If a correction changes the accepted outcome or risk contract, Codex shows the exact delta and asks for confirmation. Clear bounded corrections continue immediately.

## Quality safeguards

Speed comes from removing duplicated ceremony, not from weakening engineering:

- KISS, YAGNI, DRY, and one source of truth remain mandatory.
- Bugs are diagnosed before they are patched.
- Correctness covers the root cause and blast radius, including connected callers, schemas, keys, routes, tests, docs, configuration, and live wiring.
- Security, trust, privacy, accessibility, schema, and data-loss protections are preserved.
- Replacements complete the migration and remove legacy, alias, compatibility, and dual paths; the canonical one-time state converter is the narrow exception.
- Deterministic project gates run before model judgment.
- A green checkpoint binds the exact non-PLAN repository artifact; any later drift returns to the build loop before shipping.
- User-visible behavior receives browser or device evidence; non-visual work receives equivalent command, log, trace, or state evidence.
- Destructive actions, external writes, commits, pushes, merges, and publication retain exact approval boundaries.

No workflow can promise literally zero regressions. Hard Eng aims for lower regression risk through smaller feedback loops, focused proof, and review proportional to the actual risk.

## Context and token controls

The Feature Brief owns accepted intent. Slice checkpoints own implementation state and evidence. This lets Codex reset context after alignment or between slices without asking for approval again.

Exploration is disposable; decisions and proof receipts are durable. Large outputs are summarized into bounded evidence, reusable documentation is indexed once, and independent reads are batched. Tokens should buy a material decision or new proof—not restate the plan or re-explain unchanged context.

For long work, `$he resume` restores the accepted brief, current slice, open evidence, and next action from repository state rather than chat memory.

## Learning without blocking delivery

Hard Eng records proven process gaps when evidence shows recurrence, a false-pass gate, a systemic critical gap, or repeated waste. Product delivery continues while the improvement is investigated unless continuing would risk security, privacy, accessibility, data integrity, or another protected boundary.

Prevention prefers a root invariant and regression test, then a deterministic gate or tool, and only then more prose.

## Measuring whether it is better

Compare similar completed tasks and track:

| Signal | Desired direction |
| --- | --- |
| Time from request to first verified slice | Down |
| Tokens spent before working-code evidence | Down |
| Question and approval rounds before standard build | One |
| Replans caused by file/owner/test discovery | Zero |
| Applicable deterministic gates passed | 100% |
| Escaped defects in changed behavior | Down |
| Review findings caught before ship | Up initially, then down as prevention improves |

Metrics are evidence, not quotas. They must never reward skipping a protected check or hiding a defect.

## Worktrees and local state

Hard Eng continues in the checkout you selected. An existing branch or linked worktree continues as-is; a clean primary checkout can be used directly. If the primary checkout contains unrelated work, Codex asks once whether to stay or create a worktree. It never moves work automatically.

This repository is intentionally primary-only. Other repositories can declare required ignored local inputs in `.worktreeinclude`; only those narrow paths transfer, while dependencies and generated state rebuild through setup.

## Install

```bash
./setup.sh
./setup.sh check
```

Setup installs pinned tools, the global worktree hook dispatcher, and validates the system. Managed skills stay pinned and are not rewritten during routine setup.

## Examples

```text
Add account recovery with email and passkey paths.  # Feature Loop
Fix the typo in the account menu.                   # Direct
Make existing dashboard cards equal height.        # Direct + visual proof
Investigate this failing checkout test.             # Diagnose-first
Add passkey recovery to the approved feature.       # Show outcome delta, then confirm
$he resume                                           # Continue accepted state
$he ship                                             # Request exact delivery approvals
```
