import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import test from 'node:test';

const repoRoot = path.resolve(new URL('../../..', import.meta.url).pathname);
const scaffold = path.join(repoRoot, 'skills/e2e/scripts/scaffold-e2e-project.mjs');
const checker = path.join(repoRoot, 'skills/e2e/scripts/check-e2e-project.mjs');

function makeRepo() {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'e2e-project-pack-'));
}

function runNode(script, args) {
  return spawnSync('node', [script, ...args], {
    encoding: 'utf8',
  });
}

function parseJson(result) {
  assert.equal(result.status, 0, result.stdout + result.stderr);
  return JSON.parse(result.stdout);
}

test('scaffold creates the first-run project pack without secrets', () => {
  const root = makeRepo();
  const result = parseJson(runNode(scaffold, ['--root', root]));
  assert.equal(result.status, 'scaffolded');

  for (const rel of [
    'docs/e2e/project.json',
    'docs/e2e/auth.md',
    'docs/e2e/automation.md',
    'docs/e2e/logging.md',
    'docs/e2e/regression.md',
    'docs/e2e/issues.md',
    'docs/e2e/flows/README.md',
  ]) {
    assert.equal(fs.existsSync(path.join(root, rel)), true, `${rel} missing`);
  }

  const project = JSON.parse(fs.readFileSync(path.join(root, 'docs/e2e/project.json'), 'utf8'));
  assert.equal(project.dataMode.mode, 'unknown');
  assert.equal(project.dataMode.default, 'seeded-test');
  assert.match(project.auth.secretsPolicy, /Do not commit credentials/);
  assert.deepEqual(project.automation.commands, []);
  assert.equal(project.flows[0].automationCommand, '');
});

test('project checker reports unknown data mode and automation until verified facts are persisted', () => {
  const root = makeRepo();
  parseJson(runNode(scaffold, ['--root', root]));

  const needsInput = parseJson(runNode(checker, ['--root', root]));
  assert.equal(needsInput.status, 'needs-input');
  assert.equal(needsInput.unknowns.includes('data mode'), true);
  assert.equal(needsInput.unknowns.includes('automated E2E commands'), true);
  assert.equal(needsInput.unknowns.includes('flow automation commands'), true);

  const projectPath = path.join(root, 'docs/e2e/project.json');
  const project = JSON.parse(fs.readFileSync(projectPath, 'utf8'));
  project.targets[0].url = 'http://127.0.0.1:3000';
  project.auth.method = 'test-account';
  project.dataMode.mode = 'seeded-test';
  project.logging.commands = ['npm run dev'];
  project.regression.commands = ['npm test'];
  project.automation.commands = ['npm run e2e:smoke'];
  project.flows[0].automationCommand = 'npm run e2e:smoke -- --flow login';
  fs.writeFileSync(projectPath, `${JSON.stringify(project, null, 2)}\n`);

  const ready = parseJson(runNode(checker, ['--root', root]));
  assert.equal(ready.status, 'ready');
  assert.deepEqual(ready.unknowns, []);
});
