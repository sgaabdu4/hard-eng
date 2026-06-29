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

function normalizeDecision(value) {
  return typeof value === 'string' ? value.trim().toLowerCase().replace(/\s+/g, ' ') : '';
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
  for (const [source, ledger] of sources) {
    if (validateLedger(source, ledger, errors)) hasLedger = true;
  }
  if (!hasLedger) {
    errors.push('he-implement ready handoff requires ssot-owner-reuse ledger decisions with ownerClass, decision, owner, and evidence');
    return;
  }
  if (!hasSummary) {
    errors.push('he-implement ready handoff requires ssot-owner-reuse evidence or final receipt to summarize SSOT reused, SSOT extended, or new owners created');
  }
}
