import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';

const repo = path.resolve(new URL('..', import.meta.url).pathname);
const script = path.join(repo, 'scripts', 'he-state.mjs');
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'he-state-'));
fs.mkdirSync(path.join(tmp, 'tests'), { recursive: true });
fs.writeFileSync(path.join(tmp, 'package.json'), `${JSON.stringify({
  scripts: {
    test: 'node --test tests/owner.test.mjs',
    'test:unit': 'node --test tests/unit.test.mjs',
    mutation: 'stryker run',
    'make-it-fail': 'node --test tests/make-it-fail.test.mjs',
  },
}, null, 2)}\n`);
fs.writeFileSync(path.join(tmp, 'tests', 'owner.test.mjs'), 'import "node:test";\n');

function run(state) {
  const file = path.join(tmp, `${Math.random().toString(36).slice(2)}.json`);
  fs.writeFileSync(file, `${JSON.stringify(state, null, 2)}\n`);
  return spawnSync('node', [script, 'validate', file], { encoding: 'utf8' });
}

function handoverPrompt(stage, statePath, next) { const command = next.match(/\/he:[a-z-]+|loop complete/i)?.[0] || next; return `Start a fresh Hard Eng stage session. Worktree: /tmp/hard-eng-worktree. Command: ${command}. Stage: ${stage}. State: ${statePath}. Next: ${next}. Read ${statePath} first. Do not use the previous chat transcript.`; }
function stageReceipt(overrides = {}) { const receipt = { stage: 'he-plan', state: 'docs/planning/filters/he-state.json', decision: 'PASS', ownerProof: ['src/filters.ts', 'npm test -- filters'], artifacts: ['docs/planning/filters/he-state.json'], blocker: 'none', next: 'ready for /he:implement: yes', ...overrides }; return { ...receipt, handoverPrompt: handoverPrompt(receipt.stage, receipt.state, receipt.next) }; }
const doneReceipt = stageReceipt();

const requiredSubStages = {
  'he-plan': ['context', 'grill-me', 'owner-proof', 'artifact-choice', 'risk-route', 'learning-capture', 'state-validation'],
  'he-implement': ['owner-read', 'ssot-owner-reuse', 'test-first', 'owner-change', 'guardrails', 'learning-capture', 'state-update'],
  'he-verify': ['tests', 'guardrails', 'reviews', 'fix-loop', 'learning-capture', 'state-update'],
  'he-ship': ['status', 'hooks', 'quality-gates', 'no-mistakes', 'pr-evidence', 'pr-review-threads', 'ci-or-skip', 'learning-capture', 'state-update'],
  'he-learn': ['learning-findings', 'durable-owner', 'proof', 'state-update'],
};
const entryStages = { 'he-implement': 'he-plan', 'he-verify': 'he-implement', 'he-ship': 'he-verify', 'he-learn': 'he-ship' };
function ssotOwnerLedger() {
  return [
    {
      ownerClass: 'workflow-state',
      decision: 'reuse',
      owner: 'scripts/he-state.mjs',
      evidence: ['workflow-state owner reused for state validation'],
    },
  ];
}
function subStagesFor(stage) {
  return requiredSubStages[stage].map((id, index) => ({
    id,
    title: id,
    status: 'done',
    evidence: [id === 'ssot-owner-reuse' ? 'SSOT reused: workflow-state owner; SSOT extended: none; new owners created: none' : `${stage}:${id}`],
    ...(id === 'ssot-owner-reuse' ? { ownerLedger: ssotOwnerLedger() } : {}),
    sequence: index + 1,
  }));
}
function entryGateFor(stage) {
  return { fromStage: entryStages[stage], decision: 'PASS', statePath: 'docs/planning/filters/he-state.json', evidence: [`${entryStages[stage]} receipt`] };
}
function guardrailsFor(stage) {
  const g = (id, guardStage, kind, owner, command, evidence, blocksPush = false) => ({
    id, stage: guardStage, kind, owner, command, status: 'passed', evidence: [evidence], blocksPush,
  });
  const tq = (text) => `test-quality scenarios recorded; ${text}`;
  const stateValidation = g('state-validation', 'he-plan', 'script', 'scripts/he-state.mjs', 'node "$HOME/.agents/scripts/he-state.mjs" validate he-state.json', 'he-state: pass');
  if (stage === 'he-plan') {
    return [
      g('context-gate', 'he-plan', 'script', 'scripts/check-project-context-gates.mjs', 'node "$HOME/.agents/scripts/check-project-context-gates.mjs" --require-all .', 'context-gates: pass'),
      stateValidation,
    ];
  }
  if (stage === 'he-verify') {
    return [
      g('quality-gate', 'he-verify', 'script', 'scripts/check-project-quality-gates.mjs', 'node "$HOME/.agents/scripts/check-project-quality-gates.mjs" --require-push-gate .', 'quality-gates: pass', true),
      stateValidation,
    ];
  }
  if (stage === 'he-ship') {
    return [
      { ...g('git-status', 'he-ship', 'manual', 'git', 'git status --short', 'clean feature branch', true), sequence: 1 },
      { ...g('worktree-ready', 'he-ship', 'script', 'scripts/ensure-worktree-ready.sh', '"$HOME/.agents/scripts/ensure-worktree-ready.sh" --check --require-pre-push .', 'worktree ready', true), sequence: 2 },
      { ...g('quality-gate', 'he-ship', 'script', 'scripts/check-project-quality-gates.mjs', 'node "$HOME/.agents/scripts/check-project-quality-gates.mjs" --require-push-gate .', 'quality-gates: pass', true), sequence: 3 },
      { ...g('no-mistakes', 'he-ship', 'script', 'no-mistakes', 'no-mistakes axi run --intent "ship verified feature" --pr 7', 'no-mistakes axi run passed with findings: none', true), sequence: 4 },
      { ...g('pr-evidence', 'he-ship', 'script', 'integrations/no-mistakes/scripts/repair-pr-evidence.mjs', 'node "$HOME/.agents/integrations/no-mistakes/scripts/repair-pr-evidence.mjs" --pr 7', 'Current head: `abcdef1234567890abcdef1234567890abcdef12`; No open no-mistakes findings; PR screenshots not required; evidence clean', true), sequence: 5 },
      { ...g('pr-review-threads', 'he-ship', 'script', 'integrations/no-mistakes/scripts/repair-pr-evidence.mjs', 'node "$HOME/.agents/integrations/no-mistakes/scripts/repair-pr-evidence.mjs" --pr 7 --check-review-threads', 'No open GitHub review threads; 5 thread(s) checked', true), sequence: 6 },
      { ...g('ci-or-skip', 'he-ship', 'script', 'gh', 'gh pr checks 7', 'CI passed green', true), sequence: 7 },
      stateValidation,
    ];
  }
  if (stage === 'he-implement') {
    return [
      { ...g('deterministic-owner-scan', 'he-implement', 'script', 'scripts/find-deterministic-owner.mjs', 'node "$HOME/.agents/scripts/find-deterministic-owner.mjs" --json --root . owner path', 'deterministic owner scan recorded'), sequence: 1 },
      { ...g('test-first-proof', 'he-implement', 'test', 'tests/owner.test.mjs', 'npm test -- owner', tq('red-first failing test recorded before owner-change')), sequence: 2 },
      { ...g('implementation-proof', 'he-implement', 'test', 'tests/owner.test.mjs', 'npm test -- owner', 'post-change tests passed'), sequence: 5 },
      stateValidation,
    ];
  }
  return [stateValidation];
}
const inventoryIds = ['regex-scanners', 'git-hooks', 'lint-analyze-typecheck', 'ssot-scanners', 'fallow', 'react-doctor', 'repeat-mistake-prevention'];
function guardrailInventory(entries = {}) {
  return {
    touchedStacks: ['workflow-state'],
    requiredGuardrails: inventoryIds.map((id) => entries[id] || { id, status: 'not_applicable', reason: `${id} not touched`, evidence: ['guardrail inventory reviewed'] }),
  };
}
function closedLearningFinding() {
  return { id: 'learn-closed', stage: 'he-ship', summary: 'Repeated miss has durable guard', ownerStage: 'he-learn', repairType: 'learning', ownerProof: ['tests/he-state.test.mjs'], artifacts: [], status: 'fixed' };
}

const grillQuestion = `Q4: Where should Recorded sit in client My Sessions?

Meaning: Pick the first visible UI shape for clients who have a real recorded booking row.
Why it matters: Existing My Sessions has client product panels and a separate Training Sessions list.
Suggested default: A - it keeps recorded completion separate from live attendance.

Options:
A) Show Recorded as its own client-only section before Training Sessions.
B) Put Recorded workouts inside the existing Training Sessions list.
C) Not sure - use the default.

Reply: A/B/C, "use default", "not sure", "skip for now", or your own answer.`;

const planReadiness = {
  grillMe: {
    required: true,
    status: 'accepted',
    statePath: 'docs/planning/filters/session_state.md', questionPolicy: { mode: 'unlimited_until_aligned', evidence: ['session_state.md asks until aligned'] }, alignment: { status: 'aligned', userConfirmed: true, noGuesswork: true, openQuestions: [], openUnknowns: [], evidence: ['user confirmed plan alignment'] },
    stages: [
      { id: 'product', map: 'skip', status: 'skipped', reason: 'Product behavior was already decided in PRODUCT.md', evidence: ['PRODUCT.md'] },
      { id: 'ui-flow', map: 'run', status: 'done', evidence: ['docs/planning/filters/session_state.md'] },
      { id: 'visual-design', map: 'n/a', status: 'skipped', reason: 'No visual direction change', evidence: ['DESIGN.md'] },
    ],
    lastQuestion: { status: 'answered', format: 'grill-me/v1', text: grillQuestion, visibleText: grillQuestion },
  },
  uiReview: {
    required: true,
    status: 'accepted',
    liveTool: 'impeccable-live', decisionTool: 'lavish', decisionPurpose: 'ui_flow', localhostUrl: 'http://127.0.0.1:4173/mock-flow.html',
    designSystemEvidence: ['DESIGN.md', 'docs/design/tokens.css'], sharedComponentEvidence: ['src/components/session-card.tsx'],
    reviewSurfacePath: 'src/routes/my-sessions/recorded-preview.tsx', shownToUser: true, userResponse: 'Approved after tweaks',
    tweaks: ['Tightened copy'], alignment: { status: 'aligned', userConfirmed: true, noGuesswork: true, openDecisions: [], openUnknowns: [], evidence: ['user approved UI decision'] },
    lavish: { decisionStatus: 'accepted', launchCommand: 'npx -y lavish-axi docs/planning/filters/mock-flow.html', pollCommand: 'npx -y lavish-axi poll docs/planning/filters/mock-flow.html', optionsPath: 'docs/planning/filters/ui-options.html', pollReceiptPath: 'docs/planning/filters/lavish-poll.md', savedChoicesPath: 'docs/planning/filters/ui-decisions.md', savedComponentsPath: 'docs/planning/filters/components.md', userDecision: 'Option A approved', selectedOption: 'A', optionsShown: ['A', 'B'], rejectedOptions: ['B'], selectedComponents: ['SessionCard'], evidence: ['lavish poll returned approval'] },
    evidence: ['src/routes/my-sessions/recorded-preview.tsx', 'docs/planning/filters/impeccable-review.png'],
  },
  artifact: { status: 'accepted', paths: ['docs/planning/filters/plan.md'] },
};

const valid = {
  schema: 'he-state/v1',
  feature: 'filters',
  updatedAt: '2026-06-25T00:00:00.000Z',
  stage: 'he-plan',
  stageIndex: 1,
  status: 'ready',
  currentStep: 'handoff',
  next: { target: '/he:implement', ready: true, reason: 'plan passed' },
  steps: [
    { id: '1', title: 'Find owner', status: 'done', receipt: doneReceipt },
    { id: '2', title: 'Choose proof', status: 'done', receipt: doneReceipt },
  ],
  subStages: subStagesFor('he-plan'),
  findings: [],
  guardrails: guardrailsFor('he-plan'),
  context: {
    product: { path: 'PRODUCT.md', status: 'current' },
    design: { path: 'DESIGN.md', status: 'current' },
    tokenOwner: { path: 'docs/design/tokens.css', status: 'current' },
  },
  planReadiness,
  agentWork: [
    { id: 'review-1', kind: 'subagent', model: 'gpt-5.5', purpose: 'stage contract review', status: 'done', evidence: ['review receipt'] },
    { id: 'eval-1', kind: 'eval', model: 'gpt-5.4-mini', purpose: 'routing eval', status: 'done', evidence: ['eval pass'] },
  ],
  decisions: [],
  blockers: [],
};

let result = run(valid);
assert.equal(result.status, 0, result.stderr);
assert.match(result.stdout, /he-state: pass/);

result = run({
  ...valid,
  steps: [
    { id: '1', title: 'Find owner', status: 'done', receipt: doneReceipt },
    { id: '2', title: 'Choose proof', status: 'pending' },
  ],
});
assert.notEqual(result.status, 0);
assert.match(result.stderr, /next\.ready cannot be true/);

result = run({
  ...valid,
  steps: [{ id: '1', title: 'Find owner', status: 'done' }],
});
assert.notEqual(result.status, 0);
assert.match(result.stderr, /receipt is required/);

result = run({
  ...valid,
  steps: [
    { id: '1', title: 'Find owner', status: 'skipped' },
    { id: '2', title: 'Choose proof', status: 'done', receipt: doneReceipt },
  ],
});
assert.notEqual(result.status, 0);
assert.match(result.stderr, /reason is required for skipped/);

result = run({
  ...valid,
  findings: [{
    id: 'finding-1',
    stage: 'he-plan',
    summary: 'Owner is unclear',
    ownerStage: 'he-plan', repairType: 'scope',
    ownerProof: [],
    artifacts: [],
    status: 'open',
    blocking: true,
  }],
});
assert.notEqual(result.status, 0);
assert.match(result.stderr, /blocking findings are unresolved/);

const { context, ...missingContext } = valid;
result = run(missingContext);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /he-plan ready handoff requires context\.product/);

result = run({
  ...valid,
  planReadiness: {
    ...planReadiness,
    grillMe: {
      ...planReadiness.grillMe,
      status: 'pending',
      stages: [
        { id: 'ui-flow', map: 'run', status: 'in_progress', evidence: [] },
        { id: 'visual-design', map: 'run', status: 'pending', evidence: [] },
      ],
      lastQuestion: { status: 'asked', format: 'grill-me/v1', text: grillQuestion },
    },
  },
});
assert.notEqual(result.status, 0);
assert.match(result.stderr, /requires required Grill Me to be accepted/);
assert.match(result.stderr, /unresolved Grill Me stages/);
assert.match(result.stderr, /open Grill Me question/);
assert.match(result.stderr, /visible Grill Me question text/);

result = run({
  ...valid,
  planReadiness: {
    ...planReadiness,
    grillMe: {
      ...planReadiness.grillMe,
      lastQuestion: {
        status: 'asked',
        format: 'grill-me/v1',
        text: 'Q4: Where should Recorded sit?\nA) Own section\nB) In list\nC) Default A',
        visibleText: 'Q4: Where should Recorded sit?\nA) Own section\nB) In list\nC) Default A',
      },
    },
  },
});
assert.notEqual(result.status, 0);
assert.match(result.stderr, /full Grill Me question format/);

result = run({
  ...valid,
  planReadiness: {
    ...planReadiness,
    grillMe: {
      ...planReadiness.grillMe,
      lastQuestion: { status: 'answered', format: 'grill-me/v1', text: grillQuestion, visibleText: `${grillQuestion}\n` },
    },
  },
});
assert.notEqual(result.status, 0);
assert.match(result.stderr, /visibleText must match text exactly/);

const { uiReview, ...withoutUiReview } = planReadiness;
result = run({ ...valid, planReadiness: withoutUiReview });
assert.notEqual(result.status, 0);
assert.match(result.stderr, /requires planReadiness\.uiReview/);

result = run({
  ...valid,
  planReadiness: {
    ...planReadiness,
    uiReview: {
      ...planReadiness.uiReview,
      shownToUser: false,
    },
  },
});
assert.notEqual(result.status, 0);
assert.match(result.stderr, /shownToUser must be true/);

result = run({
  ...valid,
  planReadiness: {
    ...planReadiness,
    uiReview: {
      ...planReadiness.uiReview,
      liveTool: 'static-review',
    },
  },
});
assert.notEqual(result.status, 0);
assert.match(result.stderr, /liveTool must be impeccable-live/);

for (const [field, value, expected] of [
  ['reviewSurfacePath', '', /reviewSurfacePath is required/],
  ['userResponse', '', /userResponse is required/],
  ['designSystemEvidence', [], /designSystemEvidence is required/],
  ['evidence', [], /uiReview\.evidence is required/],
  ['tweaks', [], /tweaks must record/],
]) {
  result = run({
    ...valid,
    planReadiness: {
      ...planReadiness,
      uiReview: {
        ...planReadiness.uiReview,
        [field]: value,
      },
    },
  });
  assert.notEqual(result.status, 0, `${field} should be required`);
  assert.match(result.stderr, expected);
}

result = run({
  ...valid,
  planReadiness: {
    ...planReadiness,
    uiReview: {
      ...planReadiness.uiReview,
      status: 'parked',
      reason: '',
    },
  },
});
assert.notEqual(result.status, 0);
assert.match(result.stderr, /uiReview\.reason is required for parked/);

result = run({
  ...valid,
  subStages: subStagesFor('he-plan').filter((step) => step.id !== 'grill-me'),
});
assert.notEqual(result.status, 0);
assert.match(result.stderr, /requires subStage grill-me/);

result = run({
  ...valid,
  subStages: subStagesFor('he-plan').map((step) => step.id === 'risk-route'
    ? { id: 'risk-route', title: 'risk-route', status: 'skipped' }
    : step),
});
assert.notEqual(result.status, 0);
assert.match(result.stderr, /subStages\[\d+\]\.reason is required for skipped/);

result = run({
  ...valid,
  agentWork: [{ id: 'bad-subagent', kind: 'subagent', model: 'gpt-5.4-mini', purpose: 'review', status: 'done', evidence: ['review'] }],
});
assert.notEqual(result.status, 0);
assert.match(result.stderr, /model must be gpt-5\.5 for subagent work/);

result = run({
  ...valid,
  agentWork: [{ id: 'bad-eval', kind: 'eval', model: 'gpt-5.5', purpose: 'routing eval', status: 'done', evidence: ['eval'] }],
});
assert.notEqual(result.status, 0);
assert.match(result.stderr, /model must be gpt-5\.4-mini for eval work/);

result = run({
  ...valid,
  steps: [
    { id: '1', title: 'Find owner', status: 'done', receipt: stageReceipt({ next: `ready for /a${'a'}:implement: yes` }) },
    { id: '2', title: 'Choose proof', status: 'done', receipt: doneReceipt },
  ],
});
assert.notEqual(result.status, 0);
assert.match(result.stderr, new RegExp(`old /${String.fromCharCode(97, 97)} command`));

for (const [stage, stageIndex, target] of [
  ['he-plan', 1, '/he:implement'],
  ['he-implement', 2, '/he:verify'],
  ['he-verify', 3, '/he:ship'],
  ['he-ship', 4, 'loop-complete'],
  ['he-learn', 5, 'loop-complete'],
]) {
  result = run({
    ...valid,
    stage,
    stageIndex,
    next: { target, ready: true, reason: 'handoff allowed' },
    subStages: subStagesFor(stage),
    guardrails: guardrailsFor(stage),
    guardrailInventory: ['he-implement', 'he-verify', 'he-ship'].includes(stage) ? guardrailInventory() : undefined,
    entryGate: stage === 'he-plan' ? undefined : entryGateFor(stage),
    findings: stage === 'he-learn' ? [closedLearningFinding()] : valid.findings,
    planReadiness: stage === 'he-plan' ? planReadiness : valid.planReadiness,
    steps: [
      {
        id: '1',
        title: 'Stage passed',
        status: 'done',
        receipt: stageReceipt({ stage, next: `ready target ${target}` }),
      },
    ],
  });
  assert.equal(result.status, 0, `${stage} should allow ${target}: ${result.stderr}`);

  result = run({
    ...valid,
    stage,
    stageIndex,
    next: { target: '/he:plan', ready: true, reason: 'bad handoff' },
    subStages: subStagesFor(stage),
    guardrails: guardrailsFor(stage),
    entryGate: stage === 'he-plan' ? undefined : entryGateFor(stage),
    findings: stage === 'he-learn' ? [closedLearningFinding()] : valid.findings,
    steps: [
      {
        id: '1',
        title: 'Stage passed',
        status: 'done',
        receipt: stageReceipt({ stage, next: 'bad handoff' }),
      },
    ],
  });
  assert.notEqual(result.status, 0, `${stage} should reject the wrong next target`);
  assert.match(result.stderr, /next\.target must be/);

  for (const subStageId of requiredSubStages[stage]) {
    result = run({
      ...valid,
      stage,
      stageIndex,
      next: { target, ready: true, reason: 'handoff allowed' },
      subStages: subStagesFor(stage).filter((item) => item.id !== subStageId),
      guardrails: guardrailsFor(stage),
      entryGate: stage === 'he-plan' ? undefined : entryGateFor(stage),
      findings: stage === 'he-learn' ? [closedLearningFinding()] : valid.findings,
      steps: [
        {
          id: '1',
          title: 'Stage passed',
          status: 'done',
          receipt: stageReceipt({ stage, next: `ready target ${target}` }),
        },
      ],
    });
    assert.notEqual(result.status, 0, `${stage} should reject missing ${subStageId}`);
    assert.match(result.stderr, new RegExp(`requires subStage ${subStageId}`));

    for (const status of ['pending', 'in_progress', 'blocked']) {
      result = run({
        ...valid,
        stage,
        stageIndex,
        next: { target, ready: true, reason: 'handoff allowed' },
        subStages: subStagesFor(stage).map((item) => item.id === subStageId
          ? { ...item, status, reason: status === 'blocked' ? 'blocked by test fixture' : item.reason }
          : item),
        guardrails: guardrailsFor(stage),
        entryGate: stage === 'he-plan' ? undefined : entryGateFor(stage),
        findings: stage === 'he-learn' ? [closedLearningFinding()] : valid.findings,
        steps: [
          {
            id: '1',
            title: 'Stage passed',
            status: 'done',
            receipt: stageReceipt({ stage, next: `ready target ${target}` }),
          },
        ],
      });
      assert.notEqual(result.status, 0, `${stage} should reject ${subStageId} ${status}`);
      assert.match(result.stderr, new RegExp(`requires subStage ${subStageId} to be done or skipped`));
    }
  }
}

for (const [stage, stageIndex, target, subStageId] of [
  ['he-plan', 1, '/he:implement', 'state-validation'],
  ['he-plan', 1, '/he:implement', 'owner-proof'],
  ['he-plan', 1, '/he:implement', 'artifact-choice'],
  ['he-plan', 1, '/he:implement', 'risk-route'],
  ['he-implement', 2, '/he:verify', 'owner-change'],
  ['he-verify', 3, '/he:ship', 'tests'],
  ['he-ship', 4, 'loop-complete', 'no-mistakes'],
  ['he-ship', 4, 'loop-complete', 'quality-gates'],
  ['he-learn', 5, 'loop-complete', 'proof'],
]) {
  result = run({
    ...valid,
    stage,
    stageIndex,
    next: { target, ready: true, reason: 'handoff allowed' },
    subStages: subStagesFor(stage).map((item) => item.id === subStageId
      ? { ...item, status: 'skipped', reason: 'fixture skip', evidence: ['fixture'] }
      : item),
    guardrails: guardrailsFor(stage),
    entryGate: stage === 'he-plan' ? undefined : entryGateFor(stage),
    findings: stage === 'he-learn' ? [closedLearningFinding()] : valid.findings,
    steps: [{
      id: '1',
      title: 'Stage passed',
      status: 'done',
      receipt: stageReceipt({ stage, next: `ready target ${target}` }),
    }],
  });
  assert.notEqual(result.status, 0, `${stage} should not allow skipped ${subStageId}`);
  assert.match(result.stderr, new RegExp(`requires subStage ${subStageId} to be done, not skipped`));
}

result = run({
  ...valid,
  stage: 'he-implement',
  stageIndex: 2,
  next: { target: '/he:verify', ready: true, reason: 'handoff allowed' },
  subStages: subStagesFor('he-implement'),
  guardrails: guardrailsFor('he-implement'),
  guardrailInventory: guardrailInventory(),
  steps: [{ id: '1', title: 'Stage passed', status: 'done', receipt: stageReceipt({ stage: 'he-implement', next: 'ready target /he:verify' }) }],
});
assert.notEqual(result.status, 0);
assert.match(result.stderr, /he-implement ready handoff requires entryGate from he-plan/);

result = run({
  ...valid,
  guardrails: [],
});
assert.notEqual(result.status, 0);
assert.match(result.stderr, /requires passed guardrail context-gate/);
assert.match(result.stderr, /requires passed guardrail state-validation/);

result = run({
  ...valid,
  planReadiness: {
    ...planReadiness,
    uiReview: {
      ...planReadiness.uiReview,
      status: 'parked',
      reason: 'user paused UI review',
    },
  },
});
assert.notEqual(result.status, 0);
assert.match(result.stderr, /requires UI review to be accepted/);

result = run({
  ...valid,
  stage: 'he-ship',
  stageIndex: 4,
  subStages: subStagesFor('he-ship'),
  guardrails: [],
  guardrailInventory: guardrailInventory(),
  entryGate: entryGateFor('he-ship'),
  next: { target: 'loop-complete', ready: true, reason: 'ship clean' },
  steps: [{
    id: '1',
    title: 'Gate passed',
    status: 'done',
    receipt: stageReceipt({ stage: 'he-ship', next: 'loop complete: yes' }),
  }],
});
assert.notEqual(result.status, 0);
assert.match(result.stderr, /requires passed guardrail git-status/);
assert.match(result.stderr, /requires passed guardrail no-mistakes/);

result = run({
  ...valid,
  stage: 'he-learn',
  stageIndex: 5,
  subStages: subStagesFor('he-learn'),
  guardrails: guardrailsFor('he-learn'),
  entryGate: entryGateFor('he-learn'),
  next: { target: 'loop-complete', ready: true, reason: 'learning done' },
  steps: [{
    id: '1',
    title: 'Learning passed',
    status: 'done',
    receipt: stageReceipt({ stage: 'he-learn', next: 'loop complete: yes' }),
  }],
});
assert.notEqual(result.status, 0);
assert.match(result.stderr, /requires a fixed or accepted learning finding/);

result = run({
  ...valid,
  stage: 'he-ship',
  stageIndex: 4,
  subStages: subStagesFor('he-ship'),
  guardrails: guardrailsFor('he-ship'),
  guardrailInventory: guardrailInventory(),
  entryGate: entryGateFor('he-ship'),
  next: { target: 'loop-complete', ready: true, reason: 'ship clean and no learning needed' },
  steps: [{ id: '1', title: 'Gate passed', status: 'done', receipt: stageReceipt({ stage: 'he-ship', next: 'loop complete: yes' }) }],
});
assert.equal(result.status, 0, result.stderr);

result = run({
  ...valid,
  stage: 'he-ship',
  stageIndex: 4,
  subStages: subStagesFor('he-ship'),
  guardrails: guardrailsFor('he-ship'),
  guardrailInventory: guardrailInventory(),
  entryGate: entryGateFor('he-ship'),
  next: { target: 'loop-complete', ready: true, reason: 'ship clean' },
  steps: [{ id: '1', title: 'Gate passed', status: 'done', receipt: stageReceipt({ stage: 'he-ship', next: 'loop complete: yes' }) }],
  findings: [{
    id: 'learn-1',
    stage: 'he-ship',
    summary: 'Repeated PR evidence miss needs a guard',
    ownerStage: 'he-learn', repairType: 'learning',
    ownerProof: ['integrations/no-mistakes/scripts/repair-pr-evidence.mjs'],
    artifacts: [],
    status: 'open',
  }],
});
assert.notEqual(result.status, 0);
assert.match(result.stderr, /cannot skip he-learn/);

result = run({
  ...valid,
  stage: 'he-ship',
  stageIndex: 4,
  subStages: subStagesFor('he-ship'),
  guardrails: guardrailsFor('he-ship'),
  guardrailInventory: guardrailInventory(),
  entryGate: entryGateFor('he-ship'),
  next: { target: '/he:learn', ready: true, reason: 'learning needed' },
  steps: [{ id: '1', title: 'Gate passed', status: 'done', receipt: stageReceipt({ stage: 'he-ship', next: 'ready for /he:learn: yes' }) }],
  findings: [{
    id: 'learn-1',
    stage: 'he-ship',
    summary: 'Repeated PR evidence miss needs a guard',
    ownerStage: 'he-learn', repairType: 'learning',
    ownerProof: ['integrations/no-mistakes/scripts/repair-pr-evidence.mjs'],
    artifacts: [],
    status: 'open',
  }],
});
assert.equal(result.status, 0, result.stderr);

result = run({
  ...valid,
  stage: 'he-verify',
  stageIndex: 3,
  subStages: subStagesFor('he-verify'),
  guardrails: [{
    id: 'react-prepush',
    stage: 'he-implement',
    kind: 'hook',
    owner: '.githooks/pre-push',
    command: 'npm run qa',
    status: 'active',
    evidence: ['.githooks/pre-push'],
    blocksPush: true,
  }, ...guardrailsFor('he-verify')],
  guardrailInventory: guardrailInventory(),
  entryGate: entryGateFor('he-verify'),
  next: { target: '/he:ship', ready: true, reason: 'proof clean' },
  steps: [{ id: '1', title: 'Proof passed', status: 'done', receipt: stageReceipt({ stage: 'he-verify', next: 'ready for /he:ship: yes' }) }],
});
assert.notEqual(result.status, 0);
assert.match(result.stderr, /requires push-blocking guardrails/);

result = run({
  ...valid,
  stage: 'he-verify',
  stageIndex: 3,
  subStages: subStagesFor('he-verify'),
  guardrails: [{
    id: 'react-prepush',
    stage: 'he-implement',
    kind: 'hook',
    owner: '.githooks/pre-push',
    command: 'npm run qa',
    status: 'passed',
    evidence: ['npm run qa'],
    blocksPush: true,
  }, ...guardrailsFor('he-verify')],
  guardrailInventory: guardrailInventory(),
  entryGate: entryGateFor('he-verify'),
  next: { target: '/he:ship', ready: true, reason: 'proof clean' },
  steps: [{ id: '1', title: 'Proof passed', status: 'done', receipt: stageReceipt({ stage: 'he-verify', next: 'ready for /he:ship: yes' }) }],
});
assert.equal(result.status, 0, result.stderr);

console.log('he-state-test: pass');
