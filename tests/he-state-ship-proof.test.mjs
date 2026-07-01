#!/usr/bin/env node
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { planReadiness } from './helpers/he-state-stage-fixture.mjs';

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
  touchedStacks: ['workflow-state'],
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
    guardrail('ship-currentness', 'git rev-parse HEAD && git status --short', 'validated head: `abcdef1234567890abcdef1234567890abcdef12`; worktree clean after final proof', 8),
  ],
  guardrailInventory: guardrailInventory(),
  entryGate: { fromStage: 'he-verify', decision: 'PASS', statePath: 'docs/planning/demo/he-state.json', evidence: ['verify pass'] },
  planReadiness: planReadiness(),
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
  guardrails: base.guardrails.map((item) => item.id === 'ship-currentness'
    ? { ...item, evidence: ['validated head: `abcdef1234567890abcdef1234567890abcdef12`; git status --short no output; working tree unchanged'] }
    : item),
});
assert.equal(result.status, 0, result.stderr);

result = validate({
  ...base,
  guardrails: base.guardrails.map((item) => item.id === 'ship-currentness'
    ? { ...item, evidence: ['validated head: `abcdef1234567890abcdef1234567890abcdef12`; no staged, unstaged, or untracked changes; worktree clean'] }
    : item),
});
assert.equal(result.status, 0, result.stderr);

result = validate({
  ...base,
  guardrails: base.guardrails.map((item) => item.id === 'ship-currentness'
    ? { ...item, evidence: ['validated head: `abcdef1234567890abcdef1234567890abcdef12`; worktree has no changes; worktree clean'] }
    : item),
});
assert.equal(result.status, 0, result.stderr);

result = validate({
  ...base,
  guardrails: base.guardrails.map((item) => item.id === 'ship-currentness'
    ? { ...item, evidence: ['validated head: `abcdef1234567890abcdef1234567890abcdef12`; worktree is not only clean but unchanged'] }
    : item),
});
assert.equal(result.status, 0, result.stderr);

result = validate({
  ...base,
  guardrails: base.guardrails.map((item) => item.id === 'ship-currentness'
    ? { ...item, evidence: ['validated head: `abcdef1234567890abcdef1234567890abcdef12`; no changes in worktree; worktree clean'] }
    : item),
});
assert.equal(result.status, 0, result.stderr);

result = validate({
  ...base,
  guardrails: base.guardrails.map((item) => item.id === 'ship-currentness'
    ? { ...item, evidence: ['validated head: `abcdef1234567890abcdef1234567890abcdef12`; no staged changes, untracked files; worktree clean'] }
    : item),
});
assert.notEqual(result.status, 0);
assert.match(result.stderr, /clean worktree evidence/);

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

result = validate({
  ...base,
  guardrails: base.guardrails.filter((item) => item.id !== 'ship-currentness'),
});
assert.notEqual(result.status, 0);
assert.match(result.stderr, /requires ship-currentness after final proof/);

result = validate({
  ...base,
  guardrails: base.guardrails.map((item) => item.id === 'ship-currentness'
    ? { ...item, command: 'node scripts/he-state.mjs validate he-state.json' }
    : item),
});
assert.notEqual(result.status, 0);
assert.match(result.stderr, /requires ship-currentness after final proof/);

result = validate({
  ...base,
  guardrails: base.guardrails.map((item) => item.id === 'ship-currentness'
    ? { ...item, command: 'git rev-parse HEAD # && git status --short' }
    : item),
});
assert.notEqual(result.status, 0);
assert.match(result.stderr, /requires ship-currentness after final proof/);

for (const command of [
  'git rev-parse HEAD && false && git status --short',
  'git rev-parse HEAD && false || git status --short',
  'git rev-parse HEAD && npm test || git status --short',
  'git rev-parse HEAD; false; git status --short',
  'git rev-parse HEAD || git status --short',
  'git rev-parse HEAD; false && git status --short',
  'git rev-parse HEAD && git status --short --untracked-files=no',
]) {
  result = validate({
    ...base,
    guardrails: base.guardrails.map((item) => item.id === 'ship-currentness'
      ? { ...item, command }
      : item),
  });
  assert.notEqual(result.status, 0, command);
  assert.match(result.stderr, /requires ship-currentness after final proof/);
}

for (const command of [
  'git rev-parse HEAD && git status --short',
  'git rev-parse HEAD && true && git status --short',
  'git rev-parse HEAD; git status --short',
]) {
  result = validate({
    ...base,
    guardrails: base.guardrails.map((item) => item.id === 'ship-currentness'
      ? { ...item, command }
      : item),
  });
  assert.equal(result.status, 0, `${command}: ${result.stderr}`);
}

result = validate({
  ...base,
  guardrails: base.guardrails.map((item) => item.id === 'ship-currentness'
    ? { ...item, evidence: ['validated head: `bbbbbbbbb4567890abcdef1234567890abcdef12`; worktree clean after final proof'] }
    : item),
});
assert.notEqual(result.status, 0);
assert.match(result.stderr, /ship-currentness to match the current PR evidence head/);

result = validate({
  ...base,
  guardrails: base.guardrails.map((item) => item.id === 'ship-currentness'
    ? { ...item, evidence: ['validated head: `abcdef1234567890abcdef1234567890abcdef12`; git status --short shows modified files'] }
    : item),
});
assert.notEqual(result.status, 0);
assert.match(result.stderr, /clean worktree evidence/);

for (const evidence of [
  'validated head: `abcdef1234567890abcdef1234567890abcdef12`; worktree not clean after final proof',
  'validated head: `abcdef1234567890abcdef1234567890abcdef12`; worktree has modified files but is clean now',
  'validated head: `abcdef1234567890abcdef1234567890abcdef12`; worktree clean: false',
  'validated head: `abcdef1234567890abcdef1234567890abcdef12`; worktree clean? no',
  'validated head: `abcdef1234567890abcdef1234567890abcdef12`; git status --short no output; clean? no',
  'validated head: `abcdef1234567890abcdef1234567890abcdef12`; worktree has changes; worktree clean',
  'validated head: `abcdef1234567890abcdef1234567890abcdef12`; git status --short returned non-empty; worktree clean',
  'validated head: `abcdef1234567890abcdef1234567890abcdef12`; git status --short returned non-empty, no changes; worktree clean',
  'validated head: `abcdef1234567890abcdef1234567890abcdef12`; git status --short was not empty; worktree clean',
  'validated head: `abcdef1234567890abcdef1234567890abcdef12`; git status --short output present; worktree clean',
  'validated head: `abcdef1234567890abcdef1234567890abcdef12`; changes in worktree; worktree clean',
  'validated head: `abcdef1234567890abcdef1234567890abcdef12`; changes in working tree; worktree clean',
  'validated head: `abcdef1234567890abcdef1234567890abcdef12`; worktree is not currently clean; worktree clean',
  "validated head: `abcdef1234567890abcdef1234567890abcdef12`; git status --short wasn't empty; worktree clean",
]) {
  result = validate({
    ...base,
    guardrails: base.guardrails.map((item) => item.id === 'ship-currentness'
      ? { ...item, evidence: [evidence] }
      : item),
  });
  assert.notEqual(result.status, 0, evidence);
  assert.match(result.stderr, /clean worktree evidence/);
}

for (const porcelain of [
  'M src/app.js',
  'A src/app.js',
  'D src/app.js',
  'R src/old.js -> src/new.js',
  'C src/source.js -> src/copy.js',
  'T src/app.js',
  'U src/app.js',
  '?? src/app.js',
]) {
  result = validate({
    ...base,
    guardrails: base.guardrails.map((item) => item.id === 'ship-currentness'
      ? { ...item, evidence: [`validated head: \`abcdef1234567890abcdef1234567890abcdef12\`; git status --short: ${porcelain}; worktree clean`] }
      : item),
  });
  assert.notEqual(result.status, 0, porcelain);
  assert.match(result.stderr, /clean worktree evidence/);
}

for (const evidence of [
  'validated head: `abcdef1234567890abcdef1234567890abcdef12`; git status --short:\n M src/app.js\nworktree clean',
  'validated head: `abcdef1234567890abcdef1234567890abcdef12`; git status --short:\nT src/app.js\nworktree clean',
  'validated head: `abcdef1234567890abcdef1234567890abcdef12`; git status --short returned: M src/app.js; worktree clean',
  'validated head: `abcdef1234567890abcdef1234567890abcdef12`; git status --short stdout: M src/app.js; worktree clean',
  'validated head: `abcdef1234567890abcdef1234567890abcdef12`; git status --short result: M src/app.js; worktree clean',
  'validated head: `abcdef1234567890abcdef1234567890abcdef12`; git status --short returned `M src/app.js`; worktree clean',
  'validated head: `abcdef1234567890abcdef1234567890abcdef12`; git status --short output: `?? src/app.js`; worktree clean',
  'validated head: `abcdef1234567890abcdef1234567890abcdef12`; git status --short stdout `M src/app.js`; worktree clean',
  'validated head: `abcdef1234567890abcdef1234567890abcdef12`; git status --short result `T src/app.js`; worktree clean',
]) {
  result = validate({
    ...base,
    guardrails: base.guardrails.map((item) => item.id === 'ship-currentness'
      ? { ...item, evidence: [evidence] }
      : item),
  });
  assert.notEqual(result.status, 0, evidence);
  assert.match(result.stderr, /clean worktree evidence/);
}

result = validate({
  ...base,
  guardrails: base.guardrails.map((item) => item.id === 'ship-currentness'
    ? { ...item, sequence: 6 }
    : item),
});
assert.notEqual(result.status, 0);
assert.match(result.stderr, /requires ship-currentness after final proof/);

console.log('he-state-ship-proof-test: pass');
