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

function clone(value) {
  return JSON.parse(JSON.stringify(value));
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
        alignment: clone(alignment),
        stages: clone(stages),
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

function readyPlanWithAcceptedGrillMe() {
  const state = blockedPlanWithGrillMe({
    grillMeStatus: 'accepted',
    alignment: aligned,
    stages: doneStages,
    lastQuestionStatus: 'none',
  });
  state.status = 'ready';
  state.currentStep = 'handoff';
  state.next = { target: '/he:implement', ready: true, reason: 'planning complete' };
  state.steps[0].receipt.decision = 'PASS';
  state.steps[0].receipt.blocker = 'none';
  state.steps[0].receipt.next = 'ready for /he:implement: yes';
  state.steps[0].receipt.handoverPrompt = handoverPrompt('ready for /he:implement: yes');
  state.findings = [];
  state.blockers = [];
  state.planReadiness.grillMe.stages = state.planReadiness.grillMe.stages.map((stage) => (
    stage.id === 'ui-flow'
      ? { ...stage, map: 'n/a', status: 'skipped', reason: 'UI flow not required', evidence: ['UI flow not required'] }
      : stage
  ));
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

const duplicatedQaHistoryLedger = blockedPlanWithGrillMe({ lastQuestionStatus: 'asked' });
duplicatedQaHistoryLedger.planReadiness.grillMe.qaHistory = [
  { q: 'Q1: Who can see task comments?', a: 'A' },
];
result = run(duplicatedQaHistoryLedger);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /must not duplicate Grill Me question\/answer history/);

const duplicatedPromptReplyLedger = blockedPlanWithGrillMe({ lastQuestionStatus: 'asked' });
duplicatedPromptReplyLedger.planReadiness.grillMe.items = [
  { prompt: 'Q1: Who can see task comments?', reply: 'A' },
];
result = run(duplicatedPromptReplyLedger);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /must not duplicate Grill Me question\/answer history/);

const duplicatedSuffixedQuestionLedger = blockedPlanWithGrillMe({ lastQuestionStatus: 'asked' });
duplicatedSuffixedQuestionLedger.planReadiness.grillMe.items = [
  { questionText: 'Q1: Who can see task comments?', answerText: 'A' },
];
result = run(duplicatedSuffixedQuestionLedger);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /must not duplicate Grill Me question\/answer history/);

const duplicatedTextResponseLedger = blockedPlanWithGrillMe({ lastQuestionStatus: 'asked' });
duplicatedTextResponseLedger.planReadiness.grillMe.lastQuestion.userResponse = 'A';
result = run(duplicatedTextResponseLedger);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /must not duplicate Grill Me question\/answer history/);

const duplicatedVisibleTextResponseLedger = blockedPlanWithGrillMe({ lastQuestionStatus: 'asked' });
duplicatedVisibleTextResponseLedger.planReadiness.grillMe.items = [
  { visibleText: 'Q1: Who can see task comments?', userResponse: 'A' },
];
result = run(duplicatedVisibleTextResponseLedger);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /must not duplicate Grill Me question\/answer history/);

const duplicatedStringQuestionLedger = blockedPlanWithGrillMe({ lastQuestionStatus: 'asked' });
duplicatedStringQuestionLedger.planReadiness.grillMe.items = [
  'Q1: Who can see task comments?',
  'A: Comments inherit task visibility.',
];
result = run(duplicatedStringQuestionLedger);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /must not duplicate Grill Me question\/answer history/);

const duplicatedNumberedStringLedger = blockedPlanWithGrillMe({ lastQuestionStatus: 'asked' });
duplicatedNumberedStringLedger.planReadiness.grillMe.items = [
  'Question 1: Who can see task comments?',
  'Answer 1: Comments inherit task visibility.',
];
result = run(duplicatedNumberedStringLedger);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /must not duplicate Grill Me question\/answer history/);

const duplicatedNumberedSingleStringLedger = blockedPlanWithGrillMe({ lastQuestionStatus: 'asked' });
duplicatedNumberedSingleStringLedger.planReadiness.grillMe.notes = 'Question 1: Who can see task comments?\nAnswer 1: Comments inherit task visibility.';
result = run(duplicatedNumberedSingleStringLedger);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /must not duplicate Grill Me question\/answer history/);

const duplicatedRoleContentLedger = blockedPlanWithGrillMe({ lastQuestionStatus: 'asked' });
duplicatedRoleContentLedger.planReadiness.grillMe.messages = [
  { role: 'assistant', content: 'Q1: Who can see task comments?' },
  { role: 'user', content: 'A: Comments inherit task visibility.' },
];
result = run(duplicatedRoleContentLedger);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /must not duplicate Grill Me question\/answer history/);

for (const key of ['selectedOption', 'selection', 'choice', 'userDecision', 'option', 'selected', 'value']) {
  const duplicatedSelectedOptionLedger = blockedPlanWithGrillMe({ lastQuestionStatus: 'asked' });
  duplicatedSelectedOptionLedger.planReadiness.grillMe.lastQuestion[key] = 'A';
  result = run(duplicatedSelectedOptionLedger);
  assert.notEqual(result.status, 0, key);
  assert.match(result.stderr, /must not duplicate Grill Me question\/answer history/);
}

for (const key of ['chosenOption', 'finalDecision']) {
  const duplicatedCompoundAnswerLedger = blockedPlanWithGrillMe({ lastQuestionStatus: 'asked' });
  duplicatedCompoundAnswerLedger.planReadiness.grillMe.lastQuestion[key] = 'A';
  result = run(duplicatedCompoundAnswerLedger);
  assert.notEqual(result.status, 0, key);
  assert.match(result.stderr, /must not duplicate Grill Me question\/answer history/);
}

const duplicatedSingleStringLedger = blockedPlanWithGrillMe({ lastQuestionStatus: 'asked' });
duplicatedSingleStringLedger.planReadiness.grillMe.notes = 'Q1: Who can see task comments?\nA: Comments inherit task visibility.';
result = run(duplicatedSingleStringLedger);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /must not duplicate Grill Me question\/answer history/);

const duplicatedBareQStringLedger = blockedPlanWithGrillMe({ lastQuestionStatus: 'asked' });
duplicatedBareQStringLedger.planReadiness.grillMe.items = [
  'Q: Who can see task comments?',
  'A: Comments inherit task visibility.',
];
result = run(duplicatedBareQStringLedger);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /must not duplicate Grill Me question\/answer history/);

const duplicatedBareQSingleStringLedger = blockedPlanWithGrillMe({ lastQuestionStatus: 'asked' });
duplicatedBareQSingleStringLedger.planReadiness.grillMe.notes = 'Q: Who can see task comments?\nA: Comments inherit task visibility.';
result = run(duplicatedBareQSingleStringLedger);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /must not duplicate Grill Me question\/answer history/);

const duplicatedAnswerMapLedger = blockedPlanWithGrillMe({ lastQuestionStatus: 'asked' });
duplicatedAnswerMapLedger.planReadiness.grillMe.answersByQuestion = {
  Q1: 'Comments inherit task visibility.',
  Q2: 'Admins inherit task visibility.',
};
result = run(duplicatedAnswerMapLedger);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /must not duplicate Grill Me question\/answer history/);

const duplicatedSkippedAnswerMapLedger = skippedGrillMePlan({
  skipEvidence: ['user approved skipping Grill Me because scope was already fixed'],
});
delete duplicatedSkippedAnswerMapLedger.planReadiness.grillMe.questionPolicy;
duplicatedSkippedAnswerMapLedger.planReadiness.grillMe.answersByQuestion = {
  Q1: 'Comments inherit task visibility.',
};
result = run(duplicatedSkippedAnswerMapLedger);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /must not duplicate Grill Me question\/answer history/);

const duplicatedGenericHistoryLedger = blockedPlanWithGrillMe({ lastQuestionStatus: 'asked' });
duplicatedGenericHistoryLedger.planReadiness.grillMe.historyItems = [
  { id: 'Q1', value: 'Comments inherit task visibility.' },
];
result = run(duplicatedGenericHistoryLedger);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /must not duplicate Grill Me question\/answer history/);

const duplicatedQuestionKeyMapLedger = blockedPlanWithGrillMe({ lastQuestionStatus: 'asked' });
duplicatedQuestionKeyMapLedger.planReadiness.grillMe.metadata = {
  'Who can see task comments?': 'Comments inherit task visibility.',
};
result = run(duplicatedQuestionKeyMapLedger);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /must not duplicate Grill Me question\/answer history/);

const duplicatedNestedQuestionKeyMapLedger = blockedPlanWithGrillMe({ lastQuestionStatus: 'asked' });
duplicatedNestedQuestionKeyMapLedger.planReadiness.grillMe.metadata = {
  'Who can see task comments?': { value: 'Comments inherit task visibility.' },
};
result = run(duplicatedNestedQuestionKeyMapLedger);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /must not duplicate Grill Me question\/answer history/);

const duplicatedAllowedScalarBlockerLedger = blockedPlanWithGrillMe({ lastQuestionStatus: 'asked' });
duplicatedAllowedScalarBlockerLedger.planReadiness.grillMe.blocker = [
  { question: 'Q1: Who can see task comments?', answer: 'Comments inherit task visibility.' },
];
result = run(duplicatedAllowedScalarBlockerLedger);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /must not duplicate Grill Me question\/answer history/);

const duplicatedLastQuestionTextObjectLedger = terminalBlockedPlan();
duplicatedLastQuestionTextObjectLedger.planReadiness.grillMe.lastQuestion.text = {
  Q1: 'Comments inherit task visibility.',
};
result = run(duplicatedLastQuestionTextObjectLedger);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /must not duplicate Grill Me question\/answer history/);

for (const answerMarker of ['Reply', 'Response']) {
  const duplicatedResponseStringLedger = blockedPlanWithGrillMe({ lastQuestionStatus: 'asked' });
  duplicatedResponseStringLedger.planReadiness.grillMe.items = [
    'Question: Who can see task comments?',
    `${answerMarker}: Comments inherit task visibility.`,
  ];
  result = run(duplicatedResponseStringLedger);
  assert.notEqual(result.status, 0, answerMarker);
  assert.match(result.stderr, /must not duplicate Grill Me question\/answer history/);
}

const currentQuestionEvidenceWithOptionLabels = blockedPlanWithGrillMe({ lastQuestionStatus: 'asked' });
currentQuestionEvidenceWithOptionLabels.planReadiness.grillMe.evidence = [grillQuestion];
result = run(currentQuestionEvidenceWithOptionLabels);
assert.equal(result.status, 0, result.stderr);

const duplicatedQuestionHistoryEvidence = blockedPlanWithGrillMe({ lastQuestionStatus: 'asked' });
duplicatedQuestionHistoryEvidence.planReadiness.grillMe.evidence = [
  'Q1: Who can see task comments?',
  'Q2: Should admins see task comments?',
];
result = run(duplicatedQuestionHistoryEvidence);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /must not duplicate Grill Me question\/answer history/);

const duplicatedAnswerOnlyEvidence = blockedPlanWithGrillMe({ lastQuestionStatus: 'asked' });
duplicatedAnswerOnlyEvidence.planReadiness.grillMe.lastQuestion.evidence = ['Answer: Comments inherit task visibility.'];
result = run(duplicatedAnswerOnlyEvidence);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /must not duplicate Grill Me question\/answer history/);

const duplicatedInlineAnswerCurrentQuestion = blockedPlanWithGrillMe({ lastQuestionStatus: 'asked' });
duplicatedInlineAnswerCurrentQuestion.planReadiness.grillMe.lastQuestion.text = `${grillQuestion} Answer: A`;
result = run(duplicatedInlineAnswerCurrentQuestion);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /must not duplicate Grill Me question\/answer history/);

const duplicatedReplyInlineAnswerCurrentQuestion = blockedPlanWithGrillMe({ lastQuestionStatus: 'asked' });
duplicatedReplyInlineAnswerCurrentQuestion.planReadiness.grillMe.lastQuestion.text = `${grillQuestion} Reply: A`;
duplicatedReplyInlineAnswerCurrentQuestion.planReadiness.grillMe.lastQuestion.visibleText = duplicatedReplyInlineAnswerCurrentQuestion.planReadiness.grillMe.lastQuestion.text;
result = run(duplicatedReplyInlineAnswerCurrentQuestion);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /must not duplicate Grill Me question\/answer history/);

const duplicatedSingleLineQaEvidence = blockedPlanWithGrillMe({ lastQuestionStatus: 'asked' });
duplicatedSingleLineQaEvidence.planReadiness.grillMe.evidence = ['Q1: Who can see task comments? A: Comments inherit task visibility.'];
result = run(duplicatedSingleLineQaEvidence);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /must not duplicate Grill Me question\/answer history/);

const duplicatedCompactQaAssignmentEvidence = blockedPlanWithGrillMe({ lastQuestionStatus: 'asked' });
duplicatedCompactQaAssignmentEvidence.planReadiness.grillMe.evidence = ['Q1=A', 'Q2=B'];
result = run(duplicatedCompactQaAssignmentEvidence);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /must not duplicate Grill Me question\/answer history/);

const concernsReceiptReadyYes = blockedPlanWithGrillMe({ lastQuestionStatus: 'asked' });
concernsReceiptReadyYes.steps[0].receipt.next = 'ready for /he:implement: yes';
concernsReceiptReadyYes.steps[0].receipt.handoverPrompt = handoverPrompt('ready for /he:implement: yes');
result = run(concernsReceiptReadyYes);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /CONCERNS or FAIL receipt cannot claim ready for \/he:implement: yes/);

const concernsReceiptImplementReadyYes = blockedPlanWithGrillMe({ lastQuestionStatus: 'asked' });
concernsReceiptImplementReadyYes.steps[0].receipt.next = 'Next: /he:implement ready: yes';
concernsReceiptImplementReadyYes.steps[0].receipt.handoverPrompt = handoverPrompt('/he:implement ready: yes');
result = run(concernsReceiptImplementReadyYes);
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

const concernsReceiptSplitTargetReadyYes = blockedPlanWithGrillMe({ lastQuestionStatus: 'asked' });
concernsReceiptSplitTargetReadyYes.steps[0].receipt.next = 'ready: yes';
concernsReceiptSplitTargetReadyYes.steps[0].receipt.handoverPrompt = handoverPrompt('ready: yes');
result = run(concernsReceiptSplitTargetReadyYes);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /CONCERNS or FAIL receipt cannot claim ready for \/he:implement: yes/);

const concernsReceiptReadinessYes = blockedPlanWithGrillMe({ lastQuestionStatus: 'asked' });
concernsReceiptReadinessYes.steps[0].receipt.next = 'Next: /he:implement readiness: yes';
concernsReceiptReadinessYes.steps[0].receipt.handoverPrompt = handoverPrompt('/he:implement readiness: yes');
result = run(concernsReceiptReadinessYes);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /CONCERNS or FAIL receipt cannot claim ready for \/he:implement: yes/);

const concernsReceiptImplementYes = blockedPlanWithGrillMe({ lastQuestionStatus: 'asked' });
concernsReceiptImplementYes.steps[0].receipt.next = 'Next: /he:implement: yes';
concernsReceiptImplementYes.steps[0].receipt.handoverPrompt = handoverPrompt('/he:implement: yes');
result = run(concernsReceiptImplementYes);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /CONCERNS or FAIL receipt cannot claim ready for \/he:implement: yes/);

const concernsReceiptBareHandoverNextYes = blockedPlanWithGrillMe({ lastQuestionStatus: 'asked' });
concernsReceiptBareHandoverNextYes.steps[0].receipt.next = 'ready for /he:implement: no';
concernsReceiptBareHandoverNextYes.steps[0].receipt.handoverPrompt = handoverPrompt('yes');
result = run(concernsReceiptBareHandoverNextYes);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /CONCERNS or FAIL receipt cannot claim ready for \/he:implement: yes/);

const concernsReceiptUnlabeledImplementNextYes = blockedPlanWithGrillMe({ lastQuestionStatus: 'asked' });
concernsReceiptUnlabeledImplementNextYes.steps[0].receipt.next = 'ready for implementation: no';
concernsReceiptUnlabeledImplementNextYes.steps[0].receipt.handoverPrompt = 'Start a fresh Hard Eng stage session. Worktree: /tmp/hard-eng-worktree. Run /he:implement. Stage: he-plan. State: he-state.json. Next: yes. Read he-state.json first. Do not use the previous chat transcript.';
result = run(concernsReceiptUnlabeledImplementNextYes);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /CONCERNS or FAIL receipt cannot claim ready for \/he:implement: yes/);

const concernsReceiptThenRunImplementNextYes = blockedPlanWithGrillMe({ lastQuestionStatus: 'asked' });
concernsReceiptThenRunImplementNextYes.steps[0].receipt.next = 'ready for implementation: no';
concernsReceiptThenRunImplementNextYes.steps[0].receipt.handoverPrompt = 'Start a fresh Hard Eng stage session. Worktree: /tmp/hard-eng-worktree. Command: /he:plan. Stage: he-plan. State: he-state.json. Then run /he:implement. Next: yes. Read he-state.json first. Do not use the previous chat transcript.';
result = run(concernsReceiptThenRunImplementNextYes);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /CONCERNS or FAIL receipt cannot claim ready for \/he:implement: yes/);

const concernsReceiptEmbeddedThenRunImplementNextYes = blockedPlanWithGrillMe({ lastQuestionStatus: 'asked' });
concernsReceiptEmbeddedThenRunImplementNextYes.steps[0].receipt.next = 'ready for implementation: no';
concernsReceiptEmbeddedThenRunImplementNextYes.steps[0].receipt.handoverPrompt = 'Start a fresh Hard Eng stage session. Worktree: /tmp/hard-eng-worktree. Command: /he:plan. Stage: he-plan. State: he-state.json and then run /he:implement. Next: yes. Read he-state.json first. Do not use the previous chat transcript.';
result = run(concernsReceiptEmbeddedThenRunImplementNextYes);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /CONCERNS or FAIL receipt cannot claim ready for \/he:implement: yes/);

const concernsReceiptCommandToRunNextYes = blockedPlanWithGrillMe({ lastQuestionStatus: 'asked' });
concernsReceiptCommandToRunNextYes.steps[0].receipt.next = 'ready for implementation: no';
concernsReceiptCommandToRunNextYes.steps[0].receipt.handoverPrompt = 'Start a fresh Hard Eng stage session. Worktree: /tmp/hard-eng-worktree. Command to run: /he:implement. Stage: he-plan. State: he-state.json. Next: yes. Read he-state.json first. Do not use the previous chat transcript.';
result = run(concernsReceiptCommandToRunNextYes);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /CONCERNS or FAIL receipt cannot claim ready for \/he:implement: yes/);

const concernsReceiptWhitespaceSeparatedNextYes = blockedPlanWithGrillMe({ lastQuestionStatus: 'asked' });
concernsReceiptWhitespaceSeparatedNextYes.steps[0].receipt.next = 'ready for implementation: no';
concernsReceiptWhitespaceSeparatedNextYes.steps[0].receipt.handoverPrompt = 'Start a fresh Hard Eng stage session. Worktree: /tmp/hard-eng-worktree. Command: /he:implement Stage: he-plan State: he-state.json Next: yes. Read he-state.json first. Do not use the previous chat transcript.';
result = run(concernsReceiptWhitespaceSeparatedNextYes);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /CONCERNS or FAIL receipt cannot claim ready for \/he:implement: yes/);

const concernsReceiptReadTheStateNextYes = blockedPlanWithGrillMe({ lastQuestionStatus: 'asked' });
concernsReceiptReadTheStateNextYes.steps[0].receipt.next = 'ready for implementation: no';
concernsReceiptReadTheStateNextYes.steps[0].receipt.handoverPrompt = 'Start a fresh Hard Eng stage session. Worktree: /tmp/hard-eng-worktree. Command: /he:implement. Stage: he-plan. State: he-state.json. Next: yes. Read the he-state.json first. Do not use the previous chat transcript.';
result = run(concernsReceiptReadTheStateNextYes);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /CONCERNS or FAIL receipt cannot claim ready for \/he:implement: yes/);

const concernsReceiptWithUnrelatedArtifactReady = blockedPlanWithGrillMe({ lastQuestionStatus: 'asked' });
concernsReceiptWithUnrelatedArtifactReady.steps[0].receipt.next = 'ready for /he:implement: no';
concernsReceiptWithUnrelatedArtifactReady.steps[0].receipt.handoverPrompt = `${handoverPrompt('ready for /he:implement: no')} Artifact ready: yes.`;
result = run(concernsReceiptWithUnrelatedArtifactReady);
assert.equal(result.status, 0, result.stderr);

const concernsReceiptWithUnrelatedArtifactsReady = blockedPlanWithGrillMe({ lastQuestionStatus: 'asked' });
concernsReceiptWithUnrelatedArtifactsReady.steps[0].receipt.next = 'ready for /he:implement: no';
concernsReceiptWithUnrelatedArtifactsReady.steps[0].receipt.handoverPrompt = `${handoverPrompt('ready for /he:implement: no')} Artifacts ready: yes.`;
result = run(concernsReceiptWithUnrelatedArtifactsReady);
assert.equal(result.status, 0, result.stderr);

const concernsReceiptWithUnrelatedArtifactReadiness = blockedPlanWithGrillMe({ lastQuestionStatus: 'asked' });
concernsReceiptWithUnrelatedArtifactReadiness.steps[0].receipt.next = 'ready for /he:implement: no';
concernsReceiptWithUnrelatedArtifactReadiness.steps[0].receipt.handoverPrompt = `${handoverPrompt('ready for /he:implement: no')} Artifact readiness: yes.`;
result = run(concernsReceiptWithUnrelatedArtifactReadiness);
assert.equal(result.status, 0, result.stderr);

const concernsReceiptWithPlanReadiness = blockedPlanWithGrillMe({ lastQuestionStatus: 'asked' });
concernsReceiptWithPlanReadiness.steps[0].receipt.next = 'ready for /he:implement: no';
concernsReceiptWithPlanReadiness.steps[0].receipt.handoverPrompt = `${handoverPrompt('ready for /he:implement: no')} Plan readiness: yes.`;
result = run(concernsReceiptWithPlanReadiness);
assert.equal(result.status, 0, result.stderr);

for (const readyLabel of ['Ready', 'Readiness', 'Implementation ready', 'Implement ready']) {
  const concernsReceiptWithReadyLabel = blockedPlanWithGrillMe({ lastQuestionStatus: 'asked' });
  concernsReceiptWithReadyLabel.steps[0].receipt.next = 'ready for /he:implement: no';
  concernsReceiptWithReadyLabel.steps[0].receipt.handoverPrompt = `${handoverPrompt('ready for /he:implement: no')} ${readyLabel}: yes.`;
  result = run(concernsReceiptWithReadyLabel);
  assert.notEqual(result.status, 0, readyLabel);
  assert.match(result.stderr, /CONCERNS or FAIL receipt cannot claim ready for \/he:implement: yes/);
}

for (const readyLabel of ['Ready for /he:implement', 'Readiness for /he:implement']) {
  const concernsReceiptWithReadyForLabel = blockedPlanWithGrillMe({ lastQuestionStatus: 'asked' });
  concernsReceiptWithReadyForLabel.steps[0].receipt.next = 'ready for /he:implement: no';
  concernsReceiptWithReadyForLabel.steps[0].receipt.handoverPrompt = `${handoverPrompt('ready for /he:implement: no')} ${readyLabel}: yes.`;
  result = run(concernsReceiptWithReadyForLabel);
  assert.notEqual(result.status, 0, readyLabel);
  assert.match(result.stderr, /CONCERNS or FAIL receipt cannot claim ready for \/he:implement: yes/);
}

const concernsReceiptMissingReadyNo = blockedPlanWithGrillMe({ lastQuestionStatus: 'asked' });
concernsReceiptMissingReadyNo.steps[0].receipt.next = 'continue planning';
concernsReceiptMissingReadyNo.steps[0].receipt.handoverPrompt = handoverPrompt('continue planning');
result = run(concernsReceiptMissingReadyNo);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /CONCERNS or FAIL receipt targeting \/he:implement must state ready for \/he:implement: no/);

const notReadyPassReceiptReadyYes = terminalBlockedPlan();
notReadyPassReceiptReadyYes.steps[0].receipt.decision = 'PASS';
notReadyPassReceiptReadyYes.steps[0].receipt.next = 'ready for /he:implement: yes';
notReadyPassReceiptReadyYes.steps[0].receipt.handoverPrompt = handoverPrompt('ready for /he:implement: yes');
result = run(notReadyPassReceiptReadyYes);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /not-ready PASS receipt cannot claim ready for \/he:implement: yes/);

const notReadyPassReceiptImplementYes = terminalBlockedPlan();
notReadyPassReceiptImplementYes.steps[0].receipt.decision = 'PASS';
notReadyPassReceiptImplementYes.steps[0].receipt.next = 'Next: /he:implement: yes';
notReadyPassReceiptImplementYes.steps[0].receipt.handoverPrompt = handoverPrompt('/he:implement: yes');
result = run(notReadyPassReceiptImplementYes);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /not-ready PASS receipt cannot claim ready for \/he:implement: yes/);

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

const acceptedGrillMeWithStructuredBlocker = blockedPlanWithGrillMe({
  grillMeStatus: 'accepted',
  alignment: aligned,
  stages: doneStages,
  lastQuestionStatus: 'none',
});
acceptedGrillMeWithStructuredBlocker.steps[0].receipt.blocker = 'Comment visibility';
acceptedGrillMeWithStructuredBlocker.findings[0].summary = 'Comment visibility';
acceptedGrillMeWithStructuredBlocker.blockers = ['Comment visibility'];
result = run(acceptedGrillMeWithStructuredBlocker);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /must ask the next visible Grill Me question instead of parking concerns/);

for (const [label, mutate] of [
  ['planReadiness.grillMe.blocker', (state) => { state.planReadiness.grillMe.blocker = 'Comment visibility'; }],
  ['planReadiness.grillMe.blockers', (state) => { state.planReadiness.grillMe.blockers = ['Comment visibility']; }],
  ['planReadiness.grillMe.alignment.openBlockers', (state) => { state.planReadiness.grillMe.alignment.openBlockers = ['Comment visibility']; }],
  ['planReadiness.grillMe.alignment.blockers', (state) => { state.planReadiness.grillMe.alignment.blockers = ['Comment visibility']; }],
  ['planReadiness.grillMe.alignment.blockedBy', (state) => { state.planReadiness.grillMe.alignment.blockedBy = ['Comment visibility']; }],
]) {
  const acceptedGrillMeWithHiddenMetadataBlocker = blockedPlanWithGrillMe({
    grillMeStatus: 'accepted',
    alignment: aligned,
    stages: doneStages,
    lastQuestionStatus: 'none',
  });
  acceptedGrillMeWithHiddenMetadataBlocker.next.reason = 'Platform owner ACL matrix blocks implementation';
  acceptedGrillMeWithHiddenMetadataBlocker.steps[0].receipt.blocker = 'Platform owner ACL matrix blocks implementation';
  acceptedGrillMeWithHiddenMetadataBlocker.findings[0].summary = 'Platform owner ACL matrix blocks implementation';
  acceptedGrillMeWithHiddenMetadataBlocker.blockers = ['Platform owner ACL matrix blocks implementation'];
  mutate(acceptedGrillMeWithHiddenMetadataBlocker);
  result = run(acceptedGrillMeWithHiddenMetadataBlocker);
  assert.notEqual(result.status, 0, label);
  assert.match(result.stderr, /must ask the next visible Grill Me question instead of parking concerns/);
}

const readyPlanWithGrillMeOpenBlocker = readyPlanWithAcceptedGrillMe();
readyPlanWithGrillMeOpenBlocker.planReadiness.grillMe.alignment.openBlockers = ['Platform owner ACL matrix blocked'];
result = run(readyPlanWithGrillMeOpenBlocker);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /next\.ready true cannot have Grill Me blocker metadata/);

for (const [label, mutate] of [
  ['planReadiness.grillMe.openQuestionCount', (state) => { state.planReadiness.grillMe.openQuestionCount = 1; }],
  ['planReadiness.grillMe.openUnknownCount', (state) => { state.planReadiness.grillMe.openUnknownCount = 1; }],
  ['planReadiness.grillMe.blockerCount', (state) => { state.planReadiness.grillMe.blockerCount = 1; }],
  ['planReadiness.grillMe.alignment.blockerCount', (state) => { state.planReadiness.grillMe.alignment.blockerCount = 1; }],
  ['planReadiness.grillMe.stages[0].openQuestionCount', (state) => { state.planReadiness.grillMe.stages[0].openQuestionCount = 1; }],
  ['planReadiness.grillMe.stages[0].openUnknownCount', (state) => { state.planReadiness.grillMe.stages[0].openUnknownCount = 1; }],
  ['planReadiness.grillMe.stages[0].blockerCount', (state) => { state.planReadiness.grillMe.stages[0].blockerCount = 1; }],
]) {
  const readyPlanWithOpenCount = readyPlanWithAcceptedGrillMe();
  mutate(readyPlanWithOpenCount);
  result = run(readyPlanWithOpenCount);
  assert.notEqual(result.status, 0, label);
  assert.match(result.stderr, /next\.ready true cannot have nonzero Grill Me open question, unknown, or blocker counts/);
}

for (const [label, value] of [
  ['count prose', '1 question'],
  ['count word', 'one'],
  ['nonzero prose', 'non-zero'],
]) {
  const readyPlanWithStringOpenCount = readyPlanWithAcceptedGrillMe();
  readyPlanWithStringOpenCount.planReadiness.grillMe.openQuestionCount = value;
  result = run(readyPlanWithStringOpenCount);
  assert.notEqual(result.status, 0, label);
  assert.match(result.stderr, /next\.ready true cannot have nonzero Grill Me open question, unknown, or blocker counts/);
}

for (const [label, value] of [
  ['zero text', '0 questions'],
  ['zero word', 'zero'],
  ['none text', 'none'],
]) {
  const readyPlanWithZeroStringOpenCount = readyPlanWithAcceptedGrillMe();
  readyPlanWithZeroStringOpenCount.planReadiness.grillMe.openQuestionCount = value;
  result = run(readyPlanWithZeroStringOpenCount);
  assert.equal(result.status, 0, `${label}: ${result.stderr}`);
}

const acceptedExitWithOpenQuestionCount = blockedPlanWithGrillMe({
  grillMeStatus: 'accepted',
  alignment: aligned,
  stages: doneStages,
  lastQuestionStatus: 'none',
});
acceptedExitWithOpenQuestionCount.next.reason = 'Platform owner ACL matrix blocks implementation';
acceptedExitWithOpenQuestionCount.steps[0].receipt.blocker = 'Platform owner ACL matrix blocks implementation';
acceptedExitWithOpenQuestionCount.findings[0].summary = 'Platform owner ACL matrix blocks implementation';
acceptedExitWithOpenQuestionCount.blockers = ['Platform owner ACL matrix blocks implementation'];
acceptedExitWithOpenQuestionCount.planReadiness.grillMe.openQuestionCount = 1;
result = run(acceptedExitWithOpenQuestionCount);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /must ask the next visible Grill Me question instead of parking concerns/);

const acceptedGrillMeWithCustomerPickBlocker = blockedPlanWithGrillMe({
  grillMeStatus: 'accepted',
  alignment: aligned,
  stages: doneStages,
  lastQuestionStatus: 'none',
});
acceptedGrillMeWithCustomerPickBlocker.next.reason = 'Need customer to pick comment visibility';
acceptedGrillMeWithCustomerPickBlocker.steps[0].receipt.blocker = 'Need customer to pick comment visibility';
acceptedGrillMeWithCustomerPickBlocker.findings[0].summary = 'Need customer to pick comment visibility';
acceptedGrillMeWithCustomerPickBlocker.blockers = ['Need customer to pick comment visibility'];
result = run(acceptedGrillMeWithCustomerPickBlocker);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /must ask the next visible Grill Me question instead of parking concerns/);

for (const blocker of [
  'Comment visibility remains unanswered',
  'Comment visibility remains undecided',
  'Comment visibility TBD',
  'Comment visibility not finalized',
  'Comment visibility not decided',
  'Comment visibility not settled',
]) {
  const acceptedGrillMeWithUnresolvedBlocker = blockedPlanWithGrillMe({
    grillMeStatus: 'accepted',
    alignment: aligned,
    stages: doneStages,
    lastQuestionStatus: 'none',
  });
  acceptedGrillMeWithUnresolvedBlocker.next.reason = blocker;
  acceptedGrillMeWithUnresolvedBlocker.steps[0].receipt.blocker = blocker;
  acceptedGrillMeWithUnresolvedBlocker.findings[0].summary = blocker;
  acceptedGrillMeWithUnresolvedBlocker.blockers = [blocker];
  result = run(acceptedGrillMeWithUnresolvedBlocker);
  assert.notEqual(result.status, 0, blocker);
  assert.match(result.stderr, /must ask the next visible Grill Me question instead of parking concerns/);
}

result = run(terminalBlockedPlan());
assert.equal(result.status, 0, result.stderr);

const terminalBlockedWithGenericHandoverTerms = terminalBlockedPlan();
terminalBlockedWithGenericHandoverTerms.steps[0].receipt.handoverPrompt += ' Fresh-session prompt includes blockers, artifacts, and the next command.';
result = run(terminalBlockedWithGenericHandoverTerms);
assert.equal(result.status, 0, result.stderr);

const terminalBlockedWithBlockerArtifactPath = terminalBlockedPlan();
terminalBlockedWithBlockerArtifactPath.steps[0].receipt.ownerProof = ['docs/planning/task-comments/blockers.md'];
terminalBlockedWithBlockerArtifactPath.steps[0].receipt.artifacts = ['docs/planning/task-comments/blockers.md'];
terminalBlockedWithBlockerArtifactPath.findings[0].ownerProof = ['docs/planning/task-comments/blockers.md'];
terminalBlockedWithBlockerArtifactPath.findings[0].artifacts = ['docs/planning/task-comments/blockers.md'];
result = run(terminalBlockedWithBlockerArtifactPath);
assert.equal(result.status, 0, result.stderr);

const terminalBlockedWithDecisionId = terminalBlockedPlan();
terminalBlockedWithDecisionId.decisions = [{
  id: 'comment-visibility-blocker-recorded',
  summary: 'platform owner ACL matrix is required before user interview can continue',
}];
result = run(terminalBlockedWithDecisionId);
assert.equal(result.status, 0, result.stderr);

const terminalBlockedWithDecisionBlockerTopic = terminalBlockedPlan();
terminalBlockedWithDecisionBlockerTopic.decisions = [{
  id: 'comment-visibility',
  summary: 'platform owner ACL matrix is required before user interview can continue',
  blocker: 'Comment visibility',
}];
result = run(terminalBlockedWithDecisionBlockerTopic);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /must ask the next visible Grill Me question instead of parking concerns/);

const terminalBlockedWithResolvedBlockerExplanation = terminalBlockedPlan();
terminalBlockedWithResolvedBlockerExplanation.steps[0].receipt.blocker = 'No blockers; user answered Q4';
result = run(terminalBlockedWithResolvedBlockerExplanation);
assert.equal(result.status, 0, result.stderr);

const terminalBlockedWithResolvedScalarThenTopic = terminalBlockedPlan();
terminalBlockedWithResolvedScalarThenTopic.steps[0].receipt.blocker = 'none; comment visibility';
result = run(terminalBlockedWithResolvedScalarThenTopic);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /must ask the next visible Grill Me question instead of parking concerns/);

const terminalBlockedWithNegatedNextReason = terminalBlockedPlan();
terminalBlockedWithNegatedNextReason.next.reason = 'user did not answer Q4';
result = run(terminalBlockedWithNegatedNextReason);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /must ask the next visible Grill Me question instead of parking concerns/);

const terminalBlockedWithBareUserTopicNextReason = terminalBlockedPlan();
terminalBlockedWithBareUserTopicNextReason.next.reason = 'Comment visibility';
result = run(terminalBlockedWithBareUserTopicNextReason);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /must ask the next visible Grill Me question instead of parking concerns/);

const terminalBlockedWithNegatedResolvedBlocker = terminalBlockedPlan();
terminalBlockedWithNegatedResolvedBlocker.steps[0].receipt.blocker = 'No blockers; customer has not replied';
result = run(terminalBlockedWithNegatedResolvedBlocker);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /must ask the next visible Grill Me question instead of parking concerns/);

const terminalBlockedWithNoCustomerReplyBlocking = terminalBlockedPlan();
terminalBlockedWithNoCustomerReplyBlocking.steps[0].receipt.blocker = 'No customer reply is blocking comment visibility';
result = run(terminalBlockedWithNoCustomerReplyBlocking);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /must ask the next visible Grill Me question instead of parking concerns/);

const terminalBlockedWithNoAnswerFromCustomerBlocking = terminalBlockedPlan();
terminalBlockedWithNoAnswerFromCustomerBlocking.steps[0].receipt.blocker = 'No answer from customer is blocking comment visibility';
result = run(terminalBlockedWithNoAnswerFromCustomerBlocking);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /must ask the next visible Grill Me question instead of parking concerns/);

const terminalBlockedWithNoBlockingIssueTopic = terminalBlockedPlan();
terminalBlockedWithNoBlockingIssueTopic.steps[0].receipt.blocker = 'No blocking issue: comment visibility needs clarification';
result = run(terminalBlockedWithNoBlockingIssueTopic);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /must ask the next visible Grill Me question instead of parking concerns/);

const terminalBlockedWithOwnerVerbBlocker = terminalBlockedPlan();
terminalBlockedWithOwnerVerbBlocker.next.reason = 'Platform owner must decide ACL matrix';
terminalBlockedWithOwnerVerbBlocker.steps[0].receipt.blocker = 'Platform owner must decide ACL matrix';
terminalBlockedWithOwnerVerbBlocker.findings[0].summary = 'Platform owner must decide ACL matrix';
terminalBlockedWithOwnerVerbBlocker.blockers = ['Platform owner must decide ACL matrix'];
result = run(terminalBlockedWithOwnerVerbBlocker);
assert.equal(result.status, 0, result.stderr);

for (const [label, mutate] of [
  ['state blockers', (state) => { state.blockers = ['Need user answer on who can see task comments']; }],
  ['state decisions', (state) => { state.decisions = ['Need user answer on task comment visibility']; }],
  ['structured state decisions', (state) => { state.decisions = [{ id: 'comment-visibility', summary: 'Need user answer on task comment visibility' }]; }],
  ['finding summary', (state) => { state.findings[0].summary = 'Need user answer on who can see task comments'; }],
  ['receipt blocker', (state) => { state.steps[0].receipt.blocker = 'Need user answer on who can see task comments'; }],
  ['receipt handover prompt', (state) => { state.steps[0].receipt.handoverPrompt += ' Blocker: Need user answer on task comment visibility.'; }],
  ['receipt handover blocked label', (state) => { state.steps[0].receipt.handoverPrompt += ' Blocked: comment visibility needs clarification.'; }],
  ['receipt handover blocked on label', (state) => { state.steps[0].receipt.handoverPrompt += ' Blocked on: comment visibility needs clarification.'; }],
  ['receipt handover blocking on label', (state) => { state.steps[0].receipt.handoverPrompt += ' Blocking on: comment visibility needs clarification.'; }],
  ['receipt handover read permission', (state) => { state.steps[0].receipt.handoverPrompt += ' Blocker: Read permissions need clarification.'; }],
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
  'Platform owner ACL matrix blocked plus comment visibility needs clarification',
  'Platform owner ACL matrix blocked with comment visibility needs clarification',
  'Platform owner ACL matrix blocked because comment visibility needs clarification',
  'Platform owner ACL matrix blocked as comment visibility needs clarification',
  'Platform owner must decide ACL matrix so comment visibility needs clarification',
  'Platform owner must decide ACL matrix for comment visibility needs clarification',
  'No blockers except comment visibility',
  'No blockers except comment visibility needs clarification',
  'No blockers: comment visibility',
  'No blockers - comment visibility',
  'No blockers; comment visibility',
  'No blockers. Comment visibility',
  'No blockers - comment visibility needs clarification',
  'No blockers; comment visibility needs clarification',
  'No blockers: comment visibility needs clarification',
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

const terminalBlockedWithEvidencePath = terminalBlockedPlan();
terminalBlockedWithEvidencePath.planReadiness.grillMe.reason = 'platform owner ACL matrix blocks Grill Me';
terminalBlockedWithEvidencePath.planReadiness.grillMe.evidence = ['docs/planning/task-comments/blockers.md'];
result = run(terminalBlockedWithEvidencePath);
assert.equal(result.status, 0, result.stderr);

const terminalBlockedWithEvidenceFilename = terminalBlockedPlan();
terminalBlockedWithEvidenceFilename.planReadiness.grillMe.reason = 'platform owner ACL matrix blocks Grill Me';
terminalBlockedWithEvidenceFilename.planReadiness.grillMe.evidence = ['blockers.md#acl'];
result = run(terminalBlockedWithEvidenceFilename);
assert.equal(result.status, 0, result.stderr);

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

const inProgressExitWithBareTopicNextReason = blockedPlanWithGrillMe({
  grillMeStatus: 'accepted',
  alignment: aligned,
  stages: doneStages,
  lastQuestionStatus: 'none',
});
inProgressExitWithBareTopicNextReason.status = 'in_progress';
inProgressExitWithBareTopicNextReason.next = { target: '/he:implement', ready: false, reason: 'Comment visibility' };
inProgressExitWithBareTopicNextReason.steps[0].receipt = {
  ...stageReceipt('ready for /he:implement: no'),
  blocker: 'none',
};
inProgressExitWithBareTopicNextReason.findings = [];
inProgressExitWithBareTopicNextReason.blockers = [];
result = run(inProgressExitWithBareTopicNextReason);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /must ask the next visible Grill Me question instead of parking concerns/);

const inProgressInternalReceiptWithoutPlanReadiness = blockedPlanWithGrillMe({ lastQuestionStatus: 'none' });
inProgressInternalReceiptWithoutPlanReadiness.status = 'in_progress';
inProgressInternalReceiptWithoutPlanReadiness.next = { target: '/he:implement', ready: false, reason: 'still planning' };
inProgressInternalReceiptWithoutPlanReadiness.steps[0].receipt = {
  ...stageReceipt('continue planning'),
  handoverPrompt: 'Start a fresh Hard Eng stage session. Worktree: /tmp/hard-eng-worktree. Command: /he:plan. Stage: he-plan. State: he-state.json. Next: continue planning. Read he-state.json first. Do not use the previous chat transcript.',
};
inProgressInternalReceiptWithoutPlanReadiness.findings[0].blocking = false;
inProgressInternalReceiptWithoutPlanReadiness.blockers = [];
delete inProgressInternalReceiptWithoutPlanReadiness.planReadiness;
result = run(inProgressInternalReceiptWithoutPlanReadiness);
assert.equal(result.status, 0, result.stderr);

const inProgressInternalReceiptWithNegatedImplementMention = blockedPlanWithGrillMe({ lastQuestionStatus: 'none' });
inProgressInternalReceiptWithNegatedImplementMention.status = 'in_progress';
inProgressInternalReceiptWithNegatedImplementMention.next = { target: '/he:implement', ready: false, reason: 'still planning' };
inProgressInternalReceiptWithNegatedImplementMention.steps[0].receipt = {
  ...stageReceipt('continue planning'),
  handoverPrompt: 'Start a fresh Hard Eng stage session. Worktree: /tmp/hard-eng-worktree. Command: /he:plan. Stage: he-plan. State: he-state.json. Next: continue planning. Do not run /he:implement yet. Read he-state.json first. Do not use the previous chat transcript.',
};
inProgressInternalReceiptWithNegatedImplementMention.findings[0].blocking = false;
inProgressInternalReceiptWithNegatedImplementMention.blockers = [];
delete inProgressInternalReceiptWithNegatedImplementMention.planReadiness;
result = run(inProgressInternalReceiptWithNegatedImplementMention);
assert.equal(result.status, 0, result.stderr);

const inProgressInternalReceiptWithBareNoImplementMention = blockedPlanWithGrillMe({ lastQuestionStatus: 'none' });
inProgressInternalReceiptWithBareNoImplementMention.status = 'in_progress';
inProgressInternalReceiptWithBareNoImplementMention.next = { target: '/he:implement', ready: false, reason: 'still planning' };
inProgressInternalReceiptWithBareNoImplementMention.steps[0].receipt = {
  ...stageReceipt('continue planning'),
  handoverPrompt: 'Start a fresh Hard Eng stage session. Worktree: /tmp/hard-eng-worktree. Command: /he:plan. No /he:implement. Stage: he-plan. State: he-state.json. Next: continue planning. Read he-state.json first. Do not use the previous chat transcript.',
};
inProgressInternalReceiptWithBareNoImplementMention.findings[0].blocking = false;
inProgressInternalReceiptWithBareNoImplementMention.blockers = [];
delete inProgressInternalReceiptWithBareNoImplementMention.planReadiness;
result = run(inProgressInternalReceiptWithBareNoImplementMention);
assert.equal(result.status, 0, result.stderr);

console.log('he-state-plan-exit-grill-me-test: pass');
