#!/usr/bin/env node
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';

const repo = path.resolve(new URL('..', import.meta.url).pathname);
const script = path.join(repo, 'scripts', 'he-state.mjs');
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'he-state-stage-contract-'));
const stages = {
  'he-implement': [2, '/he:verify', 'he-plan', ['owner-read', 'owner-change', 'guardrails', 'state-update']],
  'he-verify': [3, '/he:ship', 'he-implement', ['tests', 'guardrails', 'reviews', 'fix-loop', 'state-update']],
  'he-ship': [4, 'loop-complete', 'he-verify', ['status', 'hooks', 'quality-gates', 'no-mistakes', 'pr-evidence', 'ci-or-skip', 'state-update']],
  'he-learn': [5, 'loop-complete', 'he-ship', ['learning-findings', 'durable-owner', 'proof', 'state-update']],
};

function run(state) {
  const file = path.join(tmp, `${Math.random().toString(36).slice(2)}.json`);
  fs.writeFileSync(file, `${JSON.stringify(state, null, 2)}\n`);
  return spawnSync('node', [script, 'validate', file], { encoding: 'utf8' });
}

const g = (id, stage, command, blocksPush = false) => ({
  id,
  stage,
  kind: 'script',
  owner: id,
  command,
  status: 'passed',
  evidence: [`${id}: pass`],
  blocksPush,
});

function guardrails(stage) {
  if (stage === 'he-implement') {
    return [
      g('deterministic-owner-scan', stage, 'node scripts/find-deterministic-owner.mjs --json --root . owner'),
      g('implementation-proof', stage, 'npm test -- owner'),
    ];
  }
  if (stage === 'he-verify') return [g('quality-gate', stage, 'node scripts/check-project-quality-gates.mjs --require-push-gate .', true)];
  if (stage === 'he-ship') return [
    { ...g('git-status', stage, 'git status --short', true), kind: 'manual' },
    g('worktree-ready', stage, 'scripts/ensure-worktree-ready.sh --check --require-pre-push .', true),
    g('quality-gate', stage, 'node scripts/check-project-quality-gates.mjs --require-push-gate .', true),
    g('no-mistakes', stage, 'no-mistakes axi run --intent "ship verified feature"', true),
  ];
  return [];
}

function state(stage) {
  const [stageIndex, target, fromStage, subStageIds] = stages[stage];
  return {
    schema: 'he-state/v1',
    feature: 'stage-contract',
    updatedAt: '2026-06-26T00:00:00.000Z',
    stage,
    stageIndex,
    status: 'ready',
    currentStep: 'handoff',
    next: { target, ready: true, reason: 'contract proof clean' },
    steps: [{ id: '1', title: 'Stage proof', status: 'done', receipt: { stage, state: 'he-state.json', decision: 'PASS', ownerProof: ['proof'], artifacts: [], blocker: 'none', next: target } }],
    subStages: subStageIds.map((id) => ({ id, title: id, status: 'done', evidence: [id] })),
    findings: stage === 'he-learn' ? [{ id: 'learn-1', stage: 'he-ship', summary: 'Durable guard added', ownerStage: 'he-learn', repairType: 'learning', ownerProof: ['guard'], artifacts: [], status: 'fixed' }] : [],
    guardrails: guardrails(stage),
    entryGate: { fromStage, decision: 'PASS', statePath: 'prior-he-state.json', evidence: [`${fromStage} PASS`] },
    agentWork: [],
    decisions: [],
    blockers: [],
  };
}

let result = run(state('he-implement'));
assert.equal(result.status, 0, result.stderr);

const startedWithoutEntry = state('he-implement');
startedWithoutEntry.status = 'in_progress';
startedWithoutEntry.next.ready = false;
delete startedWithoutEntry.entryGate;
result = run(startedWithoutEntry);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /he-implement requires entryGate from he-plan/);

const noImplementationGuard = state('he-implement');
noImplementationGuard.guardrails = [];
result = run(noImplementationGuard);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /passed guardrail deterministic-owner-scan/);
assert.match(result.stderr, /passed implementation guardrail/);

const badDeterministicScan = state('he-implement');
badDeterministicScan.guardrails = badDeterministicScan.guardrails.map((guardrail) => (
  guardrail.id === 'deterministic-owner-scan'
    ? { ...guardrail, command: 'node scripts/find-deterministic-owner.mjs --root . owner' }
    : guardrail
));
result = run(badDeterministicScan);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /passed guardrail deterministic-owner-scan/);

const pendingGuard = state('he-verify');
pendingGuard.guardrails.push({ ...g('docs-proof', 'he-verify', 'node docs-proof.mjs'), status: 'planned', evidence: [] });
result = run(pendingGuard);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /guardrails are planned, active, failed, or blocked/);

const duplicateSubStage = state('he-verify');
duplicateSubStage.subStages.push({ id: 'tests', title: 'duplicate tests', status: 'pending', evidence: [] });
result = run(duplicateSubStage);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /requires exactly one subStage tests/);

const missingPrEvidence = state('he-ship');
missingPrEvidence.subStages = missingPrEvidence.subStages.filter((item) => item.id !== 'pr-evidence');
result = run(missingPrEvidence);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /requires exactly one subStage pr-evidence/);

const badFindingOwner = state('he-ship');
badFindingOwner.findings = [{ id: 'proof-1', stage: 'he-ship', summary: 'E2E failed', ownerStage: 'he-ship', repairType: 'proof', ownerProof: [], artifacts: [], status: 'open' }];
result = run(badFindingOwner);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /ownerStage must be he-verify for proof/);

const completeNotReady = state('he-verify');
completeNotReady.status = 'complete';
completeNotReady.next.ready = false;
result = run(completeNotReady);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /ready or complete requires next.ready true/);

const blockedWithoutEvidence = state('he-verify');
blockedWithoutEvidence.status = 'blocked';
blockedWithoutEvidence.next.ready = false;
result = run(blockedWithoutEvidence);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /blocked requires a blocking finding or blocker entry/);

console.log('he-state-stage-contract-test: pass');
