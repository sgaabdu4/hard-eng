import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import assert from 'node:assert/strict';
import { runSetup } from '../../scripts/setup.mjs';
import { makeWiringClient } from '../fixtures/wiring-client-fixture.mjs';

const sourceRoot = path.resolve('.');
const wiringClient = makeWiringClient();

function home(prefix) {
  return fs.mkdtempSync(path.join(os.tmpdir(), prefix));
}

test('setup fails closed when CODEX_HOME is not the selected home default', () => {
  const targetHome = home('hard-eng-custom-codex-home-');
  const customCodexHome = path.join(targetHome, 'custom-codex');
  const options = {
    sourceRoot,
    wiringClient,
    env: { HOME: targetHome, CODEX_HOME: customCodexHome, PATH: '/nonexistent' },
    cronText: '',
  };
  const report = runSetup(['doctor', '--home', targetHome], options);
  assert.equal(report.environment.status, 'FAIL');
  assert.equal(report.environment.codex_home, 'custom-unsupported');
  assert.deepEqual(fs.readdirSync(targetHome), []);
  assert.throws(() => runSetup(['install', '--home', targetHome, '--dry-run'], options), /CODEX_HOME.*default/i);
});

test('setup reports and rejects unsupported operating systems before planning mutation', () => {
  const targetHome = home('hard-eng-unsupported-platform-');
  const options = {
    sourceRoot,
    wiringClient,
    env: { HOME: targetHome, PATH: '/nonexistent' },
    cronText: '',
    platform: 'win32',
  };
  const report = runSetup(['doctor', '--home', targetHome], options);
  assert.equal(report.environment.status, 'FAIL');
  assert.equal(report.environment.platform, 'win32');
  assert.throws(() => runSetup(['install', '--home', targetHome, '--dry-run'], options), /platform.*supported/i);
  assert.deepEqual(fs.readdirSync(targetHome), []);
});
