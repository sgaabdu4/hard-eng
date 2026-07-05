function isObject(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

const grillMeLedgerKeys = new Set([
  'answers',
  'answerhistory',
  'answerledger',
  'answerlog',
  'conversation',
  'conversationhistory',
  'decisions',
  'history',
  'interviewhistory',
  'qa',
  'qas',
  'qna',
  'questionanswer',
  'questionanswers',
  'questionhistory',
  'questionledger',
  'questionlog',
  'questions',
  'responses',
  'responsehistory',
  'transcript',
]);

function normalizedFieldName(key) {
  return String(key || '').replace(/[^a-z0-9]/gi, '').toLowerCase();
}

export function validateNoGrillMeLedger(value, errors, pointer = 'planReadiness.grillMe') {
  if (Array.isArray(value)) {
    value.forEach((item, index) => validateNoGrillMeLedger(item, errors, `${pointer}[${index}]`));
    return;
  }
  if (!isObject(value)) return;
  for (const [key, child] of Object.entries(value)) {
    const childPointer = `${pointer}.${key}`;
    if (grillMeLedgerKeys.has(normalizedFieldName(key))) {
      errors.push(`${childPointer} must not duplicate Grill Me question/answer history; use session_state.md during interview and final plan.md at synthesis`);
      continue;
    }
    if (key === 'lastQuestion') continue;
    validateNoGrillMeLedger(child, errors, childPointer);
  }
}
