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

const partialSummarySsotOwnerReuse = state('he-implement');
partialSummarySsotOwnerReuse.subStages = partialSummarySsotOwnerReuse.subStages.map((item) => (
  item.id === 'ssot-owner-reuse' ? { ...item, evidence: ['SSOT reused: workflow-state owner'] } : item
));
result = run(partialSummarySsotOwnerReuse);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /missing: SSOT extended, new owners created/);

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

const structuredReceiptSsotOwnerReuse = state('he-implement');
structuredReceiptSsotOwnerReuse.subStages = structuredReceiptSsotOwnerReuse.subStages.map((item) => (
  item.id === 'ssot-owner-reuse' ? { id: item.id, title: item.title, status: item.status, evidence: ['owner reuse checked'], sequence: item.sequence } : item
));
structuredReceiptSsotOwnerReuse.steps = [{
  id: '1',
  title: 'Stage proof',
  status: 'done',
  receipt: {
    ...receipt('he-implement', '/he:verify'),
    ssotOwnerReuse: {
      ownerLedger: ssotOwnerLedger(),
      summary: 'SSOT reused: workflow-state owner; SSOT extended: none; new owners created: none',
    },
  },
}];
result = run(structuredReceiptSsotOwnerReuse);
assert.equal(result.status, 0, result.stderr);

const handoverPromptOnlySsotOwnerReuseSummary = state('he-implement');
handoverPromptOnlySsotOwnerReuseSummary.subStages = handoverPromptOnlySsotOwnerReuseSummary.subStages.map((item) => (
  item.id === 'ssot-owner-reuse' ? { id: item.id, title: item.title, status: item.status, evidence: ['owner reuse checked'], ownerLedger: ssotOwnerLedger(), sequence: item.sequence } : item
));
{
  const baseReceipt = receipt('he-implement', '/he:verify');
  handoverPromptOnlySsotOwnerReuseSummary.steps = [{
    id: '1',
    title: 'Stage proof',
    status: 'done',
    receipt: {
      ...baseReceipt,
      ownerProof: ['owner proof only'],
      ssotOwnerReuse: { ownerLedger: ssotOwnerLedger() },
      handoverPrompt: `${baseReceipt.handoverPrompt} SSOT reused; SSOT extended; new owners created.`,
    },
  }];
}
result = run(handoverPromptOnlySsotOwnerReuseSummary);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /missing: SSOT reused, SSOT extended, new owners created/);

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

const emptyReferencedRequiredGuardrailEvidence = state('he-implement');
emptyReferencedRequiredGuardrailEvidence.guardrails.push({
  ...g('regex-scan', 'he-implement', 'rg owner .'),
  evidence: [''],
});
emptyReferencedRequiredGuardrailEvidence.guardrailInventory.requiredGuardrails[0] = {
  id: 'regex-scanners',
  status: 'required',
  guardrailId: 'regex-scan',
  evidence: ['regex scan required'],
};
result = run(emptyReferencedRequiredGuardrailEvidence);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /regex-scanners requires guardrails\[\] entry regex-scan evidence to be non-empty string\[\]/);

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

const uiComponentWithNotApplicableReasonAndOwnerProof = state('he-implement');
withSsotOwnerLedger(uiComponentWithNotApplicableReasonAndOwnerProof, [{
  ownerClass: 'ui-component',
  decision: 'reuse',
  owner: 'skills/he-implement/references/ssot-owner-reuse.md',
  evidence: ['ui component owner ledger reviewed'],
}]);
uiComponentWithNotApplicableReasonAndOwnerProof.guardrailInventory = {
  ...guardrailInventory({
    'ssot-scanners': {
      id: 'ssot-scanners',
      status: 'not_applicable',
      reason: 'SSOT scanner not applicable',
      evidence: ['component-pattern search run; owner ledger recorded'],
    },
  }),
  touchedStacks: ['ui', 'component'],
};
result = run(uiComponentWithNotApplicableReasonAndOwnerProof);
assert.equal(result.status, 0, result.stderr);

for (const evidence of [
  'no owner ledger recorded',
  'component-pattern search not run',
  'component-pattern search not applicable',
  'owner ledger not recorded',
  'component-pattern never searched',
  'owner ledger never recorded',
  'component-pattern search failed; owner ledger recorded',
  'component-pattern search error; owner ledger recorded',
  'component-pattern search errored; owner ledger recorded',
  'component-pattern search returned code 1; owner ledger recorded',
]) {
  const uiComponentWithNegatedNotApplicableSsotEvidence = state('he-implement');
  withSsotOwnerLedger(uiComponentWithNegatedNotApplicableSsotEvidence, [{
    ownerClass: 'ui-component',
    decision: 'reuse',
    owner: 'skills/he-implement/references/ssot-owner-reuse.md',
    evidence: ['ui component owner ledger reviewed'],
  }]);
  uiComponentWithNegatedNotApplicableSsotEvidence.guardrailInventory = {
    ...guardrailInventory({
      'ssot-scanners': {
        id: 'ssot-scanners',
        status: 'not_applicable',
        reason: 'SSOT scanner not applicable',
        evidence: [evidence],
      },
    }),
    touchedStacks: ['ui', 'component'],
  };
  result = run(uiComponentWithNegatedNotApplicableSsotEvidence);
  assert.notEqual(result.status, 0, evidence);
  assert.match(result.stderr, /ssot-scanners cannot be not_applicable/);
}

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

const uiComponentWithStatus200SsotScanner = state('he-implement');
withSsotOwnerLedger(uiComponentWithStatus200SsotScanner, [{
  ownerClass: 'ui-component',
  decision: 'reuse',
  owner: 'skills/he-implement/references/ssot-owner-reuse.md',
  evidence: ['ui component owner ledger reviewed'],
}]);
uiComponentWithStatus200SsotScanner.guardrails.push({
  ...g('ssot-scan', 'he-implement', 'node scripts/check-ssot-guardrails.mjs .'),
  evidence: ['SSOT report returned status 200; SSOT report code 200; SSOT scanner passed; owner ledger recorded'],
});
uiComponentWithStatus200SsotScanner.guardrailInventory = {
  ...guardrailInventory({
    'ssot-scanners': { id: 'ssot-scanners', status: 'required', guardrailId: 'ssot-scan', evidence: ['UI component owner changed'] },
  }),
  touchedStacks: ['ui', 'component'],
};
result = run(uiComponentWithStatus200SsotScanner);
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

const uiComponentWithNegativeRequiredSsotScannerEvidence = state('he-implement');
withSsotOwnerLedger(uiComponentWithNegativeRequiredSsotScannerEvidence, [{
  ownerClass: 'ui-component',
  decision: 'reuse',
  owner: 'skills/he-implement/references/ssot-owner-reuse.md',
  evidence: ['ui component owner ledger reviewed'],
}]);
uiComponentWithNegativeRequiredSsotScannerEvidence.guardrails.push({
  ...g('ssot-scan', 'he-implement', 'node scripts/check-ssot-guardrails.mjs .'),
  evidence: ['SSOT scanner unavailable; no SSOT scanner proof recorded'],
});
uiComponentWithNegativeRequiredSsotScannerEvidence.guardrailInventory = {
  ...guardrailInventory({
    'ssot-scanners': { id: 'ssot-scanners', status: 'required', guardrailId: 'ssot-scan', evidence: ['UI component owner changed'] },
  }),
  touchedStacks: ['ui', 'component'],
};
result = run(uiComponentWithNegativeRequiredSsotScannerEvidence);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /ssot-scanners requires passed SSOT scanner evidence/);

const uiComponentWithFailedRequiredSsotScannerEvidence = state('he-implement');
withSsotOwnerLedger(uiComponentWithFailedRequiredSsotScannerEvidence, [{
  ownerClass: 'ui-component',
  decision: 'reuse',
  owner: 'skills/he-implement/references/ssot-owner-reuse.md',
  evidence: ['ui component owner ledger reviewed'],
}]);
uiComponentWithFailedRequiredSsotScannerEvidence.guardrails.push({
  ...g('ssot-scan', 'he-implement', 'node scripts/check-ssot-guardrails.mjs .'),
  evidence: ['SSOT scanner failed; owner ledger recorded'],
});
uiComponentWithFailedRequiredSsotScannerEvidence.guardrailInventory = {
  ...guardrailInventory({
    'ssot-scanners': { id: 'ssot-scanners', status: 'required', guardrailId: 'ssot-scan', evidence: ['UI component owner changed'] },
  }),
  touchedStacks: ['ui', 'component'],
};
result = run(uiComponentWithFailedRequiredSsotScannerEvidence);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /ssot-scanners requires passed SSOT scanner evidence/);

const uiComponentWithViolationRequiredSsotScannerEvidence = state('he-implement');
withSsotOwnerLedger(uiComponentWithViolationRequiredSsotScannerEvidence, [{
  ownerClass: 'ui-component',
  decision: 'reuse',
  owner: 'skills/he-implement/references/ssot-owner-reuse.md',
  evidence: ['ui component owner ledger reviewed'],
}]);
uiComponentWithViolationRequiredSsotScannerEvidence.guardrails.push({
  ...g('ssot-scan', 'he-implement', 'node scripts/check-ssot-guardrails.mjs .'),
  evidence: ['SSOT scanner reported violations; owner ledger recorded'],
});
uiComponentWithViolationRequiredSsotScannerEvidence.guardrailInventory = {
  ...guardrailInventory({
    'ssot-scanners': { id: 'ssot-scanners', status: 'required', guardrailId: 'ssot-scan', evidence: ['UI component owner changed'] },
  }),
  touchedStacks: ['ui', 'component'],
};
result = run(uiComponentWithViolationRequiredSsotScannerEvidence);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /ssot-scanners requires passed SSOT scanner evidence/);

for (const evidence of [
  'SSOT violations: 2; owner ledger recorded',
  'SSOT violation count: 2; owner ledger recorded',
  'SSOT issue count=1; owner ledger recorded',
  'SSOT findings=1; owner ledger recorded',
  '2 SSOT violations; owner ledger recorded',
  'violations: 2; owner ledger recorded',
  'finding count: 1; owner ledger recorded',
  'issue count=1; owner ledger recorded',
]) {
  const uiComponentWithNonZeroSsotViolationCount = state('he-implement');
  withSsotOwnerLedger(uiComponentWithNonZeroSsotViolationCount, [{
    ownerClass: 'ui-component',
    decision: 'reuse',
    owner: 'skills/he-implement/references/ssot-owner-reuse.md',
    evidence: ['ui component owner ledger reviewed'],
  }]);
  uiComponentWithNonZeroSsotViolationCount.guardrails.push({
    ...g('ssot-scan', 'he-implement', 'node scripts/check-ssot-guardrails.mjs .'),
    evidence: [evidence],
  });
  uiComponentWithNonZeroSsotViolationCount.guardrailInventory = {
    ...guardrailInventory({
      'ssot-scanners': { id: 'ssot-scanners', status: 'required', guardrailId: 'ssot-scan', evidence: ['UI component owner changed'] },
    }),
    touchedStacks: ['ui', 'component'],
  };
  result = run(uiComponentWithNonZeroSsotViolationCount);
  assert.notEqual(result.status, 0, evidence);
  assert.match(result.stderr, /ssot-scanners requires passed SSOT scanner evidence/);
}

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

const genericYamlDoesNotRequireSchemaGuardrails = state('he-implement');
genericYamlDoesNotRequireSchemaGuardrails.guardrailInventory = {
  ...guardrailInventory(),
  touchedStacks: ['.github/workflows/ci.yml'],
};
result = run(genericYamlDoesNotRequireSchemaGuardrails);
assert.equal(result.status, 0, result.stderr);

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

const pluralMigrationWithoutSsotEvidence = state('he-implement');
pluralMigrationWithoutSsotEvidence.guardrails.push({
  ...g('fallow-audit', 'he-implement', 'fallow audit --dupes --base origin/main'),
  evidence: ['rg static search found no clone groups for migration files'],
});
pluralMigrationWithoutSsotEvidence.guardrailInventory = {
  ...guardrailInventory({
    fallow: { id: 'fallow', status: 'required', guardrailId: 'fallow-audit', evidence: ['migration static search passed'] },
  }),
  touchedStacks: ['migrations/add_users'],
};
result = run(pluralMigrationWithoutSsotEvidence);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /ssot-scanners cannot be not_applicable/);

const pluralMigrationWithScannerButDefaultLedger = state('he-implement');
pluralMigrationWithScannerButDefaultLedger.guardrails.push(g('ssot-scan', 'he-implement', 'node scripts/check-ssot-guardrails.mjs .'));
pluralMigrationWithScannerButDefaultLedger.guardrails.push({
  ...g('fallow-audit', 'he-implement', 'fallow audit --dupes --base origin/main'),
  evidence: ['rg static search found no clone groups for migration files'],
});
pluralMigrationWithScannerButDefaultLedger.guardrailInventory = {
  ...guardrailInventory({
    fallow: { id: 'fallow', status: 'required', guardrailId: 'fallow-audit', evidence: ['migration static search passed'] },
    'ssot-scanners': { id: 'ssot-scanners', status: 'required', guardrailId: 'ssot-scan', evidence: ['migration schema owner checked'] },
  }),
  touchedStacks: ['migrations/add_users'],
};
result = run(pluralMigrationWithScannerButDefaultLedger);
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

const nodeBackendWithoutFallow = state('he-implement');
nodeBackendWithoutFallow.guardrailInventory = {
  ...guardrailInventory(),
  touchedStacks: ['node backend'],
};
result = run(nodeBackendWithoutFallow);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /fallow cannot be not_applicable/);

const nextjsAppWithoutRequiredGuards = state('he-implement');
nextjsAppWithoutRequiredGuards.guardrailInventory = {
  ...guardrailInventory(),
  touchedStacks: ['nextjs app'],
};
result = run(nextjsAppWithoutRequiredGuards);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /ssot-scanners cannot be not_applicable/);
assert.match(result.stderr, /fallow cannot be not_applicable/);
assert.match(result.stderr, /react-doctor cannot be not_applicable/);
assert.match(result.stderr, /lint-analyze-typecheck cannot be not_applicable/);

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

const nextjsAppWithRequiredProof = state('he-implement');
withSsotOwnerLedger(nextjsAppWithRequiredProof, [{
  ownerClass: 'ui screen',
  decision: 'reuse',
  owner: 'skills/he-implement/references/ssot-owner-reuse.md',
  evidence: ['NextJS app UI screen owner ledger reviewed'],
}]);
nextjsAppWithRequiredProof.guardrails.push({
  ...g('fallow-audit', 'he-implement', 'fallow audit --dupes --base origin/main'),
  evidence: ['Fallow found no clone groups for NextJS app'],
});
nextjsAppWithRequiredProof.guardrails.push({
  ...g('react-doctor', 'he-implement', 'react-doctor --scope changed'),
  evidence: ['React Doctor passed'],
});
nextjsAppWithRequiredProof.guardrails.push({
  ...g('lint-typecheck', 'he-implement', 'npm run lint && npm run typecheck'),
  evidence: ['NextJS lint passed; NextJS typecheck passed'],
});
nextjsAppWithRequiredProof.guardrails.push({
  ...g('ssot-scan', 'he-implement', 'node scripts/check-ssot-guardrails.mjs .'),
  evidence: ['SSOT scanner passed; owner ledger recorded for NextJS app'],
});
nextjsAppWithRequiredProof.guardrailInventory = {
  ...guardrailInventory({
    fallow: { id: 'fallow', status: 'required', guardrailId: 'fallow-audit', evidence: ['Fallow NextJS duplicate proof recorded'] },
    'react-doctor': { id: 'react-doctor', status: 'required', guardrailId: 'react-doctor', evidence: ['React Doctor passed'] },
    'lint-analyze-typecheck': { id: 'lint-analyze-typecheck', status: 'required', guardrailId: 'lint-typecheck', evidence: ['NextJS lint and typecheck passed'] },
    'ssot-scanners': { id: 'ssot-scanners', status: 'required', guardrailId: 'ssot-scan', evidence: ['NextJS owner ledger checked'] },
  }),
  touchedStacks: ['nextjs app'],
};
result = run(nextjsAppWithRequiredProof);
assert.equal(result.status, 0, result.stderr);

const nodeBackendWithFallowScope = state('he-implement');
withSsotOwnerLedger(nodeBackendWithFallowScope, [{
  ownerClass: 'backend',
  decision: 'reuse',
  owner: 'skills/he-implement/references/ssot-owner-reuse.md',
  evidence: ['backend owner ledger reviewed'],
}]);
nodeBackendWithFallowScope.guardrails.push({
  ...g('fallow-audit', 'he-implement', 'fallow audit --dupes --base origin/main'),
  evidence: ['Fallow found no clone groups for Node backend'],
});
nodeBackendWithFallowScope.guardrails.push(g('ssot-scan', 'he-implement', 'node scripts/check-ssot-guardrails.mjs .'));
nodeBackendWithFallowScope.guardrailInventory = {
  ...guardrailInventory({
    fallow: { id: 'fallow', status: 'required', guardrailId: 'fallow-audit', evidence: ['Fallow Node duplicate proof recorded'] },
    'ssot-scanners': { id: 'ssot-scanners', status: 'required', guardrailId: 'ssot-scan', evidence: ['backend owner checked'] },
  }),
  touchedStacks: ['node backend'],
};
result = run(nodeBackendWithFallowScope);
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
  'React Doctor completed with exit code 1',
  'React Doctor completed with exit status 1',
  'React Doctor returned code 1',
  'React Doctor completed with code 1',
  'React Doctor exited 1',
  'React Doctor completed status 1',
  'React Doctor completed code=1',
  'React Doctor completed rc=1',
  'React Doctor completed returncode=1',
  'React Doctor completed exitcode=1',
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

const reactWithExitCodeFailedTypecheckProof = state('he-implement');
reactWithExitCodeFailedTypecheckProof.guardrails.push({
  ...g('fallow-audit', 'he-implement', 'fallow audit --dupes --base origin/main'),
  evidence: ['Fallow found no clone groups for React TypeScript files'],
});
reactWithExitCodeFailedTypecheckProof.guardrails.push(g('react-doctor', 'he-implement', 'react-doctor --scope changed'));
reactWithExitCodeFailedTypecheckProof.guardrails.push({
  ...g('lint-typecheck', 'he-implement', 'npm run lint && npm run typecheck'),
  evidence: ['React lint passed; TypeScript typecheck completed with exit code 1'],
});
reactWithExitCodeFailedTypecheckProof.guardrailInventory = {
  ...guardrailInventoryWithUiSsot(reactWithExitCodeFailedTypecheckProof, {
    fallow: { id: 'fallow', status: 'required', guardrailId: 'fallow-audit', evidence: ['Fallow found no clone groups for React TypeScript files'] },
    'react-doctor': { id: 'react-doctor', status: 'required', guardrailId: 'react-doctor', evidence: ['React files changed'] },
    'lint-analyze-typecheck': { id: 'lint-analyze-typecheck', status: 'required', guardrailId: 'lint-typecheck', evidence: ['React lint passed; TypeScript typecheck completed with exit code 1'] },
  }),
  touchedStacks: ['react', 'typescript'],
};
result = run(reactWithExitCodeFailedTypecheckProof);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /lint-analyze-typecheck requires lint\/analyze and typecheck evidence/);

const reactWithExitStatusFailedTypecheckProof = state('he-implement');
reactWithExitStatusFailedTypecheckProof.guardrails.push({
  ...g('fallow-audit', 'he-implement', 'fallow audit --dupes --base origin/main'),
  evidence: ['Fallow found no clone groups for React TypeScript files'],
});
reactWithExitStatusFailedTypecheckProof.guardrails.push(g('react-doctor', 'he-implement', 'react-doctor --scope changed'));
reactWithExitStatusFailedTypecheckProof.guardrails.push({
  ...g('lint-typecheck', 'he-implement', 'npm run lint && npm run typecheck'),
  evidence: ['React lint passed; TypeScript typecheck completed with exit status 1'],
});
reactWithExitStatusFailedTypecheckProof.guardrailInventory = {
  ...guardrailInventoryWithUiSsot(reactWithExitStatusFailedTypecheckProof, {
    fallow: { id: 'fallow', status: 'required', guardrailId: 'fallow-audit', evidence: ['Fallow found no clone groups for React TypeScript files'] },
    'react-doctor': { id: 'react-doctor', status: 'required', guardrailId: 'react-doctor', evidence: ['React files changed'] },
    'lint-analyze-typecheck': { id: 'lint-analyze-typecheck', status: 'required', guardrailId: 'lint-typecheck', evidence: ['React lint passed; TypeScript typecheck completed with exit status 1'] },
  }),
  touchedStacks: ['react', 'typescript'],
};
result = run(reactWithExitStatusFailedTypecheckProof);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /lint-analyze-typecheck requires lint\/analyze and typecheck evidence/);

for (const evidence of [
  'React lint passed; TypeScript typecheck returned code 1',
  'React lint passed; TypeScript typecheck completed with code 1',
  'React lint passed; TypeScript typecheck exited 1',
  'React lint passed; TypeScript typecheck completed status 1',
  'React lint passed; TypeScript typecheck completed code=1',
  'React lint passed; TypeScript typecheck completed rc=1',
  'React lint passed; TypeScript typecheck completed returncode=1',
  'React lint passed; TypeScript typecheck completed exitcode=1',
]) {
  const reactWithReturnCodeFailedTypecheckProof = state('he-implement');
  reactWithReturnCodeFailedTypecheckProof.guardrails.push({
    ...g('fallow-audit', 'he-implement', 'fallow audit --dupes --base origin/main'),
    evidence: ['Fallow found no clone groups for React TypeScript files'],
  });
  reactWithReturnCodeFailedTypecheckProof.guardrails.push(g('react-doctor', 'he-implement', 'react-doctor --scope changed'));
  reactWithReturnCodeFailedTypecheckProof.guardrails.push({
    ...g('lint-typecheck', 'he-implement', 'npm run lint && npm run typecheck'),
    evidence: [evidence],
  });
  reactWithReturnCodeFailedTypecheckProof.guardrailInventory = {
    ...guardrailInventoryWithUiSsot(reactWithReturnCodeFailedTypecheckProof, {
      fallow: { id: 'fallow', status: 'required', guardrailId: 'fallow-audit', evidence: ['Fallow found no clone groups for React TypeScript files'] },
      'react-doctor': { id: 'react-doctor', status: 'required', guardrailId: 'react-doctor', evidence: ['React files changed'] },
      'lint-analyze-typecheck': { id: 'lint-analyze-typecheck', status: 'required', guardrailId: 'lint-typecheck', evidence: [evidence] },
    }),
    touchedStacks: ['react', 'typescript'],
  };
  result = run(reactWithReturnCodeFailedTypecheckProof);
  assert.notEqual(result.status, 0, evidence);
  assert.match(result.stderr, /lint-analyze-typecheck requires lint\/analyze and typecheck evidence/);
}

for (const evidence of [
  'ESLint completed with non-zero exit; TypeScript typecheck passed',
  'ESLint completed with exit code 1; TypeScript typecheck passed',
  'ESLint completed with exit status 1; TypeScript typecheck passed',
  'ESLint returned code 1; TypeScript typecheck passed',
  'ESLint completed with code 1; TypeScript typecheck passed',
  'ESLint exited 1; TypeScript typecheck passed',
  'ESLint completed status 1; TypeScript typecheck passed',
  'ESLint completed code=1; TypeScript typecheck passed',
  'ESLint completed rc=1; TypeScript typecheck passed',
  'ESLint completed returncode=1; TypeScript typecheck passed',
  'ESLint completed exitcode=1; TypeScript typecheck passed',
]) {
  const reactWithFailedLintExitProof = state('he-implement');
  reactWithFailedLintExitProof.guardrails.push({
    ...g('fallow-audit', 'he-implement', 'fallow audit --dupes --base origin/main'),
    evidence: ['Fallow found no clone groups for React TypeScript files'],
  });
  reactWithFailedLintExitProof.guardrails.push(g('react-doctor', 'he-implement', 'react-doctor --scope changed'));
  reactWithFailedLintExitProof.guardrails.push({
    ...g('lint-typecheck', 'he-implement', 'npm run lint && npm run typecheck'),
    evidence: [evidence],
  });
  reactWithFailedLintExitProof.guardrailInventory = {
    ...guardrailInventoryWithUiSsot(reactWithFailedLintExitProof, {
      fallow: { id: 'fallow', status: 'required', guardrailId: 'fallow-audit', evidence: ['Fallow found no clone groups for React TypeScript files'] },
      'react-doctor': { id: 'react-doctor', status: 'required', guardrailId: 'react-doctor', evidence: ['React files changed'] },
      'lint-analyze-typecheck': { id: 'lint-analyze-typecheck', status: 'required', guardrailId: 'lint-typecheck', evidence: [evidence] },
    }),
    touchedStacks: ['react', 'typescript'],
  };
  result = run(reactWithFailedLintExitProof);
  assert.notEqual(result.status, 0, evidence);
  assert.match(result.stderr, /lint-analyze-typecheck requires lint\/analyze and typecheck evidence/);
}

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

const reactWithStatus200GuardrailProof = state('he-implement');
reactWithStatus200GuardrailProof.guardrails.push({
  ...g('fallow-audit', 'he-implement', 'fallow audit --dupes --base origin/main'),
  evidence: ['Fallow report returned status 200; Fallow report code 200; Fallow found no clone groups for React TypeScript files'],
});
reactWithStatus200GuardrailProof.guardrails.push({
  ...g('react-doctor', 'he-implement', 'react-doctor --scope changed'),
  evidence: ['React Doctor report returned status 200; React Doctor report code 200; React Doctor passed'],
});
reactWithStatus200GuardrailProof.guardrails.push({
  ...g('lint-typecheck', 'he-implement', 'npm run lint && npm run typecheck'),
  evidence: ['ESLint report returned status 200; ESLint report code 200; ESLint passed; TypeScript typecheck report returned status 200; TypeScript typecheck report code 200; TypeScript typecheck passed'],
});
reactWithStatus200GuardrailProof.guardrailInventory = {
  ...guardrailInventoryWithUiSsot(reactWithStatus200GuardrailProof, {
    fallow: { id: 'fallow', status: 'required', guardrailId: 'fallow-audit', evidence: ['Fallow React duplicate proof recorded'] },
    'react-doctor': { id: 'react-doctor', status: 'required', guardrailId: 'react-doctor', evidence: ['React Doctor passed'] },
    'lint-analyze-typecheck': { id: 'lint-analyze-typecheck', status: 'required', guardrailId: 'lint-typecheck', evidence: ['React lint and typecheck passed'] },
  }),
  touchedStacks: ['react', 'typescript'],
};
result = run(reactWithStatus200GuardrailProof);
assert.equal(result.status, 0, result.stderr);

for (const { reactDoctorEvidence, lintTypecheckEvidence } of [
  {
    reactDoctorEvidence: 'React Doctor report returned code 200; React Doctor passed',
    lintTypecheckEvidence: 'ESLint returned code 200; ESLint passed; TypeScript typecheck returned code 200; TypeScript typecheck passed',
  },
  {
    reactDoctorEvidence: 'React Doctor completed with code 200; React Doctor passed',
    lintTypecheckEvidence: 'ESLint completed with code 200; ESLint passed; TypeScript typecheck completed with code 200; TypeScript typecheck passed',
  },
]) {
  const reactWithCode200GuardrailProof = state('he-implement');
  reactWithCode200GuardrailProof.guardrails.push({
    ...g('fallow-audit', 'he-implement', 'fallow audit --dupes --base origin/main'),
    evidence: ['Fallow returned code 200; Fallow found no clone groups for React TypeScript files'],
  });
  reactWithCode200GuardrailProof.guardrails.push({
    ...g('react-doctor', 'he-implement', 'react-doctor --scope changed'),
    evidence: [reactDoctorEvidence],
  });
  reactWithCode200GuardrailProof.guardrails.push({
    ...g('lint-typecheck', 'he-implement', 'npm run lint && npm run typecheck'),
    evidence: [lintTypecheckEvidence],
  });
  reactWithCode200GuardrailProof.guardrailInventory = {
    ...guardrailInventoryWithUiSsot(reactWithCode200GuardrailProof, {
      fallow: { id: 'fallow', status: 'required', guardrailId: 'fallow-audit', evidence: ['Fallow React duplicate proof recorded'] },
      'react-doctor': { id: 'react-doctor', status: 'required', guardrailId: 'react-doctor', evidence: ['React Doctor passed'] },
      'lint-analyze-typecheck': { id: 'lint-analyze-typecheck', status: 'required', guardrailId: 'lint-typecheck', evidence: ['React lint and typecheck passed'] },
    }),
    touchedStacks: ['react', 'typescript'],
  };
  result = run(reactWithCode200GuardrailProof);
  assert.equal(result.status, 0, result.stderr);
}

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

const jsWithUnscopedCleanFallowResult = state('he-implement');
jsWithUnscopedCleanFallowResult.guardrails.push({
  ...g('fallow-audit', 'he-implement', 'fallow audit --dupes --base origin/main'),
  evidence: ['Fallow audit completed; found no clone groups for Python files'],
});
jsWithUnscopedCleanFallowResult.guardrailInventory = {
  ...guardrailInventory({
    fallow: { id: 'fallow', status: 'required', guardrailId: 'fallow-audit', evidence: ['Fallow audit completed'] },
  }),
  touchedStacks: ['scripts/foo.mjs'],
};
result = run(jsWithUnscopedCleanFallowResult);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /Fallow duplicate\/clone evidence/);

const jsWithSameSegmentOutOfScopeCleanFallowResult = state('he-implement');
jsWithSameSegmentOutOfScopeCleanFallowResult.guardrails.push({
  ...g('fallow-audit', 'he-implement', 'fallow audit --dupes --base origin/main'),
  evidence: ['Fallow found no clone groups for Python files'],
});
jsWithSameSegmentOutOfScopeCleanFallowResult.guardrailInventory = {
  ...guardrailInventory({
    fallow: { id: 'fallow', status: 'required', guardrailId: 'fallow-audit', evidence: ['Fallow Python duplicate proof recorded'] },
  }),
  touchedStacks: ['scripts/foo.mjs'],
};
result = run(jsWithSameSegmentOutOfScopeCleanFallowResult);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /Fallow duplicate\/clone evidence/);

const jsPathCleanProofRejectsGenericFallowScope = state('he-implement');
jsPathCleanProofRejectsGenericFallowScope.guardrails.push({
  ...g('fallow-audit', 'he-implement', 'fallow audit --dupes --base origin/main'),
  evidence: ['Fallow found no clone groups'],
});
jsPathCleanProofRejectsGenericFallowScope.guardrailInventory = {
  ...guardrailInventory({
    fallow: { id: 'fallow', status: 'required', guardrailId: 'fallow-audit', evidence: ['Fallow generic clean proof recorded'] },
  }),
  touchedStacks: ['scripts/foo.ts'],
};
result = run(jsPathCleanProofRejectsGenericFallowScope);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /Fallow duplicate\/clone evidence/);

const jsPathCleanProofRequiresTouchedPathScope = state('he-implement');
jsPathCleanProofRequiresTouchedPathScope.guardrails.push({
  ...g('fallow-audit', 'he-implement', 'fallow audit --dupes --base origin/main'),
  evidence: ['Fallow found no clone groups for scripts/bar.ts'],
});
jsPathCleanProofRequiresTouchedPathScope.guardrailInventory = {
  ...guardrailInventory({
    fallow: { id: 'fallow', status: 'required', guardrailId: 'fallow-audit', evidence: ['Fallow path duplicate proof recorded'] },
  }),
  touchedStacks: ['scripts/foo.ts'],
};
result = run(jsPathCleanProofRequiresTouchedPathScope);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /Fallow duplicate\/clone evidence/);

const jsPathCompletedOnlyFallowProof = state('he-implement');
jsPathCompletedOnlyFallowProof.guardrails.push({
  ...g('fallow-audit', 'he-implement', 'fallow audit --dupes --base origin/main'),
  evidence: ['Fallow duplicate groups checked and completed for scripts/foo.ts'],
});
jsPathCompletedOnlyFallowProof.guardrailInventory = jsPathCleanProofRequiresTouchedPathScope.guardrailInventory;
result = run(jsPathCompletedOnlyFallowProof);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /Fallow duplicate\/clone evidence/);

const jsPathCleanProofWithTouchedPathScope = state('he-implement');
jsPathCleanProofWithTouchedPathScope.guardrails.push({
  ...g('fallow-audit', 'he-implement', 'fallow audit --dupes --base origin/main'),
  evidence: ['Fallow found no clone groups for scripts/foo.ts'],
});
jsPathCleanProofWithTouchedPathScope.guardrailInventory = jsPathCleanProofRequiresTouchedPathScope.guardrailInventory;
result = run(jsPathCleanProofWithTouchedPathScope);
assert.equal(result.status, 0, result.stderr);

for (const evidence of [
  'Fallow found no clone groups for src/foo.js',
  'Fallow found no clone groups for JS files',
]) {
  const jsPathCleanProofWithJavaScriptScope = state('he-implement');
  jsPathCleanProofWithJavaScriptScope.guardrails.push({
    ...g('fallow-audit', 'he-implement', 'fallow audit --dupes --base origin/main'),
    evidence: [evidence],
  });
  jsPathCleanProofWithJavaScriptScope.guardrailInventory = {
    ...guardrailInventory({
      fallow: { id: 'fallow', status: 'required', guardrailId: 'fallow-audit', evidence: ['Fallow JavaScript duplicate proof recorded'] },
    }),
    touchedStacks: ['src/foo.js'],
  };
  result = run(jsPathCleanProofWithJavaScriptScope);
  assert.equal(result.status, 0, evidence);
}

for (const { evidence, touchedStack } of [
  { evidence: 'Fallow found no clone groups for JS files', touchedStack: 'scripts/foo.ts' },
  { evidence: 'Fallow found no clone groups for TS files', touchedStack: 'scripts/foo.js' },
]) {
  const jsTsPathCleanProofRejectsCrossLanguageScope = state('he-implement');
  jsTsPathCleanProofRejectsCrossLanguageScope.guardrails.push({
    ...g('fallow-audit', 'he-implement', 'fallow audit --dupes --base origin/main'),
    evidence: [evidence],
  });
  jsTsPathCleanProofRejectsCrossLanguageScope.guardrailInventory = {
    ...guardrailInventory({
      fallow: { id: 'fallow', status: 'required', guardrailId: 'fallow-audit', evidence: ['Fallow language-scope duplicate proof recorded'] },
    }),
    touchedStacks: [touchedStack],
  };
  result = run(jsTsPathCleanProofRejectsCrossLanguageScope);
  assert.notEqual(result.status, 0, `${evidence} for ${touchedStack}`);
  assert.match(result.stderr, /Fallow duplicate\/clone evidence/);
}

for (const touchedStack of ['scripts/foo.ts', 'scripts/foo.js']) {
  const jsTsPathCleanProofAcceptsCombinedScope = state('he-implement');
  jsTsPathCleanProofAcceptsCombinedScope.guardrails.push({
    ...g('fallow-audit', 'he-implement', 'fallow audit --dupes --base origin/main'),
    evidence: ['Fallow found no clone groups for JavaScript and TypeScript files'],
  });
  jsTsPathCleanProofAcceptsCombinedScope.guardrailInventory = {
    ...guardrailInventory({
      fallow: { id: 'fallow', status: 'required', guardrailId: 'fallow-audit', evidence: ['Fallow combined JS/TS duplicate proof recorded'] },
    }),
    touchedStacks: [touchedStack],
  };
  result = run(jsTsPathCleanProofAcceptsCombinedScope);
  assert.equal(result.status, 0, `${touchedStack}: ${result.stderr}`);
}

for (const modulePath of ['scripts/foo.mjs', 'scripts/foo.cjs', 'scripts/foo.mts', 'scripts/foo.cts']) {
  const jsModulePathCleanProofWithTouchedPathScope = state('he-implement');
  jsModulePathCleanProofWithTouchedPathScope.guardrails.push({
    ...g('fallow-audit', 'he-implement', 'fallow audit --dupes --base origin/main'),
    evidence: [`Fallow found no clone groups for ${modulePath}`],
  });
  jsModulePathCleanProofWithTouchedPathScope.guardrailInventory = {
    ...guardrailInventory({
      fallow: { id: 'fallow', status: 'required', guardrailId: 'fallow-audit', evidence: ['Fallow module path duplicate proof recorded'] },
    }),
    touchedStacks: [modulePath],
  };
  result = run(jsModulePathCleanProofWithTouchedPathScope);
  assert.equal(result.status, 0, modulePath);
}

const broadReactStackRejectsGenericFallowCleanProof = state('he-implement');
withSsotOwnerLedger(broadReactStackRejectsGenericFallowCleanProof, [{
  ownerClass: 'ui-component',
  decision: 'reuse',
  owner: 'skills/he-implement/references/ssot-owner-reuse.md',
  evidence: ['React UI owner ledger reviewed'],
}]);
broadReactStackRejectsGenericFallowCleanProof.guardrails.push({
  ...g('fallow-audit', 'he-implement', 'fallow audit --dupes --base origin/main'),
  evidence: ['Fallow found no clone groups'],
});
broadReactStackRejectsGenericFallowCleanProof.guardrails.push({
  ...g('react-doctor', 'he-implement', 'react-doctor --scope changed'),
  evidence: ['React Doctor passed'],
});
broadReactStackRejectsGenericFallowCleanProof.guardrails.push({
  ...g('lint-typecheck', 'he-implement', 'npm run lint && npm run typecheck'),
  evidence: ['ESLint passed; TypeScript typecheck passed'],
});
broadReactStackRejectsGenericFallowCleanProof.guardrailInventory = {
  ...guardrailInventoryWithUiSsot(broadReactStackRejectsGenericFallowCleanProof, {
    fallow: { id: 'fallow', status: 'required', guardrailId: 'fallow-audit', evidence: ['Fallow generic clean proof recorded'] },
    'react-doctor': { id: 'react-doctor', status: 'required', guardrailId: 'react-doctor', evidence: ['React Doctor passed'] },
    'lint-analyze-typecheck': { id: 'lint-analyze-typecheck', status: 'required', guardrailId: 'lint-typecheck', evidence: ['React lint and typecheck passed'] },
  }),
  touchedStacks: ['react'],
};
result = run(broadReactStackRejectsGenericFallowCleanProof);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /Fallow duplicate\/clone evidence/);

const broadReactStackAcceptsWholeScopeFallowCleanProof = state('he-implement');
withSsotOwnerLedger(broadReactStackAcceptsWholeScopeFallowCleanProof, [{
  ownerClass: 'ui-component',
  decision: 'reuse',
  owner: 'skills/he-implement/references/ssot-owner-reuse.md',
  evidence: ['React UI owner ledger reviewed'],
}]);
broadReactStackAcceptsWholeScopeFallowCleanProof.guardrails = broadReactStackRejectsGenericFallowCleanProof.guardrails.map((guardrail) => (
  guardrail.id === 'fallow-audit'
    ? { ...guardrail, evidence: ['Fallow found no clone groups for React TypeScript files'] }
    : guardrail
));
broadReactStackAcceptsWholeScopeFallowCleanProof.guardrailInventory = broadReactStackRejectsGenericFallowCleanProof.guardrailInventory;
result = run(broadReactStackAcceptsWholeScopeFallowCleanProof);
assert.equal(result.status, 0, result.stderr);

const jsWithOutOfScopeFoundCloneAfterCleanResult = state('he-implement');
jsWithOutOfScopeFoundCloneAfterCleanResult.guardrails.push({
  ...g('fallow-audit', 'he-implement', 'fallow audit --dupes --base origin/main'),
  evidence: ['Fallow found no clone groups for TypeScript files. Found Python clone groups'],
});
jsWithOutOfScopeFoundCloneAfterCleanResult.guardrailInventory = {
  ...guardrailInventory({
    fallow: { id: 'fallow', status: 'required', guardrailId: 'fallow-audit', evidence: ['Fallow TypeScript duplicate proof recorded'] },
  }),
  touchedStacks: ['scripts/foo.ts'],
};
result = run(jsWithOutOfScopeFoundCloneAfterCleanResult);
assert.equal(result.status, 0, result.stderr);

const jsWithFailedCleanFallowResult = state('he-implement');
jsWithFailedCleanFallowResult.guardrails.push({
  ...g('fallow-audit', 'he-implement', 'fallow audit --dupes --base origin/main'),
  evidence: ['Fallow failed; found no clone groups for React TypeScript files'],
});
jsWithFailedCleanFallowResult.guardrailInventory = {
  ...guardrailInventory({
    fallow: { id: 'fallow', status: 'required', guardrailId: 'fallow-audit', evidence: ['Fallow failed'] },
  }),
  touchedStacks: ['scripts/foo.mjs'],
};
result = run(jsWithFailedCleanFallowResult);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /Fallow duplicate\/clone evidence/);

for (const evidence of [
  'Fallow returned code 1; found no clone groups for React TypeScript files',
  'Fallow completed with code 1; found no clone groups for React TypeScript files',
  'Fallow exited 1; found no clone groups for React TypeScript files',
  'Fallow completed status 1; found no clone groups for React TypeScript files',
  'Fallow completed code=1; found no clone groups for React TypeScript files',
  'Fallow completed rc=1; found no clone groups for React TypeScript files',
  'Fallow completed returncode=1; found no clone groups for React TypeScript files',
  'Fallow completed exitcode=1; found no clone groups for React TypeScript files',
]) {
  const jsWithReturnCodeFailedCleanFallowResult = state('he-implement');
  jsWithReturnCodeFailedCleanFallowResult.guardrails.push({
    ...g('fallow-audit', 'he-implement', 'fallow audit --dupes --base origin/main'),
    evidence: [evidence],
  });
  jsWithReturnCodeFailedCleanFallowResult.guardrailInventory = {
    ...guardrailInventory({
      fallow: { id: 'fallow', status: 'required', guardrailId: 'fallow-audit', evidence: ['Fallow return-code failure recorded'] },
    }),
    touchedStacks: ['scripts/foo.mjs'],
  };
  result = run(jsWithReturnCodeFailedCleanFallowResult);
  assert.notEqual(result.status, 0, evidence);
  assert.match(result.stderr, /Fallow duplicate\/clone evidence/);
}

for (const evidence of [
  'Fallow duplicate result: none for JavaScript files',
  'Fallow clone output: not found for React JavaScript and TypeScript files',
]) {
  const jsWithCleanZeroResultFallow = state('he-implement');
  jsWithCleanZeroResultFallow.guardrails.push({
    ...g('fallow-audit', 'he-implement', 'fallow audit --dupes --base origin/main'),
    evidence: [evidence],
  });
  jsWithCleanZeroResultFallow.guardrailInventory = {
    ...guardrailInventory({
      fallow: { id: 'fallow', status: 'required', guardrailId: 'fallow-audit', evidence: ['Fallow zero-result duplicate proof recorded'] },
    }),
    touchedStacks: ['scripts/foo.mjs'],
  };
  result = run(jsWithCleanZeroResultFallow);
  assert.equal(result.status, 0, evidence);
}

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

for (const evidence of [
  'Fallow found no clone groups for React TypeScript files; clone groups present',
  'Fallow found no clone groups for React TypeScript files; duplicates exist',
]) {
  const jsWithPresentCloneFallow = state('he-implement');
  jsWithPresentCloneFallow.guardrails.push({
    ...g('fallow-audit', 'he-implement', 'fallow audit --dupes --base origin/main'),
    evidence: [evidence],
  });
  jsWithPresentCloneFallow.guardrailInventory = {
    ...guardrailInventory({
      fallow: { id: 'fallow', status: 'required', guardrailId: 'fallow-audit', evidence: [evidence] },
    }),
    touchedStacks: ['scripts/foo.mjs'],
  };
  result = run(jsWithPresentCloneFallow);
  assert.notEqual(result.status, 0, evidence);
  assert.match(result.stderr, /Fallow duplicate\/clone evidence/);
}

const jsWithUnrelatedFoundCloneDecision = state('he-implement');
jsWithUnrelatedFoundCloneDecision.decisions = [{
  id: 'python-clone-owner-decision',
  status: 'accepted',
  summary: 'SSOT owner decision recorded for Python clone groups',
  evidence: ['owner ledger resolved Python duplicate clone groups'],
}];
jsWithUnrelatedFoundCloneDecision.guardrails.push({
  ...g('fallow-audit', 'he-implement', 'fallow audit --dupes --base origin/main'),
  evidence: ['Fallow found clone groups'],
});
jsWithUnrelatedFoundCloneDecision.guardrailInventory = {
  ...guardrailInventory({
    fallow: { id: 'fallow', status: 'required', guardrailId: 'fallow-audit', evidence: ['Fallow found clone groups'] },
  }),
  touchedStacks: ['scripts/foo.mjs'],
};
result = run(jsWithUnrelatedFoundCloneDecision);
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
  evidence: ['owner ledger resolved JavaScript duplicate clone groups'],
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

function mixedJsTsFallowState(fallowEvidence, decisions = []) {
  const testState = state('he-implement');
  testState.decisions = decisions;
  testState.guardrails.push({
    ...g('fallow-audit', 'he-implement', 'fallow audit --dupes --base origin/main'),
    evidence: Array.isArray(fallowEvidence) ? fallowEvidence : [fallowEvidence],
  });
  testState.guardrailInventory = {
    ...guardrailInventory({
      fallow: { id: 'fallow', status: 'required', guardrailId: 'fallow-audit', evidence: ['Fallow JS/TS duplicate proof recorded'] },
    }),
    touchedStacks: ['javascript', 'typescript'],
  };
  return testState;
}

for (const { name, fallowEvidence, decisions } of [
  {
    name: 'JavaScript found clone decision does not satisfy TypeScript',
    fallowEvidence: 'Fallow found clone groups for JavaScript files',
    decisions: [{
      id: 'js-clone-owner-decision',
      status: 'accepted',
      summary: 'SSOT owner decision recorded for JavaScript clone groups',
      evidence: ['owner ledger resolved JavaScript duplicate clone groups'],
    }],
  },
  {
    name: 'TypeScript found clone decision does not satisfy JavaScript',
    fallowEvidence: 'Fallow found clone groups for TypeScript files',
    decisions: [{
      id: 'ts-clone-owner-decision',
      status: 'accepted',
      summary: 'SSOT owner decision recorded for TypeScript clone groups',
      evidence: ['owner ledger resolved TypeScript duplicate clone groups'],
    }],
  },
]) {
  result = run(mixedJsTsFallowState(fallowEvidence, decisions));
  assert.notEqual(result.status, 0, name);
  assert.match(result.stderr, /Fallow duplicate\/clone evidence/);
}

const mixedJsTsFallowPerScopeProof = mixedJsTsFallowState([
  'Fallow found clone groups for JavaScript files',
  'Fallow found no clone groups for TypeScript files',
], [{
  id: 'js-clone-owner-decision',
  status: 'accepted',
  summary: 'SSOT owner decision recorded for JavaScript clone groups',
  evidence: ['owner ledger resolved JavaScript duplicate clone groups'],
}]);
result = run(mixedJsTsFallowPerScopeProof);
assert.equal(result.status, 0, result.stderr);

const mixedJsTsFallowCombinedCleanProof = mixedJsTsFallowState(
  'Fallow found no clone groups for JavaScript and TypeScript files',
);
result = run(mixedJsTsFallowCombinedCleanProof);
assert.equal(result.status, 0, result.stderr);

for (const { evidence, decisionEvidence } of [
  {
    evidence: 'Fallow found clone groups for Node backend',
    decisionEvidence: 'owner ledger resolved Node duplicate clone groups',
  },
  {
    evidence: 'Fallow found clone groups in scripts/foo.mjs',
    decisionEvidence: 'owner ledger resolved scripts/foo.mjs duplicate clone groups',
  },
]) {
  const reactStackWithScopedJsCloneDecision = state('he-implement');
  reactStackWithScopedJsCloneDecision.decisions = [{
    id: 'scoped-js-clone-owner-decision',
    status: 'accepted',
    summary: 'SSOT owner decision recorded for scoped JavaScript clone groups',
    evidence: [decisionEvidence],
  }];
  reactStackWithScopedJsCloneDecision.guardrails.push({
    ...g('fallow-audit', 'he-implement', 'fallow audit --dupes --base origin/main'),
    evidence: [evidence],
  });
  reactStackWithScopedJsCloneDecision.guardrails.push(g('react-doctor', 'he-implement', 'react-doctor --scope changed'));
  reactStackWithScopedJsCloneDecision.guardrails.push({
    ...g('lint-typecheck', 'he-implement', 'npm run lint && npm run typecheck'),
    evidence: ['React lint passed; TypeScript typecheck passed'],
  });
  reactStackWithScopedJsCloneDecision.guardrailInventory = {
    ...guardrailInventoryWithUiSsot(reactStackWithScopedJsCloneDecision, {
      fallow: { id: 'fallow', status: 'required', guardrailId: 'fallow-audit', evidence: [evidence] },
      'react-doctor': { id: 'react-doctor', status: 'required', guardrailId: 'react-doctor', evidence: ['React files changed'] },
      'lint-analyze-typecheck': { id: 'lint-analyze-typecheck', status: 'required', guardrailId: 'lint-typecheck', evidence: ['React lint and typecheck passed'] },
    }),
    touchedStacks: ['react', 'typescript'],
  };
  result = run(reactStackWithScopedJsCloneDecision);
  assert.notEqual(result.status, 0, evidence);
  assert.match(result.stderr, /Fallow duplicate\/clone evidence/);
}

const jsPathCloneNeedsSamePathDecision = state('he-implement');
jsPathCloneNeedsSamePathDecision.decisions = [{
  id: 'card-clone-owner-decision',
  status: 'accepted',
  summary: 'SSOT owner decision recorded for TypeScript clone groups',
  evidence: ['owner ledger resolved TypeScript clone groups in src/Card.tsx'],
}];
jsPathCloneNeedsSamePathDecision.guardrails.push({
  ...g('fallow-audit', 'he-implement', 'fallow audit --dupes --base origin/main'),
  evidence: ['Fallow found clone groups in TypeScript src/Button.tsx'],
});
jsPathCloneNeedsSamePathDecision.guardrails.push(g('react-doctor', 'he-implement', 'react-doctor --scope changed'));
jsPathCloneNeedsSamePathDecision.guardrails.push({
  ...g('lint-typecheck', 'he-implement', 'npm run lint && npm run typecheck'),
  evidence: ['React lint passed; TypeScript typecheck passed'],
});
jsPathCloneNeedsSamePathDecision.guardrailInventory = {
  ...guardrailInventoryWithUiSsot(jsPathCloneNeedsSamePathDecision, {
    fallow: { id: 'fallow', status: 'required', guardrailId: 'fallow-audit', evidence: ['Fallow found clone groups in TypeScript src/Button.tsx'] },
    'react-doctor': { id: 'react-doctor', status: 'required', guardrailId: 'react-doctor', evidence: ['React files changed'] },
    'lint-analyze-typecheck': { id: 'lint-analyze-typecheck', status: 'required', guardrailId: 'lint-typecheck', evidence: ['React lint and typecheck passed'] },
  }),
  touchedStacks: ['react', 'typescript'],
};
result = run(jsPathCloneNeedsSamePathDecision);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /Fallow duplicate\/clone evidence/);

const jsPathCloneWithSamePathDecision = state('he-implement');
jsPathCloneWithSamePathDecision.decisions = [{
  id: 'button-clone-owner-decision',
  status: 'accepted',
  summary: 'SSOT owner decision recorded for TypeScript clone groups',
  evidence: ['owner ledger resolved TypeScript clone groups in src/Button.tsx'],
}];
jsPathCloneWithSamePathDecision.guardrails = jsPathCloneNeedsSamePathDecision.guardrails;
jsPathCloneWithSamePathDecision.guardrailInventory = {
  ...guardrailInventoryWithUiSsot(jsPathCloneWithSamePathDecision, {
    fallow: { id: 'fallow', status: 'required', guardrailId: 'fallow-audit', evidence: ['Fallow found clone groups in TypeScript src/Button.tsx'] },
    'react-doctor': { id: 'react-doctor', status: 'required', guardrailId: 'react-doctor', evidence: ['React files changed'] },
    'lint-analyze-typecheck': { id: 'lint-analyze-typecheck', status: 'required', guardrailId: 'lint-typecheck', evidence: ['React lint and typecheck passed'] },
  }),
  touchedStacks: ['react', 'typescript'],
};
result = run(jsPathCloneWithSamePathDecision);
assert.equal(result.status, 0, result.stderr);

const jsGenericPathCloneNeedsExactPathDecision = state('he-implement');
jsGenericPathCloneNeedsExactPathDecision.decisions = [{
  id: 'broad-typescript-clone-owner-decision',
  status: 'accepted',
  summary: 'SSOT owner decision recorded for TypeScript clone groups',
  evidence: ['owner ledger resolved TypeScript duplicate clone groups'],
}];
jsGenericPathCloneNeedsExactPathDecision.guardrails.push({
  ...g('fallow-audit', 'he-implement', 'fallow audit --dupes --base origin/main'),
  evidence: ['Fallow found clone groups in TypeScript src/index.tsx'],
});
jsGenericPathCloneNeedsExactPathDecision.guardrailInventory = {
  ...guardrailInventory({
    fallow: { id: 'fallow', status: 'required', guardrailId: 'fallow-audit', evidence: ['Fallow found clone groups in TypeScript src/index.tsx'] },
  }),
  touchedStacks: ['typescript'],
};
result = run(jsGenericPathCloneNeedsExactPathDecision);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /Fallow duplicate\/clone evidence/);

const jsGenericPathCloneWithExactPathDecision = state('he-implement');
jsGenericPathCloneWithExactPathDecision.decisions = [{
  id: 'index-clone-owner-decision',
  status: 'accepted',
  summary: 'SSOT owner decision recorded for TypeScript clone groups',
  evidence: ['owner ledger resolved TypeScript clone groups in src/index.tsx'],
}];
jsGenericPathCloneWithExactPathDecision.guardrails = jsGenericPathCloneNeedsExactPathDecision.guardrails;
jsGenericPathCloneWithExactPathDecision.guardrailInventory = jsGenericPathCloneNeedsExactPathDecision.guardrailInventory;
result = run(jsGenericPathCloneWithExactPathDecision);
assert.equal(result.status, 0, result.stderr);

const jsSymbolCloneNeedsSameSymbolDecision = state('he-implement');
jsSymbolCloneNeedsSameSymbolDecision.decisions = [{
  id: 'broad-typescript-clone-owner-decision',
  status: 'accepted',
  summary: 'SSOT owner decision recorded for TypeScript clone groups',
  evidence: ['owner ledger resolved TypeScript duplicate clone groups'],
}];
jsSymbolCloneNeedsSameSymbolDecision.guardrails.push({
  ...g('fallow-audit', 'he-implement', 'fallow audit --dupes --base origin/main'),
  evidence: ['Fallow found clone groups in Button component'],
});
jsSymbolCloneNeedsSameSymbolDecision.guardrailInventory = {
  ...guardrailInventory({
    fallow: { id: 'fallow', status: 'required', guardrailId: 'fallow-audit', evidence: ['Fallow found clone groups in Button component'] },
  }),
  touchedStacks: ['typescript'],
};
result = run(jsSymbolCloneNeedsSameSymbolDecision);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /Fallow duplicate\/clone evidence/);

const jsSymbolCloneWithSameSymbolDecision = state('he-implement');
jsSymbolCloneWithSameSymbolDecision.decisions = [{
  id: 'button-clone-owner-decision',
  status: 'accepted',
  summary: 'SSOT owner decision recorded for TypeScript clone groups',
  evidence: ['owner ledger resolved TypeScript clone groups in Button component'],
}];
jsSymbolCloneWithSameSymbolDecision.guardrails = jsSymbolCloneNeedsSameSymbolDecision.guardrails;
jsSymbolCloneWithSameSymbolDecision.guardrailInventory = jsSymbolCloneNeedsSameSymbolDecision.guardrailInventory;
result = run(jsSymbolCloneWithSameSymbolDecision);
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

const mixedJsNonJsAllowsScopedNonJsUnavailableSegment = state('he-implement');
mixedJsNonJsAllowsScopedNonJsUnavailableSegment.guardrails.push({
  ...g('fallow-audit', 'he-implement', 'fallow audit --dupes --base origin/main'),
  evidence: [
    'Fallow found no clone groups for React TypeScript files',
    'Python detector unavailable',
    'rg static search found no clone groups for scripts/migrate.py',
  ],
});
mixedJsNonJsAllowsScopedNonJsUnavailableSegment.guardrails.push(g('react-doctor', 'he-implement', 'react-doctor --scope changed'));
mixedJsNonJsAllowsScopedNonJsUnavailableSegment.guardrails.push({
  ...g('lint-typecheck', 'he-implement', 'npm run lint && npm run typecheck'),
  evidence: ['React lint passed; TypeScript typecheck passed'],
});
mixedJsNonJsAllowsScopedNonJsUnavailableSegment.guardrailInventory = {
  ...guardrailInventoryWithUiSsot(mixedJsNonJsAllowsScopedNonJsUnavailableSegment, {
    fallow: { id: 'fallow', status: 'required', guardrailId: 'fallow-audit', evidence: ['Fallow and Python static-search proof recorded'] },
    'react-doctor': { id: 'react-doctor', status: 'required', guardrailId: 'react-doctor', evidence: ['React files changed'] },
    'lint-analyze-typecheck': { id: 'lint-analyze-typecheck', status: 'required', guardrailId: 'lint-typecheck', evidence: ['React lint and typecheck passed'] },
  }),
  touchedStacks: ['src/App.tsx', 'scripts/migrate.py'],
};
result = run(mixedJsNonJsAllowsScopedNonJsUnavailableSegment);
assert.equal(result.status, 0, result.stderr);

function addMixedJsSchemaProof(testState, fallowEvidence) {
  withSsotOwnerLedger(testState, [
    {
      ownerClass: 'ui-component',
      decision: 'reuse',
      owner: 'skills/he-implement/references/ssot-owner-reuse.md',
      evidence: ['React UI owner ledger reviewed'],
    },
    {
      ownerClass: 'api-schema-backend',
      decision: 'reuse',
      owner: 'skills/he-implement/references/ssot-owner-reuse.md',
      evidence: ['API schema owner ledger reviewed'],
    },
  ]);
  testState.guardrails.push({
    ...g('fallow-audit', 'he-implement', 'fallow audit --dupes --base origin/main'),
    evidence: fallowEvidence,
  });
  testState.guardrails.push(g('react-doctor', 'he-implement', 'react-doctor --scope changed'));
  testState.guardrails.push({
    ...g('lint-typecheck', 'he-implement', 'npm run lint && npm run typecheck'),
    evidence: ['React lint passed; TypeScript typecheck passed'],
  });
  testState.guardrails.push(g('ssot-scan', 'he-implement', 'node scripts/check-ssot-guardrails.mjs .'));
  testState.guardrailInventory = {
    ...guardrailInventory({
      fallow: { id: 'fallow', status: 'required', guardrailId: 'fallow-audit', evidence: ['Fallow and static search evidence recorded'] },
      'react-doctor': { id: 'react-doctor', status: 'required', guardrailId: 'react-doctor', evidence: ['React files changed'] },
      'lint-analyze-typecheck': { id: 'lint-analyze-typecheck', status: 'required', guardrailId: 'lint-typecheck', evidence: ['React lint and typecheck passed'] },
      'ssot-scanners': { id: 'ssot-scanners', status: 'required', guardrailId: 'ssot-scan', evidence: ['React UI and OpenAPI schema owners checked'] },
    }),
    touchedStacks: ['src/App.tsx', 'openapi.yaml'],
  };
}

const mixedJsSchemaWithoutNonJsFallback = state('he-implement');
addMixedJsSchemaProof(mixedJsSchemaWithoutNonJsFallback, ['Fallow found no clone groups for TSX files']);
result = run(mixedJsSchemaWithoutNonJsFallback);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /explicit non-JS no-duplicate\/no-clone static-search proof/);

const mixedJsSchemaWithUnscopedStaticProof = state('he-implement');
addMixedJsSchemaProof(mixedJsSchemaWithUnscopedStaticProof, [
  'Fallow found no clone groups for TSX files',
  'rg static search found no clone groups',
]);
result = run(mixedJsSchemaWithUnscopedStaticProof);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /explicit non-JS no-duplicate\/no-clone static-search proof/);

const mixedJsSchemaWithMismatchedScopedStaticProof = state('he-implement');
addMixedJsSchemaProof(mixedJsSchemaWithMismatchedScopedStaticProof, [
  'Fallow found no clone groups for TSX files; rg static search covered OpenAPI schema; found no clone groups for TSX files',
]);
result = run(mixedJsSchemaWithMismatchedScopedStaticProof);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /explicit non-JS no-duplicate\/no-clone static-search proof/);

const mixedJsSchemaWithScopedStaticProof = state('he-implement');
addMixedJsSchemaProof(mixedJsSchemaWithScopedStaticProof, [
  'Fallow found no clone groups for TSX files',
  'rg static search found no clone groups for openapi.yaml',
]);
result = run(mixedJsSchemaWithScopedStaticProof);
assert.equal(result.status, 0, result.stderr);

function addJsMultiPathProof(testState, fallowEvidence) {
  withSsotOwnerLedger(testState, [
    {
      ownerClass: 'ui-component',
      decision: 'reuse',
      owner: 'skills/he-implement/references/ssot-owner-reuse.md',
      evidence: ['React UI owner ledger reviewed'],
    },
    {
      ownerClass: 'button',
      decision: 'reuse',
      owner: 'skills/he-implement/references/ssot-owner-reuse.md',
      evidence: ['button owner ledger reviewed'],
    },
    {
      ownerClass: 'card',
      decision: 'reuse',
      owner: 'skills/he-implement/references/ssot-owner-reuse.md',
      evidence: ['card owner ledger reviewed'],
    },
  ]);
  testState.guardrails.push({
    ...g('fallow-audit', 'he-implement', 'fallow audit --dupes --base origin/main'),
    evidence: fallowEvidence,
  });
  testState.guardrails.push({
    ...g('react-doctor', 'he-implement', 'react-doctor --scope changed'),
    evidence: ['React Doctor passed'],
  });
  testState.guardrails.push({
    ...g('lint-typecheck', 'he-implement', 'npm run lint && npm run typecheck'),
    evidence: ['React lint passed; TypeScript typecheck passed'],
  });
  testState.guardrails.push(g('ssot-scan', 'he-implement', 'node scripts/check-ssot-guardrails.mjs .'));
  testState.guardrailInventory = {
    ...guardrailInventory({
      fallow: { id: 'fallow', status: 'required', guardrailId: 'fallow-audit', evidence: ['Fallow duplicate proof recorded'] },
      'react-doctor': { id: 'react-doctor', status: 'required', guardrailId: 'react-doctor', evidence: ['React files changed'] },
      'lint-analyze-typecheck': { id: 'lint-analyze-typecheck', status: 'required', guardrailId: 'lint-typecheck', evidence: ['React lint and typecheck passed'] },
      'ssot-scanners': { id: 'ssot-scanners', status: 'required', guardrailId: 'ssot-scan', evidence: ['React UI owners checked'] },
    }),
    touchedStacks: ['src/Button.tsx', 'src/Card.tsx'],
  };
}

const jsMultiPathWithSinglePathFallowProof = state('he-implement');
addJsMultiPathProof(jsMultiPathWithSinglePathFallowProof, ['Fallow found no clone groups for src/Button.tsx']);
result = run(jsMultiPathWithSinglePathFallowProof);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /JS\/TS\/React\/Next touched stacks require Fallow duplicate\/clone evidence/);

const jsMultiPathWithEveryPathFallowProof = state('he-implement');
addJsMultiPathProof(jsMultiPathWithEveryPathFallowProof, [
  'Fallow found no clone groups for src/Button.tsx',
  'Fallow found no clone groups for src/Card.tsx',
]);
result = run(jsMultiPathWithEveryPathFallowProof);
assert.equal(result.status, 0, result.stderr);

function addJsSinglePathProof(testState, fallowEvidence, touchedStack = 'src/foo.ts') {
  withSsotOwnerLedger(testState, [{
    ownerClass: 'api backend',
    decision: 'reuse',
    owner: 'skills/he-implement/references/ssot-owner-reuse.md',
    evidence: ['API backend owner ledger reviewed'],
  }]);
  testState.guardrails.push({
    ...g('fallow-audit', 'he-implement', 'fallow audit --dupes --base origin/main'),
    evidence: fallowEvidence,
  });
  testState.guardrails.push(g('ssot-scan', 'he-implement', 'node scripts/check-ssot-guardrails.mjs .'));
  testState.guardrailInventory = {
    ...guardrailInventory({
      fallow: { id: 'fallow', status: 'required', guardrailId: 'fallow-audit', evidence: ['Fallow duplicate proof recorded'] },
      'ssot-scanners': { id: 'ssot-scanners', status: 'required', guardrailId: 'ssot-scan', evidence: ['API backend owner checked'] },
    }),
    touchedStacks: [touchedStack],
  };
}

for (const evidence of [
  'Fallow found no clone groups for other/src/foo.ts',
  'Fallow found no clone groups for backup/src/foo.ts.bak',
]) {
  const jsPathProofForDifferentPathFails = state('he-implement');
  addJsSinglePathProof(jsPathProofForDifferentPathFails, [evidence]);
  result = run(jsPathProofForDifferentPathFails);
  assert.notEqual(result.status, 0, evidence);
  assert.match(result.stderr, /JS\/TS\/React\/Next touched stacks require Fallow duplicate\/clone evidence/);
}

for (const evidence of [
  'Fallow found no clone groups for src/foo.ts',
  'Fallow found no clone groups for /tmp/hard-eng/src/foo.ts',
]) {
  const jsPathProofForExactPathPasses = state('he-implement');
  addJsSinglePathProof(jsPathProofForExactPathPasses, [evidence]);
  result = run(jsPathProofForExactPathPasses);
  assert.equal(result.status, 0, `${evidence}: ${result.stderr}`);
}

function addJsTsMixedPathBroadScopeProof(testState, touchedStacks, fallowEvidence) {
  withSsotOwnerLedger(testState, [{
    ownerClass: 'js-ts code',
    decision: 'reuse',
    owner: 'skills/he-implement/references/ssot-owner-reuse.md',
    evidence: ['JS/TS owner ledger reviewed'],
  }]);
  testState.guardrails.push({
    ...g('fallow-audit', 'he-implement', 'fallow audit --dupes --base origin/main'),
    evidence: fallowEvidence,
  });
  testState.guardrails.push(g('ssot-scan', 'he-implement', 'node scripts/check-ssot-guardrails.mjs .'));
  testState.guardrailInventory = {
    ...guardrailInventory({
      fallow: { id: 'fallow', status: 'required', guardrailId: 'fallow-audit', evidence: ['Fallow duplicate proof recorded'] },
      'ssot-scanners': { id: 'ssot-scanners', status: 'required', guardrailId: 'ssot-scan', evidence: ['JS/TS owner checked'] },
    }),
    touchedStacks,
  };
}

for (const { name, touchedStacks, evidence } of [
  {
    name: 'exact JS path proof does not cover broad TypeScript scope',
    touchedStacks: ['src/foo.js', 'typescript'],
    evidence: ['Fallow found no clone groups for src/foo.js'],
  },
  {
    name: 'exact TS path proof does not cover broad JavaScript scope',
    touchedStacks: ['src/foo.ts', 'javascript'],
    evidence: ['Fallow found no clone groups for src/foo.ts'],
  },
]) {
  const jsTsMixedPathBroadScopeWithoutBroadProofFails = state('he-implement');
  addJsTsMixedPathBroadScopeProof(jsTsMixedPathBroadScopeWithoutBroadProofFails, touchedStacks, evidence);
  result = run(jsTsMixedPathBroadScopeWithoutBroadProofFails);
  assert.notEqual(result.status, 0, name);
  assert.match(result.stderr, /JS\/TS\/React\/Next touched stacks require Fallow duplicate\/clone evidence/);
}

for (const { touchedStacks, evidence } of [
  {
    touchedStacks: ['src/foo.js', 'typescript'],
    evidence: ['Fallow found no clone groups for src/foo.js', 'Fallow found no clone groups for TypeScript files'],
  },
  {
    touchedStacks: ['src/foo.ts', 'javascript'],
    evidence: ['Fallow found no clone groups for src/foo.ts', 'Fallow found no clone groups for JavaScript files'],
  },
]) {
  const jsTsMixedPathBroadScopeWithExactAndBroadProofPasses = state('he-implement');
  addJsTsMixedPathBroadScopeProof(jsTsMixedPathBroadScopeWithExactAndBroadProofPasses, touchedStacks, evidence);
  result = run(jsTsMixedPathBroadScopeWithExactAndBroadProofPasses);
  assert.equal(result.status, 0, result.stderr);
}

for (const { name, touchedStacks, evidence, decisions } of [
  {
    name: 'exact JS clean proof plus accepted broad TypeScript finding passes',
    touchedStacks: ['src/foo.js', 'typescript'],
    evidence: ['Fallow found no clone groups for src/foo.js', 'Fallow found clone groups for TypeScript files'],
    decisions: [{
      id: 'ts-clone-owner-decision',
      status: 'accepted',
      summary: 'SSOT owner decision recorded for TypeScript clone groups',
      evidence: ['owner ledger resolved TypeScript duplicate clone groups'],
    }],
  },
  {
    name: 'exact TS clean proof plus accepted broad JavaScript finding passes',
    touchedStacks: ['src/foo.ts', 'javascript'],
    evidence: ['Fallow found no clone groups for src/foo.ts', 'Fallow found clone groups for JavaScript files'],
    decisions: [{
      id: 'js-clone-owner-decision',
      status: 'accepted',
      summary: 'SSOT owner decision recorded for JavaScript clone groups',
      evidence: ['owner ledger resolved JavaScript duplicate clone groups'],
    }],
  },
]) {
  const jsTsMixedPathBroadFoundScopeWithExactCleanProofPasses = state('he-implement');
  jsTsMixedPathBroadFoundScopeWithExactCleanProofPasses.decisions = decisions;
  addJsTsMixedPathBroadScopeProof(jsTsMixedPathBroadFoundScopeWithExactCleanProofPasses, touchedStacks, evidence);
  result = run(jsTsMixedPathBroadFoundScopeWithExactCleanProofPasses);
  assert.equal(result.status, 0, `${name}: ${result.stderr}`);
}

const jsTsMixedPathBroadScopeRejectsGenericDecisionForExactPathFinding = state('he-implement');
jsTsMixedPathBroadScopeRejectsGenericDecisionForExactPathFinding.decisions = [{
  id: 'js-clone-owner-decision',
  status: 'accepted',
  summary: 'SSOT owner decision recorded for JavaScript clone groups',
  evidence: ['owner ledger resolved JavaScript duplicate clone groups'],
}];
addJsTsMixedPathBroadScopeProof(jsTsMixedPathBroadScopeRejectsGenericDecisionForExactPathFinding, ['src/foo.js', 'typescript'], [
  'Fallow found clone groups in src/foo.js',
  'Fallow found no clone groups for TypeScript files',
]);
result = run(jsTsMixedPathBroadScopeRejectsGenericDecisionForExactPathFinding);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /JS\/TS\/React\/Next touched stacks require Fallow duplicate\/clone evidence/);

for (const touchedStacks of [
  ['src/foo.js', 'typescript'],
  ['src/foo.ts', 'javascript'],
]) {
  const jsTsMixedPathBroadScopeWithCombinedProofPasses = state('he-implement');
  addJsTsMixedPathBroadScopeProof(jsTsMixedPathBroadScopeWithCombinedProofPasses, touchedStacks, ['Fallow found no clone groups for JS/TS files']);
  result = run(jsTsMixedPathBroadScopeWithCombinedProofPasses);
  assert.equal(result.status, 0, result.stderr);
}

function addJsTsBroadScopeProof(testState, touchedStacks, fallowEvidence) {
  testState.guardrails.push({
    ...g('fallow-audit', 'he-implement', 'fallow audit --dupes --base origin/main'),
    evidence: fallowEvidence,
  });
  testState.guardrailInventory = {
    ...guardrailInventory({
      fallow: { id: 'fallow', status: 'required', guardrailId: 'fallow-audit', evidence: ['Fallow duplicate proof recorded'] },
    }),
    touchedStacks,
  };
}

for (const [touchedStacks, evidence] of [
  [['typescript'], 'Fallow found no clone groups for JS files'],
  [['javascript'], 'Fallow found no clone groups for TypeScript files'],
  [['javascript', 'typescript'], 'Fallow found no clone groups for JavaScript files'],
]) {
  const jsTsBroadScopeCrossLanguageCleanProofFails = state('he-implement');
  addJsTsBroadScopeProof(jsTsBroadScopeCrossLanguageCleanProofFails, touchedStacks, [evidence]);
  result = run(jsTsBroadScopeCrossLanguageCleanProofFails);
  assert.notEqual(result.status, 0, evidence);
  assert.match(result.stderr, /JS\/TS\/React\/Next touched stacks require Fallow duplicate\/clone evidence/);
}

for (const [touchedStacks, evidence] of [
  [['typescript'], 'Fallow found no clone groups for JS/TS files'],
  [['javascript'], 'Fallow found no clone groups for JS/TS files'],
  [['javascript', 'typescript'], 'Fallow found no clone groups for JavaScript and TypeScript files'],
]) {
  const jsTsBroadScopeCombinedCleanProofPasses = state('he-implement');
  addJsTsBroadScopeProof(jsTsBroadScopeCombinedCleanProofPasses, touchedStacks, [evidence]);
  result = run(jsTsBroadScopeCombinedCleanProofPasses);
  assert.equal(result.status, 0, `${evidence}: ${result.stderr}`);
}

for (const evidence of [
  'Found clone groups in src/Button.tsx; Fallow found no clone groups for TypeScript files',
  'Fallow failed in src/Button.tsx; Fallow found no clone groups for TypeScript files',
  'Fallow exited with code 1 for src/Button.tsx; Fallow found no clone groups for TypeScript files',
]) {
  const tsBroadScopeExtensionFindingBlocksCleanProof = state('he-implement');
  addJsTsBroadScopeProof(tsBroadScopeExtensionFindingBlocksCleanProof, ['typescript'], [evidence]);
  result = run(tsBroadScopeExtensionFindingBlocksCleanProof);
  assert.notEqual(result.status, 0, evidence);
  assert.match(result.stderr, /JS\/TS\/React\/Next touched stacks require Fallow duplicate\/clone evidence/);
}

const jsMultiPathWithWholeScopeFallowProof = state('he-implement');
addJsMultiPathProof(jsMultiPathWithWholeScopeFallowProof, ['Fallow found no clone groups for React TypeScript files']);
result = run(jsMultiPathWithWholeScopeFallowProof);
assert.equal(result.status, 0, result.stderr);

const reactZeroErrorGuardrailProofPasses = state('he-implement');
reactZeroErrorGuardrailProofPasses.guardrails.push({
  ...g('fallow-audit', 'he-implement', 'fallow audit --dupes --base origin/main'),
  evidence: ['Fallow duplicate scan completed with no errors; Fallow found no clone groups for React TypeScript files'],
});
reactZeroErrorGuardrailProofPasses.guardrails.push({
  ...g('react-doctor', 'he-implement', 'react-doctor --scope changed'),
  evidence: ['React Doctor completed with no errors'],
});
reactZeroErrorGuardrailProofPasses.guardrails.push({
  ...g('lint-typecheck', 'he-implement', 'npm run lint && npm run typecheck'),
  evidence: ['ESLint completed with 0 errors; TypeScript typecheck completed with no errors'],
});
reactZeroErrorGuardrailProofPasses.guardrailInventory = {
  ...guardrailInventoryWithUiSsot(reactZeroErrorGuardrailProofPasses, {
    fallow: { id: 'fallow', status: 'required', guardrailId: 'fallow-audit', evidence: ['Fallow duplicate proof recorded'] },
    'react-doctor': { id: 'react-doctor', status: 'required', guardrailId: 'react-doctor', evidence: ['React Doctor completed with no errors'] },
    'lint-analyze-typecheck': { id: 'lint-analyze-typecheck', status: 'required', guardrailId: 'lint-typecheck', evidence: ['ESLint and TypeScript checks completed with no errors'] },
  }),
  touchedStacks: ['react', 'typescript'],
};
result = run(reactZeroErrorGuardrailProofPasses);
assert.equal(result.status, 0, result.stderr);

const reactZeroFailureGuardrailProofPasses = state('he-implement');
reactZeroFailureGuardrailProofPasses.guardrails.push({
  ...g('fallow-audit', 'he-implement', 'fallow audit --dupes --base origin/main'),
  evidence: ['Fallow duplicate scan completed with no failures; Fallow found no clone groups for React TypeScript files'],
});
reactZeroFailureGuardrailProofPasses.guardrails.push({
  ...g('react-doctor', 'he-implement', 'react-doctor --scope changed'),
  evidence: ['React Doctor completed with no failures'],
});
reactZeroFailureGuardrailProofPasses.guardrails.push({
  ...g('lint-typecheck', 'he-implement', 'npm run lint && npm run typecheck'),
  evidence: ['ESLint completed with 0 failures; TypeScript typecheck completed with no failures'],
});
reactZeroFailureGuardrailProofPasses.guardrailInventory = {
  ...guardrailInventoryWithUiSsot(reactZeroFailureGuardrailProofPasses, {
    fallow: { id: 'fallow', status: 'required', guardrailId: 'fallow-audit', evidence: ['Fallow duplicate proof recorded'] },
    'react-doctor': { id: 'react-doctor', status: 'required', guardrailId: 'react-doctor', evidence: ['React Doctor completed with no failures'] },
    'lint-analyze-typecheck': { id: 'lint-analyze-typecheck', status: 'required', guardrailId: 'lint-typecheck', evidence: ['ESLint and TypeScript checks completed with no failures'] },
  }),
  touchedStacks: ['react', 'typescript'],
};
result = run(reactZeroFailureGuardrailProofPasses);
assert.equal(result.status, 0, result.stderr);

for (const [name, mutate, expectedError] of [
  [
    'ssot-never-run',
    (testState) => {
      testState.guardrails = testState.guardrails.map((guardrail) => (
        guardrail.id === 'ssot-scan'
          ? { ...guardrail, evidence: ['SSOT scanner never run; owner ledger recorded'] }
          : guardrail
      ));
    },
    /ssot-scanners requires passed SSOT scanner evidence/,
  ],
  [
    'react-doctor-never-run',
    (testState) => {
      testState.guardrails = testState.guardrails.map((guardrail) => (
        guardrail.id === 'react-doctor'
          ? { ...guardrail, evidence: ['React Doctor never run; React Doctor passed'] }
          : guardrail
      ));
    },
    /react-doctor requires passed React Doctor evidence/,
  ],
  [
    'lint-typecheck-never-run',
    (testState) => {
      testState.guardrails = testState.guardrails.map((guardrail) => (
        guardrail.id === 'lint-typecheck'
          ? { ...guardrail, evidence: ['ESLint never run; ESLint passed; TypeScript typecheck never run; TypeScript typecheck passed'] }
          : guardrail
      ));
    },
    /lint-analyze-typecheck requires lint\/analyze and typecheck evidence/,
  ],
  [
    'fallow-never-run',
    (testState) => {
      testState.guardrails = testState.guardrails.map((guardrail) => (
        guardrail.id === 'fallow-audit'
          ? { ...guardrail, evidence: ['Fallow duplicate scan never run; Fallow found no clone groups for React TypeScript files'] }
          : guardrail
      ));
    },
    /JS\/TS\/React\/Next touched stacks require Fallow duplicate\/clone evidence/,
  ],
]) {
  const neverRunGuardrailProofFails = state('he-implement');
  addJsMultiPathProof(neverRunGuardrailProofFails, ['Fallow found no clone groups for React TypeScript files']);
  mutate(neverRunGuardrailProofFails);
  result = run(neverRunGuardrailProofFails);
  assert.notEqual(result.status, 0, name);
  assert.match(result.stderr, expectedError);
}

const jsMultiPathWithOneScopedCloneDecision = state('he-implement');
addJsMultiPathProof(jsMultiPathWithOneScopedCloneDecision, ['Fallow found clone groups in src/Button.tsx']);
jsMultiPathWithOneScopedCloneDecision.decisions = [{
  id: 'button-clone-owner-decision',
  status: 'accepted',
  summary: 'SSOT owner decision recorded for clone groups',
  evidence: ['owner ledger resolved clone groups in src/Button.tsx'],
}];
result = run(jsMultiPathWithOneScopedCloneDecision);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /JS\/TS\/React\/Next touched stacks require Fallow duplicate\/clone evidence/);

const jsMultiPathSymbolCloneDecisionNeedsRemainingPathProof = state('he-implement');
addJsMultiPathProof(jsMultiPathSymbolCloneDecisionNeedsRemainingPathProof, ['Fallow found clone groups in Button component']);
jsMultiPathSymbolCloneDecisionNeedsRemainingPathProof.decisions = [{
  id: 'button-clone-owner-decision',
  status: 'accepted',
  summary: 'SSOT owner decision recorded for clone groups',
  evidence: ['owner ledger resolved clone groups in Button component'],
}];
result = run(jsMultiPathSymbolCloneDecisionNeedsRemainingPathProof);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /JS\/TS\/React\/Next touched stacks require Fallow duplicate\/clone evidence/);

const jsMultiPathWithDecisionAndRemainingCleanProof = state('he-implement');
addJsMultiPathProof(jsMultiPathWithDecisionAndRemainingCleanProof, [
  'Fallow found clone groups in src/Button.tsx',
  'Fallow found no clone groups for src/Card.tsx',
]);
jsMultiPathWithDecisionAndRemainingCleanProof.decisions = [{
  id: 'button-clone-owner-decision',
  status: 'accepted',
  summary: 'SSOT owner decision recorded for clone groups',
  evidence: ['owner ledger resolved clone groups in src/Button.tsx'],
}];
result = run(jsMultiPathWithDecisionAndRemainingCleanProof);
assert.equal(result.status, 0, result.stderr);

for (const decisionEvidence of [
  'owner ledger resolved clone groups in other/src/foo.js',
  'owner ledger resolved clone groups in src/foo.js.bak',
]) {
  const jsFoundPathDecisionForDifferentPathFails = state('he-implement');
  addJsSinglePathProof(jsFoundPathDecisionForDifferentPathFails, ['Fallow found clone groups in src/foo.js'], 'src/foo.js');
  jsFoundPathDecisionForDifferentPathFails.decisions = [{
    id: 'foo-clone-owner-decision',
    status: 'accepted',
    summary: 'SSOT owner decision recorded for clone groups',
    evidence: [decisionEvidence],
  }];
  result = run(jsFoundPathDecisionForDifferentPathFails);
  assert.notEqual(result.status, 0, decisionEvidence);
  assert.match(result.stderr, /JS\/TS\/React\/Next touched stacks require Fallow duplicate\/clone evidence/);
}

for (const decisionEvidence of [
  'owner ledger resolved clone groups in src/foo.js',
  'owner ledger resolved clone groups in /tmp/hard-eng/src/foo.js',
]) {
  const jsFoundPathDecisionForExactPathPasses = state('he-implement');
  addJsSinglePathProof(jsFoundPathDecisionForExactPathPasses, ['Fallow found clone groups in src/foo.js'], 'src/foo.js');
  jsFoundPathDecisionForExactPathPasses.decisions = [{
    id: 'foo-clone-owner-decision',
    status: 'accepted',
    summary: 'SSOT owner decision recorded for clone groups',
    evidence: [decisionEvidence],
  }];
  result = run(jsFoundPathDecisionForExactPathPasses);
  assert.equal(result.status, 0, `${decisionEvidence}: ${result.stderr}`);
}

function addJsApiPathProof(testState, touchedStack) {
  withSsotOwnerLedger(testState, [{
    ownerClass: 'api backend',
    decision: 'reuse',
    owner: 'skills/he-implement/references/ssot-owner-reuse.md',
    evidence: ['API backend owner ledger reviewed'],
  }]);
  testState.guardrails.push({
    ...g('fallow-audit', 'he-implement', 'fallow audit --dupes --base origin/main'),
    evidence: ['Fallow found no clone groups for TypeScript files'],
  });
  testState.guardrails.push(g('ssot-scan', 'he-implement', 'node scripts/check-ssot-guardrails.mjs .'));
  testState.guardrailInventory = {
    ...guardrailInventory({
      fallow: { id: 'fallow', status: 'required', guardrailId: 'fallow-audit', evidence: ['Fallow TypeScript duplicate proof recorded'] },
      'ssot-scanners': { id: 'ssot-scanners', status: 'required', guardrailId: 'ssot-scan', evidence: ['API backend owner checked'] },
    }),
    touchedStacks: [touchedStack],
  };
}

for (const touchedStack of ['src/api/client.ts', 'src/backend/service.ts']) {
  const jsApiPathWithoutNonJsStaticFallback = state('he-implement');
  addJsApiPathProof(jsApiPathWithoutNonJsStaticFallback, touchedStack);
  result = run(jsApiPathWithoutNonJsStaticFallback);
  assert.equal(result.status, 0, result.stderr);
}

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
      evidence: ['rg static search duplicate search found no clone groups for Dart touched widgets'],
    },
  }),
  touchedStacks: ['flutter', 'dart'],
};
result = run(flutterWithCloneFallback);
assert.equal(result.status, 0, result.stderr);

const flutterWithNaturalFallowToolAbsenceFallback = state('he-implement');
flutterWithNaturalFallowToolAbsenceFallback.guardrailInventory = {
  ...guardrailInventory({
    fallow: {
      id: 'fallow',
      status: 'not_applicable',
      reason: 'Fallow not applicable for Dart',
      evidence: ['rg static search found no clone groups for Dart widgets'],
    },
  }),
  touchedStacks: ['flutter', 'dart'],
};
result = run(flutterWithNaturalFallowToolAbsenceFallback);
assert.equal(result.status, 0, result.stderr);

const flutterWithMixedNaturalFallowToolAbsenceFallback = state('he-implement');
flutterWithMixedNaturalFallowToolAbsenceFallback.guardrailInventory = {
  ...guardrailInventory({
    fallow: {
      id: 'fallow',
      status: 'not_applicable',
      reason: 'Fallow fallback recorded for Dart',
      evidence: ['Fallow not applicable for Dart because rg static search found no clone groups for Dart widgets'],
    },
  }),
  touchedStacks: ['flutter', 'dart'],
};
result = run(flutterWithMixedNaturalFallowToolAbsenceFallback);
assert.equal(result.status, 0, result.stderr);

const pythonWithOnePathProofForTwoTouchedPaths = state('he-implement');
pythonWithOnePathProofForTwoTouchedPaths.guardrailInventory = {
  ...guardrailInventory({
    fallow: {
      id: 'fallow',
      status: 'not_applicable',
      reason: 'no stack-specific clone detector available for Python files',
      evidence: ['rg static search found no clone groups for scripts/foo.py'],
    },
  }),
  touchedStacks: ['scripts/foo.py', 'scripts/bar.py'],
};
result = run(pythonWithOnePathProofForTwoTouchedPaths);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /explicit no-duplicate\/no-clone static-search proof/);

const pythonWithEachPathProofForTouchedPaths = state('he-implement');
pythonWithEachPathProofForTouchedPaths.guardrailInventory = {
  ...guardrailInventory({
    fallow: {
      id: 'fallow',
      status: 'not_applicable',
      reason: 'no stack-specific clone detector available for Python files',
      evidence: [
        'rg static search found no clone groups for scripts/foo.py',
        'rg static search found no clone groups for scripts/bar.py',
      ],
    },
  }),
  touchedStacks: ['scripts/foo.py', 'scripts/bar.py'],
};
result = run(pythonWithEachPathProofForTouchedPaths);
assert.equal(result.status, 0, result.stderr);

const flutterWithSplitScopedCloneFallback = state('he-implement');
flutterWithSplitScopedCloneFallback.guardrailInventory = {
  ...guardrailInventory({
    fallow: {
      id: 'fallow',
      status: 'not_applicable',
      reason: 'no stack-specific clone detector available for Dart in this repo',
      evidence: ['rg static search covered Dart widgets and found no clone groups for Dart widgets'],
    },
  }),
  touchedStacks: ['flutter', 'dart'],
};
result = run(flutterWithSplitScopedCloneFallback);
assert.equal(result.status, 0, result.stderr);

const flutterWithZeroErrorStaticSearchFallback = state('he-implement');
flutterWithZeroErrorStaticSearchFallback.guardrailInventory = {
  ...guardrailInventory({
    fallow: {
      id: 'fallow',
      status: 'not_applicable',
      reason: 'no stack-specific clone detector available for Dart in this repo',
      evidence: ['rg static search completed with no errors for Dart widgets; found no clone groups for Dart widgets'],
    },
  }),
  touchedStacks: ['flutter', 'dart'],
};
result = run(flutterWithZeroErrorStaticSearchFallback);
assert.equal(result.status, 0, result.stderr);

const flutterWithStatus200StaticSearchFallback = state('he-implement');
flutterWithStatus200StaticSearchFallback.guardrailInventory = {
  ...guardrailInventory({
    fallow: {
      id: 'fallow',
      status: 'not_applicable',
      reason: 'no stack-specific clone detector available for Dart in this repo',
      evidence: ['rg static search returned status 200 and code 200 for Dart widgets; found no clone groups for Dart widgets'],
    },
  }),
  touchedStacks: ['flutter', 'dart'],
};
result = run(flutterWithStatus200StaticSearchFallback);
assert.equal(result.status, 0, result.stderr);

for (const evidence of [
  'rg static search returned code 200 for Dart widgets; found no clone groups for Dart widgets',
  'rg static search completed with code 200 for Dart widgets; found no clone groups for Dart widgets',
]) {
  const flutterWithCode200StaticSearchFallback = state('he-implement');
  flutterWithCode200StaticSearchFallback.guardrailInventory = {
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
  result = run(flutterWithCode200StaticSearchFallback);
  assert.equal(result.status, 0, result.stderr);
}

const flutterWithFailedStaticSearchCloneFallback = state('he-implement');
flutterWithFailedStaticSearchCloneFallback.guardrailInventory = {
  ...guardrailInventory({
    fallow: {
      id: 'fallow',
      status: 'not_applicable',
      reason: 'no stack-specific clone detector available for Dart in this repo',
      evidence: ['rg static search failed for Dart widgets; found no clone groups for Dart widgets'],
    },
  }),
  touchedStacks: ['flutter', 'dart'],
};
result = run(flutterWithFailedStaticSearchCloneFallback);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /explicit no-duplicate\/no-clone static-search proof/);

const flutterWithMixedFailedStaticSearchCloneFallback = state('he-implement');
flutterWithMixedFailedStaticSearchCloneFallback.guardrailInventory = {
  ...guardrailInventory({
    fallow: {
      id: 'fallow',
      status: 'not_applicable',
      reason: 'Fallow fallback recorded for Dart',
      evidence: ['Fallow not applicable for Dart because rg static search failed for Dart widgets; found no clone groups for Dart widgets'],
    },
  }),
  touchedStacks: ['flutter', 'dart'],
};
result = run(flutterWithMixedFailedStaticSearchCloneFallback);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /explicit no-duplicate\/no-clone static-search proof/);

for (const evidence of [
  'rg static search exited with code 1 for Dart widgets; found no clone groups for Dart widgets',
  'rg static search exited with non-zero status for Dart widgets; found no clone groups for Dart widgets',
  'rg static search exit status 1 for Dart widgets; found no clone groups for Dart widgets',
  'rg static search returned code 1 for Dart widgets; found no clone groups for Dart widgets',
  'rg static search completed with code 1 for Dart widgets; found no clone groups for Dart widgets',
  'rg static search exited 1 for Dart widgets; found no clone groups for Dart widgets',
  'rg static search status 1 for Dart widgets; found no clone groups for Dart widgets',
  'rg static search completed status 1 for Dart widgets; found no clone groups for Dart widgets',
  'rg static search code=1 for Dart widgets; found no clone groups for Dart widgets',
  'rg static search rc=1 for Dart widgets; found no clone groups for Dart widgets',
  'rg static search returncode=1 for Dart widgets; found no clone groups for Dart widgets',
  'rg static search exitcode=1 for Dart widgets; found no clone groups for Dart widgets',
]) {
  const flutterWithExitCodeFailedStaticSearch = state('he-implement');
  flutterWithExitCodeFailedStaticSearch.guardrailInventory = {
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
  result = run(flutterWithExitCodeFailedStaticSearch);
  assert.notEqual(result.status, 0, evidence);
  assert.match(result.stderr, /explicit no-duplicate\/no-clone static-search proof/);
}

const flutterWithUnscopedFoundCloneAfterScopedCleanProof = state('he-implement');
flutterWithUnscopedFoundCloneAfterScopedCleanProof.guardrailInventory = {
  ...guardrailInventory({
    fallow: {
      id: 'fallow',
      status: 'not_applicable',
      reason: 'no stack-specific clone detector available for Dart in this repo',
      evidence: ['rg static search found no clone groups for Dart widgets. Found clone groups'],
    },
  }),
  touchedStacks: ['flutter', 'dart'],
};
result = run(flutterWithUnscopedFoundCloneAfterScopedCleanProof);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /explicit no-duplicate\/no-clone static-search proof/);

const flutterWithOutOfScopeFoundCloneAfterScopedCleanProof = state('he-implement');
flutterWithOutOfScopeFoundCloneAfterScopedCleanProof.guardrailInventory = {
  ...guardrailInventory({
    fallow: {
      id: 'fallow',
      status: 'not_applicable',
      reason: 'no stack-specific clone detector available for Dart in this repo',
      evidence: ['rg static search found no clone groups for Dart widgets. Found clone groups for TSX files'],
    },
  }),
  touchedStacks: ['flutter', 'dart'],
};
result = run(flutterWithOutOfScopeFoundCloneAfterScopedCleanProof);
assert.equal(result.status, 0, result.stderr);

const flutterWithMismatchedScopedCloneFallback = state('he-implement');
flutterWithMismatchedScopedCloneFallback.guardrailInventory = {
  ...guardrailInventory({
    fallow: {
      id: 'fallow',
      status: 'not_applicable',
      reason: 'no stack-specific clone detector available for Dart in this repo',
      evidence: ['rg static search covered Dart widgets; found no clone groups for TSX files'],
    },
  }),
  touchedStacks: ['flutter', 'dart'],
};
result = run(flutterWithMismatchedScopedCloneFallback);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /explicit no-duplicate\/no-clone static-search proof/);

const flutterWithArrayMismatchedScopedCloneFallback = state('he-implement');
flutterWithArrayMismatchedScopedCloneFallback.guardrailInventory = {
  ...guardrailInventory({
    fallow: {
      id: 'fallow',
      status: 'not_applicable',
      reason: 'no stack-specific clone detector available for Dart in this repo',
      evidence: ['rg static search covered Dart widgets', 'found no clone groups for TSX files'],
    },
  }),
  touchedStacks: ['flutter', 'dart'],
};
result = run(flutterWithArrayMismatchedScopedCloneFallback);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /explicit no-duplicate\/no-clone static-search proof/);

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

const flutterWithWrongStackToolAbsenceCloneFallback = state('he-implement');
flutterWithWrongStackToolAbsenceCloneFallback.guardrailInventory = {
  ...guardrailInventory({
    fallow: {
      id: 'fallow',
      status: 'not_applicable',
      reason: 'no stack-specific Fallow detector for Ruby',
      evidence: ['rg static search found no clone groups for Dart widgets'],
    },
  }),
  touchedStacks: ['flutter', 'dart'],
};
result = run(flutterWithWrongStackToolAbsenceCloneFallback);
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
      evidence: ['tool unavailable; rg duplicate search found zero clone groups for Dart touched widgets'],
    },
  }),
  touchedStacks: ['flutter', 'dart'],
};
result = run(flutterWithZeroCloneFallback);
assert.equal(result.status, 0, result.stderr);

for (const evidence of [
  'tool unavailable; rg duplicate search clone groups none for Dart touched widgets',
  'tool unavailable; rg duplicate search duplicates absent for Dart touched widgets',
  'tool unavailable; rg duplicate result: none for Dart touched widgets',
  'tool unavailable; rg duplicate output: not found for Dart touched widgets',
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
      evidence: ['tool unavailable; rg duplicate search found clone groups for Dart touched widgets'],
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

const flutterWithThenFoundCloneClause = state('he-implement');
flutterWithThenFoundCloneClause.guardrailInventory = {
  ...guardrailInventory({
    fallow: {
      id: 'fallow',
      status: 'not_applicable',
      reason: 'no stack-specific clone detector available for Dart in this repo',
      evidence: ['tool unavailable; rg found no duplicate groups then found clone groups'],
    },
  }),
  touchedStacks: ['flutter', 'dart'],
};
result = run(flutterWithThenFoundCloneClause);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /explicit no-duplicate\/no-clone static-search proof/);

for (const evidence of [
  'tool unavailable; rg found no duplicate groups and also found clone groups',
  'tool unavailable; rg found no duplicate groups plus found clone groups',
  'tool unavailable; rg found no duplicate groups as well as found clone groups',
  'tool unavailable; rg found no duplicate groups with clone groups found for Dart widgets',
]) {
  const flutterWithAlsoPlusFoundCloneClause = state('he-implement');
  flutterWithAlsoPlusFoundCloneClause.guardrailInventory = {
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
  result = run(flutterWithAlsoPlusFoundCloneClause);
  assert.notEqual(result.status, 0, evidence);
  assert.match(result.stderr, /explicit no-duplicate\/no-clone static-search proof/);
}

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

const flutterWithCopyPasteCloneDecision = state('he-implement');
flutterWithCopyPasteCloneDecision.decisions = [{
  id: 'copy-paste-owner-decision',
  status: 'accepted',
  summary: 'SSOT owner decision recorded for copy-paste groups',
  evidence: ['copy-paste owner decision recorded for Dart widgets'],
}];
flutterWithCopyPasteCloneDecision.guardrailInventory = {
  ...guardrailInventory({
    fallow: {
      id: 'fallow',
      status: 'not_applicable',
      reason: 'no stack-specific clone detector available for Dart in this repo',
      evidence: ['tool unavailable; rg duplicate search found no clone groups for Dart widgets. Detected copy-paste widgets'],
    },
  }),
  touchedStacks: ['flutter', 'dart'],
};
result = run(flutterWithCopyPasteCloneDecision);
assert.equal(result.status, 0, result.stderr);

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

for (const evidence of [
  'rg static search found no duplicate groups for Dart widgets; clone count: 2 for Dart widgets',
  'rg static search found no clone groups for Dart widgets; duplicate count 1 for Dart widgets',
]) {
  const flutterWithCloneCountLabel = state('he-implement');
  flutterWithCloneCountLabel.guardrailInventory = {
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
  result = run(flutterWithCloneCountLabel);
  assert.notEqual(result.status, 0, evidence);
  assert.match(result.stderr, /explicit no-duplicate\/no-clone static-search proof/);
}

const flutterWithFoundCloneDecision = state('he-implement');
flutterWithFoundCloneDecision.guardrails.push(g('ssot-scan', 'he-implement', 'node scripts/check-ssot-guardrails.mjs .'));
flutterWithFoundCloneDecision.guardrailInventory = {
  ...guardrailInventory({
    'ssot-scanners': {
      id: 'ssot-scanners',
      status: 'required',
      guardrailId: 'ssot-scan',
      evidence: ['static search found Dart clone groups; SSOT owner decision recorded in owner ledger'],
    },
    fallow: {
      id: 'fallow',
      status: 'not_applicable',
      reason: 'no stack-specific clone detector available for Dart in this repo',
      evidence: ['tool unavailable; rg duplicate search found clone groups for Dart touched widgets'],
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
      evidence: ['tool unavailable; rg duplicate search found clone groups for Dart touched widgets'],
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
      evidence: ['tool unavailable; rg duplicate search found clone groups for Dart touched widgets'],
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
  evidence: ['owner ledger resolved Dart duplicate clone groups'],
}];
flutterWithStructuredCloneDecision.guardrailInventory = {
  ...guardrailInventory({
    fallow: {
      id: 'fallow',
      status: 'not_applicable',
      reason: 'no stack-specific clone detector available for Dart in this repo',
      evidence: ['tool unavailable; rg duplicate search found clone groups for Dart touched widgets'],
    },
  }),
  touchedStacks: ['flutter', 'dart'],
};
result = run(flutterWithStructuredCloneDecision);
assert.equal(result.status, 0, result.stderr);

const flutterWithUnscopedFoundCloneDecision = state('he-implement');
flutterWithUnscopedFoundCloneDecision.decisions = [{
  id: 'clone-owner-decision',
  status: 'accepted',
  summary: 'SSOT owner decision recorded for clone groups',
  evidence: ['owner ledger resolved Dart duplicate clone groups'],
}];
flutterWithUnscopedFoundCloneDecision.guardrailInventory = {
  ...guardrailInventory({
    fallow: {
      id: 'fallow',
      status: 'not_applicable',
      reason: 'no stack-specific clone detector available for Dart in this repo',
      evidence: ['rg static search found no clone groups for Dart widgets. Found clone groups'],
    },
  }),
  touchedStacks: ['flutter', 'dart'],
};
result = run(flutterWithUnscopedFoundCloneDecision);
assert.equal(result.status, 0, result.stderr);

const mixedNonJsCleanAndDecisionScopes = state('he-implement');
withSsotOwnerLedger(mixedNonJsCleanAndDecisionScopes, [
  {
    ownerClass: 'dart',
    decision: 'reuse',
    owner: 'skills/he-implement/references/ssot-owner-reuse.md',
    evidence: ['Dart owner ledger reviewed'],
  },
  {
    ownerClass: 'python',
    decision: 'reuse',
    owner: 'skills/he-implement/references/ssot-owner-reuse.md',
    evidence: ['Python owner ledger reviewed'],
  },
]);
mixedNonJsCleanAndDecisionScopes.decisions = [{
  id: 'python-clone-owner-decision',
  status: 'accepted',
  summary: 'SSOT owner decision recorded for clone groups',
  evidence: ['owner ledger resolved Python duplicate clone groups'],
}];
mixedNonJsCleanAndDecisionScopes.guardrailInventory = {
  ...guardrailInventory({
    fallow: {
      id: 'fallow',
      status: 'not_applicable',
      reason: 'no stack-specific clone detector available for Dart and Python in this repo',
      evidence: ['rg static search found no clone groups for Dart widgets. rg static search found clone groups for Python files'],
    },
  }),
  touchedStacks: ['flutter', 'dart', 'python'],
};
result = run(mixedNonJsCleanAndDecisionScopes);
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

for (const evidence of [
  'production backend write was executed',
  'production backend operation was executed',
  'without approval production backend write was executed',
  'not approved production backend write was executed',
]) {
  const genericObjectBeforeVerbProdWriteRequiresBoundary = state('he-verify');
  genericObjectBeforeVerbProdWriteRequiresBoundary.guardrails.push({
    ...g('e2e-side-effects', 'he-verify', 'npx playwright test e2e/checkout.spec.ts'),
    evidence: [evidence],
  });
  result = run(genericObjectBeforeVerbProdWriteRequiresBoundary);
  assert.notEqual(result.status, 0, evidence);
  assert.match(result.stderr, /approvalBoundaries are required/);
}

for (const evidence of [
  'not safe production backend write was executed',
  'no rollback production backend write was executed',
  'never reviewed production backend write was executed',
  'without rollback production backend write was executed',
]) {
  const contextNegationBeforeExecutedProdWriteRequiresBoundary = state('he-verify');
  contextNegationBeforeExecutedProdWriteRequiresBoundary.guardrails.push({
    ...g('e2e-side-effects', 'he-verify', 'npx playwright test e2e/checkout.spec.ts'),
    evidence: [evidence],
  });
  result = run(contextNegationBeforeExecutedProdWriteRequiresBoundary);
  assert.notEqual(result.status, 0, evidence);
  assert.match(result.stderr, /approvalBoundaries are required/);
}

for (const evidence of [
  'production backend write was not executed',
  'no production backend write executed',
  'not executed production backend write',
  'never ran production backend migration',
  'without running production backend migration',
]) {
  const directNegatedProdWriteDoesNotRequireBoundary = state('he-verify');
  directNegatedProdWriteDoesNotRequireBoundary.guardrails.push({
    ...g('safe-boundary-check', 'he-verify', 'node scripts/check-safe-boundaries.mjs'),
    evidence: [evidence],
  });
  result = run(directNegatedProdWriteDoesNotRequireBoundary);
  assert.equal(result.status, 0, evidence);
}

const missingApprovalBeforeActionRequiresBoundary = state('he-verify');
missingApprovalBeforeActionRequiresBoundary.guardrails.push({
  ...g('e2e-side-effects', 'he-verify', 'npx playwright test e2e/checkout.spec.ts'),
  evidence: ['not approved sent production SMS'],
});
result = run(missingApprovalBeforeActionRequiresBoundary);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /approvalBoundaries are required/);

for (const evidence of [
  'created test user credentials',
  'created E2E test account',
  'used E2E test account password',
]) {
  const generatedTestCredentialRequiresBoundary = state('he-verify');
  generatedTestCredentialRequiresBoundary.guardrails.push({
    ...g('credential-smoke', 'he-verify', 'node scripts/check-login.mjs'),
    evidence: [evidence],
  });
  result = run(generatedTestCredentialRequiresBoundary);
  assert.notEqual(result.status, 0, evidence);
  assert.match(result.stderr, /approvalBoundaries are required/);
}

const nonGeneratedTestAccountDoesNotRequireBoundary = state('he-verify');
nonGeneratedTestAccountDoesNotRequireBoundary.guardrails.push({
  ...g('credential-smoke', 'he-verify', 'node scripts/check-login.mjs'),
  evidence: ['created test account fixture explicitly non-generated and local only'],
});
result = run(nonGeneratedTestAccountDoesNotRequireBoundary);
assert.equal(result.status, 0, result.stderr);

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

const evalAgentWorkEvidenceDoesNotRequireBoundary = state('he-verify');
evalAgentWorkEvidenceDoesNotRequireBoundary.agentWork = [{
  id: 'model-eval',
  kind: 'eval',
  model: 'gpt-5.4-mini',
  purpose: 'approval boundary eval coverage',
  status: 'done',
  evidence: ['case id prod_payment_delete'],
}];
result = run(evalAgentWorkEvidenceDoesNotRequireBoundary);
assert.equal(result.status, 0, result.stderr);

const agentWorkPurposeOnlyDoesNotRequireBoundary = state('he-verify');
agentWorkPurposeOnlyDoesNotRequireBoundary.agentWork = [{
  id: 'review-agent',
  kind: 'subagent',
  model: 'gpt-5.5',
  purpose: 'review sent production SMS flow',
  status: 'done',
  evidence: ['reviewed flow only'],
}];
result = run(agentWorkPurposeOnlyDoesNotRequireBoundary);
assert.equal(result.status, 0, result.stderr);

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

const receiptArtifactPathDoesNotRequireBoundary = state('he-verify');
receiptArtifactPathDoesNotRequireBoundary.steps = [{
  ...receiptArtifactPathDoesNotRequireBoundary.steps[0],
  receipt: {
    ...receiptArtifactPathDoesNotRequireBoundary.steps[0].receipt,
    ownerProof: ['tests/e2e/sent-production-sms'],
    artifacts: ['tests/e2e/sent-production-sms.spec.ts'],
  },
}];
result = run(receiptArtifactPathDoesNotRequireBoundary);
assert.equal(result.status, 0, result.stderr);

const receiptEvidenceArtifactPathDoesNotRequireBoundary = state('he-verify');
receiptEvidenceArtifactPathDoesNotRequireBoundary.steps = [{
  ...receiptEvidenceArtifactPathDoesNotRequireBoundary.steps[0],
  receipt: {
    ...receiptEvidenceArtifactPathDoesNotRequireBoundary.steps[0].receipt,
    evidence: ['tests/e2e/sent-production-sms.spec.ts'],
  },
}];
result = run(receiptEvidenceArtifactPathDoesNotRequireBoundary);
assert.equal(result.status, 0, result.stderr);

const receiptArtifactPerformedRiskMarkerRequiresBoundary = state('he-verify');
receiptArtifactPerformedRiskMarkerRequiresBoundary.steps = [{
  ...receiptArtifactPerformedRiskMarkerRequiresBoundary.steps[0],
  receipt: {
    ...receiptArtifactPerformedRiskMarkerRequiresBoundary.steps[0].receipt,
    artifacts: ['performed-risk: sent production SMS; artifact tests/e2e/sent-production-sms.spec.ts'],
  },
}];
result = run(receiptArtifactPerformedRiskMarkerRequiresBoundary);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /approvalBoundaries are required/);

const receiptEvidencePerformedRiskMarkerRequiresBoundary = state('he-verify');
receiptEvidencePerformedRiskMarkerRequiresBoundary.steps = [{
  ...receiptEvidencePerformedRiskMarkerRequiresBoundary.steps[0],
  receipt: {
    ...receiptEvidencePerformedRiskMarkerRequiresBoundary.steps[0].receipt,
    evidence: ['performed-risk: sent production SMS; artifact tests/e2e/sent-production-sms.spec.ts'],
  },
}];
result = run(receiptEvidencePerformedRiskMarkerRequiresBoundary);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /approvalBoundaries are required/);

const guardrailArtifactPathDoesNotRequireBoundary = state('he-verify');
guardrailArtifactPathDoesNotRequireBoundary.guardrails.push({
  ...g('e2e-artifact', 'he-verify', 'npx playwright test e2e/sms.spec.ts'),
  reason: 'tests/e2e/sent-production-sms.spec.ts',
  evidence: ['tests/e2e/sent-production-sms.spec.ts'],
});
result = run(guardrailArtifactPathDoesNotRequireBoundary);
assert.equal(result.status, 0, result.stderr);

const guardrailArtifactPerformedRiskMarkerRequiresBoundary = state('he-verify');
guardrailArtifactPerformedRiskMarkerRequiresBoundary.guardrails.push({
  ...g('e2e-artifact', 'he-verify', 'npx playwright test e2e/sms.spec.ts'),
  evidence: ['performed-risk: sent production SMS; artifact tests/e2e/sent-production-sms.spec.ts'],
});
result = run(guardrailArtifactPerformedRiskMarkerRequiresBoundary);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /approvalBoundaries are required/);

const guardrailCommandPathWithPerformedActionRequiresBoundary = state('he-verify');
guardrailCommandPathWithPerformedActionRequiresBoundary.guardrails.push({
  ...g('e2e-artifact', 'he-verify', 'npx playwright test tests/e2e/sms.spec.ts'),
  evidence: ['npx playwright test tests/e2e/sms.spec.ts: sent production SMS'],
});
result = run(guardrailCommandPathWithPerformedActionRequiresBoundary);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /approvalBoundaries are required/);

const guardrailArtifactUrlDoesNotRequireBoundary = state('he-verify');
guardrailArtifactUrlDoesNotRequireBoundary.guardrails.push({
  ...g('e2e-artifact-url', 'he-verify', 'npx playwright test e2e/sms.spec.ts'),
  evidence: ['https://ci.example/sent-production-sms'],
});
result = run(guardrailArtifactUrlDoesNotRequireBoundary);
assert.equal(result.status, 0, result.stderr);

const guardrailArtifactUrlMarkerOnlyDoesNotRequireBoundary = state('he-verify');
guardrailArtifactUrlMarkerOnlyDoesNotRequireBoundary.guardrails.push({
  ...g('e2e-artifact-url', 'he-verify', 'npx playwright test e2e/sms.spec.ts'),
  evidence: ['performed-risk artifact https://ci.example/sent-production-sms'],
});
result = run(guardrailArtifactUrlMarkerOnlyDoesNotRequireBoundary);
assert.equal(result.status, 0, result.stderr);

const guardrailArtifactUrlWithPerformedActionRequiresBoundary = state('he-verify');
guardrailArtifactUrlWithPerformedActionRequiresBoundary.guardrails.push({
  ...g('e2e-artifact-url', 'he-verify', 'npx playwright test e2e/sms.spec.ts'),
  evidence: ['https://ci.example/sent-production-sms: sent production SMS'],
});
result = run(guardrailArtifactUrlWithPerformedActionRequiresBoundary);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /approvalBoundaries are required/);

for (const evidence of [
  '[performed-risk: sent production SMS](https://ci.example/run)',
  'performed-risk: [sent production SMS](https://ci.example/run)',
]) {
  const markdownLinkPerformedRiskRequiresBoundary = state('he-verify');
  markdownLinkPerformedRiskRequiresBoundary.guardrails.push({
    ...g('e2e-artifact-url', 'he-verify', 'npx playwright test e2e/sms.spec.ts'),
    evidence: [evidence],
  });
  result = run(markdownLinkPerformedRiskRequiresBoundary);
  assert.notEqual(result.status, 0, evidence);
  assert.match(result.stderr, /approvalBoundaries are required/);
}

for (const evidence of [
  'e2e/sent-production-sms',
  'sent-production-sms',
  '[sent production SMS](https://ci.example/run)',
  'case sent-production-sms passed',
  'artifact sent-production-sms recorded',
  'artifact: sent-production-sms recorded',
  'case_id=sent-production-sms passed',
  'case_id=sent.production.sms passed',
  'artifact: sent.production.sms recorded',
]) {
  const shallowArtifactRefDoesNotRequireBoundary = state('he-verify');
  shallowArtifactRefDoesNotRequireBoundary.guardrails.push({
    ...g('e2e-artifact-ref', 'he-verify', 'npx playwright test e2e/sms.spec.ts'),
    evidence: [evidence],
  });
  result = run(shallowArtifactRefDoesNotRequireBoundary);
  assert.equal(result.status, 0, evidence);
}

const embeddedArtifactSlugWithPerformedRiskRequiresBoundary = state('he-verify');
embeddedArtifactSlugWithPerformedRiskRequiresBoundary.guardrails.push({
  ...g('e2e-artifact-ref', 'he-verify', 'npx playwright test e2e/sms.spec.ts'),
  evidence: ['performed-risk: sent production SMS; artifact sent-production-sms recorded'],
});
result = run(embeddedArtifactSlugWithPerformedRiskRequiresBoundary);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /approvalBoundaries are required/);

for (const evidence of [
  'tests/e2e/sent-production-sms.spec.ts',
  'case sent-production-sms passed',
  'https://ci.example/runs/sent-production-sms',
]) {
  const e2ePolicyArtifactEvidenceDoesNotRequireBoundary = state('he-verify');
  e2ePolicyArtifactEvidenceDoesNotRequireBoundary.e2ePolicy = { evidence: [evidence] };
  result = run(e2ePolicyArtifactEvidenceDoesNotRequireBoundary);
  assert.equal(result.status, 0, evidence);
}

const e2ePolicyPerformedRiskEvidenceRequiresBoundary = state('he-verify');
e2ePolicyPerformedRiskEvidenceRequiresBoundary.e2ePolicy = {
  evidence: ['performed-risk: sent production SMS; artifact tests/e2e/sent-production-sms.spec.ts'],
};
result = run(e2ePolicyPerformedRiskEvidenceRequiresBoundary);
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

for (const evidence of [
  'Appwrite schema validator fixed',
  'production Appwrite schema validator fixed',
  'Appwrite schema validator needs fix',
  'production Appwrite schema validator needs fix',
]) {
  const appwriteSchemaValidatorDoesNotRequireApproval = state('he-verify');
  appwriteSchemaValidatorDoesNotRequireApproval.guardrails.push({
    ...g('appwrite-schema-validator', 'he-verify', 'node scripts/he-state-compliance.mjs'),
    evidence: [evidence],
  });
  result = run(appwriteSchemaValidatorDoesNotRequireApproval);
  assert.equal(result.status, 0, result.stderr);
}

for (const evidence of [
  'native permission prompt test updated',
  'native permission dialog opened test updated',
  'permission guardrail triggered',
  'native permission scanner triggered',
]) {
  const nativePermissionCodeTestDoesNotRequireApproval = state('he-verify');
  nativePermissionCodeTestDoesNotRequireApproval.guardrails.push({
    ...g('native-permission-test', 'he-verify', 'node scripts/he-state-compliance.mjs'),
    evidence: [evidence],
  });
  result = run(nativePermissionCodeTestDoesNotRequireApproval);
  assert.equal(result.status, 0, result.stderr);
}

for (const evidence of [
  'fixed real credential validator',
  'generated credential cleanup test updated',
  'real credential validator failed',
]) {
  const credentialCodeTestDoesNotRequireApproval = state('he-verify');
  credentialCodeTestDoesNotRequireApproval.guardrails.push({
    ...g('credential-validator-test', 'he-verify', 'node scripts/he-state-compliance.mjs'),
    evidence: [evidence],
  });
  result = run(credentialCodeTestDoesNotRequireApproval);
  assert.equal(result.status, 0, result.stderr);
}

for (const evidence of [
  'real credentials E2E test passed',
  'production account smoke test passed',
]) {
  const credentialUseTestRequiresApproval = state('he-verify');
  credentialUseTestRequiresApproval.guardrails.push({
    ...g('credential-e2e-proof', 'he-verify', 'npx playwright test'),
    evidence: [evidence],
  });
  result = run(credentialUseTestRequiresApproval);
  assert.notEqual(result.status, 0, evidence);
  assert.match(result.stderr, /approvalBoundaries are required/);
}

for (const evidence of [
  'unit test sent production SMS stub',
  'unit test clicked native permission dialog stub',
]) {
  const testStubEvidenceDoesNotRequireApproval = state('he-verify');
  testStubEvidenceDoesNotRequireApproval.guardrails.push({
    ...g('test-stub-proof', 'he-verify', 'node --test tests/e2e-stubs.test.mjs'),
    evidence: [evidence],
  });
  result = run(testStubEvidenceDoesNotRequireApproval);
  assert.equal(result.status, 0, result.stderr);
}

for (const evidence of [
  'Playwright spec sent production SMS',
  'sent production SMS in Playwright spec',
  'E2E spec clicked native permission dialog',
]) {
  const e2eSpecPerformedActionRequiresApproval = state('he-verify');
  e2eSpecPerformedActionRequiresApproval.guardrails.push({
    ...g('e2e-spec-proof', 'he-verify', 'npx playwright test tests/e2e/spec-risk.spec.ts'),
    evidence: [evidence],
  });
  result = run(e2eSpecPerformedActionRequiresApproval);
  assert.notEqual(result.status, 0, evidence);
  assert.match(result.stderr, /approvalBoundaries are required/);
}

const skippedHypotheticalGuardrailReasonDoesNotRequireApproval = state('he-verify');
skippedHypotheticalGuardrailReasonDoesNotRequireApproval.guardrails.push({
  ...g('e2e-preflight', 'he-verify', 'npx playwright test e2e/sms.spec.ts'),
  status: 'skipped',
  reason: 'skipped because it would send production SMS',
  evidence: ['preflight only'],
});
result = run(skippedHypotheticalGuardrailReasonDoesNotRequireApproval);
assert.equal(result.status, 0, result.stderr);

const skippedGerundHypotheticalGuardrailReasonDoesNotRequireApproval = state('he-verify');
skippedGerundHypotheticalGuardrailReasonDoesNotRequireApproval.guardrails.push({
  ...g('e2e-preflight', 'he-verify', 'npx playwright test e2e/sms.spec.ts'),
  status: 'skipped',
  reason: 'skipped because sending production SMS would be destructive',
  evidence: ['preflight only'],
});
result = run(skippedGerundHypotheticalGuardrailReasonDoesNotRequireApproval);
assert.equal(result.status, 0, result.stderr);

const skippedGuardrailWithPerformedEvidenceRequiresApproval = state('he-verify');
skippedGuardrailWithPerformedEvidenceRequiresApproval.guardrails.push({
  ...g('e2e-preflight', 'he-verify', 'npx playwright test e2e/sms.spec.ts'),
  status: 'skipped',
  reason: 'skipped because it would send production SMS',
  evidence: ['performed manual browser step sent production SMS'],
});
result = run(skippedGuardrailWithPerformedEvidenceRequiresApproval);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /approvalBoundaries are required/);

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

const preventionBaseVerbRiskySideEffectRequiresBoundary = state('he-verify');
preventionBaseVerbRiskySideEffectRequiresBoundary.guardrails.push({
  ...g('scanner-prevents-prod-writes', 'he-verify', 'node scripts/check-no-prod-writes.mjs'),
  evidence: ['changed scanner to prevent prod writes as we trigger production webhook'],
});
result = run(preventionBaseVerbRiskySideEffectRequiresBoundary);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /approvalBoundaries are required/);

const leadingRiskThenPreventionRequiresBoundary = state('he-verify');
leadingRiskThenPreventionRequiresBoundary.guardrails.push({
  ...g('scanner-prevents-prod-writes', 'he-verify', 'node scripts/check-no-prod-writes.mjs'),
  evidence: ['sent production SMS plus changed scanner to prevent prod writes'],
});
result = run(leadingRiskThenPreventionRequiresBoundary);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /approvalBoundaries are required/);

const preventionNativePromptRiskySideEffectRequiresBoundary = state('he-verify');
preventionNativePromptRiskySideEffectRequiresBoundary.guardrails.push({
  ...g('scanner-prevents-native-prompts', 'he-verify', 'node scripts/check-native-prompts.mjs'),
  evidence: ['changed scanner to prevent native permission prompts because native permission dialog opened'],
});
result = run(preventionNativePromptRiskySideEffectRequiresBoundary);
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

const negatedPrefixObjectBeforeVerbSideEffectRequiresBoundary = state('he-verify');
negatedPrefixObjectBeforeVerbSideEffectRequiresBoundary.guardrails.push({
  ...g('safe-boundary-check', 'he-verify', 'node scripts/check-safe-boundaries.mjs'),
  evidence: ['no prod mutation following production SMS sent'],
});
result = run(negatedPrefixObjectBeforeVerbSideEffectRequiresBoundary);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /approvalBoundaries are required/);

for (const evidence of [
  'no prod mutation where production SMS sent',
  'changed scanner to prevent prod writes with production SMS sent',
]) {
  const objectBeforeVerbConnectorSideEffectRequiresBoundary = state('he-verify');
  objectBeforeVerbConnectorSideEffectRequiresBoundary.guardrails.push({
    ...g('safe-boundary-check', 'he-verify', 'node scripts/check-safe-boundaries.mjs'),
    evidence: [evidence],
  });
  result = run(objectBeforeVerbConnectorSideEffectRequiresBoundary);
  assert.notEqual(result.status, 0, evidence);
  assert.match(result.stderr, /approvalBoundaries are required/);
}

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

const productionCleanupScriptPassedRequiresBoundary = state('he-verify');
productionCleanupScriptPassedRequiresBoundary.guardrails.push({
  ...g('prod-cleanup', 'he-verify', 'node scripts/cleanup-prod.mjs'),
  evidence: ['production cleanup script passed'],
});
result = run(productionCleanupScriptPassedRequiresBoundary);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /approvalBoundaries are required/);

const productionCleanupExecutedApproved = state('he-verify');
productionCleanupExecutedApproved.guardrails.push({
  ...g('prod-cleanup', 'he-verify', 'node scripts/cleanup-prod.mjs'),
  evidence: ['production cleanup executed'],
});
productionCleanupExecutedApproved.approvalBoundaries = [
  { id: 'prod-cleanup', category: 'prod-cleanup', status: 'approved', reason: 'user approved production cleanup', evidence: ['approval quote recorded'] },
];
result = run(productionCleanupExecutedApproved);
assert.equal(result.status, 0, result.stderr);

for (const evidence of [
  'no real credentials',
  'without generated users',
  'no native permission prompt',
  'no production SMS sent',
  'production SMS not sent',
  'no approval needed and production SMS not sent',
  'no approval needed production SMS not sent',
  'without approval production SMS not sent',
  'SMS in production was not sent',
  'email in production was not sent',
  'production SMS did not send',
  'production email does not send',
  'SMS in production did not send',
  'production messages do not send',
  'native permission prompt not shown',
  'without prod email side effects',
  'no prod payment charged',
  'no production data shared',
  'sent no production SMS',
  'sent zero production emails',
  'not sending production SMS',
  'without charging prod card',
  'not notifying production user',
  'native permission prompt not triggered',
  'permission dialog not opened',
  'no prod cleanup',
  'prod cleanup not needed',
  'production cleanup not required',
  'production cleanup validation test passed',
  'production cleanup check passed',
  'production cleanup validator passing',
  'zero production SMS sent',
  '0 prod emails sent',
  'none production messages sent',
  'production webhook not triggered',
  'production SMS not delivered',
  'production email not posted',
  "didn't send production SMS",
  "production SMS wasn't sent",
  'production file not uploaded',
  'production record not inserted',
  'prod user not upserted',
  'production data not patched',
  'not revoked production token',
  'not uploaded production file',
  'not triggered production webhook',
  'database migration was not run in production',
  'would apply production database migration',
  'would execute prod backend migration',
  'skipped to avoid triggering production webhook',
  'skipped to avoid posting production webhook',
  'skipped to avoid delivering production email',
  'skipped to avoid uploading production file',
  'skipped to avoid applying production database migration',
  'skipped to avoid opening native permission dialog',
  'would show native permission prompt',
  'card was not charged in production',
  'webhook was not fired in production',
  'file was not uploaded in production',
  'cannot send production SMS',
  'can not log into production account',
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
  'SMS was sent in production',
  'SMS in production was sent',
  'sent production email',
  'production SMS did send',
  'production email does send',
  'production messages do send',
  'sent email in production',
  'email in production was sent',
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
  'inserted production record',
  'upserted prod user',
  'patched production data',
  'uploaded production file',
  'triggered production webhook',
  'posted production webhook',
  'called production webhook',
  'invoked production webhook',
  'delivered production email',
  'created production API key',
  'revoked production token',
  'updated prod secret',
  'applied production database migration',
  'ran prod backend migration',
  'executed production Appwrite migration',
  'database migration was applied in production',
  'database migration was run in production',
  'card was charged in production',
  'webhook in production was triggered',
  'webhook in production was fired',
  'data was shared in production',
  'account was deleted in production',
  'Appwrite schema was modified in production',
]) {
  const appwriteBoundary = state('he-verify');
  appwriteBoundary.guardrails.push({
    ...g('appwrite-permission-check', 'he-verify', 'node scripts/check-appwrite.mjs'),
    evidence: [evidence],
  });
  result = run(appwriteBoundary);
  assert.notEqual(result.status, 0, evidence);
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
  'signed in with production account',
  'used prod credentials',
  'log into production account',
  'logging into production account',
  'sign into production account',
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

for (const evidence of [
  'not used personal account',
  'not used production account',
  'not signed in with production account',
  'did not log in with prod session',
  'did not log into prod session',
  'not sign into production account',
  'not authenticated with production credentials',
  'did not use prod credentials',
  'did not create test user credentials',
  'production account not disabled',
  'not suspended production user',
  'account was not reset in production',
  'user was not suspended in prod',
]) {
  const negatedCredentialAliasIsNonRisk = state('he-verify');
  negatedCredentialAliasIsNonRisk.guardrails.push({
    ...g('credential-check', 'he-verify', 'node scripts/check-credentials.mjs'),
    evidence: [evidence],
  });
  result = run(negatedCredentialAliasIsNonRisk);
  assert.equal(result.status, 0, evidence);
}

const riskyE2eWithDerivedBoundaries = state('he-verify');
riskyE2eWithDerivedBoundaries.guardrails = riskyE2eWithoutPolicyTrigger.guardrails;
riskyE2eWithDerivedBoundaries.approvalBoundaries = [
  { id: 'prod-db-permission', category: 'prod-backend-write', status: 'approved', reason: 'user approved production backend permission mutation', evidence: ['approval quote recorded'] },
  { id: 'prod-db-schema-index', category: 'prod-backend-write', status: 'approved', reason: 'user approved production backend schema index mutation', evidence: ['approval quote recorded'] },
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

const sharedActionProdSideEffectsNeedDistinctBoundaries = state('he-verify');
sharedActionProdSideEffectsNeedDistinctBoundaries.guardrails.push({
  ...g('e2e-side-effects', 'he-verify', 'npx playwright test e2e/checkout.spec.ts'),
  evidence: ['sent production SMS and production email'],
});
sharedActionProdSideEffectsNeedDistinctBoundaries.approvalBoundaries = [
  { id: 'prod-sms-send', category: 'prod-backend-write', status: 'approved', reason: 'user approved production SMS send', evidence: ['approval quote recorded'] },
];
result = run(sharedActionProdSideEffectsNeedDistinctBoundaries);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /approvalBoundaries requires prod-backend-write side effect prod-email/);

const commaSharedActionProdSideEffectsNeedDistinctBoundaries = state('he-verify');
commaSharedActionProdSideEffectsNeedDistinctBoundaries.guardrails.push({
  ...g('e2e-side-effects', 'he-verify', 'npx playwright test e2e/checkout.spec.ts'),
  evidence: ['sent production SMS, production email'],
});
commaSharedActionProdSideEffectsNeedDistinctBoundaries.approvalBoundaries = [
  { id: 'prod-sms-send', category: 'prod-backend-write', status: 'approved', reason: 'user approved production SMS send', evidence: ['approval quote recorded'] },
];
result = run(commaSharedActionProdSideEffectsNeedDistinctBoundaries);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /approvalBoundaries requires prod-backend-write side effect prod-email/);

const commaSharedActionProdSideEffectsApproved = state('he-verify');
commaSharedActionProdSideEffectsApproved.guardrails = commaSharedActionProdSideEffectsNeedDistinctBoundaries.guardrails;
commaSharedActionProdSideEffectsApproved.approvalBoundaries = [
  { id: 'prod-sms-send', category: 'prod-backend-write', status: 'approved', reason: 'user approved production SMS send', evidence: ['approval quote recorded'] },
  { id: 'prod-email-send', category: 'prod-backend-write', status: 'approved', reason: 'user approved production email send', evidence: ['approval quote recorded'] },
];
result = run(commaSharedActionProdSideEffectsApproved);
assert.equal(result.status, 0, result.stderr);

const prefixedCommaSharedActionProdSideEffectsNeedDistinctBoundaries = state('he-verify');
prefixedCommaSharedActionProdSideEffectsNeedDistinctBoundaries.guardrails.push({
  ...g('e2e-side-effects', 'he-verify', 'npx playwright test e2e/checkout.spec.ts'),
  evidence: ['E2E sent production SMS, production email'],
});
prefixedCommaSharedActionProdSideEffectsNeedDistinctBoundaries.approvalBoundaries = [
  { id: 'prod-sms-send', category: 'prod-backend-write', status: 'approved', reason: 'user approved production SMS send', evidence: ['approval quote recorded'] },
];
result = run(prefixedCommaSharedActionProdSideEffectsNeedDistinctBoundaries);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /approvalBoundaries requires prod-backend-write side effect prod-email/);

const prefixedCommaSharedActionProdSideEffectsApproved = state('he-verify');
prefixedCommaSharedActionProdSideEffectsApproved.guardrails = prefixedCommaSharedActionProdSideEffectsNeedDistinctBoundaries.guardrails;
prefixedCommaSharedActionProdSideEffectsApproved.approvalBoundaries = [
  { id: 'prod-sms-send', category: 'prod-backend-write', status: 'approved', reason: 'user approved production SMS send', evidence: ['approval quote recorded'] },
  { id: 'prod-email-send', category: 'prod-backend-write', status: 'approved', reason: 'user approved production email send', evidence: ['approval quote recorded'] },
];
result = run(prefixedCommaSharedActionProdSideEffectsApproved);
assert.equal(result.status, 0, result.stderr);

const commaSharedActionProdLaterSideEffectsNeedDistinctBoundaries = state('he-verify');
commaSharedActionProdLaterSideEffectsNeedDistinctBoundaries.guardrails.push({
  ...g('e2e-side-effects', 'he-verify', 'npx playwright test e2e/checkout.spec.ts'),
  evidence: ['sent production SMS, email in production'],
});
commaSharedActionProdLaterSideEffectsNeedDistinctBoundaries.approvalBoundaries = [
  { id: 'prod-sms-send', category: 'prod-backend-write', status: 'approved', reason: 'user approved production SMS send', evidence: ['approval quote recorded'] },
];
result = run(commaSharedActionProdLaterSideEffectsNeedDistinctBoundaries);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /approvalBoundaries requires prod-backend-write side effect prod-email/);

const commaSharedActionProdLaterSideEffectsApproved = state('he-verify');
commaSharedActionProdLaterSideEffectsApproved.guardrails = commaSharedActionProdLaterSideEffectsNeedDistinctBoundaries.guardrails;
commaSharedActionProdLaterSideEffectsApproved.approvalBoundaries = [
  { id: 'prod-sms-send', category: 'prod-backend-write', status: 'approved', reason: 'user approved production SMS send', evidence: ['approval quote recorded'] },
  { id: 'prod-email-send', category: 'prod-backend-write', status: 'approved', reason: 'user approved email in production send', evidence: ['approval quote recorded'] },
];
result = run(commaSharedActionProdLaterSideEffectsApproved);
assert.equal(result.status, 0, result.stderr);

const prefixedCommaSharedActionProdLaterSideEffectsNeedDistinctBoundaries = state('he-verify');
prefixedCommaSharedActionProdLaterSideEffectsNeedDistinctBoundaries.guardrails.push({
  ...g('e2e-side-effects', 'he-verify', 'npx playwright test e2e/checkout.spec.ts'),
  evidence: ['E2E sent production SMS, email in production'],
});
prefixedCommaSharedActionProdLaterSideEffectsNeedDistinctBoundaries.approvalBoundaries = [
  { id: 'prod-sms-send', category: 'prod-backend-write', status: 'approved', reason: 'user approved production SMS send', evidence: ['approval quote recorded'] },
];
result = run(prefixedCommaSharedActionProdLaterSideEffectsNeedDistinctBoundaries);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /approvalBoundaries requires prod-backend-write side effect prod-email/);

const prefixedCommaSharedActionProdLaterSideEffectsApproved = state('he-verify');
prefixedCommaSharedActionProdLaterSideEffectsApproved.guardrails = prefixedCommaSharedActionProdLaterSideEffectsNeedDistinctBoundaries.guardrails;
prefixedCommaSharedActionProdLaterSideEffectsApproved.approvalBoundaries = [
  { id: 'prod-sms-send', category: 'prod-backend-write', status: 'approved', reason: 'user approved production SMS send', evidence: ['approval quote recorded'] },
  { id: 'prod-email-send', category: 'prod-backend-write', status: 'approved', reason: 'user approved email in production send', evidence: ['approval quote recorded'] },
];
result = run(prefixedCommaSharedActionProdLaterSideEffectsApproved);
assert.equal(result.status, 0, result.stderr);

const leadingSmsBeforePreventionNeedsExactBoundary = state('he-verify');
leadingSmsBeforePreventionNeedsExactBoundary.guardrails.push({
  ...g('e2e-side-effects', 'he-verify', 'npx playwright test e2e/checkout.spec.ts'),
  evidence: ['sent production SMS plus changed scanner to prevent prod writes'],
});
leadingSmsBeforePreventionNeedsExactBoundary.approvalBoundaries = [
  { id: 'prod-backend-write', category: 'prod-backend-write', status: 'approved', reason: 'user approved production backend write', evidence: ['approval quote recorded'] },
];
result = run(leadingSmsBeforePreventionNeedsExactBoundary);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /approvalBoundaries requires prod-backend-write side effect prod-sms/);

const leadingSmsBeforeCodeOnlyNativeNeedsExactBoundary = state('he-verify');
leadingSmsBeforeCodeOnlyNativeNeedsExactBoundary.guardrails.push({
  ...g('e2e-side-effects', 'he-verify', 'npx playwright test e2e/checkout.spec.ts'),
  evidence: ['sent production SMS plus native permission dialog opened test updated'],
});
leadingSmsBeforeCodeOnlyNativeNeedsExactBoundary.approvalBoundaries = [
  { id: 'prod-backend-write', category: 'prod-backend-write', status: 'approved', reason: 'user approved production backend write', evidence: ['approval quote recorded'] },
];
result = run(leadingSmsBeforeCodeOnlyNativeNeedsExactBoundary);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /approvalBoundaries requires prod-backend-write side effect prod-sms/);

const paymentRecordSideEffectNeedsPaymentBoundary = state('he-verify');
paymentRecordSideEffectNeedsPaymentBoundary.guardrails.push({
  ...g('e2e-side-effects', 'he-verify', 'npx playwright test e2e/payment.spec.ts'),
  evidence: ['deleted prod payment record'],
});
paymentRecordSideEffectNeedsPaymentBoundary.approvalBoundaries = [
  { id: 'prod-record', category: 'prod-backend-write', status: 'approved', reason: 'user approved production data record mutation', evidence: ['approval quote recorded'] },
];
result = run(paymentRecordSideEffectNeedsPaymentBoundary);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /approvalBoundaries requires prod-backend-write side effect prod-payment/);

const paymentRecordSideEffectWithPaymentBoundary = state('he-verify');
paymentRecordSideEffectWithPaymentBoundary.guardrails = paymentRecordSideEffectNeedsPaymentBoundary.guardrails;
paymentRecordSideEffectWithPaymentBoundary.approvalBoundaries = [
  { id: 'prod-payment-record', category: 'prod-backend-write', status: 'approved', reason: 'user approved deleting production payment record', evidence: ['approval quote recorded'] },
];
result = run(paymentRecordSideEffectWithPaymentBoundary);
assert.equal(result.status, 0, result.stderr);

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

const requestedThenApprovedBoundarySatisfiesStructuredProof = state('he-verify');
requestedThenApprovedBoundarySatisfiesStructuredProof.guardrails.push({
  ...g('e2e-side-effects', 'he-verify', 'npx playwright test e2e/checkout.spec.ts'),
  evidence: ['sent production SMS'],
});
requestedThenApprovedBoundarySatisfiesStructuredProof.approvalBoundaries = [
  { id: 'prod-sms', category: 'prod-backend-write', sideEffectKey: 'prod-sms', status: 'approved', reason: 'production SMS send approval requested and approved by user', evidence: ['approval quote recorded'] },
];
result = run(requestedThenApprovedBoundarySatisfiesStructuredProof);
assert.equal(result.status, 0, result.stderr);

const distinctProdSideEffectsApproved = state('he-verify');
distinctProdSideEffectsApproved.guardrails = distinctProdSideEffectsNeedDistinctBoundaries.guardrails;
distinctProdSideEffectsApproved.approvalBoundaries = [
  { id: 'prod-db-permission', category: 'prod-backend-write', status: 'approved', reason: 'user approved production Appwrite permission mutation', evidence: ['approval quote recorded'] },
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

const paymentSettingsApprovalDoesNotApproveCharge = state('he-verify');
paymentSettingsApprovalDoesNotApproveCharge.guardrails.push({
  ...g('e2e-side-effects', 'he-verify', 'npx playwright test e2e/checkout.spec.ts'),
  evidence: ['charged prod card'],
});
paymentSettingsApprovalDoesNotApproveCharge.approvalBoundaries = [
  { id: 'prod-payment-settings', category: 'prod-backend-write', status: 'approved', reason: 'user approved production payment settings update', evidence: ['approval quote recorded'] },
];
result = run(paymentSettingsApprovalDoesNotApproveCharge);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /approvalBoundaries requires prod-backend-write side effect prod-payment/);

const structuredPaymentSettingsApprovalDoesNotApproveCharge = state('he-verify');
structuredPaymentSettingsApprovalDoesNotApproveCharge.guardrails.push({
  ...g('e2e-side-effects', 'he-verify', 'npx playwright test e2e/checkout.spec.ts'),
  evidence: ['charged prod card'],
});
structuredPaymentSettingsApprovalDoesNotApproveCharge.approvalBoundaries = [
  { id: 'prod-payment-settings', category: 'prod-backend-write', sideEffectKey: 'prod-payment', status: 'approved', reason: 'user approved production payment settings update', evidence: ['approval quote recorded'] },
];
result = run(structuredPaymentSettingsApprovalDoesNotApproveCharge);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /approvalBoundaries requires prod-backend-write side effect prod-payment/);

const structuredPaymentChargeApprovalSatisfiesCharge = state('he-verify');
structuredPaymentChargeApprovalSatisfiesCharge.guardrails = structuredPaymentSettingsApprovalDoesNotApproveCharge.guardrails;
structuredPaymentChargeApprovalSatisfiesCharge.approvalBoundaries = [
  { id: 'prod-payment-charge', category: 'prod-backend-write', sideEffectKey: 'prod-payment', status: 'approved', reason: 'user approved charged production card', evidence: ['approval quote recorded'] },
];
result = run(structuredPaymentChargeApprovalSatisfiesCharge);
assert.equal(result.status, 0, result.stderr);

const nonProductionBillingApprovalDoesNotApproveCharge = state('he-verify');
nonProductionBillingApprovalDoesNotApproveCharge.guardrails.push({
  ...g('e2e-side-effects', 'he-verify', 'npx playwright test e2e/checkout.spec.ts'),
  evidence: ['charged prod card'],
});
nonProductionBillingApprovalDoesNotApproveCharge.approvalBoundaries = [
  { id: 'billing-settings', category: 'prod-backend-write', status: 'approved', reason: 'user approved billing settings update', evidence: ['approval quote recorded'] },
];
result = run(nonProductionBillingApprovalDoesNotApproveCharge);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /approvalBoundaries requires prod-backend-write side effect prod-payment/);

const emailUpdateApprovalDoesNotApproveEmailSend = state('he-verify');
emailUpdateApprovalDoesNotApproveEmailSend.guardrails.push({
  ...g('e2e-side-effects', 'he-verify', 'npx playwright test e2e/checkout.spec.ts'),
  evidence: ['sent production email'],
});
emailUpdateApprovalDoesNotApproveEmailSend.approvalBoundaries = [
  { id: 'prod-email-update', category: 'prod-backend-write', status: 'approved', reason: 'user approved production user email update', evidence: ['approval quote recorded'] },
];
result = run(emailUpdateApprovalDoesNotApproveEmailSend);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /approvalBoundaries requires prod-backend-write side effect prod-email/);

for (const [evidence, expectedSideEffect] of [
  ['emailed production user', 'prod-email'],
  ['texted production user', 'prod-sms'],
  ['messaged production account', 'prod-sms'],
  ['delivered production SMS', 'prod-sms'],
  ['triggered production email', 'prod-email'],
  ['called production webhook', 'prod-webhook'],
  ['invoked production webhook', 'prod-webhook'],
  ['webhook was fired in production', 'prod-webhook'],
  ['webhook in production was fired', 'prod-webhook'],
  ['sent production notification', 'prod-notification'],
  ['delivered production notification to user', 'prod-notification'],
  ['triggered production notification', 'prod-notification'],
  ['posted production notification to customer', 'prod-notification'],
]) {
  const verbOnlyNotificationNeedsExactApproval = state('he-verify');
  verbOnlyNotificationNeedsExactApproval.guardrails.push({
    ...g('e2e-side-effects', 'he-verify', 'npx playwright test e2e/checkout.spec.ts'),
    evidence: [evidence],
  });
  verbOnlyNotificationNeedsExactApproval.approvalBoundaries = [
    { id: 'prod-backend-write', category: 'prod-backend-write', status: 'approved', reason: 'user approved production backend write', evidence: ['approval quote recorded'] },
  ];
  result = run(verbOnlyNotificationNeedsExactApproval);
  assert.notEqual(result.status, 0, evidence);
  assert.match(result.stderr, new RegExp(`approvalBoundaries requires prod-backend-write side effect ${expectedSideEffect}`));
}

for (const [evidence, expectedSideEffect] of [
  ['database migration was applied in production', 'prod-db-schema'],
  ['database migration was run in production', 'prod-db-schema'],
  ['card was charged in production', 'prod-payment'],
  ['webhook in production was triggered', 'prod-webhook'],
  ['data was shared in production', 'prod-data-sharing'],
  ['account was deleted in production', 'prod-user-account'],
  ['Appwrite schema was modified in production', 'prod-appwrite-schema'],
  ['API key was revoked in production', 'prod-credential'],
  ['token was created in prod', 'prod-credential'],
]) {
  const objectFirstProdLaterNeedsExactApproval = state('he-verify');
  objectFirstProdLaterNeedsExactApproval.guardrails.push({
    ...g('e2e-side-effects', 'he-verify', 'npx playwright test e2e/checkout.spec.ts'),
    evidence: [evidence],
  });
  objectFirstProdLaterNeedsExactApproval.approvalBoundaries = [
    { id: 'prod-backend-write', category: 'prod-backend-write', status: 'approved', reason: 'approved production backend write', evidence: ['approval quote recorded'] },
  ];
  result = run(objectFirstProdLaterNeedsExactApproval);
  assert.notEqual(result.status, 0, evidence);
  assert.match(result.stderr, new RegExp(`approvalBoundaries requires prod-backend-write side effect ${expectedSideEffect}`));
}

for (const evidence of ['sent production notification', 'delivered production notification to user']) {
  const productionNotificationApprovalSatisfiesNotification = state('he-verify');
  productionNotificationApprovalSatisfiesNotification.guardrails.push({
    ...g('e2e-side-effects', 'he-verify', 'npx playwright test e2e/checkout.spec.ts'),
    evidence: [evidence],
  });
  productionNotificationApprovalSatisfiesNotification.approvalBoundaries = [
    { id: 'prod-notification', category: 'prod-backend-write', status: 'approved', reason: `user approved ${evidence}`, evidence: ['approval quote recorded'] },
  ];
  result = run(productionNotificationApprovalSatisfiesNotification);
  assert.equal(result.status, 0, `${evidence}: ${result.stderr}`);
}

const webhookApprovalDoesNotApproveUserInvite = state('he-verify');
webhookApprovalDoesNotApproveUserInvite.guardrails.push({
  ...g('e2e-side-effects', 'he-verify', 'npx playwright test e2e/checkout.spec.ts'),
  evidence: ['invited production user'],
});
webhookApprovalDoesNotApproveUserInvite.approvalBoundaries = [
  { id: 'prod-webhook', category: 'prod-backend-write', status: 'approved', reason: 'user approved triggered production webhook', evidence: ['approval quote recorded'] },
];
result = run(webhookApprovalDoesNotApproveUserInvite);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /approvalBoundaries requires prod-backend-write side effect prod-user-invite/);

const userInviteApprovalSatisfiesUserInvite = state('he-verify');
userInviteApprovalSatisfiesUserInvite.guardrails = webhookApprovalDoesNotApproveUserInvite.guardrails;
userInviteApprovalSatisfiesUserInvite.approvalBoundaries = [
  { id: 'prod-user-invite', category: 'prod-backend-write', status: 'approved', reason: 'user approved invited production user', evidence: ['approval quote recorded'] },
];
result = run(userInviteApprovalSatisfiesUserInvite);
assert.equal(result.status, 0, result.stderr);

const structuredSideEffectKeyApprovesBoundary = state('he-verify');
structuredSideEffectKeyApprovesBoundary.guardrails.push({
  ...g('e2e-side-effects', 'he-verify', 'npx playwright test e2e/checkout.spec.ts'),
  evidence: ['sent production SMS'],
});
structuredSideEffectKeyApprovesBoundary.approvalBoundaries = [
  { id: 'prod-side-effect-approval', category: 'prod-backend-write', sideEffectKey: 'prod-sms', status: 'approved', reason: 'user approved production SMS send', evidence: ['approval quote recorded'] },
];
result = run(structuredSideEffectKeyApprovesBoundary);
assert.equal(result.status, 0, result.stderr);

const structuredSideEffectKeyRejectsMismatchedProof = state('he-verify');
structuredSideEffectKeyRejectsMismatchedProof.guardrails.push({
  ...g('e2e-side-effects', 'he-verify', 'npx playwright test e2e/checkout.spec.ts'),
  evidence: ['sent production SMS'],
});
structuredSideEffectKeyRejectsMismatchedProof.approvalBoundaries = [
  { id: 'prod-side-effect-approval', category: 'prod-backend-write', sideEffectKey: 'prod-sms', status: 'approved', reason: 'user approved production email send', evidence: ['approval quote recorded'] },
];
result = run(structuredSideEffectKeyRejectsMismatchedProof);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /approvalBoundaries requires prod-backend-write side effect prod-sms/);

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

const unstructuredBoundaryRejectsRejectedApprovalEvidence = state('he-verify');
unstructuredBoundaryRejectsRejectedApprovalEvidence.guardrails.push({
  ...g('e2e-side-effects', 'he-verify', 'npx playwright test e2e/checkout.spec.ts'),
  evidence: ['sent production SMS'],
});
unstructuredBoundaryRejectsRejectedApprovalEvidence.approvalBoundaries = [
  { id: 'prod-sms', category: 'prod-backend-write', status: 'approved', reason: 'user approved production SMS send', evidence: ['production SMS approval rejected'] },
];
result = run(unstructuredBoundaryRejectsRejectedApprovalEvidence);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /approvalBoundaries requires prod-backend-write side effect prod-sms/);

const unstructuredBoundaryRejectsGenericDeniedApprovalEvidence = state('he-verify');
unstructuredBoundaryRejectsGenericDeniedApprovalEvidence.guardrails.push({
  ...g('e2e-side-effects', 'he-verify', 'npx playwright test e2e/checkout.spec.ts'),
  evidence: ['sent production SMS'],
});
unstructuredBoundaryRejectsGenericDeniedApprovalEvidence.approvalBoundaries = [
  { id: 'prod-sms', category: 'prod-backend-write', status: 'approved', reason: 'user approved production SMS send', evidence: ['approval denied'] },
];
result = run(unstructuredBoundaryRejectsGenericDeniedApprovalEvidence);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /approvalBoundaries requires prod-backend-write side effect prod-sms/);

const unstructuredBoundaryRejectsNotApprovedEvidence = state('he-verify');
unstructuredBoundaryRejectsNotApprovedEvidence.guardrails.push({
  ...g('e2e-side-effects', 'he-verify', 'npx playwright test e2e/checkout.spec.ts'),
  evidence: ['sent production SMS'],
});
unstructuredBoundaryRejectsNotApprovedEvidence.approvalBoundaries = [
  { id: 'prod-sms', category: 'prod-backend-write', status: 'approved', reason: 'user approved production SMS send', evidence: ['production SMS not approved'] },
];
result = run(unstructuredBoundaryRejectsNotApprovedEvidence);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /approvalBoundaries requires prod-backend-write side effect prod-sms/);

for (const evidence of [
  'production SMS approval revoked',
  'production SMS approval cancelled',
  'production SMS approval withdrawn',
  'production SMS approval expired',
]) {
  const unstructuredBoundaryRejectsRevokedApprovalEvidence = state('he-verify');
  unstructuredBoundaryRejectsRevokedApprovalEvidence.guardrails.push({
    ...g('e2e-side-effects', 'he-verify', 'npx playwright test e2e/checkout.spec.ts'),
    evidence: ['sent production SMS'],
  });
  unstructuredBoundaryRejectsRevokedApprovalEvidence.approvalBoundaries = [
    { id: 'prod-sms', category: 'prod-backend-write', status: 'approved', reason: 'user approved production SMS send', evidence: [evidence] },
  ];
  result = run(unstructuredBoundaryRejectsRevokedApprovalEvidence);
  assert.notEqual(result.status, 0, evidence);
  assert.match(result.stderr, /approvalBoundaries requires prod-backend-write side effect prod-sms/);
}

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
  { id: 'prod-appwrite-permission', category: 'prod-backend-write', status: 'approved', reason: 'user approved production Appwrite permission mutation', evidence: ['approval quote recorded'] },
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

const productionMigrationNeedsSchemaBoundary = state('he-verify');
productionMigrationNeedsSchemaBoundary.guardrails.push({
  ...g('prod-migration', 'he-verify', 'node scripts/run-migration.mjs'),
  evidence: ['applied production database migration'],
});
productionMigrationNeedsSchemaBoundary.approvalBoundaries = [
  { id: 'prod-backend-write', category: 'prod-backend-write', status: 'approved', reason: 'user approved production backend write', evidence: ['approval quote recorded'] },
];
result = run(productionMigrationNeedsSchemaBoundary);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /approvalBoundaries requires prod-backend-write side effect prod-db-schema/);

const productionMigrationSchemaBoundaryApproved = state('he-verify');
productionMigrationSchemaBoundaryApproved.guardrails = productionMigrationNeedsSchemaBoundary.guardrails;
productionMigrationSchemaBoundaryApproved.approvalBoundaries = [
  { id: 'prod-db-migration', category: 'prod-backend-write', status: 'approved', reason: 'user approved production database migration', evidence: ['approval quote recorded'] },
];
result = run(productionMigrationSchemaBoundaryApproved);
assert.equal(result.status, 0, result.stderr);

for (const evidence of [
  'would run production database migration',
  'skipped to avoid running database migration in production',
]) {
  const hypotheticalMigrationRunDoesNotNeedApproval = state('he-verify');
  hypotheticalMigrationRunDoesNotNeedApproval.guardrails.push({
    ...g('prod-migration', 'he-verify', 'node scripts/run-migration.mjs'),
    evidence: [evidence],
  });
  result = run(hypotheticalMigrationRunDoesNotNeedApproval);
  assert.equal(result.status, 0, evidence);
}

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

const logConfirmationDoesNotApproveSideEffect = state('he-verify');
logConfirmationDoesNotApproveSideEffect.guardrails.push({
  ...g('e2e-side-effects', 'he-verify', 'npx playwright test e2e/checkout.spec.ts'),
  evidence: ['sent production SMS'],
});
logConfirmationDoesNotApproveSideEffect.approvalBoundaries = [
  { id: 'prod-sms', category: 'prod-backend-write', status: 'approved', reason: 'production SMS sent confirmed by logs', evidence: ['log confirmation recorded'] },
];
result = run(logConfirmationDoesNotApproveSideEffect);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /approvalBoundaries requires prod-backend-write side effect prod-sms/);

for (const reason of [
  'production SMS approved by logs',
  'production SMS authorized by logs',
  'production SMS authorised by logs',
  'production SMS okayed by logs',
  'production SMS signed off by logs',
  'production SMS confirmed by logs',
  'production SMS allowed by logs',
]) {
  const logApprovalTermDoesNotApproveStructuredSideEffect = state('he-verify');
  logApprovalTermDoesNotApproveStructuredSideEffect.guardrails.push({
    ...g('e2e-side-effects', 'he-verify', 'npx playwright test e2e/checkout.spec.ts'),
    evidence: ['sent production SMS'],
  });
  logApprovalTermDoesNotApproveStructuredSideEffect.approvalBoundaries = [
    { id: 'prod-sms', category: 'prod-backend-write', sideEffectKey: 'prod-sms', status: 'approved', reason, evidence: ['log record'] },
  ];
  result = run(logApprovalTermDoesNotApproveStructuredSideEffect);
  assert.notEqual(result.status, 0, reason);
  assert.match(result.stderr, /approvalBoundaries requires prod-backend-write side effect prod-sms/);
}

for (const decisionTerm of ['approved', 'authorized', 'authorised', 'okayed', 'signed off', 'confirmed', 'allowed']) {
  const negatedApprovalDecisionDoesNotNegateExecutedWrite = state('he-verify');
  negatedApprovalDecisionDoesNotNegateExecutedWrite.guardrails.push({
    ...g('prod-backend-write', 'he-verify', 'node scripts/check-prod-write.mjs'),
    evidence: [`not ${decisionTerm} production backend write was executed`],
  });
  negatedApprovalDecisionDoesNotNegateExecutedWrite.approvalBoundaries = [];
  result = run(negatedApprovalDecisionDoesNotNegateExecutedWrite);
  assert.notEqual(result.status, 0, decisionTerm);
  assert.match(result.stderr, /approvalBoundaries requires prod-backend-write/);
}

const userConfirmationApprovesSideEffect = state('he-verify');
userConfirmationApprovesSideEffect.guardrails = logConfirmationDoesNotApproveSideEffect.guardrails;
userConfirmationApprovesSideEffect.approvalBoundaries = [
  { id: 'prod-sms', category: 'prod-backend-write', sideEffectKey: 'prod-sms', status: 'approved', reason: 'production SMS send approval confirmed by user', evidence: ['approval quote recorded'] },
];
result = run(userConfirmationApprovesSideEffect);
assert.equal(result.status, 0, result.stderr);

for (const reason of [
  'production SMS send approval granted',
  'production SMS send approval granted by logs',
  'production SMS send granted approval by logs',
  'production SMS send authorization granted by status',
  'production SMS send granted authorization from status',
  'production SMS send authorisation granted by logs',
  'production SMS send granted authorisation by logs',
  'production SMS send consent granted by logs',
  'production SMS send granted consent by logs',
  'production SMS send permission granted by logs',
  'production SMS send granted permission by logs',
  'production SMS send explicit approval granted by logs',
  'explicit approval granted for production SMS send',
  'explicit permission granted for production SMS send',
]) {
  const nonHumanGrantPhraseDoesNotApproveSideEffect = state('he-verify');
  nonHumanGrantPhraseDoesNotApproveSideEffect.guardrails = logConfirmationDoesNotApproveSideEffect.guardrails;
  nonHumanGrantPhraseDoesNotApproveSideEffect.approvalBoundaries = [
    { id: 'prod-sms', category: 'prod-backend-write', sideEffectKey: 'prod-sms', status: 'approved', reason, evidence: ['approval quote recorded'] },
  ];
  result = run(nonHumanGrantPhraseDoesNotApproveSideEffect);
  assert.notEqual(result.status, 0, reason);
  assert.match(result.stderr, /approvalBoundaries requires prod-backend-write side effect prod-sms/);
}

for (const reason of [
  'production SMS send approval granted by user',
  'production SMS send granted approval from operator',
  'user granted approval for production SMS send',
  'operator granted authorization for production SMS send',
  'maintainer granted authorisation for production SMS send',
  'manual consent granted for production SMS send',
  'requester permission granted for production SMS send',
]) {
  const humanGrantPhraseApprovesSideEffect = state('he-verify');
  humanGrantPhraseApprovesSideEffect.guardrails = logConfirmationDoesNotApproveSideEffect.guardrails;
  humanGrantPhraseApprovesSideEffect.approvalBoundaries = [
    { id: 'prod-sms', category: 'prod-backend-write', sideEffectKey: 'prod-sms', status: 'approved', reason, evidence: ['approval quote recorded'] },
  ];
  result = run(humanGrantPhraseApprovesSideEffect);
  assert.equal(result.status, 0, `${reason}: ${result.stderr}`);
}

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

const productionCredentialWriteNeedsCredentialBoundary = state('he-verify');
productionCredentialWriteNeedsCredentialBoundary.guardrails.push({
  ...g('prod-credential-write', 'he-verify', 'node scripts/check-prod-credential.mjs'),
  evidence: ['created production API key'],
});
productionCredentialWriteNeedsCredentialBoundary.approvalBoundaries = [
  { id: 'prod-backend-write', category: 'prod-backend-write', status: 'approved', reason: 'user approved production backend write', evidence: ['approval quote recorded'] },
];
result = run(productionCredentialWriteNeedsCredentialBoundary);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /approvalBoundaries requires prod-backend-write side effect prod-credential/);

const productionCredentialWriteBoundaryApproved = state('he-verify');
productionCredentialWriteBoundaryApproved.guardrails = productionCredentialWriteNeedsCredentialBoundary.guardrails;
productionCredentialWriteBoundaryApproved.approvalBoundaries = [
  { id: 'prod-credential-write', category: 'prod-backend-write', status: 'approved', reason: 'user approved creating production API key', evidence: ['approval quote recorded'] },
];
result = run(productionCredentialWriteBoundaryApproved);
assert.equal(result.status, 0, result.stderr);

const approvedBoundaries = state('he-verify');
approvedBoundaries.e2ePolicy = { requiredApprovalBoundaries: ['prod-backend-write', 'native-permission', 'generated-credentials'] };
approvedBoundaries.approvalBoundaries = [
  { id: 'prod-db-permission', category: 'prod-backend-write', status: 'approved', reason: 'user approved production Appwrite permission mutation', evidence: ['approval quote recorded'] },
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
  { id: 'prod-side-effect-approval', category: 'prod-backend-write', sideEffectKey: 'prod-sms', status: 'approved', reason: 'user approved production SMS send', evidence: ['approval quote recorded'] },
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
  'deleted ticket recorded',
  'deletion ticket recorded',
  'removal scheduled',
  'deleted ticket for generated user',
  'deleted cleanup record for generated user',
  'deleted audit log for generated user',
  'purged generated user audit logs',
  'deleted user account',
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

const generatedCredentialDetachedCleanupProof = state('he-verify');
generatedCredentialDetachedCleanupProof.e2ePolicy = { requiredApprovalBoundaries: ['generated-credentials'] };
generatedCredentialDetachedCleanupProof.approvalBoundaries = [
  { id: 'generated-user', category: 'generated-credentials', status: 'approved', reason: 'user approved generated test user', evidence: ['created test user'], redactedCredentialRef: 'user: he-e2e-***@example.test', dataScope: 'seeded-test user only', cleanupProof: ['generated user cleanup target recorded', 'deleted ticket recorded'] },
];
result = run(generatedCredentialDetachedCleanupProof);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /cleanupProof must include positive cleanup result/);

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

for (const status of ['fixed', 'accepted']) {
  const repeatedMissLearnComplete = state('he-learn');
  repeatedMissLearnComplete.repeatMisses = [
    { issueClass: 'auth', evidence: ['user caught auth owner miss'] },
    { issueClass: 'auth', evidence: ['user caught auth proof miss'] },
  ];
  repeatedMissLearnComplete.findings = [{
    id: `learn-auth-workflow-${status}`,
    stage: 'he-ship',
    summary: 'auth repeated and durable guard captured',
    ownerStage: 'he-learn',
    repairType: 'learning',
    issueClass: 'auth',
    ownerProof: ['tests/he-state-compliance.test.mjs'],
    artifacts: [],
    status,
  }];
  result = run(repeatedMissLearnComplete);
  assert.equal(result.status, 0, result.stderr);
}

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
