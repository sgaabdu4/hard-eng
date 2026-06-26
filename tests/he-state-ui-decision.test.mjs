#!/usr/bin/env node
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';

const repo = path.resolve(new URL('..', import.meta.url).pathname);
const script = path.join(repo, 'scripts', 'he-state.mjs');
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'he-state-ui-'));

function run(state) {
  const file = path.join(tmp, `${Math.random().toString(36).slice(2)}.json`);
  fs.writeFileSync(file, `${JSON.stringify(state, null, 2)}\n`);
  return spawnSync('node', [script, 'validate', file], { encoding: 'utf8' });
}

const receipt = { stage: 'he-plan', state: 'docs/planning/demo/he-state.json', decision: 'PASS', ownerProof: ['src/ui/demo.tsx'], artifacts: ['docs/planning/demo/plan.md'], blocker: 'none', next: 'ready for /he:implement: yes' };
const grillQuestion = `Q1: Which UI option should ship?

Meaning: Pick the visible UI direction before implementation.
Why it matters: The implementation must reuse the chosen components.
Suggested default: A - it reuses the existing card and filter primitives.

Options:
A) Card-first flow
B) Table-first flow
C) Not sure - use the default.

Reply: A/B/C, "use default", "not sure", "skip for now", or your own answer.`;
const guardrail = (id, owner, command) => ({ id, stage: 'he-plan', kind: 'script', owner, command, status: 'passed', evidence: [`${id}: pass`], blocksPush: false });

function valid() {
  return {
    schema: 'he-state/v1',
    feature: 'demo-ui',
    updatedAt: '2026-06-26T00:00:00.000Z',
    stage: 'he-plan',
    stageIndex: 1,
    status: 'ready',
    currentStep: 'handoff',
    next: { target: '/he:implement', ready: true, reason: 'plan passed' },
    steps: [{ id: '1', title: 'Align UI', status: 'done', receipt }],
    subStages: ['context', 'grill-me', 'owner-proof', 'artifact-choice', 'risk-route', 'state-validation'].map((id) => ({ id, title: id, status: 'done', evidence: [id] })),
    findings: [],
    guardrails: [
      guardrail('context-gate', 'scripts/check-project-context-gates.mjs', 'node "$HOME/.agents/scripts/check-project-context-gates.mjs" --require-all .'),
      guardrail('state-validation', 'scripts/he-state.mjs', 'node "$HOME/.agents/scripts/he-state.mjs" validate he-state.json'),
    ],
    context: {
      product: { path: 'PRODUCT.md', status: 'current' },
      design: { path: 'DESIGN.md', status: 'current' },
      tokenOwner: { path: 'docs/design/tokens.css', status: 'current' },
    },
    planReadiness: {
      grillMe: {
        required: true,
        status: 'accepted',
        statePath: 'docs/planning/demo/session_state.md',
        questionPolicy: { mode: 'unlimited_until_aligned', evidence: ['asked until user approved'] },
        alignment: { status: 'aligned', userConfirmed: true, noGuesswork: true, openQuestions: [], openUnknowns: [], evidence: ['user confirmed no open unknowns'] },
        stages: [{ id: 'ui-flow', map: 'run', status: 'done', evidence: ['session_state.md'] }],
        lastQuestion: { status: 'answered', format: 'grill-me/v1', text: grillQuestion, visibleText: grillQuestion },
      },
      uiReview: {
        required: true,
        status: 'accepted',
        liveTool: 'impeccable-live',
        decisionTool: 'lavish',
        decisionPurpose: 'ui_flow',
        localhostUrl: 'http://localhost:4173/demo-ui',
        designSystemEvidence: ['DESIGN.md', 'docs/design/tokens.css'],
        sharedComponentEvidence: ['src/components/card.tsx'],
        mockFlowPath: 'docs/planning/demo/mock-flow.html',
        shownToUser: true,
        userResponse: 'A approved',
        tweaks: ['none requested'],
        alignment: { status: 'aligned', userConfirmed: true, noGuesswork: true, openDecisions: [], openUnknowns: [], evidence: ['Lavish approval received'] },
        lavish: {
          decisionStatus: 'accepted',
          launchCommand: 'npx -y lavish-axi docs/planning/demo/mock-flow.html',
          pollCommand: 'npx -y lavish-axi poll docs/planning/demo/mock-flow.html',
          optionsPath: 'docs/planning/demo/ui-options.html',
          pollReceiptPath: 'docs/planning/demo/lavish-poll.md',
          savedChoicesPath: 'docs/planning/demo/ui-decisions.md',
          savedComponentsPath: 'docs/planning/demo/components.md',
          userDecision: 'A approved',
          selectedOption: 'A',
          optionsShown: ['A card-first flow', 'B table-first flow'],
          rejectedOptions: ['B table-first flow'],
          selectedComponents: ['Card', 'FilterBar'],
          evidence: ['poll returned user decision'],
        },
        evidence: ['docs/planning/demo/mock-flow.html', 'docs/planning/demo/lavish-poll.md'],
      },
      artifact: { status: 'accepted', paths: ['docs/planning/demo/plan.md'] },
    },
    agentWork: [],
    decisions: [],
    blockers: [],
  };
}

let result = run(valid());
assert.equal(result.status, 0, result.stderr);

for (const [decisionStatus, extra] of [
  ['pending', {}],
  ['polled', { optionsShown: ['A', 'B'], evidence: ['poll waiting for user'] }],
  ['saved', { optionsShown: ['A', 'B'], savedChoicesPath: 'docs/planning/demo/ui-decisions.md', savedComponentsPath: 'docs/planning/demo/components.md', evidence: ['saved draft'] }],
]) {
  const state = valid();
  state.status = 'in_progress';
  state.next = { target: '/he:implement', ready: false, reason: 'UI decision still in progress' };
  state.planReadiness.uiReview.status = 'pending';
  state.planReadiness.uiReview.shownToUser = false;
  state.planReadiness.uiReview.userResponse = '';
  state.planReadiness.uiReview.tweaks = [];
  state.planReadiness.uiReview.alignment = { status: 'pending', userConfirmed: false, noGuesswork: false, openDecisions: ['Choose option'], openUnknowns: [], evidence: [] };
  state.planReadiness.uiReview.lavish = {
    decisionStatus,
    launchCommand: 'npx -y lavish-axi docs/planning/demo/mock-flow.html',
    pollCommand: 'npx -y lavish-axi poll docs/planning/demo/mock-flow.html',
    optionsPath: 'docs/planning/demo/ui-options.html',
    pollReceiptPath: 'docs/planning/demo/lavish-poll.md',
    ...extra,
  };
  result = run(state);
  assert.equal(result.status, 0, `${decisionStatus}: ${result.stderr}`);
}

for (const [mutate, expected] of [
  [(state) => { state.planReadiness.grillMe.alignment.openQuestions = ['Need option']; }, /openQuestions must be empty/],
  [(state) => { state.planReadiness.grillMe.questionPolicy.mode = 'bounded'; }, /questionPolicy\.mode must be unlimited_until_aligned/],
  [(state) => { state.planReadiness.artifact.status = 'parked'; }, /plan artifact to be accepted or not_required/],
  [(state) => { state.planReadiness.uiReview.localhostUrl = 'https://example.com/demo'; }, /localhostUrl must be a localhost URL/],
  [(state) => { state.planReadiness.uiReview.sharedComponentEvidence = []; }, /sharedComponentEvidence is required/],
  [(state) => { state.planReadiness.uiReview.alignment.openDecisions = ['Choose layout']; }, /openDecisions must be empty/],
  [(state) => { state.planReadiness.uiReview.lavish.pollCommand = 'npx -y lavish-axi poll docs/planning/demo/mock-flow.html --timeout-ms 5000'; }, /pollCommand must be a no-timeout/],
  [(state) => { state.planReadiness.uiReview.lavish.optionsShown = ['A only']; }, /optionsShown must include at least two UI options/],
  [(state) => { state.planReadiness.uiReview.lavish.savedComponentsPath = ''; }, /savedComponentsPath is required/],
  [(state) => { state.planReadiness.grillMe.stages = [{ id: 'product', map: 'run', status: 'done', evidence: ['session_state.md'] }]; }, /cannot use Lavish unless Grill Me UI flow or visual design ran/],
]) {
  const state = valid();
  mutate(state);
  result = run(state);
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, expected);
}

console.log('he-state-ui-decision-test: pass');
