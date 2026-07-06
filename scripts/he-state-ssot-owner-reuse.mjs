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
  ['ux', ['ui']],
  ['widgets', ['widget']],
  ['screens', ['screen']],
  ['routes', ['screen']],
  ['rows', ['row']],
  ['cards', ['card']],
  ['forms', ['form']],
  ['pickers', ['picker']],
  ['tabs', ['tab']],
  ['nav', ['navigation']],
  ['menus', ['menu']],
  ['dialogs', ['modal']],
  ['dropdowns', ['select']],
  ['settings', ['setting']],
  ['styles', ['style']],
  ['styling', ['style']],
  ['css', ['style']],
  ['scss', ['style']],
  ['sass', ['style']],
  ['less', ['style']],
  ['react', ['ui', 'component']],
  ['next', ['ui', 'screen']],
  ['nextjs', ['next', 'ui', 'screen']],
  ['tsx', ['ui', 'component']],
  ['jsx', ['ui', 'component']],
  ['page', ['screen']],
  ['route', ['screen']],
  ['storybook', ['ui', 'component']],
  ['widgetbook', ['ui', 'widget']],
  ['sql', ['schema', 'backend']],
  ['migration', ['schema', 'backend']],
  ['openapi', ['api', 'schema', 'backend']],
  ['graphql', ['api', 'schema', 'backend']],
  ['gql', ['api', 'schema', 'backend']],
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
  'menu',
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
  const baseVariants = [token];
  if (token.endsWith('ies') && token.length > 4) baseVariants.push(`${token.slice(0, -3)}y`);
  if (token.endsWith('s') && !token.endsWith('ss') && token.length > 3) baseVariants.push(token.slice(0, -1));
  const variants = new Set(baseVariants);
  for (const variant of baseVariants) {
    const aliases = ownerClassAliases.get(variant);
    if (aliases) aliases.forEach((alias) => variants.add(alias));
  }
  return Array.from(variants);
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

const uiTouchedOwnerClassTokens = new Set([
  'ui',
  'component',
  'widget',
  'screen',
  'list',
  'card',
  'modal',
  'form',
  'picker',
  'tab',
  'navigation',
  'menu',
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
  'design',
  'token',
  'theme',
  'typography',
  'spacing',
  'color',
  'style',
  'radius',
  'motion',
  'formatting',
]);

const rowUiQualifierTokens = new Set([
  'ui',
  'component',
  'widget',
  'screen',
  'list',
  'card',
  'modal',
  'form',
  'grid',
  'view',
  'panel',
  'layout',
  'page',
]);

function normalizedOwnerClassText(value) {
  return String(value || '').replace(/([a-z0-9])([A-Z])/g, '$1 $2').toLowerCase();
}

function hasUiTouchedRowContext(value, tokens) {
  if (!tokens.has('row')) return false;
  for (const token of rowUiQualifierTokens) {
    if (tokens.has(token)) return true;
  }
  const text = normalizedOwnerClassText(value);
  if (/\b(?:ui|interface|visible|user[-\s]+visible|user[-\s]+facing|frontend|front[-\s]+end)\b/i.test(text)) return true;
  if (!/\b(?:table\s+rows?|rows?\s+table)\b/i.test(text)) return false;
  return !/\b(?:appwrite|database|databases|db|sql|schema|migration|migrations|record|records|tables\s*db|tablesdb)\b/i.test(text);
}

export function hasUiTouchedOwnerClass(value) {
  const tokens = normalizedTokens(value);
  for (const token of tokens) {
    if (uiTouchedOwnerClassTokens.has(token)) return true;
  }
  return hasUiTouchedRowContext(value, tokens);
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

function summaryEvidenceValues(subStage, receipt) {
  return [
    ...stringValues(subStage?.evidence),
    ...stringValues(subStage?.ssotOwnerReuse?.summary),
    ...stringValues(subStage?.ssotOwnerReuse?.evidence),
    ...stringValues(receipt?.ownerProof),
    ...stringValues(receipt?.ssotOwnerReuse?.summary),
    ...stringValues(receipt?.ssotOwnerReuse?.evidence),
    ...stringValues(receipt?.ssotOwnerReuse?.ssotReused),
    ...stringValues(receipt?.ssotOwnerReuse?.ssotExtended),
    ...stringValues(receipt?.ssotOwnerReuse?.newOwnersCreated),
  ];
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
  const evidence = summaryEvidenceValues(subStage, receipt).filter(hasText).join(' ');
  const requiredSummaryLabels = [
    ['SSOT reused', /\bSSOT reused\b/i],
    ['SSOT extended', /\bSSOT extended\b/i],
    ['new owners created', /\bnew[- ]owners? (?:created|summary|recorded)\b|\bcreated (?:feature[- ]local|shared|new) owners?\b/i],
  ];
  const missingSummaryLabels = requiredSummaryLabels
    .filter(([, pattern]) => !pattern.test(evidence))
    .map(([label]) => label);
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
  if (missingSummaryLabels.length > 0) {
    errors.push(`he-implement ready handoff requires ssot-owner-reuse evidence or final receipt to summarize SSOT reused, SSOT extended, and new owners created; missing: ${missingSummaryLabels.join(', ')}`);
  }
}
