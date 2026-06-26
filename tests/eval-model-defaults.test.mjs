#!/usr/bin/env node
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';

const repo = path.resolve(new URL('..', import.meta.url).pathname);
const mini = 'gpt-5.4-mini';

function walk(dir, out = []) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) walk(fullPath, out);
    if (entry.isFile()) out.push(fullPath);
  }
  return out;
}

const evalFiles = walk(path.join(repo, 'tests'))
  .filter((file) => file.includes(`${path.sep}evals${path.sep}`));
const descriptionRoutingPath = path.join('tests', 'skills', 'description-routing', 'evals', 'evals.json');

for (const file of evalFiles.filter((item) => item.endsWith('.json'))) {
  const parsed = JSON.parse(fs.readFileSync(file, 'utf8'));
  if (Object.hasOwn(parsed, 'model')) {
    assert.equal(parsed.model, mini, `${path.relative(repo, file)} model must be ${mini}`);
  }
  const relativePath = path.relative(repo, file);
  if (relativePath === path.join('tests', 'agents-md-routing', 'evals', 'evals.json') && Array.isArray(parsed.cases)) {
    const caseIds = new Set(parsed.cases.map((item) => item.id));
    for (const requiredCase of [
      'workflow_help_front_door',
      'he_stage_order_receipts_full_path',
      'he_failure_loops_all_stages',
      'he_plan_no_guesswork_alignment',
      'lavish_ui_decision_poll_receipt',
      'verify_loop_before_no_mistakes',
      'no_mistakes_handoff',
    ]) {
      assert.ok(caseIds.has(requiredCase), `${path.relative(repo, file)} missing required eval case ${requiredCase}`);
    }
  }
  if (relativePath === descriptionRoutingPath && Array.isArray(parsed.cases)) {
    const routedSkills = new Set(parsed.cases.flatMap((item) => item.expectedSkills || []));
    const activeSkills = fs.readdirSync(path.join(repo, 'skills'), { withFileTypes: true })
      .filter((entry) => entry.isDirectory() || entry.isSymbolicLink())
      .filter((entry) => fs.existsSync(path.join(repo, 'skills', entry.name, 'SKILL.md')))
      .map((entry) => entry.name)
      .sort();
    for (const skill of activeSkills) {
      assert.ok(routedSkills.has(skill), `${descriptionRoutingPath} missing broad routing eval for ${skill}`);
    }
  }
}

for (const file of [
  path.join(repo, 'scripts', 'run-skill-mini-evals.mjs'),
  ...evalFiles.filter((item) => /run.*evals\.(mjs|py)$/.test(path.basename(item))),
]) {
  const text = fs.readFileSync(file, 'utf8');
  const configPath = path.join(path.dirname(file), 'evals.json');
  const usesPinnedConfig = text.includes('config.model') &&
    fs.existsSync(configPath) &&
    JSON.parse(fs.readFileSync(configPath, 'utf8')).model === mini;
  assert.ok(text.includes(mini) || usesPinnedConfig, `${path.relative(repo, file)} must default evals to ${mini}`);
  assert.ok(!/gpt-5\.5/.test(text), `${path.relative(repo, file)} must not run evals on gpt-5.5`);
}

console.log('eval-model-defaults-test: pass');
