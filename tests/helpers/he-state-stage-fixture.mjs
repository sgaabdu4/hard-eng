import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';

const repo = path.resolve(new URL('../..', import.meta.url).pathname);
const script = path.join(repo, 'scripts', 'he-state.mjs');
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'he-state-stage-contract-'));
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

export const stages = {
  'he-implement': [2, '/he:verify', 'he-plan', ['owner-read', 'ssot-owner-reuse', 'test-first', 'owner-change', 'guardrails', 'learning-capture', 'state-update']],
  'he-verify': [3, '/he:ship', 'he-implement', ['tests', 'guardrails', 'reviews', 'fix-loop', 'learning-capture', 'state-update']],
  'he-ship': [4, 'loop-complete', 'he-verify', ['status', 'hooks', 'quality-gates', 'no-mistakes', 'pr-evidence', 'pr-review-threads', 'ci-or-skip', 'learning-capture', 'state-update']],
  'he-learn': [5, 'loop-complete', 'he-ship', ['learning-findings', 'durable-owner', 'proof', 'state-update']],
};

export function run(state) {
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
      { ...g('test-first-proof', stage, 'npm test -- owner'), kind: 'test', evidence: [tq('red-first failed as expected before owner-change')], sequence: 2 },
      { ...g('implementation-proof', stage, 'npm test -- owner'), kind: 'test', evidence: ['post-change tests passed'], sequence: 5 },
    ];
  }
  if (stage === 'he-verify') return [g('quality-gate', stage, 'node scripts/check-project-quality-gates.mjs --require-push-gate .', true)];
  if (stage === 'he-ship') return [
    { ...g('git-status', stage, 'git status --short', true), kind: 'manual', sequence: 1 },
    { ...g('worktree-ready', stage, 'scripts/ensure-worktree-ready.sh --check --require-pre-push .', true), sequence: 2 },
    { ...g('quality-gate', stage, 'node scripts/check-project-quality-gates.mjs --require-push-gate .', true), sequence: 3 },
    { ...g('no-mistakes', stage, 'no-mistakes axi run --intent "ship verified feature"', true), sequence: 4 },
    { ...g('pr-evidence', stage, 'node integrations/no-mistakes/scripts/repair-pr-evidence.mjs --pr 7', true), evidence: ['Current head: `abcdef1234567890abcdef1234567890abcdef12`; No open no-mistakes findings; PR evidence updated'], sequence: 5 },
    { ...g('pr-review-threads', stage, 'node integrations/no-mistakes/scripts/repair-pr-evidence.mjs --pr 7 --check-review-threads No open GitHub review threads', true), sequence: 6 },
    { ...g('ci-or-skip', stage, 'gh run view --json conclusion,status CI passed', true), sequence: 7 },
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
    subStages: subStageIds.map((id, index) => ({ id, title: id, status: 'done', evidence: [id], sequence: index + 1 })),
    findings: stage === 'he-learn' ? [{ id: 'learn-1', stage: 'he-ship', summary: 'Durable guard added', ownerStage: 'he-learn', repairType: 'learning', ownerProof: ['guard'], artifacts: [], status: 'fixed' }] : [],
    guardrails: guardrails(stage),
    guardrailInventory: ['he-implement', 'he-verify', 'he-ship'].includes(stage) ? guardrailInventory() : undefined,
    entryGate: { fromStage, decision: 'PASS', statePath: 'prior-he-state.json', evidence: [`${fromStage} PASS`] },
    agentWork: [],
    decisions: [],
    blockers: [],
  };
}
