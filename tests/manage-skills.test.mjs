#!/usr/bin/env node
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { isUninitializedSubmodule } from './helpers/submodules.mjs';

const repo = path.resolve(new URL('..', import.meta.url).pathname);
const script = path.join(repo, 'scripts', 'manage-skills.mjs');
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'hard-eng-skills-'));
const config = path.join(tmp, '.config', 'hard-eng', 'skills.json');
const env = { ...process.env, HOME: tmp, HARD_ENG_SKILL_CONFIG: config };
const retiredUiDecisionSkill = ['lav', 'ish'].join('');
const removedLocalSkills = ['skill-creator', 'tavily-cli', 'to-issues', 'to-prd', 'tvly'];
delete env.HARD_ENG_SKILLS;

function run(args, extraEnv = {}) {
  const result = spawnSync('node', [script, ...args], {
    cwd: repo,
    env: { ...env, ...extraEnv },
    encoding: 'utf8',
  });
  assert.equal(result.status, 0, `${args.join(' ')}\n${result.stderr}`);
  return result.stdout;
}

function skillTarget(homeRelative, name) {
  return path.join(tmp, homeRelative, 'skills', name);
}

function assertManagedLink(homeRelative, name) {
  const target = skillTarget(homeRelative, name);
  assert.ok(fs.lstatSync(target).isSymbolicLink(), `${target} should be a symlink`);
  assert.equal(fs.readlinkSync(target), path.join(repo, 'skills', name));
}

const available = run(['list']).trim().split('\n');
assert.ok(available.includes('he-plan'));
assert.ok(available.includes('atomic-ui'));
if (fs.existsSync(path.join(repo, 'skills', 'no-mistakes', 'SKILL.md'))) {
  assert.ok(available.includes('no-mistakes'), 'no-mistakes must be linked from the pinned upstream submodule');
} else {
  assert.ok(!available.includes('no-mistakes'), 'uninitialized no-mistakes submodule must not be installable');
  assert.ok(isUninitializedSubmodule(repo, 'vendor/skill-upstreams/no-mistakes'), 'missing no-mistakes skill must be an uninitialized submodule');
}

run(['configure', 'he-plan,atomic-ui']);
assert.deepEqual(JSON.parse(fs.readFileSync(config, 'utf8')), { selection: 'atomic-ui,he-plan' });
run(['apply']);
for (const homeRelative of ['.codex', '.copilot', '.pi', path.join('.pi', 'agent')]) {
  assertManagedLink(homeRelative, 'he-plan');
  assertManagedLink(homeRelative, 'atomic-ui');
  assert.equal(fs.existsSync(skillTarget(homeRelative, 'no-mistakes')), false);
}

const userOwned = skillTarget('.codex', 'no-mistakes');
fs.mkdirSync(userOwned, { recursive: true });
fs.writeFileSync(path.join(userOwned, 'SKILL.md'), '# User-owned skill\n');
const stale = skillTarget('.copilot', 'stale-hard-eng-skill');
fs.symlinkSync(path.join(repo, 'skills', 'missing-hard-eng-skill'), stale, 'dir');

run(['configure', 'none']);
run(['apply']);
assert.ok(fs.existsSync(userOwned), 'user-owned skill folders must be preserved');
assert.equal(fs.existsSync(skillTarget('.codex', 'he-plan')), false, 'deselected managed skills must be removed');
assert.equal(fs.lstatSync(stale, { throwIfNoEntry: false }), undefined, 'stale managed skill links must be removed');

run(['apply'], { HARD_ENG_SKILLS: 'atomic-ui' });
assertManagedLink('.codex', 'atomic-ui');
assert.equal(fs.existsSync(skillTarget('.codex', 'he-plan')), false, 'env override must beat saved config');

fs.writeFileSync(config, `${JSON.stringify({ selection: `he-plan,${retiredUiDecisionSkill}` }, null, 2)}\n`);
run(['apply']);
assertManagedLink('.codex', 'he-plan');
assert.equal(fs.existsSync(skillTarget('.codex', retiredUiDecisionSkill)), false, 'retired UI decision selections must be dropped');

fs.writeFileSync(config, `${JSON.stringify({ selection: `he-plan,${removedLocalSkills.join(',')}` }, null, 2)}\n`);
run(['apply']);
assertManagedLink('.codex', 'he-plan');
for (const skill of removedLocalSkills) {
  assert.equal(fs.existsSync(skillTarget('.codex', skill)), false, `removed local skill ${skill} selections must be dropped`);
}

run(['apply'], { HARD_ENG_SKILLS: `${retiredUiDecisionSkill},atomic-ui` });
assertManagedLink('.codex', 'atomic-ui');
assert.equal(fs.existsSync(skillTarget('.codex', retiredUiDecisionSkill)), false, 'retired UI decision env selections must be dropped');

run(['remove']);
assert.equal(fs.existsSync(skillTarget('.codex', 'atomic-ui')), false);
assert.equal(fs.existsSync(skillTarget('.codex', 'he-plan')), false);
assert.ok(fs.existsSync(userOwned), 'remove must preserve user-owned skill folders');

console.log('manage-skills-test: pass');
