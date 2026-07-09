#!/usr/bin/env node
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';

const repo = path.resolve(new URL('../..', import.meta.url).pathname);
const workflowSkill = fs.readFileSync(path.join(repo, 'skills/workflow-help/SKILL.md'), 'utf8');
const routeMap = fs.readFileSync(path.join(repo, 'skills/workflow-help/references/route-map.md'), 'utf8');
const agents = fs.readFileSync(path.join(repo, 'AGENTS.md'), 'utf8');
const readme = fs.readFileSync(path.join(repo, 'README.md'), 'utf8');

for (const needle of [
  'Canonical router',
  'onboarding gaps',
  'evidence read',
  'decisions made',
  'proof required',
]) {
  assert.match(workflowSkill, new RegExp(needle, 'i'), `workflow-help SKILL.md must mention ${needle}`);
}

for (const needle of [
  '## Canonical Router Handshake',
  'Route first',
  'Check onboarding gaps',
  'Read evidence before discussion',
  'Ask discussion questions only when evidence leaves a blocking choice',
  'Return a route receipt before build',
  'Small change',
  'The handshake does not force Hard Eng',
]) {
  assert.ok(routeMap.includes(needle), `route-map must codify: ${needle}`);
}

assert.match(agents, /Workflow\/next-step\/router\/onboarding\/HE-vs-direct -> `workflow-help`/);
assert.match(readme, /router handshake checks onboarding gaps/);
assert.match(readme, /direct answer, direct skill, small change, normal decision, or Hard\s+Eng/);

console.log('workflow-help-router: pass');
