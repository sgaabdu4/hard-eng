#!/usr/bin/env node
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { validateHePlanEvals } from './skills/he-plan/evals/validate-evals.mjs';

const repo = path.resolve(new URL('..', import.meta.url).pathname);
const script = path.join(repo, 'scripts', 'check-hard-eng-full-repo.mjs');
const scriptText = fs.readFileSync(script, 'utf8');

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
const commandById = new Map(payload.commands.map((entry) => [entry.id, entry]));
const hePlanEvalCount = JSON.parse(fs.readFileSync(path.join(repo, 'tests/skills/he-plan/evals/evals.json'), 'utf8')).evals.length;
const taskCommentEval = {
  id: 1,
  prompt: '[$he-plan](./skills/he-plan/SKILL.md) Use Grill Me for task comments visibility with delegate and admin ambiguity; UI screenshots are still missing and implementation is not ready.',
  expected_output: 'Asks one Grill Me question, requires screenshots when UI review is accepted, and keeps /he:implement not ready.',
  expectations: [
    'Uses Grill Me.',
    'Mentions comments visibility.',
    'Keeps delegate ambiguity open.',
    'Keeps admin ambiguity open.',
    'Does not mark UI screenshots as complete.',
  ],
};
const unrelatedEval = {
  id: 2,
  prompt: '[$he-plan](./skills/he-plan/SKILL.md) Plan a billing export retry policy.',
  expected_output: 'Asks the next planning question for retry ownership.',
  expectations: [
    'Uses he-plan.',
    'Does not finalize implementation.',
    'Asks one question.',
    'Records unknowns.',
  ],
};
assert.deepEqual(validateHePlanEvals({
  skill_name: 'he-plan',
  model: 'gpt-5.4-mini',
  evals: [taskCommentEval, unrelatedEval],
}), []);
assert.ok(validateHePlanEvals({
  skill_name: 'he-plan',
  model: 'gpt-5.4-mini',
  evals: [taskCommentEval, { ...unrelatedEval, id: taskCommentEval.id }],
}).some((error) => error === 'eval id 1 must be unique'));
assert.ok(validateHePlanEvals({
  skill_name: 'he-plan',
  model: 'gpt-5.4-mini',
  evals: {},
}).some((error) => error === 'evals must contain at least one case'));
assert.ok(validateHePlanEvals({
  skill_name: 'he-plan',
  model: 'gpt-5.4-mini',
  evals: [{ ...taskCommentEval, files: {} }, unrelatedEval],
}).some((error) => error === 'eval 1 files must be array'));
assert.ok(validateHePlanEvals({
  skill_name: 'he-plan',
  model: 'gpt-5.4-mini',
  evals: [{ ...taskCommentEval, files: [[]] }, unrelatedEval],
}).some((error) => error === 'eval 1 files[0] must be object'));
assert.deepEqual(validateHePlanEvals({
  skill_name: 'he-plan',
  model: 'gpt-5.4-mini',
  evals: [{
    ...taskCommentEval,
    files: [{ path: 'docs/planning/example-feature/session_state.md', content: '' }],
  }, unrelatedEval],
}), []);
assert.ok(validateHePlanEvals({
  skill_name: 'he-plan',
  model: 'gpt-5.4-mini',
  evals: [{ ...taskCommentEval, files: [{ path: '../escape.md', content: '' }] }, unrelatedEval],
}).some((error) => error === 'eval 1 files[0].path must stay inside eval target'));
assert.ok(validateHePlanEvals({
  skill_name: 'he-plan',
  model: 'gpt-5.4-mini',
  evals: [{ ...taskCommentEval, files: [{ path: 'a/..', content: '' }] }, unrelatedEval],
}).some((error) => error === 'eval 1 files[0].path must stay inside eval target'));
assert.ok(validateHePlanEvals({
  skill_name: 'he-plan',
  model: 'gpt-5.4-mini',
  evals: [{ ...taskCommentEval, files: [{ path: '.', content: '' }] }, unrelatedEval],
}).some((error) => error === 'eval 1 files[0].path must stay inside eval target'));
assert.ok(validateHePlanEvals({
  skill_name: 'he-plan',
  model: 'gpt-5.4-mini',
  evals: [{ ...taskCommentEval, files: [{ path: 'C:escape.md', content: '' }] }, unrelatedEval],
}).some((error) => error === 'eval 1 files[0].path must stay inside eval target'));
assert.ok(validateHePlanEvals({
  skill_name: 'he-plan',
  model: 'gpt-5.4-mini',
  evals: [{ ...taskCommentEval, files: [{ path: 'state.md' }] }, unrelatedEval],
}).some((error) => error === 'eval 1 files[0].content must be string'));
assert.ok(validateHePlanEvals({
  skill_name: 'he-plan',
  model: 'gpt-5.4-mini',
  evals: [unrelatedEval],
}).some((error) => error === 'eval suite missing coverage term comments'));
assert.ok(scriptText.includes('do not run model evals after every session'), 'full-repo gate help must keep eval cadence realistic');
assert.ok(scriptText.includes('maxBuffer: 1024 * 1024 * 64'), 'full-repo gate must allow verbose model eval output');
assert.ok(scriptText.includes('signal: ${result.signal}'), 'full-repo gate logs must include process termination signals');
assert.ok(scriptText.includes("AGENTS_ROUTING_EVAL_CONCURRENCY: '2'"), 'routing evals must stay parallel but bounded in the broad gate');
assert.ok(commandById.get('tests/he-state-compliance.test.mjs')?.timeoutMs >= 420000, 'full-repo gate must allow the compliance matrix to finish');
const explicitDefaultSkips = new Set([
  'tests/skills/e2e/dogfood-playwright-smoke.test.mjs',
  'tests/agents-md-routing/evals/run-evals.mjs',
  'tests/skills/description-routing/evals/run-evals.mjs',
  'tests/skills/e2e/evals/run-evals.mjs',
  'tests/skills/grill-me/evals/run-stage-routing-evals.mjs',
  'tests/skills/grill-me/evals/run-trigger-evals.mjs',
  'tests/skills/he-plan/evals/run-mini-evals.mjs',
  'tests/skills/terse/evals/run-mini-evals.py',
  'tests/skills/treehouse/evals/run-trigger-evals.mjs',
  'tests/skills/grill-me/evals/run-mini-evals.mjs',
]);
const modelEvalSkips = new Set([
  'tests/agents-md-routing/evals/run-evals.mjs',
  'tests/skills/description-routing/evals/run-evals.mjs',
  'tests/skills/e2e/evals/run-evals.mjs',
  'tests/skills/grill-me/evals/run-stage-routing-evals.mjs',
  'tests/skills/grill-me/evals/run-trigger-evals.mjs',
  'tests/skills/he-plan/evals/run-mini-evals.mjs',
  'tests/skills/terse/evals/run-mini-evals.py',
  'tests/skills/treehouse/evals/run-trigger-evals.mjs',
]);
const sessionEvalSkips = new Set([
  'tests/skills/grill-me/evals/run-mini-evals.mjs',
]);
const allEvalRunners = walk('tests')
  .filter((entry) => /\/evals\/run-.*evals\.(mjs|py)$/.test(entry))
  .sort();
const ownedEvalRunners = new Set([...modelEvalSkips, ...sessionEvalSkips]);
const selfRecursiveCheckScripts = new Set([
  'scripts/check-hard-eng-full-repo.mjs',
]);
const allCheckScripts = walk('scripts')
  .filter((entry) => /^scripts\/check-.*\.mjs$/.test(entry))
  .sort();

assert.deepEqual(defaultSkipped, explicitDefaultSkips);
for (const file of allEvalRunners) {
  assert.ok(ownedEvalRunners.has(file), `${file} must be assigned to model or session eval lane`);
}

for (const file of allCheckScripts) {
  if (selfRecursiveCheckScripts.has(file)) continue;
  assert.ok(hasCommand(commands, file), `${file} must be owned by the full-repo gate or explicitly exempted`);
}

for (const file of walk('tests').filter((entry) => entry.endsWith('.test.mjs'))) {
  if (explicitDefaultSkips.has(file)) {
    assert.ok(defaultSkipped.has(file), `${file} must be explicitly skipped`);
  } else {
    assert.ok(hasCommand(commands, file), `${file} must be owned by the full-repo gate`);
  }
}

for (const required of [
  'git diff --check',
  'scripts/check-markdown-hygiene.mjs',
  'tests/skills/grill-me/evals/validate-evals.mjs',
  'tests/skills/he-plan/evals/validate-evals.mjs',
  'tests/skills/treehouse/validate-skill.mjs',
  'scripts/check-generated-assets.mjs .',
  'scripts/check-hard-eng-artifacts.mjs --head .',
  'scripts/check-hard-eng-write-safety.mjs --head .',
  'scripts/check-project-context-gates.mjs --require-all .',
  'scripts/check-project-quality-gates.mjs --require-push-gate .',
  'scripts/check-ssot-guardrails.mjs .',
  'scripts/check-vendor-skill-integrity.mjs .',
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
const withEvalsById = new Map(withEvals.commands.map((entry) => [entry.id, entry]));
assert.ok(
  withEvalsById.get('tests/skills/he-plan/evals/run-mini-evals.mjs')?.timeoutMs > hePlanEvalCount * 900000,
  'include-evals must give he-plan evals parent timeout overhead beyond child budgets',
);
for (const file of modelEvalSkips) {
  assert.ok(hasCommand(commandSet(withEvals), file), `include-evals must add ${file}`);
  assert.equal(withEvals.skipped.includes(file), false);
}
for (const file of sessionEvalSkips) {
  assert.equal(
    hasCommand(commandSet(withEvals), file),
    false,
    `include-evals must not add long session eval ${file}`,
  );
  assert.equal(withEvals.skipped.includes(file), true);
}

const withSessionEvals = list(['--include-session-evals']);
for (const file of sessionEvalSkips) {
  assert.ok(hasCommand(commandSet(withSessionEvals), file), `include-session-evals must add ${file}`);
  assert.equal(withSessionEvals.skipped.includes(file), false);
}

console.log('hard-eng-full-repo-gate-test: pass');
