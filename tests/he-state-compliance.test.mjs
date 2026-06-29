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

const dummySsotOwnerReuse = state('he-implement');
dummySsotOwnerReuse.subStages = dummySsotOwnerReuse.subStages.map((item) => (
  item.id === 'ssot-owner-reuse' ? { ...item, evidence: ['owner reuse checked'] } : item
));
dummySsotOwnerReuse.steps = [{ id: '1', title: 'Stage proof', status: 'done', receipt: receipt('he-implement', '/he:verify') }];
result = run(dummySsotOwnerReuse);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /requires ssot-owner-reuse evidence or final receipt/);

const receiptSsotOwnerReuse = state('he-implement');
receiptSsotOwnerReuse.subStages = receiptSsotOwnerReuse.subStages.map((item) => (
  item.id === 'ssot-owner-reuse' ? { ...item, evidence: ['owner reuse checked'] } : item
));
receiptSsotOwnerReuse.steps = [{
  id: '1',
  title: 'Stage proof',
  status: 'done',
  receipt: {
    ...receipt('he-implement', '/he:verify'),
    ownerProof: ['SSOT reused: workflow-state owner; SSOT extended: none; new owners created: none'],
  },
}];
result = run(receiptSsotOwnerReuse);
assert.equal(result.status, 0, result.stderr);

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

const settingsRowPathWithoutSsotEvidence = state('he-implement');
settingsRowPathWithoutSsotEvidence.guardrails.push(g('fallow-audit', 'he-implement', 'fallow audit --dupes --base origin/main'));
settingsRowPathWithoutSsotEvidence.guardrailInventory = {
  ...guardrailInventory({
    fallow: { id: 'fallow', status: 'required', guardrailId: 'fallow-audit', evidence: ['TSX clone groups checked'] },
  }),
  touchedStacks: ['src/features/settings/SettingsRow.tsx'],
};
result = run(settingsRowPathWithoutSsotEvidence);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /ssot-scanners cannot be not_applicable/);

const selectableCardsWithoutSsotEvidence = state('he-implement');
selectableCardsWithoutSsotEvidence.guardrails.push(g('fallow-audit', 'he-implement', 'fallow audit --dupes --base origin/main'));
selectableCardsWithoutSsotEvidence.guardrailInventory = {
  ...guardrailInventory({
    fallow: { id: 'fallow', status: 'required', guardrailId: 'fallow-audit', evidence: ['TSX clone groups checked'] },
  }),
  touchedStacks: ['settings rows', 'selectable cards'],
};
result = run(selectableCardsWithoutSsotEvidence);
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

for (const touchedPath of [
  'scripts/foo.py',
  'src/Foo.kt',
  'src/Foo.kts',
  'src/lib.rs',
  'cmd/foo.go',
  'lib/foo.rb',
  'public/foo.php',
  'src/Foo.java',
  'ios/Foo.swift',
  'src/Foo.scala',
  'src/foo.c',
  'src/foo.cc',
  'src/foo.cpp',
  'include/foo.h',
  'include/foo.hpp',
]) {
  const pathWithoutCloneFallback = state('he-implement');
  pathWithoutCloneFallback.guardrailInventory = {
    ...guardrailInventory(),
    touchedStacks: [touchedPath],
  };
  result = run(pathWithoutCloneFallback);
  assert.notEqual(result.status, 0, `${touchedPath} should require non-JS clone fallback proof`);
  assert.match(result.stderr, /explicit no-duplicate\/no-clone static-search proof/);
}

const reactWithFallow = state('he-implement');
reactWithFallow.guardrails.push(g('fallow-audit', 'he-implement', 'fallow audit --dupes --base origin/main'));
reactWithFallow.guardrails.push(g('react-doctor', 'he-implement', 'react-doctor --scope changed'));
reactWithFallow.guardrails.push(g('lint-typecheck', 'he-implement', 'npm run lint && npm run typecheck'));
reactWithFallow.guardrailInventory = {
  ...guardrailInventory({
    fallow: { id: 'fallow', status: 'required', guardrailId: 'fallow-audit', evidence: ['React TypeScript clone groups checked'] },
    'react-doctor': { id: 'react-doctor', status: 'required', guardrailId: 'react-doctor', evidence: ['React files changed'] },
    'lint-analyze-typecheck': { id: 'lint-analyze-typecheck', status: 'required', guardrailId: 'lint-typecheck', evidence: ['React lint and typecheck passed'] },
  }),
  touchedStacks: ['react', 'typescript'],
};
result = run(reactWithFallow);
assert.equal(result.status, 0, result.stderr);

const reactWithoutReactDoctorOrLint = state('he-implement');
reactWithoutReactDoctorOrLint.guardrails.push(g('fallow-audit', 'he-implement', 'fallow audit --dupes --base origin/main'));
reactWithoutReactDoctorOrLint.guardrailInventory = {
  ...guardrailInventory({
    fallow: { id: 'fallow', status: 'required', guardrailId: 'fallow-audit', evidence: ['React TypeScript clone groups checked'] },
  }),
  touchedStacks: ['react', 'typescript'],
};
result = run(reactWithoutReactDoctorOrLint);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /react-doctor cannot be not_applicable/);
assert.match(result.stderr, /lint-analyze-typecheck cannot be not_applicable/);

const jsWithGenericFallowRun = state('he-implement');
jsWithGenericFallowRun.guardrails.push(g('fallow-audit', 'he-implement', 'fallow audit --base origin/main'));
jsWithGenericFallowRun.guardrailInventory = {
  ...guardrailInventory({
    fallow: { id: 'fallow', status: 'required', guardrailId: 'fallow-audit', evidence: ['Fallow completed'] },
  }),
  touchedStacks: ['scripts/foo.mjs'],
};
result = run(jsWithGenericFallowRun);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /Fallow duplicate\/clone evidence/);

const jsWithCommandOnlyDuplicateFallow = state('he-implement');
jsWithCommandOnlyDuplicateFallow.guardrails.push(g('fallow-audit', 'he-implement', 'fallow audit --dupes --base origin/main'));
jsWithCommandOnlyDuplicateFallow.guardrailInventory = {
  ...guardrailInventory({
    fallow: { id: 'fallow', status: 'required', guardrailId: 'fallow-audit', evidence: ['Fallow completed'] },
  }),
  touchedStacks: ['scripts/foo.mjs'],
};
result = run(jsWithCommandOnlyDuplicateFallow);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /Fallow duplicate\/clone evidence/);

const jsWithSkippedDuplicateFallow = state('he-implement');
jsWithSkippedDuplicateFallow.guardrails.push(g('fallow-audit', 'he-implement', 'fallow audit --dupes --base origin/main'));
jsWithSkippedDuplicateFallow.guardrailInventory = {
  ...guardrailInventory({
    fallow: { id: 'fallow', status: 'required', guardrailId: 'fallow-audit', evidence: ['duplicate scan skipped; no duplicate evidence available'] },
  }),
  touchedStacks: ['scripts/foo.mjs'],
};
result = run(jsWithSkippedDuplicateFallow);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /Fallow duplicate\/clone evidence/);

const mixedJsNonJsWithoutCloneFallback = state('he-implement');
mixedJsNonJsWithoutCloneFallback.guardrails.push(g('fallow-audit', 'he-implement', 'fallow audit --dupes --base origin/main'));
mixedJsNonJsWithoutCloneFallback.guardrailInventory = {
  ...guardrailInventory({
    fallow: { id: 'fallow', status: 'required', guardrailId: 'fallow-audit', evidence: ['TSX clone groups checked'] },
  }),
  touchedStacks: ['src/App.tsx', 'scripts/migrate.py'],
};
result = run(mixedJsNonJsWithoutCloneFallback);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /explicit non-JS no-duplicate\/no-clone static-search proof/);

const mixedJsNonJsWithCloneFallback = state('he-implement');
mixedJsNonJsWithCloneFallback.guardrails.push({
  ...g('fallow-audit', 'he-implement', 'fallow audit --dupes --base origin/main'),
  evidence: ['TSX clone groups checked', 'rg static search found no clone groups for scripts/migrate.py'],
});
mixedJsNonJsWithCloneFallback.guardrails.push(g('react-doctor', 'he-implement', 'react-doctor --scope changed'));
mixedJsNonJsWithCloneFallback.guardrails.push(g('lint-typecheck', 'he-implement', 'npm run lint && npm run typecheck'));
mixedJsNonJsWithCloneFallback.guardrailInventory = {
  ...guardrailInventory({
    fallow: { id: 'fallow', status: 'required', guardrailId: 'fallow-audit', evidence: ['TSX clone groups checked'] },
    'react-doctor': { id: 'react-doctor', status: 'required', guardrailId: 'react-doctor', evidence: ['React files changed'] },
    'lint-analyze-typecheck': { id: 'lint-analyze-typecheck', status: 'required', guardrailId: 'lint-typecheck', evidence: ['React lint and typecheck passed'] },
  }),
  touchedStacks: ['src/App.tsx', 'scripts/migrate.py'],
};
result = run(mixedJsNonJsWithCloneFallback);
assert.equal(result.status, 0, result.stderr);

const flutterWithoutCloneFallback = state('he-implement');
flutterWithoutCloneFallback.guardrailInventory = {
  ...guardrailInventory(),
  touchedStacks: ['flutter', 'dart'],
};
result = run(flutterWithoutCloneFallback);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /explicit no-duplicate\/no-clone static-search proof/);

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

const flutterWithRequiredFallowWithoutStaticProof = state('he-implement');
flutterWithRequiredFallowWithoutStaticProof.guardrails.push({
  ...g('fallow-audit', 'he-implement', 'fallow audit --dupes --base origin/main'),
  evidence: ['Fallow duplicate scan passed'],
});
flutterWithRequiredFallowWithoutStaticProof.guardrailInventory = {
  ...guardrailInventory({
    fallow: {
      id: 'fallow',
      status: 'required',
      guardrailId: 'fallow-audit',
      evidence: ['Fallow duplicate scan passed'],
    },
  }),
  touchedStacks: ['flutter', 'dart'],
};
result = run(flutterWithRequiredFallowWithoutStaticProof);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /fallow required for non-JS\/TS stacks requires explicit no-duplicate\/no-clone/);

const flutterWithRequiredFallowStaticProof = state('he-implement');
flutterWithRequiredFallowStaticProof.guardrails.push({
  ...g('fallow-audit', 'he-implement', 'fallow audit --dupes --base origin/main'),
  evidence: ['Fallow duplicate scan passed', 'rg static search found no duplicate groups for lib/main.dart'],
});
flutterWithRequiredFallowStaticProof.guardrailInventory = {
  ...guardrailInventory({
    fallow: {
      id: 'fallow',
      status: 'required',
      guardrailId: 'fallow-audit',
      evidence: ['Fallow duplicate scan passed'],
    },
  }),
  touchedStacks: ['flutter', 'dart'],
};
result = run(flutterWithRequiredFallowStaticProof);
assert.equal(result.status, 0, result.stderr);

const flutterWithZeroCloneFallback = state('he-implement');
flutterWithZeroCloneFallback.guardrailInventory = {
  ...guardrailInventory({
    fallow: {
      id: 'fallow',
      status: 'not_applicable',
      reason: 'no stack-specific clone detector available for Dart in this repo',
      evidence: ['tool unavailable; rg duplicate search found zero clone groups near touched widgets'],
    },
  }),
  touchedStacks: ['flutter', 'dart'],
};
result = run(flutterWithZeroCloneFallback);
assert.equal(result.status, 0, result.stderr);

const flutterWithFoundCloneFallback = state('he-implement');
flutterWithFoundCloneFallback.guardrailInventory = {
  ...guardrailInventory({
    fallow: {
      id: 'fallow',
      status: 'not_applicable',
      reason: 'no stack-specific clone detector available for Dart in this repo',
      evidence: ['tool unavailable; rg duplicate search found clone groups near touched widgets'],
    },
  }),
  touchedStacks: ['flutter', 'dart'],
};
result = run(flutterWithFoundCloneFallback);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /explicit no-duplicate\/no-clone static-search proof/);

const flutterWithMixedCloneFallback = state('he-implement');
flutterWithMixedCloneFallback.guardrailInventory = {
  ...guardrailInventory({
    fallow: {
      id: 'fallow',
      status: 'not_applicable',
      reason: 'no stack-specific clone detector available for Dart in this repo',
      evidence: ['tool unavailable; rg duplicate search found zero clone groups near touched widgets; found clone groups in copied widgets'],
    },
  }),
  touchedStacks: ['flutter', 'dart'],
};
result = run(flutterWithMixedCloneFallback);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /explicit no-duplicate\/no-clone static-search proof/);

const flutterWithContradictoryCloneClause = state('he-implement');
flutterWithContradictoryCloneClause.guardrailInventory = {
  ...guardrailInventory({
    fallow: {
      id: 'fallow',
      status: 'not_applicable',
      reason: 'no stack-specific clone detector available for Dart in this repo',
      evidence: ['tool unavailable; rg found no duplicate groups but found clone groups'],
    },
  }),
  touchedStacks: ['flutter', 'dart'],
};
result = run(flutterWithContradictoryCloneClause);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /explicit no-duplicate\/no-clone static-search proof/);

const flutterWithFoundCloneDecision = state('he-implement');
flutterWithFoundCloneDecision.guardrails.push(g('ssot-scan', 'he-implement', 'node scripts/check-ssot-guardrails.mjs .'));
flutterWithFoundCloneDecision.guardrailInventory = {
  ...guardrailInventory({
    'ssot-scanners': {
      id: 'ssot-scanners',
      status: 'required',
      guardrailId: 'ssot-scan',
      evidence: ['static search found clone groups; SSOT owner decision recorded in owner ledger'],
    },
    fallow: {
      id: 'fallow',
      status: 'not_applicable',
      reason: 'no stack-specific clone detector available for Dart in this repo',
      evidence: ['tool unavailable; rg duplicate search found clone groups near touched widgets'],
    },
  }),
  touchedStacks: ['flutter', 'dart'],
};
result = run(flutterWithFoundCloneDecision);
assert.equal(result.status, 0, result.stderr);

const flutterWithSkippedCloneDecision = state('he-implement');
flutterWithSkippedCloneDecision.guardrails.push({
  ...g('ssot-scan', 'he-implement', 'node scripts/check-ssot-guardrails.mjs .'),
  status: 'skipped',
});
flutterWithSkippedCloneDecision.guardrailInventory = {
  ...guardrailInventory({
    'ssot-scanners': {
      id: 'ssot-scanners',
      status: 'required',
      guardrailId: 'ssot-scan',
      evidence: ['static search found clone groups; SSOT owner decision recorded in owner ledger'],
    },
    fallow: {
      id: 'fallow',
      status: 'not_applicable',
      reason: 'no stack-specific clone detector available for Dart in this repo',
      evidence: ['tool unavailable; rg duplicate search found clone groups near touched widgets'],
    },
  }),
  touchedStacks: ['flutter', 'dart'],
};
result = run(flutterWithSkippedCloneDecision);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /explicit no-duplicate\/no-clone static-search proof/);

const flutterWithStructuredCloneDecision = state('he-implement');
flutterWithStructuredCloneDecision.decisions = [{
  id: 'clone-owner-decision',
  status: 'accepted',
  summary: 'SSOT owner decision recorded for clone groups',
  evidence: ['owner ledger resolved duplicate clone groups'],
}];
flutterWithStructuredCloneDecision.guardrailInventory = {
  ...guardrailInventory({
    fallow: {
      id: 'fallow',
      status: 'not_applicable',
      reason: 'no stack-specific clone detector available for Dart in this repo',
      evidence: ['tool unavailable; rg duplicate search found clone groups near touched widgets'],
    },
  }),
  touchedStacks: ['flutter', 'dart'],
};
result = run(flutterWithStructuredCloneDecision);
assert.equal(result.status, 0, result.stderr);

const flutterWithBareStructuredCloneDecision = state('he-implement');
flutterWithBareStructuredCloneDecision.decisions = [{
  id: 'clone-owner-decision',
  status: 'accepted',
  summary: 'SSOT owner decision recorded for clone groups',
}];
flutterWithBareStructuredCloneDecision.guardrailInventory = {
  ...guardrailInventory({
    fallow: {
      id: 'fallow',
      status: 'not_applicable',
      reason: 'no stack-specific clone detector available for Dart in this repo',
      evidence: ['tool unavailable; rg duplicate search found clone groups near touched widgets'],
    },
  }),
  touchedStacks: ['flutter', 'dart'],
};
result = run(flutterWithBareStructuredCloneDecision);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /explicit no-duplicate\/no-clone static-search proof/);

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

const negatedProdGuardrailDoesNotRequireApproval = state('he-verify');
negatedProdGuardrailDoesNotRequireApproval.guardrails.push({
  ...g('check-no-prod-writes', 'he-verify', 'node scripts/check-no-prod-writes.mjs'),
  evidence: ['no prod mutation; read-only prevention check passed'],
});
result = run(negatedProdGuardrailDoesNotRequireApproval);
assert.equal(result.status, 0, result.stderr);

const changedScannerPreventionDoesNotRequireApproval = state('he-verify');
changedScannerPreventionDoesNotRequireApproval.guardrails.push({
  ...g('scanner-prevents-prod-writes', 'he-verify', 'node scripts/check-no-prod-writes.mjs'),
  evidence: ['changed scanner to prevent prod writes'],
});
result = run(changedScannerPreventionDoesNotRequireApproval);
assert.equal(result.status, 0, result.stderr);

const mixedApprovalEvidenceRequiresBoundary = state('he-verify');
mixedApprovalEvidenceRequiresBoundary.guardrails.push({
  ...g('mixed-appwrite-check', 'he-verify', 'node scripts/check-appwrite.mjs'),
  evidence: ['changed Appwrite permissions in prod; cleanup check clean'],
});
result = run(mixedApprovalEvidenceRequiresBoundary);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /approvalBoundaries are required/);

const negatedThenMixedApprovalEvidenceRequiresBoundary = state('he-verify');
negatedThenMixedApprovalEvidenceRequiresBoundary.guardrails.push({
  ...g('mixed-appwrite-check', 'he-verify', 'node scripts/check-appwrite.mjs'),
  evidence: ['no prod mutation, changed Appwrite permissions in prod'],
});
result = run(negatedThenMixedApprovalEvidenceRequiresBoundary);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /approvalBoundaries are required/);

const negatedButMixedApprovalEvidenceRequiresBoundary = state('he-verify');
negatedButMixedApprovalEvidenceRequiresBoundary.guardrails.push({
  ...g('mixed-appwrite-check', 'he-verify', 'node scripts/check-appwrite.mjs'),
  evidence: ['no prod mutation but changed Appwrite permissions in prod'],
});
result = run(negatedButMixedApprovalEvidenceRequiresBoundary);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /approvalBoundaries are required/);

const negatedAndMixedApprovalEvidenceRequiresBoundary = state('he-verify');
negatedAndMixedApprovalEvidenceRequiresBoundary.guardrails.push({
  ...g('mixed-appwrite-check', 'he-verify', 'node scripts/check-appwrite.mjs'),
  evidence: ['no prod mutation and changed Appwrite permissions in prod'],
});
result = run(negatedAndMixedApprovalEvidenceRequiresBoundary);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /approvalBoundaries are required/);

for (const evidence of [
  'no real credentials',
  'without generated users',
  'no native permission prompt',
  'no production SMS sent',
  'without prod email side effects',
  'no prod payment charged',
  'no production data shared',
]) {
  const negatedBoundary = state('he-verify');
  negatedBoundary.guardrails.push({
    ...g('safe-boundary-check', 'he-verify', 'node scripts/check-safe-boundaries.mjs'),
    evidence: [evidence],
  });
  result = run(negatedBoundary);
  assert.equal(result.status, 0, result.stderr);
}

for (const evidence of [
  'changed Appwrite permissions in prod',
  'production Appwrite permission gap',
  'backend schema/index must change',
  'changed prod payment record',
  'deleted prod payment record',
  'sent production SMS',
  'sent production email',
  'sent email in production',
  'charged prod payment',
  'charged saved card in prod',
  'charged customer subscription in production',
  'shared production data',
  'shared data in production',
]) {
  const appwriteBoundary = state('he-verify');
  appwriteBoundary.guardrails.push({
    ...g('appwrite-permission-check', 'he-verify', 'node scripts/check-appwrite.mjs'),
    evidence: [evidence],
  });
  result = run(appwriteBoundary);
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /approvalBoundaries are required/);
}

const riskyE2eWithDerivedBoundaries = state('he-verify');
riskyE2eWithDerivedBoundaries.guardrails = riskyE2eWithoutPolicyTrigger.guardrails;
riskyE2eWithDerivedBoundaries.approvalBoundaries = [
  { id: 'prod-db-permission', category: 'prod-backend-write', status: 'approved', reason: 'user approved exact backend permission mutation', evidence: ['approval quote recorded'] },
  { id: 'native-notifications', category: 'native-permission', status: 'approved', reason: 'user approved clicking Allow', evidence: ['approval quote recorded'] },
  { id: 'generated-user', category: 'generated-credentials', status: 'approved', reason: 'user approved generated test user', evidence: ['created test user'], redactedCredentialRef: 'user: he-e2e-***@example.test', dataScope: 'seeded-test user only', cleanupProof: ['source-of-truth lookup confirmed deleted'] },
];
result = run(riskyE2eWithDerivedBoundaries);
assert.equal(result.status, 0, result.stderr);

const distinctProdSideEffectsNeedDistinctBoundaries = state('he-verify');
distinctProdSideEffectsNeedDistinctBoundaries.guardrails.push({
  ...g('e2e-side-effects', 'he-verify', 'npx playwright test e2e/checkout.spec.ts'),
  evidence: ['changed Appwrite permissions in prod', 'sent production SMS'],
});
distinctProdSideEffectsNeedDistinctBoundaries.approvalBoundaries = [
  { id: 'prod-db-permission', category: 'prod-backend-write', status: 'approved', reason: 'user approved exact Appwrite permission mutation', evidence: ['approval quote recorded'] },
];
result = run(distinctProdSideEffectsNeedDistinctBoundaries);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /approvalBoundaries requires prod-backend-write side effect prod-sms/);

const distinctProdSideEffectsApproved = state('he-verify');
distinctProdSideEffectsApproved.guardrails = distinctProdSideEffectsNeedDistinctBoundaries.guardrails;
distinctProdSideEffectsApproved.approvalBoundaries = [
  { id: 'prod-db-permission', category: 'prod-backend-write', status: 'approved', reason: 'user approved exact Appwrite permission mutation', evidence: ['approval quote recorded'] },
  { id: 'prod-sms-send', category: 'prod-backend-write', status: 'approved', reason: 'user approved production SMS send', evidence: ['approval quote recorded'] },
];
result = run(distinctProdSideEffectsApproved);
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

const configuredProdBoundaryIsCategoryOnly = state('he-verify');
configuredProdBoundaryIsCategoryOnly.e2ePolicy = { requiredApprovalBoundaries: ['prod-backend-write'] };
configuredProdBoundaryIsCategoryOnly.approvalBoundaries = [
  { id: 'prod-approval', category: 'prod-backend-write', status: 'approved', reason: 'user approved required production side-effect boundary', evidence: ['approval quote recorded'] },
];
result = run(configuredProdBoundaryIsCategoryOnly);
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

const repeatedMissPunctuationNoLearning = state('he-ship');
repeatedMissPunctuationNoLearning.repeatMisses = [
  { issueClass: 'ssot/component-owner', evidence: ['user caught wrong list-row owner'] },
  { issueClass: 'ssot component owner', evidence: ['user caught duplicate selectable-control owner'] },
];
result = run(repeatedMissPunctuationNoLearning);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /ssot-component-owner requires a he-learn learning finding/);

const repeatedMissEmptySlug = state('he-ship');
repeatedMissEmptySlug.repeatMisses = [
  { issueClass: '-', evidence: ['user caught wrong list-row owner'] },
  { issueClass: ' - ', evidence: ['user caught duplicate selectable-control owner'] },
];
result = run(repeatedMissEmptySlug);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /issueClass must include an alphanumeric slug/);

const repeatedMissSubstringLearning = state('he-ship');
repeatedMissSubstringLearning.repeatMisses = [
  { issueClass: 'auth', evidence: ['user caught auth owner miss'] },
  { issueClass: 'auth', evidence: ['user caught auth proof miss'] },
];
repeatedMissSubstringLearning.findings = [{
  id: 'learn-author-workflow',
  stage: 'he-implement',
  summary: 'author workflow repeated and needs durable guard',
  ownerStage: 'he-learn',
  repairType: 'learning',
  ownerProof: ['skills/he-implement/SKILL.md'],
  artifacts: [],
  status: 'open',
}];
result = run(repeatedMissSubstringLearning);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /repeatMisses auth requires a he-learn learning finding/);

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
