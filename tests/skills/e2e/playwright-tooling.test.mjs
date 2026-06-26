import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import test from 'node:test';

const repoRoot = path.resolve(new URL('../../..', import.meta.url).pathname);
const ensurePlaywright = path.join(repoRoot, 'skills/e2e/scripts/ensure-playwright.mjs');
const checkRuntime = path.join(repoRoot, 'skills/e2e/scripts/check-ui-runtime.mjs');

function makeDir() {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'e2e-playwright-tooling-'));
}

function runEnsure(args = [], env = {}) {
  return spawnSync('node', [ensurePlaywright, ...args], {
    cwd: makeDir(),
    env: { ...process.env, ...env },
    encoding: 'utf8',
  });
}

test('ensure-playwright reports missing without installing by default', () => {
  const installDir = makeDir();
  const result = runEnsure(['--install-dir', installDir], {
    PLAYWRIGHT_NODE_MODULE_DIR: '',
    E2E_PLAYWRIGHT_HOME: '',
  });
  assert.notEqual(result.status, 0);
  const parsed = JSON.parse(result.stdout);
  assert.equal(parsed.status, 'missing');
  assert.match(parsed.command, /ensure-playwright\.mjs --install/);
});

test('ensure-playwright finds an existing Playwright package from PLAYWRIGHT_NODE_MODULE_DIR', () => {
  const root = makeDir();
  const moduleDir = path.join(root, 'node_modules');
  const packageDir = path.join(moduleDir, 'playwright');
  fs.mkdirSync(packageDir, { recursive: true });
  fs.writeFileSync(path.join(packageDir, 'package.json'), JSON.stringify({
    name: 'playwright',
    version: '1.2.3-test',
  }));

  const result = runEnsure([], { PLAYWRIGHT_NODE_MODULE_DIR: moduleDir });
  assert.equal(result.status, 0, result.stdout + result.stderr);
  const parsed = JSON.parse(result.stdout);
  assert.equal(parsed.status, 'ready');
  assert.equal(parsed.version, '1.2.3-test');
  assert.equal(parsed.nodeModuleDir, moduleDir);
});

test('check-ui-runtime reports Node and npm preflight details', () => {
  const result = spawnSync('node', [checkRuntime, '--root', makeDir()], {
    encoding: 'utf8',
  });
  assert.equal(result.status, 0, result.stdout + result.stderr);
  const parsed = JSON.parse(result.stdout);
  assert.equal(parsed.status, 'ready');
  assert.ok(parsed.nodes.some((node) => node.status === 'ready' && node.version));
  assert.equal(parsed.npmIgnoreScripts.status, 'ready');
});

test('check-ui-runtime fails before E2E when a requested native module is unavailable', () => {
  const result = spawnSync('node', [
    checkRuntime,
    '--root',
    makeDir(),
    '--native-module',
    'definitely-not-installed-native-e2e-module',
  ], {
    encoding: 'utf8',
  });
  assert.notEqual(result.status, 0);
  const parsed = JSON.parse(result.stdout);
  assert.equal(parsed.status, 'failed');
  assert.equal(parsed.nativeModules[0].status, 'failed');
});
