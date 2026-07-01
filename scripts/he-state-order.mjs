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

function shellCommandSegments(command) {
  const text = stripShellComments(command);
  const segments = [];
  let start = 0;
  let separator = 'sequence';
  let quote = null;
  let escaped = false;
  const push = (end, separatorAfter = 'sequence') => {
    const segment = text.slice(start, end).replace(/\s+/g, ' ').trim();
    if (segment) {
      segments.push({ segment, separator, separatorAfter });
      separator = separatorAfter;
      start = end;
      return;
    }
    if (!(['&&', '||'].includes(separator) && separatorAfter === 'sequence')) {
      separator = separatorAfter;
    }
    start = end;
  };
  for (let index = 0; index < text.length; index += 1) {
    const char = text[index];
    if (quote === "'") {
      if (char === "'") quote = null;
      continue;
    }
    if (escaped) {
      escaped = false;
      continue;
    }
    if (char === '\\') {
      escaped = true;
      continue;
    }
    if (quote === '"') {
      if (char === '"') quote = null;
      continue;
    }
    if (char === "'" || char === '"') {
      quote = char;
      continue;
    }
    if (char === '\n' || char === ';') {
      push(index, 'sequence');
      start = index + 1;
      continue;
    }
    if ((char === '&' || char === '|') && text[index + 1] === char) {
      push(index, `${char}${char}`);
      index += 1;
      start = index + 1;
      continue;
    }
    if (char === '&' || char === '|') {
      push(index, char === '&' ? 'background' : '|');
      start = index + 1;
    }
  }
  push(text.length);
  return segments;
}

function commandWords(segment) {
  return String(segment || '').split(/\s+/).map((word) => word.replace(/['"]/g, '')).filter(Boolean);
}

function staticCommandStatus(segment) {
  const command = commandWords(segment)[0]?.toLowerCase();
  if (['true', ':', 'echo', 'printf'].includes(command)) return 'success';
  if (command === 'false') return 'failure';
  return 'unknown';
}

function isTerminalCommand(segment) {
  return ['exit', 'return', 'exec'].includes(commandWords(segment)[0]?.toLowerCase());
}

function mayRunAfter(separator, status) {
  if (separator === 'sequence') return true;
  if (separator === '&&') return status === 'success';
  if (separator === '||') return status === 'failure';
  return false;
}

function isShipHeadCommand(segment) {
  return /^git\s+rev-parse\s+HEAD(?:\s|$)/.test(segment);
}

function isShipStatusCommand(segment) {
  const words = commandWords(segment).map((word) => word.toLowerCase());
  return words.length === 3 && words[0] === 'git' && words[1] === 'status' && words[2] === '--short';
}

function hasShipCurrentnessCommand(entry) {
  const segments = shellCommandSegments(entry?.item?.command);
  if (segments.some((item) => ['|', 'background'].includes(item.separator) || ['|', 'background'].includes(item.separatorAfter))) return false;
  let states = [{ status: 'success', headSucceeded: false, normal: true }];
  for (const { segment, separator } of segments) {
    const nextStates = [];
    for (const state of states) {
      if (!mayRunAfter(separator, state.status)) {
        nextStates.push(state);
        continue;
      }
      if (isShipStatusCommand(segment) && state.headSucceeded && state.normal) return true;
      if (isTerminalCommand(segment)) continue;
      const headCommand = isShipHeadCommand(segment);
      const commandStatus = staticCommandStatus(segment);
      const statuses = commandStatus === 'unknown' ? ['success', 'failure'] : [commandStatus];
      for (const status of statuses) {
        const succeeded = status === 'success';
        nextStates.push({
          status,
          normal: state.normal && succeeded,
          headSucceeded: commandStatus === 'failure'
            ? false
            : state.headSucceeded || (headCommand && succeeded),
        });
      }
    }
    states = nextStates;
  }
  return false;
}

function extractCurrentHead(text) {
  return text.match(/Current head:\s*`?([0-9a-f]{7,40})`?/i)?.[1] || null;
}

function extractValidatedHead(text) {
  return text.match(/(?:validated|current)\s+head:\s*`?([0-9a-f]{7,40})`?/i)?.[1] || null;
}

function stripAffirmedNoDirtyTerms(text) {
  return String(text || '')
    .replace(/\b(?:no|zero|without)\s+(?:(?:staged|unstaged|untracked|modified)\s*(?:,|\band\b|\bor\b)\s*)*(?:\b(?:and|or)\b\s*)?(?:staged|unstaged|untracked|modified)\s+(?:files?|changes?)\b/gi, '')
    .replace(/\b(?:no|zero|without)\s+(?:files?|changes?)\s+(?:staged|unstaged|untracked|modified)\b/gi, '');
}

function hasDirtyShortStatusOutput(text) {
  const value = String(text || '').replace(/[`'"]/g, '').replace(/\r/g, '');
  const markerPattern = /\bgit status --short\b/gi;
  let match;
  while ((match = markerPattern.exec(value)) !== null) {
    const output = value.slice(match.index + match[0].length);
    if (/(?:^|[;\n]|:\s*|\b(?:output|returned|returns|stdout|stderr|result|results?)\b\s*:?\s*)\s*(?:\?\?|[ MADRCUT]{0,1}[MADRCUT][ MADRCUT]{0,1})\s+\S/im.test(output)) return true;
  }
  return false;
}

function hasAffirmedNoChangesClause(text) {
  return /\b(?:no|zero|without)\s+(?:(?:uncommitted|local|outstanding|pending|unstaged)\s+)?changes?\b/i.test(text) ||
    /\bchanges?\s*(?:[:=?]|is|are|was|were)\s*(?:false|no|none|0)\b/i.test(text) ||
    /\bworktree\b[^.;\n]*\bhas\s+no\s+(?:(?:uncommitted|local|outstanding|pending|unstaged)\s+)?changes?\b/i.test(text);
}

function stripAffirmedNoChangesTerms(text) {
  return String(text || '')
    .replace(/\b(?:no|zero|without)\s+(?:(?:uncommitted|local|outstanding|pending|unstaged)\s+)?changes?\b/gi, '')
    .replace(/\bchanges?\s*(?:[:=?]|is|are|was|were)\s*(?:false|no|none|0)\b/gi, '')
    .replace(/\bworktree\b[^.;\n]*\bhas\s+no\s+(?:(?:uncommitted|local|outstanding|pending|unstaged)\s+)?changes?\b/gi, '');
}

function hasGenericDirtyEvidence(text) {
  const dirtyText = stripAffirmedNoDirtyTerms(text);
  const clauses = String(dirtyText || '').split(/[.;\n]+/).map((segment) => segment.trim()).filter(Boolean);
  return clauses.some((clause) => {
    const dirtyClause = hasAffirmedNoChangesClause(clause) ? stripAffirmedNoChangesTerms(clause) : clause;
    return [
      /\b(?:worktree|working tree)\b[^.;\n]*\b(?:has|had|contains|showed|shows|with)\s+(?!no\b|zero\b)(?:(?:uncommitted|local|outstanding|pending|unstaged)\s+)?changes?\b/i,
      /\b(?:worktree|working tree)\b[^.;\n]*\b(?:(?:uncommitted|local|outstanding|pending|unstaged)\s+)?changes?\s+(?:present|detected|found|remaining|remain)\b/i,
      /\b(?:(?:uncommitted|local|outstanding|pending|unstaged)\s+)?changes?\s+(?:in|on|within)\s+(?:the\s+)?(?:worktree|working tree)\b/i,
      /\bgit status --short\b[^.;\n]*\b(?:not\s+empty|output\s+(?:present|detected|found|returned|exists))\b/i,
      /\bgit status --short\b[^.;\n]*\b(?:returned|returns|showed|shows|reported|reports|had|has|with)\s+(?!no\b|zero\b|empty\b)(?:non[- ]?empty|changes?|dirty|output)\b/i,
      /\bnon[- ]?empty\b[^.;\n]*\bgit status --short\b/i,
    ].some((pattern) => pattern.test(dirtyClause));
  });
}

function hasNegatedCleanEvidence(text) {
  const negative = "(?:(?:not|never|isn(?:['’]|\\s)?t|aren(?:['’]|\\s)?t|wasn(?:['’]|\\s)?t|weren(?:['’]|\\s)?t|hasn(?:['’]|\\s)?t|hadn(?:['’]|\\s)?t)(?!\\s+(?:only|just|merely|simply)\\b))";
  return [
    new RegExp(`\\b(?:worktree|working tree)\\b[^.;\\n]{0,80}\\b${negative}\\b[^.;\\n]{0,40}\\b(?:clean|unchanged)\\b`, 'i'),
    new RegExp(`\\bgit status --short\\b[^.;\\n]{0,80}\\b${negative}\\b[^.;\\n]{0,40}\\b(?:empty|clean|unchanged|no\\s+output)\\b`, 'i'),
  ].some((pattern) => pattern.test(text));
}

function hasCleanWorktreeEvidence(text) {
  const dirtyText = stripAffirmedNoDirtyTerms(text);
  if (/\b(?:not[- ]?clean|not\s+unchanged|unclean|dirty|changes?\s+pending)\b/i.test(dirtyText)) return false;
  if (hasNegatedCleanEvidence(text)) return false;
  if (/\b(?:modified|untracked|unstaged|staged)\s+(?:files?|changes?)\b/i.test(dirtyText)) return false;
  if (/\b(?:files?|changes?)\s+(?:modified|untracked|unstaged|staged)\b/i.test(dirtyText)) return false;
  if (/\bgit status --short\b[^.;\n]*\b(?:modified|untracked|unstaged|staged)\b/i.test(dirtyText)) return false;
  if (hasDirtyShortStatusOutput(text)) return false;
  if (hasGenericDirtyEvidence(text)) return false;
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
