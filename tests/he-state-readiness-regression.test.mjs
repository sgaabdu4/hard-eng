#!/usr/bin/env node
import assert from 'node:assert/strict';
import { planReadiness, receipt, run, state } from './helpers/he-state-stage-fixture.mjs';

const missingPlanReadiness = state('he-verify');
delete missingPlanReadiness.planReadiness;

let result = run(missingPlanReadiness);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /requires planReadiness/);

const pendingRequiredGrillMe = state('he-verify');
pendingRequiredGrillMe.planReadiness = planReadiness();
pendingRequiredGrillMe.planReadiness.grillMe = {
  required: true,
  status: 'pending',
  statePath: 'docs/planning/demo/session_state.md',
  questionPolicy: { mode: 'unlimited_until_aligned', evidence: ['question policy recorded'] },
  alignment: { status: 'pending', userConfirmed: false, noGuesswork: false, openQuestions: ['Need scope'], openUnknowns: [], evidence: [] },
  stages: [{ id: 'product', map: 'run', status: 'in_progress', evidence: [] }],
  lastQuestion: { status: 'asked', format: 'grill-me/v1', text: 'Q1: Need scope?' },
};
result = run(pendingRequiredGrillMe);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /requires required Grill Me to be accepted/);
assert.match(result.stderr, /aligned with no open questions or unknowns/);

const userCaughtMiss = state('he-verify');
userCaughtMiss.findings = [{
  id: 'process-miss-1',
  stage: 'he-verify',
  summary: 'user caught workflow miss where UI approval was skipped',
  ownerStage: 'he-verify',
  repairType: 'proof',
  ownerProof: ['user caught workflow miss'],
  artifacts: [],
  status: 'open',
}];

result = run(userCaughtMiss);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /user-caught workflow\/process misses/);

const missWithUnrelatedRepeatRecord = state('he-verify');
missWithUnrelatedRepeatRecord.findings = userCaughtMiss.findings;
missWithUnrelatedRepeatRecord.repeatMisses = [
  { issueClass: 'auth-owner', evidence: ['user caught auth owner miss'] },
];
result = run(missWithUnrelatedRepeatRecord);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /user-caught workflow\/process misses/);

const missWithRepeatRecord = state('he-verify');
missWithRepeatRecord.findings = userCaughtMiss.findings;
missWithRepeatRecord.repeatMisses = [
  { issueClass: 'ui-approval-skip', evidence: ['user caught workflow miss where UI approval was skipped'] },
];
result = run(missWithRepeatRecord);
assert.equal(result.status, 0, result.stderr);

const missWithRepeatIssueClass = state('he-verify');
missWithRepeatIssueClass.findings = [{
  ...userCaughtMiss.findings[0],
  issueClass: 'ui-approval-skip',
  summary: 'user caught workflow miss',
}];
missWithRepeatIssueClass.repeatMisses = [
  { issueClass: 'ui approval skip', evidence: ['captured from review feedback'] },
];
result = run(missWithRepeatIssueClass);
assert.equal(result.status, 0, result.stderr);

const missWithUnrelatedLearningFinding = state('he-ship');
missWithUnrelatedLearningFinding.next = { target: '/he:learn', ready: true, reason: 'learning finding open' };
missWithUnrelatedLearningFinding.steps = [{ id: '1', title: 'Gate passed', status: 'done', receipt: receipt('he-ship', 'ready for /he:learn: yes') }];
missWithUnrelatedLearningFinding.findings = [
  userCaughtMiss.findings[0],
  {
    id: 'learn-auth-owner',
    stage: 'he-verify',
    summary: 'auth owner repeated and needs durable guard',
    ownerStage: 'he-learn',
    repairType: 'learning',
    issueClass: 'auth-owner',
    ownerProof: ['tests/auth-owner.test.mjs'],
    artifacts: [],
    status: 'open',
  },
];
result = run(missWithUnrelatedLearningFinding);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /user-caught workflow\/process misses/);

const missWithLearningFinding = state('he-ship');
missWithLearningFinding.next = { target: '/he:learn', ready: true, reason: 'learning finding open' };
missWithLearningFinding.steps = [{
  id: '1',
  title: 'Gate passed',
  status: 'done',
  receipt: {
    stage: 'he-ship',
    state: 'he-state.json',
    decision: 'PASS',
    ownerProof: ['proof'],
    artifacts: [],
    blocker: 'none',
    next: 'ready for /he:learn: yes',
    handoverPrompt: 'Start a fresh Hard Eng stage session. Worktree: /tmp/hard-eng-worktree. Command: /he:learn. Stage: he-ship. State: he-state.json. Next: ready for /he:learn: yes. Read he-state.json first. Do not use the previous chat transcript.',
  },
}];
missWithLearningFinding.findings = [
  userCaughtMiss.findings[0],
  {
    id: 'learn-ui-approval-skip',
    stage: 'he-verify',
    summary: 'UI approval skip needs durable guard',
    ownerStage: 'he-learn',
    repairType: 'learning',
    issueClass: 'ui-approval-skip',
    ownerProof: ['user caught workflow miss where UI approval was skipped'],
    artifacts: [],
    status: 'open',
  },
];
result = run(missWithLearningFinding);
assert.equal(result.status, 0, result.stderr);

for (const [status, repairType] of [['fixed', 'learning'], ['accepted', 'process']]) {
  const learnCompleteRecordedMiss = state('he-learn');
  learnCompleteRecordedMiss.findings = [{
    id: `learn-ui-approval-skip-${status}`,
    stage: 'he-ship',
    summary: 'user caught workflow miss and durable guard was recorded',
    ownerStage: 'he-learn',
    repairType,
    issueClass: 'ui-approval-skip',
    ownerProof: ['tests/he-state-readiness-regression.test.mjs'],
    artifacts: [],
    status,
  }];
  learnCompleteRecordedMiss.decisions = ['user caught workflow miss where UI approval was skipped before he-learn completed'];
  learnCompleteRecordedMiss.steps = [{ id: '1', title: 'Learning passed', status: 'done', receipt: receipt('he-learn', 'loop complete: yes') }];
  result = run(learnCompleteRecordedMiss);
  assert.equal(result.status, 0, `${status}: ${result.stderr}`);
}

console.log('he-state-readiness-regression-test: pass');
