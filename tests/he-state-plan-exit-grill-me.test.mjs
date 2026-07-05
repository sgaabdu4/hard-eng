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

let result = run(blockedPlanWithGrillMe({ lastQuestionStatus: 'parked' }));
assert.notEqual(result.status, 0);
assert.match(result.stderr, /must ask the next visible Grill Me question instead of parking concerns/);

result = run(blockedPlanWithGrillMe({ lastQuestionStatus: 'asked' }));
assert.equal(result.status, 0, result.stderr);

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

console.log('he-state-plan-exit-grill-me-test: pass');
