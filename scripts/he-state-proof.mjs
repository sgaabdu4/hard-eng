// HARD_ENG_SCANNER_OWNER
const assignmentPattern = /^[A-Za-z_][A-Za-z0-9_]*(?:\+)?=/;
const assignmentNamePattern = /^([A-Za-z_][A-Za-z0-9_]*)(?:\+)?=/;
const packageManagers = new Set(['npm', 'pnpm', 'yarn', 'bun']);
const packageOptionValueFlags = new Set(['--prefix', '--filter', '--workspace', '-f', '--dir', '--cwd', '-c']);
const packageCwdValueFlags = new Set(['--prefix', '--dir', '--cwd', '-c']);
const packageOptionBooleanFlags = new Set(['--workspace-root', '--workspaces', '--ws', '--recursive', '-r']);
const directTestRunners = new Set(['pytest', 'vitest', 'jest', 'mocha', 'ava', 'tap', 'rspec', 'phpunit', 'vendor/bin/phpunit']);
const npxTestRunners = new Set(['vitest', 'jest', 'mocha']);
const npxOptionBooleanFlags = new Set(['-y', '--yes']);
const mavenPathValueFlags = new Set(['-f', '--file']);
const mavenLeadingOptions = new Set(['-q', '--quiet', '-B', '--batch-mode', '-ntp', '--no-transfer-progress', '-U', '--update-snapshots', '-o', '--offline', '-e', '--errors', '-X', '--debug', '-V', '--show-version']);
const gradlePathValueFlags = new Set(['-p', '--project-dir', '-b', '--build-file', '-c', '--settings-file', '--include-build']);
const gradleLeadingOptions = new Set(['--no-daemon', '--daemon', '--offline', '--stacktrace', '--full-stacktrace', '--info', '-i', '--debug', '-d', '--quiet', '-q', '--warn', '-w', '--scan', '--no-scan', '--build-cache', '--no-build-cache', '--configuration-cache', '--no-configuration-cache', '--rerun-tasks', '--continue', '--parallel']);
const makePathValueFlags = new Set(['-f', '--file', '--makefile', '-c', '--directory']);
const testSubcommands = new Set(['spec', 'vitest', 'jest']);
const mutationCommands = new Set(['mutmut', 'infection', 'pitest']);
const noOpProofFlags = new Set(['--if-present', '--passwithnotests', '--pass-with-no-tests', '--help', '-h', '--version', '--dry-run', '--dryrun', '--list', '--list-tests', '--listtests', '--collect-only', '--co', '-list', '--no-run', '--norun', '--no-test', '--no-tests', '--no-execute', '--no-exec', '--skip-tests', '--skiptests']);
const pathChangingBuiltins = new Set(['export', 'typeset', 'declare', 'local', 'readonly']);
const proofEnvExportCommands = new Set(['export', 'typeset', 'declare', 'local', 'readonly']);
const shadowableRunnerNames = new Set([
  ...packageManagers, ...npxTestRunners, ...mutationCommands,
  'ava', 'cargo', 'dart', 'flutter', 'go', 'gradle', 'jest', 'make', 'mocha', 'mvn', 'mvnw',
  'env', 'node', 'npx', 'phpunit', 'pytest', 'python', 'python3', 'rspec', 'stryker', 'tap',
]);
const shellControlFlowCommands = new Set(['if', 'then', 'else', 'elif', 'fi', 'case', 'esac', 'for', 'while', 'until', 'select', 'do', 'done']);
const terminalCommands = new Set(['exit', 'return', 'exec']);
const staticSuccessCommands = new Set(['true', ':', 'echo', 'printf']);
const npmNoOpConfigAssignments = new Set(['npm_config_if_present', 'npm_config_ignore_scripts']);
const proofNoOpEnvAssignments = new Set(['pytest_addopts', ...npmNoOpConfigAssignments]);
const redProofPattern = /\b(?:red[- ]?first\s+(?:failed|failure|red|reproduced|confirmed|recorded|nonzero)|red\s+(?:state|run)\s+(?:recorded|confirmed|reproduced)|failed as expected|[1-9]\d*\s+(?:failing tests?|failures?|failed tests?)|failing tests?\s+(?:recorded|confirmed|reproduced|before implementation|as expected)|(?:recorded|confirmed|reproduced)\s+failing tests?)\b/i;
const mutationProofPattern = /\b(?:(?:mutation|mutants?)[^\n]*failed as expected|make[- ]?it[- ]?fail[^\n]*(?:failed as expected|reproduced|confirmed|red|nonzero))\b/i;
const makeItFailProofPattern = /\bmake[- ]?it[- ]?fail[^\n]*(?:failed as expected|reproduced|confirmed|red|nonzero)\b/i;
const redFailureCountPattern = /(?:^|[^\d/])(?:[1-9]\d*\s+(?:failed(?: tests?)?|tests?\s+failed|failing(?: tests?)?|failures?)|(?:failed tests?|tests?\s+failed|failing(?: tests?)?|failures?|failed)\s*[:=]\s*[1-9]\d*)\b/i;
const mutationCountProofPattern = /(?:^|[^\d/])(?:(?:[1-9]\d*\s+(?:mutants?|mutations?)\s+(?:were\s+)?\b(?:killed|detected)\b)|\b(?:killed|detected)\b\s+[1-9]\d*\s+(?:mutants?|mutations?)|(?:mutants?|mutations?)\s+(?:were\s+)?\b(?:killed|detected)\b\s*[:=]\s*[1-9]\d*|(?:mutation|mutations?|mutants?)[^\n]*\b(?:killed|detected)\b\s*[:=]\s*[1-9]\d*|\b(?:killed|detected)\b\s*[:=]\s*[1-9]\d*[^\n]*(?:mutation|mutations?|mutants?))\b/i;
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
  String.raw`(?:mutation|mutations?|mutants?)[^\n]*(?:not|was not|wasn't|did not|didn't)\s+fail(?:ed)?`,
  String.raw`(?:mutants?|mutations?)[^\n]*(?:not|was not|wasn't|did not|didn't)\s+(?:run|executed?|kill(?:ed)?|detected?)`,
];
const redCountContradictionTerms = [
  ...notRedProofTerms.filter((term) => term !== 'green' && term !== 'clean'),
  String.raw`all\s+tests?\s+passed`,
  String.raw`green(?:\s+test)?\s+run`,
  String.raw`clean\s+test\s+run`,
];
const mutationProofContradictionTerms = [
  String.raw`0\s+(?:(?:mutants?|mutations?)\s+(?:were\s+)?(?:killed|detected)|killed\s+(?:mutants?|mutations?))`,
  String.raw`0\s*\/\s*\d+\s+(?:mutants?|mutations?)\s+(?:killed|detected)`,
  String.raw`(?:killed|detected)\s+0\s+(?:mutants?|mutations?)`,
  String.raw`(?:mutants?|mutations?)\s+(?:were\s+)?(?:killed|detected)\s*[:=]\s*0`,
  String.raw`(?:mutation|mutations?|mutants?)[^\n]*(?:killed|detected)\s*[:=]\s*0`,
  String.raw`(?:killed|detected)\s*[:=]\s*0[^\n]*(?:mutation|mutations?|mutants?)`,
  String.raw`(?:mutants?|mutations?)\s+(?:were\s+)?(?:killed|detected)\s*[:=]?\s*none`,
  String.raw`(?:killed|detected)\s*[:=]?\s*none[^\n]*(?:mutants?|mutations?)`,
  String.raw`(?:mutation|mutations?|mutants?)[^\n]*(?:0|zero|none)\s+(?:mutants?\s+|mutations?\s+)?(?:killed|detected)`,
  String.raw`(?:mutation|mutations?|mutants?)[^\n]*(?:killed|detected)\s*[:=]?\s*(?:0|zero|none)`,
  String.raw`no\s+(?:mutants?\s+killed|(?:mutants?|mutations?)\s+(?:were\s+)?(?:killed|detected))`,
  String.raw`zero\s+(?:(?:mutants?|mutations?)\s+(?:killed|detected))`,
  String.raw`not run`,
  String.raw`did not run`,
  String.raw`didn't run`,
  String.raw`(?:mutation|mutations?|mutants?)[^\n]*(?:not|was not|wasn't|did not|didn't)\s+fail(?:ed)?`,
  String.raw`(?:mutants?|mutations?)[^\n]*(?:not|was not|wasn't|did not|didn't)\s+(?:run|executed?|kill(?:ed)?|detected?)`,
];
const redCountContradictionPattern = new RegExp(`\\b(?:${redCountContradictionTerms.join('|')})\\b`, 'i');
const mutationProofContradictionPattern = new RegExp(`\\b(?:${mutationProofContradictionTerms.join('|')})\\b`, 'i');
const makeItFailProofContradictionPattern = /\b(?:not run|did not run|didn't run|make[- ]?it[- ]?fail[^\n]*(?:not|was not|wasn't|did not|didn't)\s+(?:run|executed?|fail(?:ed)?)|make[- ]?it[- ]?fail[^\n]*(?:skipped|disabled|unavailable))\b/i;
const expectedRedClausePattern = /\bexpected\b([^\n.;]*)\b(?:got|actual(?:ly)?|observed|received|but)\b([^\n.;]*)/gi;
const expectedFailurePattern = /\b(?:[1-9]\d*\s+)?(?:failed(?: tests?)?|tests?\s+failed|failing(?: tests?)?|failures?)(?:\s*[:=]\s*[1-9]\d*)?\b/i;
const actualPassedContradictionPattern = /\b(?:all\s+tests?\s+passed|[1-9]\d*\s+(?:tests?\s+)?passed|passed\s*[:=]\s*[1-9]\d*|0\s+(?:failed|failing|failures?|tests?\s+failed)|no\s+(?:failed|failing|failures?)|did not fail|didn't fail|passed|green|clean)\b/i;
const expectationOnlyFailurePattern = /\b(?:expected|should|would)\b[^\n.;]*\b(?:[1-9]\d*\s+(?:failed(?: tests?)?|tests?\s+failed|failing(?: tests?)?|failures?)|(?:failed tests?|tests?\s+failed|failing(?: tests?)?|failures?|failed)\s*[:=]\s*[1-9]\d*)\b/i;
const actualRedOutputPattern = /\b(?:actual(?:ly)?|observed|got|received)\b[^\n.;]*\b(?:[1-9]\d*\s+(?:failed(?: tests?)?|tests?\s+failed|failing(?: tests?)?|failures?)|(?:failed tests?|tests?\s+failed|failing(?: tests?)?|failures?|failed)\s*[:=]\s*[1-9]\d*)\b|\b(?:recorded|confirmed|reproduced)\s+(?:red|nonzero|failure|failing|failed)\s+(?:test\s+)?(?:output|run|proof|result)\b|\b(?:red|nonzero|failure|failing|failed)\s+(?:test\s+)?(?:output|run|proof|result)\s+(?:recorded|confirmed|reproduced)\b/i;
const redProofContradictionPattern = new RegExp(`\\b(?:${notRedProofTerms.join('|')})\\b`, 'i');
const notRedProofPattern = new RegExp(`\\b(?:${[...notRedProofTerms, 'skipped', 'pending', 'todo'].join('|')})\\b`, 'i');
const greenProofPattern = /\b(?:all tests? passed|tests? passed|[1-9]\d*\s+(?:tests?|specs?|checks?|assertions?)?\s*(?:passed|passing)|passed:\s*[1-9]\d*|green(?: test)? run)\b/i;
const failedProofPattern = /\b(?:not all (?:tests?|specs?|checks?) passed|no\s+(?:tests?|specs?|checks?)\s+passed|tests?\s+passed:\s*0|passed\s*[:=]\s*0|passed\s*[:=]\s*\d+[^.;\n]*(?:failed|failures?|errors?|errored)\s*[:=]\s*[1-9]\d*|(?:failed|failures?|errors?|errored)\s*[:=]\s*[1-9]\d*|(?:failed|failures?|errors?|errored)\s+(?:[1-9]\d*|remain|remaining|left|present)|[1-9]\d*\s+(?:errors?|errored)|did not pass|didn't pass|not pass(?:ed)?|not green|not clean|not success(?:ful)?|tests? failed|failed tests?|[1-9]\d*\s+(?:failing|failures?|failed)|failing tests?(?:\s+(?:remain|remaining|left|present))?|failures?(?:\s+(?:remain|remaining|left|present))?|red[- ]?first|failed as expected|mutation|make[- ]?it[- ]?fail|not run|did not run|didn't run|0\s+(?:(?:tests?|specs?|checks?|assertions?)\s+)?(?:passed|passing)|0\/\d+\s+passed)\b/i;
const expectationOnlyGreenPattern = /\b(?:expected|should|would)\b[^\n.;]*\b(?:all tests? passed|tests? passed|passed|passing|green|clean)\b/i;
const actualGreenOutputPattern = /\b(?:actual(?:ly)?|observed|got|received)\b[^\n.;]*\b(?:all tests? passed|tests? passed|passed|passing|green|clean)\b|\b(?:recorded|confirmed|reproduced)\s+(?:green|clean|passing|passed)(?:\s+(?:test\s+)?(?:output|run|state|proof|result))?\b|\b(?:green|clean|passing|passed)(?:\s+(?:test\s+)?(?:output|run|state|proof|result))?\s+(?:recorded|confirmed|reproduced)\b/i;
const negatedTestQualityPattern = /\b(?:without|skipped?|no)\s+(?:the\s+)?test-quality\b|\b(?:no|without)\s+(?:recorded|used|using|loaded|ran|applied)\s+(?:the\s+)?test-quality\b|\b(?:not|never)\s+(?:recorded|used|using|loaded|ran|with|via|through|applied)\s+(?:the\s+)?test-quality\b|\b(?:did\s+not|didn't|failed\s+to)\s+(?:record|use|load|run|apply)\s+(?:the\s+)?test-quality\b|\bnot\s+using\s+(?:the\s+)?test-quality\b|\btest-quality(?:\s+(?:scenarios?|review|skill|use|used|evidence))?(?:\s+(?:is|are|was|were))?\s+(?:not\s+(?:used|loaded|run|applied|recorded|available)|wasn't\s+(?:used|loaded|run|applied|recorded)|skipped|missing|disabled|unavailable)\b/i;
const positiveTestQualityPattern = /\b(?:(?:used|using|loaded|ran|with|via|through|applied|recorded)\s+(?:the\s+)?test-quality(?:\s+(?:scenarios?|review|skill|evidence))?|test-quality(?:\s+(?:scenarios?|review|skill|evidence))?(?:\s+(?:is|are|was|were))?\s+(?:recorded|used|loaded|ran|applied))\b/i;

function evidenceText(guardrail) {
  return Array.isArray(guardrail?.evidence) ? guardrail.evidence.join(' ') : '';
}

function normalizedTestQualityEvidence(text) {
  return String(text || '').replace(/`test-quality`/gi, 'test-quality');
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

function hasUnsupportedShellFeature(command) {
  const text = String(command || '');
  let quote = null;
  let escaped = false;
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
      return true;
    }
    if (char === '`') {
      return true;
    }
    if (startsShellParameterExpansion(text, index)) {
      return true;
    }
    if (quote === '"') {
      if (char === '"') quote = null;
      continue;
    }
    if (char === "'" || char === '"') {
      quote = char;
      continue;
    }
    if (char === '{' && shellBraceExpansionEnd(text, index) !== -1) {
      return true;
    }
    if (char === '*' || char === '?' || char === '[') return true;
    if ((char === '$' && (text[index + 1] === "'" || text[index + 1] === '"')) || char === '<' || char === '>' || (char === '=' && text[index + 1] === '(')) return true;
  }
  return false;
}

function shellBraceExpansionEnd(text, start) {
  let depth = 1;
  let quote = null;
  let escaped = false;
  let hasExpansionOperator = false;
  for (let index = start + 1; index < text.length; index += 1) {
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
    if (char === '{') {
      depth += 1;
      continue;
    }
    if (char === '}') {
      depth -= 1;
      if (depth === 0) return hasExpansionOperator ? index : -1;
      continue;
    }
    if (depth === 1 && (char === ',' || (char === '.' && text[index + 1] === '.'))) hasExpansionOperator = true;
  }
  return -1;
}

function startsShellParameterExpansion(text, index) {
  if (text[index] !== '$') return false;
  const next = text[index + 1];
  if (!next || next === '(' || next === "'" || next === '"') return false;
  return next === '{' || /[A-Za-z0-9_@*#?$!-]/.test(next);
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

function isMavenCommand(command) {
  return ['mvn', 'mvnw', './mvnw'].includes(lower(command));
}

function shellWordValue(word) {
  return String(word || '').replace(/(^|=)\$(?=['"])/g, '$1').replace(/\\([\s\S])/g, '$1').replace(/['"]/g, '');
}

function commandWords(segment) {
  const words = shellWords(segment);
  let index = 0;
  if (lower(shellWordValue(words[index])) === 'env') index += 1;
  while (assignmentPattern.test(words[index] || '')) index += 1;
  return words.slice(index).map(shellWordValue);
}

function leadingCommandAssignments(segment) {
  const words = shellWords(segment);
  let index = 0;
  if (lower(shellWordValue(words[index])) === 'env') index += 1;
  const assignments = [];
  while (assignmentPattern.test(words[index] || '')) {
    const assignment = assignmentParts(shellWordValue(words[index]));
    if (assignment) assignments.push(assignment);
    index += 1;
  }
  return assignments;
}

function effectiveCommandWords(segment) {
  const words = commandWords(segment);
  return ['builtin', 'command'].includes(lower(words[0])) ? words.slice(1) : words;
}

function assignmentName(word) {
  return lower(String(word || '').match(assignmentNamePattern)?.[1]);
}

function assignmentParts(word) {
  const match = String(word || '').match(/^([A-Za-z_][A-Za-z0-9_]*)(\+)?=(.*)$/);
  return match ? { name: lower(match[1]), append: match[2] === '+', value: match[3] } : null;
}

function hasCommandLookupOverride(segment) {
  const words = shellWords(segment).map(shellWordValue);
  let index = lower(words[0]) === 'env' ? 1 : 0;
  while (assignmentPattern.test(words[index] || '')) {
    if (assignmentName(words[index]) === 'path') return true;
    index += 1;
  }
  const effective = effectiveCommandWords(segment);
  if (pathChangingBuiltins.has(lower(effective[0]))) {
    for (const word of effective.slice(1)) {
      if (assignmentName(word) === 'path') return true;
    }
  }
  return false;
}

function setOptionMode(segment, shortFlag, optionName) {
  const words = effectiveCommandWords(segment);
  if (lower(words[0]) !== 'set') return null;
  let mode = null;
  for (let index = 1; index < words.length; index += 1) {
    const word = lower(words[index]);
    if (!/^[+-][a-z]+$/.test(word)) continue;
    const flags = word.slice(1);
    if (flags.includes('o') && lower(words[index + 1]) === optionName) mode = word[0] === '-';
    if (shortFlag && flags !== 'o' && flags.includes(shortFlag)) mode = word[0] === '-';
  }
  return mode;
}

function errexitMode(segment) { return setOptionMode(segment, 'e', 'errexit'); }

function pipefailMode(segment) { return setOptionMode(segment, null, 'pipefail'); }

function allexportMode(segment) { return setOptionMode(segment, 'a', 'allexport'); }

function staticCommandStatus(segment) {
  if (errexitMode(segment) !== null || pipefailMode(segment) !== null || allexportMode(segment) !== null) return 'success';
  const words = effectiveCommandWords(segment);
  let index = 0;
  let negated = false;
  while (words[index] === '!') {
    negated = !negated;
    index += 1;
  }
  const command = lower(words[index]);
  let status = null;
  if (staticSuccessCommands.has(command)) status = 'success';
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
  const words = effectiveCommandWords(segment);
  let index = 0;
  while (words[index] === '!') index += 1;
  return terminalCommands.has(lower(words[index]));
}

function definesShadowedRunner(segment) {
  const text = String(segment || '').trimStart();
  const nameMatch = text.match(/^([A-Za-z_][A-Za-z0-9_-]*)\s*\(\s*\)\s*(?:\{|\(|$)/);
  const functionMatch = text.match(/^function\s+([A-Za-z_][A-Za-z0-9_-]*)\b/);
  const name = lower(nameMatch?.[1] || functionMatch?.[1]);
  return shadowableRunnerNames.has(name);
}

function definesRunnerOverride(segment) {
  if (definesShadowedRunner(segment)) return true;
  const words = effectiveCommandWords(segment);
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
  return ['eval', 'source', '.'].includes(lower(effectiveCommandWords(segment)[0]));
}

function hasStatusAlteringHook(segment) {
  return lower(effectiveCommandWords(segment)[0]) === 'trap';
}

function changesWorkingDirectory(segment) {
  return ['cd', 'pushd', 'popd', 'chdir'].includes(lower(effectiveCommandWords(segment)[0]));
}

function isSafeProofPathValue(word) {
  const value = shellWordValue(word);
  if (!value || /[`$]/.test(value)) return false;
  if (value.startsWith('/') || value.startsWith('~') || value.startsWith('\\\\') || /^[A-Za-z]:[\\/]/.test(value)) return false;
  return !value.split(/[\\/]+/).includes('..');
}

function hasUnsafePathValueOption(words, valueFlags, longInlinePattern, shortFlags = []) {
  for (let index = 0; index < words.length; index += 1) {
    const rawWord = String(words[index] || '');
    const word = lower(rawWord);
    if (valueFlags.has(word)) {
      if (!isSafeProofPathValue(words[index + 1])) return true;
      index += 1;
      continue;
    }
    const inlineMatch = rawWord.match(longInlinePattern);
    if (inlineMatch) {
      if (!isSafeProofPathValue(inlineMatch[1])) return true;
      continue;
    }
    for (const flag of shortFlags) {
      if (word.startsWith(lower(flag)) && rawWord.length > flag.length) {
        if (!isSafeProofPathValue(rawWord.slice(flag.length))) return true;
        break;
      }
    }
  }
  return false;
}

function skipSafePathValueOption(words, index, valueFlags, longInlinePattern, shortFlags = []) {
  const rawWord = String(words[index] || '');
  const word = lower(rawWord);
  if (valueFlags.has(word) && isSafeProofPathValue(words[index + 1])) return index + 2;
  const inlineMatch = rawWord.match(longInlinePattern);
  if (inlineMatch?.[1] && isSafeProofPathValue(inlineMatch[1])) return index + 1;
  for (const flag of shortFlags) {
    if (word.startsWith(lower(flag)) && rawWord.length > flag.length && isSafeProofPathValue(rawWord.slice(flag.length))) return index + 1;
  }
  return index;
}

function skipPackageOptions(words, index, manager) {
  while (index < words.length) {
    const rawWord = shellWordValue(words[index]);
    const word = lower(rawWord);
    if (word === '--') return index + 1;
    if (word === '-w') {
      index += manager === 'pnpm' ? 1 : 2;
      continue;
    }
    if (packageOptionValueFlags.has(word)) {
      if (packageCwdValueFlags.has(word) && !isSafeProofPathValue(words[index + 1])) return -1;
      index += 2;
      continue;
    }
    const cwdValueMatch = rawWord.match(/^--(?:prefix|dir|cwd)=(.*)$/i);
    if (cwdValueMatch) {
      if (!isSafeProofPathValue(cwdValueMatch[1])) return -1;
      index += 1;
      continue;
    }
    if (/^--(?:filter|workspace)=/i.test(rawWord)) {
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
  let index = skipPackageOptions(words, 1, manager);
  if (index < 0) return null;
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

function buildToolTaskIndex(words, tool) {
  let index = 1;
  while (index < words.length) {
    const rawWord = String(words[index] || '');
    const word = lower(rawWord);
    if (word === '--') return index + 1;
    if (isMavenCommand(tool)) {
      const nextIndex = skipSafePathValueOption(words, index, mavenPathValueFlags, /^--file=(.*)$/i, ['-f']);
      if (nextIndex !== index) {
        index = nextIndex;
        continue;
      }
    }
    if ((tool === 'gradle' || tool === './gradlew')) {
      const nextIndex = skipSafePathValueOption(words, index, gradlePathValueFlags, /^--(?:project-dir|build-file|settings-file|include-build)=(.*)$/i, ['-p', '-b', '-c']);
      if (nextIndex !== index) {
        index = nextIndex;
        continue;
      }
    }
    if (isMavenCommand(tool) && (mavenLeadingOptions.has(word) || /^-D[\w.-]+(?:=.*)?$/i.test(rawWord))) {
      index += 1;
      continue;
    }
    if ((tool === 'gradle' || tool === './gradlew') && (gradleLeadingOptions.has(word) || /^-[DP][\w.-]+(?:=.*)?$/i.test(rawWord) || /^--(?:console|warning-mode)=.+$/i.test(rawWord))) {
      index += 1;
      continue;
    }
    break;
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

function isTruthyConfigValue(value) {
  const normalized = String(value || '').trim();
  return normalized === '' || /^(?:1|true|yes|on)$/i.test(normalized);
}

function hasNoOpProofEnvValue(name, value) {
  if (name === 'pytest_addopts') return shellWords(value).map(shellWordValue).some(isNoOpProofFlag);
  return npmNoOpConfigAssignments.has(name) && isTruthyConfigValue(value);
}

function setProofEnvValue(state, name, value, append = false) {
  if (!proofNoOpEnvAssignments.has(name)) return;
  const nextValue = append ? `${state.values.get(name) || ''}${value}` : value;
  state.values.set(name, nextValue);
  if (state.exportAll) state.exported.add(name);
  if (!state.exported.has(name)) return;
  if (hasNoOpProofEnvValue(name, nextValue)) state.noOp.add(name);
  else state.noOp.delete(name);
}

function exportProofEnvName(state, name) {
  if (!proofNoOpEnvAssignments.has(name)) return;
  state.exported.add(name);
  if (state.values.has(name) && hasNoOpProofEnvValue(name, state.values.get(name))) state.noOp.add(name);
  else state.noOp.delete(name);
}

function unexportProofEnvName(state, name) {
  if (!proofNoOpEnvAssignments.has(name)) return;
  state.exported.delete(name);
  state.noOp.delete(name);
}

function unsetProofEnvName(state, name) {
  if (!proofNoOpEnvAssignments.has(name)) return;
  state.values.delete(name);
  state.exported.delete(name);
  state.noOp.delete(name);
}

function applyAssignmentOnlyProofEnv(segment, state) {
  const words = shellWords(segment).map(shellWordValue);
  if (words.length === 0 || lower(words[0]) === 'env' || !words.every((word) => assignmentPattern.test(word))) return;
  for (const word of words) {
    const assignment = assignmentParts(word);
    if (assignment) setProofEnvValue(state, assignment.name, assignment.value, assignment.append);
  }
}

function exportModeFlag(word) {
  const value = lower(word);
  if (value === '-n' || value === '+x') return false;
  if (value === '-x') return true;
  if (/^-[A-Za-z]+$/.test(value) && value.includes('x')) return true;
  if (/^\+[A-Za-z]+$/.test(value) && value.includes('x')) return false;
  return null;
}

function applyExportProofEnv(segment, state) {
  const words = effectiveCommandWords(segment).map(shellWordValue);
  const command = lower(words[0]);
  if (!proofEnvExportCommands.has(command)) return;
  let exportMode = command === 'export' ? true : null;
  for (const word of words.slice(1)) {
    const value = lower(word);
    if (value === '--') continue;
    const flagMode = exportModeFlag(value);
    if (flagMode !== null) {
      exportMode = flagMode;
      continue;
    }
    if (value.startsWith('-') || value.startsWith('+')) continue;
    const assignment = assignmentParts(word);
    if (assignment) {
      setProofEnvValue(state, assignment.name, assignment.value, assignment.append);
      if (exportMode === false) unexportProofEnvName(state, assignment.name);
      else if (exportMode === true) exportProofEnvName(state, assignment.name);
      continue;
    }
    if (exportMode === false) unexportProofEnvName(state, value);
    else if (exportMode === true) exportProofEnvName(state, value);
  }
}

function applyUnsetProofEnv(segment, state) {
  const words = effectiveCommandWords(segment).map(shellWordValue);
  if (lower(words[0]) !== 'unset') return;
  for (const word of words.slice(1)) {
    const value = lower(word);
    if (value === '--' || value.startsWith('-')) continue;
    unsetProofEnvName(state, value);
  }
}

function applyProofEnvUpdates(segment, state) {
  applyAssignmentOnlyProofEnv(segment, state);
  applyExportProofEnv(segment, state);
  applyUnsetProofEnv(segment, state);
  const mode = allexportMode(segment);
  if (mode !== null) state.exportAll = mode;
}

function isNoOpProofFlag(word) {
  return noOpProofFlags.has(lower(word)) || /^(?:--(?:if-present|passwithnotests|pass-with-no-tests|help|version|dry-run|dryrun|list|listtests|list-tests|collect-only|co|no-run|norun|no-test|no-tests|no-execute|no-exec|skip-tests|skiptests)|-list)(?:=|$)/i.test(word || '') || hasTruthyMavenSkipTestsOption(word);
}

function hasNoOpProofAssignment(segment, words) {
  const assignments = leadingCommandAssignments(segment);
  if (assignments.length === 0) return false;
  const command = lower(words[0]);
  if (command === 'pytest' || ((command === 'python' || command === 'python3') && lower(words[1]) === '-m' && lower(words[2]) === 'pytest')) {
    if (assignments.some(({ name, value }) => name === 'pytest_addopts' && shellWords(value).map(shellWordValue).some(isNoOpProofFlag))) return true;
  }
  if (packageManagers.has(command)) {
    return assignments.some(({ name, value }) => npmNoOpConfigAssignments.has(name) && isTruthyConfigValue(value));
  }
  return false;
}

function hasExportedNoOpProofEnv(words, exportedNoOpProofEnv) {
  const command = lower(words[0]);
  if (command === 'pytest' || ((command === 'python' || command === 'python3') && lower(words[1]) === '-m' && lower(words[2]) === 'pytest')) {
    return exportedNoOpProofEnv.has('pytest_addopts');
  }
  if (packageManagers.has(command)) {
    return [...npmNoOpConfigAssignments].some((name) => exportedNoOpProofEnv.has(name));
  }
  return false;
}

function hasNoOpProofOption(words, segment = '', exportedNoOpProofEnv = new Set()) {
  const normalized = words.map(shellWordValue);
  if (hasNoOpProofAssignment(segment, normalized)) return true;
  if (hasExportedNoOpProofEnv(normalized, exportedNoOpProofEnv)) return true;
  if (hasGradleNoOpProofOption(normalized)) return true;
  if (hasMakeNoOpProofOption(normalized)) return true;
  if (hasUnsafePathOverrideProofOption(normalized)) return true;
  if (hasRunnerMetadataNoOpProofOption(normalized)) return true;
  return normalized.some(isNoOpProofFlag);
}

function hasTruthyMavenSkipTestsOption(word) {
  const match = String(word || '').match(/^-D(?:skipTests|maven\.test\.skip)(?:=(.*))?$/i);
  if (!match) return false;
  const value = match[1];
  return value === undefined || value.trim() === '' || /^(?:true|1|yes|on)$/i.test(value.trim());
}

function gradleTaskName(word) {
  const parts = lower(word).split(':').filter(Boolean);
  return parts.length === 0 ? lower(word) : parts[parts.length - 1];
}

function isGradleTestTask(word) {
  return gradleTaskName(word) === 'test';
}

function hasGradleNoOpProofOption(words) {
  const command = lower(words[0]);
  if (command !== 'gradle' && command !== './gradlew') return false;
  return words.some((word, index) => {
    const value = lower(word);
    const excludeTask = value.match(/^--exclude-task=(.+)$/)?.[1];
    return value === '-m' || (value === '-x' && isGradleTestTask(words[index + 1])) || (value === '--exclude-task' && isGradleTestTask(words[index + 1])) || (excludeTask && isGradleTestTask(excludeTask));
  });
}

function isMakeNoOpProofOption(word) {
  const value = lower(word);
  if (/^--(?:just-print|dry-run|recon|question|touch)(?:=|$)/i.test(value)) return true;
  return /^-[A-Za-z]+$/.test(value) && /[nqt]/.test(value.slice(1));
}

function hasMakeNoOpProofOption(words) {
  if (lower(words[0]) !== 'make') return false;
  for (const word of words.slice(1)) {
    if (word === '--') return false;
    if (isMakeNoOpProofOption(word)) return true;
  }
  return false;
}

function hasUnsafePathOverrideProofOption(words) {
  const command = lower(words[0]);
  if (packageManagers.has(command) && hasUnsafePathValueOption(words, packageCwdValueFlags, /^--(?:prefix|dir|cwd)=(.*)$/i, ['-c'])) return true;
  if (isMavenCommand(command)) return hasUnsafePathValueOption(words, mavenPathValueFlags, /^--file=(.*)$/i, ['-f']);
  if (command === 'gradle' || command === './gradlew') {
    return hasUnsafePathValueOption(words, gradlePathValueFlags, /^--(?:project-dir|build-file|settings-file|include-build)=(.*)$/i, ['-p', '-b', '-c']);
  }
  if (command === 'make') return hasUnsafePathValueOption(words, makePathValueFlags, /^--(?:file|makefile|directory)=(.*)$/i, ['-f', '-C']);
  return hasUnsafeDirectRunnerPathOverride(words);
}

function directRunnerOptionStart(words) {
  const command = lower(words[0]);
  if (directTestRunners.has(command)) return { runner: command, start: 1 };
  if ((command === 'python' || command === 'python3') && lower(words[1]) === '-m' && lower(words[2]) === 'pytest') return { runner: 'pytest', start: 3 };
  if (command === 'npx') {
    const index = npxCommandIndex(words);
    const runner = lower(words[index]);
    return npxTestRunners.has(runner) ? { runner, start: index + 1 } : null;
  }
  const packageInfo = packageCommand(words);
  if (packageInfo && lower(words[packageInfo.index]) === 'exec' && npxTestRunners.has(lower(words[packageInfo.index + 1]))) {
    return { runner: lower(words[packageInfo.index + 1]), start: packageInfo.index + 2 };
  }
  return null;
}

function hasUnsafeDirectRunnerPathOverride(words) {
  const info = directRunnerOptionStart(words);
  if (!info) return false;
  const runnerWords = words.slice(info.start);
  if (info.runner === 'pytest') return hasUnsafePathValueOption(runnerWords, new Set(['-c', '--rootdir']), /^--rootdir=(.*)$/i, ['-c']);
  if (info.runner === 'jest') return hasUnsafePathValueOption(runnerWords, new Set(['-c', '--config']), /^--config=(.*)$/i, ['-c']);
  if (info.runner === 'vitest') return hasUnsafePathValueOption(runnerWords, new Set(['-c', '--config', '-r', '--root']), /^--(?:config|root)=(.*)$/i, ['-c', '-r']);
  return false;
}

function hasPytestMetadataNoOpProofOption(words) {
  const command = lower(words[0]);
  const start = command === 'pytest' ? 1 : (command === 'python' || command === 'python3') && lower(words[1]) === '-m' && lower(words[2]) === 'pytest' ? 3 : -1;
  if (start < 0) return false;
  return words.slice(start).some((word) => /^(?:--fixtures(?:-per-test)?|--markers|--setup-(?:only|plan))(?:=|$)/i.test(word));
}

function hasJestMetadataNoOpProofOption(words) {
  const command = lower(words[0]);
  let start = command === 'jest' ? 1 : -1;
  if (command === 'npx') {
    const index = npxCommandIndex(words);
    if (lower(words[index]) === 'jest') start = index + 1;
  }
  const packageInfo = packageCommand(words);
  if (packageInfo && lower(words[packageInfo.index]) === 'exec' && lower(words[packageInfo.index + 1]) === 'jest') start = packageInfo.index + 2;
  if (start < 0) return false;
  return words.slice(start).some((word) => /^(?:--showconfig|--clearcache)(?:=|$)/i.test(word));
}

function hasGoNoOpProofOption(words) {
  if (lower(words[0]) !== 'go' || lower(words[1]) !== 'test') return false;
  return words.some((word, index) => {
    const value = lower(word);
    return value === '-run=^$' || value === '--run=^$' || ((value === '-run' || value === '--run') && lower(words[index + 1]) === '^$');
  });
}

function hasRunnerMetadataNoOpProofOption(words) {
  return hasPytestMetadataNoOpProofOption(words) || hasJestMetadataNoOpProofOption(words) || hasGoNoOpProofOption(words);
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

function matchesTestRunner(words, segment, exportedNoOpProofEnv) {
  if (hasNoOpProofOption(words, segment, exportedNoOpProofEnv)) return false;
  const command = lower(words[0]);
  if (matchesPackageTest(words)) return true;
  if (command === 'npx') return npxTestRunners.has(lower(words[npxCommandIndex(words)]));
  if (command === 'node') return lower(words[1]) === '--test';
  if (directTestRunners.has(command)) return true;
  if ((command === 'python' || command === 'python3') && lower(words[1]) === '-m') return lower(words[2]) === 'pytest';
  if (['flutter', 'dart', 'go', 'cargo'].includes(command)) return lower(words[1]) === 'test';
  if (isMavenCommand(command)) return lower(words[buildToolTaskIndex(words, command)]) === 'test';
  if (command === 'gradle' || command === './gradlew') return isGradleTestTask(words[buildToolTaskIndex(words, command)]);
  if (command === 'make') return lower(words[1]) === 'test';
  return false;
}

function matchesMutationCommand(words, segment, exportedNoOpProofEnv) {
  if (hasNoOpProofOption(words, segment, exportedNoOpProofEnv)) return false;
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

function matchesMakeItFailCommand(words, segment, exportedNoOpProofEnv) {
  if (hasNoOpProofOption(words, segment, exportedNoOpProofEnv)) return false;
  const command = lower(words[0]);
  const packageInfo = packageCommand(words);
  if (packageInfo) {
    const subcommand = lower(words[packageInfo.index]);
    if (packageInfo.manager === 'npm') return subcommand === 'run' && isMakeItFailScript(words[packageInfo.index + 1]);
    return (subcommand === 'run' && isMakeItFailScript(words[packageInfo.index + 1])) || isMakeItFailScript(words[packageInfo.index]);
  }
  return command === 'make' && /^(?:make[- ]?it[- ]?fail|test[- ]?fail|fail[- ]?test)$/i.test(words[1] || '');
}

function isUnmaskedProofSegment(segments, index, errexit) {
  let activeErrexit = errexit;
  for (let cursor = index; cursor < segments.length; cursor += 1) {
    const segment = segments[cursor]?.segment;
    if (cursor > index && (isTerminalCommand(segment) || staticCommandStatus(segment) === 'failure')) return false;
    const separatorAfter = segments[cursor]?.separatorAfter;
    if (cursor === segments.length - 1) return separatorAfter === 'sequence';
    if (separatorAfter !== '&&' && !(activeErrexit && separatorAfter === 'sequence')) return false;
    const mode = errexitMode(segment);
    if (mode !== null) activeErrexit = mode;
  }
  return false;
}

function hasCommandMatching(command, matcher) {
  if (hasUnsupportedShellFeature(command)) return false;
  const segments = shellCommandSegments(command);
  if (segments.some(({ segment }) => startsShellControlFlow(segment))) return false;
  if (segments.some(({ segment }) => startsUnsupportedCompoundGroup(segment))) return false;
  if (segments.some(({ segment }) => definesRunnerOverride(segment))) return false;
  if (segments.some(({ segment }) => hasCommandLookupOverride(segment))) return false;
  if (segments.some(({ segment }) => hasStatusAlteringHook(segment))) return false;
  if (segments.some(({ segment }) => changesWorkingDirectory(segment))) return false;
  let statuses = new Set(['success']);
  let errexit = false;
  let pipefail = false;
  let dynamicRunnerOverride = false;
  const proofEnvState = { values: new Map(), exported: new Set(), noOp: new Set(), exportAll: false };
  for (let index = 0; index < segments.length; index += 1) {
    const { segment, separator, separatorAfter } = segments[index];
    if (pipefail && (separator === '|' || separatorAfter === '|')) return false;
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
    const proofReachable = separator === '&&' ? statuses.size === 1 && statuses.has('success') : separator === '||' ? statuses.size === 1 && statuses.has('failure') : executeStatuses.size > 0;
    const words = commandWords(segment);
    if (proofReachable && !dynamicRunnerOverride && matcher(words, segment, proofEnvState.noOp) && isUnmaskedProofSegment(segments, index, errexit)) return true;
    const nextStatuses = new Set(skippedStatuses);
    if (executeStatuses.size > 0 && !isTerminalCommand(segment)) {
      if (canDynamicallyOverrideRunner(segment)) dynamicRunnerOverride = true;
      applyProofEnvUpdates(segment, proofEnvState);
      for (const status of possibleCommandStatuses(segment)) {
        if (errexit && status === 'failure' && separatorAfter === 'sequence') continue;
        nextStatuses.add(status);
      }
      const mode = errexitMode(segment);
      if (mode !== null) errexit = mode;
      const pipeMode = pipefailMode(segment);
      if (pipeMode !== null) pipefail = pipeMode;
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

function hasExpectationOnlyGreenProof(text) {
  return expectationOnlyGreenPattern.test(text) && !actualGreenOutputPattern.test(text);
}

export function hasRedProof(text) {
  if (redCountContradictionPattern.test(text) || hasExpectedRedContradiction(text) || hasExpectationOnlyRedCount(text)) return false;
  if (redFailureCountPattern.test(text) || mutationCountProofPattern.test(text)) return true;
  if (redProofContradictionPattern.test(text)) return false;
  return !notRedProofPattern.test(text) && (redProofPattern.test(text) || mutationProofPattern.test(text));
}

function hasRedTestProof(text) {
  if (redCountContradictionPattern.test(text) || hasExpectedRedContradiction(text) || hasExpectationOnlyRedCount(text)) return false;
  if (redFailureCountPattern.test(text)) return true;
  if (redProofContradictionPattern.test(text)) return false;
  if (mutationProofPattern.test(text) || mutationCountProofPattern.test(text)) return false;
  return !notRedProofPattern.test(text) && redProofPattern.test(text);
}

function hasMutationProof(text) {
  return !mutationProofContradictionPattern.test(text) && mutationCountProofPattern.test(text);
}

function hasMakeItFailProof(text) {
  if (makeItFailProofContradictionPattern.test(text)) return false;
  return makeItFailProofPattern.test(text);
}

export function hasGreenProof(text) {
  return !failedProofPattern.test(text) && !hasExpectationOnlyGreenProof(text) && greenProofPattern.test(text);
}

export function hasTestQualityEvidence(guardrail) {
  const text = normalizedTestQualityEvidence(evidenceText(guardrail));
  return !negatedTestQualityPattern.test(text) && positiveTestQualityPattern.test(text);
}

function hasMatchingTestFirstProof(command, text) {
  return (hasCommandMatching(command, matchesTestRunner) && hasRedTestProof(text))
    || (hasCommandMatching(command, matchesMutationCommand) && hasMutationProof(text))
    || (hasCommandMatching(command, matchesMakeItFailCommand) && hasMakeItFailProof(text));
}

export function matchesTestFirstProofGuardrail(guardrail) {
  return guardrail?.id === 'test-first-proof' && guardrail?.stage === 'he-implement' && guardrail?.kind === 'test' && hasMatchingTestFirstProof(guardrail?.command || '', evidenceText(guardrail)) && hasTestQualityEvidence(guardrail);
}

export function matchesImplementationProofGuardrail(guardrail) {
  return guardrail?.id === 'implementation-proof' && guardrail?.stage === 'he-implement' && guardrail?.kind === 'test' && hasImplementationProofCommand(guardrail?.command || '') && hasGreenProof(evidenceText(guardrail));
}
