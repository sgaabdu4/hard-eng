# Plan

Plan turns an ambiguous or material request into one decision-complete,
user-approved implementation contract. It is evidence-first and interactive;
it is not a long speculative document or an implementation stage.

## Operating contract

- Obey the bound `Plan` cursor. At `discover`, resolve the product and technical
  contract. For UI work, read [ui-decision-lab.md](ui-decision-lab.md) and use
  `prototype` before approval.
- Keep exactly one visible owner: repository-root `plan.md`. Do not create a
  second tracker, stage file, decision file, or JSON mirror. Durable lifecycle
  state stores only bounded digests, IDs, and the current cursor.
- Inspect repository evidence before asking. Use Codebase Memory for structure,
  owners, callers, dependencies, routes, and impact through
  `codebase-memory-mcp cli ...` only; never use its MCP transport. Use Context
  Mode when the evidence would otherwise be large. Record their
  runtime-observed support receipts before declaring readiness.
- Ask only for facts or choices that cannot be discovered safely. Ask one
  bounded decision at a time; group fields only when they are inseparable.
  Include a recommendation, material alternatives, and consequences. Write the
  answer into `plan.md` immediately and never ask it again unless evidence
  conflicts or scope changes.
- Immediately before a question, classify its premise and each proposed option
  as proven, unresolved, or unsupported. Apply proven facts without asking,
  ask only the unresolved choice, and discard unsupported options. A user
  decision requires an exact user answer; a recommendation or evidence-backed
  inference is not user approval.
- Make each question answerable in plain language: state what it decides, why
  it matters, the recommended default and reason, and two or three genuinely
  distinct options when alternatives exist. Permit a custom answer and “not
  sure”; use a default only when its consequences are safe and explicit.
- Before asking a material question in a bound run, record
  `clarification.required` with bounded question IDs and the conflict/decision
  digest. Wait at `await-user-clarification`; record the explicit answer digest
  before returning to the exact Plan cursor.
- Distinguish `Verified`, `Evidence-backed inference`, and `User decision`.
  Unknown is `open`, never silently assumed. Plan cannot finish with an open
  readiness domain, blocker, acceptance criterion, dependency, or material
  contradiction.
- Read current `PRODUCT.md`, `DESIGN.md`, and the code-owned token/theme source
  when applicable. Product decisions update `PRODUCT.md`; UI, design, or token
  decisions update `DESIGN.md` and the code owner before approval.
- When a brief, issue, specification, or other normative source exists, bind
  its path, Git blob or external revision, and SHA-256 digest in section 3.
  Account for every normative clause as covered by a concrete plan section,
  explicitly superseded by a user decision, not applicable with a reason, or
  open. Gaps, overlaps, changed source digests, and contradictions block
  approval. When no source exists, record that fact and its evidence in
  section 3.
- Canonicalize domain terms that affect behavior, data, ownership, permissions,
  or lifecycle. Record a compact ADR decision only when it is hard to reverse,
  surprising without context, and contains a real tradeoff; do not create a
  second planning owner.
- Do not automatically launch a model, eval, subagent, Imagegen call, or review
  fleet. Imagegen is available only through the explicit UI budget in the UI
  Decision Lab.

## Discovery coverage

Resolve every domain below. Use the exact ID and label in the section 3
readiness ledger so the deterministic validator can prove completeness.

| Domain | Resolve |
| --- | --- |
| D1 user/problem/value/success | Target user, real problem, value, measurable outcome, and failure definition |
| D2 actors/permissions/trust/accessibility | Actors, roles, authorization, trust boundaries, accessibility, privacy expectations |
| D3 scope/non-goals/compatibility/rollout | In scope, explicit non-goals, compatibility, constraints, launch and rollback |
| D4 journeys/states/recovery | End-to-end happy path, alternate paths, loading/empty/error states, cancellation and recovery |
| D5 information-architecture/visual/responsive/copy/interaction | IA, hierarchy, visual direction, responsive behavior, copy, interaction and feedback |
| D6 data/validation/privacy/retention/cache/migration | Data ownership, schema, validation, privacy, retention, cache, migration and data-loss controls |
| D7 API/events/timeouts/idempotency/concurrency/offline | Contracts, events, failure semantics, timeouts, retries, idempotency, concurrency and offline behavior |
| D8 ownership/reuse/dependencies/deletion | Canonical owner, callers, reuse, dependencies, concepts replaced, and safe deletion |
| D9 observability/support/performance/security/abuse | Logs/metrics/traces, support diagnostics, performance budgets, security and abuse cases |
| D10 tests/E2E/proof/release/rollback/completion | Test layers, E2E scenarios, visual proof, release gates, rollback and definition of done |

Allowed readiness statuses are `resolved`, `evidence-backed inference`, `not
applicable`, and `open`. Every row needs concrete evidence or a named decision.
`not applicable` requires a reason. Readiness requires no `open` rows.

## UI and complete-flow approval

When D5 is applicable, Plan owns the decision surface but does not modify
production modules. The UI Decision Lab must provide the complete inspectable
journey with realistic sanitized mock data and happy, loading, empty,
validation, permission, offline/retry, and error states. Mock boundaries must
be local and obvious; never connect the Plan artifact to production data,
credentials, auth, storage, payments, analytics, or external APIs.

For an existing product, capture a reproducible baseline and start from its
actual token/component owners. For greenfield or radical visual work, offer two
or three Imagegen direction boards only after the user approves the exact call
budget; then translate the selected direction into code-native tokens and an
interactive prototype. Generated pixels are exploration, not implementation.

Record the baseline or greenfield reason, design owner, exploration path,
prototype path and digest, approved direction, mock states, rejected options,
and Build review cadence in section 6. Submit `plan.prototype-ready` only when
the artifact is real and inspectable. The user approves the direction before
Build. Final before/after screenshots and sequence video come from the real app
during Build/Ship, not from Plan mockups.

## The one plan.md contract

The first two lines must be:

```text
<!-- hard-eng:plan/v1 run=<run-id> accepted-digest=pending -->
# Plan: <specific outcome>
```

Use exactly these numbered sections and headings:

1. `Outcome and success measures`
2. `Scope and non-goals`
3. `Evidence and constraints`
4. `Decisions and rejected alternatives`
5. `Actors and end-to-end journeys`
6. `UI/design contract and approved prototype reference, when applicable`
7. `Data/API/security/migration/observability contract`
8. `Vertical implementation slices with owners and dependencies`
9. `Acceptance and proof matrix`
10. `Adversarial findings and dispositions`
11. `Rollout, rollback, and open blockers`

Section 3 contains the D1–D10 readiness ledger. Section 8 contains contiguous
`S1..Sn` vertical slices, each with an observable outcome, canonical owner,
earlier dependencies or `none`, and mapped proof IDs. Slice by end-to-end value,
not by technical layer; each slice will run the Build–Verify loop independently.

Section 9 contains `P1..Pn`, each with exact observable acceptance, proof owner,
and deterministic command or artifact. Every slice maps to at least one existing
proof ID. Include real-app visual/E2E artifacts when behavior is user-visible.

Section 10 performs a concrete adversarial pass with all exact categories:

| Category | Challenge |
| --- | --- |
| A1 problem/scope | Wrong problem, hidden scope, or success metric gaming |
| A2 trust/people | Role, permission, privacy, accessibility, or support harm |
| A3 journey failure | Abandonment, retries, recovery, and bad edge-state behavior |
| A4 state/data | Invalid, stale, concurrent, migrated, cached, or lost data |
| A5 architecture/operations | Wrong owner, coupling, performance, observability, deploy or rollback failure |
| A6 interface | API/UI contract mismatch, responsive/copy/interaction ambiguity |
| A7 delivery | Dependency, sequencing, rollout, compatibility, or handoff failure |
| A8 false proof | A check or artifact that can pass while the intended behavior is broken |

Each adversarial row records a concrete counterexample, observed outcome,
`resolve`, `accept`, or `out-of-scope`, affected section, and evidence or
mitigation. `accept` requires explicit user-approved rationale. Apply resolved
findings back to the owning section; do not leave a detached critique list.

Section 11 ends with exactly `**Open blockers:** none` only when that is true.
An unresolved blocker keeps the cursor in Plan.

## Readiness and approval

Before requesting approval:

- reconcile contradictions and show any evidence-backed inference plainly;
- confirm D1–D10, A1–A8, slice dependencies, proof mappings, rollout, and
  rollback are complete;
- confirm every normative source is current and completely mapped;
- run `he plan-validate --repo . --run <run-id>` and fix every deterministic
  error; and
- submit `plan.ready-for-approval` only after Codebase Memory and Context Mode
  dispositions are recorded and any UI prototype is reviewable.

Present a compact decision packet: outcome, scope/non-goals, complete journeys,
UI direction when applicable, data/API/security choices, vertical slices,
acceptance proof, material risks, rollout, rollback, and the plan digest. Do not
substitute “looks good” from the model for user approval.

After explicit approval, run `he plan-digest --repo . --run <run-id>`, replace
`accepted-digest=pending` with that exact digest, validate again with acceptance
required, and submit `plan.accepted` with `approver: user`. The state server
re-reads the file and binds its sections, slice IDs, proof IDs, UI evidence, and
digest before entering `Build:red` at S1.

Any post-approval content edit invalidates the digest. A changed outcome, scope,
acceptance rule, product behavior, or design returns to Plan, shows the section
delta, and requires fresh explicit approval.

## Cost discipline

Load the full Plan reference and `plan.md` only while planning or reconciling.
Routine Build loads one bounded `he plan-excerpt --run <run-id> --slice S<n>`.
Never copy transcripts, raw tool output, full code maps, or repeated rationale
into the plan or state. Prefer exact tables and short evidence references over
verbose prose. The validator warns beyond roughly 12,000 tokens; size alone
never justifies omitting an unresolved decision.
