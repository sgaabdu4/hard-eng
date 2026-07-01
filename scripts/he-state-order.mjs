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

function evidenceText(entry) {
  return Array.isArray(entry?.item?.evidence) ? entry.item.evidence.join(' ') : '';
}

function stripShellComments(command) {
  const text = String(command || '');
  let output = '';
  let quote = null;
  let escaped = false;
  for (let index = 0; index < text.length; index += 1) {
    const char = text[index];
    if (quote === "'") {
      output += char;
      if (char === "'") quote = null;
      continue;
    }
    if (escaped) {
      output += char;
      escaped = false;
      continue;
    }
    if (char === '\\') {
      output += char;
      escaped = true;
      continue;
    }
    if (quote === '"') {
      output += char;
      if (char === '"') quote = null;
      continue;
    }
    if (char === "'" || char === '"') {
      output += char;
      quote = char;
      continue;
    }
    const previous = output[output.length - 1] || '';
    if (char === '#' && (!previous || /\s|[;&|()]/.test(previous))) {
      while (index < text.length && text[index] !== '\n') index += 1;
      if (index < text.length) output += '\n';
      continue;
    }
    output += char;
  }
  return output;
}

function commandSegments(command) {
  return stripShellComments(command)
    .split(/\s*(?:&&|;|\n)\s*/)
    .map((segment) => segment.replace(/\s+/g, ' ').trim())
    .filter(Boolean);
}

function hasShipCurrentnessCommand(entry) {
  const segments = commandSegments(entry?.item?.command);
  const headIndex = segments.findIndex((segment) => /^git\s+rev-parse\s+HEAD(?:\s|$)/.test(segment));
  return headIndex !== -1 && segments.slice(headIndex + 1).some((segment) => /^git\s+status\s+--short(?:\s|$)/.test(segment));
}

function extractCurrentHead(text) {
  return text.match(/Current head:\s*`?([0-9a-f]{7,40})`?/i)?.[1] || null;
}

function extractValidatedHead(text) {
  return text.match(/(?:validated|current)\s+head:\s*`?([0-9a-f]{7,40})`?/i)?.[1] || null;
}

function isAffirmedNoDirtyClause(clause) {
  return /\b(?:no|zero|without)\b/i.test(clause) &&
    /\b(?:staged|unstaged|untracked|modified)\b/i.test(clause) &&
    !/\b(?:but|except|however|pending|found|detected|present|remaining)\b/i.test(clause);
}

function stripAffirmedNoDirtyClauses(text) {
  return String(text || '')
    .split(/([.;\n]+)/)
    .map((part) => (isAffirmedNoDirtyClause(part) ? '' : part))
    .join('');
}

function hasDirtyShortStatusOutput(text) {
  return String(text || '')
    .split(/[.;\n]+/)
    .some((clause) => {
      const marker = clause.search(/\bgit status --short\b/i);
      if (marker === -1) return false;
      const output = clause.slice(marker).replace(/\bgit status --short\b/i, '');
      return /(?:^|:|\s)\s*(?:\?\?|[MADRCU]{1,2})\s+\S/.test(output);
    });
}

function hasCleanWorktreeEvidence(text) {
  const dirtyText = stripAffirmedNoDirtyClauses(text);
  if (/\b(?:not[- ]?clean|not\s+unchanged|unclean|dirty|changes?\s+pending)\b/i.test(dirtyText)) return false;
  if (/\b(?:modified|untracked|unstaged|staged)\s+(?:files?|changes?)\b/i.test(dirtyText)) return false;
  if (/\b(?:files?|changes?)\s+(?:modified|untracked|unstaged|staged)\b/i.test(dirtyText)) return false;
  if (/\bgit status --short\b[^.;\n]*\b(?:modified|untracked|unstaged|staged)\b/i.test(dirtyText)) return false;
  if (hasDirtyShortStatusOutput(text)) return false;
  if (/\b(?:clean|unchanged)\b\s*(?:[:=?]|is|was)\s*(?:false|no)\b/i.test(text)) return false;
  if (/\b(?:worktree|working tree|git status --short)\b[^.;\n]*\b(?:clean|unchanged)\b\s*(?:[:=?]|is|was)?\s*(?:false|no)\b/i.test(text)) return false;
  return [
    /\bworktree\b[^.;\n]*(?:\bis\b|\bwas\b|\bremained\b)?[^.;\n]*\b(clean|unchanged)\b/i,
    /\bworking tree\b[^.;\n]*(?:\bis\b|\bwas\b|\bremained\b)?[^.;\n]*\b(clean|unchanged)\b/i,
    /\bgit status --short\b[^.;\n]*\b(no output|empty|clean|unchanged)\b/i,
    /\bnothing to commit, working tree clean\b/i,
  ].some((pattern) => pattern.test(text));
}

export function validateImplementOrder(state, errors, options = {}) {
  if (state.stage !== 'he-implement' || state.next?.ready !== true) return;
  const ssotOwnerReuse = entryById(state.subStages, 'ssot-owner-reuse');
  const testFirst = entryById(state.subStages, 'test-first');
  const ownerChange = entryById(state.subStages, 'owner-change');
  const testProof = passedEntriesByMatcher(state.guardrails, matchesTestFirstProofGuardrail, options);
  const implementationProof = passedEntriesByMatcher(state.guardrails, matchesImplementationProofGuardrail, options);
  const ssotOwnerReuseSeq = sequence(ssotOwnerReuse, `subStages[${ssotOwnerReuse?.index}]`, errors);
  const testFirstSeq = sequence(testFirst, `subStages[${testFirst?.index}]`, errors);
  const ownerChangeSeq = sequence(ownerChange, `subStages[${ownerChange?.index}]`, errors);
  const testProofSeqs = sequences(testProof, errors);
  const implementationProofSeqs = sequences(implementationProof, errors);
  if (ssotOwnerReuseSeq !== null && testFirstSeq !== null && ssotOwnerReuseSeq >= testFirstSeq) errors.push('he-implement ready handoff requires ssot-owner-reuse before test-first');
  if (ssotOwnerReuseSeq !== null && ownerChangeSeq !== null && ssotOwnerReuseSeq >= ownerChangeSeq) errors.push('he-implement ready handoff requires ssot-owner-reuse before owner-change');
  if (testFirstSeq !== null && ownerChangeSeq !== null && testFirstSeq >= ownerChangeSeq) errors.push('he-implement ready handoff requires test-first before owner-change');
  if (testProofSeqs.length && ownerChangeSeq !== null && testProofSeqs.some((value) => value >= ownerChangeSeq)) errors.push('he-implement ready handoff requires test-first-proof before owner-change');
  if (testProofSeqs.length && ssotOwnerReuseSeq !== null && testProofSeqs.some((value) => value <= ssotOwnerReuseSeq)) errors.push('he-implement ready handoff requires test-first-proof after ssot-owner-reuse and before owner-change');
  if (implementationProofSeqs.length && ownerChangeSeq !== null && !implementationProofSeqs.some((value) => value > ownerChangeSeq)) errors.push('he-implement ready handoff requires implementation-proof after owner-change');
}

export function validateShipOrder(state, errors) {
  if (state.stage !== 'he-ship' || state.next?.ready !== true) return;
  const noMistakesSeqs = sequences(passedEntriesById(state.guardrails, 'no-mistakes'), errors);
  const prEvidenceSeqs = sequences(passedEntriesById(state.guardrails, 'pr-evidence'), errors);
  const reviewThreadSeqs = sequences(passedEntriesById(state.guardrails, 'pr-review-threads'), errors);
  const ciSeqs = sequences(passedEntriesById(state.guardrails, 'ci-or-skip'), errors);
  const currentnessEntries = passedEntriesById(state.guardrails, 'ship-currentness')
    .filter(hasShipCurrentnessCommand);
  const currentnessSeqs = sequences(currentnessEntries, errors);
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
  const currentCiSeqs = ciSeqs.filter((value) => value > latestReviewThreads);
  if (!currentCiSeqs.length) {
    errors.push('he-ship ready handoff requires ci-or-skip after current pr-review-threads');
    return;
  }
  if (state.next?.target !== 'loop-complete') return;
  const latestCi = Math.max(...currentCiSeqs);
  const latestCurrentnessSeq = currentnessSeqs.filter((value) => value > latestCi).sort((a, b) => b - a)[0];
  if (!latestCurrentnessSeq) {
    errors.push('he-ship loop-complete requires ship-currentness after final proof');
    return;
  }
  const latestEvidenceEntry = passedEntriesById(state.guardrails, 'pr-evidence')
    .find((entry) => entry.item.sequence === latestEvidence);
  const currentnessEntry = currentnessEntries.find((entry) => entry.item.sequence === latestCurrentnessSeq);
  const currentHead = extractCurrentHead(evidenceText(latestEvidenceEntry));
  const validatedHead = extractValidatedHead(evidenceText(currentnessEntry));
  if (!validatedHead || validatedHead !== currentHead) errors.push('he-ship loop-complete requires ship-currentness to match the current PR evidence head');
  if (!hasCleanWorktreeEvidence(evidenceText(currentnessEntry))) errors.push('he-ship loop-complete requires ship-currentness clean worktree evidence');
}
