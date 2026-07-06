#!/usr/bin/env node
import assert from 'node:assert/strict';
import { run } from './helpers/he-state-stage-fixture.mjs';

const grillQuestion = 'Who can see task comments?';

function lastQuestion(status) {
  return status === 'none'
    ? { status, format: 'grill-me/v1', text: '' }
    : { status, format: 'grill-me/v1', text: grillQuestion, visibleText: grillQuestion };
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
    handoverPrompt: `Start a fresh Hard Eng stage session. Command: /he:implement. Stage: he-plan. State: he-state.json. Next: ${next}.`,
  };
}

function blockedPlanWithGrillMe({ grillMeStatus = 'pending', alignment, stages, lastQuestionStatus = 'asked' } = {}) {
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
      status: index === 1 ? 'blocked' : 'done',
      evidence: index === 1 ? [] : [`${id} complete`],
    })),
    context: { product: { status: 'unchanged', evidence: ['PRODUCT.md read'] } },
    findings: [{
      id: 'grill-me-comment-visibility',
      severity: 'blocking',
      blocking: true,
      summary: 'Need user answer on who can see task comments',
      ownerStage: 'he-plan',
      ownerProof: ['ask visible Grill Me question'],
    }],
    planReadiness: {
      owner: { status: 'accepted', proof: ['planner owns task comment scope'] },
      artifact: { status: 'accepted', paths: ['docs/planning/task-comments/plan.md'] },
      uiReview: { required: false, status: 'not_required' },
      grillMe: {
        required: true,
        status: grillMeStatus,
        statePath: 'docs/planning/task-comments/session_state.md',
        questionPolicy: { mode: 'unlimited_until_aligned', evidence: ['Grill Me skill requires unlimited questions until aligned'] },
        alignment: alignment || {
          status: 'pending',
          userConfirmed: false,
          noGuesswork: false,
          openQuestions: ['Who can see task comments?'],
          openUnknowns: ['Whether delegates and admins inherit comment visibility'],
          evidence: [],
        },
        stages: stages || [
          { id: 'product', map: 'run', status: 'in_progress', evidence: [] },
          { id: 'ui-flow', map: 'brief', status: 'pending', evidence: [] },
        ],
        lastQuestion: lastQuestion(lastQuestionStatus),
      },
    },
    agentWork: [],
    decisions: [],
    blockers: ['Need user answer on who can see task comments'],
  };
}

function terminalBlockedPlan() {
  const state = blockedPlanWithGrillMe({
    grillMeStatus: 'blocked',
    alignment: {
      status: 'blocked',
      userConfirmed: false,
      noGuesswork: false,
      openQuestions: [],
      openUnknowns: ['Platform owner must provide the tenant ACL matrix'],
      evidence: ['blocked on platform owner ACL matrix before Grill Me can continue'],
    },
    stages: [
      { id: 'product', map: 'run', status: 'done', evidence: ['product scope recorded'] },
      { id: 'ui-flow', map: 'brief', status: 'blocked', reason: 'platform owner ACL matrix is required before user interview can continue', evidence: ['platform owner ACL request recorded'] },
    ],
    lastQuestionStatus: 'none',
  });
  state.currentStep = 'record-platform-owner-acl-blocker';
  state.next.reason = 'platform owner ACL matrix blocks Grill Me before any user question is ready';
  state.steps[0].receipt.blocker = 'Platform owner ACL matrix is required before user interview can continue';
  state.findings[0].summary = 'Platform owner ACL matrix blocks Grill Me before user interview can continue';
  state.blockers = ['Platform owner ACL matrix is required before user interview can continue'];
  return state;
}

function skippedGrillMePlan() {
  const state = blockedPlanWithGrillMe({ lastQuestionStatus: 'none' });
  state.planReadiness.grillMe = {
    required: false,
    status: 'not_required',
    statePath: '',
    questionPolicy: { mode: 'unlimited_until_aligned', evidence: [] },
    alignment: { status: 'pending', userConfirmed: false, noGuesswork: false, openQuestions: [], openUnknowns: [], evidence: [] },
    stages: [],
    evidence: ['user approved skipping Grill Me'],
    lastQuestion: lastQuestion('none'),
  };
  state.planReadiness.artifact = { status: 'not_required', paths: [] };
  return state;
}

let state = blockedPlanWithGrillMe({ lastQuestionStatus: 'asked' });
state.steps[0].receipt.next = '/he:implement: no blockers';
state.steps[0].receipt.handoverPrompt = stageReceipt('/he:implement: no blockers').handoverPrompt;
let result = run(state);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /CONCERNS or FAIL receipt targeting \/he:implement must state ready for \/he:implement: no/);

for (const [label, staleState] of [
  ['blocked', terminalBlockedPlan()],
  ['not-required', skippedGrillMePlan()],
]) {
  staleState.planReadiness.grillMe.lastQuestion.text = grillQuestion;
  staleState.planReadiness.grillMe.lastQuestion.visibleText = grillQuestion;
  staleState.planReadiness.grillMe.lastQuestion.evidence = [grillQuestion];
  result = run(staleState);
  assert.notEqual(result.status, 0, label);
  assert.match(result.stderr, /must not duplicate Grill Me question\/answer history/);
}

console.log('he-state-plan-exit-grill-me-behavior-test: pass');
