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
  'prompt',
  'prompts',
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
  'reply',
  'replies',
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

const promptLikeKeys = new Set(['prompt', 'prompts', 'q', 'question', 'questions']);
const replyLikeKeys = new Set(['a', 'answer', 'answers', 'reply', 'replies', 'response', 'responses']);

function hasPromptReplyPair(value) {
  if (!isObject(value)) return false;
  const keys = new Set(Object.keys(value).map(normalizedFieldName));
  return [...promptLikeKeys].some((key) => keys.has(key)) &&
    [...replyLikeKeys].some((key) => keys.has(key));
}

function hasQuestionAnswerPair(value) {
  return hasShortQuestionAnswerPair(value) || hasPromptReplyPair(value);
}

export function validateNoGrillMeLedger(value, errors, pointer = 'planReadiness.grillMe') {
  if (Array.isArray(value)) {
    value.forEach((item, index) => {
      const childPointer = `${pointer}[${index}]`;
      if (hasQuestionAnswerPair(item)) {
        errors.push(`${childPointer} must not duplicate Grill Me question/answer history; use session_state.md during interview and final plan.md at synthesis`);
        return;
      }
      validateNoGrillMeLedger(item, errors, childPointer);
    });
    return;
  }
  if (!isObject(value)) return;
  if (hasQuestionAnswerPair(value)) {
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
