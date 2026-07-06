#!/usr/bin/env node
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { state as stageState } from './helpers/he-state-stage-fixture.mjs';

const repo = path.resolve(new URL('..', import.meta.url).pathname);
const script = path.join(repo, 'scripts', 'he-state.mjs');
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'he-state-ui-'));

function run(state) {
  const file = path.join(tmp, `${Math.random().toString(36).slice(2)}.json`);
  fs.writeFileSync(file, `${JSON.stringify(state, null, 2)}\n`);
  return spawnSync('node', [script, 'validate', file], { encoding: 'utf8' });
}

const statePath = 'docs/planning/demo/he-state.json';
const receipt = { stage: 'he-plan', state: statePath, decision: 'PASS', ownerProof: ['src/ui/demo.tsx'], artifacts: ['docs/planning/demo/plan.md'], blocker: 'none', next: 'ready for /he:implement: yes', handoverPrompt: `Start a fresh Hard Eng stage session. Worktree: /tmp/hard-eng-worktree. Command: /he:implement. Stage: he-plan. State: ${statePath}. Next: ready for /he:implement: yes. Read ${statePath} first. Do not use the previous chat transcript.` };
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
    subStages: ['context', 'grill-me', 'owner-proof', 'artifact-choice', 'risk-route', 'learning-capture', 'state-validation'].map((id) => ({ id, title: id, status: 'done', evidence: [id] })),
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
        lastQuestion: { status: 'none', format: 'grill-me/v1', text: '' },
      },
      uiReview: {
        required: true,
        status: 'accepted',
        liveTool: 'impeccable-live',
        decisionTool: 'ui-review-receipt',
        decisionPurpose: 'ui_flow',
        localhostUrl: 'http://localhost:6006/?path=/story/demo-ui--card-first',
        designSystemEvidence: ['DESIGN.md', 'docs/design/tokens.css'],
        sharedComponentEvidence: ['src/components/card.tsx'],
        reviewSurfacePath: 'src/components/demo-ui.stories.tsx',
        shownToUser: true,
        userResponse: 'A approved',
        tweaks: ['none requested'],
        alignment: { status: 'aligned', userConfirmed: true, noGuesswork: true, openDecisions: [], openUnknowns: [], evidence: ['UI review receipt accepted'] },
        receipt: {
          status: 'accepted',
          surfaceKind: 'storybook',
          surfaceUrl: 'http://localhost:6006/?path=/story/demo-ui--card-first',
          artifactPath: 'src/components/demo-ui.stories.tsx',
          receiptPath: 'docs/planning/demo/ui-review-receipt.md',
          savedChoicesPath: 'docs/planning/demo/ui-decisions.md',
          savedComponentsPath: 'docs/planning/demo/components.md',
          questionText: grillQuestion,
          userDecision: 'A approved',
          selectedOption: 'A card-first flow',
          optionsShown: ['A card-first flow', 'B table-first flow'],
          rejectedOptions: ['B table-first flow'],
          selectedComponents: ['Card', 'FilterBar'],
          screenshotPaths: ['docs/planning/demo/screenshots/card-first.png', 'docs/planning/demo/screenshots/table-first.png'],
          userVisibleEvidence: ['Screenshots docs/planning/demo/screenshots/card-first.png and docs/planning/demo/screenshots/table-first.png were shown inline before the user approved A'],
          evidence: ['Storybook preview showed both options and user approved A'],
        },
        evidence: ['src/components/demo-ui.stories.tsx', 'docs/planning/demo/ui-review-receipt.md'],
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

for (const [status, extra] of [
  ['pending', {}],
  ['shown', { optionsShown: ['A', 'B'], evidence: ['preview shown to user'] }],
  ['saved', { optionsShown: ['A', 'B'], savedChoicesPath: 'docs/planning/demo/ui-decisions.md', savedComponentsPath: 'docs/planning/demo/components.md', evidence: ['saved draft'] }],
]) {
  const state = valid();
  state.status = 'in_progress';
  state.next = { target: '/he:implement', ready: false, reason: 'UI decision still in progress' };
  const inProgressNext = 'ready for /he:implement: no';
  state.steps[0].receipt = {
    ...state.steps[0].receipt,
    next: inProgressNext,
    handoverPrompt: `Start a fresh Hard Eng stage session. Worktree: /tmp/hard-eng-worktree. Command: /he:implement. Stage: he-plan. State: ${statePath}. Next: ${inProgressNext}. Read ${statePath} first. Do not use the previous chat transcript.`,
  };
  state.planReadiness.uiReview.status = 'pending';
  state.planReadiness.uiReview.shownToUser = false;
  state.planReadiness.uiReview.userResponse = '';
  state.planReadiness.uiReview.tweaks = [];
  state.planReadiness.uiReview.alignment = { status: 'pending', userConfirmed: false, noGuesswork: false, openDecisions: ['Choose option'], openUnknowns: [], evidence: [] };
  state.planReadiness.uiReview.receipt = {
    status,
    surfaceKind: 'react-localhost',
    surfaceUrl: 'http://localhost:4173/demo-ui',
    artifactPath: 'docs/planning/demo/mock-flow.html',
    receiptPath: 'docs/planning/demo/ui-review-receipt.md',
    ...extra,
  };
  result = run(state);
  assert.equal(result.status, 0, `${status}: ${result.stderr}`);
}

for (const [mutate, expected] of [
  [(state) => { state.planReadiness.grillMe.alignment.openQuestions = ['Need option']; }, /openQuestions must be empty/],
  [(state) => { state.planReadiness.grillMe.questionPolicy.mode = 'bounded'; }, /questionPolicy\.mode must be unlimited_until_aligned/],
  [(state) => { state.planReadiness.artifact.status = 'parked'; }, /plan artifact to be accepted or not_required/],
  [(state) => { state.planReadiness.uiReview.localhostUrl = 'https://example.com/demo'; }, /localhostUrl must be a localhost URL/],
  [(state) => { state.planReadiness.uiReview.sharedComponentEvidence = []; }, /sharedComponentEvidence is required/],
  [(state) => { state.planReadiness.uiReview.alignment.openDecisions = ['Choose layout']; }, /openDecisions must be empty/],
  [(state) => { state.planReadiness.uiReview.receipt.surfaceUrl = 'https://example.com/demo'; }, /surfaceUrl must be a localhost URL/],
  [(state) => { state.planReadiness.uiReview.receipt.optionsShown = ['A only']; }, /optionsShown must include at least two UI options/],
  [(state) => { delete state.planReadiness.uiReview.receipt.rejectedOptions; }, /rejectedOptions must include at least one rejected UI option/],
  [(state) => { state.planReadiness.uiReview.receipt.rejectedOptions = []; }, /rejectedOptions must include at least one rejected UI option/],
  [(state) => { delete state.planReadiness.uiReview.receipt.screenshotPaths; }, /screenshotPaths must be non-empty string\[\]/],
  [(state) => { state.planReadiness.uiReview.receipt.screenshotPaths = []; }, /screenshotPaths must include at least 1 item/],
  [(state) => { state.planReadiness.uiReview.receipt.screenshotPaths = ['docs/planning/demo/screenshots/card-first.png']; }, /screenshotPaths must include screenshots for every UI option shown/],
  [(state) => { state.planReadiness.uiReview.receipt.screenshotPaths = ['docs/planning/demo/screenshots/card-first.png', 'docs/planning/demo/screenshots/card-first.png']; }, /screenshotPaths must be distinct/],
  [(state) => { state.planReadiness.uiReview.receipt.userVisibleEvidence = ['receipt saved in docs only']; }, /userVisibleEvidence must prove screenshots or visual artifacts were shown to the user/],
  [(state) => { state.planReadiness.uiReview.receipt.userVisibleEvidence = ['Screenshots docs/planning/demo/screenshots/card-first.png and table-first.png were not shown before acceptance']; }, /userVisibleEvidence must prove screenshots or visual artifacts were shown to the user/],
  [(state) => { state.planReadiness.uiReview.receipt.userVisibleEvidence = ['Screenshots docs/planning/demo/screenshots/card-first.png and table-first.png were shown after acceptance']; }, /userVisibleEvidence must prove screenshots or visual artifacts were shown to the user/],
  [(state) => { state.planReadiness.uiReview.receipt.userVisibleEvidence = ['Screenshots docs/planning/demo/screenshots/card-first.png and table-first.png will be shown before approval']; }, /userVisibleEvidence must prove screenshots or visual artifacts were shown to the user/],
  [(state) => { state.planReadiness.uiReview.receipt.selectedOption = 'C compact flow'; }, /selectedOption must be one of optionsShown/],
  [(state) => { state.planReadiness.uiReview.receipt.rejectedOptions = ['C compact flow']; }, /rejectedOptions must only include optionsShown entries/],
  [(state) => { state.planReadiness.uiReview.receipt.rejectedOptions = ['A card-first flow']; }, /selectedOption must not be in rejectedOptions/],
  [(state) => { state.planReadiness.uiReview.receipt.savedComponentsPath = ''; }, /savedComponentsPath is required/],
  [(state) => { state.planReadiness.grillMe.stages = [{ id: 'product', map: 'run', status: 'done', evidence: ['session_state.md'] }]; }, /cannot use UI review receipt unless Grill Me UI flow or visual design ran/],
]) {
  const state = valid();
  mutate(state);
  result = run(state);
  assert.notEqual(result.status, 0, `expected failure matching ${expected}`);
  assert.match(result.stderr, expected);
}

const appointmentRemindersNoRoute = valid();
appointmentRemindersNoRoute.feature = 'appointment-reminders';
appointmentRemindersNoRoute.steps = [{
  id: '1',
  title: 'Parked UI review',
  status: 'done',
  receipt: { ...receipt, decision: 'CONCERNS', next: 'ready for /he:implement: yes' },
}];
appointmentRemindersNoRoute.planReadiness.grillMe.stages = [
  { id: 'ui-flow', map: 'run', status: 'done', evidence: ['bottom nav entry and list-vs-calendar question answered'] },
  { id: 'visual-design', map: 'run', status: 'done', evidence: ['UI entry prompt answered'] },
];
appointmentRemindersNoRoute.planReadiness.uiReview = {
  ...appointmentRemindersNoRoute.planReadiness.uiReview,
  status: 'parked',
  reason: 'real Reminders route does not exist yet and no fallback mock was reviewed',
  decisionTool: 'none',
  shownToUser: false,
  userResponse: '',
  evidence: [],
  receipt: null,
};
result = run(appointmentRemindersNoRoute);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /requires UI review to be accepted/);
assert.match(result.stderr, /final stage receipt decision PASS/);

const pendingVerifyUiReview = stageState('he-verify');
pendingVerifyUiReview.planReadiness = JSON.parse(JSON.stringify(valid().planReadiness));
pendingVerifyUiReview.planReadiness.uiReview.status = 'pending';
result = run(pendingVerifyUiReview);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /next\.ready cannot be true while required UI review is not accepted/);

const pendingShipUiReview = stageState('he-ship');
pendingShipUiReview.planReadiness = JSON.parse(JSON.stringify(valid().planReadiness));
pendingShipUiReview.planReadiness.uiReview.status = 'pending';
result = run(pendingShipUiReview);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /next\.ready cannot be true while required UI review is not accepted/);

const selfSkippedGrillMe = valid();
selfSkippedGrillMe.planReadiness = {
  ...selfSkippedGrillMe.planReadiness,
  grillMe: {
    required: false,
    status: 'not_required',
    statePath: '',
    questionPolicy: { mode: 'unlimited_until_aligned', evidence: [] },
    alignment: { status: 'pending', userConfirmed: false, noGuesswork: false, openQuestions: [], openUnknowns: [], evidence: [] },
    stages: [{ id: 'product', map: 'skip', status: 'skipped', reason: 'agent decided Grill Me was not needed', evidence: ['agent decided'] }],
    lastQuestion: { status: 'none', format: 'grill-me/v1', text: '' },
  },
  uiReview: { required: false, status: 'not_required', liveTool: '', decisionTool: 'none', decisionPurpose: 'none', designSystemEvidence: [], sharedComponentEvidence: [], evidence: [], tweaks: [], receipt: null },
};
result = run(selfSkippedGrillMe);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /explicit user-approved Grill Me skip evidence/);

const userApprovedGrillMeSkip = JSON.parse(JSON.stringify(selfSkippedGrillMe));
userApprovedGrillMeSkip.planReadiness.grillMe.stages[0].reason = 'user approved skipping Grill Me because scope was already fixed';
userApprovedGrillMeSkip.planReadiness.grillMe.stages[0].evidence = ['user approved skip in planning thread'];
result = run(userApprovedGrillMeSkip);
assert.equal(result.status, 0, result.stderr);

const skippedGrillMePendingUiReview = valid();
skippedGrillMePendingUiReview.planReadiness.grillMe = {
  required: false,
  status: 'not_required',
  statePath: '',
  questionPolicy: { mode: 'unlimited_until_aligned', evidence: [] },
  alignment: { status: 'pending', userConfirmed: false, noGuesswork: false, openQuestions: [], openUnknowns: [], evidence: [] },
  stages: [{ id: 'ui-flow', map: 'run', status: 'done', evidence: ['agent self-certified UI flow'] }],
  lastQuestion: { status: 'none', format: 'grill-me/v1', text: '' },
};
skippedGrillMePendingUiReview.planReadiness.uiReview.status = 'pending';
skippedGrillMePendingUiReview.planReadiness.uiReview.shownToUser = false;
skippedGrillMePendingUiReview.planReadiness.uiReview.userResponse = '';
result = run(skippedGrillMePendingUiReview);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /requires UI review to be accepted/);
assert.match(result.stderr, /explicit user-approved Grill Me skip evidence/);

console.log('he-state-ui-decision-test: pass');
