#!/usr/bin/env node
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { createHash } from 'node:crypto';

const repo = path.resolve(new URL('..', import.meta.url).pathname);
const validator = path.join(repo, 'scripts', 'he-state.mjs');
const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'he-source-coverage-'));
const sourcePath = path.join(directory, 'specification.md');
const sourceText = '# Specification\n\nRequirement one.\nRequirement two.\n\nContext only.';
fs.writeFileSync(sourcePath, sourceText);
for (const [relativePath, text] of [
  ['docs/planning/example/plan.md', '# Owner\n\n## Source register\n\n## Behavior 1\n\n## Decisions\n\n## Non-goals\n\n## Source review\n'],
  ['docs/planning/example/source-audit.md', '# Heading classification\n'],
  ['docs/planning/example/decision-record.md', '# Decision 2\n'],
  ['docs/planning/example/scope-evidence.md', '# Context only\n'],
  ['docs/planning/example/other-plan.md', '# Other behavior\n'],
  ['tests/example-behavior.test.mjs', 'export const case1 = true;\n'],
]) {
  const file = path.join(directory, relativePath);
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, text);
}
let stateFileCounter = 0;

function run(state) {
  stateFileCounter += 1;
  const statePath = path.join(directory, `${String(stateFileCounter).padStart(3, '0')}-he-state.json`);
  fs.writeFileSync(statePath, `${JSON.stringify(state, null, 2)}\n`);
  return spawnSync('node', [validator, 'validate', statePath], { cwd: directory, encoding: 'utf8' });
}

function digest(text) {
  return createHash('sha256').update(text).digest('hex');
}

function sourceCoverage(text = sourceText) {
  const lines = text.split(/\r\n|\n|\r/);
  return {
    required: true,
    status: 'complete',
    sources: [
      {
        id: 'primary-spec',
        kind: 'spec',
        path: sourcePath,
        revision: 'fixture-v1',
        sha256: digest(text),
        lineCount: lines.length,
        nonblankLineCount: lines.filter((line) => line.trim()).length,
      },
    ],
    items: [
      {
        id: 'SPAN-001',
        sourceId: 'primary-spec',
        sourceRef: `${sourcePath}#L1-L1`,
        startLine: 1,
        endLine: 1,
        status: 'non_normative',
        planRefs: ['docs/planning/example/plan.md#source-register'],
        evidenceRefs: ['docs/planning/example/source-audit.md#heading-classification'],
      },
      {
        id: 'SPAN-002',
        sourceId: 'primary-spec',
        sourceRef: `${sourcePath}#L3-L3`,
        startLine: 3,
        endLine: 3,
        status: 'covered',
        planRefs: ['docs/planning/example/plan.md#behavior-1'],
        evidenceRefs: ['tests/example-behavior.test.mjs#case-1'],
      },
      {
        id: 'SPAN-003',
        sourceId: 'primary-spec',
        sourceRef: `${sourcePath}#L4-L4`,
        startLine: 4,
        endLine: 4,
        status: 'overridden',
        planRefs: ['docs/planning/example/plan.md#decisions'],
        evidenceRefs: ['docs/planning/example/decision-record.md#decision-2'],
      },
      {
        id: 'SPAN-004',
        sourceId: 'primary-spec',
        sourceRef: `${sourcePath}#L6-L6`,
        startLine: 6,
        endLine: 6,
        status: 'not_applicable',
        planRefs: ['docs/planning/example/plan.md#non-goals'],
        evidenceRefs: ['docs/planning/example/scope-evidence.md#context-only'],
      },
    ],
  };
}

function noSourceCoverage() {
  return {
    required: false,
    status: 'not_required',
    reason: 'No source brief or specification exists for this plan.',
    evidenceRefs: ['docs/planning/example/plan.md#source-review'],
    sources: [],
    items: [],
  };
}

function planState(coverage = sourceCoverage()) {
  const statePath = 'docs/planning/example/he-state.json';
  const receipt = {
    stage: 'he-plan',
    state: statePath,
    decision: 'PASS',
    ownerProof: ['docs/planning/example/plan.md#owner'],
    artifacts: ['docs/planning/example/plan.md'],
    blocker: 'none',
    next: 'ready for /he:implement: yes',
    handoverPrompt: `Fresh session. Worktree: /tmp/example-worktree. Stage: he-plan. State: ${statePath}. Next: ready for /he:implement: yes. Read ${statePath} first.`,
  };
  const subStages = ['context', 'grill-me', 'owner-proof', 'artifact-choice', 'risk-route', 'learning-capture', 'state-validation'];
  return {
    schema: 'he-state/v1',
    feature: 'example-feature',
    updatedAt: '2026-07-10T00:00:00.000Z',
    stage: 'he-plan',
    stageIndex: 1,
    status: 'ready',
    currentStep: 'handoff',
    next: { target: '/he:implement', ready: true, reason: 'source coverage complete' },
    steps: [{ id: '1', title: 'Plan handoff', status: 'done', receipt }],
    subStages: subStages.map((id) => ({ id, title: id, status: 'done', evidence: [`${id} complete`], reason: '' })),
    findings: [],
    guardrails: [
      {
        id: 'context-gate',
        stage: 'he-plan',
        kind: 'script',
        owner: 'scripts/check-project-context-gates.mjs',
        command: 'node scripts/check-project-context-gates.mjs --require-all .',
        status: 'passed',
        evidence: ['context gate passed'],
        blocksPush: false,
      },
      {
        id: 'state-validation',
        stage: 'he-plan',
        kind: 'script',
        owner: 'scripts/he-state.mjs',
        command: 'node scripts/he-state.mjs validate docs/planning/example/he-state.json',
        status: 'passed',
        evidence: ['state validation passed'],
        blocksPush: false,
      },
    ],
    context: {
      product: { path: 'PRODUCT.md', status: 'current' },
      design: { path: 'DESIGN.md', status: 'current' },
      tokenOwner: { path: 'docs/design/tokens.css', status: 'current' },
    },
    planReadiness: {
      grillMe: {
        required: false,
        status: 'not_required',
        statePath: '',
        questionPolicy: { mode: 'unlimited_until_aligned', evidence: [] },
        alignment: { status: 'pending', userConfirmed: false, noGuesswork: false, openQuestions: [], openUnknowns: [], evidence: [] },
        stages: [
          {
            id: 'product-plan',
            map: 'skip',
            status: 'skipped',
            reason: 'Scope was already fixed',
            evidence: ['User explicitly approved skipping Grill Me for this synthetic fixture'],
          },
        ],
        lastQuestion: { status: 'none', format: 'grill-me/v1', text: '' },
      },
      uiReview: {
        required: false,
        status: 'not_required',
        liveTool: '',
        decisionTool: 'none',
        decisionPurpose: 'none',
        localhostUrl: '',
        designSystemEvidence: [],
        sharedComponentEvidence: [],
        reviewSurfacePath: '',
        shownToUser: false,
        userResponse: '',
        tweaks: [],
        evidence: [],
        receipt: null,
      },
      sourceCoverage: coverage,
      artifact: { status: 'accepted', paths: ['docs/planning/example/plan.md'] },
    },
    agentWork: [],
    decisions: [],
    blockers: [],
  };
}

let result = run(planState());
assert.equal(result.status, 0, result.stderr);

const omittedClause = sourceCoverage();
omittedClause.items.pop();
result = run(planState(omittedClause));
assert.notEqual(result.status, 0, 'omitted normative source item must block PASS');
assert.match(result.stderr, /sourceCoverage.*uncovered|source coverage.*gap/i);

const overlappingClause = sourceCoverage();
overlappingClause.items[2].startLine = 3;
overlappingClause.items[2].sourceRef = `${sourcePath}#L3-L4`;
result = run(planState(overlappingClause));
assert.notEqual(result.status, 0, 'overlapping source spans must block PASS');
assert.match(result.stderr, /sourceCoverage.*overlap/i);

for (const status of ['open', 'contradictory']) {
  const incomplete = sourceCoverage();
  incomplete.items[1].status = status;
  result = run(planState(incomplete));
  assert.notEqual(result.status, 0, `${status} source item must block PASS`);
  assert.match(result.stderr, new RegExp(`sourceCoverage.*${status}|source coverage.*${status}`, 'i'));
}

const inProgressAudit = planState(sourceCoverage());
inProgressAudit.status = 'in_progress';
inProgressAudit.currentStep = 'source-audit';
inProgressAudit.next.ready = false;
inProgressAudit.next.reason = 'source contradiction still needs resolution';
inProgressAudit.planReadiness.sourceCoverage.status = 'pending';
inProgressAudit.planReadiness.sourceCoverage.items[1].status = 'contradictory';
inProgressAudit.steps[0].receipt.next = 'source-audit';
inProgressAudit.steps[0].receipt.handoverPrompt = 'Fresh session. Worktree: /tmp/example-worktree. Stage: he-plan. State: docs/planning/example/he-state.json. Next: continue /he:plan source audit. Read docs/planning/example/he-state.json first.';
inProgressAudit.steps.push({ id: '2', title: 'Complete source audit', status: 'in_progress' });
result = run(inProgressAudit);
assert.equal(result.status, 0, `a stale intermediate PASS receipt must not be treated as the final ready handoff\n${result.stderr}`);

const missingPlanRefs = sourceCoverage();
missingPlanRefs.items[1].planRefs = [];
result = run(planState(missingPlanRefs));
assert.notEqual(result.status, 0, 'missing plan references must block PASS');
assert.match(result.stderr, /sourceCoverage.*planRefs/i);

const missingEvidenceRefs = sourceCoverage();
missingEvidenceRefs.items[1].evidenceRefs = [];
result = run(planState(missingEvidenceRefs));
assert.notEqual(result.status, 0, 'missing evidence references must block PASS');
assert.match(result.stderr, /sourceCoverage.*evidenceRefs/i);

const unresolvedPlanRef = sourceCoverage();
unresolvedPlanRef.items[1].planRefs = ['docs/planning/example/missing-plan.md#behavior-1'];
result = run(planState(unresolvedPlanRef));
assert.notEqual(result.status, 0, 'nonexistent plan references must block PASS');
assert.match(result.stderr, /sourceCoverage.*planRefs.*(?:does not exist|accepted plan artifact)/i);

const wrongPlanArtifact = sourceCoverage();
wrongPlanArtifact.items[1].planRefs = ['docs/planning/example/other-plan.md#other-behavior'];
result = run(planState(wrongPlanArtifact));
assert.notEqual(result.status, 0, 'plan references outside accepted plan artifacts must block PASS');
assert.match(result.stderr, /sourceCoverage.*planRefs.*accepted plan artifact/i);

const unresolvedEvidenceRef = sourceCoverage();
unresolvedEvidenceRef.items[1].evidenceRefs = ['tests/missing-behavior.test.mjs#case-1'];
result = run(planState(unresolvedEvidenceRef));
assert.notEqual(result.status, 0, 'nonexistent evidence references must block PASS');
assert.match(result.stderr, /sourceCoverage.*evidenceRefs.*does not exist/i);

const malformedPlanRef = sourceCoverage();
malformedPlanRef.items[1].planRefs = ['docs/planning/example/plan.md#%ZZ'];
result = run(planState(malformedPlanRef));
assert.notEqual(result.status, 0, 'malformed reference locators must block PASS without crashing');
assert.match(result.stderr, /sourceCoverage.*planRefs.*invalid encoded heading locator/i);

const changedSourceState = planState(sourceCoverage());
fs.writeFileSync(sourcePath, `${sourceText}\nChanged after audit.`);
result = run(changedSourceState);
assert.notEqual(result.status, 0, 'source changes after audit must block PASS');
assert.match(result.stderr, /sourceCoverage.*sha256|source coverage.*changed/i);
fs.writeFileSync(sourcePath, sourceText);

const missingSourceState = planState(sourceCoverage());
fs.renameSync(sourcePath, `${sourcePath}.missing`);
result = run(missingSourceState);
assert.notEqual(result.status, 0, 'missing source file must block PASS');
assert.match(result.stderr, /sourceCoverage.*cannot read source/i);
fs.renameSync(`${sourcePath}.missing`, sourcePath);

const absentCoverage = planState();
delete absentCoverage.planReadiness.sourceCoverage;
result = run(absentCoverage);
assert.notEqual(result.status, 0, 'missing sourceCoverage must block PASS');
assert.match(result.stderr, /sourceCoverage is required/i);

result = run(planState(noSourceCoverage()));
assert.equal(result.status, 0, result.stderr);

console.log('he-state-source-coverage-test: pass');
