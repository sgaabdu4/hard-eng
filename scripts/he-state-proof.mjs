const assignmentPattern = /^[A-Za-z_][A-Za-z0-9_]*=/;
const assignmentNamePattern = /^([A-Za-z_][A-Za-z0-9_]*)(?:\+)?=/;
const packageManagers = new Set(['npm', 'pnpm', 'yarn', 'bun']);
const packageOptionValueFlags = new Set(['--prefix', '--filter', '--workspace', '-w', '-F', '--dir', '--cwd', '-C']);
const packageOptionBooleanFlags = new Set(['--workspace-root', '--recursive', '-r']);
const directTestRunners = new Set(['pytest', 'vitest', 'jest', 'mocha', 'ava', 'tap', 'rspec', 'phpunit', 'vendor/bin/phpunit']);
const npxTestRunners = new Set(['vitest', 'jest', 'mocha']);
const npxOptionBooleanFlags = new Set(['-y', '--yes']);
const testSubcommands = new Set(['spec', 'vitest', 'jest']);
const mutationCommands = new Set(['mutmut', 'infection', 'pitest']);
const noOpProofFlags = new Set(['--if-present', '--passwithnotests', '--pass-with-no-tests', '--help', '-h', '--version', '--dry-run', '--dryrun', '--list', '--list-tests', '--listtests', '--collect-only', '--co', '-list']);
const shadowableRunnerNames = new Set([
  ...packageManagers,
  ...npxTestRunners,
  ...mutationCommands,
  'ava',
  'cargo',
  'dart',
  'flutter',
  'go',
  'gradle',
  'jest',
  'make',
  'mocha',
  'mvn',
  'node',
  'npx',
  'phpunit',
  'pytest',
  'python',
  'python3',
  'rspec',
  'stryker',
  'tap',
]);
const shellControlFlowCommands = new Set(['if', 'then', 'else', 'elif', 'fi', 'case', 'esac', 'for', 'while', 'until', 'select', 'do', 'done']);
const terminalCommands = new Set(['exit', 'return', 'exec']);
const redProofPattern = /\b(?:red[- ]?first\s+(?:failed|failure|red|reproduced|confirmed|recorded|nonzero)|red\s+(?:state|run)\s+(?:recorded|confirmed|reproduced)|failed as expected|[1-9]\d*\s+(?:failing tests?|failures?|failed tests?)|failing tests?\s+(?:recorded|confirmed|reproduced|before implementation|as expected)|(?:recorded|confirmed|reproduced)\s+failing tests?)\b/i;
const mutationProofPattern = /\b(?:(?:mutation|mutants?)[^\n]*failed as expected|make[- ]?it[- ]?fail[^\n]*(?:failed as expected|reproduced|confirmed|red|nonzero))\b/i;
const redFailureCountPattern = /(?:^|[^\d/])(?:[1-9]\d*\s+(?:failed(?: tests?)?|tests?\s+failed|failing(?: tests?)?|failures?)|(?:failed tests?|tests?\s+failed|failing(?: tests?)?|failures?|failed)\s*[:=]\s*[1-9]\d*)\b/i;
const mutationCountProofPattern = /(?:^|[^\d/])(?:(?:[1-9]\d*\s+(?:mutants?|mutations?)\s+(?:were\s+)?(?:killed|detected))|(?:killed|detected)\s+[1-9]\d*\s+(?:mutants?|mutations?)|(?:mutants?|mutations?)\s+(?:were\s+)?(?:killed|detected)\s*[:=]\s*[1-9]\d*|(?:mutation|mutations?|mutants?)[^\n]*(?:killed|detected)\s*[:=]\s*[1-9]\d*|(?:killed|detected)\s*[:=]\s*[1-9]\d*[^\n]*(?:mutation|mutations?|mutants?))\b/i;
const notRedProofTerms = [
  String.raw`0\s+(?:failing(?: tests?)?|failures?|failed(?: tests?)?|tests?\s+failed|(?:mutants?|mutations?)\s+(?:were\s+)?(?:killed|detected)|killed\s+(?:mutants?|mutations?))`,
  String.raw`(?:failed tests?|failing tests?|failures?|failed)\s*[:=]\s*0`,
  String.raw`0\s*\/\s*\d+\s+(?:mutants?|mutations?)\s+(?:killed|detected)`,
  String.raw`(?:killed|detected)\s+0\s+(?:mutants?|mutations?)`,
  String.raw`(?:mutants?|mutations?)\s+(?:were\s+)?(?:killed|detected)\s*[:=]\s*0`,
  String.raw`(?:mutation|mutations?|mutants?)[^\n]*(?:killed|detected)\s*[:=]\s*0`,
  String.raw`(?:killed|detected)\s*[:=]\s*0[^\n]*(?:mutation|mutations?|mutants?)`,
  String.raw`(?:mutants?|mutations?)\s+(?:were\s+)?(?:killed|detected)\s*[:=]?\s*none`,
  String.raw`(?:killed|detected)\s*[:=]?\s*none[^\n]*(?:mutants?|mutations?)`,
  String.raw`(?:mutation|mutations?|mutants?)[^\n]*(?:0|zero|none)\s+(?:mutants?\s+|mutations?\s+)?(?:killed|detected)`,
  String.raw`(?:mutation|mutations?|mutants?)[^\n]*(?:killed|detected)\s*[:=]?\s*(?:0|zero|none)`,
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
const redCountContradictionTerms = [
  ...notRedProofTerms.filter((term) => term !== 'green' && term !== 'clean'),
  String.raw`all\s+tests?\s+passed`,
  String.raw`green(?:\s+test)?\s+run`,
  String.raw`clean\s+test\s+run`,
];
const redCountContradictionPattern = new RegExp(`\\b(?:${redCountContradictionTerms.join('|')})\\b`, 'i');
const expectedRedClausePattern = /\bexpected\b([^\n.;]*)\b(?:got|actual(?:ly)?|observed|received|but)\b([^\n.;]*)/gi;
const expectedFailurePattern = /\b(?:[1-9]\d*\s+)?(?:failed(?: tests?)?|tests?\s+failed|failing(?: tests?)?|failures?)(?:\s*[:=]\s*[1-9]\d*)?\b/i;
const actualPassedContradictionPattern = /\b(?:all\s+tests?\s+passed|[1-9]\d*\s+(?:tests?\s+)?passed|passed\s*[:=]\s*[1-9]\d*|0\s+(?:failed|failing|failures?|tests?\s+failed)|no\s+(?:failed|failing|failures?)|did not fail|didn't fail|passed|green|clean)\b/i;
const expectationOnlyFailurePattern = /\b(?:expected|should|would)\b[^\n.;]*\b(?:[1-9]\d*\s+(?:failed(?: tests?)?|tests?\s+failed|failing(?: tests?)?|failures?)|(?:failed tests?|tests?\s+failed|failing(?: tests?)?|failures?|failed)\s*[:=]\s*[1-9]\d*)\b/i;
const actualRedOutputPattern = /\b(?:actual(?:ly)?|observed|got|received)\b[^\n.;]*\b(?:[1-9]\d*\s+(?:failed(?: tests?)?|tests?\s+failed|failing(?: tests?)?|failures?)|(?:failed tests?|tests?\s+failed|failing(?: tests?)?|failures?|failed)\s*[:=]\s*[1-9]\d*)\b|\b(?:recorded|confirmed|reproduced)\b[^\n.;]*\b(?:red|nonzero|failed(?: tests?)?|tests?\s+failed|failing(?: tests?)?|failures?)\b|\b(?:[1-9]\d*\s+(?:failed(?: tests?)?|tests?\s+failed|failing(?: tests?)?|failures?)|(?:failed tests?|tests?\s+failed|failing(?: tests?)?|failures?|failed)\s*[:=]\s*[1-9]\d*)\b[^\n.;]*\b(?:recorded|confirmed|reproduced)\b/i;
const redProofContradictionPattern = new RegExp(`\\b(?:${notRedProofTerms.join('|')})\\b`, 'i');
const notRedProofPattern = new RegExp(`\\b(?:${[...notRedProofTerms, 'skipped', 'pending', 'todo'].join('|')})\\b`, 'i');
const greenProofPattern = /\b(?:all tests? passed|tests? passed|[1-9]\d*\s+(?:tests?|specs?|checks?|assertions?)?\s*(?:passed|passing)|passed:\s*[1-9]\d*|green(?: test)? run)\b/i;
const failedProofPattern = /\b(?:not all (?:tests?|specs?|checks?) passed|no\s+(?:tests?|specs?|checks?)\s+passed|tests?\s+passed:\s*0|passed\s*[:=]\s*0|passed\s*[:=]\s*\d+[^.;\n]*(?:failed|failures?|errors?|errored)\s*[:=]\s*[1-9]\d*|(?:failed|failures?|errors?|errored)\s*[:=]\s*[1-9]\d*|(?:failed|failures?|errors?|errored)\s+(?:[1-9]\d*|remain|remaining|left|present)|[1-9]\d*\s+(?:errors?|errored)|did not pass|didn't pass|not pass(?:ed)?|not green|not clean|not success(?:ful)?|tests? failed|failed tests?|[1-9]\d*\s+(?:failing|failures?|failed)|failing tests?(?:\s+(?:remain|remaining|left|present))?|failures?(?:\s+(?:remain|remaining|left|present))?|red[- ]?first|failed as expected|mutation|make[- ]?it[- ]?fail|not run|did not run|didn't run|0\s+(?:(?:tests?|specs?|checks?|assertions?)\s+)?(?:passed|passing)|0\/\d+\s+passed)\b/i;
const negatedTestQualityPattern = /\b(?:without|skipped?|no)\s+(?:the\s+)?test-quality\b|\b(?:did\s+not|didn't)\s+use\s+(?:the\s+)?test-quality\b|\bnot\s+using\s+(?:the\s+)?test-quality\b|\btest-quality(?:\s+(?:scenarios?|review|skill|use|used|evidence))?(?:\s+(?:is|are|was|were))?\s+(?:not\s+(?:used|loaded|run|applied|recorded|available)|wasn't\s+(?:used|loaded|run|applied|recorded)|skipped|missing|disabled|unavailable)\b/i;
const positiveTestQualityPattern = /\b(?:(?:used|using|loaded|ran|with|via|through|applied|recorded)\s+(?:the\s+)?test-quality(?:\s+(?:scenarios?|review|skill|evidence))?|test-quality(?:\s+(?:scenarios?|review|skill|evidence))?(?:\s+(?:is|are|was|were))?\s+(?:recorded|used|loaded|ran|applied))\b/i;

function evidenceText(guardrail) {
  return Array.isArray(guardrail?.evidence) ? guardrail.evidence.join(' ') : '';
}

function commandSubstitutionEnd(text, start) {
  let depth = 1;
  let quote = null;
  let escaped = false;
  for (let index = start + 2; index < text.length; index += 1) {
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
      if (char === '`') index = backtickEnd(text, index);
      if (char === '$' && text[index + 1] === '(') {
        depth += 1;
        index += 1;
      }
      continue;
    }
    if (char === "'" || char === '"') {
      quote = char;
      continue;
    }
    if (char === '`') {
      index = backtickEnd(text, index);
      continue;
    }
    if (char === '$' && text[index + 1] === '(') {
      depth += 1;
      index += 1;
      continue;
    }
    if (char === '(') {
      depth += 1;
      continue;
    }
    if (char === ')') {
      depth -= 1;
      if (depth === 0) return index;
    }
  }
  return text.length - 1;
}

function backtickEnd(text, start) {
  let escaped = false;
  for (let index = start + 1; index < text.length; index += 1) {
    const char = text[index];
    if (escaped) {
      escaped = false;
      continue;
    }
    if (char === '\\') {
      escaped = true;
      continue;
    }
    if (char === '`') return index;
  }
  return text.length - 1;
}

function shellCommandSegments(command) {
  const text = String(command || '');
  const segments = [];
  let start = 0;
  let separatorBefore = 'sequence';
  let quote = null;
  let escaped = false;
  const push = (end, separatorAfter = 'sequence') => {
    const segment = text.slice(start, end);
    if (segment.trim()) {
      segments.push({ segment, separator: separatorBefore, separatorAfter });
      separatorBefore = separatorAfter;
      return;
    }
    if ((separatorBefore === '&&' || separatorBefore === '||') && separatorAfter === 'sequence') return;
    separatorBefore = separatorAfter;
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
    if (char === '$' && text[index + 1] === '(') {
      index = commandSubstitutionEnd(text, index);
      continue;
    }
    if (char === '`') {
      index = backtickEnd(text, index);
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
    if (char === '#' && (index === start || /\s/.test(text[index - 1]))) {
      push(index, 'sequence');
      while (index < text.length && text[index] !== '\n') index += 1;
      start = index + 1;
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
    if (char === '&') {
      if (text[index + 1] === '>' || text[index - 1] === '>' || text[index - 1] === '<') continue;
      push(index, 'background');
      start = index + 1;
      continue;
    }
    if (char === '|') {
      push(index, '|');
      if (text[index + 1] === '&') index += 1;
      start = index + 1;
    }
  }
  push(text.length);
  return segments;
}

function shellWords(segment) {
  const text = String(segment || '');
  const words = [];
  let start = null;
  let quote = null;
  let escaped = false;
  const push = (end) => {
    if (start === null) return;
    const word = text.slice(start, end);
    if (word.trim()) words.push(word);
    start = null;
  };
  for (let index = 0; index < text.length; index += 1) {
    const char = text[index];
    if (start === null && !/\s/.test(char)) start = index;
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
    if (char === '$' && text[index + 1] === '(') {
      index = commandSubstitutionEnd(text, index);
      continue;
    }
    if (char === '`') {
      index = backtickEnd(text, index);
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
    if (/\s/.test(char)) push(index);
  }
  push(text.length);
  return words;
}

function lower(word) {
  return String(word || '').toLowerCase();
}

function commandWords(segment) {
  const words = shellWords(segment);
  let index = 0;
  if (lower(words[index]) === 'env') index += 1;
  while (assignmentPattern.test(words[index] || '')) index += 1;
  return words.slice(index);
}

function assignmentName(word) {
  return lower(String(word || '').match(assignmentNamePattern)?.[1]);
}

function hasCommandLookupOverride(segment) {
  const words = shellWords(segment);
  let index = lower(words[0]) === 'env' ? 1 : 0;
  while (assignmentPattern.test(words[index] || '')) {
    if (assignmentName(words[index]) === 'path') return true;
    index += 1;
  }
  if (lower(words[0]) === 'export') {
    for (const word of words.slice(1)) {
      if (assignmentName(word) === 'path') return true;
    }
  }
  return false;
}

function errexitMode(segment) {
  const words = commandWords(segment);
  if (lower(words[0]) !== 'set') return null;
  if (words.some((word) => word === '-e') || words.some((word, index) => word === '-o' && lower(words[index + 1]) === 'errexit')) return true;
  if (words.some((word) => word === '+e') || words.some((word, index) => word === '+o' && lower(words[index + 1]) === 'errexit')) return false;
  return null;
}

function staticCommandStatus(segment) {
  const mode = errexitMode(segment);
  if (mode !== null) return 'success';
  const words = commandWords(segment);
  let index = 0;
  let negated = false;
  while (words[index] === '!') {
    negated = !negated;
    index += 1;
  }
  const command = lower(words[index]);
  let status = null;
  if (command === 'true' || command === ':') status = 'success';
  if (command === 'false') status = 'failure';
  if (!status || !negated) return status;
  return status === 'success' ? 'failure' : 'success';
}

function possibleCommandStatuses(segment) {
  const status = staticCommandStatus(segment);
  return status ? [status] : ['success', 'failure'];
}

function startsShellControlFlow(segment) {
  return shellControlFlowCommands.has(lower(commandWords(segment)[0]));
}

function startsUnsupportedCompoundGroup(segment) {
  const command = lower(commandWords(segment)[0]);
  return command.startsWith('{') || command.startsWith('(') || command === '}' || command === ')';
}

function isTerminalCommand(segment) {
  const words = commandWords(segment);
  let index = 0;
  while (words[index] === '!') index += 1;
  return terminalCommands.has(lower(words[index]));
}

function definesShadowedRunner(segment) {
  const text = String(segment || '').trimStart();
  const nameMatch = text.match(/^([A-Za-z_][A-Za-z0-9_-]*)\s*\(\s*\)\s*(?:\{|$)/);
  const functionMatch = text.match(/^function\s+([A-Za-z_][A-Za-z0-9_-]*)\b/);
  const name = lower(nameMatch?.[1] || functionMatch?.[1]);
  return shadowableRunnerNames.has(name);
}

function definesRunnerOverride(segment) {
  if (definesShadowedRunner(segment)) return true;
  const words = commandWords(segment);
  const command = lower(words[0]);
  if (command === 'alias') {
    return words.slice(1).some((word) => shadowableRunnerNames.has(lower(String(word).match(/^([A-Za-z_][A-Za-z0-9_-]*)=/)?.[1])));
  }
  if (command !== 'hash') return false;
  const args = words.slice(1);
  if (args.some((word) => shadowableRunnerNames.has(assignmentName(word)))) return true;
  if (!args.some((word) => lower(word) === '-p' || lower(word).startsWith('-p'))) return false;
  return args.some((word) => shadowableRunnerNames.has(lower(word)));
}

function canDynamicallyOverrideRunner(segment) {
  return ['eval', 'source', '.'].includes(lower(commandWords(segment)[0]));
}

function skipPackageOptions(words, index) {
  while (index < words.length) {
    const word = lower(words[index]);
    if (word === '--') return index + 1;
    if (packageOptionValueFlags.has(word)) {
      index += 2;
      continue;
    }
    if (/^--(?:prefix|filter|workspace|dir|cwd)=/.test(word)) {
      index += 1;
      continue;
    }
    if (packageOptionBooleanFlags.has(word)) {
      index += 1;
      continue;
    }
    break;
  }
  return index;
}

function packageCommand(words) {
  const manager = lower(words[0]);
  if (!packageManagers.has(manager)) return null;
  let index = skipPackageOptions(words, 1);
  if (manager === 'yarn' && lower(words[index]) === 'workspace' && words[index + 1]) index += 2;
  return { manager, index };
}

function npxCommandIndex(words) {
  let index = 1;
  while (index < words.length) {
    const word = lower(words[index]);
    if (word === '--') return index + 1;
    if (!npxOptionBooleanFlags.has(word)) break;
    index += 1;
  }
  return index;
}

function isTestScript(word) {
  const value = lower(word);
  return value === 'test' || value.startsWith('test:') || testSubcommands.has(value);
}

function isMutationScript(word) {
  return /^(?:mutation|mutate|mutants?|stryker)(?::[\w:-]+)?$/i.test(word || '');
}

function isMakeItFailScript(word) {
  return /^(?:make[-:]?it[-:]?fail|test[-:]?fail|fail[-:]?test)(?::[\w:-]+)?$/i.test(word || '');
}

function hasNoOpProofOption(words) {
  return words.some((word) => noOpProofFlags.has(lower(word)) || /^(?:--(?:if-present|passwithnotests|pass-with-no-tests|help|version|dry-run|dryrun|list|listtests|list-tests|collect-only)|-list)(?:=|$)/i.test(word || ''));
}

function matchesPackageTest(words) {
  const command = packageCommand(words);
  if (!command) return false;
  const subcommand = lower(words[command.index]);
  if (subcommand === 'test') return true;
  if (command.manager !== 'npm' && isTestScript(subcommand)) return true;
  if (subcommand === 'run') return isTestScript(words[command.index + 1]);
  return subcommand === 'exec' && npxTestRunners.has(lower(words[command.index + 1]));
}

function matchesTestRunner(words) {
  if (hasNoOpProofOption(words)) return false;
  const command = lower(words[0]);
  if (matchesPackageTest(words)) return true;
  if (command === 'npx') return npxTestRunners.has(lower(words[npxCommandIndex(words)]));
  if (command === 'node') return lower(words[1]) === '--test';
  if (directTestRunners.has(command)) return true;
  if ((command === 'python' || command === 'python3') && lower(words[1]) === '-m') return lower(words[2]) === 'pytest';
  if (['flutter', 'dart', 'go', 'cargo', 'mvn', 'gradle'].includes(command)) return lower(words[1]) === 'test';
  if (command === 'make') return lower(words[1]) === 'test';
  return command === './gradlew' && lower(words[1]) === 'test';
}

function matchesMutationCommand(words) {
  if (hasNoOpProofOption(words)) return false;
  const command = lower(words[0]);
  const packageInfo = packageCommand(words);
  if (command === 'npx') {
    const index = npxCommandIndex(words);
    return lower(words[index]) === 'stryker' && lower(words[index + 1]) === 'run';
  }
  if (command === 'stryker') return lower(words[1]) === 'run';
  if (packageInfo) {
    const subcommand = lower(words[packageInfo.index]);
    if (packageInfo.manager === 'npm') return subcommand === 'run' && isMutationScript(words[packageInfo.index + 1]);
    return (subcommand === 'run' && isMutationScript(words[packageInfo.index + 1])) || isMutationScript(words[packageInfo.index]);
  }
  if (mutationCommands.has(command)) return true;
  if (command === 'cargo') return lower(words[1]) === 'mutants';
  return command === 'make' && /^(?:mutation|mutate|mutants?)$/i.test(words[1] || '');
}

function matchesMakeItFailCommand(words) {
  if (hasNoOpProofOption(words)) return false;
  const command = lower(words[0]);
  const packageInfo = packageCommand(words);
  if (packageInfo) {
    const subcommand = lower(words[packageInfo.index]);
    if (packageInfo.manager === 'npm') return subcommand === 'run' && isMakeItFailScript(words[packageInfo.index + 1]);
    return (subcommand === 'run' && isMakeItFailScript(words[packageInfo.index + 1])) || isMakeItFailScript(words[packageInfo.index]);
  }
  return command === 'make' && /^(?:make[- ]?it[- ]?fail|test[- ]?fail|fail[- ]?test)$/i.test(words[1] || '');
}

function isUnmaskedProofSegment(segments, index) {
  for (let cursor = index; cursor < segments.length; cursor += 1) {
    const separatorAfter = segments[cursor]?.separatorAfter;
    if (cursor === segments.length - 1) return separatorAfter === 'sequence';
    if (separatorAfter !== '&&') return false;
  }
  return false;
}

function hasCommandMatching(command, matcher) {
  const segments = shellCommandSegments(command);
  if (segments.some(({ segment }) => startsShellControlFlow(segment))) return false;
  if (segments.some(({ segment }) => startsUnsupportedCompoundGroup(segment))) return false;
  if (segments.some(({ segment }) => definesRunnerOverride(segment))) return false;
  if (segments.some(({ segment }) => hasCommandLookupOverride(segment))) return false;
  let statuses = new Set(['success']);
  let errexit = false;
  let dynamicRunnerOverride = false;
  for (let index = 0; index < segments.length; index += 1) {
    const { segment, separator, separatorAfter } = segments[index];
    const executeStatuses = new Set();
    const skippedStatuses = new Set();
    if (separator === '&&') {
      if (statuses.has('success')) executeStatuses.add('success');
      if (statuses.has('failure')) skippedStatuses.add('failure');
    } else if (separator === '||') {
      if (statuses.has('failure')) executeStatuses.add('failure');
      if (statuses.has('success')) skippedStatuses.add('success');
    } else {
      if (statuses.size > 0) executeStatuses.add('success');
    }
    const proofReachable = separator === '||' ? statuses.size === 1 && statuses.has('failure') : executeStatuses.size > 0;
    if (proofReachable && !dynamicRunnerOverride && matcher(commandWords(segment)) && isUnmaskedProofSegment(segments, index)) return true;
    const nextStatuses = new Set(skippedStatuses);
    if (executeStatuses.size > 0 && !isTerminalCommand(segment)) {
      if (canDynamicallyOverrideRunner(segment)) dynamicRunnerOverride = true;
      for (const status of possibleCommandStatuses(segment)) {
        if (errexit && status === 'failure' && separatorAfter === 'sequence') continue;
        nextStatuses.add(status);
      }
      const mode = errexitMode(segment);
      if (mode !== null) errexit = mode;
    }
    statuses = nextStatuses;
  }
  return false;
}

export function hasTestFirstProofCommand(command) {
  return hasCommandMatching(command, matchesTestRunner) || hasCommandMatching(command, matchesMutationCommand) || hasCommandMatching(command, matchesMakeItFailCommand);
}

export function hasImplementationProofCommand(command) {
  return hasCommandMatching(command, matchesTestRunner);
}

function hasExpectedRedContradiction(text) {
  for (const [, expected, actual] of String(text || '').matchAll(expectedRedClausePattern)) {
    if (expectedFailurePattern.test(expected) && actualPassedContradictionPattern.test(actual) && !redFailureCountPattern.test(actual)) return true;
  }
  return false;
}

function hasExpectationOnlyRedCount(text) {
  return expectationOnlyFailurePattern.test(text) && !actualRedOutputPattern.test(text);
}

export function hasRedProof(text) {
  if (redCountContradictionPattern.test(text) || hasExpectedRedContradiction(text) || hasExpectationOnlyRedCount(text)) return false;
  if (redFailureCountPattern.test(text) || mutationCountProofPattern.test(text)) return true;
  if (redProofContradictionPattern.test(text)) return false;
  return !notRedProofPattern.test(text) && (redProofPattern.test(text) || mutationProofPattern.test(text));
}

export function hasGreenProof(text) {
  return !failedProofPattern.test(text) && greenProofPattern.test(text);
}

export function hasTestQualityEvidence(guardrail) {
  const text = evidenceText(guardrail);
  return !negatedTestQualityPattern.test(text) && positiveTestQualityPattern.test(text);
}

export function matchesTestFirstProofGuardrail(guardrail) {
  return guardrail?.id === 'test-first-proof' && guardrail?.stage === 'he-implement' && guardrail?.kind === 'test' && hasTestFirstProofCommand(guardrail?.command || '') && hasRedProof(evidenceText(guardrail)) && hasTestQualityEvidence(guardrail);
}

export function matchesImplementationProofGuardrail(guardrail) {
  return guardrail?.id === 'implementation-proof' && guardrail?.stage === 'he-implement' && guardrail?.kind === 'test' && hasImplementationProofCommand(guardrail?.command || '') && hasGreenProof(evidenceText(guardrail));
}
