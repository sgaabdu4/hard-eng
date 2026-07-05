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

function hasKeyLike(keys, exactKeys, prefixes) {
  return [...keys].some((key) => exactKeys.has(key) || prefixes.some((prefix) => key.startsWith(prefix)));
}

function hasPromptReplyPair(value) {
  if (!isObject(value)) return false;
  const keys = new Set(Object.keys(value).map(normalizedFieldName));
  return hasKeyLike(keys, promptLikeKeys, ['prompt', 'question']) &&
    hasKeyLike(keys, replyLikeKeys, ['answer', 'reply', 'response']);
}

function hasQuestionAnswerPair(value) {
  return hasShortQuestionAnswerPair(value) || hasPromptReplyPair(value);
}

function hasQuestionString(value) {
  return typeof value === 'string' && /(?:^|\b)(?:q\d+|question)\s*[:.)-]/i.test(value);
}

function hasAnswerString(value) {
  return typeof value === 'string' && /(?:^|\b)(?:a\d*|answer|reply|response)\s*[:.)-]/i.test(value);
}

function hasQuestionAnswerStringPair(value) {
  return Array.isArray(value) && value.some(hasQuestionString) && value.some(hasAnswerString);
}

export function validateNoGrillMeLedger(value, errors, pointer = 'planReadiness.grillMe') {
  if (Array.isArray(value)) {
    if (hasQuestionAnswerStringPair(value)) {
      errors.push(`${pointer} must not duplicate Grill Me question/answer history; use session_state.md during interview and final plan.md at synthesis`);
      return;
    }
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
