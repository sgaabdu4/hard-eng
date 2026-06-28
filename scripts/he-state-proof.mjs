const commandStart = String.raw`^\s*(?:env\s+)?(?:[A-Za-z_][A-Za-z0-9_]*=(?:"[^"]*"|'[^']*'|\S+)\s+)*`;
const shellTokenEnd = String.raw`(?=$|\s|[;&|])`;
const testRunnerPattern = new RegExp(`${commandStart}(?:(?:npm|pnpm|yarn|bun)\\s+(?:test${shellTokenEnd}|run\\s+(?:test(?::[\\w:-]+)?|spec|vitest|jest)${shellTokenEnd}|exec\\s+(?:vitest|jest|mocha)${shellTokenEnd})|npx\\s+(?:vitest|jest|mocha)${shellTokenEnd}|node\\s+--test${shellTokenEnd}|(?:pytest|vitest|jest|mocha|ava|tap|rspec|phpunit|vendor\\/bin\\/phpunit)${shellTokenEnd}|(?:flutter|dart|go|cargo|mvn|gradle)\\s+test${shellTokenEnd}|make\\s+test${shellTokenEnd}|\\.\\/gradlew\\s+test${shellTokenEnd})`, 'i');
const mutationCommandPattern = new RegExp(`${commandStart}(?:(?:npx\\s+)?stryker\\s+run${shellTokenEnd}|npm\\s+run\\s+(?:mutation|mutate|mutants?|stryker)(?::[\\w:-]+)?${shellTokenEnd}|(?:pnpm|yarn|bun)\\s+(?:run\\s+)?(?:mutation|mutate|mutants?|stryker)(?::[\\w:-]+)?${shellTokenEnd}|(?:mutmut|infection|pitest)${shellTokenEnd}|cargo\\s+mutants${shellTokenEnd}|make\\s+(?:mutation|mutate|mutants?)${shellTokenEnd})`, 'i');
const makeItFailCommandPattern = new RegExp(`${commandStart}(?:npm\\s+run\\s+(?:make[-:]?it[-:]?fail|test[-:]?fail|fail[-:]?test)(?::[\\w:-]+)?${shellTokenEnd}|(?:pnpm|yarn|bun)\\s+(?:run\\s+)?(?:make[-:]?it[-:]?fail|test[-:]?fail|fail[-:]?test)(?::[\\w:-]+)?${shellTokenEnd}|make\\s+(?:make[- ]?it[- ]?fail|test[- ]?fail|fail[- ]?test)${shellTokenEnd})`, 'i');
const redProofPattern = /\b(?:red[- ]?first\s+(?:failed|failure|red|reproduced|confirmed|recorded|nonzero)|red\s+(?:state|run)\s+(?:recorded|confirmed|reproduced)|failed as expected|[1-9]\d*\s+(?:failing tests?|failures?|failed tests?)|failing tests?\s+(?:recorded|confirmed|reproduced|before implementation|as expected)|(?:recorded|confirmed|reproduced)\s+failing tests?)\b/i;
const mutationProofPattern = /\b(?:(?:mutation|mutants?).*(?:killed|detected|failed as expected)|(?:killed|detected).*(?:mutation|mutants?)|make[- ]?it[- ]?fail.*(?:failed as expected|reproduced|confirmed|red|nonzero))\b/i;
const redFailureCountPattern = /\b(?:[1-9]\d*\s+(?:failed|failing tests?|failures?|failed tests?)|(?:failed tests?|failing tests?|failures?|failed)\s*[:=]\s*[1-9]\d*)\b/i;
const mutationCountProofPattern = /\b(?:(?:[1-9]\d*\s+(?:mutants?|mutations?)\s+(?:were\s+)?(?:killed|detected))|(?:killed|detected)\s+[1-9]\d*\s+(?:mutants?|mutations?)|(?:mutants?|mutations?)\s+(?:were\s+)?(?:killed|detected)\s*[:=]\s*[1-9]\d*|(?:mutation|mutations?|mutants?)[^\n]*(?:killed|detected)\s*[:=]\s*[1-9]\d*|(?:killed|detected)\s*[:=]\s*[1-9]\d*[^\n]*(?:mutation|mutations?|mutants?))\b/i;
const notRedProofTerms = [
  String.raw`0\s+(?:failing tests?|failures?|failed(?: tests?)?|(?:mutants?|mutations?)\s+(?:were\s+)?(?:killed|detected)|killed\s+(?:mutants?|mutations?))`,
  String.raw`(?:failed tests?|failing tests?|failures?|failed)\s*[:=]\s*0`,
  String.raw`0\s*\/\s*\d+\s+(?:mutants?|mutations?)\s+(?:killed|detected)`,
  String.raw`(?:killed|detected)\s+0\s+(?:mutants?|mutations?)`,
  String.raw`(?:mutants?|mutations?)\s+(?:were\s+)?(?:killed|detected)\s*[:=]\s*0`,
  String.raw`(?:mutation|mutations?|mutants?)[^\n]*(?:killed|detected)\s*[:=]\s*0`,
  String.raw`(?:killed|detected)\s*[:=]\s*0[^\n]*(?:mutation|mutations?|mutants?)`,
  String.raw`(?:mutants?|mutations?)\s+(?:were\s+)?(?:killed|detected)\s*[:=]?\s*none`,
  String.raw`(?:killed|detected)\s*[:=]?\s*none[^\n]*(?:mutants?|mutations?)`,
  String.raw`no\s+(?:failing tests?|failures?|failed(?: tests?)?|mutants?\s+killed|(?:mutants?|mutations?)\s+(?:were\s+)?(?:killed|detected))`,
  String.raw`zero\s+(?:failing tests?|failures?|failed(?: tests?)?|(?:mutants?|mutations?)\s+(?:killed|detected))`,
  String.raw`not failing`,
  String.raw`did not fail`,
  String.raw`didn't fail`,
  String.raw`not run`,
  String.raw`did not run`,
  String.raw`didn't run`,
  String.raw`green`,
  String.raw`clean`,
  String.raw`(?:mutants?|mutations?)[^\n]*(?:not|was not|wasn't|did not|didn't)\s+(?:run|executed?|kill(?:ed)?|detected?)`,
];
const redProofContradictionPattern = new RegExp(`\\b(?:${notRedProofTerms.join('|')})\\b`, 'i');
const notRedProofPattern = new RegExp(`\\b(?:${[...notRedProofTerms, 'skipped', 'pending', 'todo'].join('|')})\\b`, 'i');
const greenProofPattern = /\b(?:all tests? passed|tests? passed|[1-9]\d*\s+(?:tests?|specs?|checks?|assertions?)?\s*passed|passed:\s*[1-9]\d*|green(?: test)? run)\b/i;
const failedProofPattern = /\b(?:not all (?:tests?|specs?|checks?) passed|no\s+(?:tests?|specs?|checks?)\s+passed|tests?\s+passed:\s*0|passed\s*[:=]\s*0|passed\s*[:=]\s*\d+[^.;\n]*(?:failed|failures?|errors?|errored)\s*[:=]\s*[1-9]\d*|(?:failed|failures?|errors?|errored)\s*[:=]\s*[1-9]\d*|(?:failed|failures?|errors?|errored)\s+(?:[1-9]\d*|remain|remaining|left|present)|[1-9]\d*\s+(?:errors?|errored)|did not pass|didn't pass|not pass(?:ed)?|not green|not clean|not success(?:ful)?|tests? failed|failed tests?|[1-9]\d*\s+(?:failing|failures?|failed)|failing tests?(?:\s+(?:remain|remaining|left|present))?|failures?(?:\s+(?:remain|remaining|left|present))?|red[- ]?first|failed as expected|mutation|make[- ]?it[- ]?fail|not run|did not run|didn't run|skipped|pending|todo|0\s+(?:tests?\s+)?passed|0\/\d+\s+passed)\b/i;

function evidenceText(guardrail) {
  return Array.isArray(guardrail?.evidence) ? guardrail.evidence.join(' ') : '';
}

function shellCommandSegments(command) {
  const text = String(command || '');
  const segments = [];
  let start = 0;
  let quote = null;
  let escaped = false;
  const push = (end) => {
    const segment = text.slice(start, end);
    if (segment.trim()) segments.push(segment);
  };
  for (let index = 0; index < text.length; index += 1) {
    const char = text[index];
    if (quote === "'") {
      if (char === "'") quote = null;
      continue;
    }
    if (quote === '"') {
      if (escaped) {
        escaped = false;
        continue;
      }
      if (char === '\\') {
        escaped = true;
        continue;
      }
      if (char === '"') quote = null;
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
    if (char === "'" || char === '"') {
      quote = char;
      continue;
    }
    if (char === '#' && (index === start || /\s/.test(text[index - 1]))) {
      push(index);
      while (index < text.length && text[index] !== '\n') index += 1;
      start = index + 1;
      continue;
    }
    if (char === '\n' || char === ';') {
      push(index);
      start = index + 1;
      continue;
    }
    if ((char === '&' || char === '|') && text[index + 1] === char) {
      push(index);
      index += 1;
      start = index + 1;
    }
  }
  push(text.length);
  return segments;
}

function hasCommandMatching(command, pattern) {
  return shellCommandSegments(command).some((segment) => pattern.test(segment));
}

export function hasTestFirstProofCommand(command) {
  return hasCommandMatching(command, testRunnerPattern) || hasCommandMatching(command, mutationCommandPattern) || hasCommandMatching(command, makeItFailCommandPattern);
}

export function hasImplementationProofCommand(command) {
  return hasCommandMatching(command, testRunnerPattern);
}

export function hasRedProof(text) {
  if (redProofContradictionPattern.test(text)) return false;
  if (redFailureCountPattern.test(text) || mutationCountProofPattern.test(text)) return true;
  return !notRedProofPattern.test(text) && (redProofPattern.test(text) || mutationProofPattern.test(text));
}

export function hasGreenProof(text) {
  return !failedProofPattern.test(text) && greenProofPattern.test(text);
}

export function matchesTestFirstProofGuardrail(guardrail) {
  return guardrail?.id === 'test-first-proof' && guardrail?.stage === 'he-implement' && guardrail?.kind === 'test' && hasTestFirstProofCommand(guardrail?.command || '') && hasRedProof(evidenceText(guardrail));
}

export function matchesImplementationProofGuardrail(guardrail) {
  return guardrail?.id === 'implementation-proof' && guardrail?.stage === 'he-implement' && guardrail?.kind === 'test' && hasImplementationProofCommand(guardrail?.command || '') && hasGreenProof(evidenceText(guardrail));
}
