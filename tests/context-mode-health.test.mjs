#!/usr/bin/env node
import path from 'node:path';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';

const repo = path.join(process.env.HOME, '.agents');
const health = path.join(repo, 'codex', 'bin', 'codex-context-mode-health');

const result = spawnSync(health, {
  cwd: repo,
  env: {
    ...process.env,
    HARD_ENG_ROOT: repo,
    CONTEXT_MODE_MCP_PROBE_TIMEOUT_MS: '5000',
  },
  encoding: 'utf8',
});

assert.equal(result.status, 0, `codex-context-mode-health failed:\nSTDOUT:\n${result.stdout}\nSTDERR:\n${result.stderr}`);
assert.match(result.stdout, /context-mode no-hooks config ok: MCP registered; storage pinned to ~\/.codex\/context-mode;/);
assert.match(result.stdout, /context-mode MCP probe ok:/);
assert.doesNotMatch(result.stdout, /hook missing or not pointing to context-mode/);
assert.doesNotMatch(result.stdout, /\bFAIL\b/);

console.log('context-mode-health: pass');
