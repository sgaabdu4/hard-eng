#!/usr/bin/env node
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';

const repo = path.resolve(new URL('../..', import.meta.url).pathname);
const read = (file) => fs.readFileSync(path.join(repo, file), 'utf8');

const license = read('LICENSE');
assert.match(license, /Copyright \(c\) 2026 Matt Pocock/);
assert.match(license, /mattpocock\/skills/);

const prototypeUi = read('skills/prototype/UI.md');
assert.match(prototypeUi, /gate variant selection/i);
assert.match(prototypeUi, /production.*(?:existing page|not found|404)/i);
assert.match(prototypeUi, /explicit.*deletion|deletion.*explicit/i);

const prototypeLogic = read('skills/prototype/LOGIC.md');
assert.match(prototypeLogic, /production.*behavior tests|behavior tests.*production/i);
assert.match(prototypeLogic, /error handling/i);

const architectureReport = read('skills/improve-codebase-architecture/HTML-REPORT.md');
const architectureWorkflow = read('skills/improve-codebase-architecture/references/workflow.md');
for (const text of [architectureReport, architectureWorkflow]) {
  assert.doesNotMatch(text, /https?:\/\//);
  assert.doesNotMatch(text, /<script\b|securityLevel:\s*["']loose/i);
  assert.match(text, /inline CSS/i);
  assert.match(text, /static inline SVG/i);
}

const deepening = read('skills/codebase-design/references/deepening.md');
assert.match(deepening, /explicit(?:ly)? approved deletion scope/i);
assert.match(deepening, /failure proof/i);

const reviewContract = read('skills/code-review/references/two-axis-review.md');
assert.ok(reviewContract.indexOf('a path or spec content the user passed') < reviewContract.indexOf('issue or PR references'));
for (const evidence of ['git diff --cached', 'git diff`', 'git ls-files --others --exclude-standard']) {
  assert.match(reviewContract, new RegExp(evidence.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')));
}

const triageWorkflow = read('skills/triage/references/workflow.md');
assert.match(triageWorkflow, /docs\/agents\/issue-tracker\.md/);
assert.match(triageWorkflow, /docs\/agents\/triage-labels\.md/);

const preCommit = read('skills/setup-pre-commit/SKILL.md');
assert.match(preCommit, /explicit.*pre-commit|pre-commit.*explicit/i);
assert.doesNotMatch(preCommit.match(/^description:.*$/m)?.[0] || '', /Prettier, typecheck, test/);

const tdd = read('skills/tdd/SKILL.md');
assert.doesNotMatch(tdd.match(/^description:.*$/m)?.[0] || '', /integration tests/i);
assert.match(tdd, /Load `references\/workflow\.md`/);
assert.doesNotMatch(tdd, /## Rules of the loop/);

const routeMap = read('skills/workflow-help/references/route-map.md');
for (const stage of ['he-plan', 'he-implement', 'he-verify', 'he-ship', 'he-learn']) {
  assert.match(routeMap, new RegExp(`\\.\\.\\/\\.\\.\\/${stage}\\/references\\/stage-contract\\.md`));
}
assert.doesNotMatch(routeMap, /then `node "\$HOME\/\.agents\/scripts\/format-hard-eng\.mjs"/);
assert.match(routeMap, /current.*research.*`research`.*web\/search/i);
assert.match(routeMap, /simple.*(?:open|navigation).*browser/i);

const product = read('PRODUCT.md');
assert.match(product, /Canonical routing ownership/i);
assert.match(product, /`to-prd`.*`to-spec`[\s\S]*`plan\.md`/);

const slices = read('skills/grill-me/modules/vertical-slices.md');
const trackerPublishing = read('skills/grill-me/references/tracker-publishing.md');
assert.match(slices, /references\/tracker-publishing\.md/);
for (const field of ['Source plan', 'User value', 'Dependencies', 'Acceptance criteria', 'Verification']) {
  assert.match(trackerPublishing, new RegExp(field, 'i'));
}

const routingDefinitions = read('tests/agents-md-routing/evals/run-evals.mjs');
assert.match(routingDefinitions, /avoidsSeparateTicketRequirement: does not require separate issue\/ticket artifacts as a prerequisite/);

console.log('review-findings-contract: pass');
