// HARD_ENG_SCANNER_OWNER
import fs from 'node:fs';
import path from 'node:path';

const assignmentPattern = /^[A-Za-z_][A-Za-z0-9_]*(?:\+)?=/;
const assignmentNamePattern = /^([A-Za-z_][A-Za-z0-9_]*)(?:\+)?=/;
const packageManagers = new Set(['npm', 'pnpm', 'yarn', 'bun']);
const packageOptionValueFlags = new Set(['--prefix', '--filter', '--workspace', '-f', '--dir', '--cwd', '-c']);
const packageCwdValueFlags = new Set(['--prefix', '--dir', '--cwd', '-c']);
const packageOptionBooleanFlags = new Set(['--workspace-root', '--workspaces', '--ws', '--recursive', '-r']);
const directTestRunners = new Set(['pytest', 'vitest', 'jest', 'mocha', 'ava', 'tap']);
const npxTestRunners = new Set(['vitest', 'jest', 'mocha']);
const npxOptionBooleanFlags = new Set(['-y', '--yes']);
const mavenPathValueFlags = new Set(['-f', '--file']);
const mavenLeadingOptions = new Set(['-q', '--quiet', '-B', '--batch-mode', '-ntp', '--no-transfer-progress', '-U', '--update-snapshots', '-o', '--offline', '-e', '--errors', '-X', '--debug', '-V', '--show-version']);
const gradlePathValueFlags = new Set(['-p', '--project-dir', '-b', '--build-file', '-c', '--settings-file', '--include-build']);
const gradleLeadingOptions = new Set(['--no-daemon', '--daemon', '--offline', '--stacktrace', '--full-stacktrace', '--info', '-i', '--debug', '-d', '--quiet', '-q', '--warn', '-w', '--scan', '--no-scan', '--build-cache', '--no-build-cache', '--configuration-cache', '--no-configuration-cache', '--rerun-tasks', '--continue', '--parallel']);
const makePathValueFlags = new Set(['-f', '--file', '--makefile', '-c', '--directory']);
const goTestValueFlags = new Set(['-run', '--run', '-skip', '--skip', '-count', '--count', '-bench', '--bench', '-benchtime', '--benchtime', '-timeout', '--timeout', '-parallel', '--parallel', '-coverprofile', '--coverprofile', '-coverpkg', '--coverpkg', '-exec', '--exec', '-vet', '--vet', '-tags', '--tags', '-mod', '--mod', '-modfile', '--modfile', '-overlay', '--overlay', '-shuffle', '--shuffle', '-cpu', '--cpu']);
const goUnsafeAnyValueFlags = new Set(['-exec', '--exec', '-overlay', '--overlay', '-modfile', '--modfile']);
const goUnsafePathValueFlags = new Set(['-exec', '--exec', '-overlay', '--overlay', '-modfile', '--modfile', '-coverprofile', '--coverprofile']);
const cargoPathValueFlags = new Set(['--manifest-path', '--config']);
const dartFlutterPathValueFlags = new Set(['--packages', '--flutter-assets-dir', '--dart-define-from-file']);
const dartFlutterTestValueFlags = new Set(['--name', '--plain-name', '--tags', '--exclude-tags', '--platform', '--compiler', '--concurrency', '--timeout', '--total-shards', '--shard-index', '--test-randomize-ordering-seed', '--coverage-path', '--file-reporter', '--reporter', ...dartFlutterPathValueFlags]);
const nodeTestSelectionValueFlags = new Set(['--test-name-pattern', '--test-skip-pattern']);
const nodeTestPathValueFlags = new Set(['--require', '-r', '--import', '--loader', '--experimental-loader', '--test-reporter', '--test-reporter-destination']);
const nodeTestValueFlags = new Set([...nodeTestSelectionValueFlags, ...nodeTestPathValueFlags]);
const jestPathValueFlags = new Set(['-c', '--config', '--rootdir', '--setupfiles', '--setupfilesafterenv', '--testrunner', '--reporter', '--reporters', '--globalsetup', '--globalteardown', '--testenvironment']);
const vitestPathValueFlags = new Set(['-c', '--config', '-r', '--root', '--setupfiles']);
const mochaPathValueFlags = new Set(['--require', '-r', '--import', '--loader', '--experimental-loader', '--config', '--package', '--opts', '--file', '--node-option', '-n']);
const mochaSelectionValueFlags = new Set(['--grep', '-g', '--fgrep', '-f']);
const mochaRunnerValueFlags = new Set([...mochaPathValueFlags, ...mochaSelectionValueFlags]);
const avaPathValueFlags = new Set(['--config', '--require', '--node-arguments']);
const avaSelectionValueFlags = new Set(['--match', '-m']);
const avaRunnerValueFlags = new Set([...avaPathValueFlags, ...avaSelectionValueFlags]);
const tapPathValueFlags = new Set(['--node-arg', '--test-arg']);
const tapSelectionValueFlags = new Set(['--grep', '-g', '--test-regex']);
const tapRunnerValueFlags = new Set([...tapPathValueFlags, ...tapSelectionValueFlags]);
const testSubcommands = new Set(['spec', 'vitest', 'jest']);
const mutationCommands = new Set(['mutmut', 'infection', 'pitest']);
const noOpProofFlags = new Set(['--if-present', '--passwithnotests', '--pass-with-no-tests', '--help', '-h', '--version', '--dry-run', '--dryrun', '--list', '--list-tests', '--listtests', '--collect-only', '--co', '-list', '--no-run', '--norun', '--no-test', '--no-tests', '--no-execute', '--no-exec', '--skip-tests', '--skiptests']);
const pathChangingBuiltins = new Set(['export', 'typeset', 'declare', 'local', 'readonly']);
const proofEnvExportCommands = new Set(['export', 'typeset', 'declare', 'local', 'readonly']);
const shellControlFlowCommands = new Set(['if', 'then', 'else', 'elif', 'fi', 'case', 'esac', 'for', 'while', 'until', 'select', 'do', 'done']);
const terminalCommands = new Set(['exit', 'return', 'exec']);
const staticSuccessCommands = new Set(['true', ':', 'echo', 'printf']);
const modeledShellCommandNames = new Set([
  ...pathChangingBuiltins, ...proofEnvExportCommands, ...terminalCommands, ...staticSuccessCommands,
  'builtin', 'cd', 'chdir', 'command', 'env', 'eval', 'false', 'popd', 'pushd', 'set', 'source', 'trap', 'unset',
]);
const shadowableProofCommandNames = new Set([
  ...packageManagers, ...npxTestRunners, ...mutationCommands,
  ...modeledShellCommandNames,
  'ava', 'cargo', 'dart', 'flutter', 'go', 'gradle', 'jest', 'make', 'mocha', 'mvn', 'mvnw',
  'env', 'node', 'npx', 'phpunit', 'pytest', 'python', 'python3', 'rspec', 'stryker', 'tap',
]);
const npmNoOpConfigAssignments = new Set(['npm_config_if_present', 'npm_config_ignore_scripts']);
const npmUnsafeConfigAssignments = new Set(['npm_config_script_shell']);
const packagePathConfigAssignments = new Set(['npm_config_prefix', 'npm_config_local_prefix', 'npm_config_global_prefix', 'npm_config_userconfig', 'npm_config_globalconfig', 'npm_config_cache', 'npm_config_workspace', 'npm_config_workspaces', 'npm_config_ws', 'npm_config_filter', 'npm_config_dir', 'npm_config_cwd', 'pnpm_config_dir', 'pnpm_config_cwd', 'pnpm_config_userconfig', 'pnpm_config_globalconfig', 'pnpm_config_store_dir', 'pnpm_config_virtual_store_dir', 'pnpm_config_cache_dir', 'pnpm_config_workspace', 'pnpm_config_workspaces', 'pnpm_config_workspace_root', 'pnpm_config_ws', 'pnpm_config_filter', 'pnpm_config_recursive', 'yarn_config_cwd', 'yarn_config_userconfig', 'yarn_config_cache_folder', 'yarn_config_global_folder', 'yarn_cache_folder']);
const makeNoOpEnvAssignments = new Set(['makeflags', 'mflags', 'gnumakeflags', 'shell']);
const proofNoOpEnvAssignments = new Set(['pytest_addopts', 'goflags', 'node_options', ...npmNoOpConfigAssignments, ...npmUnsafeConfigAssignments, ...packagePathConfigAssignments, ...makeNoOpEnvAssignments]);
const redProofPattern = /\b(?:red[- ]?first\s+(?:failed|failure|red|reproduced|confirmed|recorded|nonzero)|red\s+(?:state|run)\s+(?:recorded|confirmed|reproduced)|failed as expected|[1-9]\d*\s+(?:failing tests?|failures?|failed tests?)|failing tests?\s+(?:recorded|confirmed|reproduced|before implementation|as expected)|(?:recorded|confirmed|reproduced)\s+failing tests?)\b/i;
const mutationProofPattern = /\b(?:mutation|mutants?)[^\n]*failed as expected\b/i;
const makeItFailProofPattern = /\bmake[- ]?it[- ]?fail[^\n]*(?:failed as expected|(?:red|nonzero)[^\n.;]*(?:output|run|proof|result|state|failure|exit)|(?:output|run|proof|result|state|failure|exit)[^\n.;]*(?:red|nonzero)|(?:exited?|exit(?:ed)?(?:\s+with)?|failed\s+with)\s+nonzero|nonzero\s+(?:exit|exited|failure|failed))\b/i;
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
const makeItFailProofContradictionPattern = /\b(?:not run|did not run|didn't run|make[- ]?it[- ]?fail[^\n]*(?:not|was not|wasn't|did not|didn't)\s+(?:run|executed?|fail(?:ed)?|red|(?:exit(?:\s+with)?\s+)?nonzero)|make[- ]?it[- ]?fail[^\n]*(?:passed|green|clean|skipped|disabled|unavailable))\b/i;
const expectedRedClausePattern = /\bexpected\b([^\n.;]*)\b(?:got|actual(?:ly)?|observed|received|but)\b([^\n.;]*)/gi;
const expectedFailurePattern = /\b(?:[1-9]\d*\s+)?(?:failed(?: tests?)?|tests?\s+failed|failing(?: tests?)?|failures?)(?:\s*[:=]\s*[1-9]\d*)?\b/i;
const actualPassedContradictionPattern = /\b(?:all\s+tests?\s+passed|[1-9]\d*\s+(?:tests?\s+)?passed|passed\s*[:=]\s*[1-9]\d*|0\s+(?:failed|failing|failures?|tests?\s+failed)|no\s+(?:failed|failing|failures?)|did not fail|didn't fail|passed|green|clean)\b/i;
const trailingExpectationMarker = String.raw`(?:(?:was\s+)?expected|should|would|planned)`;
const expectationOnlyFailurePattern = /\b(?:expected|should|would)\b[^\n.;]*\b(?:[1-9]\d*\s+(?:failed(?: tests?)?|tests?\s+failed|failing(?: tests?)?|failures?)|(?:failed tests?|tests?\s+failed|failing(?: tests?)?|failures?|failed)\s*[:=]\s*[1-9]\d*)\b/i;
const actualRedOutputPattern = /\b(?:actual(?:ly)?|observed|got|received)\b[^\n.;]*\b(?:[1-9]\d*\s+(?:failed(?: tests?)?|tests?\s+failed|failing(?: tests?)?|failures?)|(?:failed tests?|tests?\s+failed|failing(?: tests?)?|failures?|failed)\s*[:=]\s*[1-9]\d*)\b|\b(?:recorded|confirmed|reproduced)\s+(?:red|nonzero|failure|failing|failed)\s+(?:test\s+)?(?:output|run|proof|result)\b|\b(?:red|nonzero|failure|failing|failed)\s+(?:test\s+)?(?:output|run|proof|result)\s+(?:recorded|confirmed|reproduced)\b/i;
const trailingExpectationOnlyFailurePattern = new RegExp(`\\b(?:[1-9]\\d*\\s+(?:failed(?: tests?)?|tests?\\s+failed|failing(?: tests?)?|failures?)|(?:failed tests?|tests?\\s+failed|failing(?: tests?)?|failures?|failed)\\s*[:=]\\s*[1-9]\\d*)\\b[^\\n.;]*\\b${trailingExpectationMarker}\\b`, 'i');
const mutationExpectationOnlyPattern = /\b(?:expected|should|would|planned|would report)\b[^\n.;]*\b(?:[1-9]\d*\s+(?:mutants?|mutations?)\s+(?:were\s+)?(?:killed|detected)|(?:killed|detected)\s*[:=]?\s*[1-9]\d*|(?:mutants?|mutations?)[^\n.;]*(?:killed|detected))\b/i;
const actualMutationOutputPattern = /\b(?:actual(?:ly)?|observed|got|received)\b[^\n.;]*\b(?:[1-9]\d*\s+(?:mutants?|mutations?)\s+(?:were\s+)?(?:killed|detected)|(?:killed|detected)\s*[:=]?\s*[1-9]\d*|(?:mutants?|mutations?)[^\n.;]*(?:killed|detected))\b/i;
const trailingExpectationOnlyMutationPattern = new RegExp(`\\b(?:[1-9]\\d*\\s+(?:mutants?|mutations?)\\s+(?:were\\s+)?(?:killed|detected)|(?:killed|detected)\\s*[:=]\\s*[1-9]\\d*|(?:mutation|mutations?|mutants?)[^\\n.;]*(?:killed|detected)\\s*[:=]\\s*[1-9]\\d*)\\b[^\\n.;]*\\b${trailingExpectationMarker}\\b(?!\\s+(?:mutants?|mutations?)\\b)`, 'i');
const redProofContradictionPattern = new RegExp(`\\b(?:${notRedProofTerms.join('|')})\\b`, 'i');
const notRedProofPattern = new RegExp(`\\b(?:${[...notRedProofTerms, 'skipped', 'pending', 'todo'].join('|')})\\b`, 'i');
const greenProofPattern = /\b(?:all tests? passed|tests? passed|[1-9]\d*\s+(?:tests?|specs?|checks?|assertions?)?\s*(?:passed|passing)|passed:\s*[1-9]\d*|green(?: test)? run)\b/i;
const failedProofPattern = /\b(?:not all (?:tests?|specs?|checks?) passed|no\s+(?:tests?|specs?|checks?)\s+passed|tests?\s+passed:\s*0|passed\s*[:=]\s*0|passed\s*[:=]\s*\d+[^.;\n]*(?:failed|failures?|errors?|errored)\s*[:=]\s*[1-9]\d*|(?:failed|failures?|errors?|errored)\s*[:=]\s*[1-9]\d*|(?:failed|failures?|errors?|errored)\s+(?:[1-9]\d*|remain|remaining|left|present)|[1-9]\d*\s+(?:errors?|errored)|did not pass|didn't pass|not pass(?:ed)?|not green|not clean|not success(?:ful)?|tests? failed|failed tests?|[1-9]\d*\s+(?:failing|failures?|failed)|failing tests?(?:\s+(?:remain|remaining|left|present))?|failures?(?:\s+(?:remain|remaining|left|present))?|red[- ]?first|failed as expected|mutation|make[- ]?it[- ]?fail|not run|did not run|didn't run|0\s+(?:(?:tests?|specs?|checks?|assertions?)\s+)?(?:passed|passing)|0\/\d+\s+passed)\b/i;
const expectationOnlyGreenPattern = /\b(?:expected|should|would)\b[^\n.;]*\b(?:all tests? passed|tests? passed|passed|passing|green|clean)\b/i;
const actualGreenOutputPattern = /\b(?:actual(?:ly)?|observed|got|received)\b[^\n.;]*\b(?:all tests? passed|tests? passed|passed|passing|green|clean)\b|\b(?:recorded|confirmed|reproduced)\s+(?:green|clean|passing|passed)(?:\s+(?:test\s+)?(?:output|run|state|proof|result))?\b|\b(?:green|clean|passing|passed)(?:\s+(?:test\s+)?(?:output|run|state|proof|result))?\s+(?:recorded|confirmed|reproduced)\b/i;
const trailingExpectationOnlyGreenPattern = new RegExp(`\\b(?:all tests? passed|tests? passed|[1-9]\\d*\\s+(?:tests?|specs?|checks?|assertions?)?\\s*(?:passed|passing)|passed\\s*[:=]\\s*[1-9]\\d*|green(?: test)? run)\\b[^\\n.;]*\\b${trailingExpectationMarker}\\b`, 'i');
const makeItFailExpectationOnlyPattern = new RegExp(`\\b(?:expected|should|would)\\b[^\\n.;]*\\bmake[- ]?it[- ]?fail\\b[^\\n.;]*\\b(?:red|nonzero|fail(?:ed|ure)?)\\b|\\bmake[- ]?it[- ]?fail\\b[^\\n.;]*\\b(?:expected|should|would)\\b[^\\n.;]*\\b(?:red|nonzero|fail(?:ed|ure)?)\\b|\\bmake[- ]?it[- ]?fail\\b[^\\n.;]*\\b(?:(?:red|nonzero)[^\\n.;]*(?:output|run|proof|result|state|failure|exit)|(?:output|run|proof|result|state|failure|exit)[^\\n.;]*(?:red|nonzero)|(?:exited?|exit(?:ed)?(?:\\s+with)?|failed\\s+with)\\s+nonzero|nonzero\\s+(?:exit|exited|failure|failed))\\b[^\\n.;]*\\b${trailingExpectationMarker}\\b`, 'i');
const negatedTestQualityPattern = /\b(?:without|skipped?|no)\s+(?:the\s+)?test-quality\b|\b(?:no|without)\s+(?:recorded|used|using|loaded|ran|applied)\s+(?:the\s+)?test-quality\b|\b(?:not|never)\s+(?:recorded|used|using|loaded|ran|with|via|through|applied)\s+(?:the\s+)?test-quality\b|\b(?:did\s+not|didn't|failed\s+to)\s+(?:record|use|load|run|apply)\s+(?:the\s+)?test-quality\b|\bnot\s+using\s+(?:the\s+)?test-quality\b|\btest-quality(?:\s+(?:scenarios?|review|skill|use|used|evidence))?(?:\s+(?:is|are|was|were))?\s+(?:not\s+(?:used|loaded|run|applied|recorded|available)|wasn't\s+(?:used|loaded|run|applied|recorded)|skipped|missing|disabled|unavailable)\b/i;
const positiveTestQualityPattern = /\b(?:(?:used|using|loaded|ran|with|via|through|applied|recorded)\s+(?:the\s+)?test-quality(?:\s+(?:scenarios?|review|skill|evidence))?|test-quality(?:\s+(?:scenarios?|review|skill|evidence))?(?:\s+(?:is|are|was|were))?\s+(?:recorded|used|loaded|ran|applied))\b/i;
const nodeTestFilePattern = /\.(?:test|spec)\.(?:mjs|cjs|js|ts|tsx)$/;
const packageScriptsCache = new Map();

function evidenceText(guardrail) {
  return Array.isArray(guardrail?.evidence) ? guardrail.evidence.join(' ') : '';
}

function resolveProofRoot(root = process.cwd()) {
  let current = path.resolve(root || process.cwd());
  while (true) {
    if (fs.existsSync(path.join(current, '.git'))) return current;
    const parent = path.dirname(current);
    if (parent === current) return path.resolve(root || process.cwd());
    current = parent;
  }
}

function hasRootEntry(root, names) {
  return names.some((name) => fs.existsSync(path.join(root, name)));
}

function hasNodeTestFiles(root) {
  return ['test', 'tests'].some((name) => hasNodeTestFile(path.join(root, name)));
}

function hasNodeTestFile(dir) {
  try {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      if (entry.isFile() && nodeTestFilePattern.test(entry.name)) return true;
      if (entry.isDirectory() && hasNodeTestFile(path.join(dir, entry.name))) return true;
    }
  } catch {
    return false;
  }
  return false;
}

function normalizePackageScripts(scripts) {
  if (!scripts || typeof scripts !== 'object') return new Map();
  return new Map(Object.entries(scripts).filter(([, value]) => typeof value === 'string'));
}

function rootPackageScripts(root) {
  const packageFile = path.join(root, 'package.json');
  if (packageScriptsCache.has(packageFile)) return packageScriptsCache.get(packageFile);
  let scripts = new Map();
  try {
    scripts = normalizePackageScripts(JSON.parse(fs.readFileSync(packageFile, 'utf8')).scripts);
  } catch {
    scripts = new Map();
  }
  packageScriptsCache.set(packageFile, scripts);
  return scripts;
}

function commandUsesNodeTest(command) {
  return hasCommandMatching(command, matchesNodeTestStackCommand, {
    __proofContext: true,
    root: '',
    packageScripts: new Map(),
    stacks: new Set(),
    depth: 0,
    visitedScripts: new Set(),
  });
}

function packageScriptsUseNodeTest(scripts) {
  return [...scripts.values()].some(commandUsesNodeTest);
}

function normalizeProofStack(stack) {
  const value = lower(stack).replace(/_/g, '-');
  if (['js', 'javascript', 'typescript', 'node-package', 'package'].includes(value)) return 'js-package';
  if (['nodejs', 'node-test'].includes(value)) return 'node';
  if (['mvn'].includes(value)) return 'maven';
  if (['rust'].includes(value)) return 'cargo';
  if (['dart', 'flutter'].includes(value)) return 'dart-flutter';
  return value;
}

function proofStackSet(stacks) {
  const values = Array.isArray(stacks) ? stacks : [];
  return new Set(values.map(normalizeProofStack).filter(Boolean));
}

function detectedProofStacks(root, scripts) {
  const stacks = new Set();
  if (scripts.size || hasRootEntry(root, ['package.json'])) stacks.add('js-package');
  if (hasNodeTestFiles(root) || packageScriptsUseNodeTest(scripts) || hasRootEntry(root, ['node.config.js', 'node.config.mjs'])) stacks.add('node');
  if (hasRootEntry(root, ['pyproject.toml', 'pytest.ini', 'setup.cfg', 'setup.py', 'requirements.txt'])) stacks.add('python');
  if (hasRootEntry(root, ['go.mod'])) stacks.add('go');
  if (hasRootEntry(root, ['Cargo.toml'])) stacks.add('cargo');
  if (hasRootEntry(root, ['build.gradle', 'build.gradle.kts', 'settings.gradle', 'settings.gradle.kts', 'gradlew'])) stacks.add('gradle');
  if (hasRootEntry(root, ['pom.xml', 'mvnw'])) stacks.add('maven');
  if (hasRootEntry(root, ['pubspec.yaml'])) stacks.add('dart-flutter');
  if (hasRootEntry(root, ['Makefile', 'makefile', 'GNUmakefile'])) stacks.add('make');
  if ([...scripts.keys()].some(isMutationScript) || hasRootEntry(root, ['stryker.conf.js', 'stryker.conf.json', 'stryker.conf.mjs', 'infection.json'])) stacks.add('mutation');
  return stacks;
}

function proofContext(options = {}) {
  if (options.__proofContext) return options;
  const root = resolveProofRoot(options.root);
  const scripts = options.packageScripts ? normalizePackageScripts(options.packageScripts) : rootPackageScripts(root);
  const explicitStacks = proofStackSet(options.proofStacks);
  const stacks = new Set([...detectedProofStacks(root, scripts), ...explicitStacks]);
  return { __proofContext: true, root, packageScripts: scripts, stacks, depth: options.depth || 0, visitedScripts: new Set(options.visitedScripts || []) };
}

function guardrailProofOptions(_guardrail, options = {}) {
  return { ...options };
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

function combinedAssignments(assignments) {
  const values = new Map();
  for (const assignment of assignments) {
    const prior = values.get(assignment.name) || '';
    values.set(assignment.name, assignment.append ? `${prior}${assignment.value}` : assignment.value);
  }
  return [...values].map(([name, value]) => ({ name, value }));
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

function keywordMode(segment) { return setOptionMode(segment, 'k', 'keyword'); }

function staticCommandStatus(segment) {
  if (errexitMode(segment) !== null || pipefailMode(segment) !== null || allexportMode(segment) !== null || keywordMode(segment) !== null) return 'success';
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
  return shadowableProofCommandNames.has(name);
}

function definesRunnerOverride(segment) {
  if (definesShadowedRunner(segment)) return true;
  const words = effectiveCommandWords(segment);
  const command = lower(words[0]);
  if (command === 'alias') {
    return words.slice(1).some((word) => shadowableProofCommandNames.has(lower(String(word).match(/^([A-Za-z_][A-Za-z0-9_-]*)=/)?.[1])));
  }
  if (command !== 'hash') return false;
  const args = words.slice(1);
  if (args.some((word) => shadowableProofCommandNames.has(assignmentName(word)))) return true;
  if (!args.some((word) => lower(word) === '-p' || lower(word).startsWith('-p'))) return false;
  return args.some((word) => shadowableProofCommandNames.has(lower(word)));
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

function isSafeNormalizedProofPathValue(value) {
  if (!value || /[`$]/.test(value)) return false;
  if (value.startsWith('/') || value.startsWith('~') || value.startsWith('\\\\') || /^[A-Za-z]:[\\/]/.test(value)) return false;
  if (hasUriSchemeProofPathValue(value)) return false;
  return !value.split(/[\\/]+/).includes('..');
}

function isSafeProofPathValue(word) {
  return isSafeNormalizedProofPathValue(shellWordValue(word));
}

function isSafeProofPathOptionValue(word) {
  return isSafeNormalizedProofPathValue(shellWordValue(word).replace(/^=/, ''));
}

function isUnsafePositionalProofPath(word) {
  const value = shellWordValue(word).split('::')[0];
  if (!value || value.startsWith('-')) return false;
  return value.startsWith('/') || value.startsWith('~') || value.startsWith('\\\\') || /^[A-Za-z]:[\\/]/.test(value) || hasUriSchemeProofPathValue(value) || value.split(/[\\/]+/).includes('..');
}

function hasUriSchemeProofPathValue(value) {
  return /^[A-Za-z][A-Za-z0-9+.-]*:/.test(value);
}

function isInlineConfigValue(word) {
  const value = shellWordValue(word).replace(/^=/, '').trim();
  return value.startsWith('{');
}

function hasUnsafeConfigOptionValue(word, flag) {
  const option = lower(String(flag || '').split('=')[0]);
  return (option === '-c' || option === '--config') && isInlineConfigValue(word);
}

function hasUnsafePathValueOption(words, valueFlags, longInlinePattern, shortFlags = [], unsafeValue = () => false) {
  for (let index = 0; index < words.length; index += 1) {
    const rawWord = String(words[index] || '');
    const word = lower(rawWord);
    if (valueFlags.has(word)) {
      if (unsafeValue(words[index + 1], word) || !isSafeProofPathOptionValue(words[index + 1])) return true;
      index += 1;
      continue;
    }
    const inlineMatch = rawWord.match(longInlinePattern);
    if (inlineMatch) {
      if (unsafeValue(inlineMatch[1], rawWord) || !isSafeProofPathOptionValue(inlineMatch[1])) return true;
      continue;
    }
    for (const flag of shortFlags) {
      if (word.startsWith(lower(flag)) && rawWord.length > flag.length) {
        if (unsafeValue(rawWord.slice(flag.length), flag) || !isSafeProofPathOptionValue(rawWord.slice(flag.length))) return true;
        break;
      }
    }
  }
  return false;
}

function longOptionFlags(...flagSets) {
  return new Set(flagSets.flatMap((flags) => [...flags]).filter((flag) => flag.startsWith('--')).map(lower));
}

function hasUnknownUnsafeInlinePathOption(words, knownInlineFlags = new Set()) {
  for (const rawWord of words) {
    const match = String(rawWord || '').match(/^(--[^=\s]+)=(.*)$/);
    if (!match) continue;
    if (knownInlineFlags.has(lower(match[1]))) continue;
    if (!isSafeProofPathOptionValue(match[2])) return true;
  }
  return false;
}

function skipSafePathValueOption(words, index, valueFlags, longInlinePattern, shortFlags = []) {
  const rawWord = String(words[index] || '');
  const word = lower(rawWord);
  if (valueFlags.has(word) && isSafeProofPathOptionValue(words[index + 1])) return index + 2;
  const inlineMatch = rawWord.match(longInlinePattern);
  if (inlineMatch?.[1] && isSafeProofPathOptionValue(inlineMatch[1])) return index + 1;
  for (const flag of shortFlags) {
    if (word.startsWith(lower(flag)) && rawWord.length > flag.length && isSafeProofPathOptionValue(rawWord.slice(flag.length))) return index + 1;
  }
  return index;
}

function hasUnsafeRunnerPositionalPath(words, valueFlags = new Set(), longInlinePattern = /^$/, shortFlags = []) {
  let optionsTerminated = false;
  for (let index = 0; index < words.length; index += 1) {
    const rawWord = String(words[index] || '');
    const word = lower(rawWord);
    if (!optionsTerminated) {
      if (word === '--') {
        optionsTerminated = true;
        continue;
      }
      if (valueFlags.has(word)) {
        index += 1;
        continue;
      }
      if (rawWord.match(longInlinePattern)) continue;
      let hasShortValue = false;
      for (const flag of shortFlags) {
        if (word.startsWith(lower(flag)) && rawWord.length > flag.length) {
          hasShortValue = true;
          break;
        }
      }
      if (hasShortValue || word.startsWith('-')) continue;
    }
    if (isUnsafePositionalProofPath(rawWord)) return true;
  }
  return false;
}

function hasPackageScopeOption(words, manager) {
  for (let index = 1; index < words.length; index += 1) {
    const rawWord = shellWordValue(words[index]);
    const word = lower(rawWord);
    if (word === '--') return false;
    if (word === 'workspace' && manager === 'yarn') return true;
    if (word === '-w' || word.startsWith('-w')) return true;
    if (packageOptionValueFlags.has(word) || packageOptionBooleanFlags.has(word)) return true;
    if (/^--(?:prefix|filter|workspace|dir|cwd|workspaces|ws|recursive|workspace-root)=/i.test(rawWord)) return true;
    for (const flag of ['-f', '-c']) {
      if (word.startsWith(flag) && rawWord.length > flag.length) return true;
    }
  }
  return false;
}

function packageCommand(words) {
  const manager = lower(words[0]);
  if (!packageManagers.has(manager)) return null;
  if (hasPackageScopeOption(words, manager)) return null;
  return { manager, index: 1 };
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

function makeTargetIndex(words) {
  let index = 1;
  while (index < words.length) {
    const word = lower(words[index]);
    if (word === '--') return index + 1;
    const nextIndex = skipSafePathValueOption(words, index, makePathValueFlags, /^--(?:file|makefile|directory)=(.*)$/i, ['-f', '-C']);
    if (nextIndex !== index) {
      index = nextIndex;
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

function hasPackageNoOpProofEnvValue(name, value) {
  return npmUnsafeConfigAssignments.has(name) || (npmNoOpConfigAssignments.has(name) && isTruthyConfigValue(value)) || packagePathConfigAssignments.has(name);
}

function hasMakeNoOpFlagValue(value) {
  const words = shellWords(value).map(shellWordValue);
  return words.some((word) => isMakeNoOpProofOption(word) || /^[A-Za-z]*[nqt][A-Za-z]*$/i.test(word));
}

function hasMakeNoOpProofAssignment({ name, value }) {
  if (name === 'makeflags' || name === 'mflags' || name === 'gnumakeflags') return hasMakeNoOpFlagValue(value);
  if (name === 'shell') return String(value || '').trim() !== '';
  return false;
}

function isPytestMetadataNoOpProofFlag(word) {
  return /^(?:--fixtures(?:-per-test)?|--markers|--setup-(?:only|plan))(?:=|$)/i.test(word || '');
}

function isPytestNoOpProofFlag(word) {
  return isNoOpProofFlag(word) || isPytestMetadataNoOpProofFlag(word);
}

function pytestOverrideIniAddoptsValue(word) {
  const value = shellWordValue(word).replace(/^=/, '').trim();
  const match = value.match(/^addopts\s*=(.*)$/i);
  return match ? match[1] : null;
}

function hasPytestOverrideIniNoOpProofOption(words) {
  for (let index = 0; index < words.length; index += 1) {
    const rawWord = String(words[index] || '');
    const word = lower(rawWord);
    let value = optionValue(words, index, '-o') ?? optionValue(words, index, '--override-ini');
    if (value === null && word.startsWith('-o') && rawWord.length > 2) value = rawWord.slice(2);
    const addopts = value === null ? null : pytestOverrideIniAddoptsValue(value);
    if (addopts !== null && hasPytestNoOpProofArgs(addopts)) return true;
  }
  return false;
}

function hasPytestNoOpProofArgs(value) {
  const words = shellWords(value).map(shellWordValue);
  return words.some(isPytestNoOpProofFlag) || hasUnsafePytestPathOverride(words) || hasPytestOverrideIniNoOpProofOption(words);
}

function hasGoNoOpProofArgs(value) {
  const words = ['go', 'test', ...shellWords(value).map(shellWordValue)];
  return hasGoNoOpProofOption(words) || hasUnsafeGoTestPathOverride(words);
}

function hasNodeTestNoOpProofArgsValue(value) {
  return hasNodeTestNoOpArgs(shellWords(value).map(shellWordValue));
}

function hasNoOpProofEnvValue(name, value) {
  if (name === 'pytest_addopts') return hasPytestNoOpProofArgs(value);
  if (name === 'goflags') return hasGoNoOpProofArgs(value);
  if (name === 'node_options') return hasNodeTestNoOpProofArgsValue(value);
  if (makeNoOpEnvAssignments.has(name)) return hasMakeNoOpProofAssignment({ name, value });
  return hasPackageNoOpProofEnvValue(name, value);
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

function exportCommandParts(segment) {
  const words = shellWords(segment).map(shellWordValue);
  let index = 0;
  const leadingAssignments = [];
  while (assignmentPattern.test(words[index] || '')) {
    const assignment = assignmentParts(words[index]);
    if (assignment) leadingAssignments.push(assignment);
    index += 1;
  }
  if (['builtin', 'command'].includes(lower(words[index]))) index += 1;
  if (!proofEnvExportCommands.has(lower(words[index]))) return null;
  return { words: words.slice(index), leadingAssignments };
}

function applyExportProofEnv(segment, state) {
  const parts = exportCommandParts(segment);
  if (!parts) return;
  for (const assignment of parts.leadingAssignments) {
    setProofEnvValue(state, assignment.name, assignment.value, assignment.append);
  }
  const words = parts.words;
  const command = lower(words[0]);
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

function hasAssignmentOnlyProofEnvMutation(segment) {
  const words = shellWords(segment).map(shellWordValue);
  if (words.length === 0 || lower(words[0]) === 'env' || !words.every((word) => assignmentPattern.test(word))) return false;
  return words.some((word) => proofNoOpEnvAssignments.has(assignmentName(word)));
}

function hasExportProofEnvMutation(segment) {
  const parts = exportCommandParts(segment);
  if (!parts) return false;
  if (parts.leadingAssignments.some((assignment) => proofNoOpEnvAssignments.has(assignment.name))) return true;
  for (const word of parts.words.slice(1)) {
    const value = lower(word);
    if (value === '--') continue;
    const flagMode = exportModeFlag(value);
    if (flagMode !== null) continue;
    if (value.startsWith('-') || value.startsWith('+')) continue;
    const assignment = assignmentParts(word);
    const name = assignment?.name || value;
    if (proofNoOpEnvAssignments.has(name)) return true;
  }
  return false;
}

function hasUnsetProofEnvMutation(segment) {
  const words = effectiveCommandWords(segment).map(shellWordValue);
  if (lower(words[0]) !== 'unset') return false;
  return words.slice(1).some((word) => lower(word) !== '--' && !lower(word).startsWith('-') && proofNoOpEnvAssignments.has(lower(word)));
}

function hasProofEnvMutation(segment) {
  return allexportMode(segment) !== null || hasAssignmentOnlyProofEnvMutation(segment) || hasExportProofEnvMutation(segment) || hasUnsetProofEnvMutation(segment);
}

function isConditionalSeparator(separator) {
  return separator === '&&' || separator === '||';
}

function isNoOpProofFlag(word) {
  return noOpProofFlags.has(lower(word)) || /^(?:--(?:if-present|passwithnotests|pass-with-no-tests|help|version|dry-run|dryrun|list|listtests|list-tests|collect-only|co|no-run|norun|no-test|no-tests|no-execute|no-exec|skip-tests|skiptests)|-list)(?:=|$)/i.test(word || '') || hasTruthyMavenSkipTestsOption(word);
}

function hasNoOpProofAssignment(segment, words) {
  const assignments = combinedAssignments(leadingCommandAssignments(segment));
  if (assignments.length === 0) return false;
  const command = lower(words[0]);
  if (command === 'pytest' || ((command === 'python' || command === 'python3') && lower(words[1]) === '-m' && lower(words[2]) === 'pytest')) {
    if (assignments.some(({ name, value }) => name === 'pytest_addopts' && hasPytestNoOpProofArgs(value))) return true;
  }
  if (command === 'go' && lower(words[1]) === 'test') {
    return assignments.some(({ name, value }) => name === 'goflags' && hasGoNoOpProofArgs(value));
  }
  if (command === 'node') {
    return assignments.some(({ name, value }) => name === 'node_options' && hasNodeTestNoOpProofArgsValue(value));
  }
  const directRunner = directRunnerOptionStart(words);
  if (directRunner && directRunner.runner !== 'pytest') {
    return assignments.some(({ name, value }) => name === 'node_options' && hasNodeTestNoOpProofArgsValue(value));
  }
  if (packageManagers.has(command)) {
    return assignments.some(({ name, value }) => hasPackageNoOpProofEnvValue(name, value) || (name === 'node_options' && hasNodeTestNoOpProofArgsValue(value)));
  }
  if (command === 'make') return assignments.some(hasMakeNoOpProofAssignment);
  return false;
}

function hasExportedNoOpProofEnv(words, exportedNoOpProofEnv) {
  const command = lower(words[0]);
  if (command === 'pytest' || ((command === 'python' || command === 'python3') && lower(words[1]) === '-m' && lower(words[2]) === 'pytest')) {
    return exportedNoOpProofEnv.has('pytest_addopts');
  }
  if (command === 'go' && lower(words[1]) === 'test') return exportedNoOpProofEnv.has('goflags');
  if (command === 'node') return exportedNoOpProofEnv.has('node_options');
  const directRunner = directRunnerOptionStart(words);
  if (directRunner && directRunner.runner !== 'pytest') return exportedNoOpProofEnv.has('node_options');
  if (packageManagers.has(command)) {
    return ['node_options', ...npmNoOpConfigAssignments, ...npmUnsafeConfigAssignments, ...packagePathConfigAssignments].some((name) => exportedNoOpProofEnv.has(name));
  }
  if (command === 'make') return [...makeNoOpEnvAssignments].some((name) => exportedNoOpProofEnv.has(name));
  return false;
}

function hasNoOpProofOption(words, segment = '', exportedNoOpProofEnv = new Set(), context = {}) {
  const normalized = words.map(shellWordValue);
  if (hasNoOpProofAssignment(segment, normalized)) return true;
  if (hasExportedNoOpProofEnv(normalized, exportedNoOpProofEnv)) return true;
  if (hasPackageScriptShellProofOption(normalized)) return true;
  if (hasGenericPackageScriptRunnerNoOpOption(normalized, context)) return true;
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
    const assignment = assignmentParts(word);
    if (assignment && hasMakeNoOpProofAssignment(assignment)) return true;
  }
  return false;
}

function hasUnsafePathOverrideProofOption(words) {
  const command = lower(words[0]);
  if (packageManagers.has(command) && hasPackageScopeOption(words, command)) return true;
  if (packageManagers.has(command) && hasUnsafePathValueOption(words, packageCwdValueFlags, /^--(?:prefix|dir|cwd)=(.*)$/i, ['-c'])) return true;
  if (isMavenCommand(command)) return hasUnsafePathValueOption(words, mavenPathValueFlags, /^--file=(.*)$/i, ['-f']);
  if (command === 'gradle' || command === './gradlew') {
    return hasUnsafePathValueOption(words, gradlePathValueFlags, /^--(?:project-dir|build-file|settings-file|include-build)=(.*)$/i, ['-p', '-b', '-c']);
  }
  if (command === 'make') return hasUnsafePathValueOption(words, makePathValueFlags, /^--(?:file|makefile|directory)=(.*)$/i, ['-f', '-C']);
  if (command === 'go') return hasUnsafeGoTestPathOverride(words);
  if (command === 'cargo') return hasUnsafeCargoTestPathOverride(words);
  if (command === 'dart' || command === 'flutter') return hasUnsafeDartFlutterTestPathOverride(words);
  return hasUnsafeDirectRunnerProofOption(words);
}

function hasUnsafeGoTestPathOverride(words) {
  if (lower(words[1]) !== 'test') return false;
  const args = words.slice(2);
  return hasUnsafePathValueOption(args, goUnsafePathValueFlags, /^-(?:exec|overlay|modfile|coverprofile)=(.*)$/i, [], (_value, flag) => goUnsafeAnyValueFlags.has(lower(String(flag || '').split('=')[0])))
    || hasUnsafeRunnerPositionalPath(args, goTestValueFlags, /^-(?:run|skip|count|bench|benchtime|timeout|parallel|coverprofile|coverpkg|exec|vet|tags|mod|modfile|overlay|shuffle|cpu)=(.*)$/i);
}

function hasUnsafeCargoTestPathOverride(words) {
  if (lower(words[1]) !== 'test') return false;
  return hasUnsafePathValueOption(words.slice(2), cargoPathValueFlags, /^--(?:manifest-path|config)=(.*)$/i);
}

function hasUnsafeDartFlutterTestPathOverride(words) {
  if (lower(words[1]) !== 'test') return false;
  const args = words.slice(2);
  return hasUnsafePathValueOption(args, dartFlutterPathValueFlags, /^--(?:packages|flutter-assets-dir|dart-define-from-file)=(.*)$/i)
    || hasUnsafeRunnerPositionalPath(args, dartFlutterTestValueFlags, /^--(?:name|plain-name|tags|exclude-tags|platform|compiler|concurrency|timeout|total-shards|shard-index|test-randomize-ordering-seed|coverage-path|file-reporter|reporter|packages|flutter-assets-dir|dart-define-from-file)=(.*)$/i, ['-n', '-p', '-r', '-j', '-t', '-x']);
}

function skipPackageRunnerSeparator(words, start) {
  return lower(words[start]) === '--' ? start + 1 : start;
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
  if (packageInfo) {
    const subcommand = lower(words[packageInfo.index]);
    const next = lower(words[packageInfo.index + 1]);
    if (subcommand === 'exec' && npxTestRunners.has(next)) {
      return { runner: next, start: packageInfo.index + 2 };
    }
    if (subcommand === 'run' && npxTestRunners.has(next)) {
      return { runner: next, start: skipPackageRunnerSeparator(words, packageInfo.index + 2) };
    }
    if (packageInfo.manager !== 'npm' && isTestScript(subcommand) && npxTestRunners.has(subcommand)) {
      return { runner: subcommand, start: skipPackageRunnerSeparator(words, packageInfo.index + 1) };
    }
  }
  return null;
}

function hasUnsafeDirectRunnerProofOption(words) {
  const info = directRunnerOptionStart(words);
  if (!info) return false;
  return hasUnsafeRunnerProofOption(info.runner, words.slice(info.start));
}

function hasUnsafeRunnerProofOption(runner, runnerWords) {
  if (runner === 'pytest') return hasUnsafePytestPathOverride(runnerWords) || hasPytestOverrideIniNoOpProofOption(runnerWords) || hasUnsafeRunnerPositionalPath(runnerWords, new Set(['-c', '--rootdir', '-o', '--override-ini']), /^--(?:rootdir|override-ini)=(.*)$/i, ['-c', '-o']);
  if (runner === 'jest') return hasUnsafeJestProofOption(runnerWords);
  if (runner === 'vitest') return hasUnsafeVitestProofOption(runnerWords);
  if (runner === 'mocha') return hasUnsafeMochaProofOption(runnerWords);
  if (runner === 'ava') return hasUnsafeAvaProofOption(runnerWords);
  if (runner === 'tap') return hasUnsafeTapProofOption(runnerWords);
  return false;
}

function hasUnsafeJestProofOption(words) {
  return hasUnsafePathValueOption(words, jestPathValueFlags, /^--(?:config|rootdir|setupfiles|setupfilesafterenv|testrunner|reporters?|globalsetup|globalteardown|testenvironment)=(.*)$/i, ['-c'], hasUnsafeConfigOptionValue)
    || hasUnsafeRunnerPositionalPath(words, jestPathValueFlags, /^--(?:config|rootdir|setupfiles|setupfilesafterenv|testrunner|reporters?|globalsetup|globalteardown|testenvironment)=(.*)$/i, ['-c'])
    || hasUnknownUnsafeInlinePathOption(words, longOptionFlags(jestPathValueFlags));
}

function hasUnsafeVitestProofOption(words) {
  return hasUnsafePathValueOption(words, vitestPathValueFlags, /^--(?:config|root|setupfiles)=(.*)$/i, ['-c', '-r'], hasUnsafeConfigOptionValue)
    || hasUnsafeRunnerPositionalPath(words, vitestPathValueFlags, /^--(?:config|root|setupfiles)=(.*)$/i, ['-c', '-r'])
    || hasUnknownUnsafeInlinePathOption(words, longOptionFlags(vitestPathValueFlags));
}

function hasNoOpSelectionValueOption(words, valueFlags, longInlinePattern, shortFlags = []) {
  for (let index = 0; index < words.length; index += 1) {
    const rawWord = String(words[index] || '');
    const word = lower(rawWord);
    let value = null;
    if (valueFlags.has(word)) {
      value = words[index + 1];
      index += 1;
    } else {
      value = rawWord.match(longInlinePattern)?.[1] ?? null;
      if (value === null) {
        for (const flag of shortFlags) {
          if (word.startsWith(lower(flag)) && rawWord.length > flag.length) {
            value = rawWord.slice(flag.length);
            break;
          }
        }
      }
    }
    if (value !== null && isEmptyProofSelectionPattern(value)) return true;
  }
  return false;
}

function hasUnsafeNodeOptionValue(value) {
  const rawWords = shellWords(value).map(shellWordValue);
  const words = rawWords.map((word, index) => {
    const previous = index > 0 ? nodeOptionFlagWord(rawWords[index - 1]) : '';
    if (nodeTestValueFlags.has(previous)) return word;
    return nodeOptionFlagWord(word);
  });
  return hasNodeTestNoOpArgs(words) || hasUnsafeRunnerPositionalPath(words, nodeTestValueFlags, /^--(?:test-name-pattern|test-skip-pattern|require|import|loader|experimental-loader|test-reporter|test-reporter-destination)=(.*)$/i, ['-r']);
}

function nodeOptionFlagWord(word) {
  const value = shellWordValue(word);
  return lower(value).startsWith('-') || !/^[A-Za-z][A-Za-z0-9-]*(?:=.*)?$/.test(value) ? value : `--${value}`;
}

function hasMochaMetadataNoOpProofFlag(word) {
  return /^--list-(?:interfaces|reporters)(?:=|$)/i.test(word || '');
}

function hasMochaNoOpProofFlag(word) {
  return hasMochaMetadataNoOpProofFlag(word) || /^--pass-on-failing-test-suite(?:=|$)/i.test(word || '');
}

function hasUnsafeMochaOptionValue(value, flag) {
  const name = lower(String(flag || '').split('=')[0]);
  if (name === '--node-option' || name === '-n') return hasUnsafeNodeOptionValue(value);
  return hasUnsafeConfigOptionValue(value, flag);
}

function hasUnsafeMochaProofOption(words) {
  return hasUnsafePathValueOption(words, mochaPathValueFlags, /^--(?:require|import|loader|experimental-loader|config|package|opts|file|node-option)=(.*)$/i, ['-r', '-n'], hasUnsafeMochaOptionValue)
    || hasUnsafeRunnerPositionalPath(words, mochaRunnerValueFlags, /^--(?:require|import|loader|experimental-loader|config|package|opts|file|node-option|grep|fgrep)=(.*)$/i, ['-r', '-n', '-g', '-f'])
    || hasNoOpSelectionValueOption(words, mochaSelectionValueFlags, /^--(?:grep|fgrep)=(.*)$/i, ['-g', '-f'])
    || hasUnknownUnsafeInlinePathOption(words, longOptionFlags(mochaRunnerValueFlags))
    || words.some(hasMochaNoOpProofFlag);
}

function hasUnsafeAvaProofOption(words) {
  return hasUnsafePathValueOption(words, avaPathValueFlags, /^--(?:config|require|node-arguments)=(.*)$/i, [], (value, flag) => lower(String(flag || '').split('=')[0]) === '--node-arguments' && hasUnsafeNodeOptionValue(value))
    || hasUnsafeRunnerPositionalPath(words, avaRunnerValueFlags, /^--(?:config|require|node-arguments|match)=(.*)$/i, ['-m'])
    || hasNoOpSelectionValueOption(words, avaSelectionValueFlags, /^--match=(.*)$/i, ['-m'])
    || hasUnknownUnsafeInlinePathOption(words, longOptionFlags(avaRunnerValueFlags));
}

function hasUnsafeTapProofOption(words) {
  return hasUnsafePathValueOption(words, tapPathValueFlags, /^--(?:node-arg|test-arg)=(.*)$/i, [], (value, flag) => lower(String(flag || '').split('=')[0]) === '--node-arg' && hasUnsafeNodeOptionValue(value))
    || hasUnsafeRunnerPositionalPath(words, tapRunnerValueFlags, /^--(?:node-arg|test-arg|grep|test-regex)=(.*)$/i, ['-g'])
    || hasNoOpSelectionValueOption(words, tapSelectionValueFlags, /^--(?:grep|test-regex)=(.*)$/i, ['-g'])
    || hasUnknownUnsafeInlinePathOption(words, longOptionFlags(tapRunnerValueFlags));
}

function hasUnsafePytestPathOverride(words) {
  return hasUnsafePathValueOption(words, new Set(['-c', '--rootdir']), /^--rootdir=(.*)$/i, ['-c']);
}

function hasPytestMetadataNoOpProofOption(words) {
  const command = lower(words[0]);
  const start = command === 'pytest' ? 1 : (command === 'python' || command === 'python3') && lower(words[1]) === '-m' && lower(words[2]) === 'pytest' ? 3 : -1;
  if (start < 0) return false;
  return words.slice(start).some(isPytestMetadataNoOpProofFlag);
}

function hasJestMetadataNoOpProofFlag(word) {
  return /^(?:--showconfig|--clearcache)(?:=|$)/i.test(word || '');
}

function hasJestMetadataNoOpProofOption(words) {
  const info = directRunnerOptionStart(words);
  return info?.runner === 'jest' && words.slice(info.start).some(hasJestMetadataNoOpProofFlag);
}

function optionValue(words, index, flag) {
  const rawWord = String(words[index] || '');
  const value = lower(rawWord);
  const normalizedFlag = lower(flag);
  if (value.startsWith(`${normalizedFlag}=`)) return rawWord.slice(flag.length + 1);
  return value === normalizedFlag ? words[index + 1] : null;
}

function patternWithoutRegexDelimiters(value) {
  const pattern = lower(value).trim();
  return pattern.startsWith('/') && pattern.endsWith('/') && pattern.length > 1 ? pattern.slice(1, -1) : pattern;
}

function isEmptyProofSelectionPattern(value) {
  return patternWithoutRegexDelimiters(value) === '^$';
}

function isAllProofSelectionPattern(value) {
  return ['.', '.*', '^.*$', '.+', '^.+$', '^', '$'].includes(patternWithoutRegexDelimiters(value));
}

function hasGoNoOpProofOption(words) {
  if (lower(words[0]) !== 'go' || lower(words[1]) !== 'test') return false;
  return words.some((_, index) => {
    const runPattern = optionValue(words, index, '-run') ?? optionValue(words, index, '--run');
    const skipPattern = optionValue(words, index, '-skip') ?? optionValue(words, index, '--skip');
    const count = optionValue(words, index, '-count') ?? optionValue(words, index, '--count');
    return (runPattern !== null && isEmptyProofSelectionPattern(runPattern)) || (skipPattern !== null && isAllProofSelectionPattern(skipPattern)) || (count !== null && String(count).trim() === '0');
  });
}

function hasNodeTestNoOpArgs(words) {
  if (hasUnsafeNodeTestPathOverride(words)) return true;
  return words.some((word, index) => {
    const value = lower(word);
    if (value === '--test-only') return true;
    const namePattern = optionValue(words, index, '--test-name-pattern');
    const skipPattern = optionValue(words, index, '--test-skip-pattern');
    return (namePattern !== null && isEmptyProofSelectionPattern(namePattern)) || (skipPattern !== null && isAllProofSelectionPattern(skipPattern));
  });
}

function hasUnsafeNodeTestPathOverride(words) {
  return hasUnsafePathValueOption(words, nodeTestPathValueFlags, /^--(?:require|import|loader|experimental-loader|test-reporter|test-reporter-destination)=(.*)$/i, ['-r']);
}

function hasNodeTestNoOpProofOption(words) {
  if (lower(words[0]) !== 'node' || lower(words[1]) !== '--test') return false;
  const args = words.slice(2);
  return hasNodeTestNoOpArgs(args) || hasUnsafeRunnerPositionalPath(args, nodeTestValueFlags, /^--(?:test-name-pattern|test-skip-pattern|require|import|loader|experimental-loader|test-reporter|test-reporter-destination)=(.*)$/i, ['-r']);
}

function hasRunnerMetadataNoOpProofOption(words) {
  return hasPytestMetadataNoOpProofOption(words) || hasJestMetadataNoOpProofOption(words) || hasGoNoOpProofOption(words) || hasNodeTestNoOpProofOption(words);
}

function hasPackageScriptShellProofOption(words) {
  if (!packageManagers.has(lower(words[0]))) return false;
  return words.some((word) => /^--script-shell(?:=|$)/i.test(word));
}

function isRunnerPassthroughScript(word) {
  return isTestScript(word) || isMakeItFailScript(word);
}

function genericPackageScriptRunnerArgStart(words) {
  const command = packageCommand(words);
  if (!command) return -1;
  const subcommand = lower(words[command.index]);
  let start = -1;
  if (subcommand === 'test') start = command.index + 1;
  else if (command.manager !== 'npm' && isRunnerPassthroughScript(subcommand)) start = command.index + 1;
  else if (subcommand === 'run' && isRunnerPassthroughScript(words[command.index + 1])) start = command.index + 2;
  if (start < 0) return -1;
  if (command.manager !== 'npm') return start;
  for (let index = start; index < words.length; index += 1) {
    if (lower(words[index]) === '--') return index + 1;
  }
  return -1;
}

function packageScriptDirectRunner(command, context = {}) {
  const ctx = proofContext(context);
  let runner = null;
  const matched = hasCommandMatching(command, (words, segment, exportedNoOpProofEnv, matcherContext) => {
    if (hasNoOpProofOption(words, segment, exportedNoOpProofEnv, matcherContext)) return false;
    const info = directRunnerOptionStart(words);
    if (info) {
      runner = info.runner;
      return true;
    }
    const nestedRunner = packageScriptPassthroughRunner(words, matcherContext);
    if (!nestedRunner) return false;
    runner = nestedRunner;
    return true;
  }, ctx);
  return matched ? runner : null;
}

function packageScriptPassthroughRunner(words, context) {
  const ctx = proofContext(context);
  const name = packageScriptName(words, isRunnerPassthroughScript);
  if (!name) return null;
  if (!hasProofStack(ctx, 'js-package')) return null;
  const script = ctx.packageScripts.get(name);
  if (!script || ctx.depth >= 4 || ctx.visitedScripts.has(name)) return null;
  return packageScriptDirectRunner(script, {
    ...ctx,
    depth: ctx.depth + 1,
    visitedScripts: new Set([...ctx.visitedScripts, name]),
  });
}

function hasGenericPackageScriptRunnerNoOpOption(words, context = {}) {
  const start = genericPackageScriptRunnerArgStart(words);
  if (start < 0) return false;
  const args = words.slice(start);
  const runner = packageScriptPassthroughRunner(words, context);
  if (runner && hasUnsafeRunnerProofOption(runner, args)) return true;
  if (args.some(isPytestMetadataNoOpProofFlag) || args.some(hasJestMetadataNoOpProofFlag) || hasNodeTestNoOpArgs(args)) return true;
  return hasUnsafePathValueOption(args, new Set(['-c', '--config', '-r', '--root', '--rootdir', ...nodeTestPathValueFlags]), /^--(?:config|root|rootdir|require|import|loader|experimental-loader|test-reporter|test-reporter-destination)=(.*)$/i, ['-c', '-r'], hasUnsafeConfigOptionValue) || hasUnsafeRunnerPositionalPath(args, new Set(['-c', '--config', '-r', '--root', '--rootdir', ...nodeTestValueFlags]), /^--(?:config|root|rootdir|test-name-pattern|test-skip-pattern|require|import|loader|experimental-loader|test-reporter|test-reporter-destination)=(.*)$/i, ['-c', '-r']);
}

function matchesPackageTest(words) {
  const command = packageCommand(words);
  if (!command) return false;
  const subcommand = lower(words[command.index]);
  if (subcommand === 'test') return true;
  if (command.manager !== 'npm' && isTestScript(subcommand)) return true;
  if (subcommand === 'run') return isTestScript(words[command.index + 1]);
  return false;
}

function packageScriptName(words, predicate) {
  const command = packageCommand(words);
  if (!command) return null;
  const subcommand = lower(words[command.index]);
  if (subcommand === 'test' && predicate('test')) return 'test';
  if (command.manager !== 'npm' && predicate(subcommand)) return subcommand;
  if (subcommand === 'run' && predicate(words[command.index + 1])) return words[command.index + 1];
  return null;
}

function hasProofStack(context, stack) {
  return proofContext(context).stacks.has(stack);
}

function packageScriptMatches(words, context, predicate, matcher) {
  const name = packageScriptName(words, predicate);
  if (!name || !hasProofStack(context, 'js-package')) return false;
  const ctx = proofContext(context);
  const script = ctx.packageScripts.get(name);
  if (!script || ctx.depth >= 4 || ctx.visitedScripts.has(name)) return false;
  return hasCommandMatching(script, matcher, {
    ...ctx,
    depth: ctx.depth + 1,
    visitedScripts: new Set([...ctx.visitedScripts, name]),
  });
}

function matchesPackageExecRunner(words, context) {
  const command = packageCommand(words);
  if (!command || !hasProofStack(context, 'js-package')) return false;
  const subcommand = lower(words[command.index]);
  return subcommand === 'exec' && npxTestRunners.has(lower(words[command.index + 1]));
}

function matchesNodeTestStackCommand(words, segment, exportedNoOpProofEnv, context) {
  if (hasNoOpProofOption(words, segment, exportedNoOpProofEnv, context)) return false;
  return lower(words[0]) === 'node' && lower(words[1]) === '--test';
}

function matchesTestRunner(words, segment, exportedNoOpProofEnv, context) {
  if (hasNoOpProofOption(words, segment, exportedNoOpProofEnv, context)) return false;
  const command = lower(words[0]);
  if (matchesPackageTest(words)) return packageScriptMatches(words, context, isTestScript, matchesTestRunner);
  if (matchesPackageExecRunner(words, context)) return true;
  if (command === 'npx') return hasProofStack(context, 'js-package') && npxTestRunners.has(lower(words[npxCommandIndex(words)]));
  if (command === 'node') return hasProofStack(context, 'node') && lower(words[1]) === '--test';
  if (directTestRunners.has(command)) return hasProofStack(context, command === 'pytest' ? 'python' : 'js-package');
  if ((command === 'python' || command === 'python3') && lower(words[1]) === '-m') return hasProofStack(context, 'python') && lower(words[2]) === 'pytest';
  if (['flutter', 'dart'].includes(command)) return hasProofStack(context, 'dart-flutter') && lower(words[1]) === 'test';
  if (command === 'go') return hasProofStack(context, 'go') && lower(words[1]) === 'test';
  if (command === 'cargo') return hasProofStack(context, 'cargo') && lower(words[1]) === 'test';
  if (isMavenCommand(command)) return hasProofStack(context, 'maven') && lower(words[buildToolTaskIndex(words, command)]) === 'test';
  if (command === 'gradle' || command === './gradlew') return hasProofStack(context, 'gradle') && isGradleTestTask(words[buildToolTaskIndex(words, command)]);
  if (command === 'make') return hasProofStack(context, 'make') && lower(words[makeTargetIndex(words)]) === 'test';
  return false;
}

function matchesMutationCommand(words, segment, exportedNoOpProofEnv, context) {
  if (hasNoOpProofOption(words, segment, exportedNoOpProofEnv, context)) return false;
  const command = lower(words[0]);
  const packageInfo = packageCommand(words);
  if (command === 'npx') {
    const index = npxCommandIndex(words);
    return hasProofStack(context, 'mutation') && lower(words[index]) === 'stryker' && lower(words[index + 1]) === 'run';
  }
  if (command === 'stryker') return hasProofStack(context, 'mutation') && lower(words[1]) === 'run';
  if (packageInfo) {
    return packageScriptMatches(words, context, isMutationScript, matchesMutationCommand);
  }
  if (mutationCommands.has(command)) return hasProofStack(context, 'mutation');
  if (command === 'cargo') return hasProofStack(context, 'cargo') && lower(words[1]) === 'mutants';
  return command === 'make' && hasProofStack(context, 'make') && /^(?:mutation|mutate|mutants?)$/i.test(words[makeTargetIndex(words)] || '');
}

function matchesMakeItFailCommand(words, segment, exportedNoOpProofEnv, context) {
  if (hasNoOpProofOption(words, segment, exportedNoOpProofEnv, context)) return false;
  const command = lower(words[0]);
  const packageInfo = packageCommand(words);
  if (packageInfo) {
    return packageScriptMatches(words, context, isMakeItFailScript, matchesTestRunner);
  }
  return command === 'make' && hasProofStack(context, 'make') && /^(?:make[- ]?it[- ]?fail|test[- ]?fail|fail[- ]?test)$/i.test(words[makeTargetIndex(words)] || '');
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

function hasCommandMatching(command, matcher, options = {}) {
  const context = proofContext(options);
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
    if (executeStatuses.size > 0 && keywordMode(segment) === true) return false;
    if (executeStatuses.size > 0 && isTerminalCommand(segment)) return false;
    if (executeStatuses.size > 0 && hasProofEnvMutation(segment) && (isConditionalSeparator(separator) || isConditionalSeparator(separatorAfter))) return false;
    const words = commandWords(segment);
    if (proofReachable && !dynamicRunnerOverride && matcher(words, segment, proofEnvState.noOp, context) && isUnmaskedProofSegment(segments, index, errexit)) return true;
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

export function hasTestFirstProofCommand(command, options = {}) {
  const context = proofContext(options);
  return hasCommandMatching(command, matchesTestRunner, context) || hasCommandMatching(command, matchesMutationCommand, context) || hasCommandMatching(command, matchesMakeItFailCommand, context);
}

export function hasImplementationProofCommand(command, options = {}) {
  return hasCommandMatching(command, matchesTestRunner, proofContext(options));
}

function hasExpectedRedContradiction(text) {
  for (const [, expected, actual] of String(text || '').matchAll(expectedRedClausePattern)) {
    if (expectedFailurePattern.test(expected) && actualPassedContradictionPattern.test(actual) && !redFailureCountPattern.test(actual)) return true;
  }
  return false;
}

function hasExpectationOnlyRedCount(text) {
  return (expectationOnlyFailurePattern.test(text) || trailingExpectationOnlyFailurePattern.test(text)) && !actualRedOutputPattern.test(text);
}

function hasExpectationOnlyMutationProof(text) {
  return (mutationExpectationOnlyPattern.test(text) || trailingExpectationOnlyMutationPattern.test(text)) && !actualMutationOutputPattern.test(text);
}

function hasExpectationOnlyGreenProof(text) {
  return (expectationOnlyGreenPattern.test(text) || trailingExpectationOnlyGreenPattern.test(text)) && !actualGreenOutputPattern.test(text);
}

export function hasRedProof(text) {
  if (redCountContradictionPattern.test(text) || hasExpectedRedContradiction(text) || hasExpectationOnlyRedCount(text) || hasExpectationOnlyMutationProof(text)) return false;
  if (redFailureCountPattern.test(text) || mutationCountProofPattern.test(text)) return true;
  if (redProofContradictionPattern.test(text)) return false;
  return !notRedProofPattern.test(text) && (redProofPattern.test(text) || mutationProofPattern.test(text) || hasMakeItFailProof(text));
}

function hasRedTestProof(text) {
  if (redCountContradictionPattern.test(text) || hasExpectedRedContradiction(text) || hasExpectationOnlyRedCount(text)) return false;
  if (redFailureCountPattern.test(text)) return true;
  if (redProofContradictionPattern.test(text)) return false;
  if (mutationProofPattern.test(text) || mutationCountProofPattern.test(text) || makeItFailProofPattern.test(text)) return false;
  return !notRedProofPattern.test(text) && redProofPattern.test(text);
}

function hasMutationProof(text) {
  return !mutationProofContradictionPattern.test(text) && !hasExpectationOnlyMutationProof(text) && mutationCountProofPattern.test(text);
}

function hasMakeItFailProof(text) {
  if (makeItFailProofContradictionPattern.test(text) || makeItFailExpectationOnlyPattern.test(text)) return false;
  return makeItFailProofPattern.test(text);
}

export function hasGreenProof(text) {
  return !failedProofPattern.test(text) && !hasExpectationOnlyGreenProof(text) && greenProofPattern.test(text);
}

export function hasTestQualityEvidence(guardrail) {
  const text = normalizedTestQualityEvidence(evidenceText(guardrail));
  return !negatedTestQualityPattern.test(text) && positiveTestQualityPattern.test(text);
}

function hasMatchingTestFirstProof(command, text, options = {}) {
  const context = proofContext(options);
  return (hasCommandMatching(command, matchesTestRunner, context) && hasRedTestProof(text))
    || (hasCommandMatching(command, matchesMutationCommand, context) && hasMutationProof(text))
    || (hasCommandMatching(command, matchesMakeItFailCommand, context) && hasMakeItFailProof(text));
}

export function matchesTestFirstProofGuardrail(guardrail, options = {}) {
  const proofOptions = guardrailProofOptions(guardrail, options);
  return guardrail?.id === 'test-first-proof' && guardrail?.stage === 'he-implement' && guardrail?.kind === 'test' && hasMatchingTestFirstProof(guardrail?.command || '', evidenceText(guardrail), proofOptions) && hasTestQualityEvidence(guardrail);
}

export function matchesImplementationProofGuardrail(guardrail, options = {}) {
  const proofOptions = guardrailProofOptions(guardrail, options);
  return guardrail?.id === 'implementation-proof' && guardrail?.stage === 'he-implement' && guardrail?.kind === 'test' && hasImplementationProofCommand(guardrail?.command || '', proofOptions) && hasGreenProof(evidenceText(guardrail));
}
