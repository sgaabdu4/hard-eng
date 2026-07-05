function isObject(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

function hasText(value) {
  return typeof value === 'string' && value.trim().length > 0;
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
  'choice',
  'selectedoption',
  'selection',
  'reply',
  'replies',
  'responses',
  'responsehistory',
  'transcript',
  'useranswer',
  'userchoice',
  'userdecision',
  'userreply',
  'userresponse',
  'userselection',
]);

function normalizedFieldName(key) {
  return String(key || '').replace(/[^a-z0-9]/gi, '').toLowerCase();
}

const ledgerQuestionTokens = new Set(['prompt', 'prompts', 'q', 'qa', 'qna', 'question', 'questions']);
const ledgerAnswerTokens = new Set(['a', 'answer', 'answers', 'choice', 'choices', 'option', 'options', 'reply', 'replies', 'response', 'responses', 'selected', 'selectedoption', 'selectedoptions', 'selection', 'selections', 'useranswer', 'useranswers', 'userchoice', 'userchoices', 'userdecision', 'userdecisions', 'userreply', 'userreplies', 'userresponse', 'userresponses', 'userselection', 'userselections', 'value', 'values']);
const ledgerContainerTokens = new Set(['by', 'conversation', 'conversations', 'entries', 'entry', 'histories', 'history', 'index', 'indexes', 'indices', 'item', 'items', 'ledger', 'ledgers', 'list', 'lists', 'log', 'logs', 'lookup', 'lookups', 'map', 'maps', 'message', 'messages', 'record', 'records', 'transcript', 'transcripts']);
const forbiddenLedgerContainerTokens = new Set(['conversation', 'conversations', 'histories', 'history', 'transcript', 'transcripts']);

function fieldNameTokens(key) {
  return String(key || '')
    .replace(/([a-z0-9])([A-Z])/g, '$1 $2')
    .toLowerCase()
    .split(/[^a-z0-9]+/)
    .filter(Boolean);
}

function hasAnyToken(tokens, tokenSet) {
  return tokens.some((token) => tokenSet.has(token));
}

function isGrillMeLedgerKey(key) {
  const normalized = normalizedFieldName(key);
  if (grillMeLedgerKeys.has(normalized)) return true;
  const tokens = fieldNameTokens(key);
  const hasQuestion = hasAnyToken(tokens, ledgerQuestionTokens);
  const hasAnswer = hasAnyToken(tokens, ledgerAnswerTokens);
  const hasContainer = hasAnyToken(tokens, ledgerContainerTokens);
  const hasForbiddenContainer = hasAnyToken(tokens, forbiddenLedgerContainerTokens);
  const hasNormalizedQuestion = /question|prompt|qa|qna/.test(normalized);
  const hasNormalizedAnswer = /answer|choice|option|reply|response|selected|selection|useranswer|userchoice|userdecision|userreply|userresponse|userselection|value/.test(normalized);
  const hasNormalizedForbiddenContainer = /conversation|histories|history|transcripts?/.test(normalized);
  const hasNormalizedContainer = /conversation|entries|entry|histories|history|index|indexes|indices|items?|ledgers?|lists?|logs?|lookups?|maps?|messages?|records?|transcripts?/.test(normalized) ||
    /(?:answers?|choices?|options?|prompts?|questions?|replies|responses?|selected|selections?|useranswers?|userchoices?|userdecisions?|userreplies|userresponses?|userselections?|values?)by/.test(normalized);
  return hasForbiddenContainer ||
    hasNormalizedForbiddenContainer ||
    (hasQuestion && hasAnswer) ||
    (hasNormalizedQuestion && hasNormalizedAnswer) ||
    ((hasQuestion || hasAnswer) && hasContainer) ||
    ((hasNormalizedQuestion || hasNormalizedAnswer) && hasNormalizedContainer);
}

function hasShortQuestionAnswerPair(value) {
  if (!isObject(value)) return false;
  const keys = new Set(Object.keys(value).map(normalizedFieldName));
  return keys.has('q') && keys.has('a');
}

const promptLikeKeys = new Set(['prompt', 'prompts', 'q', 'question', 'questions', 'text', 'visibletext']);
const replyLikeKeys = new Set(['a', 'answer', 'answers', 'choice', 'option', 'options', 'reply', 'replies', 'response', 'responses', 'selected', 'selectedoption', 'selection', 'useranswer', 'userchoice', 'userdecision', 'userreply', 'userresponse', 'userselection', 'value']);

function hasKeyLike(keys, exactKeys, prefixes) {
  return [...keys].some((key) => exactKeys.has(key) || prefixes.some((prefix) => key.startsWith(prefix)));
}

function hasPromptReplyPair(value) {
  if (!isObject(value)) return false;
  const keys = new Set(Object.keys(value).map(normalizedFieldName));
  return hasKeyLike(keys, promptLikeKeys, ['prompt', 'question']) &&
    hasKeyLike(keys, replyLikeKeys, ['answer', 'choice', 'option', 'reply', 'response', 'selected', 'selectedoption', 'selection', 'useranswer', 'userchoice', 'userdecision', 'userreply', 'userresponse', 'userselection']);
}

function isQuestionLikeMapKey(key) {
  const text = String(key || '').trim();
  return /^(?:q|question)\d+$/.test(normalizedFieldName(key)) ||
    /\?$/.test(text) ||
    /^(?:who|what|which|whether|how|when|where)\b/i.test(text);
}

function hasQuestionAnswerMap(value) {
  if (!isObject(value)) return false;
  return Object.entries(value).some(([key, child]) => (
    isQuestionLikeMapKey(key) && hasText(child)
  ));
}

function hasQuestionAnswerPair(value) {
  return hasShortQuestionAnswerPair(value) || hasPromptReplyPair(value) || hasQuestionAnswerMap(value);
}

const questionMarker = '(?:q(?:\\s*#?\\d+)?|question(?:\\s*#?\\d+)?)';
const answerMarker = '(?:a\\s*\\d*|answer(?:\\s*#?\\d+)?|reply(?:\\s*#?\\d+)?|response(?:\\s*#?\\d+)?)';
const nonInstructionAnswerMarker = '(?:a\\s*\\d*|answer(?:\\s*#?\\d+)?|response(?:\\s*#?\\d+)?)';
const transcriptAnswerMarker = answerMarker;
const questionStringPattern = new RegExp(`(?:^|\\b)${questionMarker}\\s*[:.)-]`, 'i');
const answerStringPattern = new RegExp(`(?:^|\\b)${answerMarker}\\s*:`, 'i');
const transcriptQuestionPattern = new RegExp(`(?:^|\\n)\\s*${questionMarker}\\s*[:.)-]`, 'i');
const transcriptAnswerPattern = new RegExp(`(?:^|\\n)\\s*${transcriptAnswerMarker}\\s*:`, 'i');
const nonInstructionAnswerPattern = new RegExp(`(?:^|\\n)\\s*${nonInstructionAnswerMarker}\\s*:`, 'i');

function hasQuestionString(value) {
  return typeof value === 'string' && questionStringPattern.test(value);
}

function hasAnswerString(value) {
  return typeof value === 'string' && answerStringPattern.test(value);
}

function hasCurrentQuestionOnlyInstructionShape(value) {
  return typeof value === 'string' &&
    /^Q\d+:/m.test(value) &&
    /Meaning:/m.test(value) &&
    /Why it matters:/m.test(value) &&
    /Suggested default:/m.test(value) &&
    /Options:/m.test(value) &&
    /^A\)/m.test(value) &&
    /^B\)/m.test(value) &&
    /^C\)/m.test(value) &&
    /^Reply:\s*A\/B\/C\b/m.test(value) &&
    !nonInstructionAnswerPattern.test(value);
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

const promptRoles = new Set(['assistant', 'agent', 'codex', 'system']);
const replyRoles = new Set(['user', 'human', 'customer', 'client', 'stakeholder']);

function roleContentMessage(value) {
  if (!isObject(value)) return null;
  const role = normalizedFieldName(value.role);
  if (!role || !hasText(value.content)) return null;
  return { role, content: value.content };
}

function hasRoleContentTranscriptPair(value) {
  if (!Array.isArray(value)) return false;
  const messages = value.map(roleContentMessage).filter(Boolean);
  return messages.some((prompt, promptIndex) => (
    (promptRoles.has(prompt.role) || hasQuestionString(prompt.content)) &&
    messages.some((reply, replyIndex) => (
      replyIndex !== promptIndex &&
      (replyRoles.has(reply.role) || hasAnswerString(reply.content))
    ))
  ));
}

export function validateNoGrillMeLedger(value, errors, pointer = 'planReadiness.grillMe') {
  if (hasQuestionAnswerTranscriptString(value)) {
    errors.push(`${pointer} must not duplicate Grill Me question/answer history; use session_state.md during interview and final plan.md at synthesis`);
    return;
  }
  if (Array.isArray(value)) {
    if (hasQuestionAnswerStringPair(value) || hasRoleContentTranscriptPair(value)) {
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
    if (isGrillMeLedgerKey(key)) {
      errors.push(`${childPointer} must not duplicate Grill Me question/answer history; use session_state.md during interview and final plan.md at synthesis`);
      continue;
    }
    validateNoGrillMeLedger(child, errors, childPointer);
  }
}
