#!/usr/bin/env node
import assert from 'node:assert/strict';
import { planReadiness, receipt, run, state } from './helpers/he-state-stage-fixture.mjs';

const missingPlanReadiness = state('he-verify');
delete missingPlanReadiness.planReadiness;

let result = run(missingPlanReadiness);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /requires planReadiness/);

const parkedArtifactAfterPlan = state('he-verify');
parkedArtifactAfterPlan.planReadiness.artifact = { status: 'parked', paths: [] };
result = run(parkedArtifactAfterPlan);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /plan artifact to be accepted or not_required/);

const lavishWithoutUiGrillMe = state('he-verify');
lavishWithoutUiGrillMe.planReadiness.grillMe = {
  required: true,
  status: 'accepted',
  statePath: 'docs/planning/demo/session_state.md',
  questionPolicy: { mode: 'unlimited_until_aligned', evidence: ['asked until aligned'] },
  alignment: { status: 'aligned', userConfirmed: true, noGuesswork: true, openQuestions: [], openUnknowns: [], evidence: ['user confirmed'] },
  stages: [{ id: 'product', map: 'run', status: 'done', evidence: ['session_state.md'] }],
  lastQuestion: { status: 'none', format: 'grill-me/v1', text: '' },
};
lavishWithoutUiGrillMe.planReadiness.uiReview = {
  required: true,
  status: 'accepted',
  liveTool: 'impeccable-live',
  decisionTool: 'lavish',
  decisionPurpose: 'ui_flow',
  localhostUrl: 'http://localhost:4173/demo-ui',
  designSystemEvidence: ['DESIGN.md'],
  sharedComponentEvidence: ['src/components/card.tsx'],
  reviewSurfacePath: 'src/routes/demo-ui.tsx',
  shownToUser: true,
  userResponse: 'A approved',
  tweaks: ['none requested'],
  alignment: { status: 'aligned', userConfirmed: true, noGuesswork: true, openDecisions: [], openUnknowns: [], evidence: ['Lavish accepted'] },
  lavish: {
    decisionStatus: 'accepted',
    launchCommand: 'npx -y lavish-axi docs/planning/demo/mock-flow.html',
    pollCommand: 'npx -y lavish-axi poll docs/planning/demo/mock-flow.html',
    optionsPath: 'docs/planning/demo/ui-options.html',
    pollReceiptPath: 'docs/planning/demo/lavish-poll.md',
    savedChoicesPath: 'docs/planning/demo/ui-decisions.md',
    savedComponentsPath: 'docs/planning/demo/components.md',
    userDecision: 'A approved',
    selectedOption: 'A',
    optionsShown: ['A card-first flow', 'B table-first flow'],
    rejectedOptions: ['B table-first flow'],
    selectedComponents: ['Card'],
    evidence: ['poll returned user decision'],
  },
  evidence: ['docs/planning/demo/lavish-poll.md'],
};
result = run(lavishWithoutUiGrillMe);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /cannot use Lavish unless Grill Me UI flow or visual design ran/);

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

for (const [source, evidence] of [
  ['decisions', 'no workflow miss found in this handoff'],
  ['decisions', 'no user-caught workflow miss found in this handoff'],
  ['blockers', 'no process miss found'],
]) {
  const absenceOnly = state('he-verify');
  absenceOnly[source] = [evidence];
  result = run(absenceOnly);
  assert.equal(result.status, 0, `${source}: ${result.stderr}`);
}

const findingWithAbsenceOnly = state('he-verify');
findingWithAbsenceOnly.findings = [{
  id: 'process-check-1',
  stage: 'he-verify',
  summary: 'no workflow miss',
  ownerStage: 'he-verify',
  repairType: 'proof',
  ownerProof: ['no process miss found'],
  artifacts: [],
  status: 'open',
}];
result = run(findingWithAbsenceOnly);
assert.equal(result.status, 0, result.stderr);

for (const [source, evidence] of [
  ['decisions', 'workflow miss detected where UI approval was skipped'],
  ['decisions', 'process miss found where UI approval was skipped'],
  ['blockers', 'workflow miss recorded where UI approval was skipped'],
]) {
  const positiveMissEvidence = state('he-verify');
  positiveMissEvidence[source] = [evidence];
  result = run(positiveMissEvidence);
  assert.notEqual(result.status, 0, evidence);
  assert.match(result.stderr, /user-caught workflow\/process misses/);
}

const structuredDecisionMiss = state('he-verify');
structuredDecisionMiss.decisions = [{ summary: 'user caught workflow miss where UI approval was skipped' }];
result = run(structuredDecisionMiss);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /user-caught workflow\/process misses/);

const structuredBlockerMiss = state('he-verify');
structuredBlockerMiss.blockers = [{ evidence: ['process miss found where UI approval was skipped'] }];
result = run(structuredBlockerMiss);
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

const structuredDecisionMissWithRepeatRecord = state('he-verify');
structuredDecisionMissWithRepeatRecord.decisions = [{ summary: 'user caught workflow miss where UI approval was skipped' }];
structuredDecisionMissWithRepeatRecord.repeatMisses = [
  { issueClass: 'ui-approval-skip', evidence: ['user caught workflow miss where UI approval was skipped'] },
];
result = run(structuredDecisionMissWithRepeatRecord);
assert.equal(result.status, 0, result.stderr);

for (const evidence of [
  'no user approved skip evidence',
  'user has not approved skip',
  'skip was not approved by user',
  'user explicitly requested not to skip Grill Me',
  'user was not asked; agent approved skip',
  'skip approved by agent after user declined',
]) {
  const negatedSkipApproval = state('he-verify');
  negatedSkipApproval.planReadiness.grillMe = {
    required: false,
    status: 'not_required',
    statePath: '',
    questionPolicy: { mode: 'unlimited_until_aligned', evidence: [] },
    alignment: { status: 'pending', userConfirmed: false, noGuesswork: false, openQuestions: [], openUnknowns: [], evidence: [] },
    stages: [{ id: 'product', map: 'skip', status: 'skipped', reason: evidence, evidence: [evidence] }],
    lastQuestion: { status: 'none', format: 'grill-me/v1', text: '' },
  };
  negatedSkipApproval.planReadiness.artifact = { status: 'accepted', paths: ['docs/planning/demo/plan.md'] };
  result = run(negatedSkipApproval);
  assert.notEqual(result.status, 0, evidence);
  assert.match(result.stderr, /explicit user-approved Grill Me skip evidence/);
}

const reverseUserApprovedGrillMeSkip = state('he-verify');
reverseUserApprovedGrillMeSkip.planReadiness.grillMe = {
  required: false,
  status: 'not_required',
  statePath: '',
  questionPolicy: { mode: 'unlimited_until_aligned', evidence: [] },
  alignment: { status: 'pending', userConfirmed: false, noGuesswork: false, openQuestions: [], openUnknowns: [], evidence: [] },
  stages: [{ id: 'product', map: 'skip', status: 'skipped', reason: 'skip was approved by user in planning', evidence: ['skip approved by user'] }],
  lastQuestion: { status: 'none', format: 'grill-me/v1', text: '' },
};
reverseUserApprovedGrillMeSkip.planReadiness.artifact = { status: 'accepted', paths: ['docs/planning/demo/plan.md'] };
result = run(reverseUserApprovedGrillMeSkip);
assert.equal(result.status, 0, result.stderr);

const agentRecordedUserApproval = state('he-verify');
agentRecordedUserApproval.planReadiness.grillMe = {
  required: false,
  status: 'not_required',
  statePath: '',
  questionPolicy: { mode: 'unlimited_until_aligned', evidence: [] },
  alignment: { status: 'pending', userConfirmed: false, noGuesswork: false, openQuestions: [], openUnknowns: [], evidence: [] },
  stages: [{ id: 'product', map: 'skip', status: 'skipped', reason: 'agent recorded user approval to skip Grill Me', evidence: ['agent recorded user approval to skip Grill Me'] }],
  lastQuestion: { status: 'none', format: 'grill-me/v1', text: '' },
};
agentRecordedUserApproval.planReadiness.artifact = { status: 'accepted', paths: ['docs/planning/demo/plan.md'] };
result = run(agentRecordedUserApproval);
assert.equal(result.status, 0, result.stderr);

const mixedAbsenceAndPositiveMiss = state('he-verify');
mixedAbsenceAndPositiveMiss.decisions = ['no workflow miss found, but user caught workflow miss where UI approval was skipped'];
result = run(mixedAbsenceAndPositiveMiss);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /user-caught workflow\/process misses/);

const mixedAbsenceAndPositiveMissRecorded = state('he-verify');
mixedAbsenceAndPositiveMissRecorded.decisions = ['no workflow miss found, but user caught workflow miss where UI approval was skipped'];
mixedAbsenceAndPositiveMissRecorded.repeatMisses = [
  { issueClass: 'ui-approval-skip', evidence: ['user caught workflow miss where UI approval was skipped'] },
];
result = run(mixedAbsenceAndPositiveMissRecorded);
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
