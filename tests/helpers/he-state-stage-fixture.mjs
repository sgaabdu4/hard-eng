import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { createHash } from 'node:crypto';

const repo = path.resolve(new URL('../..', import.meta.url).pathname);
const script = path.join(repo, 'scripts', 'he-state.mjs');
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'he-state-stage-contract-'));
spawnSync('git', ['init', '-q', '-b', 'main'], { cwd: tmp, encoding: 'utf8' });
fs.mkdirSync(path.join(tmp, 'tests'), { recursive: true });
fs.writeFileSync(path.join(tmp, 'package.json'), `${JSON.stringify({
  scripts: {
    test: 'node --test tests/owner.test.mjs',
    'test:unit': 'node --test tests/unit.test.mjs',
    jest: 'jest',
    vitest: 'vitest',
    mutation: 'stryker run',
    'make-it-fail': 'node --test tests/make-it-fail.test.mjs',
  },
}, null, 2)}\n`);
fs.writeFileSync(path.join(tmp, 'tests', 'owner.test.mjs'), 'import "node:test";\n');
fs.writeFileSync(path.join(tmp, 'pyproject.toml'), '[tool.pytest.ini_options]\n');
fs.writeFileSync(path.join(tmp, 'go.mod'), 'module example.test/he-state\n');
fs.writeFileSync(path.join(tmp, 'Cargo.toml'), '[package]\nname = "he-state"\nversion = "0.0.0"\nedition = "2021"\n');
fs.writeFileSync(path.join(tmp, 'build.gradle'), 'tasks.register("test") {}\n');
fs.writeFileSync(path.join(tmp, 'pom.xml'), '<project />\n');
fs.writeFileSync(path.join(tmp, 'pubspec.yaml'), 'name: he_state\n');
fs.writeFileSync(path.join(tmp, 'Makefile'), 'test:\n\t@true\n');
const png = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=', 'base64');

export function materializeUiReviewArtifacts(value) {
  const receipt = value?.planReadiness?.uiReview?.receipt || value?.uiReview?.receipt;
  if (!receipt) return;
  for (const key of ['artifactPath', 'receiptPath', 'savedChoicesPath', 'savedComponentsPath']) {
    const relativePath = receipt[key];
    if (typeof relativePath !== 'string' || !relativePath || path.isAbsolute(relativePath) || relativePath.startsWith('..')) continue;
    const target = path.join(tmp, relativePath);
    fs.mkdirSync(path.dirname(target), { recursive: true });
    const content = key === 'receiptPath'
      ? [receipt.questionText, receipt.userDecision, receipt.selectedOption, ...(receipt.optionsShown || []), ...(receipt.rejectedOptions || []), ...(receipt.screenshotPaths || []), receipt.presentation?.eventId, receipt.presentation?.eventPath].join('\n')
      : key === 'savedChoicesPath'
        ? [receipt.selectedOption, ...(receipt.rejectedOptions || [])].join('\n')
        : key === 'savedComponentsPath'
          ? (receipt.selectedComponents || []).join('\n')
          : `${key}\n`;
    if (!fs.existsSync(target)) fs.writeFileSync(target, `${content}\n`);
  }
  for (const relativePath of receipt.screenshotPaths || []) {
    if (typeof relativePath !== 'string' || !relativePath || path.isAbsolute(relativePath) || relativePath.startsWith('..')) continue;
    const target = path.join(tmp, relativePath);
    fs.mkdirSync(path.dirname(target), { recursive: true });
    if (!fs.existsSync(target)) fs.writeFileSync(target, png);
  }
  const presentation = receipt.presentation;
  if (presentation?.eventPath) {
    const digest = (relativePath) => createHash('sha256').update(fs.readFileSync(path.join(tmp, relativePath))).digest('hex');
    const event = {
      schema: 'ui-presentation/v1',
      eventId: presentation.eventId,
      tool: presentation.tool,
      channel: presentation.channel,
      surfacePath: receipt.artifactPath,
      surfaceUrl: receipt.surfaceUrl || '',
      surfaceSha256: digest(receipt.artifactPath),
      questionText: receipt.questionText,
      screenshotSha256: Object.fromEntries((receipt.screenshotPaths || []).map((relativePath) => [relativePath, digest(relativePath)])),
      presentedAt: presentation.presentedAt,
      approval: { decision: receipt.userDecision, selectedOption: receipt.selectedOption, approvedAt: presentation.approvedAt },
    };
    const target = path.join(tmp, presentation.eventPath);
    fs.mkdirSync(path.dirname(target), { recursive: true });
    fs.writeFileSync(target, `${JSON.stringify(event, null, 2)}\n`);
  }
}

export function materializeImplementationScreenshots(value, bytes = png) {
  for (const guardrail of value?.guardrails || []) {
    if (guardrail?.id !== 'implementation-ui-screenshots') continue;
    const evidence = Array.isArray(guardrail.evidence) ? guardrail.evidence.join(' ') : '';
    for (const match of evidence.matchAll(/(?:^|[\s:(])([A-Za-z0-9_.\/-]+\.(?:png|jpe?g|webp))\b/gi)) {
      const target = path.join(tmp, match[1]);
      fs.mkdirSync(path.dirname(target), { recursive: true });
      fs.writeFileSync(target, bytes);
    }
  }
}

function materializePlanArtifacts(value) {
  for (const relativePath of value?.planReadiness?.artifact?.paths || []) {
    if (typeof relativePath !== 'string' || !relativePath || path.isAbsolute(relativePath) || relativePath.startsWith('..')) continue;
    const target = path.join(tmp, relativePath);
    fs.mkdirSync(path.dirname(target), { recursive: true });
    if (!fs.existsSync(target)) fs.writeFileSync(target, '# Plan\n\n## Source inventory\n\nNo source brief or specification was registered.\n');
  }
}

export const stages = {
  'he-implement': [2, '/he:verify', 'he-plan', ['owner-read', 'ssot-owner-reuse', 'test-first', 'owner-change', 'guardrails', 'learning-capture', 'state-update']],
  'he-verify': [3, '/he:ship', 'he-implement', ['tests', 'guardrails', 'reviews', 'fix-loop', 'learning-capture', 'state-update']],
  'he-ship': [4, 'loop-complete', 'he-verify', ['status', 'hooks', 'format-check', 'project-inventory', 'quality-gates', 'no-mistakes', 'pr-evidence', 'pr-review-threads', 'ci-or-skip', 'learning-capture', 'state-update']],
  'he-learn': [5, 'loop-complete', 'he-ship', ['learning-findings', 'durable-owner', 'proof', 'state-update']],
};

export function run(state) {
  materializePlanArtifacts(state);
  const file = path.join(tmp, `${Math.random().toString(36).slice(2)}.json`);
  fs.writeFileSync(file, `${JSON.stringify(state, null, 2)}\n`);
  return spawnSync('node', [script, 'validate', file], { encoding: 'utf8' });
}

export function receipt(stage, next) {
  const statePath = 'he-state.json';
  const command = next.match(/\/he:[a-z-]+|loop complete/i)?.[0] || next;
  return { stage, state: statePath, decision: 'PASS', ownerProof: ['proof'], artifacts: [], blocker: 'none', next, handoverPrompt: `Start a fresh Hard Eng stage session. Worktree: /tmp/hard-eng-worktree. Command: ${command}. Stage: ${stage}. State: ${statePath}. Next: ${next}. Read ${statePath} first. Do not use the previous chat transcript.` };
}

export const g = (id, stage, command, blocksPush = false) => ({
  id,
  stage,
  kind: 'script',
  owner: id,
  command,
  status: 'passed',
  evidence: [`${id}: pass`],
  blocksPush,
});

export const tq = (text) => `test-quality scenarios recorded; ${text}`;

export function guardrails(stage) {
  if (stage === 'he-implement') {
    return [
      { ...g('deterministic-owner-scan', stage, 'node scripts/find-deterministic-owner.mjs --json --root . owner'), sequence: 1 },
      { ...g('test-first-proof', stage, 'npm test -- owner'), kind: 'test', evidence: [tq('red-first failed as expected before owner-change')], sequence: 3 },
      { ...g('implementation-proof', stage, 'npm test -- owner'), kind: 'test', evidence: ['post-change tests passed'], sequence: 5 },
    ];
  }
  if (stage === 'he-verify') return [g('quality-gate', stage, 'node scripts/check-project-quality-gates.mjs --require-push-gate .', true)];
  if (stage === 'he-ship') return [
    { ...g('git-status', stage, 'git status --short', true), kind: 'manual', sequence: 1 },
    { ...g('worktree-ready', stage, 'scripts/ensure-worktree-ready.sh --check --require-pre-push .', true), sequence: 2 },
    { ...g('format-check', stage, 'node scripts/format-hard-eng.mjs --check .', true), sequence: 3 },
    { ...g('project-inventory', stage, 'node scripts/check-no-mistakes-projects.mjs .', true), sequence: 4 },
    { ...g('quality-gate', stage, 'node scripts/check-project-quality-gates.mjs --require-push-gate .', true), sequence: 5 },
    { ...g('no-mistakes', stage, 'no-mistakes axi run --intent "ship verified feature"', true), sequence: 6 },
    { ...g('pr-evidence', stage, 'node integrations/no-mistakes/scripts/repair-pr-evidence.mjs --pr 7', true), evidence: ['Current head: `abcdef1234567890abcdef1234567890abcdef12`; No open no-mistakes findings; PR evidence updated'], sequence: 7 },
    { ...g('pr-review-threads', stage, 'node integrations/no-mistakes/scripts/repair-pr-evidence.mjs --pr 7 --check-review-threads', true), evidence: ['No open GitHub review threads'], sequence: 8 },
    { ...g('ci-or-skip', stage, 'gh run view --json conclusion,status', true), evidence: ['CI passed'], sequence: 9 },
    { ...g('ship-currentness', stage, 'git rev-parse HEAD && git status --short', true), kind: 'manual', evidence: ['validated head: `abcdef1234567890abcdef1234567890abcdef12`; worktree clean after final proof'], sequence: 10 },
  ];
  return [];
}

export const inventoryIds = ['regex-scanners', 'git-hooks', 'lint-analyze-typecheck', 'ssot-scanners', 'fallow', 'react-doctor', 'repeat-mistake-prevention'];

export const quotedOrCommentedRunnerCommands = [
  'echo "&& npm test"',
  'echo "&& npm test "',
  'printf "; pytest"',
  'printf "; pytest "',
  "echo '# npm test'",
  'echo ok # && npm test',
  'echo ok;# && npm test',
];

export const assignmentSubstitutionRunnerCommands = [
  'FOO=$(echo npm test )',
  'FOO=`echo npm test `',
  'FOO=$(printf "; pytest")',
  'env FOO=$(echo npm test )',
];

export const unreachableConditionalRunnerCommands = [
  'false && npm test -- owner',
  'true || npm test -- owner',
  'exit 0; npm test -- owner',
  'return 0; npm test -- owner',
  'exec true; npm test -- owner',
  `if false
then
npm test -- owner
fi`,
  'npm --if-present test', 'npm run test --if-present', 'jest --passWithNoTests', 'go test -list .',
  '{ false; } && npm test -- owner', '{ exit 0; }; npm test -- owner', 'alias npm=true; npm test -- owner', 'hash -p /bin/true npm; npm test -- owner',
];

export function guardrailInventory(entries = {}) {
  return {
    touchedStacks: ['workflow-state'],
    requiredGuardrails: inventoryIds.map((id) => entries[id] || { id, status: 'not_applicable', reason: `${id} not touched`, evidence: ['guardrail inventory reviewed'] }),
  };
}

export function ssotOwnerLedger() {
  return [
    {
      ownerClass: 'workflow-state',
      decision: 'reuse',
      owner: 'scripts/he-state.mjs',
      evidence: ['workflow-state owner reused for state validation'],
    },
  ];
}

export function planReadiness() {
  return {
    grillMe: {
      required: false,
      status: 'not_required',
      statePath: '',
      questionPolicy: { mode: 'unlimited_until_aligned', evidence: [] },
      alignment: { status: 'pending', userConfirmed: false, noGuesswork: false, openQuestions: [], openUnknowns: [], evidence: [] },
      stages: [{ id: 'product-plan', map: 'skip', status: 'skipped', reason: 'Scope was fixed for this synthetic fixture.', evidence: ['user approved skipping Grill Me for this synthetic fixture'] }],
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
    sourceCoverage: {
      required: false,
      status: 'not_required',
      reason: 'No source brief or specification exists for this synthetic fixture.',
      evidenceRefs: ['docs/planning/demo/plan.md#source-inventory'],
      sources: [],
      items: [],
    },
    artifact: { status: 'accepted', paths: ['docs/planning/demo/plan.md'] },
  };
}

export function state(stage) {
  const [stageIndex, target, fromStage, subStageIds] = stages[stage];
  return {
    schema: 'he-state/v1',
    feature: 'stage-contract',
    updatedAt: '2026-06-26T00:00:00.000Z',
    stage,
    stageIndex,
    status: 'ready',
    currentStep: 'handoff',
    next: { target, ready: true, reason: 'contract proof clean' },
    steps: [{ id: '1', title: 'Stage proof', status: 'done', receipt: receipt(stage, target) }],
    subStages: subStageIds.map((id, index) => ({
      id,
      title: id,
      status: 'done',
      evidence: [id === 'ssot-owner-reuse' ? 'SSOT reused: workflow-state owner; SSOT extended: none; new owners created: none' : id],
      ...(id === 'ssot-owner-reuse' ? { ownerLedger: ssotOwnerLedger() } : {}),
      sequence: index + 1,
    })),
    findings: stage === 'he-learn' ? [{ id: 'learn-1', stage: 'he-ship', summary: 'Durable guard added', ownerStage: 'he-learn', repairType: 'learning', ownerProof: ['guard'], artifacts: [], status: 'fixed' }] : [],
    guardrails: guardrails(stage),
    guardrailInventory: ['he-implement', 'he-verify', 'he-ship'].includes(stage) ? guardrailInventory() : undefined,
    entryGate: { fromStage, decision: 'PASS', statePath: 'prior-he-state.json', evidence: [`${fromStage} PASS`] },
    planReadiness: planReadiness(),
    agentWork: [],
    decisions: [],
    blockers: [],
  };
}
