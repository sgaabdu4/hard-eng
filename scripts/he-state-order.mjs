import { matchesImplementationProofGuardrail, matchesTestFirstProofGuardrail } from './he-state-proof.mjs';

function entryById(items, id) {
  const index = Array.isArray(items) ? items.findIndex((item) => item?.id === id) : -1;
  return index === -1 ? null : { index, item: items[index] };
}

function passedEntriesByMatcher(items, matcher, options = {}) {
  if (!Array.isArray(items)) return [];
  return items
    .map((item, index) => ({ index, item }))
    .filter((entry) => entry.item?.status === 'passed' && matcher(entry.item, options));
}

function passedEntriesById(items, id) {
  if (!Array.isArray(items)) return [];
  return items
    .map((item, index) => ({ index, item }))
    .filter((entry) => entry.item?.id === id && entry.item?.status === 'passed');
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

export function validateImplementOrder(state, errors, options = {}) {
  if (state.stage !== 'he-implement' || state.next?.ready !== true) return;
  const testFirst = entryById(state.subStages, 'test-first');
  const ownerChange = entryById(state.subStages, 'owner-change');
  const testProof = passedEntriesByMatcher(state.guardrails, matchesTestFirstProofGuardrail, options);
  const implementationProof = passedEntriesByMatcher(state.guardrails, matchesImplementationProofGuardrail, options);
  const testFirstSeq = sequence(testFirst, `subStages[${testFirst?.index}]`, errors);
  const ownerChangeSeq = sequence(ownerChange, `subStages[${ownerChange?.index}]`, errors);
  const testProofSeqs = sequences(testProof, errors);
  const implementationProofSeqs = sequences(implementationProof, errors);
  if (testFirstSeq !== null && ownerChangeSeq !== null && testFirstSeq >= ownerChangeSeq) errors.push('he-implement ready handoff requires test-first before owner-change');
  if (testProofSeqs.length && ownerChangeSeq !== null && !testProofSeqs.some((value) => value < ownerChangeSeq)) errors.push('he-implement ready handoff requires test-first-proof before owner-change');
  if (implementationProofSeqs.length && ownerChangeSeq !== null && !implementationProofSeqs.some((value) => value > ownerChangeSeq)) errors.push('he-implement ready handoff requires implementation-proof after owner-change');
}

export function validateShipOrder(state, errors) {
  if (state.stage !== 'he-ship' || state.next?.ready !== true) return;
  const noMistakesSeqs = sequences(passedEntriesById(state.guardrails, 'no-mistakes'), errors);
  const prEvidenceSeqs = sequences(passedEntriesById(state.guardrails, 'pr-evidence'), errors);
  const reviewThreadSeqs = sequences(passedEntriesById(state.guardrails, 'pr-review-threads'), errors);
  const ciSeqs = sequences(passedEntriesById(state.guardrails, 'ci-or-skip'), errors);
  if (!noMistakesSeqs.length || !prEvidenceSeqs.length || !reviewThreadSeqs.length || !ciSeqs.length) return;

  const latestNoMistakes = Math.max(...noMistakesSeqs);
  const currentEvidenceSeqs = prEvidenceSeqs.filter((value) => value > latestNoMistakes);
  if (!currentEvidenceSeqs.length) {
    errors.push('he-ship ready handoff requires pr-evidence after latest no-mistakes');
    return;
  }

  const latestEvidence = Math.max(...currentEvidenceSeqs);
  const currentReviewThreadSeqs = reviewThreadSeqs.filter((value) => value > latestEvidence);
  if (!currentReviewThreadSeqs.length) {
    errors.push('he-ship ready handoff requires pr-review-threads after current pr-evidence');
    return;
  }

  const latestReviewThreads = Math.max(...currentReviewThreadSeqs);
  if (!ciSeqs.some((value) => value > latestReviewThreads)) {
    errors.push('he-ship ready handoff requires ci-or-skip after current pr-review-threads');
  }
}
