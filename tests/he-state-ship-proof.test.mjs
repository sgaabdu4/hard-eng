#!/usr/bin/env node
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';

const repo = path.resolve(new URL('..', import.meta.url).pathname);
const script = path.join(repo, 'scripts', 'he-state.mjs');
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'he-state-ship-'));

function validate(state) {
  const file = path.join(tmp, `${Math.random().toString(36).slice(2)}.json`);
  fs.writeFileSync(file, `${JSON.stringify(state, null, 2)}\n`);
  return spawnSync('node', [script, 'validate', file], { encoding: 'utf8' });
}

const templateFile = path.join(tmp, 'template.json');
const templateResult = spawnSync('node', [script, 'template'], { encoding: 'utf8' });
assert.equal(templateResult.status, 0, templateResult.stderr);
fs.writeFileSync(templateFile, templateResult.stdout);
let result = spawnSync('node', [script, 'validate', templateFile], { encoding: 'utf8' });
assert.equal(result.status, 0, result.stderr);

const receipt = {
  stage: 'he-ship',
  state: 'docs/planning/demo/he-state.json',
  decision: 'PASS',
  ownerProof: ['no-mistakes run'],
  artifacts: [],
  blocker: 'none',
  next: 'loop complete: yes',
};
const guardrail = (id, command, evidence) => ({
  id,
  stage: 'he-ship',
  kind: id === 'git-status' ? 'manual' : 'script',
  owner: id,
  command,
  status: 'passed',
  evidence: [evidence],
  blocksPush: true,
});
const base = {
  schema: 'he-state/v1',
  feature: 'ship-proof',
  updatedAt: '2026-06-26T00:00:00.000Z',
  stage: 'he-ship',
  stageIndex: 4,
  status: 'ready',
  currentStep: 'handoff',
  next: { target: 'loop-complete', ready: true, reason: 'ship clean' },
  steps: [{ id: '1', title: 'Ship gate', status: 'done', receipt }],
  subStages: ['status', 'hooks', 'quality-gates', 'no-mistakes', 'ci-or-skip', 'state-update']
    .map((id) => ({ id, title: id, status: 'done', evidence: [id] })),
  findings: [],
  guardrails: [
    guardrail('git-status', 'git status --short', 'clean'),
    guardrail('worktree-ready', 'scripts/ensure-worktree-ready.sh --check --require-pre-push .', 'ready'),
    guardrail('quality-gate', 'node scripts/check-project-quality-gates.mjs --require-push-gate .', 'passed'),
    guardrail('no-mistakes', 'no-mistakes axi run --intent "ship verified feature" --pr 7', 'no-mistakes axi run passed with findings: none'),
  ],
  entryGate: { fromStage: 'he-verify', decision: 'PASS', statePath: 'docs/planning/demo/he-state.json', evidence: ['verify pass'] },
  agentWork: [],
  decisions: [],
  blockers: [],
};

result = validate(base);
assert.equal(result.status, 0, result.stderr);

result = validate({
  ...base,
  guardrails: base.guardrails.map((item) => item.id === 'no-mistakes'
    ? { ...item, command: 'no-mistakes axi', evidence: ['no-mistakes: pass'] }
    : item),
});
assert.notEqual(result.status, 0);
assert.match(result.stderr, /requires passed guardrail no-mistakes/);

console.log('he-state-ship-proof-test: pass');
