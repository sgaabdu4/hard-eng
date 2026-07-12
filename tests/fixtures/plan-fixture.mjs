export const PLAN_HEADINGS = [
  'Outcome and success measures',
  'Scope and non-goals',
  'Evidence and constraints',
  'Decisions and rejected alternatives',
  'Actors and end-to-end journeys',
  'UI/design contract and approved prototype reference, when applicable',
  'Data/API/security/migration/observability contract',
  'Vertical implementation slices with owners and dependencies',
  'Acceptance and proof matrix',
  'Adversarial findings and dispositions',
  'Rollout, rollback, and open blockers',
];

const domains = [
  'D1 user/problem/value/success',
  'D2 actors/permissions/trust/accessibility',
  'D3 scope/non-goals/compatibility/rollout',
  'D4 journeys/states/recovery',
  'D5 information-architecture/visual/responsive/copy/interaction',
  'D6 data/validation/privacy/retention/cache/migration',
  'D7 API/events/timeouts/idempotency/concurrency/offline',
  'D8 ownership/reuse/dependencies/deletion',
  'D9 observability/support/performance/security/abuse',
  'D10 tests/E2E/proof/release/rollback/completion',
];

const adversarial = [
  'A1 problem/scope',
  'A2 trust/people',
  'A3 journey failure',
  'A4 state/data',
  'A5 architecture/operations',
  'A6 interface',
  'A7 delivery',
  'A8 false proof',
];

export function withAcceptedDigest(text, digest) {
  return text.replace('accepted-digest=pending', `accepted-digest=${digest}`);
}

export function makePlan({
  runId = 'he-plan-fixture',
  acceptedDigest = 'pending',
  openDomain = null,
  omitAdversarial = null,
  ui = null,
} = {}) {
  const ledger = domains.map((domain) => {
    const id = domain.split(' ')[0];
    const status = id === openDomain ? 'open' : id === 'D5' && !ui ? 'not applicable' : 'resolved';
    return `| ${domain} | ${status} | ${status === 'open' ? 'Decision required' : 'Verified fixture evidence'} |`;
  }).join('\n');
  const adversarialRows = adversarial
    .filter((category) => !category.startsWith(`${omitAdversarial} `) && category.split(' ')[0] !== omitAdversarial)
    .map((category) => `| ${category} | Concrete counterexample for ${category} | Observed bounded behavior | resolve | §2 | Updated the named contract with fixture evidence |`)
    .join('\n');
  const uiContract = ui ? [
    '**UI applicability:** applicable',
    `**Baseline:** ${ui.baseline ?? 'not applicable — greenfield fixture'}`,
    `**Design owner:** ${ui.designOwner ?? 'new token proposal in the coded prototype'}`,
    `**Exploration path:** ${ui.exploration ?? 'constrained'}`,
    ...((ui.exploration ?? 'constrained') === 'imagegen' ? [
      `**Imagegen budget:** ${ui.imagegenBudget ?? 'approved: 2 calls'}`,
      `**Visual brief:** ${ui.visualBrief ?? 'Sanitized fixture brief with identical actors, flow, states, and mock content'}`,
      `**Direction boards:** ${ui.directionBoards}`,
      '**Rejected directions:** Rejected named alternatives and retained only the approved constraints',
    ] : []),
    `**Prototype:** ${ui.prototypePath} @ ${ui.prototypeDigest}`,
    '**Approved direction:** Fixture direction — user-approved',
    '**Mock states:** happy, loading, empty, validation, permission, error',
    '**Review cadence:** meaningful-milestones',
    '**Coded options:** not applicable — direction already constrained',
  ].join('\n') : '**UI applicability:** not applicable — no user-visible interface';

  return `<!-- hard-eng:plan/v1 run=${runId} accepted-digest=${acceptedDigest} -->
# Plan: Deterministic fixture

## 1. ${PLAN_HEADINGS[0]}

Deliver exact behavior with measurable acceptance P1 and P2.

## 2. ${PLAN_HEADINGS[1]}

In scope: one owner. Non-goal: unrelated product work.

## 3. ${PLAN_HEADINGS[2]}

Primary evidence is the repository and accepted user decisions.

### Readiness ledger

| Domain | Status | Evidence or decision |
| --- | --- | --- |
${ledger}

## 4. ${PLAN_HEADINGS[3]}

Selected one canonical owner. Rejected parallel state files because they drift.

## 5. ${PLAN_HEADINGS[4]}

Actor starts the flow, observes recovery states, and completes safely.

## 6. ${PLAN_HEADINGS[5]}

${uiContract}

## 7. ${PLAN_HEADINGS[6]}

Validate inputs, preserve privacy, use idempotency, expose support diagnostics, and roll back safely.

## 8. ${PLAN_HEADINGS[7]}

| Slice | Outcome | Owner | Depends on | Proof IDs |
| --- | --- | --- | --- | --- |
| S1 | Establish the owner | runtime | none | P1 |
| S2 | Complete the behavior | runtime | S1 | P2 |

## 9. ${PLAN_HEADINGS[8]}

| Proof | Acceptance | Owner | Command or artifact |
| --- | --- | --- | --- |
| P1 | Owner rejects invalid state | runtime test | node --test tests/owner.test.mjs |
| P2 | Journey passes end to end | E2E | artifacts/final-proof.json |

## 10. ${PLAN_HEADINGS[9]}

| Category | Concrete challenge | Observed outcome | Disposition | Affected section | Evidence or mitigation |
| --- | --- | --- | --- | --- | --- |
${adversarialRows}

## 11. ${PLAN_HEADINGS[10]}

Roll out behind the existing owner and revert the candidate commit on failure.

**Open blockers:** none
`;
}
