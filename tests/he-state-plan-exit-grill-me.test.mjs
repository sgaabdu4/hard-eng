#!/usr/bin/env node
import assert from 'node:assert/strict';
import { run } from './helpers/he-state-stage-fixture.mjs';

const grillQuestion = `Q4: Who can see task comments?

Meaning: Decide whether task comments inherit task visibility or use a smaller comment-only audience.
Why it matters: Backend ACLs and the task detail UI need the same answer before implementation.
Suggested default: A - comments inherit task visibility.

Options:
A) Comments inherit existing task visibility, including assignee, assigner, owner, admins, and delegate-chain users.
B) Only assignee, assigner, and owner can see comments.
C) Not sure - use the default.

Reply: A/B/C, "use default", "not sure", "skip for now", or your own answer.`;

function handoverPrompt(next) {
  return `Start a fresh Hard Eng stage session. Worktree: /tmp/hard-eng-worktree. Command: /he:implement. Stage: he-plan. State: he-state.json. Next: ${next}. Read he-state.json first. Do not use the previous chat transcript.`;
}

function stageReceipt(next = 'ready for /he:implement: no') {
  return {
    stage: 'he-plan',
    state: 'he-state.json',
    decision: 'CONCERNS',
    ownerProof: ['ask Grill Me question about task comment visibility'],
    artifacts: ['he-state.json'],
    blocker: 'Need user answer on who can see task comments',
    next,
    handoverPrompt: handoverPrompt(next),
  };
}

const openAlignment = {
  status: 'pending',
  userConfirmed: false,
  noGuesswork: false,
  openQuestions: ['Who can see task comments?'],
  openUnknowns: ['Whether delegates and admins inherit comment visibility'],
  evidence: [],
};

const aligned = {
  status: 'aligned',
  userConfirmed: true,
  noGuesswork: true,
  openQuestions: [],
  openUnknowns: [],
  evidence: ['user chose inherited task visibility'],
};

const blockedAlignment = {
  status: 'blocked',
  userConfirmed: false,
  noGuesswork: false,
  openQuestions: [],
  openUnknowns: ['Platform owner must provide the tenant ACL matrix'],
  evidence: ['blocked on platform owner ACL matrix before Grill Me can continue'],
};

const openStages = [
  { id: 'product', map: 'run', status: 'in_progress', evidence: [] },
  { id: 'ui-flow', map: 'brief', status: 'pending', evidence: [] },
  { id: 'backend-tech', map: 'run', status: 'pending', evidence: [] },
];

const doneStages = [
  { id: 'product', map: 'run', status: 'done', evidence: ['product scope recorded'] },
  { id: 'ui-flow', map: 'brief', status: 'done', evidence: ['UI flow recorded'] },
  { id: 'backend-tech', map: 'run', status: 'done', evidence: ['backend scope recorded'] },
];

const blockedStages = [
  { id: 'product', map: 'run', status: 'done', evidence: ['product scope recorded'] },
  { id: 'ui-flow', map: 'brief', status: 'blocked', reason: 'platform owner ACL matrix is required before user interview can continue', evidence: ['platform owner ACL request recorded'] },
  { id: 'backend-tech', map: 'run', status: 'blocked', reason: 'backend ACL proof needs platform owner input before user interview can continue', evidence: ['backend ACL proof request recorded'] },
];

function lastQuestion(status, { visibleText = grillQuestion, omitVisibleText = false } = {}) {
  if (status === 'none') return { status, format: 'grill-me/v1', text: '' };
  const question = {
    status,
    format: 'grill-me/v1',
    text: grillQuestion,
  };
  if (!omitVisibleText) question.visibleText = visibleText;
  return question;
}

function blockedPlanWithGrillMe({
  grillMeStatus = 'pending',
  alignment = openAlignment,
  stages = openStages,
  lastQuestionStatus = 'parked',
  visibleText = grillQuestion,
  omitVisibleText = false,
} = {}) {
  return {
    schema: 'he-state/v1',
    feature: 'task-comments',
    updatedAt: '2026-07-05T00:00:00.000Z',
    stage: 'he-plan',
    stageIndex: 1,
    status: 'blocked',
    currentStep: 'ask-grill-me-question',
    next: { target: '/he:implement', ready: false, reason: 'task comment visibility needs user clarification' },
    steps: [{ id: '1', title: 'Ask task comment visibility question', status: 'done', receipt: stageReceipt() }],
    subStages: ['context', 'grill-me', 'owner-proof', 'artifact-choice', 'risk-route', 'learning-capture', 'state-validation'].map((id, index) => ({
      id,
      title: id,
      status: 'done',
      evidence: [`he-plan:${id}`],
      sequence: index + 1,
    })),
    findings: [{
      id: 'comment-visibility-unknown',
      stage: 'he-plan',
      summary: 'Task comment visibility and UI flow need clarification',
      ownerStage: 'he-plan',
      repairType: 'scope',
      ownerProof: ['ask Grill Me question about task comment visibility'],
      artifacts: [],
      status: 'blocked',
      blocking: true,
    }],
    guardrails: [
      { id: 'context-gate', stage: 'he-plan', kind: 'script', owner: 'scripts/check-project-context-gates.mjs', command: 'node scripts/check-project-context-gates.mjs --require-all .', status: 'passed', evidence: ['context-gates: pass'] },
      { id: 'state-validation', stage: 'he-plan', kind: 'script', owner: 'scripts/he-state.mjs', command: 'node scripts/he-state.mjs validate he-state.json', status: 'passed', evidence: ['he-state: pass'] },
    ],
    context: {
      product: { path: 'PRODUCT.md', status: 'current' },
      design: { path: 'DESIGN.md', status: 'current' },
      tokenOwner: { path: 'docs/design/tokens.css', status: 'current' },
    },
    planReadiness: {
      grillMe: {
        required: true,
        status: grillMeStatus,
        statePath: 'docs/planning/task-comments/session_state.md',
        questionPolicy: { mode: 'unlimited_until_aligned', evidence: ['comments touch product/security/UI scope'] },
        alignment,
        stages,
        lastQuestion: lastQuestion(lastQuestionStatus, { visibleText, omitVisibleText }),
      },
      uiReview: {
        required: false,
        status: 'not_required',
        liveTool: '',
        decisionTool: 'none',
        decisionPurpose: 'none',
        localhostUrl: '',
        designSystemEvidence: [],
        sharedComponentEvidence: [],
        reviewSurfacePath: '',
        shownToUser: false,
        userResponse: '',
        tweaks: [],
        evidence: [],
        receipt: null,
      },
      artifact: { status: 'accepted', paths: ['docs/planning/task-comments/plan.md'] },
    },
    agentWork: [],
    decisions: [],
    blockers: ['Need user answer on whether assignee, assigner, owner, delegates, and admins can see task comments'],
  };
}

function terminalBlockedPlan(overrides = {}) {
  const state = blockedPlanWithGrillMe({
    grillMeStatus: 'blocked',
    alignment: blockedAlignment,
    stages: blockedStages,
    lastQuestionStatus: 'none',
    ...overrides,
  });
  state.currentStep = 'record-platform-owner-acl-blocker';
  state.next.reason = 'platform owner ACL matrix blocks Grill Me before any user question is ready';
  state.steps[0].title = 'Record platform owner ACL blocker';
  state.steps[0].receipt.ownerProof = ['record platform owner ACL blocker'];
  state.steps[0].receipt.blocker = 'Platform owner ACL matrix is required before user interview can continue';
  state.findings[0].summary = 'Platform owner ACL matrix blocks Grill Me before user interview can continue';
  state.findings[0].ownerProof = ['record platform owner ACL blocker'];
  state.blockers = ['Platform owner ACL matrix is required before user interview can continue'];
  return state;
}

function skippedGrillMePlan({
  alignment = { status: 'pending', userConfirmed: false, noGuesswork: false, openQuestions: [], openUnknowns: [], evidence: [] },
  stages = [],
  lastQuestionStatus = 'none',
  visibleText = grillQuestion,
  skipEvidence = [],
} = {}) {
  const state = blockedPlanWithGrillMe({
    grillMeStatus: 'not_required',
    alignment,
    stages,
    lastQuestionStatus,
    visibleText,
  });
  state.planReadiness.grillMe = {
    required: false,
    status: 'not_required',
    statePath: '',
    questionPolicy: { mode: 'unlimited_until_aligned', evidence: [] },
    alignment,
    stages,
    evidence: skipEvidence,
    lastQuestion: lastQuestion(lastQuestionStatus, { visibleText }),
  };
  state.planReadiness.artifact = { status: 'not_required', paths: [] };
  return state;
}

let result = run(blockedPlanWithGrillMe({ lastQuestionStatus: 'parked' }));
assert.notEqual(result.status, 0);
assert.match(result.stderr, /must ask the next visible Grill Me question instead of parking concerns/);

result = run(blockedPlanWithGrillMe({ lastQuestionStatus: 'asked' }));
assert.equal(result.status, 0, result.stderr);

const duplicatedQuestionLedger = blockedPlanWithGrillMe({ lastQuestionStatus: 'asked' });
duplicatedQuestionLedger.planReadiness.grillMe.questions = [
  { id: 'Q1', answer: 'A' },
  { id: 'Q2', answer: 'B' },
];
result = run(duplicatedQuestionLedger);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /must not duplicate Grill Me question\/answer history/);

const duplicatedLastQuestionLedger = blockedPlanWithGrillMe({ lastQuestionStatus: 'asked' });
duplicatedLastQuestionLedger.planReadiness.grillMe.lastQuestion.questions = [
  { id: 'Q1', answer: 'A' },
];
duplicatedLastQuestionLedger.planReadiness.grillMe.lastQuestion.answers = ['A'];
result = run(duplicatedLastQuestionLedger);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /must not duplicate Grill Me question\/answer history/);

const duplicatedSingularQuestionLedger = blockedPlanWithGrillMe({ lastQuestionStatus: 'asked' });
duplicatedSingularQuestionLedger.planReadiness.grillMe.items = [
  { question: 'Q1: Who can see task comments?', answer: 'A' },
];
result = run(duplicatedSingularQuestionLedger);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /must not duplicate Grill Me question\/answer history/);

const concernsReceiptReadyYes = blockedPlanWithGrillMe({ lastQuestionStatus: 'asked' });
concernsReceiptReadyYes.steps[0].receipt.next = 'ready for /he:implement: yes';
concernsReceiptReadyYes.steps[0].receipt.handoverPrompt = handoverPrompt('ready for /he:implement: yes');
result = run(concernsReceiptReadyYes);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /CONCERNS or FAIL receipt cannot claim ready for \/he:implement: yes/);

const concernsReceiptHandoverReadyYes = blockedPlanWithGrillMe({ lastQuestionStatus: 'asked' });
concernsReceiptHandoverReadyYes.steps[0].receipt.next = 'ready for implementation: no';
concernsReceiptHandoverReadyYes.steps[0].receipt.handoverPrompt = handoverPrompt('ready for /he:implement: yes');
result = run(concernsReceiptHandoverReadyYes);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /CONCERNS or FAIL receipt cannot claim ready for \/he:implement: yes/);

const concernsReceiptHandoverNegatedReadyYes = blockedPlanWithGrillMe({ lastQuestionStatus: 'asked' });
concernsReceiptHandoverNegatedReadyYes.steps[0].receipt.next = 'ready for implementation: no';
concernsReceiptHandoverNegatedReadyYes.steps[0].receipt.handoverPrompt = `${handoverPrompt('ready for implementation: no')} No blockers. Next: ready for /he:implement: yes.`;
result = run(concernsReceiptHandoverNegatedReadyYes);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /CONCERNS or FAIL receipt cannot claim ready for \/he:implement: yes/);

result = run(blockedPlanWithGrillMe({
  grillMeStatus: 'accepted',
  alignment: openAlignment,
  stages: doneStages,
  lastQuestionStatus: 'none',
}));
assert.notEqual(result.status, 0);
assert.match(result.stderr, /must ask the next visible Grill Me question instead of parking concerns/);

result = run(blockedPlanWithGrillMe({
  grillMeStatus: 'pending',
  alignment: aligned,
  stages: doneStages,
  lastQuestionStatus: 'none',
}));
assert.notEqual(result.status, 0);
assert.match(result.stderr, /must ask the next visible Grill Me question instead of parking concerns/);

result = run(blockedPlanWithGrillMe({
  grillMeStatus: 'accepted',
  alignment: aligned,
  stages: doneStages,
  lastQuestionStatus: 'asked',
  omitVisibleText: true,
}));
assert.notEqual(result.status, 0);
assert.match(result.stderr, /must ask the next visible Grill Me question instead of parking concerns/);

result = run(blockedPlanWithGrillMe({
  grillMeStatus: 'accepted',
  alignment: aligned,
  stages: doneStages,
  lastQuestionStatus: 'none',
}));
assert.notEqual(result.status, 0);
assert.match(result.stderr, /must ask the next visible Grill Me question instead of parking concerns/);

const acceptedGrillMeWithGenericBlocker = blockedPlanWithGrillMe({
  grillMeStatus: 'accepted',
  alignment: aligned,
  stages: doneStages,
  lastQuestionStatus: 'none',
});
acceptedGrillMeWithGenericBlocker.next.reason = 'Task comment visibility blocker';
acceptedGrillMeWithGenericBlocker.steps[0].receipt.blocker = 'Task comment visibility blocker';
acceptedGrillMeWithGenericBlocker.findings[0].summary = 'Task comment visibility blocker';
acceptedGrillMeWithGenericBlocker.blockers = ['Task comment visibility blocker'];
result = run(acceptedGrillMeWithGenericBlocker);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /must ask the next visible Grill Me question instead of parking concerns/);

result = run(terminalBlockedPlan());
assert.equal(result.status, 0, result.stderr);

for (const [label, mutate] of [
  ['state blockers', (state) => { state.blockers = ['Need user answer on who can see task comments']; }],
  ['state decisions', (state) => { state.decisions = ['Need user answer on task comment visibility']; }],
  ['finding summary', (state) => { state.findings[0].summary = 'Need user answer on who can see task comments'; }],
  ['receipt blocker', (state) => { state.steps[0].receipt.blocker = 'Need user answer on who can see task comments'; }],
  ['receipt handover prompt', (state) => { state.steps[0].receipt.handoverPrompt += ' Blocker: Need user answer on task comment visibility.'; }],
]) {
  const state = terminalBlockedPlan();
  mutate(state);
  result = run(state);
  assert.notEqual(result.status, 0, label);
  assert.match(result.stderr, /must ask the next visible Grill Me question instead of parking concerns/);
}

for (const blocker of [
  'User must decide who can see task comments',
  'Who can see task comments?',
  'Can you confirm who can see task comments?',
  'Platform owner ACL matrix blocked; comment visibility needs clarification',
]) {
  const state = terminalBlockedPlan();
  state.blockers = [blocker];
  result = run(state);
  assert.notEqual(result.status, 0, blocker);
  assert.match(result.stderr, /must ask the next visible Grill Me question instead of parking concerns/);
}

result = run(terminalBlockedPlan({
  alignment: { ...blockedAlignment, openUnknowns: ['Which roles can read task comments?'] },
}));
assert.notEqual(result.status, 0);
assert.match(result.stderr, /must ask the next visible Grill Me question instead of parking concerns/);

result = run(terminalBlockedPlan({
  alignment: { ...blockedAlignment, openUnknowns: [] },
  stages: [
    blockedStages[0],
    { id: 'ui-flow', map: 'brief', status: 'blocked', reason: 'Need user answer before planning can continue', evidence: ['Need user answer on task comment visibility'] },
    { id: 'backend-tech', map: 'run', status: 'blocked', reason: 'Need user answer before backend ACL planning can continue', evidence: ['Need user answer on task comment visibility'] },
  ],
}));
assert.notEqual(result.status, 0);
assert.match(result.stderr, /must ask the next visible Grill Me question instead of parking concerns/);

result = run(terminalBlockedPlan({
  alignment: { ...blockedAlignment, openUnknowns: [] },
  stages: [
    blockedStages[0],
    { id: 'ui-flow', map: 'brief', status: 'blocked', reason: 'platform owner ACL matrix is required before user interview can continue', evidence: ['platform owner ACL request recorded'] },
    { id: 'backend-tech', map: 'run', status: 'blocked', reason: 'task comment visibility needs clarification', evidence: ['comment visibility needs clarification'] },
  ],
}));
assert.notEqual(result.status, 0);
assert.match(result.stderr, /must ask the next visible Grill Me question instead of parking concerns/);

result = run(terminalBlockedPlan({
  alignment: { ...blockedAlignment, openUnknowns: [] },
  stages: [
    blockedStages[0],
    { id: 'ui-flow', map: 'brief', status: 'blocked', reason: 'platform owner ACL matrix is required before user interview can continue', evidence: ['platform owner ACL request recorded'] },
    { id: 'backend-tech', map: 'run', status: 'blocked', reason: 'credential sharing needs clarification', evidence: ['credential sharing needs clarification'] },
  ],
}));
assert.notEqual(result.status, 0);
assert.match(result.stderr, /must ask the next visible Grill Me question instead of parking concerns/);

const terminalBlockedWithAmbiguousGrillMeReason = terminalBlockedPlan();
terminalBlockedWithAmbiguousGrillMeReason.planReadiness.grillMe.reason = 'comment visibility needs clarification';
terminalBlockedWithAmbiguousGrillMeReason.planReadiness.grillMe.evidence = ['comment visibility needs clarification'];
result = run(terminalBlockedWithAmbiguousGrillMeReason);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /must ask the next visible Grill Me question instead of parking concerns/);

const terminalBlockedWithMixedGrillMeEvidence = terminalBlockedPlan();
terminalBlockedWithMixedGrillMeEvidence.planReadiness.grillMe.reason = 'platform owner ACL matrix blocks Grill Me';
terminalBlockedWithMixedGrillMeEvidence.planReadiness.grillMe.evidence = ['comment visibility needs clarification'];
result = run(terminalBlockedWithMixedGrillMeEvidence);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /must ask the next visible Grill Me question instead of parking concerns/);

result = run(terminalBlockedPlan({
  alignment: { ...blockedAlignment, openQuestions: ['Can the user pick the task comment visibility model?'] },
}));
assert.notEqual(result.status, 0);
assert.match(result.stderr, /must ask the next visible Grill Me question instead of parking concerns/);

result = run(terminalBlockedPlan({
  stages: [
    blockedStages[0],
    { id: 'ui-flow', map: 'brief', status: 'pending', evidence: [] },
    blockedStages[2],
  ],
}));
assert.notEqual(result.status, 0);
assert.match(result.stderr, /must ask the next visible Grill Me question instead of parking concerns/);

result = run(skippedGrillMePlan());
assert.notEqual(result.status, 0);
assert.match(result.stderr, /must ask the next visible Grill Me question instead of parking concerns/);

const skippedGrillMeWithVisibleQuestion = skippedGrillMePlan({ lastQuestionStatus: 'asked' });
result = run(skippedGrillMeWithVisibleQuestion);
assert.equal(result.status, 0, result.stderr);

const skippedGrillMeWithUserApprovedSkip = skippedGrillMePlan({ skipEvidence: ['user approved skipping Grill Me'] });
result = run(skippedGrillMeWithUserApprovedSkip);
assert.equal(result.status, 0, result.stderr);

const skippedGrillMeWithOpenQuestion = skippedGrillMePlan({
  alignment: {
    status: 'pending',
    userConfirmed: false,
    noGuesswork: false,
    openQuestions: ['Who can see task comments?'],
    openUnknowns: [],
    evidence: [],
  },
});
skippedGrillMeWithOpenQuestion.steps[0].receipt.blocker = 'Platform owner ACL matrix is required before user interview can continue';
skippedGrillMeWithOpenQuestion.findings[0].summary = 'Platform owner ACL matrix blocks Grill Me before user interview can continue';
skippedGrillMeWithOpenQuestion.blockers = ['Platform owner ACL matrix is required before user interview can continue'];
result = run(skippedGrillMeWithOpenQuestion);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /must ask the next visible Grill Me question instead of parking concerns/);

for (const blocker of [
  'Need your answer on who can see task comments',
  'Comment visibility needs clarification',
  'User must decide who can see task comments',
  'Who can see task comments?',
  'Can you confirm who can see task comments?',
  'Platform owner ACL matrix blocked; comment visibility needs clarification',
]) {
  const skippedGrillMeWithAmbiguousBlocker = skippedGrillMePlan();
  skippedGrillMeWithAmbiguousBlocker.next.reason = blocker;
  skippedGrillMeWithAmbiguousBlocker.steps[0].receipt.blocker = blocker;
  skippedGrillMeWithAmbiguousBlocker.findings[0].summary = blocker;
  skippedGrillMeWithAmbiguousBlocker.blockers = [blocker];
  result = run(skippedGrillMeWithAmbiguousBlocker);
  assert.notEqual(result.status, 0, blocker);
  assert.match(result.stderr, /must ask the next visible Grill Me question instead of parking concerns/);
}

const skippedGrillMeWithBlockedUserReason = skippedGrillMePlan();
skippedGrillMeWithBlockedUserReason.next.reason = 'Platform owner ACL matrix is required before user interview can continue';
skippedGrillMeWithBlockedUserReason.steps[0].receipt.blocker = 'Platform owner ACL matrix is required before user interview can continue';
skippedGrillMeWithBlockedUserReason.findings[0].summary = 'Platform owner ACL matrix blocks Grill Me before user interview can continue';
skippedGrillMeWithBlockedUserReason.blockers = ['Platform owner ACL matrix is required before user interview can continue'];
skippedGrillMeWithBlockedUserReason.planReadiness.grillMe.status = 'blocked';
skippedGrillMeWithBlockedUserReason.planReadiness.grillMe.reason = 'Need user answer on who can see task comments';
skippedGrillMeWithBlockedUserReason.planReadiness.grillMe.evidence = ['Need user answer on task comment visibility'];
result = run(skippedGrillMeWithBlockedUserReason);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /must ask the next visible Grill Me question instead of parking concerns/);

const inProgressExitWithoutPlanReadiness = blockedPlanWithGrillMe({ lastQuestionStatus: 'none' });
inProgressExitWithoutPlanReadiness.status = 'in_progress';
inProgressExitWithoutPlanReadiness.steps[0].receipt = stageReceipt('ready for implementation: no');
inProgressExitWithoutPlanReadiness.findings[0].blocking = false;
inProgressExitWithoutPlanReadiness.blockers = [];
delete inProgressExitWithoutPlanReadiness.planReadiness;
result = run(inProgressExitWithoutPlanReadiness);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /he-plan exit requires planReadiness/);

const inProgressExitWithMistypedReceiptStage = blockedPlanWithGrillMe({ lastQuestionStatus: 'none' });
inProgressExitWithMistypedReceiptStage.status = 'in_progress';
inProgressExitWithMistypedReceiptStage.steps[0].receipt = stageReceipt('ready for implementation: no');
inProgressExitWithMistypedReceiptStage.steps[0].receipt.stage = 'he-plna';
inProgressExitWithMistypedReceiptStage.findings[0].blocking = false;
inProgressExitWithMistypedReceiptStage.blockers = [];
delete inProgressExitWithMistypedReceiptStage.planReadiness;
result = run(inProgressExitWithMistypedReceiptStage);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /he-plan exit requires planReadiness/);

const inProgressExitWithMistypedReceiptDecision = blockedPlanWithGrillMe({ lastQuestionStatus: 'none' });
inProgressExitWithMistypedReceiptDecision.status = 'in_progress';
inProgressExitWithMistypedReceiptDecision.steps[0].receipt = stageReceipt('ready for implementation: no');
inProgressExitWithMistypedReceiptDecision.steps[0].receipt.decision = 'CONCERN';
inProgressExitWithMistypedReceiptDecision.findings[0].blocking = false;
inProgressExitWithMistypedReceiptDecision.blockers = [];
delete inProgressExitWithMistypedReceiptDecision.planReadiness;
result = run(inProgressExitWithMistypedReceiptDecision);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /receipt\.decision must be PASS, CONCERNS, or FAIL/);

console.log('he-state-plan-exit-grill-me-test: pass');
