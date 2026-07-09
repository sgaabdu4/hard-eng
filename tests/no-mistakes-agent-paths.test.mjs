#!/usr/bin/env node
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';

const repo = path.resolve(new URL('..', import.meta.url).pathname);
const script = path.join(repo, 'scripts', 'refresh-no-mistakes-agent-paths.mjs');
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'no-mistakes-agent-paths-'));
const replacement = path.join(tmp, 'codex');
fs.writeFileSync(replacement, '#!/bin/sh\nexit 0\n', { mode: 0o755 });

function repair(name, text) {
  const config = path.join(tmp, `${name}.yaml`);
  fs.writeFileSync(config, text);
  const result = spawnSync('node', [script, '--config', config, '--agent', 'codex', '--binary', replacement], { encoding: 'utf8' });
  assert.equal(result.status, 0, result.stderr);
  return { config, output: result.stdout, text: fs.readFileSync(config, 'utf8') };
}

const stale = repair('stale', [
  'agent: codex',
  'agent_path_override:',
  '  codex: /missing/Codex.app/codex',
  '  claude: /custom/claude',
  'auto_fix:',
  '  review: 0',
  '',
].join('\n'));
assert.match(stale.output, /refreshed codex override/);
assert.match(stale.text, new RegExp(`  codex: ${JSON.stringify(replacement).replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}`));
assert.match(stale.text, /  claude: \/custom\/claude/);
assert.match(stale.text, /auto_fix:\n  review: 0/);

const validBinary = path.join(tmp, 'valid-codex');
fs.copyFileSync(replacement, validBinary);
fs.chmodSync(validBinary, 0o755);
const valid = repair('valid', `agent_path_override:\n  codex: ${validBinary}\n`);
assert.match(valid.output, /preserved executable codex override/);
assert.match(valid.text, new RegExp(validBinary.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')));

const absent = repair('absent', 'agent: codex\nauto_fix:\n  review: 0\n');
assert.match(absent.output, /no override section/);
assert.equal(absent.text, 'agent: codex\nauto_fix:\n  review: 0\n');

const symlinkTarget = path.join(tmp, 'linked-target.yaml');
const symlinkConfig = path.join(tmp, 'linked-config.yaml');
fs.writeFileSync(symlinkTarget, 'agent_path_override:\n  codex: /missing/codex\n');
fs.symlinkSync(path.basename(symlinkTarget), symlinkConfig);
let result = spawnSync('node', [script, '--config', symlinkConfig, '--agent', 'codex', '--binary', replacement], { encoding: 'utf8' });
assert.equal(result.status, 0, result.stderr);
assert.equal(fs.lstatSync(symlinkConfig).isSymbolicLink(), true, 'config refresh must preserve config.yaml symlinks');
assert.match(fs.readFileSync(symlinkTarget, 'utf8'), new RegExp(JSON.stringify(replacement).replace(/[.*+?^${}()|[\]\\]/g, '\\$&')));

const nmHome = path.join(tmp, 'nm-home');
const noMistakesHome = path.join(tmp, 'no-mistakes-home');
fs.mkdirSync(nmHome, { recursive: true });
fs.mkdirSync(noMistakesHome, { recursive: true });
fs.writeFileSync(path.join(nmHome, 'config.yaml'), 'agent_path_override:\n  codex: /missing/nm-codex\n');
fs.writeFileSync(path.join(noMistakesHome, 'config.yaml'), 'agent_path_override:\n  codex: /missing/no-mistakes-codex\n');
result = spawnSync('bash', ['-c', [
  'set -euo pipefail',
  'source "$ROOT/scripts/no-mistakes-wrapper-install.sh"',
  'refresh_no_mistakes_agent_paths',
].join('\n')], {
  cwd: repo,
  encoding: 'utf8',
  env: {
    ...process.env,
    ROOT: repo,
    NM_HOME: nmHome,
    NO_MISTAKES_HOME: noMistakesHome,
    HARD_ENG_CODEX_BIN: replacement,
  },
});
assert.equal(result.status, 0, result.stderr);
assert.match(fs.readFileSync(path.join(nmHome, 'config.yaml'), 'utf8'), new RegExp(JSON.stringify(replacement).replace(/[.*+?^${}()|[\]\\]/g, '\\$&')));
assert.match(fs.readFileSync(path.join(noMistakesHome, 'config.yaml'), 'utf8'), /\/missing\/no-mistakes-codex/);

console.log('no-mistakes-agent-paths-test: pass');
