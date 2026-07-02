#!/usr/bin/env node
import assert from 'node:assert/strict';
import { run, state } from './helpers/he-state-stage-fixture.mjs';

const base = state('he-verify');

let result = run({
  ...base,
  agentWork: { id: 'bad-shape' },
});
assert.notEqual(result.status, 0);
assert.match(result.stderr, /agentWork must be an array/);

result = run({
  ...base,
  agentWork: [{
    id: 'review-1',
    kind: 'subagent',
    model: 'gpt-5.5',
    purpose: 'independent proof review',
    status: 'done',
    evidence: ['review receipt with final findings'],
  }],
});
assert.equal(result.status, 0, result.stderr);

result = run({
  ...base,
  agentWork: [{
    id: 'review-1',
    kind: 'subagent',
    model: 'gpt-5.5',
    purpose: 'independent proof review',
    status: 'running',
    evidence: [],
  }],
});
assert.notEqual(result.status, 0);
assert.match(result.stderr, /progress is required for running/);
assert.match(result.stderr, /lastProgressAt is required for running/);
assert.match(result.stderr, /recoveryPrompt is required for running/);
assert.match(result.stderr, /agentWork is planned, running, stalled, failed, or blocked/);

result = run({
  ...base,
  agentWork: [{
    id: 'review-1',
    kind: 'subagent',
    model: 'gpt-5.5',
    purpose: 'independent proof review',
    status: 'stalled',
    evidence: ['no update after parent regained control'],
    progress: ['reviewed state validator', 'started route-map check'],
    lastProgressAt: '2026-07-01T12:00:00.000Z',
  }],
});
assert.notEqual(result.status, 0);
assert.match(result.stderr, /recoveryPrompt is required for stalled/);
assert.match(result.stderr, /reason is required for stalled/);

result = run({
  ...base,
  agentWork: [{
    id: 'review-1',
    kind: 'subagent',
    model: 'gpt-5.5',
    purpose: 'independent proof review',
    status: 'stalled',
    reason: 'parent regained control before final receipt',
    evidence: ['no update after parent regained control'],
    progress: ['reviewed state validator', 'started route-map check'],
    lastProgressAt: '2026-07-01T12:00:00.000Z',
    recoveryPrompt: 'Resume independent proof review from he-state.json and report remaining route-map risks.',
  }],
});
assert.notEqual(result.status, 0);
assert.match(result.stderr, /agentWork is planned, running, stalled, failed, or blocked/);

result = run({
  ...base,
  status: 'in_progress',
  next: { target: '/he:ship', ready: false, reason: 'waiting for subagent recovery' },
  agentWork: [{
    id: 'review-1',
    kind: 'subagent',
    model: 'gpt-5.5',
    purpose: 'independent proof review',
    status: 'stalled',
    reason: 'parent regained control before final receipt',
    evidence: ['no update after parent regained control'],
    progress: ['reviewed state validator', 'started route-map check'],
    lastProgressAt: '2026-07-01T12:00:00.000Z',
    recoveryPrompt: 'Resume independent proof review from he-state.json and report remaining route-map risks.',
  }],
});
assert.equal(result.status, 0, result.stderr);

console.log('he-state-agent-work-test: pass');
