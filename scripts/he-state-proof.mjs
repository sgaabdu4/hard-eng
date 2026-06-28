const commandPrefix = String.raw`(?:^|(?:&&|\|\||;)\s*)\s*(?:env\s+)?(?:[A-Za-z_][A-Za-z0-9_]*=(?:"[^"]*"|'[^']*'|\S+)\s+)*`;
const testRunnerPattern = new RegExp(`${commandPrefix}(?:(?:npm|pnpm|yarn|bun)\\s+(?:test\\b|run\\s+(?:test(?::[\\w:-]+)?|spec|vitest|jest)\\b|exec\\s+(?:vitest|jest|mocha)\\b)|npx\\s+(?:vitest|jest|mocha)\\b|node\\s+--test\\b|(?:pytest|vitest|jest|mocha|ava|tap|flutter\\s+test|dart\\s+test|go\\s+test|cargo\\s+test|make\\s+test|rspec|phpunit|vendor\\/bin\\/phpunit|mvn\\s+test|gradle\\s+test|\\.\\/gradlew\\s+test)\\b)`, 'i');
const mutationCommandPattern = new RegExp(`${commandPrefix}(?:(?:npx\\s+)?stryker\\s+run\\b|npm\\s+run\\s+(?:mutation|mutate|mutants?|stryker)(?::[\\w:-]+)?\\b|(?:pnpm|yarn|bun)\\s+(?:run\\s+)?(?:mutation|mutate|mutants?|stryker)(?::[\\w:-]+)?\\b|(?:mutmut|infection|pitest)\\b|cargo\\s+mutants\\b|make\\s+(?:mutation|mutate|mutants?)\\b)`, 'i');
const makeItFailCommandPattern = new RegExp(`${commandPrefix}(?:npm\\s+run\\s+(?:make[-:]?it[-:]?fail|test[-:]?fail|fail[-:]?test)(?::[\\w:-]+)?\\b|(?:pnpm|yarn|bun)\\s+(?:run\\s+)?(?:make[-:]?it[-:]?fail|test[-:]?fail|fail[-:]?test)(?::[\\w:-]+)?\\b|make\\s+(?:make[- ]?it[- ]?fail|test[- ]?fail|fail[- ]?test)\\b)`, 'i');
const redProofPattern = /\b(?:red[- ]?first\s+(?:failed|failure|red|reproduced|confirmed|recorded|nonzero)|red\s+(?:state|run)\s+(?:recorded|confirmed|reproduced)|failed as expected|[1-9]\d*\s+(?:failing tests?|failures?|failed tests?)|failing tests?\s+(?:recorded|confirmed|reproduced|before implementation|as expected)|(?:recorded|confirmed|reproduced)\s+failing tests?)\b/i;
const mutationProofPattern = /\b(?:(?:mutation|mutants?).*(?:killed|detected|failed as expected)|(?:killed|detected).*(?:mutation|mutants?)|make[- ]?it[- ]?fail.*(?:failed as expected|reproduced|confirmed|red|nonzero))\b/i;
const notRedProofPattern = /\b(?:0\s+(?:failing tests?|failures?|failed tests?|(?:mutants?|mutations?)\s+(?:were\s+)?(?:killed|detected)|killed\s+(?:mutants?|mutations?))|0\s*\/\s*\d+\s+(?:mutants?|mutations?)\s+(?:killed|detected)|(?:killed|detected)\s+0\s+(?:mutants?|mutations?)|(?:mutants?|mutations?)\s+(?:were\s+)?(?:killed|detected)\s*[:=]\s*0|no\s+(?:failing tests?|failures?|failed tests?|mutants?\s+killed|(?:mutants?|mutations?)\s+(?:were\s+)?(?:killed|detected))|zero\s+(?:failing tests?|failures?|failed tests?|(?:mutants?|mutations?)\s+(?:killed|detected))|not failing|did not fail|didn't fail|not run|did not run|didn't run|skipped|pending|todo|green|clean|mutation\s+(?:not|was not|wasn't|did not|didn't)\s+(?:run|executed?|kill(?:ed)?))\b/i;
const greenProofPattern = /\b(?:all tests? passed|tests? passed|[1-9]\d*\s+(?:tests?|specs?|checks?|assertions?)?\s*passed|passed:\s*[1-9]\d*|green(?: test)? run)\b/i;
const failedProofPattern = /\b(?:not all (?:tests?|specs?|checks?) passed|no\s+(?:tests?|specs?|checks?)\s+passed|tests?\s+passed:\s*0|passed\s*[:=]\s*0|passed:\s*\d+[^.;\n]*(?:failed|failures?)\s*[:=]\s*[1-9]\d*|(?:failed|failures?)\s*[:=]\s*[1-9]\d*|did not pass|didn't pass|not pass(?:ed)?|not green|not clean|not success(?:ful)?|tests? failed|failed tests?|[1-9]\d*\s+(?:failing|failures?|failed)|failing tests?(?:\s+(?:remain|remaining|left|present))?|failures?(?:\s+(?:remain|remaining|left|present))?|red[- ]?first|failed as expected|mutation|make[- ]?it[- ]?fail|not run|did not run|didn't run|skipped|pending|todo|0\s+(?:tests?\s+)?passed|0\/\d+\s+passed)\b/i;

function evidenceText(guardrail) {
  return Array.isArray(guardrail?.evidence) ? guardrail.evidence.join(' ') : '';
}

export function hasTestFirstProofCommand(command) {
  return testRunnerPattern.test(command) || mutationCommandPattern.test(command) || makeItFailCommandPattern.test(command);
}

export function hasImplementationProofCommand(command) {
  return testRunnerPattern.test(command);
}

export function hasRedProof(text) {
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
