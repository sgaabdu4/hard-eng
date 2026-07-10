#!/usr/bin/env node
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { state as stageState } from './helpers/he-state-stage-fixture.mjs';

const repo = path.resolve(new URL('..', import.meta.url).pathname);
const script = path.join(repo, 'scripts', 'he-state.mjs');
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'he-state-ui-'));
spawnSync('git', ['init', '-q', '-b', 'main'], { cwd: tmp, encoding: 'utf8' });
const png = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=', 'base64');
const grillQuestion = `Q1: Which UI option should ship?

Meaning: Pick the visible UI direction before implementation.
Why it matters: The implementation must reuse the chosen components.
Suggested default: A - it reuses the existing card and filter primitives.

Options:
A) Card-first flow
B) Table-first flow
C) Not sure - use the default.

Reply: A/B/C, "use default", "not sure", "skip for now", or your own answer.`;

for (const [relativePath, content] of [
  ['src/components/demo-ui.stories.tsx', 'export const DemoUi = {};\n'],
  ['lib/reminders/reminders_entry_preview.dart', 'void main() {}\n'],
  ['docs/planning/demo/ui-review-receipt.md', 'A approved\nA card-first flow\nB table-first flow\ndocs/planning/demo/screenshots/card-first.png\ndocs/planning/demo/screenshots/table-first.png\n'],
  ['docs/planning/demo/ui-decisions.md', 'A card-first flow\nB table-first flow\n'],
  ['docs/planning/demo/components.md', 'Card\nFilterBar\n'],
  ['docs/planning/demo/plan.md', '# Plan\n\n## Source inventory\n\nNo source brief or specification was registered.\n'],
  ['tests/he-state-ui-decision.test.mjs', 'export const valid = true;\n'],
]) {
  const target = path.join(tmp, relativePath);
  fs.mkdirSync(path.dirname(target), { recursive: true });
  fs.writeFileSync(target, content);
}
for (const relativePath of [
  'docs/planning/demo/screenshots/card-first.png',
  'docs/planning/demo/screenshots/table-first.png',
]) {
  const target = path.join(tmp, relativePath);
  fs.mkdirSync(path.dirname(target), { recursive: true });
  fs.writeFileSync(target, png);
}
const uiPresentation = {
  channel: 'user-opened-review-surface',
  tool: 'browser',
  eventId: 'browser-event-demo-0003',
  eventPath: 'docs/planning/demo/ui-presentation-event.json',
  presentedAt: '2026-07-10T10:00:00.000Z',
  approvedAt: '2026-07-10T10:01:00.000Z',
  surfaceOpened: true,
  visualsIncluded: true,
  questionIncluded: true,
  approvalAfterPresentation: true,
};
const fixtureDigest = (relativePath) => createHash('sha256').update(fs.readFileSync(path.join(tmp, relativePath))).digest('hex');
fs.writeFileSync(path.join(tmp, uiPresentation.eventPath), `${JSON.stringify({
  schema: 'ui-presentation/v1',
  eventId: uiPresentation.eventId,
  tool: uiPresentation.tool,
  channel: uiPresentation.channel,
  surfacePath: 'src/components/demo-ui.stories.tsx',
  surfaceUrl: 'http://localhost:6006/?path=/story/demo-ui--card-first',
  surfaceSha256: fixtureDigest('src/components/demo-ui.stories.tsx'),
  questionText: grillQuestion,
  screenshotSha256: {
    'docs/planning/demo/screenshots/card-first.png': fixtureDigest('docs/planning/demo/screenshots/card-first.png'),
    'docs/planning/demo/screenshots/table-first.png': fixtureDigest('docs/planning/demo/screenshots/table-first.png'),
  },
  presentedAt: uiPresentation.presentedAt,
  approval: { decision: 'A approved', selectedOption: 'A card-first flow', approvedAt: uiPresentation.approvedAt },
}, null, 2)}\n`);

function materializePresentationEvent(state) {
  const current = state?.planReadiness?.uiReview?.receipt;
  const presentation = current?.presentation;
  if (!presentation?.eventPath || !current.artifactPath || !fs.existsSync(path.join(tmp, current.artifactPath))) return;
  const screenshotPaths = (current.screenshotPaths || []).filter((relativePath) => fs.existsSync(path.join(tmp, relativePath)));
  const event = {
    schema: 'ui-presentation/v1',
    eventId: presentation.eventId,
    tool: presentation.tool,
    channel: presentation.channel,
    surfacePath: current.artifactPath,
    surfaceUrl: current.surfaceUrl || '',
    surfaceSha256: fixtureDigest(current.artifactPath),
    questionText: current.questionText,
    screenshotSha256: Object.fromEntries(screenshotPaths.map((relativePath) => [relativePath, fixtureDigest(relativePath)])),
    presentedAt: presentation.presentedAt,
    approval: { decision: current.userDecision, selectedOption: current.selectedOption, approvedAt: presentation.approvedAt },
  };
  const target = path.join(tmp, presentation.eventPath);
  fs.mkdirSync(path.dirname(target), { recursive: true });
  fs.writeFileSync(target, `${JSON.stringify(event, null, 2)}\n`);
}

function run(state, { materializeEvent = true } = {}) {
  if (materializeEvent) materializePresentationEvent(state);
  const file = path.join(tmp, `${Math.random().toString(36).slice(2)}.json`);
  fs.writeFileSync(file, `${JSON.stringify(state, null, 2)}\n`);
  return spawnSync('node', [script, 'validate', file], { encoding: 'utf8' });
}

const statePath = 'docs/planning/demo/he-state.json';
const receipt = { stage: 'he-plan', state: statePath, decision: 'PASS', ownerProof: ['src/ui/demo.tsx'], artifacts: ['docs/planning/demo/plan.md'], blocker: 'none', next: 'ready for /he:implement: yes', handoverPrompt: `Start a fresh Hard Eng stage session. Worktree: /tmp/hard-eng-worktree. Command: /he:implement. Stage: he-plan. State: ${statePath}. Next: ready for /he:implement: yes. Read ${statePath} first. Do not use the previous chat transcript.` };
const guardrail = (id, owner, command) => ({ id, stage: 'he-plan', kind: 'script', owner, command, status: 'passed', evidence: [`${id}: pass`], blocksPush: false });

function addImplementationScreenshotGuardrail(current) {
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
  });
  current.guardrails.push({
    id: 'implementation-ui-screenshots',
    stage: 'he-implement',
    kind: 'manual',
    owner: 'artifacts/ui-review/implementation',
    command: 'capture actual implementation screenshots for the real app route',
    status: 'passed',
    evidence: ['actual implementation screenshots captured before /he:verify: artifacts/ui-review/implementation/desktop.png'],
    blocksPush: false,
    sequence: 6,
    sequenceAfter: { 'owner-change': 4 },
  });
}

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
          presentation: { ...uiPresentation },
          userVisibleEvidence: ['Screenshots docs/planning/demo/screenshots/card-first.png and docs/planning/demo/screenshots/table-first.png were shown inline before the user approved A'],
          evidence: ['Storybook preview showed both options and user approved A'],
        },
        evidence: ['src/components/demo-ui.stories.tsx', 'docs/planning/demo/ui-review-receipt.md'],
      },
      sourceCoverage: {
        required: false,
        status: 'not_required',
        reason: 'No source brief or specification exists for this synthetic fixture.',
        evidenceRefs: ['docs/planning/demo/plan.md#source-inventory'],
        sources: [],
        items: [],
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

const tamperedPresentationEvent = valid();
tamperedPresentationEvent.planReadiness.uiReview.receipt.presentation.eventPath = 'docs/planning/demo/tampered-ui-presentation-event.json';
fs.writeFileSync(path.join(tmp, tamperedPresentationEvent.planReadiness.uiReview.receipt.presentation.eventPath), '{"schema":"ui-presentation/v1"}\n');
result = run(tamperedPresentationEvent, { materializeEvent: false });
assert.notEqual(result.status, 0, 'unbound tool-event provenance must block accepted UI review');
assert.match(result.stderr, /presentation event .*must bind|surfaceSha256|screenshotSha256|approval must bind/i);

const missingScreenshotArtifact = valid();
missingScreenshotArtifact.planReadiness.uiReview.receipt.screenshotPaths[1] = 'docs/planning/demo/screenshots/table-first-fabricated.png';
missingScreenshotArtifact.planReadiness.uiReview.receipt.userVisibleEvidence = [
  'Screenshots docs/planning/demo/screenshots/card-first.png and docs/planning/demo/screenshots/table-first-fabricated.png were shown inline before the user approved A',
];
result = run(missingScreenshotArtifact);
assert.notEqual(result.status, 0, 'missing screenshot files must block accepted UI review');
assert.match(result.stderr, /screenshotPaths.*does not exist/i);

const missingReviewSurface = valid();
missingReviewSurface.planReadiness.uiReview.reviewSurfacePath = 'src/components/missing-ui.stories.tsx';
missingReviewSurface.planReadiness.uiReview.receipt.artifactPath = 'src/components/missing-ui.stories.tsx';
result = run(missingReviewSurface);
assert.notEqual(result.status, 0, 'missing review surfaces must block accepted UI review');
assert.match(result.stderr, /artifactPath.*does not exist/i);

const unboundReceiptPath = path.join(tmp, 'docs/planning/demo/unbound-ui-review-receipt.md');
fs.writeFileSync(unboundReceiptPath, '# UI review receipt\n');
const unboundReceipt = valid();
unboundReceipt.planReadiness.uiReview.receipt.receiptPath = 'docs/planning/demo/unbound-ui-review-receipt.md';
result = run(unboundReceipt);
assert.notEqual(result.status, 0, 'unrelated receipt files must not satisfy accepted UI review');
assert.match(result.stderr, /receiptPath must bind the decision, options, and screenshotPaths/);

const outsideProjectScreenshot = valid();
outsideProjectScreenshot.planReadiness.uiReview.receipt.screenshotPaths[0] = '../card-first.png';
outsideProjectScreenshot.planReadiness.uiReview.receipt.userVisibleEvidence = [
  'Screenshots ../card-first.png and docs/planning/demo/screenshots/table-first.png were shown inline before the user approved A',
];
result = run(outsideProjectScreenshot);
assert.notEqual(result.status, 0, 'screenshot paths outside the project must block accepted UI review');
assert.match(result.stderr, /screenshotPaths.*stay within the project root/i);

const fakeImagePath = path.join(tmp, 'docs/planning/demo/screenshots/table-first-text.png');
fs.writeFileSync(fakeImagePath, 'not an image\n');
const fakeImageArtifact = valid();
fakeImageArtifact.planReadiness.uiReview.receipt.screenshotPaths[1] = 'docs/planning/demo/screenshots/table-first-text.png';
fakeImageArtifact.planReadiness.uiReview.receipt.userVisibleEvidence = [
  'Screenshots docs/planning/demo/screenshots/card-first.png and docs/planning/demo/screenshots/table-first-text.png were shown inline before the user approved A',
];
result = run(fakeImageArtifact);
assert.notEqual(result.status, 0, 'non-image screenshot files must block accepted UI review');
assert.match(result.stderr, /valid PNG, JPEG, or WebP image/);

const signatureOnlyImagePath = path.join(tmp, 'docs/planning/demo/screenshots/table-first-signature.png');
fs.writeFileSync(signatureOnlyImagePath, Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]));
const signatureOnlyImageArtifact = valid();
signatureOnlyImageArtifact.planReadiness.uiReview.receipt.screenshotPaths[1] = 'docs/planning/demo/screenshots/table-first-signature.png';
signatureOnlyImageArtifact.planReadiness.uiReview.receipt.userVisibleEvidence = [
  'Screenshots docs/planning/demo/screenshots/card-first.png and docs/planning/demo/screenshots/table-first-signature.png were shown inline before the user approved A',
];
result = run(signatureOnlyImageArtifact);
assert.notEqual(result.status, 0, 'signature-only image files must not prove UI review screenshots');
assert.match(result.stderr, /valid PNG, JPEG, or WebP image/);

function removePngChunk(bytes, removedType) {
  const parts = [bytes.subarray(0, 8)];
  let offset = 8;
  while (offset + 12 <= bytes.length) {
    const length = bytes.readUInt32BE(offset);
    const end = offset + 12 + length;
    const type = bytes.subarray(offset + 4, offset + 8).toString('ascii');
    if (type !== removedType) parts.push(bytes.subarray(offset, end));
    offset = end;
  }
  return Buffer.concat(parts);
}

const noImageDataPath = path.join(tmp, 'docs/planning/demo/screenshots/table-first-empty-data.png');
fs.writeFileSync(noImageDataPath, removePngChunk(png, 'IDAT'));
const noImageDataArtifact = valid();
noImageDataArtifact.planReadiness.uiReview.receipt.screenshotPaths[1] = 'docs/planning/demo/screenshots/table-first-empty-data.png';
noImageDataArtifact.planReadiness.uiReview.receipt.userVisibleEvidence = [
  'Screenshots docs/planning/demo/screenshots/card-first.png and docs/planning/demo/screenshots/table-first-empty-data.png were shown inline before the user approved A',
];
noImageDataArtifact.planReadiness.uiReview.receipt.receiptPath = 'docs/planning/demo/ui-review-receipt-empty-data.md';
fs.writeFileSync(path.join(tmp, noImageDataArtifact.planReadiness.uiReview.receipt.receiptPath), 'A approved\nA card-first flow\nB table-first flow\ndocs/planning/demo/screenshots/card-first.png\ndocs/planning/demo/screenshots/table-first-empty-data.png\n');
result = run(noImageDataArtifact);
assert.notEqual(result.status, 0, 'PNG containers without image data must not prove UI review screenshots');
assert.match(result.stderr, /valid PNG, JPEG, or WebP image/);

const unboundScreenshotEvidence = valid();
unboundScreenshotEvidence.planReadiness.uiReview.receipt.userVisibleEvidence = [
  'Card-first and table-first screenshots were shown inline before the user approved A',
];
result = run(unboundScreenshotEvidence);
assert.notEqual(result.status, 0, 'presentation evidence must identify the verified screenshot files');
assert.match(result.stderr, /userVisibleEvidence.*reference every screenshotPaths/i);

const shownBeforeApprovedAfterThat = valid();
shownBeforeApprovedAfterThat.planReadiness.uiReview.receipt.userVisibleEvidence = [
  'Screenshots docs/planning/demo/screenshots/card-first.png and docs/planning/demo/screenshots/table-first.png were shown inline; after that, the user approved A',
];
result = run(shownBeforeApprovedAfterThat);
assert.equal(result.status, 0, result.stderr);

const flutterWidgetPreviewDeviceTarget = valid();
flutterWidgetPreviewDeviceTarget.planReadiness.uiReview.localhostUrl = '';
flutterWidgetPreviewDeviceTarget.planReadiness.uiReview.reviewSurfacePath = 'lib/reminders/reminders_entry_preview.dart';
Object.assign(flutterWidgetPreviewDeviceTarget.planReadiness.uiReview.receipt, {
  surfaceKind: 'flutter-widget-preview',
  artifactPath: 'lib/reminders/reminders_entry_preview.dart',
  deviceTarget: 'iPhone 15 simulator',
  evidence: ['Flutter Widget Previewer showed both options on iPhone 15 simulator and user approved A'],
});
delete flutterWidgetPreviewDeviceTarget.planReadiness.uiReview.receipt.surfaceUrl;
result = run(flutterWidgetPreviewDeviceTarget);
assert.equal(result.status, 0, result.stderr);

const flutterWidgetPreviewLoopback = valid();
flutterWidgetPreviewLoopback.planReadiness.uiReview.reviewSurfacePath = 'lib/reminders/reminders_entry_preview.dart';
Object.assign(flutterWidgetPreviewLoopback.planReadiness.uiReview.receipt, {
  surfaceKind: 'flutter-widget-preview',
  surfaceUrl: 'http://localhost:9100/#/reminders-entry-preview',
  artifactPath: 'lib/reminders/reminders_entry_preview.dart',
  evidence: ['Flutter Widget Previewer localhost surface showed both options and user approved A'],
});
delete flutterWidgetPreviewLoopback.planReadiness.uiReview.receipt.deviceTarget;
result = run(flutterWidgetPreviewLoopback);
assert.equal(result.status, 0, result.stderr);

const flutterWidgetPreviewMissingSurface = valid();
Object.assign(flutterWidgetPreviewMissingSurface.planReadiness.uiReview.receipt, {
  surfaceKind: 'flutter-widget-preview',
  artifactPath: 'lib/reminders/reminders_entry_preview.dart',
});
delete flutterWidgetPreviewMissingSurface.planReadiness.uiReview.receipt.surfaceUrl;
delete flutterWidgetPreviewMissingSurface.planReadiness.uiReview.receipt.deviceTarget;
result = run(flutterWidgetPreviewMissingSurface);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /surfaceUrl or deviceTarget is required for flutter-widget-preview review/);

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
  [(state) => { delete state.planReadiness.uiReview.receipt.surfaceUrl; state.planReadiness.uiReview.receipt.deviceTarget = 'iPhone 15 simulator'; }, /surfaceUrl must be a localhost URL for storybook/],
  [(state) => { state.planReadiness.uiReview.receipt.optionsShown = ['A only']; }, /optionsShown must include at least two UI options/],
  [(state) => { delete state.planReadiness.uiReview.receipt.rejectedOptions; }, /rejectedOptions must include at least one rejected UI option/],
  [(state) => { state.planReadiness.uiReview.receipt.rejectedOptions = []; }, /rejectedOptions must include at least one rejected UI option/],
  [(state) => { delete state.planReadiness.uiReview.receipt.screenshotPaths; }, /screenshotPaths must be non-empty string\[\]/],
  [(state) => { state.planReadiness.uiReview.receipt.screenshotPaths = []; }, /screenshotPaths must include at least 1 item/],
  [(state) => { state.planReadiness.uiReview.receipt.screenshotPaths = ['docs/planning/demo/screenshots/card-first.png']; }, /screenshotPaths must include screenshots for every UI option shown/],
  [(state) => { state.planReadiness.uiReview.receipt.screenshotPaths = ['docs/planning/demo/screenshots/card-first.png', 'docs/planning/demo/screenshots/card-first.png']; }, /screenshotPaths must be distinct/],
  [(state) => { state.planReadiness.uiReview.receipt.screenshotPaths = ['docs/planning/demo/screenshots/card-first-desktop.png', 'docs/planning/demo/screenshots/card-first-mobile.png']; }, /screenshotPaths must reference every UI option shown/],
  [(state) => { delete state.planReadiness.uiReview.receipt.presentation; }, /presentation is required for accepted/],
  [(state) => { state.planReadiness.uiReview.receipt.presentation.channel = 'commentary'; }, /presentation.channel must be user-opened-review-surface/],
  [(state) => { state.planReadiness.uiReview.receipt.presentation.tool = 'agent-text'; }, /presentation.tool must identify browser, chrome, or computer-use/],
  [(state) => { state.planReadiness.uiReview.receipt.presentation.eventPath = ''; }, /presentation.eventPath is required/],
  [(state) => { state.planReadiness.uiReview.receipt.presentation.approvedAt = '2026-07-10T09:59:00.000Z'; }, /presentation approvedAt must be after presentedAt/],
  [(state) => { state.planReadiness.uiReview.receipt.presentation.surfaceOpened = false; }, /presentation.surfaceOpened must be true/],
  [(state) => { state.planReadiness.uiReview.receipt.presentation.visualsIncluded = false; }, /presentation.visualsIncluded must be true/],
  [(state) => { state.planReadiness.uiReview.receipt.presentation.questionIncluded = false; }, /presentation.questionIncluded must be true/],
  [(state) => { state.planReadiness.uiReview.receipt.presentation.approvalAfterPresentation = false; }, /presentation.approvalAfterPresentation must be true/],
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

const verifyUiReviewDroppedReceipt = stageState('he-verify');
verifyUiReviewDroppedReceipt.planReadiness = JSON.parse(JSON.stringify(valid().planReadiness));
verifyUiReviewDroppedReceipt.planReadiness.uiReview.decisionTool = 'none';
verifyUiReviewDroppedReceipt.planReadiness.uiReview.receipt = null;
addImplementationScreenshotGuardrail(verifyUiReviewDroppedReceipt);
result = run(verifyUiReviewDroppedReceipt);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /next\.ready true requires required UI review decisionTool ui-review-receipt/);

const verifyUiReviewDroppedScreenshotProof = stageState('he-verify');
verifyUiReviewDroppedScreenshotProof.planReadiness = JSON.parse(JSON.stringify(valid().planReadiness));
delete verifyUiReviewDroppedScreenshotProof.planReadiness.uiReview.receipt.screenshotPaths;
addImplementationScreenshotGuardrail(verifyUiReviewDroppedScreenshotProof);
result = run(verifyUiReviewDroppedScreenshotProof);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /next\.ready true requires required UI review receipt with screenshotPaths and userVisibleEvidence/);

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
