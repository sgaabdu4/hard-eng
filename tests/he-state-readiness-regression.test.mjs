#!/usr/bin/env node
import assert from 'node:assert/strict';
import { run, state } from './helpers/he-state-stage-fixture.mjs';

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

let result = run(userCaughtMiss);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /user-caught workflow\/process misses/);

const missWithRepeatRecord = state('he-verify');
missWithRepeatRecord.findings = userCaughtMiss.findings;
missWithRepeatRecord.repeatMisses = [
  { issueClass: 'ui-approval-skip', evidence: ['user caught workflow miss where UI approval was skipped'] },
];
result = run(missWithRepeatRecord);
assert.equal(result.status, 0, result.stderr);

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
missWithLearningFinding.findings = [{
  id: 'learn-ui-approval-skip',
  stage: 'he-verify',
  summary: 'user caught workflow miss where UI approval was skipped',
  ownerStage: 'he-learn',
  repairType: 'learning',
  issueClass: 'ui-approval-skip',
  ownerProof: ['tests/he-state-readiness-regression.test.mjs'],
  artifacts: [],
  status: 'open',
}];
result = run(missWithLearningFinding);
assert.equal(result.status, 0, result.stderr);

console.log('he-state-readiness-regression-test: pass');
