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

function lastDoneReceipt(steps) {
  const receipts = Array.isArray(steps)
    ? steps.filter((step) => step?.status === 'done' && isObject(step.receipt)).map((step) => step.receipt)
    : [];
  return receipts[receipts.length - 1] || null;
}

export function validateSsotOwnerReuse(state, errors) {
  if (state.stage !== 'he-implement' || state.next?.ready !== true) return;
  const subStage = Array.isArray(state.subStages)
    ? state.subStages.find((item) => item?.id === 'ssot-owner-reuse')
    : null;
  const evidence = [
    ...stringValues(subStage?.evidence),
    ...stringValues(lastDoneReceipt(state.steps)),
  ].filter(hasText).join(' ');
  const hasSummary = /\bSSOT reused\b/i.test(evidence)
    || /\bSSOT extended\b/i.test(evidence)
    || /\bnew[- ]owners? (?:created|summary|recorded)\b/i.test(evidence)
    || /\bcreated (?:feature[- ]local|shared|new) owners?\b/i.test(evidence);
  if (!hasSummary) {
    errors.push('he-implement ready handoff requires ssot-owner-reuse evidence or final receipt to summarize SSOT reused, SSOT extended, or new owners created');
  }
}
