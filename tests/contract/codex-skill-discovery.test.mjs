import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import readline from 'node:readline';
import { spawn, spawnSync } from 'node:child_process';
import test from 'node:test';
import assert from 'node:assert/strict';

const root = path.resolve('.');
const realCodexAvailable = process.env.HARD_ENG_CHECK !== '1'
  && spawnSync('codex', ['--version'], { encoding: 'utf8' }).status === 0;

function minimalEnvironment(home) {
  return Object.fromEntries([
    ['HOME', home],
    ['CODEX_HOME', path.join(home, '.codex')],
    ...['PATH', 'TMPDIR', 'TMP', 'TEMP', 'SHELL', 'LANG', 'LC_ALL', 'LC_CTYPE']
      .filter((key) => process.env[key] !== undefined)
      .map((key) => [key, process.env[key]]),
  ]);
}

function listCodexSkills(home) {
  return new Promise((resolve, reject) => {
    const child = spawn('codex', [
      'app-server', '--disable', 'plugins', '--disable', 'remote_plugin',
      '--disable', 'apps', '--stdio',
    ], {
      cwd: root,
      env: minimalEnvironment(home),
      stdio: ['pipe', 'pipe', 'pipe'],
    });
    let settled = false;
    let stderr = '';
    const lines = readline.createInterface({ input: child.stdout });
    const timer = setTimeout(() => finish(new Error('Codex skills/list timed out.')), 15_000);
    function finish(error, value) {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      lines.close();
      child.stdin.end();
      child.kill('SIGTERM');
      if (error) reject(error);
      else resolve(value);
    }
    child.stderr.on('data', (chunk) => {
      stderr = `${stderr}${chunk}`.slice(-8_192);
    });
    child.on('error', finish);
    child.on('exit', (code) => {
      if (!settled) finish(new Error(`Codex app-server exited ${code}: ${stderr}`));
    });
    lines.on('line', (line) => {
      let message;
      try { message = JSON.parse(line); } catch { return; }
      if (message.id === 1) {
        child.stdin.write(`${JSON.stringify({ method: 'initialized', params: {} })}\n`);
        child.stdin.write(`${JSON.stringify({
          id: 2,
          method: 'skills/list',
          params: { cwds: [root], forceReload: true },
        })}\n`);
      } else if (message.id === 2) finish(null, message.result);
    });
    child.stdin.write(`${JSON.stringify({
      id: 1,
      method: 'initialize',
      params: {
        clientInfo: { name: 'hard-eng-contract', version: '1.0.0' },
        capabilities: { experimentalApi: true },
      },
    })}\n`);
  });
}

test('a clean Codex app-server discovers every native user skill with no plugin owner', {
  skip: realCodexAvailable ? false : 'Real Codex discovery is unavailable inside the model-free ordinary check registry.',
}, async () => {
  const home = fs.mkdtempSync(path.join(os.tmpdir(), 'hard-eng-codex-skills-'));
  fs.symlinkSync(root, path.join(home, '.agents'));
  fs.mkdirSync(path.join(home, '.codex'), { recursive: true });
  try {
    const response = await listCodexSkills(home);
    assert.equal(response.data.length, 1);
    assert.deepEqual(response.data[0].errors, []);
    const discovered = response.data[0].skills.filter((skill) => skill.scope === 'user');
    const expectedPaths = fs.readdirSync(path.join(root, 'skills'), { withFileTypes: true })
      .filter((entry) => entry.isDirectory() || entry.isSymbolicLink())
      .map((entry) => fs.realpathSync(path.join(root, 'skills', entry.name, 'SKILL.md')))
      .sort();
    const discoveredPaths = discovered.map((skill) => fs.realpathSync(skill.path)).sort();
    assert.equal(discovered.length, 35);
    assert.equal(new Set(discovered.map((skill) => skill.name)).size, 35);
    assert.deepEqual(discoveredPaths, expectedPaths);
    assert.equal(discovered.every((skill) => skill.enabled === true), true);
    assert.equal(discovered.some((skill) => skill.name === 'hard-eng:hard-eng'), false);
    assert.equal(discovered.some((skill) => skill.path.includes(`${path.sep}.codex${path.sep}skills${path.sep}`)), false);
  } finally {
    fs.rmSync(home, { recursive: true, force: true });
  }
});
