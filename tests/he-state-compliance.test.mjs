#!/usr/bin/env node
import assert from 'node:assert/strict';
import {
  g,
  guardrailInventory,
  receipt,
  run,
  state,
} from './helpers/he-state-stage-fixture.mjs';

let result = run(state('he-implement'));
assert.equal(result.status, 0, result.stderr);

const missingSsotOwnerReuse = state('he-implement');
missingSsotOwnerReuse.subStages = missingSsotOwnerReuse.subStages.filter((item) => item.id !== 'ssot-owner-reuse');
result = run(missingSsotOwnerReuse);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /requires exactly one subStage ssot-owner-reuse/);

const lateSsotOwnerReuse = state('he-implement');
lateSsotOwnerReuse.subStages = lateSsotOwnerReuse.subStages.map((item) => (
  item.id === 'ssot-owner-reuse' ? { ...item, sequence: 4 } : item
));
result = run(lateSsotOwnerReuse);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /ssot-owner-reuse before test-first/);
assert.match(result.stderr, /ssot-owner-reuse before owner-change/);

const uiComponentWithoutSsotEvidence = state('he-implement');
uiComponentWithoutSsotEvidence.guardrailInventory = {
  ...guardrailInventory(),
  touchedStacks: ['ui', 'component'],
};
result = run(uiComponentWithoutSsotEvidence);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /ssot-scanners cannot be not_applicable/);

const missingTouchedStacks = state('he-implement');
delete missingTouchedStacks.guardrailInventory.touchedStacks;
result = run(missingTouchedStacks);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /guardrailInventory\.touchedStacks is required for ready handoff/);

const emptyTouchedStacks = state('he-implement');
emptyTouchedStacks.guardrailInventory.touchedStacks = [];
result = run(emptyTouchedStacks);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /guardrailInventory\.touchedStacks is required for ready handoff/);

const uiComponentWithPatternSearchEvidence = state('he-implement');
uiComponentWithPatternSearchEvidence.guardrailInventory = {
  ...guardrailInventory({
    'ssot-scanners': {
      id: 'ssot-scanners',
      status: 'not_applicable',
      reason: 'no shared owner changed after component-pattern search',
      evidence: ['shared component and interaction-pattern owners searched; owner ledger recorded'],
    },
  }),
  touchedStacks: ['ui', 'component'],
};
result = run(uiComponentWithPatternSearchEvidence);
assert.equal(result.status, 0, result.stderr);

const uiComponentWithRequiredSsotScanner = state('he-implement');
uiComponentWithRequiredSsotScanner.guardrails.push(g('ssot-scan', 'he-implement', 'node scripts/check-ssot-guardrails.mjs .'));
uiComponentWithRequiredSsotScanner.guardrailInventory = {
  ...guardrailInventory({
    'ssot-scanners': { id: 'ssot-scanners', status: 'required', guardrailId: 'ssot-scan', evidence: ['UI component owner changed'] },
  }),
  touchedStacks: ['ui', 'component'],
};
result = run(uiComponentWithRequiredSsotScanner);
assert.equal(result.status, 0, result.stderr);

const tsxComponentPathWithoutSsotEvidence = state('he-implement');
tsxComponentPathWithoutSsotEvidence.guardrails.push(g('fallow-audit', 'he-implement', 'fallow audit --dupes --base origin/main'));
tsxComponentPathWithoutSsotEvidence.guardrailInventory = {
  ...guardrailInventory({
    fallow: { id: 'fallow', status: 'required', guardrailId: 'fallow-audit', evidence: ['TSX clone groups checked'] },
  }),
  touchedStacks: ['src/components/Foo.tsx'],
};
result = run(tsxComponentPathWithoutSsotEvidence);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /ssot-scanners cannot be not_applicable/);

const reactWithoutFallow = state('he-implement');
reactWithoutFallow.guardrailInventory = {
  ...guardrailInventory(),
  touchedStacks: ['react', 'typescript'],
};
result = run(reactWithoutFallow);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /fallow cannot be not_applicable/);

const mjsPathWithoutFallow = state('he-implement');
mjsPathWithoutFallow.guardrailInventory = {
  ...guardrailInventory(),
  touchedStacks: ['scripts/foo.mjs'],
};
result = run(mjsPathWithoutFallow);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /fallow cannot be not_applicable/);

const reactWithFallow = state('he-implement');
reactWithFallow.guardrails.push(g('fallow-audit', 'he-implement', 'fallow audit --dupes --base origin/main'));
reactWithFallow.guardrailInventory = {
  ...guardrailInventory({
    fallow: { id: 'fallow', status: 'required', guardrailId: 'fallow-audit', evidence: ['React TypeScript clone groups checked'] },
  }),
  touchedStacks: ['react', 'typescript'],
};
result = run(reactWithFallow);
assert.equal(result.status, 0, result.stderr);

const flutterWithoutCloneFallback = state('he-implement');
flutterWithoutCloneFallback.guardrailInventory = {
  ...guardrailInventory(),
  touchedStacks: ['flutter', 'dart'],
};
result = run(flutterWithoutCloneFallback);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /stack-specific tool absence reason plus static-search/);

const flutterWithCloneFallback = state('he-implement');
flutterWithCloneFallback.guardrailInventory = {
  ...guardrailInventory({
    fallow: {
      id: 'fallow',
      status: 'not_applicable',
      reason: 'no stack-specific clone detector available for Dart in this repo',
      evidence: ['rg static search duplicate search found no clone groups near touched widgets'],
    },
  }),
  touchedStacks: ['flutter', 'dart'],
};
result = run(flutterWithCloneFallback);
assert.equal(result.status, 0, result.stderr);

const missingApprovalBoundaries = state('he-verify');
missingApprovalBoundaries.e2ePolicy = { requiredApprovalBoundaries: ['prod-backend-write', 'native-permission', 'generated-credentials'] };
result = run(missingApprovalBoundaries);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /approvalBoundaries are required/);

const riskyE2eWithoutPolicyTrigger = state('he-verify');
riskyE2eWithoutPolicyTrigger.guardrails.push({
  ...g('e2e-smoke', 'he-verify', 'npx playwright test e2e/checkout.spec.ts'),
  evidence: [
    'E2E clicked native permission prompt Allow',
    'E2E created generated test user credentials',
    'E2E changed production backend permission schema index for seeded run',
  ],
});
result = run(riskyE2eWithoutPolicyTrigger);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /approvalBoundaries are required/);

const riskyGuardrailWithoutE2eMarker = state('he-verify');
riskyGuardrailWithoutE2eMarker.guardrails.push({
  ...g('credential-smoke', 'he-verify', 'node scripts/check-login.mjs'),
  evidence: [
    'used real credentials for seeded account',
    'created generated user credentials',
    'production backend permission changed',
  ],
});
result = run(riskyGuardrailWithoutE2eMarker);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /approvalBoundaries are required/);

const riskyE2eWithDerivedBoundaries = state('he-verify');
riskyE2eWithDerivedBoundaries.guardrails = riskyE2eWithoutPolicyTrigger.guardrails;
riskyE2eWithDerivedBoundaries.approvalBoundaries = [
  { id: 'prod-db-permission', category: 'prod-backend-write', status: 'approved', reason: 'user approved exact backend permission mutation', evidence: ['approval quote recorded'] },
  { id: 'native-notifications', category: 'native-permission', status: 'approved', reason: 'user approved clicking Allow', evidence: ['approval quote recorded'] },
  { id: 'generated-user', category: 'generated-credentials', status: 'approved', reason: 'user approved generated test user', evidence: ['created test user'], redactedCredentialRef: 'user: he-e2e-***@example.test', dataScope: 'seeded-test user only', cleanupProof: ['source-of-truth lookup confirmed deleted'] },
];
result = run(riskyE2eWithDerivedBoundaries);
assert.equal(result.status, 0, result.stderr);

const approvedBoundaries = state('he-verify');
approvedBoundaries.e2ePolicy = { requiredApprovalBoundaries: ['prod-backend-write', 'native-permission', 'generated-credentials'] };
approvedBoundaries.approvalBoundaries = [
  { id: 'prod-db-permission', category: 'prod-backend-write', status: 'approved', reason: 'user approved exact Appwrite permission mutation', evidence: ['approval quote recorded'] },
  { id: 'native-notifications', category: 'native-permission', status: 'approved', reason: 'user approved clicking Allow', evidence: ['approval quote recorded'] },
  { id: 'generated-user', category: 'generated-credentials', status: 'approved', reason: 'user approved generated test user', evidence: ['created test user'], redactedCredentialRef: 'user: he-e2e-***@example.test', dataScope: 'seeded-test user only', cleanupProof: ['source-of-truth lookup confirmed deleted'] },
];
result = run(approvedBoundaries);
assert.equal(result.status, 0, result.stderr);

const realCredentialMissingScope = state('he-verify');
realCredentialMissingScope.e2ePolicy = { requiredApprovalBoundaries: ['real-credentials'] };
realCredentialMissingScope.approvalBoundaries = [
  { id: 'real-user', category: 'real-credentials', status: 'approved', reason: 'user approved real account use', evidence: ['approval quote recorded'] },
];
result = run(realCredentialMissingScope);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /redactedCredentialRef is required for real-credentials/);
assert.match(result.stderr, /dataScope is required for real-credentials/);

const realCredentialApproved = state('he-verify');
realCredentialApproved.e2ePolicy = { requiredApprovalBoundaries: ['real-credentials'] };
realCredentialApproved.approvalBoundaries = [
  { id: 'real-user', category: 'real-credentials', status: 'approved', reason: 'user approved real account use', evidence: ['approval quote recorded'], redactedCredentialRef: 'user: real-***@example.com', dataScope: 'approved read-only account' },
];
result = run(realCredentialApproved);
assert.equal(result.status, 0, result.stderr);

const repeatedMissNoLearning = state('he-ship');
repeatedMissNoLearning.repeatMisses = [
  { issueClass: 'ssot-component-owner', evidence: ['user caught wrong list-row owner'] },
  { issueClass: 'ssot-component-owner', evidence: ['user caught duplicate selectable-control owner'] },
];
result = run(repeatedMissNoLearning);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /ssot-component-owner requires a he-learn learning finding/);

const repeatedMissCaseWhitespaceNoLearning = state('he-ship');
repeatedMissCaseWhitespaceNoLearning.repeatMisses = [
  { issueClass: ' ssot-component-owner ', evidence: ['user caught wrong list-row owner'] },
  { issueClass: 'SSOT-COMPONENT-OWNER', evidence: ['user caught duplicate selectable-control owner'] },
];
result = run(repeatedMissCaseWhitespaceNoLearning);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /ssot-component-owner requires a he-learn learning finding/);

const repeatedMissWithLearning = state('he-ship');
repeatedMissWithLearning.next = { target: '/he:learn', ready: true, reason: 'learning finding open' };
repeatedMissWithLearning.steps = [{ id: '1', title: 'Gate passed', status: 'done', receipt: receipt('he-ship', 'ready for /he:learn: yes') }];
repeatedMissWithLearning.repeatMisses = repeatedMissNoLearning.repeatMisses;
repeatedMissWithLearning.findings = [{
  id: 'learn-ssot-component-owner',
  stage: 'he-implement',
  summary: 'ssot-component-owner repeated and needs durable guard',
  ownerStage: 'he-learn',
  repairType: 'learning',
  ownerProof: ['skills/he-implement/SKILL.md', 'tests/agents-md-routing/evals/evals.json'],
  artifacts: [],
  status: 'open',
}];
result = run(repeatedMissWithLearning);
assert.equal(result.status, 0, result.stderr);

console.log('he-state-compliance-test: pass');
