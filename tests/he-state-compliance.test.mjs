#!/usr/bin/env node
import assert from 'node:assert/strict';
import {
  g,
  guardrailInventory,
  receipt,
  run,
  ssotOwnerLedger,
  state,
} from './helpers/he-state-stage-fixture.mjs';

function withSsotOwnerLedger(testState, ownerLedger) {
  testState.subStages = testState.subStages.map((item) => (
    item.id === 'ssot-owner-reuse'
      ? { ...item, ownerLedger: [...ssotOwnerLedger(), ...ownerLedger] }
      : item
  ));
  return testState;
}

function guardrailInventoryWithUiSsot(testState, entries = {}) {
  withSsotOwnerLedger(testState, [{
    ownerClass: 'ui-component',
    decision: 'reuse',
    owner: 'skills/he-implement/references/ssot-owner-reuse.md',
    evidence: ['ui component owner ledger reviewed'],
  }]);
  return guardrailInventory({
    'ssot-scanners': {
      id: 'ssot-scanners',
      status: 'not_applicable',
      reason: 'no shared owner changed after component-pattern search',
      evidence: ['shared component and interaction-pattern owners searched; owner ledger recorded'],
    },
    ...entries,
  });
}

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
  item.id === 'ssot-owner-reuse' ? { id: item.id, title: item.title, status: item.status, evidence: ['owner reuse checked'], sequence: item.sequence } : item
));
dummySsotOwnerReuse.steps = [{ id: '1', title: 'Stage proof', status: 'done', receipt: receipt('he-implement', '/he:verify') }];
result = run(dummySsotOwnerReuse);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /requires ssot-owner-reuse ledger decisions/);

const keywordOnlySsotOwnerReuse = state('he-implement');
keywordOnlySsotOwnerReuse.subStages = keywordOnlySsotOwnerReuse.subStages.map((item) => (
  item.id === 'ssot-owner-reuse' ? { id: item.id, title: item.title, status: item.status, evidence: ['SSOT reused: workflow-state owner; SSOT extended: none; new owners created: none'], sequence: item.sequence } : item
));
result = run(keywordOnlySsotOwnerReuse);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /requires ssot-owner-reuse ledger decisions/);

const malformedSsotOwnerReuseLedger = state('he-implement');
malformedSsotOwnerReuseLedger.subStages = malformedSsotOwnerReuseLedger.subStages.map((item) => (
  item.id === 'ssot-owner-reuse'
    ? {
        ...item,
        ownerLedger: [{ ownerClass: 'workflow-state', decision: 'reuse', evidence: ['workflow-state owner searched'] }],
      }
    : item
));
result = run(malformedSsotOwnerReuseLedger);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /owner is required for reuse/);

const receiptSsotOwnerReuse = state('he-implement');
receiptSsotOwnerReuse.subStages = receiptSsotOwnerReuse.subStages.map((item) => (
  item.id === 'ssot-owner-reuse' ? { id: item.id, title: item.title, status: item.status, evidence: ['owner reuse checked'], sequence: item.sequence } : item
));
receiptSsotOwnerReuse.steps = [{
  id: '1',
  title: 'Stage proof',
  status: 'done',
  receipt: {
    ...receipt('he-implement', '/he:verify'),
    ownerProof: ['SSOT reused: workflow-state owner; SSOT extended: none; new owners created: none'],
    ssotOwnerReuse: { ownerLedger: ssotOwnerLedger() },
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

const emptyNotApplicableInventoryEvidence = state('he-implement');
emptyNotApplicableInventoryEvidence.guardrailInventory.requiredGuardrails[0] = {
  ...emptyNotApplicableInventoryEvidence.guardrailInventory.requiredGuardrails[0],
  evidence: [''],
};
result = run(emptyNotApplicableInventoryEvidence);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /guardrailInventory\.requiredGuardrails\[0\]\.evidence must be non-empty string\[\]/);

const emptyRequiredInventoryEvidence = state('he-implement');
emptyRequiredInventoryEvidence.guardrails.push(g('regex-scan', 'he-implement', 'rg owner .'));
emptyRequiredInventoryEvidence.guardrailInventory.requiredGuardrails[0] = {
  id: 'regex-scanners',
  status: 'required',
  guardrailId: 'regex-scan',
  evidence: [''],
};
result = run(emptyRequiredInventoryEvidence);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /guardrailInventory\.requiredGuardrails\[0\]\.evidence must be non-empty string\[\]/);

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
withSsotOwnerLedger(uiComponentWithPatternSearchEvidence, [{
  ownerClass: 'ui-component',
  decision: 'reuse',
  owner: 'skills/he-implement/references/ssot-owner-reuse.md',
  evidence: ['ui component owner ledger reviewed'],
}]);
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

const uiComponentWithIrrelevantOwnerLedger = state('he-implement');
uiComponentWithIrrelevantOwnerLedger.guardrailInventory = {
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
result = run(uiComponentWithIrrelevantOwnerLedger);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /ownerLedger coverage for touched owner classes/);

const uiComponentWithRequiredSsotScanner = state('he-implement');
withSsotOwnerLedger(uiComponentWithRequiredSsotScanner, [{
  ownerClass: 'ui-component',
  decision: 'reuse',
  owner: 'skills/he-implement/references/ssot-owner-reuse.md',
  evidence: ['ui component owner ledger reviewed'],
}]);
uiComponentWithRequiredSsotScanner.guardrails.push(g('ssot-scan', 'he-implement', 'node scripts/check-ssot-guardrails.mjs .'));
uiComponentWithRequiredSsotScanner.guardrailInventory = {
  ...guardrailInventory({
    'ssot-scanners': { id: 'ssot-scanners', status: 'required', guardrailId: 'ssot-scan', evidence: ['UI component owner changed'] },
  }),
  touchedStacks: ['ui', 'component'],
};
result = run(uiComponentWithRequiredSsotScanner);
assert.equal(result.status, 0, result.stderr);

const uiComponentWithSkippedRequiredSsotScanner = state('he-implement');
withSsotOwnerLedger(uiComponentWithSkippedRequiredSsotScanner, [{
  ownerClass: 'ui-component',
  decision: 'reuse',
  owner: 'skills/he-implement/references/ssot-owner-reuse.md',
  evidence: ['ui component owner ledger reviewed'],
}]);
uiComponentWithSkippedRequiredSsotScanner.guardrails.push({
  ...g('ssot-scan', 'he-implement', 'node scripts/check-ssot-guardrails.mjs .'),
  status: 'skipped',
  reason: 'not run',
  evidence: ['SSOT scanner skipped'],
});
uiComponentWithSkippedRequiredSsotScanner.guardrailInventory = {
  ...guardrailInventory({
    'ssot-scanners': { id: 'ssot-scanners', status: 'required', guardrailId: 'ssot-scan', evidence: ['UI component owner changed'] },
  }),
  touchedStacks: ['ui', 'component'],
};
result = run(uiComponentWithSkippedRequiredSsotScanner);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /ssot-scanners requires passed SSOT scanner evidence/);

const tsxComponentPathWithoutSsotEvidence = state('he-implement');
tsxComponentPathWithoutSsotEvidence.guardrails.push(g('fallow-audit', 'he-implement', 'fallow audit --dupes --base origin/main'));
tsxComponentPathWithoutSsotEvidence.guardrailInventory = {
  ...guardrailInventory({
    fallow: { id: 'fallow', status: 'required', guardrailId: 'fallow-audit', evidence: ['Fallow found no clone groups for TSX files'] },
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
    fallow: { id: 'fallow', status: 'required', guardrailId: 'fallow-audit', evidence: ['Fallow found no clone groups for TSX files'] },
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
    fallow: { id: 'fallow', status: 'required', guardrailId: 'fallow-audit', evidence: ['Fallow found no clone groups for TSX files'] },
  }),
  touchedStacks: ['settings rows', 'selectable cards'],
};
result = run(selectableCardsWithoutSsotEvidence);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /ssot-scanners cannot be not_applicable/);

for (const touchedStack of ['src/styles/Button.css', 'Button.module.css', 'button styling']) {
  const styleStackWithoutSsotEvidence = state('he-implement');
  styleStackWithoutSsotEvidence.guardrailInventory = {
    ...guardrailInventory(),
    touchedStacks: [touchedStack],
  };
  result = run(styleStackWithoutSsotEvidence);
  assert.notEqual(result.status, 0, `${touchedStack} should require SSOT evidence`);
  assert.match(result.stderr, /ssot-scanners cannot be not_applicable/);
}

for (const touchedStack of ['src/App.tsx', 'app/page.tsx', 'react']) {
  const genericReactUiWithoutSsotEvidence = state('he-implement');
  genericReactUiWithoutSsotEvidence.guardrails.push({
    ...g('fallow-audit', 'he-implement', 'fallow audit --dupes --base origin/main'),
    evidence: ['Fallow found no clone groups for React TypeScript files'],
  });
  genericReactUiWithoutSsotEvidence.guardrails.push(g('react-doctor', 'he-implement', 'react-doctor --scope changed'));
  genericReactUiWithoutSsotEvidence.guardrails.push({
    ...g('lint-typecheck', 'he-implement', 'npm run lint && npm run typecheck'),
    evidence: ['React lint passed; TypeScript typecheck passed'],
  });
  genericReactUiWithoutSsotEvidence.guardrailInventory = {
    ...guardrailInventory({
      fallow: { id: 'fallow', status: 'required', guardrailId: 'fallow-audit', evidence: ['Fallow found no clone groups for React TypeScript files'] },
      'react-doctor': { id: 'react-doctor', status: 'required', guardrailId: 'react-doctor', evidence: ['React files changed'] },
      'lint-analyze-typecheck': { id: 'lint-analyze-typecheck', status: 'required', guardrailId: 'lint-typecheck', evidence: ['React lint and typecheck passed'] },
    }),
    touchedStacks: [touchedStack],
  };
  result = run(genericReactUiWithoutSsotEvidence);
  assert.notEqual(result.status, 0, `${touchedStack} should require SSOT evidence`);
  assert.match(result.stderr, /ssot-scanners cannot be not_applicable/);
}

const reactUiWithScannerButDefaultLedger = state('he-implement');
reactUiWithScannerButDefaultLedger.guardrails.push({
  ...g('fallow-audit', 'he-implement', 'fallow audit --dupes --base origin/main'),
  evidence: ['Fallow found no clone groups for React TypeScript files'],
});
reactUiWithScannerButDefaultLedger.guardrails.push(g('react-doctor', 'he-implement', 'react-doctor --scope changed'));
reactUiWithScannerButDefaultLedger.guardrails.push({
  ...g('lint-typecheck', 'he-implement', 'npm run lint && npm run typecheck'),
  evidence: ['React lint passed; TypeScript typecheck passed'],
});
reactUiWithScannerButDefaultLedger.guardrails.push(g('ssot-scan', 'he-implement', 'node scripts/check-ssot-guardrails.mjs .'));
reactUiWithScannerButDefaultLedger.guardrailInventory = {
  ...guardrailInventory({
    fallow: { id: 'fallow', status: 'required', guardrailId: 'fallow-audit', evidence: ['Fallow found no clone groups for React TypeScript files'] },
    'react-doctor': { id: 'react-doctor', status: 'required', guardrailId: 'react-doctor', evidence: ['React files changed'] },
    'lint-analyze-typecheck': { id: 'lint-analyze-typecheck', status: 'required', guardrailId: 'lint-typecheck', evidence: ['React lint and typecheck passed'] },
    'ssot-scanners': { id: 'ssot-scanners', status: 'required', guardrailId: 'ssot-scan', evidence: ['React UI owner checked'] },
  }),
  touchedStacks: ['src/App.tsx'],
};
result = run(reactUiWithScannerButDefaultLedger);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /ownerLedger coverage for touched owner classes/);

for (const touchedStack of ['migrations/001_add_users.sql', 'openapi.yaml', 'graphql/user.graphql']) {
  const schemaStackWithoutSsotEvidence = state('he-implement');
  schemaStackWithoutSsotEvidence.guardrailInventory = {
    ...guardrailInventory(),
    touchedStacks: [touchedStack],
  };
  result = run(schemaStackWithoutSsotEvidence);
  assert.notEqual(result.status, 0, `${touchedStack} should require schema-sensitive guardrails`);
  assert.match(result.stderr, /ssot-scanners cannot be not_applicable/);
}

const schemaStackWithScannersButDefaultLedger = state('he-implement');
schemaStackWithScannersButDefaultLedger.guardrails.push(g('ssot-scan', 'he-implement', 'node scripts/check-ssot-guardrails.mjs .'));
schemaStackWithScannersButDefaultLedger.guardrails.push({
  ...g('fallow-audit', 'he-implement', 'fallow audit --dupes --base origin/main'),
  evidence: ['rg duplicate search found no duplicate groups for SQL migrations'],
});
schemaStackWithScannersButDefaultLedger.guardrailInventory = {
  ...guardrailInventory({
    fallow: { id: 'fallow', status: 'required', guardrailId: 'fallow-audit', evidence: ['SQL migration duplicate search passed'] },
    'ssot-scanners': { id: 'ssot-scanners', status: 'required', guardrailId: 'ssot-scan', evidence: ['SQL migration schema owner checked'] },
  }),
  touchedStacks: ['migrations/001_add_users.sql'],
};
result = run(schemaStackWithScannersButDefaultLedger);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /ownerLedger coverage for touched owner classes/);

const reactWithoutFallow = state('he-implement');
reactWithoutFallow.guardrailInventory = {
  ...guardrailInventoryWithUiSsot(reactWithoutFallow),
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
reactWithFallow.guardrails.push({
  ...g('fallow-audit', 'he-implement', 'fallow audit --dupes --base origin/main'),
  evidence: ['Fallow found no clone groups for React TypeScript files'],
});
reactWithFallow.guardrails.push(g('react-doctor', 'he-implement', 'react-doctor --scope changed'));
reactWithFallow.guardrails.push({
  ...g('lint-typecheck', 'he-implement', 'npm run lint && npm run typecheck'),
  evidence: ['React lint passed; TypeScript typecheck passed'],
});
reactWithFallow.guardrailInventory = {
  ...guardrailInventoryWithUiSsot(reactWithFallow, {
    fallow: { id: 'fallow', status: 'required', guardrailId: 'fallow-audit', evidence: ['Fallow found no clone groups for React TypeScript files'] },
    'react-doctor': { id: 'react-doctor', status: 'required', guardrailId: 'react-doctor', evidence: ['React files changed'] },
    'lint-analyze-typecheck': { id: 'lint-analyze-typecheck', status: 'required', guardrailId: 'lint-typecheck', evidence: ['React lint and typecheck passed'] },
  }),
  touchedStacks: ['react', 'typescript'],
};
result = run(reactWithFallow);
assert.equal(result.status, 0, result.stderr);

const reactWithNextBuildTypecheckProof = state('he-implement');
reactWithNextBuildTypecheckProof.guardrails.push({
  ...g('fallow-audit', 'he-implement', 'fallow audit --dupes --base origin/main'),
  evidence: ['Fallow found no clone groups for React TypeScript files'],
});
reactWithNextBuildTypecheckProof.guardrails.push(g('react-doctor', 'he-implement', 'react-doctor --scope changed'));
reactWithNextBuildTypecheckProof.guardrails.push({
  ...g('lint-typecheck', 'he-implement', 'npm run lint && next build'),
  evidence: ['React lint passed; Next build passed'],
});
reactWithNextBuildTypecheckProof.guardrailInventory = {
  ...guardrailInventoryWithUiSsot(reactWithNextBuildTypecheckProof, {
    fallow: { id: 'fallow', status: 'required', guardrailId: 'fallow-audit', evidence: ['Fallow found no clone groups for React TypeScript files'] },
    'react-doctor': { id: 'react-doctor', status: 'required', guardrailId: 'react-doctor', evidence: ['React files changed'] },
    'lint-analyze-typecheck': { id: 'lint-analyze-typecheck', status: 'required', guardrailId: 'lint-typecheck', evidence: ['React lint passed; Next build passed'] },
  }),
  touchedStacks: ['react', 'typescript'],
};
result = run(reactWithNextBuildTypecheckProof);
assert.equal(result.status, 0, result.stderr);

const reactWithSkippedReactDoctor = state('he-implement');
reactWithSkippedReactDoctor.guardrails.push({
  ...g('fallow-audit', 'he-implement', 'fallow audit --dupes --base origin/main'),
  evidence: ['Fallow found no clone groups for React TypeScript files'],
});
reactWithSkippedReactDoctor.guardrails.push({
  ...g('react-doctor', 'he-implement', 'react-doctor --scope changed'),
  status: 'skipped',
  reason: 'not run',
  evidence: ['React Doctor skipped'],
});
reactWithSkippedReactDoctor.guardrails.push({
  ...g('lint-typecheck', 'he-implement', 'npm run lint && npm run typecheck'),
  evidence: ['React lint passed; TypeScript typecheck passed'],
});
reactWithSkippedReactDoctor.guardrailInventory = {
  ...guardrailInventoryWithUiSsot(reactWithSkippedReactDoctor, {
    fallow: { id: 'fallow', status: 'required', guardrailId: 'fallow-audit', evidence: ['Fallow found no clone groups for React TypeScript files'] },
    'react-doctor': { id: 'react-doctor', status: 'required', guardrailId: 'react-doctor', evidence: ['React files changed'] },
    'lint-analyze-typecheck': { id: 'lint-analyze-typecheck', status: 'required', guardrailId: 'lint-typecheck', evidence: ['React lint and typecheck passed'] },
  }),
  touchedStacks: ['react', 'typescript'],
};
result = run(reactWithSkippedReactDoctor);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /react-doctor requires passed React Doctor evidence/);

for (const evidence of [
  'React Doctor skipped',
  'React Doctor unavailable',
  'no React Doctor proof available',
  'React Doctor result failed',
]) {
  const reactWithNegativeReactDoctorEvidence = state('he-implement');
  reactWithNegativeReactDoctorEvidence.guardrails.push({
    ...g('fallow-audit', 'he-implement', 'fallow audit --dupes --base origin/main'),
    evidence: ['Fallow found no clone groups for React TypeScript files'],
  });
  reactWithNegativeReactDoctorEvidence.guardrails.push({
    ...g('react-doctor', 'he-implement', 'react-doctor --scope changed'),
    evidence: [evidence],
  });
  reactWithNegativeReactDoctorEvidence.guardrails.push({
    ...g('lint-typecheck', 'he-implement', 'npm run lint && npm run typecheck'),
    evidence: ['React lint passed; TypeScript typecheck passed'],
  });
  reactWithNegativeReactDoctorEvidence.guardrailInventory = {
    ...guardrailInventoryWithUiSsot(reactWithNegativeReactDoctorEvidence, {
      fallow: { id: 'fallow', status: 'required', guardrailId: 'fallow-audit', evidence: ['Fallow found no clone groups for React TypeScript files'] },
      'react-doctor': { id: 'react-doctor', status: 'required', guardrailId: 'react-doctor', evidence: [evidence] },
      'lint-analyze-typecheck': { id: 'lint-analyze-typecheck', status: 'required', guardrailId: 'lint-typecheck', evidence: ['React lint and typecheck passed'] },
    }),
    touchedStacks: ['react', 'typescript'],
  };
  result = run(reactWithNegativeReactDoctorEvidence);
  assert.notEqual(result.status, 0, evidence);
  assert.match(result.stderr, /react-doctor requires passed React Doctor evidence/);
}

const reactWithoutReactDoctorOrLint = state('he-implement');
reactWithoutReactDoctorOrLint.guardrails.push(g('fallow-audit', 'he-implement', 'fallow audit --dupes --base origin/main'));
reactWithoutReactDoctorOrLint.guardrailInventory = {
  ...guardrailInventoryWithUiSsot(reactWithoutReactDoctorOrLint, {
    fallow: { id: 'fallow', status: 'required', guardrailId: 'fallow-audit', evidence: ['Fallow found no clone groups for React TypeScript files'] },
  }),
  touchedStacks: ['react', 'typescript'],
};
result = run(reactWithoutReactDoctorOrLint);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /react-doctor cannot be not_applicable/);
assert.match(result.stderr, /lint-analyze-typecheck cannot be not_applicable/);

const reactWithLintOnlyProof = state('he-implement');
reactWithLintOnlyProof.guardrails.push({
  ...g('fallow-audit', 'he-implement', 'fallow audit --dupes --base origin/main'),
  evidence: ['Fallow found no clone groups for React TypeScript files'],
});
reactWithLintOnlyProof.guardrails.push(g('react-doctor', 'he-implement', 'react-doctor --scope changed'));
reactWithLintOnlyProof.guardrails.push({
  ...g('lint-typecheck', 'he-implement', 'npm run lint'),
  evidence: ['React lint passed'],
});
reactWithLintOnlyProof.guardrailInventory = {
  ...guardrailInventoryWithUiSsot(reactWithLintOnlyProof, {
    fallow: { id: 'fallow', status: 'required', guardrailId: 'fallow-audit', evidence: ['Fallow found no clone groups for React TypeScript files'] },
    'react-doctor': { id: 'react-doctor', status: 'required', guardrailId: 'react-doctor', evidence: ['React files changed'] },
    'lint-analyze-typecheck': { id: 'lint-analyze-typecheck', status: 'required', guardrailId: 'lint-typecheck', evidence: ['React lint passed'] },
  }),
  touchedStacks: ['react', 'typescript'],
};
result = run(reactWithLintOnlyProof);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /lint-analyze-typecheck requires lint\/analyze and typecheck evidence/);

const reactWithSkippedTypecheckProof = state('he-implement');
reactWithSkippedTypecheckProof.guardrails.push({
  ...g('fallow-audit', 'he-implement', 'fallow audit --dupes --base origin/main'),
  evidence: ['Fallow found no clone groups for React TypeScript files'],
});
reactWithSkippedTypecheckProof.guardrails.push(g('react-doctor', 'he-implement', 'react-doctor --scope changed'));
reactWithSkippedTypecheckProof.guardrails.push({
  ...g('lint-typecheck', 'he-implement', 'npm run lint && npm run typecheck'),
  evidence: ['React lint passed; typecheck skipped'],
});
reactWithSkippedTypecheckProof.guardrailInventory = {
  ...guardrailInventoryWithUiSsot(reactWithSkippedTypecheckProof, {
    fallow: { id: 'fallow', status: 'required', guardrailId: 'fallow-audit', evidence: ['Fallow found no clone groups for React TypeScript files'] },
    'react-doctor': { id: 'react-doctor', status: 'required', guardrailId: 'react-doctor', evidence: ['React files changed'] },
    'lint-analyze-typecheck': { id: 'lint-analyze-typecheck', status: 'required', guardrailId: 'lint-typecheck', evidence: ['React lint passed; typecheck skipped'] },
  }),
  touchedStacks: ['react', 'typescript'],
};
result = run(reactWithSkippedTypecheckProof);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /lint-analyze-typecheck requires lint\/analyze and typecheck evidence/);

const reactWithCommandOnlyLintProof = state('he-implement');
reactWithCommandOnlyLintProof.guardrails.push({
  ...g('fallow-audit', 'he-implement', 'fallow audit --dupes --base origin/main'),
  evidence: ['Fallow found no clone groups for React TypeScript files'],
});
reactWithCommandOnlyLintProof.guardrails.push(g('react-doctor', 'he-implement', 'react-doctor --scope changed'));
reactWithCommandOnlyLintProof.guardrails.push({
  ...g('lint-typecheck', 'he-implement', 'npm run lint && npm run typecheck'),
  evidence: ['TypeScript typecheck passed'],
});
reactWithCommandOnlyLintProof.guardrailInventory = {
  ...guardrailInventoryWithUiSsot(reactWithCommandOnlyLintProof, {
    fallow: { id: 'fallow', status: 'required', guardrailId: 'fallow-audit', evidence: ['Fallow found no clone groups for React TypeScript files'] },
    'react-doctor': { id: 'react-doctor', status: 'required', guardrailId: 'react-doctor', evidence: ['React files changed'] },
    'lint-analyze-typecheck': { id: 'lint-analyze-typecheck', status: 'required', guardrailId: 'lint-typecheck', evidence: ['TypeScript typecheck passed'] },
  }),
  touchedStacks: ['react', 'typescript'],
};
result = run(reactWithCommandOnlyLintProof);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /lint-analyze-typecheck requires lint\/analyze and typecheck evidence/);

const reactWithFailedLintProof = state('he-implement');
reactWithFailedLintProof.guardrails.push({
  ...g('fallow-audit', 'he-implement', 'fallow audit --dupes --base origin/main'),
  evidence: ['Fallow found no clone groups for React TypeScript files'],
});
reactWithFailedLintProof.guardrails.push(g('react-doctor', 'he-implement', 'react-doctor --scope changed'));
reactWithFailedLintProof.guardrails.push({
  ...g('lint-typecheck', 'he-implement', 'npm run lint && npm run typecheck'),
  evidence: ['ESLint failed; TypeScript typecheck passed'],
});
reactWithFailedLintProof.guardrailInventory = {
  ...guardrailInventoryWithUiSsot(reactWithFailedLintProof, {
    fallow: { id: 'fallow', status: 'required', guardrailId: 'fallow-audit', evidence: ['Fallow found no clone groups for React TypeScript files'] },
    'react-doctor': { id: 'react-doctor', status: 'required', guardrailId: 'react-doctor', evidence: ['React files changed'] },
    'lint-analyze-typecheck': { id: 'lint-analyze-typecheck', status: 'required', guardrailId: 'lint-typecheck', evidence: ['ESLint failed; TypeScript typecheck passed'] },
  }),
  touchedStacks: ['react', 'typescript'],
};
result = run(reactWithFailedLintProof);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /lint-analyze-typecheck requires lint\/analyze and typecheck evidence/);

const reactWithFailedTypecheckProof = state('he-implement');
reactWithFailedTypecheckProof.guardrails.push({
  ...g('fallow-audit', 'he-implement', 'fallow audit --dupes --base origin/main'),
  evidence: ['Fallow found no clone groups for React TypeScript files'],
});
reactWithFailedTypecheckProof.guardrails.push(g('react-doctor', 'he-implement', 'react-doctor --scope changed'));
reactWithFailedTypecheckProof.guardrails.push({
  ...g('lint-typecheck', 'he-implement', 'npm run lint && npm run typecheck'),
  evidence: ['React lint passed; TypeScript typecheck result failed'],
});
reactWithFailedTypecheckProof.guardrailInventory = {
  ...guardrailInventoryWithUiSsot(reactWithFailedTypecheckProof, {
    fallow: { id: 'fallow', status: 'required', guardrailId: 'fallow-audit', evidence: ['Fallow found no clone groups for React TypeScript files'] },
    'react-doctor': { id: 'react-doctor', status: 'required', guardrailId: 'react-doctor', evidence: ['React files changed'] },
    'lint-analyze-typecheck': { id: 'lint-analyze-typecheck', status: 'required', guardrailId: 'lint-typecheck', evidence: ['React lint passed; TypeScript typecheck result failed'] },
  }),
  touchedStacks: ['react', 'typescript'],
};
result = run(reactWithFailedTypecheckProof);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /lint-analyze-typecheck requires lint\/analyze and typecheck evidence/);

const reactWithNonJsLintTypecheckProof = state('he-implement');
reactWithNonJsLintTypecheckProof.guardrails.push({
  ...g('fallow-audit', 'he-implement', 'fallow audit --dupes --base origin/main'),
  evidence: ['Fallow found no clone groups for React TypeScript files'],
});
reactWithNonJsLintTypecheckProof.guardrails.push(g('react-doctor', 'he-implement', 'react-doctor --scope changed'));
reactWithNonJsLintTypecheckProof.guardrails.push({
  ...g('lint-typecheck', 'he-implement', 'ruff check . && mypy .'),
  evidence: ['ruff lint passed; mypy typecheck passed'],
});
reactWithNonJsLintTypecheckProof.guardrailInventory = {
  ...guardrailInventoryWithUiSsot(reactWithNonJsLintTypecheckProof, {
    fallow: { id: 'fallow', status: 'required', guardrailId: 'fallow-audit', evidence: ['Fallow found no clone groups for React TypeScript files'] },
    'react-doctor': { id: 'react-doctor', status: 'required', guardrailId: 'react-doctor', evidence: ['React files changed'] },
    'lint-analyze-typecheck': { id: 'lint-analyze-typecheck', status: 'required', guardrailId: 'lint-typecheck', evidence: ['ruff lint passed; mypy typecheck passed'] },
  }),
  touchedStacks: ['react', 'typescript'],
};
result = run(reactWithNonJsLintTypecheckProof);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /lint-analyze-typecheck requires lint\/analyze and typecheck evidence/);

const reactWithReactLintMypyTypecheckProof = state('he-implement');
reactWithReactLintMypyTypecheckProof.guardrails.push({
  ...g('fallow-audit', 'he-implement', 'fallow audit --dupes --base origin/main'),
  evidence: ['Fallow found no clone groups for React TypeScript files'],
});
reactWithReactLintMypyTypecheckProof.guardrails.push(g('react-doctor', 'he-implement', 'react-doctor --scope changed'));
reactWithReactLintMypyTypecheckProof.guardrails.push({
  ...g('lint-typecheck', 'he-implement', 'ruff check . && mypy .'),
  evidence: ['React lint passed; mypy typecheck passed'],
});
reactWithReactLintMypyTypecheckProof.guardrailInventory = {
  ...guardrailInventoryWithUiSsot(reactWithReactLintMypyTypecheckProof, {
    fallow: { id: 'fallow', status: 'required', guardrailId: 'fallow-audit', evidence: ['Fallow found no clone groups for React TypeScript files'] },
    'react-doctor': { id: 'react-doctor', status: 'required', guardrailId: 'react-doctor', evidence: ['React files changed'] },
    'lint-analyze-typecheck': { id: 'lint-analyze-typecheck', status: 'required', guardrailId: 'lint-typecheck', evidence: ['React lint passed; mypy typecheck passed'] },
  }),
  touchedStacks: ['react', 'typescript'],
};
result = run(reactWithReactLintMypyTypecheckProof);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /lint-analyze-typecheck requires lint\/analyze and typecheck evidence/);

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

const jsWithInventoryOnlyDuplicateFallow = state('he-implement');
jsWithInventoryOnlyDuplicateFallow.guardrails.push(g('fallow-audit', 'he-implement', 'fallow audit --dupes --base origin/main'));
jsWithInventoryOnlyDuplicateFallow.guardrailInventory = {
  ...guardrailInventory({
    fallow: { id: 'fallow', status: 'required', guardrailId: 'fallow-audit', evidence: ['Fallow found no clone groups for React TypeScript files'] },
  }),
  touchedStacks: ['scripts/foo.mjs'],
};
result = run(jsWithInventoryOnlyDuplicateFallow);
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

const jsWithFoundCloneFallow = state('he-implement');
jsWithFoundCloneFallow.guardrails.push({
  ...g('fallow-audit', 'he-implement', 'fallow audit --dupes --base origin/main'),
  evidence: ['Fallow found clone groups'],
});
jsWithFoundCloneFallow.guardrailInventory = {
  ...guardrailInventory({
    fallow: { id: 'fallow', status: 'required', guardrailId: 'fallow-audit', evidence: ['Fallow found clone groups'] },
  }),
  touchedStacks: ['scripts/foo.mjs'],
};
result = run(jsWithFoundCloneFallow);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /Fallow duplicate\/clone evidence/);

const jsWithFallowInventoryCloneDecision = state('he-implement');
jsWithFallowInventoryCloneDecision.guardrails.push({
  ...g('fallow-audit', 'he-implement', 'fallow audit --dupes --base origin/main'),
  evidence: ['Fallow found clone groups'],
});
jsWithFallowInventoryCloneDecision.guardrailInventory = {
  ...guardrailInventory({
    fallow: { id: 'fallow', status: 'required', guardrailId: 'fallow-audit', evidence: ['SSOT owner decision recorded for clone groups'] },
  }),
  touchedStacks: ['scripts/foo.mjs'],
};
result = run(jsWithFallowInventoryCloneDecision);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /Fallow duplicate\/clone evidence/);

const jsWithFoundCloneDecision = state('he-implement');
jsWithFoundCloneDecision.decisions = [{
  id: 'js-clone-owner-decision',
  status: 'accepted',
  summary: 'SSOT owner decision recorded for JavaScript clone groups',
  evidence: ['owner ledger resolved duplicate clone groups'],
}];
jsWithFoundCloneDecision.guardrails.push({
  ...g('fallow-audit', 'he-implement', 'fallow audit --dupes --base origin/main'),
  evidence: ['Fallow found clone groups'],
});
jsWithFoundCloneDecision.guardrailInventory = {
  ...guardrailInventory({
    fallow: { id: 'fallow', status: 'required', guardrailId: 'fallow-audit', evidence: ['Fallow found clone groups'] },
  }),
  touchedStacks: ['scripts/foo.mjs'],
};
result = run(jsWithFoundCloneDecision);
assert.equal(result.status, 0, result.stderr);

const mixedJsNonJsWithoutCloneFallback = state('he-implement');
mixedJsNonJsWithoutCloneFallback.guardrails.push(g('fallow-audit', 'he-implement', 'fallow audit --dupes --base origin/main'));
mixedJsNonJsWithoutCloneFallback.guardrailInventory = {
  ...guardrailInventoryWithUiSsot(mixedJsNonJsWithoutCloneFallback, {
    fallow: { id: 'fallow', status: 'required', guardrailId: 'fallow-audit', evidence: ['Fallow found no clone groups for TSX files'] },
  }),
  touchedStacks: ['src/App.tsx', 'scripts/migrate.py'],
};
result = run(mixedJsNonJsWithoutCloneFallback);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /explicit non-JS no-duplicate\/no-clone static-search proof/);

const mixedJsNonJsWithCloneFallback = state('he-implement');
mixedJsNonJsWithCloneFallback.guardrails.push({
  ...g('fallow-audit', 'he-implement', 'fallow audit --dupes --base origin/main'),
  evidence: ['Fallow found no clone groups for TSX files', 'rg static search found no clone groups for scripts/migrate.py'],
});
mixedJsNonJsWithCloneFallback.guardrails.push(g('react-doctor', 'he-implement', 'react-doctor --scope changed'));
mixedJsNonJsWithCloneFallback.guardrails.push({
  ...g('lint-typecheck', 'he-implement', 'npm run lint && npm run typecheck'),
  evidence: ['React lint passed; TypeScript typecheck passed'],
});
mixedJsNonJsWithCloneFallback.guardrailInventory = {
  ...guardrailInventoryWithUiSsot(mixedJsNonJsWithCloneFallback, {
    fallow: { id: 'fallow', status: 'required', guardrailId: 'fallow-audit', evidence: ['Fallow found no clone groups for TSX files'] },
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

const flutterWithNoProofCloneFallback = state('he-implement');
flutterWithNoProofCloneFallback.guardrailInventory = {
  ...guardrailInventory({
    fallow: {
      id: 'fallow',
      status: 'not_applicable',
      reason: 'no stack-specific clone detector available for Dart in this repo',
      evidence: ['tool unavailable; rg duplicate search: no duplicate evidence available'],
    },
  }),
  touchedStacks: ['flutter', 'dart'],
};
result = run(flutterWithNoProofCloneFallback);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /explicit no-duplicate\/no-clone static-search proof/);

const flutterWithWeakToolAbsenceCloneFallback = state('he-implement');
flutterWithWeakToolAbsenceCloneFallback.guardrailInventory = {
  ...guardrailInventory({
    fallow: {
      id: 'fallow',
      status: 'not_applicable',
      reason: 'no stack-specific changes in Dart',
      evidence: ['rg static search duplicate search found no clone groups near touched widgets'],
    },
  }),
  touchedStacks: ['flutter', 'dart'],
};
result = run(flutterWithWeakToolAbsenceCloneFallback);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /explicit no-duplicate\/no-clone static-search proof/);

const flutterWithWeakToolAbsenceAndDuplicateCheck = state('he-implement');
flutterWithWeakToolAbsenceAndDuplicateCheck.guardrailInventory = {
  ...guardrailInventory({
    fallow: {
      id: 'fallow',
      status: 'not_applicable',
      reason: 'no stack-specific changes in Dart',
      evidence: ['rg duplicate check found no clone groups near touched widgets'],
    },
  }),
  touchedStacks: ['flutter', 'dart'],
};
result = run(flutterWithWeakToolAbsenceAndDuplicateCheck);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /explicit no-duplicate\/no-clone static-search proof/);

const flutterWithGenericToolUnavailableCloneFallback = state('he-implement');
flutterWithGenericToolUnavailableCloneFallback.guardrailInventory = {
  ...guardrailInventory({
    fallow: {
      id: 'fallow',
      status: 'not_applicable',
      reason: 'tool unavailable',
      evidence: ['rg duplicate search found no clone groups near touched widgets'],
    },
  }),
  touchedStacks: ['flutter', 'dart'],
};
result = run(flutterWithGenericToolUnavailableCloneFallback);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /explicit no-duplicate\/no-clone static-search proof/);

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

const flutterWithSkippedRequiredFallowStaticProof = state('he-implement');
flutterWithSkippedRequiredFallowStaticProof.guardrails.push({
  ...g('fallow-audit', 'he-implement', 'fallow audit --dupes --base origin/main'),
  status: 'skipped',
  reason: 'tool skipped',
  evidence: ['rg static search found no duplicate groups for lib/main.dart'],
});
flutterWithSkippedRequiredFallowStaticProof.guardrailInventory = {
  ...guardrailInventory({
    fallow: {
      id: 'fallow',
      status: 'required',
      guardrailId: 'fallow-audit',
      evidence: ['rg static search found no duplicate groups for lib/main.dart'],
    },
  }),
  touchedStacks: ['flutter', 'dart'],
};
result = run(flutterWithSkippedRequiredFallowStaticProof);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /fallow required for non-JS\/TS stacks requires explicit no-duplicate\/no-clone/);

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

for (const evidence of [
  'tool unavailable; rg duplicate search clone groups none near touched widgets',
  'tool unavailable; rg duplicate search duplicates absent near touched widgets',
  'tool unavailable; rg duplicate result: none near touched widgets',
  'tool unavailable; rg duplicate output: not found near touched widgets',
]) {
  const flutterWithNoneCloneFallback = state('he-implement');
  flutterWithNoneCloneFallback.guardrailInventory = {
    ...guardrailInventory({
      fallow: {
        id: 'fallow',
        status: 'not_applicable',
        reason: 'no stack-specific clone detector available for Dart in this repo',
        evidence: [evidence],
      },
    }),
    touchedStacks: ['flutter', 'dart'],
  };
  result = run(flutterWithNoneCloneFallback);
  assert.equal(result.status, 0, result.stderr);
}

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

const flutterWithSentenceFoundCloneEvidence = state('he-implement');
flutterWithSentenceFoundCloneEvidence.guardrailInventory = {
  ...guardrailInventory({
    fallow: {
      id: 'fallow',
      status: 'not_applicable',
      reason: 'no stack-specific clone detector available for Dart in this repo',
      evidence: ['tool unavailable; rg duplicate search found no duplicate groups. Found clone groups'],
    },
  }),
  touchedStacks: ['flutter', 'dart'],
};
result = run(flutterWithSentenceFoundCloneEvidence);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /explicit no-duplicate\/no-clone static-search proof/);

for (const evidence of [
  'tool unavailable; rg duplicate search found no clone groups. Detected copy-paste widgets',
  'tool unavailable; rg duplicate search found no clone groups. Reported near-duplicate widgets',
]) {
  const flutterWithAliasCloneEvidence = state('he-implement');
  flutterWithAliasCloneEvidence.guardrailInventory = {
    ...guardrailInventory({
      fallow: {
        id: 'fallow',
        status: 'not_applicable',
        reason: 'no stack-specific clone detector available for Dart in this repo',
        evidence: [evidence],
      },
    }),
    touchedStacks: ['flutter', 'dart'],
  };
  result = run(flutterWithAliasCloneEvidence);
  assert.notEqual(result.status, 0, evidence);
  assert.match(result.stderr, /explicit no-duplicate\/no-clone static-search proof/);
}

const flutterWithNumericCloneCount = state('he-implement');
flutterWithNumericCloneCount.guardrailInventory = {
  ...guardrailInventory({
    fallow: {
      id: 'fallow',
      status: 'not_applicable',
      reason: 'no stack-specific clone detector available for Dart in this repo',
      evidence: ['tool unavailable; rg found no duplicate groups; 2 clone groups in copied widgets'],
    },
  }),
  touchedStacks: ['flutter', 'dart'],
};
result = run(flutterWithNumericCloneCount);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /explicit no-duplicate\/no-clone static-search proof/);

const flutterWithNumericCloneCountAfterAnd = state('he-implement');
flutterWithNumericCloneCountAfterAnd.guardrailInventory = {
  ...guardrailInventory({
    fallow: {
      id: 'fallow',
      status: 'not_applicable',
      reason: 'no stack-specific clone detector available for Dart in this repo',
      evidence: ['tool unavailable; rg found no duplicate groups and 2 clone groups'],
    },
  }),
  touchedStacks: ['flutter', 'dart'],
};
result = run(flutterWithNumericCloneCountAfterAnd);
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

const flutterWithGenericSsotScannerCloneText = state('he-implement');
flutterWithGenericSsotScannerCloneText.guardrails.push(g('ssot-scan', 'he-implement', 'node scripts/check-ssot-guardrails.mjs .'));
flutterWithGenericSsotScannerCloneText.guardrailInventory = {
  ...guardrailInventory({
    'ssot-scanners': {
      id: 'ssot-scanners',
      status: 'required',
      guardrailId: 'ssot-scan',
      evidence: ['duplicate SSOT scanner passed'],
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
result = run(flutterWithGenericSsotScannerCloneText);
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

const riskyAgentWorkRequiresBoundary = state('he-verify');
riskyAgentWorkRequiresBoundary.agentWork = [{
  id: 'browser-agent',
  kind: 'subagent',
  model: 'gpt-5.5',
  purpose: 'E2E smoke',
  status: 'done',
  evidence: ['sent production SMS'],
}];
result = run(riskyAgentWorkRequiresBoundary);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /approvalBoundaries are required/);

const riskyStepReceiptRequiresBoundary = state('he-verify');
riskyStepReceiptRequiresBoundary.steps = [{
  ...riskyStepReceiptRequiresBoundary.steps[0],
  receipt: {
    ...riskyStepReceiptRequiresBoundary.steps[0].receipt,
    ownerProof: ['sent production SMS'],
  },
}];
result = run(riskyStepReceiptRequiresBoundary);
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

const changedScannerPreventionWithBackendDoesNotRequireApproval = state('he-verify');
changedScannerPreventionWithBackendDoesNotRequireApproval.guardrails.push({
  ...g('scanner-prevents-prod-backend-writes', 'he-verify', 'node scripts/check-no-prod-writes.mjs'),
  evidence: ['changed scanner to prevent prod backend writes'],
});
result = run(changedScannerPreventionWithBackendDoesNotRequireApproval);
assert.equal(result.status, 0, result.stderr);

const preventionThenRiskySideEffectRequiresBoundary = state('he-verify');
preventionThenRiskySideEffectRequiresBoundary.guardrails.push({
  ...g('scanner-prevents-prod-writes', 'he-verify', 'node scripts/check-no-prod-writes.mjs'),
  evidence: ['changed scanner to prevent prod writes after sending production SMS'],
});
result = run(preventionThenRiskySideEffectRequiresBoundary);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /approvalBoundaries are required/);

const preventionBeforeRiskySideEffectRequiresBoundary = state('he-verify');
preventionBeforeRiskySideEffectRequiresBoundary.guardrails.push({
  ...g('scanner-prevents-prod-writes', 'he-verify', 'node scripts/check-no-prod-writes.mjs'),
  evidence: ['changed scanner to prevent prod writes before sending production SMS'],
});
result = run(preventionBeforeRiskySideEffectRequiresBoundary);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /approvalBoundaries are required/);

const preventionFillerThenRiskySideEffectRequiresBoundary = state('he-verify');
preventionFillerThenRiskySideEffectRequiresBoundary.guardrails.push({
  ...g('scanner-prevents-prod-writes', 'he-verify', 'node scripts/check-no-prod-writes.mjs'),
  evidence: ['changed scanner to prevent prod writes after we sent production SMS'],
});
result = run(preventionFillerThenRiskySideEffectRequiresBoundary);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /approvalBoundaries are required/);

const preventionBecauseRiskySideEffectRequiresBoundary = state('he-verify');
preventionBecauseRiskySideEffectRequiresBoundary.guardrails.push({
  ...g('scanner-prevents-prod-writes', 'he-verify', 'node scripts/check-no-prod-writes.mjs'),
  evidence: ['changed scanner to prevent prod writes because we sent production SMS'],
});
result = run(preventionBecauseRiskySideEffectRequiresBoundary);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /approvalBoundaries are required/);

const preventionSinceRiskySideEffectRequiresBoundary = state('he-verify');
preventionSinceRiskySideEffectRequiresBoundary.guardrails.push({
  ...g('scanner-prevents-prod-writes', 'he-verify', 'node scripts/check-no-prod-writes.mjs'),
  evidence: ['changed scanner to prevent prod writes since we sent production SMS'],
});
result = run(preventionSinceRiskySideEffectRequiresBoundary);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /approvalBoundaries are required/);

const preventionUnlistedConnectorRiskySideEffectRequiresBoundary = state('he-verify');
preventionUnlistedConnectorRiskySideEffectRequiresBoundary.guardrails.push({
  ...g('scanner-prevents-prod-writes', 'he-verify', 'node scripts/check-no-prod-writes.mjs'),
  evidence: ['changed scanner to prevent prod writes as we sent production SMS'],
});
result = run(preventionUnlistedConnectorRiskySideEffectRequiresBoundary);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /approvalBoundaries are required/);

const preventionFollowingRiskySideEffectRequiresBoundary = state('he-verify');
preventionFollowingRiskySideEffectRequiresBoundary.guardrails.push({
  ...g('scanner-prevents-prod-writes', 'he-verify', 'node scripts/check-no-prod-writes.mjs'),
  evidence: ['changed scanner to prevent prod writes following sending production SMS'],
});
result = run(preventionFollowingRiskySideEffectRequiresBoundary);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /approvalBoundaries are required/);

const preventionObjectBeforeVerbSideEffectRequiresBoundary = state('he-verify');
preventionObjectBeforeVerbSideEffectRequiresBoundary.guardrails.push({
  ...g('scanner-prevents-prod-writes', 'he-verify', 'node scripts/check-no-prod-writes.mjs'),
  evidence: ['changed scanner to prevent prod writes following production SMS sent'],
});
result = run(preventionObjectBeforeVerbSideEffectRequiresBoundary);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /approvalBoundaries are required/);

const negatedThenTemporalRiskySideEffectRequiresBoundary = state('he-verify');
negatedThenTemporalRiskySideEffectRequiresBoundary.guardrails.push({
  ...g('safe-boundary-check', 'he-verify', 'node scripts/check-safe-boundaries.mjs'),
  evidence: ['no prod mutation after sending production SMS'],
});
result = run(negatedThenTemporalRiskySideEffectRequiresBoundary);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /approvalBoundaries are required/);

const negatedThenDuringRiskySideEffectRequiresBoundary = state('he-verify');
negatedThenDuringRiskySideEffectRequiresBoundary.guardrails.push({
  ...g('safe-boundary-check', 'he-verify', 'node scripts/check-safe-boundaries.mjs'),
  evidence: ['no prod mutation during sending production SMS'],
});
result = run(negatedThenDuringRiskySideEffectRequiresBoundary);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /approvalBoundaries are required/);

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
  'production SMS not sent',
  'native permission prompt not shown',
  'without prod email side effects',
  'no prod payment charged',
  'no production data shared',
  'sent no production SMS',
  'sent zero production emails',
  'not sending production SMS',
  'without charging prod card',
  'not notifying production user',
  'prod cleanup not needed',
  'production cleanup not required',
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
  'deleted production user',
  'created prod account',
  'updated Appwrite permissions in prod',
  'modified production database schema',
  'granted prod account access',
  'revoked production user access',
  'invited production user',
  'notified prod account',
  'disabled production account',
  'enabled prod user',
  'suspended production user',
  'deactivated prod account',
  'removed production user',
  'reset prod account',
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

const signedInPersonalAccountRequiresBoundary = state('he-verify');
signedInPersonalAccountRequiresBoundary.guardrails.push({
  ...g('real-account-login', 'he-verify', 'node scripts/check-login.mjs'),
  evidence: ['signed in with personal account'],
});
result = run(signedInPersonalAccountRequiresBoundary);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /approvalBoundaries are required/);

for (const evidence of [
  'log in with personal account',
  'logging in with real account',
  'sign in with saved account',
]) {
  const realAccountLoginAliasRequiresBoundary = state('he-verify');
  realAccountLoginAliasRequiresBoundary.guardrails.push({
    ...g('real-account-login', 'he-verify', 'node scripts/check-login.mjs'),
    evidence: [evidence],
  });
  result = run(realAccountLoginAliasRequiresBoundary);
  assert.notEqual(result.status, 0, evidence);
  assert.match(result.stderr, /approvalBoundaries are required/);
}

const riskyE2eWithDerivedBoundaries = state('he-verify');
riskyE2eWithDerivedBoundaries.guardrails = riskyE2eWithoutPolicyTrigger.guardrails;
riskyE2eWithDerivedBoundaries.approvalBoundaries = [
  { id: 'prod-db-permission', category: 'prod-backend-write', status: 'approved', reason: 'user approved exact backend permission mutation', evidence: ['approval quote recorded'] },
  { id: 'prod-db-schema-index', category: 'prod-backend-write', status: 'approved', reason: 'user approved exact backend schema index mutation', evidence: ['approval quote recorded'] },
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

const negatedBoundaryTextDoesNotApproveSideEffect = state('he-verify');
negatedBoundaryTextDoesNotApproveSideEffect.guardrails.push({
  ...g('e2e-side-effects', 'he-verify', 'npx playwright test e2e/checkout.spec.ts'),
  evidence: ['sent production SMS'],
});
negatedBoundaryTextDoesNotApproveSideEffect.approvalBoundaries = [
  { id: 'prod-appwrite-permission', category: 'prod-backend-write', status: 'approved', reason: 'production SMS was not approved', evidence: ['no production SMS sent'] },
];
result = run(negatedBoundaryTextDoesNotApproveSideEffect);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /approvalBoundaries requires prod-backend-write side effect prod-sms/);

const boundaryIdDoesNotApproveSideEffect = state('he-verify');
boundaryIdDoesNotApproveSideEffect.guardrails.push({
  ...g('e2e-side-effects', 'he-verify', 'npx playwright test e2e/checkout.spec.ts'),
  evidence: ['sent production SMS'],
});
boundaryIdDoesNotApproveSideEffect.approvalBoundaries = [
  { id: 'prod-sms-send', category: 'prod-backend-write', status: 'approved', reason: 'user approved exact Appwrite permission mutation', evidence: ['approval quote recorded'] },
];
result = run(boundaryIdDoesNotApproveSideEffect);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /approvalBoundaries requires prod-backend-write side effect prod-sms/);

for (const reason of [
  'production SMS approval not required',
  'production SMS approval not needed',
]) {
  const nonRequiredApprovalTextDoesNotApproveSideEffect = state('he-verify');
  nonRequiredApprovalTextDoesNotApproveSideEffect.guardrails.push({
    ...g('e2e-side-effects', 'he-verify', 'npx playwright test e2e/checkout.spec.ts'),
    evidence: ['sent production SMS'],
  });
  nonRequiredApprovalTextDoesNotApproveSideEffect.approvalBoundaries = [
    { id: 'prod-sms', category: 'prod-backend-write', status: 'approved', reason, evidence: ['approval quote recorded'] },
  ];
  result = run(nonRequiredApprovalTextDoesNotApproveSideEffect);
  assert.notEqual(result.status, 0, reason);
  assert.match(result.stderr, /approvalBoundaries requires prod-backend-write side effect prod-sms/);
}

for (const reason of [
  'production SMS approval required',
  'production SMS approval requested',
  'production SMS approval pending',
  'awaiting production SMS approval',
]) {
  const pendingApprovalTextDoesNotApproveSideEffect = state('he-verify');
  pendingApprovalTextDoesNotApproveSideEffect.guardrails.push({
    ...g('e2e-side-effects', 'he-verify', 'npx playwright test e2e/checkout.spec.ts'),
    evidence: ['sent production SMS'],
  });
  pendingApprovalTextDoesNotApproveSideEffect.approvalBoundaries = [
    { id: 'prod-sms', category: 'prod-backend-write', sideEffectKey: 'prod-sms', status: 'approved', reason, evidence: ['approval ticket recorded'] },
  ];
  result = run(pendingApprovalTextDoesNotApproveSideEffect);
  assert.notEqual(result.status, 0, reason);
  assert.match(result.stderr, /approvalBoundaries requires prod-backend-write side effect prod-sms/);
}

const distinctProdSideEffectsApproved = state('he-verify');
distinctProdSideEffectsApproved.guardrails = distinctProdSideEffectsNeedDistinctBoundaries.guardrails;
distinctProdSideEffectsApproved.approvalBoundaries = [
  { id: 'prod-db-permission', category: 'prod-backend-write', status: 'approved', reason: 'user approved exact Appwrite permission mutation', evidence: ['approval quote recorded'] },
  { id: 'prod-sms-send', category: 'prod-backend-write', status: 'approved', reason: 'user approved production SMS send', evidence: ['approval quote recorded'] },
];
result = run(distinctProdSideEffectsApproved);
assert.equal(result.status, 0, result.stderr);

const smsToCustomerDoesNotRequirePaymentBoundary = state('he-verify');
smsToCustomerDoesNotRequirePaymentBoundary.guardrails.push({
  ...g('e2e-side-effects', 'he-verify', 'npx playwright test e2e/checkout.spec.ts'),
  evidence: ['sent production SMS to customer'],
});
smsToCustomerDoesNotRequirePaymentBoundary.approvalBoundaries = [
  { id: 'prod-sms-send', category: 'prod-backend-write', status: 'approved', reason: 'user approved production SMS send', evidence: ['approval quote recorded'] },
];
result = run(smsToCustomerDoesNotRequirePaymentBoundary);
assert.equal(result.status, 0, result.stderr);

const smsCustomerApprovalDoesNotApprovePayment = state('he-verify');
smsCustomerApprovalDoesNotApprovePayment.guardrails.push({
  ...g('e2e-side-effects', 'he-verify', 'npx playwright test e2e/checkout.spec.ts'),
  evidence: ['charged prod card'],
});
smsCustomerApprovalDoesNotApprovePayment.approvalBoundaries = [
  { id: 'prod-sms-customer', category: 'prod-backend-write', status: 'approved', reason: 'user approved sent production SMS to customer', evidence: ['approval quote recorded'] },
];
result = run(smsCustomerApprovalDoesNotApprovePayment);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /approvalBoundaries requires prod-backend-write side effect prod-payment/);

const structuredSideEffectKeyApprovesBoundary = state('he-verify');
structuredSideEffectKeyApprovesBoundary.guardrails.push({
  ...g('e2e-side-effects', 'he-verify', 'npx playwright test e2e/checkout.spec.ts'),
  evidence: ['sent production SMS'],
});
structuredSideEffectKeyApprovesBoundary.approvalBoundaries = [
  { id: 'prod-side-effect-approval', category: 'prod-backend-write', sideEffectKey: 'prod-sms', status: 'approved', reason: 'user approved exact production side effect', evidence: ['approval quote recorded'] },
];
result = run(structuredSideEffectKeyApprovesBoundary);
assert.equal(result.status, 0, result.stderr);

const structuredSideEffectKeyNeedsAffirmativeProof = state('he-verify');
structuredSideEffectKeyNeedsAffirmativeProof.guardrails.push({
  ...g('e2e-side-effects', 'he-verify', 'npx playwright test e2e/checkout.spec.ts'),
  evidence: ['sent production SMS'],
});
structuredSideEffectKeyNeedsAffirmativeProof.approvalBoundaries = [
  { id: 'prod-side-effect-approval', category: 'prod-backend-write', sideEffectKey: 'prod-sms', status: 'approved', reason: 'production SMS was not approved', evidence: ['approval quote recorded'] },
];
result = run(structuredSideEffectKeyNeedsAffirmativeProof);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /approvalBoundaries requires prod-backend-write side effect prod-sms/);

const structuredSideEffectKeyRejectsContradictoryEvidence = state('he-verify');
structuredSideEffectKeyRejectsContradictoryEvidence.guardrails.push({
  ...g('e2e-side-effects', 'he-verify', 'npx playwright test e2e/checkout.spec.ts'),
  evidence: ['sent production SMS'],
});
structuredSideEffectKeyRejectsContradictoryEvidence.approvalBoundaries = [
  { id: 'prod-side-effect-approval', category: 'prod-backend-write', sideEffectKey: 'prod-sms', status: 'approved', reason: 'user approved exact production side effect', evidence: ['no production SMS sent'] },
];
result = run(structuredSideEffectKeyRejectsContradictoryEvidence);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /approvalBoundaries requires prod-backend-write side effect prod-sms/);

const unstructuredBoundaryRejectsContradictoryEvidence = state('he-verify');
unstructuredBoundaryRejectsContradictoryEvidence.guardrails.push({
  ...g('e2e-side-effects', 'he-verify', 'npx playwright test e2e/checkout.spec.ts'),
  evidence: ['sent production SMS'],
});
unstructuredBoundaryRejectsContradictoryEvidence.approvalBoundaries = [
  { id: 'prod-sms', category: 'prod-backend-write', status: 'approved', reason: 'user approved production SMS send', evidence: ['no production SMS sent'] },
];
result = run(unstructuredBoundaryRejectsContradictoryEvidence);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /approvalBoundaries requires prod-backend-write side effect prod-sms/);

const laterApprovedBoundarySatisfiesRequirement = state('he-verify');
laterApprovedBoundarySatisfiesRequirement.guardrails.push({
  ...g('e2e-side-effects', 'he-verify', 'npx playwright test e2e/checkout.spec.ts'),
  evidence: ['sent production SMS'],
});
laterApprovedBoundarySatisfiesRequirement.approvalBoundaries = [
  { id: 'old-prod-sms', category: 'prod-backend-write', status: 'blocked', reason: 'user approved production SMS send', evidence: ['approval quote recorded'] },
  { id: 'new-prod-sms', category: 'prod-backend-write', status: 'approved', reason: 'user approved production SMS send', evidence: ['approval quote recorded'] },
];
result = run(laterApprovedBoundarySatisfiesRequirement);
assert.equal(result.status, 0, result.stderr);

const distinctBackendConfigSideEffectsNeedDistinctBoundaries = state('he-verify');
distinctBackendConfigSideEffectsNeedDistinctBoundaries.guardrails.push({
  ...g('e2e-backend-config', 'he-verify', 'npx playwright test e2e/admin.spec.ts'),
  evidence: ['changed Appwrite permissions in prod', 'modified production database schema'],
});
distinctBackendConfigSideEffectsNeedDistinctBoundaries.approvalBoundaries = [
  { id: 'prod-appwrite-permission', category: 'prod-backend-write', status: 'approved', reason: 'user approved exact Appwrite permission mutation', evidence: ['approval quote recorded'] },
];
result = run(distinctBackendConfigSideEffectsNeedDistinctBoundaries);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /approvalBoundaries requires prod-backend-write side effect prod-db-schema/);

const distinctBackendConfigSideEffectsApproved = state('he-verify');
distinctBackendConfigSideEffectsApproved.guardrails = distinctBackendConfigSideEffectsNeedDistinctBoundaries.guardrails;
distinctBackendConfigSideEffectsApproved.approvalBoundaries = [
  { id: 'prod-appwrite-permission', category: 'prod-backend-write', status: 'approved', reason: 'user approved exact Appwrite permission mutation', evidence: ['approval quote recorded'] },
  { id: 'prod-db-schema', category: 'prod-backend-write', status: 'approved', reason: 'user approved production database schema mutation', evidence: ['approval quote recorded'] },
];
result = run(distinctBackendConfigSideEffectsApproved);
assert.equal(result.status, 0, result.stderr);

const appwriteSchemaAndDbPermissionNeedDistinctBoundaries = state('he-verify');
appwriteSchemaAndDbPermissionNeedDistinctBoundaries.guardrails.push({
  ...g('e2e-backend-config', 'he-verify', 'npx playwright test e2e/admin.spec.ts'),
  evidence: ['changed Appwrite schema in prod', 'changed database permissions in prod'],
});
appwriteSchemaAndDbPermissionNeedDistinctBoundaries.approvalBoundaries = [
  { id: 'prod-backend-write', category: 'prod-backend-write', status: 'approved', reason: 'user approved production backend write', evidence: ['approval quote recorded'] },
];
result = run(appwriteSchemaAndDbPermissionNeedDistinctBoundaries);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /approvalBoundaries requires prod-backend-write side effect prod-appwrite-schema/);
assert.match(result.stderr, /approvalBoundaries requires prod-backend-write side effect prod-db-permission/);

const appwriteSchemaAndDbPermissionApproved = state('he-verify');
appwriteSchemaAndDbPermissionApproved.guardrails = appwriteSchemaAndDbPermissionNeedDistinctBoundaries.guardrails;
appwriteSchemaAndDbPermissionApproved.approvalBoundaries = [
  { id: 'prod-appwrite-schema', category: 'prod-backend-write', status: 'approved', reason: 'user approved production Appwrite schema mutation', evidence: ['approval quote recorded'] },
  { id: 'prod-db-permission', category: 'prod-backend-write', status: 'approved', reason: 'user approved production database permission mutation', evidence: ['approval quote recorded'] },
];
result = run(appwriteSchemaAndDbPermissionApproved);
assert.equal(result.status, 0, result.stderr);

const bareApprovalNounsDoNotApproveBoundary = state('he-verify');
bareApprovalNounsDoNotApproveBoundary.guardrails.push({
  ...g('e2e-backend-config', 'he-verify', 'npx playwright test e2e/admin.spec.ts'),
  evidence: ['changed Appwrite permissions in prod'],
});
bareApprovalNounsDoNotApproveBoundary.approvalBoundaries = [
  { id: 'prod-appwrite-permission', category: 'prod-backend-write', status: 'approved', reason: 'Appwrite permission changed in prod', evidence: ['approval and consent recorded'] },
];
result = run(bareApprovalNounsDoNotApproveBoundary);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /approvalBoundaries requires prod-backend-write side effect prod-appwrite-permission/);

const productionAccountBoundaryApproved = state('he-verify');
productionAccountBoundaryApproved.guardrails.push({
  ...g('prod-account-write', 'he-verify', 'node scripts/check-prod-account.mjs'),
  evidence: ['deleted production user'],
});
productionAccountBoundaryApproved.approvalBoundaries = [
  { id: 'prod-user-delete', category: 'prod-backend-write', status: 'approved', reason: 'user approved deleting production account', evidence: ['approval quote recorded'] },
];
result = run(productionAccountBoundaryApproved);
assert.equal(result.status, 0, result.stderr);

const productionUserAccessNeedsAccountBoundary = state('he-verify');
productionUserAccessNeedsAccountBoundary.guardrails.push({
  ...g('prod-account-write', 'he-verify', 'node scripts/check-prod-account.mjs'),
  evidence: ['revoked production user access'],
});
productionUserAccessNeedsAccountBoundary.approvalBoundaries = [
  { id: 'prod-db-permission', category: 'prod-backend-write', status: 'approved', reason: 'user approved exact Appwrite permission mutation', evidence: ['approval quote recorded'] },
];
result = run(productionUserAccessNeedsAccountBoundary);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /approvalBoundaries requires prod-backend-write side effect prod-user-account/);

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

for (const reason of [
  'production backend approval pending',
  'user approved design review',
]) {
  const configuredCategoryBoundaryNeedsAffirmativeProof = state('he-verify');
  configuredCategoryBoundaryNeedsAffirmativeProof.e2ePolicy = { requiredApprovalBoundaries: ['prod-backend-write'] };
  configuredCategoryBoundaryNeedsAffirmativeProof.approvalBoundaries = [
    { id: 'prod-approval', category: 'prod-backend-write', status: 'approved', reason, evidence: ['approval quote recorded'] },
  ];
  result = run(configuredCategoryBoundaryNeedsAffirmativeProof);
  assert.notEqual(result.status, 0, reason);
  assert.match(result.stderr, /approvalBoundaries requires prod-backend-write/);
}

const configuredCategoryBoundaryAllowsStructuredSideEffect = state('he-verify');
configuredCategoryBoundaryAllowsStructuredSideEffect.e2ePolicy = { requiredApprovalBoundaries: ['prod-backend-write'] };
configuredCategoryBoundaryAllowsStructuredSideEffect.approvalBoundaries = [
  { id: 'prod-side-effect-approval', category: 'prod-backend-write', sideEffectKey: 'prod-sms', status: 'approved', reason: 'user approved exact production side effect', evidence: ['approval quote recorded'] },
];
result = run(configuredCategoryBoundaryAllowsStructuredSideEffect);
assert.equal(result.status, 0, result.stderr);

const generatedCredentialEmptyProof = state('he-verify');
generatedCredentialEmptyProof.e2ePolicy = { requiredApprovalBoundaries: ['generated-credentials'] };
generatedCredentialEmptyProof.approvalBoundaries = [
  { id: 'generated-user', category: 'generated-credentials', status: 'approved', reason: 'user approved generated test user', evidence: [''], redactedCredentialRef: 'user: he-e2e-***@example.test', dataScope: 'seeded-test user only', cleanupProof: [''] },
];
result = run(generatedCredentialEmptyProof);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /approvalBoundaries\[0\]\.evidence must be non-empty string\[\]/);
assert.match(result.stderr, /approvalBoundaries\[0\]\.cleanupProof must be non-empty string\[\] for generated credentials/);

for (const cleanupProof of [
  'cleanup pending',
  'cleanup requested',
  'not deleted',
  'cleanup failed',
  'generated user not cleaned up',
]) {
  const generatedCredentialWeakCleanupProof = state('he-verify');
  generatedCredentialWeakCleanupProof.e2ePolicy = { requiredApprovalBoundaries: ['generated-credentials'] };
  generatedCredentialWeakCleanupProof.approvalBoundaries = [
    { id: 'generated-user', category: 'generated-credentials', status: 'approved', reason: 'user approved generated test user', evidence: ['created test user'], redactedCredentialRef: 'user: he-e2e-***@example.test', dataScope: 'seeded-test user only', cleanupProof: [cleanupProof] },
  ];
  result = run(generatedCredentialWeakCleanupProof);
  assert.notEqual(result.status, 0, cleanupProof);
  assert.match(result.stderr, /cleanupProof must include positive cleanup result/);
}

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

const repeatedMissEmptyEvidence = state('he-ship');
repeatedMissEmptyEvidence.repeatMisses = [
  { issueClass: 'auth', evidence: [''] },
];
result = run(repeatedMissEmptyEvidence);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /repeatMisses\[0\]\.evidence must be non-empty string\[\]/);

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

const repeatedMissClosedLearning = state('he-ship');
repeatedMissClosedLearning.repeatMisses = [
  { issueClass: 'auth', evidence: ['user caught auth owner miss'] },
  { issueClass: 'auth', evidence: ['user caught auth proof miss'] },
];
repeatedMissClosedLearning.findings = [{
  id: 'learn-auth-workflow',
  stage: 'he-implement',
  summary: 'auth repeated and needs durable guard',
  ownerStage: 'he-learn',
  repairType: 'learning',
  ownerProof: ['skills/he-implement/SKILL.md'],
  artifacts: [],
  status: 'fixed',
}];
result = run(repeatedMissClosedLearning);
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
