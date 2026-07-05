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

function blockedPlanWithGrillMe(lastQuestionStatus) {
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
        status: 'pending',
        statePath: 'docs/planning/task-comments/session_state.md',
        questionPolicy: { mode: 'unlimited_until_aligned', evidence: ['comments touch product/security/UI scope'] },
        alignment: {
          status: 'pending',
          userConfirmed: false,
          noGuesswork: false,
          openQuestions: ['Who can see task comments?'],
          openUnknowns: ['Whether delegates and admins inherit comment visibility'],
          evidence: [],
        },
        stages: [
          { id: 'product', map: 'run', status: 'in_progress', evidence: [] },
          { id: 'ui-flow', map: 'brief', status: 'pending', evidence: [] },
          { id: 'backend-tech', map: 'run', status: 'pending', evidence: [] },
        ],
        lastQuestion: {
          status: lastQuestionStatus,
          format: 'grill-me/v1',
          text: grillQuestion,
          visibleText: grillQuestion,
        },
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

function clone(value) {
  return JSON.parse(JSON.stringify(value));
}

let result = run(blockedPlanWithGrillMe('parked'));
assert.notEqual(result.status, 0);
assert.match(result.stderr, /must ask the next visible Grill Me question instead of parking concerns/);

result = run(blockedPlanWithGrillMe('asked'));
assert.equal(result.status, 0, result.stderr);

const duplicatedQuestionLedger = blockedPlanWithGrillMe('asked');
duplicatedQuestionLedger.planReadiness.grillMe.questions = [
  { id: 'Q1', answer: 'A' },
  { id: 'Q2', answer: 'B' },
];
result = run(duplicatedQuestionLedger);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /must not duplicate Grill Me question\/answer history/);

const nonPassReadyYes = blockedPlanWithGrillMe('asked');
nonPassReadyYes.steps[0].receipt.next = 'ready for /he:implement: no';
nonPassReadyYes.steps[0].receipt.handoverPrompt = handoverPrompt('ready for /he:implement: yes');
result = run(nonPassReadyYes);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /CONCERNS\/FAIL exit cannot claim ready for \/he:implement: yes/);

const mixedBlocker = blockedPlanWithGrillMe('none');
mixedBlocker.planReadiness.grillMe.status = 'blocked';
mixedBlocker.planReadiness.grillMe.alignment = {
  status: 'blocked',
  userConfirmed: false,
  noGuesswork: false,
  openQuestions: [],
  openUnknowns: [],
  evidence: ['blocked before alignment'],
};
mixedBlocker.planReadiness.grillMe.stages = [
  {
    id: 'backend-tech',
    map: 'run',
    status: 'blocked',
    reason: 'Platform owner ACL matrix blocked',
    evidence: ['platform owner ACL matrix blocked'],
  },
];
mixedBlocker.planReadiness.grillMe.lastQuestion = { status: 'none', format: 'grill-me/v1', text: '' };
mixedBlocker.blockers = ['Platform owner ACL matrix blocked; comment visibility needs clarification'];
mixedBlocker.findings[0].summary = 'Platform owner ACL matrix blocked; comment visibility needs clarification';
result = run(mixedBlocker);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /must ask the next visible Grill Me question instead of parking concerns/);

const terminalNonUserBlocker = clone(mixedBlocker);
terminalNonUserBlocker.blockers = ['Platform owner ACL matrix blocked'];
terminalNonUserBlocker.findings[0].summary = 'Platform owner ACL matrix blocked';
terminalNonUserBlocker.steps[0].receipt.blocker = 'Platform owner ACL matrix blocked';
terminalNonUserBlocker.next.reason = 'platform owner ACL matrix blocked';
result = run(terminalNonUserBlocker);
assert.equal(result.status, 0, result.stderr);

const skippedWithUserQuestion = blockedPlanWithGrillMe('none');
skippedWithUserQuestion.planReadiness.grillMe = {
  required: false,
  status: 'not_required',
  statePath: '',
  questionPolicy: { mode: 'unlimited_until_aligned', evidence: [] },
  alignment: { status: 'pending', userConfirmed: false, noGuesswork: false, openQuestions: [], openUnknowns: [], evidence: [] },
  stages: [],
  lastQuestion: { status: 'none', format: 'grill-me/v1', text: '' },
};
skippedWithUserQuestion.blockers = ['Can you confirm who can see task comments?'];
result = run(skippedWithUserQuestion);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /must ask the next visible Grill Me question instead of parking concerns/);

console.log('he-state-plan-exit-grill-me-test: pass');
