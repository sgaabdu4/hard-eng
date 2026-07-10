#!/usr/bin/env node
import assert from 'node:assert/strict';
import { materializeUiReviewArtifacts, run, state } from './helpers/he-state-stage-fixture.mjs';

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
      presentation: { channel: 'final-response', surfaceOpened: true, visualsIncluded: true, questionIncluded: true, approvalAfterPresentation: true },
      userVisibleEvidence: ['Screenshots docs/planning/demo/a.png and docs/planning/demo/b.png were shown inline before the user approved A'],
      evidence: ['Storybook preview accepted'],
    },
    evidence: ['docs/planning/demo/ui-review-receipt.md'],
  },
  sourceCoverage: {
    required: false,
    status: 'not_required',
    reason: 'No source brief or specification exists for this synthetic fixture.',
    evidenceRefs: ['tests/he-state-implementation-ui-screenshots.test.mjs#acceptedUiReview'],
    sources: [],
    items: [],
  },
  artifact: { status: 'accepted', paths: ['docs/planning/demo/plan.md'] },
};
materializeUiReviewArtifacts(acceptedUiReview);

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

function addInventoryProof(current, touchedStack) {
  current.guardrails.push({
    id: 'ssot-scan',
    stage: current.stage,
    kind: 'scanner',
    owner: 'scripts/check-ssot-guardrails.mjs',
    command: `node scripts/check-ssot-guardrails.mjs ${touchedStack}`,
    status: 'passed',
    evidence: [`SSOT owner ledger clean for ${touchedStack}`],
    blocksPush: false,
  });
  current.guardrails.push({
    id: 'fallow-audit',
    stage: current.stage,
    kind: 'scanner',
    owner: 'fallow',
    command: `fallow audit --dupes ${touchedStack}`,
    status: 'passed',
    evidence: [`Fallow found no duplicate groups for ${touchedStack}`],
    blocksPush: false,
  });
  current.guardrailInventory.requiredGuardrails = current.guardrailInventory.requiredGuardrails.map((guardrail) => {
    if (guardrail.id === 'ssot-scanners') return { id: 'ssot-scanners', status: 'required', guardrailId: 'ssot-scan', evidence: [`owner ledger checked for ${touchedStack}`] };
    if (guardrail.id === 'fallow') return { id: 'fallow', status: 'required', guardrailId: 'fallow-audit', evidence: [`Fallow found no duplicate groups for ${touchedStack}`] };
    return guardrail;
  });
}

function addOwnerLedger(current, ownerClasses) {
  current.subStages = current.subStages.map((subStage) => (
    subStage.id === 'ssot-owner-reuse'
      ? {
          ...subStage,
          evidence: ['SSOT reused: workflow-state and route owners; SSOT extended: none; new owners created: none'],
          ownerLedger: [
            { ownerClass: 'workflow-state', decision: 'reuse', owner: 'scripts/he-state.mjs', evidence: ['workflow-state owner reused'] },
            ...ownerClasses.map((ownerClass) => ({ ownerClass, decision: 'reuse', owner: `src/${ownerClass}`, evidence: [`${ownerClass} owner reused`] })),
          ],
        }
      : subStage
  ));
}

function addImplementationScreenshotGuardrail(current, overrides = {}) {
  current.guardrails.push({
    id: 'implementation-ui-screenshots',
    stage: 'he-implement',
    kind: 'manual',
    owner: 'artifacts/ui-review/feature/screenshots',
    command: 'capture actual implementation screenshots for the real app route',
    status: 'passed',
    evidence: [
      'actual implementation screenshots captured before /he:verify: artifacts/ui-review/feature/screenshots/desktop.png and artifacts/ui-review/feature/screenshots/mobile.png',
    ],
    blocksPush: false,
    sequence: 6,
    sequenceAfter: { 'owner-change': 4 },
    ...overrides,
  });
}

function addHistoricalImplementationProof(current, overrides = {}) {
  current.guardrails.push({
    id: 'implementation-proof',
    stage: 'he-implement',
    kind: 'test',
    owner: 'tests/owner.test.mjs',
    command: 'npm test -- owner',
    status: 'passed',
    evidence: ['post-change tests passed'],
    blocksPush: false,
    sequence: 5,
    ...overrides,
  });
}

let result = run(uiImplementState());
assert.notEqual(result.status, 0);
assert.match(result.stderr, /implementation-ui-screenshots/);

const withScreenshots = uiImplementState();
withScreenshots.guardrails.push({
  id: 'implementation-ui-screenshots',
  stage: 'he-implement',
  kind: 'manual',
  owner: 'artifacts/ui-review/feature/screenshots',
  command: 'capture actual implementation screenshots for the real app route',
  status: 'passed',
  evidence: [
    'actual implementation screenshots captured before /he:verify: artifacts/ui-review/feature/screenshots/desktop.png and artifacts/ui-review/feature/screenshots/mobile.png',
  ],
  blocksPush: false,
  sequence: 6,
});
result = run(withScreenshots);
assert.equal(result.status, 0, result.stderr);

for (const evidence of [
  'actual implementation screenshots shown before /he:verify: artifacts/ui-review/feature/screenshots/desktop.png',
  'actual implementation screenshots displayed before /he:verify: artifacts/ui-review/feature/screenshots/desktop.png',
]) {
  const displayOnlyScreenshots = uiImplementState();
  displayOnlyScreenshots.guardrails.push({
    id: 'implementation-ui-screenshots',
    stage: 'he-implement',
    kind: 'manual',
    owner: 'artifacts/ui-review/feature/screenshots',
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
  owner: 'artifacts/ui-review/feature/screenshots',
  command: 'capture actual implementation screenshots for the real app route',
  status: 'passed',
  evidence: [
    'actual implementation screenshots were not captured before /he:verify: artifacts/ui-review/feature/screenshots/desktop.png',
  ],
  blocksPush: false,
  sequence: 6,
});
result = run(negatedScreenshots);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /implementation-ui-screenshots/);

for (const evidence of [
  'will capture actual implementation screenshots before /he:verify: artifacts/ui-review/feature/screenshots/desktop.png',
  'actual implementation screenshots captured after /he:verify: artifacts/ui-review/feature/screenshots/desktop.png',
]) {
  const plannedOrLateScreenshots = uiImplementState();
  plannedOrLateScreenshots.guardrails.push({
    id: 'implementation-ui-screenshots',
    stage: 'he-implement',
    kind: 'manual',
    owner: 'artifacts/ui-review/feature/screenshots',
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
  owner: 'artifacts/ui-review/feature/screenshots',
  command: 'capture actual implementation screenshots for real localhost route artifacts/ui-review/feature/screenshots/desktop.png',
  status: 'passed',
  evidence: ['UI review command was listed'],
  blocksPush: false,
  sequence: 6,
});
result = run(commandOnlyScreenshots);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /implementation-ui-screenshots/);

const afterImplementationBeforeVerifyScreenshots = uiImplementState();
addImplementationScreenshotGuardrail(afterImplementationBeforeVerifyScreenshots, {
  evidence: ['actual implementation screenshots captured after implementation before /he:verify: artifacts/ui-review/feature/screenshots/desktop.png'],
});
result = run(afterImplementationBeforeVerifyScreenshots);
assert.equal(result.status, 0, result.stderr);

const staleScreenshots = uiImplementState();
staleScreenshots.guardrails.push({
  id: 'implementation-ui-screenshots',
  stage: 'he-implement',
  kind: 'manual',
  owner: 'artifacts/ui-review/feature/screenshots',
  command: 'capture actual implementation screenshots for the real app route',
  status: 'passed',
  evidence: ['actual implementation screenshot captured before /he:verify too early: artifacts/ui-review/feature/screenshots/desktop.png'],
  blocksPush: false,
  sequence: 4,
});
result = run(staleScreenshots);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /sequence after owner-change and implementation-proof/);

for (const laterStage of ['he-verify', 'he-ship']) {
  const missingLaterScreenshots = state(laterStage);
  missingLaterScreenshots.guardrailInventory.touchedStacks = ['public/mock-flow.html'];
  addInventoryProof(missingLaterScreenshots, 'public/mock-flow.html');
  result = run(missingLaterScreenshots);
  assert.notEqual(result.status, 0, laterStage);
  assert.match(result.stderr, /implementation-ui-screenshots/, laterStage);

  const lateStageScreenshots = state(laterStage);
  lateStageScreenshots.guardrailInventory.touchedStacks = ['public/mock-flow.html'];
  addInventoryProof(lateStageScreenshots, 'public/mock-flow.html');
  addImplementationScreenshotGuardrail(lateStageScreenshots, { stage: laterStage });
  result = run(lateStageScreenshots);
  assert.notEqual(result.status, 0, `${laterStage} screenshots added at current stage should fail`);
  assert.match(result.stderr, /he-implement guardrail implementation-ui-screenshots/, laterStage);

  const staleLaterScreenshots = state(laterStage);
  staleLaterScreenshots.guardrailInventory.touchedStacks = ['public/mock-flow.html'];
  addInventoryProof(staleLaterScreenshots, 'public/mock-flow.html');
  addHistoricalImplementationProof(staleLaterScreenshots, { sequence: 7 });
  addImplementationScreenshotGuardrail(staleLaterScreenshots);
  result = run(staleLaterScreenshots);
  assert.notEqual(result.status, 0, `${laterStage} stale he-implement screenshots should fail`);
  assert.match(result.stderr, /sequence after owner-change and implementation-proof/, laterStage);

  const backdatedScreenshots = state(laterStage);
  backdatedScreenshots.guardrailInventory.touchedStacks = ['public/mock-flow.html'];
  addInventoryProof(backdatedScreenshots, 'public/mock-flow.html');
  addImplementationScreenshotGuardrail(backdatedScreenshots, { sequenceAfter: undefined });
  result = run(backdatedScreenshots);
  assert.notEqual(result.status, 0, `${laterStage} backdated screenshots without preserved sequence evidence should fail`);
  assert.match(result.stderr, /sequence after owner-change and implementation-proof/, laterStage);

  const withLaterScreenshots = state(laterStage);
  withLaterScreenshots.guardrailInventory.touchedStacks = ['public/mock-flow.html'];
  addInventoryProof(withLaterScreenshots, 'public/mock-flow.html');
  addHistoricalImplementationProof(withLaterScreenshots);
  addImplementationScreenshotGuardrail(withLaterScreenshots);
  result = run(withLaterScreenshots);
  assert.equal(result.status, 0, `${laterStage}: ${result.stderr}`);
}

for (const touchedStack of [
  'public/mock-flow.html',
  'src/routes/+page.svelte',
  'src/components/ReviewPanel.vue',
  'lib/screens/home_screen.dart',
  'api routes, src/components/ExamplePanel.tsx',
  'api routes, button',
  'table rows',
  'visible rows',
  'row widget',
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

const backendApiRouteTouched = state('he-implement');
backendApiRouteTouched.guardrailInventory.touchedStacks = ['src/api/routes/comments.ts'];
backendApiRouteTouched.guardrails.push({
  id: 'ssot-scan',
  stage: 'he-implement',
  kind: 'scanner',
  owner: 'scripts/check-ssot-guardrails.mjs',
  command: 'node scripts/check-ssot-guardrails.mjs .',
  status: 'passed',
  evidence: ['SSOT owner ledger clean for api routes'],
  blocksPush: false,
});
backendApiRouteTouched.guardrails.push({
  id: 'fallow-audit',
  stage: 'he-implement',
  kind: 'scanner',
  owner: 'fallow',
  command: 'fallow audit --dupes src/api/routes/comments.ts',
  status: 'passed',
  evidence: ['Fallow found no duplicate groups for src/api/routes/comments.ts'],
  blocksPush: false,
});
backendApiRouteTouched.guardrailInventory.requiredGuardrails = backendApiRouteTouched.guardrailInventory.requiredGuardrails.map((guardrail) => {
  if (guardrail.id === 'ssot-scanners') return { id: 'ssot-scanners', status: 'required', guardrailId: 'ssot-scan', evidence: ['api route owner ledger checked'] };
  if (guardrail.id === 'fallow') return { id: 'fallow', status: 'required', guardrailId: 'fallow-audit', evidence: ['Fallow found no duplicate groups for src/api/routes/comments.ts'] };
  return guardrail;
});
backendApiRouteTouched.subStages = backendApiRouteTouched.subStages.map((subStage) => (
  subStage.id === 'ssot-owner-reuse'
    ? {
        ...subStage,
        evidence: ['SSOT reused: workflow-state, api, and screen owners; SSOT extended: none; new owners created: none'],
        ownerLedger: [
          { ownerClass: 'workflow-state', decision: 'reuse', owner: 'scripts/he-state.mjs', evidence: ['workflow-state owner reused'] },
          { ownerClass: 'api', decision: 'reuse', owner: 'src/api', evidence: ['api owner reused'] },
          { ownerClass: 'screen', decision: 'reuse', owner: 'src/api/routes', evidence: ['route owner reused without UI surface'] },
        ],
      }
    : subStage
));
result = run(backendApiRouteTouched);
assert.equal(result.status, 0, result.stderr);

for (const touchedStack of [
  'src/routes/+page.server.ts',
  'src/routes/+layout.server.ts',
]) {
  const serverRouteTouched = state('he-implement');
  serverRouteTouched.guardrailInventory.touchedStacks = [touchedStack];
  serverRouteTouched.guardrails.push({
    id: 'ssot-scan',
    stage: 'he-implement',
    kind: 'scanner',
    owner: 'scripts/check-ssot-guardrails.mjs',
    command: `node scripts/check-ssot-guardrails.mjs ${touchedStack}`,
    status: 'passed',
    evidence: [`SSOT owner ledger clean for ${touchedStack}`],
    blocksPush: false,
  });
  serverRouteTouched.guardrails.push({
    id: 'fallow-audit',
    stage: 'he-implement',
    kind: 'scanner',
    owner: 'fallow',
    command: `fallow audit --dupes ${touchedStack}`,
    status: 'passed',
    evidence: [`Fallow found no duplicate groups for ${touchedStack}`],
    blocksPush: false,
  });
  serverRouteTouched.guardrailInventory.requiredGuardrails = serverRouteTouched.guardrailInventory.requiredGuardrails.map((guardrail) => {
    if (guardrail.id === 'ssot-scanners') return { id: 'ssot-scanners', status: 'required', guardrailId: 'ssot-scan', evidence: [`server route owner ledger checked for ${touchedStack}`] };
    if (guardrail.id === 'fallow') return { id: 'fallow', status: 'required', guardrailId: 'fallow-audit', evidence: [`Fallow found no duplicate groups for ${touchedStack}`] };
    return guardrail;
  });
  serverRouteTouched.subStages = serverRouteTouched.subStages.map((subStage) => (
    subStage.id === 'ssot-owner-reuse'
      ? {
          ...subStage,
          evidence: ['SSOT reused: workflow-state, backend, server, and screen owners; SSOT extended: none; new owners created: none'],
          ownerLedger: [
            { ownerClass: 'workflow-state', decision: 'reuse', owner: 'scripts/he-state.mjs', evidence: ['workflow-state owner reused'] },
            { ownerClass: 'backend', decision: 'reuse', owner: 'src/routes', evidence: ['backend owner reused'] },
            { ownerClass: 'server', decision: 'reuse', owner: 'src/routes', evidence: ['server owner reused'] },
            { ownerClass: 'screen', decision: 'reuse', owner: 'src/routes', evidence: ['server route owner reused without UI surface'] },
          ],
        }
      : subStage
  ));
  result = run(serverRouteTouched);
  assert.equal(result.status, 0, `${touchedStack}: ${result.stderr}`);
}

for (const [touchedStack, ownerClasses] of [
  ['api routes', ['api', 'screen']],
  ['backend routes', ['backend', 'screen']],
  ['server routes', ['screen']],
]) {
  const backendRouteLabelTouched = state('he-implement');
  backendRouteLabelTouched.guardrailInventory.touchedStacks = [touchedStack];
  addInventoryProof(backendRouteLabelTouched, touchedStack);
  addOwnerLedger(backendRouteLabelTouched, ownerClasses);
  result = run(backendRouteLabelTouched);
  assert.equal(result.status, 0, `${touchedStack}: ${result.stderr}`);
}

for (const touchedStack of [
  'database rows',
  'TablesDB rows',
  'database table rows',
]) {
  const dataRowsTouched = state('he-implement');
  dataRowsTouched.guardrailInventory.touchedStacks = [touchedStack];
  addInventoryProof(dataRowsTouched, touchedStack);
  addOwnerLedger(dataRowsTouched, ['row']);
  result = run(dataRowsTouched);
  assert.equal(result.status, 0, `${touchedStack}: ${result.stderr}`);
}

console.log('he-state-implementation-ui-screenshots-test: pass');
