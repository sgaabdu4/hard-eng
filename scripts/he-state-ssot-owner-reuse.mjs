function isObject(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

function hasText(value) {
  return typeof value === 'string' && value.trim().length > 0;
}

function stringValues(value) {
  if (typeof value === 'string') return [value];
  if (Array.isArray(value)) return value.flatMap(stringValues);
  if (isObject(value)) return Object.values(value).flatMap(stringValues);
  return [];
}

function stringArray(value) {
  return Array.isArray(value) && value.every((item) => typeof item === 'string');
}

function lastDoneReceipt(steps) {
  const receipts = Array.isArray(steps)
    ? steps.filter((step) => step?.status === 'done' && isObject(step.receipt)).map((step) => step.receipt)
    : [];
  return receipts[receipts.length - 1] || null;
}

const ownerDecisions = new Set([
  'reuse',
  'extend existing owner',
  'create feature-local owner',
  'create shared owner',
  'not applicable',
]);

const ownerClassAliases = new Map([
  ['components', ['component']],
  ['widgets', ['widget']],
  ['screens', ['screen']],
  ['rows', ['row']],
  ['cards', ['card']],
  ['forms', ['form']],
  ['pickers', ['picker']],
  ['tabs', ['tab']],
  ['settings', ['setting']],
  ['styles', ['style']],
  ['styling', ['style']],
  ['css', ['style']],
  ['scss', ['style']],
  ['sass', ['style']],
  ['less', ['style']],
]);

const ssotOwnerClassTokens = new Set([
  'workflow',
  'state',
  'ui',
  'component',
  'widget',
  'screen',
  'list',
  'row',
  'card',
  'modal',
  'form',
  'picker',
  'tab',
  'navigation',
  'cta',
  'empty',
  'loading',
  'error',
  'calendar',
  'date',
  'grid',
  'month',
  'select',
  'checkbox',
  'toggle',
  'selectable',
  'chip',
  'setting',
  'answer',
  'alert',
  'control',
  'button',
  'input',
  'label',
  'drag',
  'drop',
  'search',
  'filter',
  'pagination',
  'upload',
  'stepper',
  'api',
  'schema',
  'repository',
  'query',
  'cache',
  'backend',
  'permission',
  'constant',
  'fixture',
  'helper',
  'design',
  'token',
  'theme',
  'typography',
  'spacing',
  'color',
  'style',
  'radius',
  'motion',
  'time',
  'currency',
  'number',
  'formatting',
]);

function normalizeDecision(value) {
  return typeof value === 'string' ? value.trim().toLowerCase().replace(/\s+/g, ' ') : '';
}

function tokenVariants(token) {
  const variants = [token];
  if (token.endsWith('ies') && token.length > 4) variants.push(`${token.slice(0, -3)}y`);
  if (token.endsWith('s') && !token.endsWith('ss') && token.length > 3) variants.push(token.slice(0, -1));
  const aliases = ownerClassAliases.get(token);
  if (aliases) variants.push(...aliases);
  return variants;
}

function normalizedTokens(value) {
  if (!hasText(value)) return new Set();
  const tokens = new Set();
  const text = value.replace(/([a-z0-9])([A-Z])/g, '$1 $2').toLowerCase();
  for (const token of text.split(/[^a-z0-9]+/).filter(Boolean)) {
    for (const variant of tokenVariants(token)) tokens.add(variant);
  }
  return tokens;
}

function requiredOwnerClasses(state) {
  const touchedStacks = state.guardrailInventory?.touchedStacks;
  if (!Array.isArray(touchedStacks) || !touchedStacks.every(hasText)) return [];
  const required = new Set();
  for (const stack of touchedStacks) {
    for (const token of normalizedTokens(stack)) {
      if (ssotOwnerClassTokens.has(token)) required.add(token);
    }
  }
  return Array.from(required);
}

function missingOwnerClassCoverage(state, ledgerEntries) {
  const required = requiredOwnerClasses(state);
  if (required.length === 0) return [];
  const covered = new Set();
  for (const entry of ledgerEntries) {
    const ownerClassTokens = normalizedTokens(entry?.ownerClass);
    for (const requiredClass of required) {
      if (ownerClassTokens.has(requiredClass)) covered.add(requiredClass);
    }
  }
  return required.filter((ownerClass) => !covered.has(ownerClass));
}

function ledgerSources(subStage, receipt) {
  return [
    ['subStages.ssot-owner-reuse.ownerLedger', subStage?.ownerLedger],
    ['subStages.ssot-owner-reuse.ssotOwnerReuse.ownerLedger', subStage?.ssotOwnerReuse?.ownerLedger],
    ['receipt.ssotOwnerReuse.ownerLedger', receipt?.ssotOwnerReuse?.ownerLedger],
  ].filter(([, ledger]) => ledger !== undefined);
}

function validateLedger(source, ledger, errors) {
  if (!Array.isArray(ledger)) {
    errors.push(`${source} must be an array`);
    return false;
  }
  if (ledger.length === 0) {
    errors.push(`${source} must be non-empty`);
    return false;
  }
  let valid = true;
  for (const [index, entry] of ledger.entries()) {
    if (!isObject(entry)) {
      errors.push(`${source}[${index}] must be an object`);
      valid = false;
      continue;
    }
    if (!hasText(entry.ownerClass)) {
      errors.push(`${source}[${index}].ownerClass is required`);
      valid = false;
    }
    const decision = normalizeDecision(entry.decision);
    if (!ownerDecisions.has(decision)) {
      errors.push(`${source}[${index}].decision must be reuse, extend existing owner, create feature-local owner, create shared owner, or not applicable`);
      valid = false;
    }
    if (decision && decision !== 'not applicable' && !hasText(entry.owner)) {
      errors.push(`${source}[${index}].owner is required for ${decision}`);
      valid = false;
    }
    if (!stringArray(entry.evidence) || entry.evidence.length === 0 || !entry.evidence.every(hasText)) {
      errors.push(`${source}[${index}].evidence must be non-empty string[]`);
      valid = false;
    }
  }
  return valid;
}

export function validateSsotOwnerReuse(state, errors) {
  if (state.stage !== 'he-implement' || state.next?.ready !== true) return;
  const subStage = Array.isArray(state.subStages)
    ? state.subStages.find((item) => item?.id === 'ssot-owner-reuse')
    : null;
  const receipt = lastDoneReceipt(state.steps);
  const evidence = [
    ...stringValues(subStage?.evidence),
    ...stringValues(receipt),
  ].filter(hasText).join(' ');
  const hasSummary = /\bSSOT reused\b/i.test(evidence)
    || /\bSSOT extended\b/i.test(evidence)
    || /\bnew[- ]owners? (?:created|summary|recorded)\b/i.test(evidence)
    || /\bcreated (?:feature[- ]local|shared|new) owners?\b/i.test(evidence);
  const sources = ledgerSources(subStage, receipt);
  let hasLedger = false;
  const validLedgerEntries = [];
  for (const [source, ledger] of sources) {
    if (validateLedger(source, ledger, errors)) {
      hasLedger = true;
      validLedgerEntries.push(...ledger);
    }
  }
  if (!hasLedger) {
    errors.push('he-implement ready handoff requires ssot-owner-reuse ledger decisions with ownerClass, decision, owner, and evidence');
    return;
  }
  const missingCoverage = missingOwnerClassCoverage(state, validLedgerEntries);
  if (missingCoverage.length > 0) {
    errors.push(`he-implement ready handoff requires ssot-owner-reuse ownerLedger coverage for touched owner classes: ${missingCoverage.join(', ')}`);
  }
  if (!hasSummary) {
    errors.push('he-implement ready handoff requires ssot-owner-reuse evidence or final receipt to summarize SSOT reused, SSOT extended, or new owners created');
  }
}
