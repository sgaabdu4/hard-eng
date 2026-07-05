function isObject(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

const grillMeLedgerKeys = new Set([
  'answer',
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
  'qahistory',
  'qaledger',
  'qalog',
  'qas',
  'qna',
  'question',
  'questionandanswer',
  'questionandanswers',
  'questionanswer',
  'questionanswers',
  'questionhistory',
  'questionledger',
  'questionlog',
  'questionsandanswers',
  'questions',
  'responses',
  'responsehistory',
  'transcript',
]);

function normalizedFieldName(key) {
  return String(key || '').replace(/[^a-z0-9]/gi, '').toLowerCase();
}

function hasShortQuestionAnswerPair(value) {
  if (!isObject(value)) return false;
  const keys = new Set(Object.keys(value).map(normalizedFieldName));
  return keys.has('q') && keys.has('a');
}

export function validateNoGrillMeLedger(value, errors, pointer = 'planReadiness.grillMe') {
  if (Array.isArray(value)) {
    value.forEach((item, index) => {
      const childPointer = `${pointer}[${index}]`;
      if (hasShortQuestionAnswerPair(item)) {
        errors.push(`${childPointer} must not duplicate Grill Me question/answer history; use session_state.md during interview and final plan.md at synthesis`);
        return;
      }
      validateNoGrillMeLedger(item, errors, childPointer);
    });
    return;
  }
  if (!isObject(value)) return;
  if (hasShortQuestionAnswerPair(value)) {
    errors.push(`${pointer} must not duplicate Grill Me question/answer history; use session_state.md during interview and final plan.md at synthesis`);
    return;
  }
  for (const [key, child] of Object.entries(value)) {
    const childPointer = `${pointer}.${key}`;
    if (grillMeLedgerKeys.has(normalizedFieldName(key))) {
      errors.push(`${childPointer} must not duplicate Grill Me question/answer history; use session_state.md during interview and final plan.md at synthesis`);
      continue;
    }
    validateNoGrillMeLedger(child, errors, childPointer);
  }
}
