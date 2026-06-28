function entryById(items, id) {
  const index = Array.isArray(items) ? items.findIndex((item) => item?.id === id) : -1;
  return index === -1 ? null : { index, item: items[index] };
}

function sequence(entry, pointer, errors) {
  if (!entry) return null;
  const value = entry.item?.sequence;
  if (!Number.isInteger(value) || value < 1) {
    errors.push(`${pointer}.sequence must be a positive integer before ready handoff`);
    return null;
  }
  return value;
}

export function validateImplementOrder(state, errors) {
  if (state.stage !== 'he-implement' || state.next?.ready !== true) return;
  const testFirst = entryById(state.subStages, 'test-first');
  const ownerChange = entryById(state.subStages, 'owner-change');
  const testProof = entryById(state.guardrails, 'test-first-proof');
  const implementationProof = entryById(state.guardrails, 'implementation-proof');
  const testFirstSeq = sequence(testFirst, `subStages[${testFirst?.index}]`, errors);
  const ownerChangeSeq = sequence(ownerChange, `subStages[${ownerChange?.index}]`, errors);
  const testProofSeq = sequence(testProof, `guardrails[${testProof?.index}]`, errors);
  const implementationProofSeq = sequence(implementationProof, `guardrails[${implementationProof?.index}]`, errors);
  if (testFirstSeq !== null && ownerChangeSeq !== null && testFirstSeq >= ownerChangeSeq) errors.push('he-implement ready handoff requires test-first before owner-change');
  if (testProofSeq !== null && ownerChangeSeq !== null && testProofSeq >= ownerChangeSeq) errors.push('he-implement ready handoff requires test-first-proof before owner-change');
  if (implementationProofSeq !== null && ownerChangeSeq !== null && implementationProofSeq <= ownerChangeSeq) errors.push('he-implement ready handoff requires implementation-proof after owner-change');
}
