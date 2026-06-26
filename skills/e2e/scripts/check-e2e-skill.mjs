#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';

const root = process.cwd();
const skillDir = path.join(root, 'skills/e2e');
const skillPath = path.join(skillDir, 'SKILL.md');
const failures = [];

function read(rel) {
  return fs.readFileSync(path.join(skillDir, rel), 'utf8');
}

function lineCount(text) {
  return text.split('\n').length;
}

function assert(condition, message) {
  if (!condition) failures.push(message);
}

const skill = fs.readFileSync(skillPath, 'utf8');
assert(lineCount(skill) <= 100, `SKILL.md has ${lineCount(skill)} lines, expected <= 100`);

const requiredRefs = [
  'references/defaults.md',
  'references/project-pack.md',
  'references/browser-first.md',
  'references/capture-artifacts.md',
  'references/runbook.md',
  'references/dogfood.md',
];
const requiredTemplates = [
  'templates/project.json',
  'templates/auth.md',
  'templates/automation.md',
  'templates/flow.md',
  'templates/logging.md',
  'templates/regression.md',
  'templates/issues.md',
];
const requiredScripts = [
  'scripts/check-e2e-project.mjs',
  'scripts/check-e2e-run-artifacts.mjs',
  'scripts/check-ui-runtime.mjs',
  'scripts/dogfood-playwright-smoke.mjs',
  'scripts/ensure-playwright.mjs',
  'scripts/make-2x-recap.mjs',
  'scripts/scaffold-e2e-project.mjs',
];

for (const rel of requiredRefs) {
  const fullPath = path.join(skillDir, rel);
  assert(fs.existsSync(fullPath), `${rel} is missing`);
  if (fs.existsSync(fullPath)) {
    const text = fs.readFileSync(fullPath, 'utf8');
    assert(lineCount(text) <= 700, `${rel} has ${lineCount(text)} lines, expected <= 700`);
  }
  assert(skill.includes(rel), `SKILL.md does not link ${rel}`);
}

const defaults = read('references/defaults.md');
const projectPack = read('references/project-pack.md');
const browser = read('references/browser-first.md');
const capture = read('references/capture-artifacts.md');
const runbook = read('references/runbook.md');
const dogfood = read('references/dogfood.md');

assert(skill.includes('auto-full-safe'), 'SKILL.md must default to auto-full-safe');
assert(skill.includes('Codex Browser first'), 'SKILL.md must state Codex Browser first');
assert(skill.includes('standalone Playwright is last resort'), 'SKILL.md must make Playwright last resort');
assert(skill.includes('saved auth/flow reuse'), 'SKILL.md must require project-pack checks before saved auth/flow reuse');
assert(skill.includes('runnable automated E2E command'), 'SKILL.md must require automated E2E commands');
assert(defaults.includes('ask only'), 'defaults must minimize onboarding questions');
assert(defaults.includes('automated UI command'), 'defaults must require automated UI commands');
assert(defaults.includes('regression'), 'defaults must require regression checks');
assert(defaults.includes('Default data mode is mock or seeded test data'), 'defaults must avoid implicit prod data');
assert(skill.includes('Confirm data mode before running flows'), 'SKILL.md must require data-mode confirmation');
assert(projectPack.includes('docs/e2e/project.json'), 'project pack must define persisted project.json');
assert(projectPack.includes('check-e2e-project.mjs'), 'project pack must require project checker');
assert(projectPack.includes('Every E2E flow should be automated'), 'project pack must require automated flows');
assert(projectPack.includes('automation.commands'), 'project pack must require automation commands');
assert(projectPack.includes('prod-read-only'), 'project pack must persist prod-read-only data mode');
assert(browser.indexOf('Codex Browser first') < browser.indexOf('Standalone Playwright'), 'browser-first policy must list Browser before Playwright');
assert(/stop (that driver|UI automation probing)/.test(browser), 'browser-first policy must stop after failed probes');
assert(browser.includes('ensure-playwright.mjs'), 'browser-first policy must check/provision Playwright before declaring it unavailable');
assert(browser.includes('Computer Use'), 'browser-first policy must include Computer Use fallback');
assert(browser.includes('check-ui-runtime.mjs'), 'browser-first policy must include runtime preflight');
assert(capture.includes('events.jsonl'), 'capture policy must require events.jsonl');
assert(capture.includes('videos/<flow>_<desktop|mobile>.mp4'), 'capture policy must define desktop/mobile video artifacts');
assert(capture.includes('desktop and mobile 2x speed recap videos'), 'capture policy must require desktop/mobile 2x recap videos');
assert(capture.includes('make-2x-recap.mjs'), 'capture policy must link the 2x recap helper');
assert(capture.includes('check-e2e-run-artifacts.mjs'), 'capture policy must link the run artifact checker');
assert(capture.includes('click bloom'), 'capture policy must include mouse clicker/click bloom');
assert(runbook.includes('event row'), 'runbook runner prompt must require event rows');
assert(runbook.includes('regression commands'), 'runbook report must include regression commands');
assert(runbook.includes('desktop/mobile 2x cursor recap'), 'runbook report must include desktop/mobile 2x cursor recap');
assert(dogfood.includes('Artifact Checker'), 'dogfood must define artifact checker expectations');
assert(dogfood.includes('check-e2e-run-artifacts.mjs'), 'dogfood must use the run artifact checker');
assert(dogfood.includes('desktop and mobile 2x videos'), 'dogfood must require desktop/mobile 2x videos');
assert(!/Skill Eval|gpt-5\\.4-mini|model eval/i.test(dogfood), 'dogfood reference must not contain skill-eval guidance');

for (const rel of requiredTemplates) {
  const fullPath = path.join(skillDir, rel);
  assert(fs.existsSync(fullPath), `${rel} is missing`);
}
for (const rel of requiredScripts) {
  const fullPath = path.join(skillDir, rel);
  assert(fs.existsSync(fullPath), `${rel} is missing`);
}

if (failures.length) {
  console.error(failures.map((failure) => `FAIL ${failure}`).join('\n'));
  process.exit(1);
}

console.log('PASS e2e skill checks');
console.log(`SKILL.md lines: ${lineCount(skill)}`);
for (const rel of requiredRefs) {
  console.log(`${rel} lines: ${lineCount(read(rel))}`);
}
