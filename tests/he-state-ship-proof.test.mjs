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
  handoverPrompt: 'Start a fresh Hard Eng stage session. Worktree: /tmp/hard-eng-worktree. Command: loop complete. Stage: he-ship. State: docs/planning/demo/he-state.json. Next: loop complete: yes. Read docs/planning/demo/he-state.json first. Do not use the previous chat transcript.',
};
const guardrail = (id, command, evidence, sequence) => ({
  id,
  stage: 'he-ship',
  kind: id === 'git-status' ? 'manual' : 'script',
  owner: id,
  command,
  status: 'passed',
  evidence: [evidence],
  blocksPush: true,
  sequence,
});
const inventoryIds = ['regex-scanners', 'git-hooks', 'lint-analyze-typecheck', 'ssot-scanners', 'fallow', 'react-doctor', 'repeat-mistake-prevention'];
const guardrailInventory = () => ({
  requiredGuardrails: inventoryIds.map((id) => ({
    id,
    status: 'not_applicable',
    reason: `${id} not touched`,
    evidence: ['guardrail inventory reviewed'],
  })),
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
  subStages: ['status', 'hooks', 'quality-gates', 'no-mistakes', 'pr-evidence', 'pr-review-threads', 'ci-or-skip', 'learning-capture', 'state-update']
    .map((id) => ({ id, title: id, status: 'done', evidence: [id] })),
  findings: [],
  guardrails: [
    guardrail('git-status', 'git status --short', 'clean', 1),
    guardrail('worktree-ready', 'scripts/ensure-worktree-ready.sh --check --require-pre-push .', 'ready', 2),
    guardrail('quality-gate', 'node scripts/check-project-quality-gates.mjs --require-push-gate .', 'passed', 3),
    guardrail('no-mistakes', 'no-mistakes axi run --intent "ship verified feature" --pr 7', 'no-mistakes axi run passed with findings: none', 4),
    guardrail('pr-evidence', 'node integrations/no-mistakes/scripts/repair-pr-evidence.mjs --pr 7 --e2e-video-required --videos https://github.com/user-attachments/assets/video', 'Current head: `abcdef1234567890abcdef1234567890abcdef12`; No open no-mistakes findings; PR screenshots attached; 2x E2E video attached', 5),
    guardrail('pr-review-threads', 'node integrations/no-mistakes/scripts/repair-pr-evidence.mjs --pr 7 --check-review-threads', 'No open GitHub review threads; 5 thread(s) checked', 6),
    guardrail('ci-or-skip', 'gh run view --json conclusion,status', 'CI green', 7),
  ],
  guardrailInventory: guardrailInventory(),
  entryGate: { fromStage: 'he-verify', decision: 'PASS', statePath: 'docs/planning/demo/he-state.json', evidence: ['verify pass'] },
  agentWork: [],
  decisions: [],
  blockers: [],
};

result = validate(base);
assert.equal(result.status, 0, result.stderr);

result = validate({
  ...base,
  guardrails: base.guardrails.map((item) => item.id === 'pr-evidence'
    ? { ...item, evidence: ['Current head: `abcdef1234567890abcdef1234567890abcdef12`; outcome: checks-passed; PR screenshots attached'] }
    : item),
});
assert.equal(result.status, 0, result.stderr);

result = validate({
  ...base,
  guardrails: base.guardrails.map((item) => item.id === 'no-mistakes'
    ? { ...item, command: 'no-mistakes axi', evidence: ['no-mistakes: pass'] }
    : item),
});
assert.notEqual(result.status, 0);
assert.match(result.stderr, /requires passed guardrail no-mistakes/);

result = validate({
  ...base,
  guardrails: base.guardrails.map((item) => item.id === 'no-mistakes'
    ? { ...item, sequence: 6 }
    : item),
});
assert.notEqual(result.status, 0);
assert.match(result.stderr, /requires pr-evidence after latest no-mistakes/);

result = validate({
  ...base,
  subStages: base.subStages.map((item) => item.id === 'pr-evidence'
    ? { ...item, status: 'skipped', reason: 'not needed' }
    : item),
});
assert.notEqual(result.status, 0);
assert.match(result.stderr, /requires subStage pr-evidence to be done, not skipped/);

result = validate({
  ...base,
  guardrails: base.guardrails.filter((item) => item.id !== 'pr-evidence'),
});
assert.notEqual(result.status, 0);
assert.match(result.stderr, /requires passed guardrail pr-evidence/);

result = validate({
  ...base,
  guardrails: base.guardrails.map((item) => item.id === 'pr-evidence'
    ? { ...item, evidence: ['No open no-mistakes findings; PR screenshots attached'] }
    : item),
});
assert.notEqual(result.status, 0);
assert.match(result.stderr, /requires passed guardrail pr-evidence/);

result = validate({
  ...base,
  guardrails: base.guardrails.map((item) => item.id === 'pr-evidence'
    ? { ...item, evidence: ['Current head: `abcdef1234567890abcdef1234567890abcdef12`; PR screenshots attached'] }
    : item),
});
assert.notEqual(result.status, 0);
assert.match(result.stderr, /requires passed guardrail pr-evidence/);

result = validate({
  ...base,
  subStages: base.subStages.map((item) => item.id === 'pr-review-threads'
    ? { ...item, status: 'skipped', reason: 'not needed' }
    : item),
});
assert.notEqual(result.status, 0);
assert.match(result.stderr, /requires subStage pr-review-threads to be done, not skipped/);

result = validate({
  ...base,
  guardrails: base.guardrails.filter((item) => item.id !== 'pr-review-threads'),
});
assert.notEqual(result.status, 0);
assert.match(result.stderr, /requires passed guardrail pr-review-threads/);

result = validate({
  ...base,
  guardrails: base.guardrails.map((item) => item.id === 'pr-review-threads'
    ? { ...item, command: 'node integrations/no-mistakes/scripts/repair-pr-evidence.mjs --pr 7', evidence: ['PR evidence updated'] }
    : item),
});
assert.notEqual(result.status, 0);
assert.match(result.stderr, /requires passed guardrail pr-review-threads/);

result = validate({
  ...base,
  guardrails: base.guardrails.filter((item) => item.id !== 'ci-or-skip'),
});
assert.notEqual(result.status, 0);
assert.match(result.stderr, /requires passed guardrail ci-or-skip/);

console.log('he-state-ship-proof-test: pass');
