#!/usr/bin/env node
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';

const repo = path.resolve(new URL('..', import.meta.url).pathname);
const script = path.join(repo, 'scripts', 'check-hard-eng-full-repo.mjs');

function walk(dir, out = []) {
  for (const entry of fs.readdirSync(path.join(repo, dir), { withFileTypes: true })) {
    const rel = path.posix.join(dir, entry.name);
    if (entry.isDirectory()) walk(rel, out);
    else out.push(rel);
  }
  return out;
}

function list(args = []) {
  const result = spawnSync('node', [script, '--list', '--json', ...args], {
    cwd: repo,
    encoding: 'utf8',
  });
  assert.equal(result.status, 0, result.stderr || result.stdout);
  return JSON.parse(result.stdout);
}

function commandSet(payload) {
  return new Set(payload.commands.map((entry) => entry.command));
}

function hasCommand(commands, snippet) {
  return [...commands].some((command) => command.includes(snippet));
}

const payload = list();
const commands = commandSet(payload);
const defaultSkipped = new Set(payload.skipped);
const explicitDefaultSkips = new Set([
  'tests/skills/e2e/dogfood-playwright-smoke.test.mjs',
  'tests/agents-md-routing/evals/run-evals.mjs',
  'tests/skills/description-routing/evals/run-evals.mjs',
  'tests/skills/e2e/evals/run-evals.mjs',
  'tests/skills/grill-me/evals/run-mini-evals.mjs',
  'tests/skills/grill-me/evals/run-trigger-evals.mjs',
  'tests/skills/terse/evals/run-mini-evals.py',
  'tests/skills/treehouse/evals/run-trigger-evals.mjs',
]);

assert.deepEqual(defaultSkipped, explicitDefaultSkips);

for (const file of walk('tests').filter((entry) => entry.endsWith('.test.mjs'))) {
  if (explicitDefaultSkips.has(file)) {
    assert.ok(defaultSkipped.has(file), `${file} must be explicitly skipped`);
  } else {
    assert.ok(hasCommand(commands, file), `${file} must be owned by the full-repo gate`);
  }
}

for (const required of [
  'git diff --check',
  'tests/skills/grill-me/evals/validate-evals.mjs',
  'tests/skills/treehouse/validate-skill.mjs',
  'scripts/check-generated-assets.mjs .',
  'scripts/check-project-context-gates.mjs --require-all .',
  'scripts/check-project-quality-gates.mjs --require-push-gate .',
  'scripts/check-ssot-guardrails.mjs .',
]) {
  assert.ok(hasCommand(commands, required), `missing required gate command: ${required}`);
}

const withE2e = list(['--include-e2e']);
assert.ok(
  hasCommand(commandSet(withE2e), 'tests/skills/e2e/dogfood-playwright-smoke.test.mjs'),
  'include-e2e must add the real E2E dogfood smoke',
);
assert.equal(withE2e.skipped.includes('tests/skills/e2e/dogfood-playwright-smoke.test.mjs'), false);

const withEvals = list(['--include-evals']);
for (const file of [...explicitDefaultSkips].filter((entry) => entry.includes('/evals/'))) {
  assert.ok(hasCommand(commandSet(withEvals), file), `include-evals must add ${file}`);
  assert.equal(withEvals.skipped.includes(file), false);
}

console.log('hard-eng-full-repo-gate-test: pass');
