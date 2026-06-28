import { matchesImplementationProofGuardrail, matchesTestFirstProofGuardrail } from './he-state-proof.mjs';

function entryById(items, id) {
  const index = Array.isArray(items) ? items.findIndex((item) => item?.id === id) : -1;
  return index === -1 ? null : { index, item: items[index] };
}

function passedEntriesByMatcher(items, matcher) {
  if (!Array.isArray(items)) return [];
  return items
    .map((item, index) => ({ index, item }))
    .filter((entry) => entry.item?.status === 'passed' && matcher(entry.item));
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

function sequences(entries, errors) {
  return entries
    .map((entry) => sequence(entry, `guardrails[${entry.index}]`, errors))
    .filter((value) => value !== null);
}

export function validateImplementOrder(state, errors) {
  if (state.stage !== 'he-implement' || state.next?.ready !== true) return;
  const testFirst = entryById(state.subStages, 'test-first');
  const ownerChange = entryById(state.subStages, 'owner-change');
  const testProof = passedEntriesByMatcher(state.guardrails, matchesTestFirstProofGuardrail);
  const implementationProof = passedEntriesByMatcher(state.guardrails, matchesImplementationProofGuardrail);
  const testFirstSeq = sequence(testFirst, `subStages[${testFirst?.index}]`, errors);
  const ownerChangeSeq = sequence(ownerChange, `subStages[${ownerChange?.index}]`, errors);
  const testProofSeqs = sequences(testProof, errors);
  const implementationProofSeqs = sequences(implementationProof, errors);
  if (testFirstSeq !== null && ownerChangeSeq !== null && testFirstSeq >= ownerChangeSeq) errors.push('he-implement ready handoff requires test-first before owner-change');
  if (testProofSeqs.length && ownerChangeSeq !== null && !testProofSeqs.some((value) => value < ownerChangeSeq)) errors.push('he-implement ready handoff requires test-first-proof before owner-change');
  if (implementationProofSeqs.length && ownerChangeSeq !== null && !implementationProofSeqs.some((value) => value > ownerChangeSeq)) errors.push('he-implement ready handoff requires implementation-proof after owner-change');
}
