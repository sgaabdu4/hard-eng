#!/usr/bin/env node
import assert from 'node:assert/strict';
import { run, state } from './helpers/he-state-stage-fixture.mjs';

const acceptedUiReview = {
  grillMe: {
    required: true,
    status: 'accepted',
    statePath: 'docs/planning/demo/session_state.md',
    questionPolicy: { mode: 'unlimited_until_aligned', evidence: ['asked until user approved'] },
    alignment: { status: 'aligned', userConfirmed: true, noGuesswork: true, openQuestions: [], openUnknowns: [], evidence: ['user confirmed UI choice'] },
    stages: [{ id: 'ui-flow', map: 'run', status: 'done', evidence: ['UI flow reviewed'] }],
    lastQuestion: { status: 'none', format: 'grill-me/v1', text: '' },
  },
  uiReview: {
    required: true,
    status: 'accepted',
    liveTool: 'impeccable-live',
    decisionTool: 'ui-review-receipt',
    decisionPurpose: 'ui_flow',
    localhostUrl: 'http://localhost:6006/demo',
    designSystemEvidence: ['DESIGN.md'],
    sharedComponentEvidence: ['src/components/card.tsx'],
    reviewSurfacePath: 'src/components/demo.stories.tsx',
    shownToUser: true,
    userResponse: 'A approved',
    tweaks: ['none requested'],
    alignment: { status: 'aligned', userConfirmed: true, noGuesswork: true, openDecisions: [], openUnknowns: [], evidence: ['UI review accepted'] },
    receipt: {
      status: 'accepted',
      surfaceKind: 'storybook',
      surfaceUrl: 'http://localhost:6006/demo',
      artifactPath: 'src/components/demo.stories.tsx',
      receiptPath: 'docs/planning/demo/ui-review-receipt.md',
      savedChoicesPath: 'docs/planning/demo/ui-decisions.md',
      savedComponentsPath: 'docs/planning/demo/components.md',
      questionText: 'Q1: Which UI option should ship?',
      userDecision: 'A approved',
      selectedOption: 'A card-first flow',
      optionsShown: ['A card-first flow', 'B table-first flow'],
      rejectedOptions: ['B table-first flow'],
      selectedComponents: ['Card'],
      screenshotPaths: ['docs/planning/demo/a.png', 'docs/planning/demo/b.png'],
      userVisibleEvidence: ['Screenshots docs/planning/demo/a.png and docs/planning/demo/b.png were shown inline before the user approved A'],
      evidence: ['Storybook preview accepted'],
    },
    evidence: ['docs/planning/demo/ui-review-receipt.md'],
  },
  artifact: { status: 'accepted', paths: ['docs/planning/demo/plan.md'] },
};

function uiImplementState() {
  const current = state('he-implement');
  current.planReadiness = JSON.parse(JSON.stringify(acceptedUiReview));
  current.subStages = current.subStages.map((subStage) => {
    if (subStage.id !== 'ssot-owner-reuse') return subStage;
    return {
      ...subStage,
      evidence: ['SSOT reused: UI component owner; SSOT extended: none; new owners created: none'],
      ownerLedger: [
        { ownerClass: 'workflow-state', decision: 'reuse', owner: 'scripts/he-state.mjs', evidence: ['workflow-state owner reused'] },
        { ownerClass: 'ui', decision: 'reuse', owner: 'src/ui', evidence: ['existing UI owner reused'] },
        { ownerClass: 'component', decision: 'reuse', owner: 'src/components', evidence: ['existing component owner reused'] },
      ],
    };
  });
  return current;
}

let result = run(uiImplementState());
assert.notEqual(result.status, 0);
assert.match(result.stderr, /implementation-ui-screenshots/);

const withScreenshots = uiImplementState();
withScreenshots.guardrails.push({
  id: 'implementation-ui-screenshots',
  stage: 'he-implement',
  kind: 'manual',
  owner: 'docs/e2e/feature/screenshots',
  command: 'capture actual implementation screenshots for the real app route',
  status: 'passed',
  evidence: [
    'actual implementation screenshots captured before /he:verify: docs/e2e/feature/screenshots/desktop.png and docs/e2e/feature/screenshots/mobile.png',
  ],
  blocksPush: false,
  sequence: 6,
});
result = run(withScreenshots);
assert.equal(result.status, 0, result.stderr);

for (const evidence of [
  'actual implementation screenshots shown before /he:verify: docs/e2e/feature/screenshots/desktop.png',
  'actual implementation screenshots displayed before /he:verify: docs/e2e/feature/screenshots/desktop.png',
]) {
  const displayOnlyScreenshots = uiImplementState();
  displayOnlyScreenshots.guardrails.push({
    id: 'implementation-ui-screenshots',
    stage: 'he-implement',
    kind: 'manual',
    owner: 'docs/e2e/feature/screenshots',
    command: 'capture actual implementation screenshots for the real app route',
    status: 'passed',
    evidence: [evidence],
    blocksPush: false,
    sequence: 6,
  });
  result = run(displayOnlyScreenshots);
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /implementation-ui-screenshots/);
}

const negatedScreenshots = uiImplementState();
negatedScreenshots.guardrails.push({
  id: 'implementation-ui-screenshots',
  stage: 'he-implement',
  kind: 'manual',
  owner: 'docs/e2e/feature/screenshots',
  command: 'capture actual implementation screenshots for the real app route',
  status: 'passed',
  evidence: [
    'actual implementation screenshots were not captured before /he:verify: docs/e2e/feature/screenshots/desktop.png',
  ],
  blocksPush: false,
  sequence: 6,
});
result = run(negatedScreenshots);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /implementation-ui-screenshots/);

for (const evidence of [
  'will capture actual implementation screenshots before /he:verify: docs/e2e/feature/screenshots/desktop.png',
  'actual implementation screenshots captured after /he:verify: docs/e2e/feature/screenshots/desktop.png',
]) {
  const plannedOrLateScreenshots = uiImplementState();
  plannedOrLateScreenshots.guardrails.push({
    id: 'implementation-ui-screenshots',
    stage: 'he-implement',
    kind: 'manual',
    owner: 'docs/e2e/feature/screenshots',
    command: 'capture actual implementation screenshots for the real app route',
    status: 'passed',
    evidence: [evidence],
    blocksPush: false,
    sequence: 6,
  });
  result = run(plannedOrLateScreenshots);
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /implementation-ui-screenshots/);
}

const commandOnlyScreenshots = uiImplementState();
commandOnlyScreenshots.guardrails.push({
  id: 'implementation-ui-screenshots',
  stage: 'he-implement',
  kind: 'manual',
  owner: 'docs/e2e/feature/screenshots',
  command: 'capture actual implementation screenshots for real localhost route docs/e2e/feature/screenshots/desktop.png',
  status: 'passed',
  evidence: ['UI review command was listed'],
  blocksPush: false,
  sequence: 6,
});
result = run(commandOnlyScreenshots);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /implementation-ui-screenshots/);

const staleScreenshots = uiImplementState();
staleScreenshots.guardrails.push({
  id: 'implementation-ui-screenshots',
  stage: 'he-implement',
  kind: 'manual',
  owner: 'docs/e2e/feature/screenshots',
  command: 'capture actual implementation screenshots for the real app route',
  status: 'passed',
  evidence: ['actual implementation screenshot captured before /he:verify too early: docs/e2e/feature/screenshots/desktop.png'],
  blocksPush: false,
  sequence: 4,
});
result = run(staleScreenshots);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /sequence after owner-change and implementation-proof/);

for (const touchedStack of [
  'public/mock-flow.html',
  'src/routes/+page.svelte',
  'src/components/ReviewPanel.vue',
  'lib/screens/home_screen.dart',
]) {
  const uiSurfaceTouched = state('he-implement');
  uiSurfaceTouched.guardrailInventory.touchedStacks = [touchedStack];
  result = run(uiSurfaceTouched);
  assert.notEqual(result.status, 0, touchedStack);
  assert.match(result.stderr, /implementation-ui-screenshots/, touchedStack);
}

const canonicalButtonTouched = state('he-implement');
canonicalButtonTouched.guardrailInventory.touchedStacks = ['button'];
canonicalButtonTouched.subStages = canonicalButtonTouched.subStages.map((subStage) => (
  subStage.id === 'ssot-owner-reuse'
    ? {
        ...subStage,
        evidence: ['SSOT reused: workflow-state and button owners; SSOT extended: none; new owners created: none'],
        ownerLedger: [
          {
            ownerClass: 'workflow-state',
            decision: 'reuse',
            owner: 'scripts/he-state.mjs',
            evidence: ['workflow-state owner reused'],
          },
          {
            ownerClass: 'button',
            decision: 'reuse',
            owner: 'src/components/Button.tsx',
            evidence: ['button owner reused'],
          },
        ],
      }
    : subStage
));
result = run(canonicalButtonTouched);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /implementation-ui-screenshots/);

const backendOnly = state('he-implement');
result = run(backendOnly);
assert.equal(result.status, 0, result.stderr);

console.log('he-state-implementation-ui-screenshots-test: pass');
