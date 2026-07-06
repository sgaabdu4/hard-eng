function isObject(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

function hasText(value) {
  return typeof value === 'string' && value.trim().length > 0;
}

const ledgerMessage = 'must not duplicate Grill Me question/answer history; use session_state.md during interview and final plan.md at synthesis';

function ledgerError(errors, pointer) {
  errors.push(`${pointer} ${ledgerMessage}`);
}

const questionMarker = '(?:q(?:\\s*#?\\d+)?|question(?:\\s*#?\\d+)?)';
const answerMarker = '(?:a\\s*\\d*|answer(?:\\s*#?\\d+)?|reply(?:\\s*#?\\d+)?|response(?:\\s*#?\\d+)?)';
const nonInstructionAnswerMarker = '(?:a\\s*\\d*|answer(?:\\s*#?\\d+)?|response(?:\\s*#?\\d+)?)';
const questionStringPattern = new RegExp(`(?:^|\\b)${questionMarker}\\s*[:.)-]`, 'i');
const questionStringGlobalPattern = new RegExp(`(?:^|\\b)${questionMarker}\\s*[:.)-]`, 'gi');
const answerStringPattern = new RegExp(`(?:^|\\b)${answerMarker}\\s*:`, 'i');
const transcriptQuestionPattern = new RegExp(`(?:^|\\n)\\s*${questionMarker}\\s*[:.)-]`, 'i');
const transcriptAnswerPattern = new RegExp(`(?:^|\\n|\\b)\\s*${answerMarker}\\s*:`, 'i');
const nonInstructionAnswerPattern = new RegExp(`(?:^|\\n|\\b)\\s*${nonInstructionAnswerMarker}\\s*:`, 'i');
const nonInstructionReplyAnswerPattern = /(?:^|\n|\b)\s*reply(?:\s*#?\d+)?\s*:(?!\s*A\/B\/C\b)/i;
const compactQuestionAnswerAssignmentPattern = /(?:^|[\s,;])(?:q|question)\s*#?\d+\s*=\s*\S/i;

function hasQuestionString(value) {
  return typeof value === 'string' && questionStringPattern.test(value);
}

function hasAnswerString(value) {
  return typeof value === 'string' && answerStringPattern.test(value);
}

function questionStringCount(value) {
  return typeof value === 'string' ? (value.match(questionStringGlobalPattern) || []).length : 0;
}

function hasCompactQuestionAnswerAssignment(value) {
  return typeof value === 'string' && compactQuestionAnswerAssignmentPattern.test(value);
}

function hasCurrentQuestionOnlyInstructionShape(value) {
  return typeof value === 'string' &&
    questionStringCount(value) === 1 &&
    /^Q\d+:/m.test(value) &&
    /Meaning:/m.test(value) &&
    /Why it matters:/m.test(value) &&
    /Suggested default:/m.test(value) &&
    /Options:/m.test(value) &&
    /^A\)/m.test(value) &&
    /^B\)/m.test(value) &&
    /^C\)/m.test(value) &&
    /^Reply:\s*A\/B\/C\b/m.test(value) &&
    !nonInstructionAnswerPattern.test(value) &&
    !nonInstructionReplyAnswerPattern.test(value);
}

function hasQuestionAnswerTranscriptString(value) {
  return typeof value === 'string' &&
    !hasCurrentQuestionOnlyInstructionShape(value) &&
    transcriptQuestionPattern.test(value) &&
    transcriptAnswerPattern.test(value);
}

function hasQuestionAnswerStringPair(value) {
  return Array.isArray(value) && value.some((question, questionIndex) => (
    hasQuestionString(question) &&
    value.some((answer, answerIndex) => answerIndex !== questionIndex && hasAnswerString(answer))
  ));
}

const grillMeKeys = new Set([
  'required',
  'status',
  'statePath',
  'questionPolicy',
  'alignment',
  'stages',
  'lastQuestion',
  'reason',
  'evidence',
  'skipEvidence',
  'blocker',
  'blockers',
  'artifactPaths',
  'planPath',
  'planPaths',
  'sessionStatePath',
  'planDraftPath',
  'questionCount',
  'stageCount',
  'openQuestionCount',
  'openUnknownCount',
  'blockerCount',
  'createdAt',
  'updatedAt',
  'acceptedAt',
  'blockedAt',
  'refs',
  'references',
  'evidenceRefs',
  'artifactRefs',
]);

const questionPolicyKeys = new Set([
  'mode',
  'evidence',
  'reason',
  'questionCount',
  'turnCount',
  'askedCount',
  'createdAt',
  'updatedAt',
  'refs',
  'references',
  'evidenceRefs',
]);

const alignmentKeys = new Set([
  'status',
  'userConfirmed',
  'noGuesswork',
  'openQuestions',
  'openUnknowns',
  'openBlockers',
  'blockers',
  'blockedBy',
  'reason',
  'evidence',
  'questionCount',
  'unknownCount',
  'blockerCount',
  'createdAt',
  'updatedAt',
  'acceptedAt',
  'blockedAt',
  'refs',
  'references',
  'evidenceRefs',
]);

const stageKeys = new Set([
  'id',
  'map',
  'status',
  'reason',
  'evidence',
  'path',
  'paths',
  'ref',
  'refs',
  'createdAt',
  'updatedAt',
  'startedAt',
  'completedAt',
  'blockedAt',
  'skippedAt',
  'sequence',
  'questionCount',
  'openQuestionCount',
  'openUnknownCount',
  'blockerCount',
]);

const lastQuestionKeys = new Set([
  'id',
  'index',
  'status',
  'format',
  'text',
  'visibleText',
  'statePath',
  'path',
  'ref',
  'refs',
  'evidence',
  'createdAt',
  'updatedAt',
  'askedAt',
]);

function validateText(value, errors, pointer) {
  if (Array.isArray(value) || isObject(value)) {
    ledgerError(errors, pointer);
    return;
  }
  if (
    hasCompactQuestionAnswerAssignment(value) ||
    questionStringCount(value) > 1 ||
    hasQuestionAnswerTranscriptString(value) ||
    (typeof value === 'string' && !hasCurrentQuestionOnlyInstructionShape(value) && hasAnswerString(value))
  ) ledgerError(errors, pointer);
}

function validateTextArray(value, errors, pointer) {
  if (hasQuestionAnswerStringPair(value)) {
    ledgerError(errors, pointer);
    return;
  }
  if (!Array.isArray(value)) {
    validateText(value, errors, pointer);
    return;
  }
  const questionCount = value.reduce((count, item) => count + questionStringCount(item), 0);
  if (questionCount > 1) {
    ledgerError(errors, pointer);
    return;
  }
  value.forEach((item, index) => {
    const itemPointer = `${pointer}[${index}]`;
    if (typeof item === 'string') {
      validateText(item, errors, itemPointer);
    } else if (item !== null && item !== undefined) {
      ledgerError(errors, itemPointer);
    }
  });
}

function validateAllowedKeys(value, allowedKeys, errors, pointer) {
  let valid = true;
  for (const key of Object.keys(value)) {
    if (!allowedKeys.has(key)) {
      ledgerError(errors, `${pointer}.${key}`);
      valid = false;
    }
  }
  return valid;
}

function validateObject(value, errors, pointer) {
  if (isObject(value)) return true;
  if (value !== null && value !== undefined) ledgerError(errors, pointer);
  return false;
}

function validateQuestionPolicy(value, errors, pointer) {
  if (!validateObject(value, errors, pointer)) return;
  validateAllowedKeys(value, questionPolicyKeys, errors, pointer);
  for (const [key, child] of Object.entries(value)) {
    if (['evidence', 'refs', 'references', 'evidenceRefs'].includes(key)) validateTextArray(child, errors, `${pointer}.${key}`);
    else validateText(child, errors, `${pointer}.${key}`);
  }
}

function validateAlignment(value, errors, pointer) {
  if (!validateObject(value, errors, pointer)) return;
  validateAllowedKeys(value, alignmentKeys, errors, pointer);
  for (const [key, child] of Object.entries(value)) {
    if (['openQuestions', 'openUnknowns', 'openBlockers', 'blockers', 'blockedBy', 'evidence', 'refs', 'references', 'evidenceRefs'].includes(key)) {
      validateTextArray(child, errors, `${pointer}.${key}`);
    } else {
      validateText(child, errors, `${pointer}.${key}`);
    }
  }
}

function validateStage(value, errors, pointer) {
  if (!isObject(value)) {
    if (value !== null && value !== undefined) ledgerError(errors, pointer);
    return;
  }
  validateAllowedKeys(value, stageKeys, errors, pointer);
  for (const [key, child] of Object.entries(value)) {
    if (['evidence', 'paths', 'refs'].includes(key)) validateTextArray(child, errors, `${pointer}.${key}`);
    else validateText(child, errors, `${pointer}.${key}`);
  }
}

function validateStages(value, errors, pointer) {
  if (!Array.isArray(value)) {
    if (value !== null && value !== undefined) ledgerError(errors, pointer);
    return;
  }
  value.forEach((item, index) => validateStage(item, errors, `${pointer}[${index}]`));
}

function validateLastQuestion(value, errors, pointer) {
  if (!validateObject(value, errors, pointer)) return;
  validateAllowedKeys(value, lastQuestionKeys, errors, pointer);
  for (const [key, child] of Object.entries(value)) {
    if (['evidence', 'refs'].includes(key)) validateTextArray(child, errors, `${pointer}.${key}`);
    else validateText(child, errors, `${pointer}.${key}`);
  }
}

export function validateNoGrillMeLedger(value, errors, pointer = 'planReadiness.grillMe') {
  if (!isObject(value)) return;
  validateAllowedKeys(value, grillMeKeys, errors, pointer);
  for (const [key, child] of Object.entries(value)) {
    const childPointer = `${pointer}.${key}`;
    if (key === 'questionPolicy') validateQuestionPolicy(child, errors, childPointer);
    else if (key === 'alignment') validateAlignment(child, errors, childPointer);
    else if (key === 'stages') validateStages(child, errors, childPointer);
    else if (key === 'lastQuestion') validateLastQuestion(child, errors, childPointer);
    else if (['evidence', 'skipEvidence', 'blockers', 'artifactPaths', 'planPaths', 'refs', 'references', 'evidenceRefs', 'artifactRefs'].includes(key)) validateTextArray(child, errors, childPointer);
    else validateText(child, errors, childPointer);
  }
}
