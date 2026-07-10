#!/usr/bin/env node
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';

const repo = path.resolve(new URL('../..', import.meta.url).pathname);
const workflowSkill = fs.readFileSync(path.join(repo, 'skills/workflow-help/SKILL.md'), 'utf8');
const routeMap = fs.readFileSync(path.join(repo, 'skills/workflow-help/references/route-map.md'), 'utf8');
const agents = fs.readFileSync(path.join(repo, 'AGENTS.md'), 'utf8');
const readme = fs.readFileSync(path.join(repo, 'README.md'), 'utf8');
const grillModes = fs.readFileSync(path.join(repo, 'skills/grill-me/modules/modes.md'), 'utf8');
const grillOrchestration = fs.readFileSync(path.join(repo, 'skills/grill-me/modules/orchestration.md'), 'utf8');
const tddSkill = fs.readFileSync(path.join(repo, 'skills/tdd/SKILL.md'), 'utf8');
const tddWorkflow = fs.readFileSync(path.join(repo, 'skills/tdd/references/workflow.md'), 'utf8');
const descriptionRouting = JSON.parse(fs.readFileSync(path.join(repo, 'tests/skills/description-routing/evals/evals.json'), 'utf8'));

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
  '`setup-engineering-skills`',
]) {
  assert.ok(routeMap.includes(needle), `route-map must codify: ${needle}`);
}

assert.match(agents, /Every non-trivial request -> `workflow-help` first/);
assert.match(workflowSkill, /description: Before every non-trivial request,/);
assert.match(grillModes, /align.*lite[\s\S]*inline decision summary[\s\S]*`plan\.md` only when useful/i);
assert.match(grillOrchestration, /inline decision summary[\s\S]*without `plan\.md`/i);
assert.match(readme, /router handshake checks onboarding gaps/);
assert.match(readme, /direct answer, direct skill, small change, normal decision, or Hard\s+Eng/);
assert.deepEqual(descriptionRouting.alwaysExpectedSkills, ['workflow-help']);
for (const id of ['sentry_cli', 'sentry_feature_setup', 'sentry_sdk_setup', 'sentry_workflow']) {
  assert.deepEqual(descriptionRouting.cases.find((entry) => entry.id === id)?.expectedSkills, ['sentry-workflow']);
}
assert.match(agents, /Sentry\/observability\/issues\/setup -> `sentry-workflow` only/);
assert.match(routeMap, /Sentry\/observability\/issues\/setup[^\n]*`sentry-workflow` only/);
assert.deepEqual(
  descriptionRouting.cases.find((entry) => entry.id === 'react_doctor')?.expectedSkills,
  ['react-doctor', 'fallow', 'vercel-react-best-practices'],
);
for (const id of ['code_review', 'thermo_review']) {
  assert.deepEqual(
    descriptionRouting.cases.find((entry) => entry.id === id)?.expectedSkills,
    ['code-review', 'thermo-nuclear-code-quality-review'],
  );
}
assert.match(tddWorkflow, /repo evidence[\s\S]*public boundary[\s\S]*proceed/i);
assert.match(tddWorkflow, /Ask the user only when\s+competing seams materially change coverage or behavior/i);
assert.doesNotMatch(tddWorkflow, /confirm them with the user/);
assert.match(tddWorkflow, /red.+green.+refactor/i);
assert.match(tddWorkflow, /Refactor:/i);
assert.doesNotMatch(tddWorkflow, /Refactoring is not part of the loop/i);

console.log('workflow-help-router: pass');
