#!/usr/bin/env node
// HARD_ENG_SCANNER_OWNER: multi-stack quality gate scanner with focused behavior coverage.
import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';

const args = process.argv.slice(2);
let root = process.cwd();
let requirePushGate = false;
let json = false;

for (let index = 0; index < args.length; index += 1) {
  const arg = args[index];
  if (arg === '--require-push-gate') {
    requirePushGate = true;
  } else if (arg === '--json') {
    json = true;
  } else if (arg === '--help' || arg === '-h') {
    console.log(`Usage: check-project-quality-gates.mjs [--require-push-gate] [--json] [repo]

Checks whether a repo has deterministic quality gates for detected stacks.
It inspects active pre-push hooks, hook-referenced package scripts, and repo-local .no-mistakes.yaml commands.`);
    process.exit(0);
  } else {
    root = path.resolve(arg);
  }
}

root = path.resolve(root);

function exists(file) {
  return fs.existsSync(path.isAbsolute(file) ? file : path.join(root, file));
}

function read(file) {
  try {
    return fs.readFileSync(path.isAbsolute(file) ? file : path.join(root, file), 'utf8');
  } catch {
    return '';
  }
}

function readJson(file) {
  try {
    return JSON.parse(read(file));
  } catch {
    return null;
  }
}

function gitOutput(gitArgs) {
  const result = spawnSync('git', gitArgs, { cwd: root, encoding: 'utf8' });
  return result.status === 0 ? result.stdout.trim() : '';
}

const ignoredDirectoryNames = new Set([
  '.cache',
  '.codebase',
  '.dart_tool',
  '.git',
  '.next',
  '.turbo',
  'build',
  'coverage',
  'dist',
  'node_modules',
  'outputs',
  'target',
  'tmp',
  'vendor',
]);

function collectNestedGitRoots(dir = '', depth = 0, out = []) {
  if (depth > 7 || out.length > 500) return out;
  let entries = [];
  try {
    entries = fs.readdirSync(path.join(root, dir), { withFileTypes: true });
  } catch {
    return out;
  }
  const hasGitMarker = entries.some((entry) => entry.name === '.git' && (entry.isDirectory() || entry.isFile()));
  if (dir && hasGitMarker) {
    out.push(dir.split(path.sep).join('/'));
    return out;
  }
  for (const entry of entries) {
    if (!entry.isDirectory() || ignoredDirectoryNames.has(entry.name)) continue;
    collectNestedGitRoots(path.join(dir, entry.name), depth + 1, out);
  }
  return out;
}

function trackedSubmodulePaths() {
  const output = gitOutput(['ls-files', '-s']);
  const paths = new Set();
  for (const line of output.split('\n')) {
    const match = line.match(/^160000\s+\S+\s+\d+\t(.+)$/);
    if (match) paths.add(match[1].replaceAll('\\', '/'));
  }
  return paths;
}

const nestedGitRepos = collectNestedGitRoots();
const nestedGitRepoSet = new Set(nestedGitRepos);
const submodulePathSet = trackedSubmodulePaths();
function nestedRepoHasNoMistakesConfig(entry) {
  return fs.existsSync(path.join(root, entry, '.no-mistakes.yaml'));
}
const configuredNestedGitRepos = nestedGitRepos.filter((entry) => (
  !submodulePathSet.has(entry) && nestedRepoHasNoMistakesConfig(entry)
));
const configuredNestedGitRepoSet = new Set(configuredNestedGitRepos);
const unmanagedNestedGitRepos = nestedGitRepos.filter((entry) => (
  !submodulePathSet.has(entry) && !configuredNestedGitRepoSet.has(entry)
));

const maxInventoryDepth = 7;
const maxInventoryFiles = 5000;
const inventoryTruncations = new Set();

function walk(dir, depth, out) {
  if (depth > maxInventoryDepth) {
    inventoryTruncations.add(`at depth ${maxInventoryDepth}: ${dir.split(path.sep).join('/')}`);
    return;
  }
  if (out.length >= maxInventoryFiles) {
    inventoryTruncations.add(`at file limit ${maxInventoryFiles}`);
    return;
  }
  let entries = [];
  try {
    entries = fs.readdirSync(path.join(root, dir), { withFileTypes: true });
  } catch {
    return;
  }
  for (const entry of entries) {
    if (out.length >= maxInventoryFiles) {
      inventoryTruncations.add(`at file limit ${maxInventoryFiles}`);
      return;
    }
    const rel = path.join(dir, entry.name);
    const normalizedRel = rel.split(path.sep).join('/');
    if (ignoredDirectoryNames.has(entry.name) || nestedGitRepoSet.has(normalizedRel)) continue;
    if (entry.isDirectory()) walk(rel, depth + 1, out);
    else if (entry.isFile()) out.push(rel.split(path.sep).join('/'));
  }
}

function scriptsFor(file) {
  const pkg = readJson(file);
  return pkg?.scripts && typeof pkg.scripts === 'object' ? pkg.scripts : {};
}

const files = [];
walk('', 0, files);
const packageFiles = files.filter((file) => file.endsWith('package.json'));
const packageScripts = new Map();
const packageScriptEntries = [];
const packageRootNames = new Map();

function scriptKey(rootDir, name) {
  return `${rootDir}\0${name}`;
}

for (const file of packageFiles) {
  const rootDir = parentDir(file);
  const pkg = readJson(file) || {};
  if (typeof pkg.name === 'string' && pkg.name.trim()) packageRootNames.set(pkg.name.trim(), rootDir);
  const scripts = scriptsFor(file);
  for (const [name, body] of Object.entries(scripts)) {
    const entry = { key: scriptKey(rootDir, name), root: rootDir, name, body: String(body) };
    packageScripts.set(entry.key, entry);
    packageScriptEntries.push(entry);
  }
}

function depsFor(file) {
  const pkg = readJson(file) || {};
  return {
    ...pkg.dependencies,
    ...pkg.devDependencies,
    ...pkg.peerDependencies,
    ...pkg.optionalDependencies,
  };
}

const allDeps = Object.assign({}, ...packageFiles.map(depsFor));
const hasPackage = packageFiles.length > 0;
const appSourcePattern = /^(src|app|pages|components|lib|apps\/[^/]+\/(src|app|pages|components|lib)|packages\/[^/]+\/(src|app|pages|components|lib))\//;
const hasJsTsSource = files.some((file) => appSourcePattern.test(file) && /\.(tsx?|jsx?)$/.test(file));
const hasTs = files.some((file) => appSourcePattern.test(file) && /\.tsx?$/.test(file)) || files.some((file) => file.endsWith('tsconfig.json'));
const isReact = Boolean(allDeps.react || allDeps.next) || files.some((file) => appSourcePattern.test(file) && /\.(tsx|jsx)$/.test(file));
const isJsTs = hasPackage || hasJsTsSource;
const pubspecs = files.filter((file) => file.endsWith('pubspec.yaml'));
const isFlutter = pubspecs.some((file) => /(^|\n)\s*flutter\s*:/m.test(read(file)) || /\bflutter\s*:/m.test(read(file))) || exists('lib') && files.some((file) => file.endsWith('.dart'));
const hasFlutterTests = files.some((file) => /^test\/.*_test\.dart$/.test(file) || /^integration_test\/.*_test\.dart$/.test(file));
const isHardEng = exists('scripts/check-hard-eng-full-repo.mjs') && exists('skills/workflow-help/references/route-map.md');

function parentDir(file) {
  const dir = path.posix.dirname(file);
  return dir === '.' ? '.' : dir;
}

function relativeToRoot(file, rootDir) {
  if (rootDir === '.') return file;
  return file.startsWith(`${rootDir}/`) ? file.slice(rootDir.length + 1) : '';
}

function underRoot(file, rootDir) {
  return rootDir === '.' || file === rootDir || file.startsWith(`${rootDir}/`);
}

function rootFiles(rootDir) {
  return files.filter((file) => underRoot(file, rootDir)).map((file) => relativeToRoot(file, rootDir));
}

function rootHasFile(rootDir, name) {
  return exists(rootDir === '.' ? name : `${rootDir}/${name}`);
}

function rootHasPattern(rootDir, pattern) {
  return rootFiles(rootDir).some((file) => pattern.test(file));
}

const projectRoots = [];

function addProjectRoot(stack, rootDir, marker, options = {}) {
  const normalizedRoot = rootDir || '.';
  const key = `${stack}:${normalizedRoot}`;
  const existing = projectRoots.find((entry) => entry.key === key);
  if (existing) {
    existing.markers.push(marker);
    existing.testsPresent ||= Boolean(options.testsPresent);
    existing.hasTypeScript ||= Boolean(options.hasTypeScript);
    return;
  }
  projectRoots.push({
    key,
    stack,
    root: normalizedRoot,
    markers: [marker],
    testsPresent: Boolean(options.testsPresent),
    hasTypeScript: Boolean(options.hasTypeScript),
  });
}

function packageRootInfo(file) {
  const rootDir = parentDir(file);
  const deps = depsFor(file);
  const rootRelativeFiles = rootFiles(rootDir);
  const sourceFiles = rootRelativeFiles.filter((entry) => /\.(tsx?|jsx?)$/.test(entry) && !entry.endsWith('.d.ts'));
  const testsPresent = rootRelativeFiles.some((entry) => /(^|\/)(__tests__|test|tests|spec)\//.test(entry) || /\.(test|spec)\.[cm]?[jt]sx?$/.test(entry));
  const hasTypeScriptInRoot = Boolean(deps.typescript) || rootHasFile(rootDir, 'tsconfig.json') || sourceFiles.some((entry) => /\.tsx?$/.test(entry));
  const isReactRoot = Boolean(deps.react || deps.next) || sourceFiles.some((entry) => /\.(tsx|jsx)$/.test(entry));
  return { rootDir, testsPresent, hasTypeScriptInRoot, isReactRoot };
}

for (const file of packageFiles) {
  const info = packageRootInfo(file);
  addProjectRoot('js-ts', info.rootDir, file, {
    testsPresent: info.testsPresent,
    hasTypeScript: info.hasTypeScriptInRoot,
  });
  if (info.isReactRoot) {
    addProjectRoot('react', info.rootDir, file, {
      testsPresent: info.testsPresent,
      hasTypeScript: info.hasTypeScriptInRoot,
    });
  }
}

for (const file of pubspecs) {
  const rootDir = parentDir(file);
  const text = read(file);
  const stack = /(^|\n)\s*flutter\s*:/m.test(text) || /\bflutter\s*:/m.test(text) ? 'flutter' : 'dart';
  addProjectRoot(stack, rootDir, file, {
    testsPresent: rootHasPattern(rootDir, /^test\/.*_test\.dart$/) || rootHasPattern(rootDir, /^integration_test\/.*_test\.dart$/),
  });
}

for (const marker of ['pyproject.toml', 'setup.py', 'setup.cfg', 'requirements.txt', 'Pipfile']) {
  for (const file of files.filter((entry) => path.posix.basename(entry) === marker)) {
    const rootDir = parentDir(file);
    addProjectRoot('python', rootDir, file, {
      testsPresent: rootHasPattern(rootDir, /(^|\/)(test|tests)\/.*\.py$/) || rootHasPattern(rootDir, /(^|\/)test_.*\.py$/) || rootHasPattern(rootDir, /(^|\/).*_test\.py$/),
    });
  }
}

for (const file of files.filter((entry) => entry.endsWith('go.mod'))) addProjectRoot('go', parentDir(file), file, { testsPresent: rootHasPattern(parentDir(file), /_test\.go$/) });
for (const file of files.filter((entry) => entry.endsWith('Cargo.toml'))) addProjectRoot('rust', parentDir(file), file, { testsPresent: true });
for (const file of files.filter((entry) => /(^|\/)(pom\.xml|build\.gradle|build\.gradle\.kts)$/.test(entry))) addProjectRoot('java', parentDir(file), file, { testsPresent: true });
for (const file of files.filter((entry) => /(^|\/)(Package\.swift)$/.test(entry))) addProjectRoot('swift', parentDir(file), file, { testsPresent: true });
for (const file of files.filter((entry) => /\.(sln|csproj)$/.test(entry))) addProjectRoot('dotnet', parentDir(file), file, { testsPresent: true });
for (const file of files.filter((entry) => /(^|\/)(Gemfile|[^/]+\.gemspec)$/.test(entry))) addProjectRoot('ruby', parentDir(file), file, { testsPresent: rootHasPattern(parentDir(file), /(^|\/)(test|spec)\//) });
for (const file of files.filter((entry) => /(^|\/)composer\.json$/.test(entry))) addProjectRoot('php', parentDir(file), file, { testsPresent: rootHasPattern(parentDir(file), /(^|\/)(test|tests|spec)\//) });

const terraformRoots = new Set(files
  .filter((entry) => entry.endsWith('.tf') && !entry.includes('/.terraform/'))
  .map(parentDir));
for (const rootDir of terraformRoots) addProjectRoot('terraform', rootDir, `${rootDir}/`);

const scannerScripts = files.filter((entry) => (
  /^(scripts|tools|bin)\/(?:check-|scan-|[^/]*scanner[^/]*)[^/]*\.(mjs|cjs|js|ts|sh)$/.test(entry)
));

function stripInlineComment(value) {
  let quote = '';
  for (let index = 0; index < value.length; index += 1) {
    const char = value[index];
    if ((char === '"' || char === "'") && value[index - 1] !== '\\') {
      quote = quote === char ? '' : quote || char;
    }
    if (char === '#' && !quote && /\s/.test(value[index - 1] || ' ')) return value.slice(0, index).trim();
  }
  return value.trim();
}

function unquoteYamlScalar(value) {
  const stripped = stripInlineComment(value);
  if ((stripped.startsWith('"') && stripped.endsWith('"')) || (stripped.startsWith("'") && stripped.endsWith("'"))) {
    return stripped.slice(1, -1).trim();
  }
  return stripped.trim();
}

function parseNoMistakesConfig() {
  const configPath = '.no-mistakes.yaml';
  const text = read(configPath);
  const commands = {};
  const commandTexts = { test: '', lint: '', format: '' };
  if (!text) return { exists: false, commands, scripts: [], text: '', commandTexts };
  const lines = text.replace(/\r\n/g, '\n').split('\n');
  const commandsLine = lines.findIndex((line) => /^commands\s*:\s*(?:#.*)?$/.test(line));
  if (commandsLine === -1) return { exists: true, commands, scripts: [], text: '', commandTexts };
  for (let index = commandsLine + 1; index < lines.length; index += 1) {
    const line = lines[index];
    if (/^\S/.test(line) && line.trim()) break;
    const match = line.match(/^\s{2,}(test|lint|format)\s*:\s*(.*)$/);
    if (!match) continue;
    let value = unquoteYamlScalar(match[2]);
    if (/^[>|]/.test(value)) {
      const blockLines = [];
      for (let blockIndex = index + 1; blockIndex < lines.length; blockIndex += 1) {
        const blockLine = lines[blockIndex];
        if (/^\s{4,}\S/.test(blockLine)) blockLines.push(blockLine.trim());
        else if (blockLine.trim()) break;
      }
      value = blockLines.join('\n').trim();
    }
    commands[match[1]] = value;
  }
  const expandedCommands = {
    test: expandPackageScriptReferences(commands.test || ''),
    lint: expandPackageScriptReferences(commands.lint || ''),
    format: expandPackageScriptReferences(commands.format || ''),
  };
  const scripts = new Set();
  for (const expanded of Object.values(expandedCommands)) {
    for (const script of expanded.scriptNames) scripts.add(script);
  }
  commandTexts.test = expandedCommands.test.text;
  commandTexts.lint = expandedCommands.lint.text;
  commandTexts.format = expandedCommands.format.text;
  const textForChecks = [commandTexts.test, commandTexts.lint].filter((value) => value.trim()).join('\n');
  return { exists: true, commands, scripts: [...scripts], text: textForChecks, commandTexts };
}

function escapeRegExp(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function stripShellComments(text) {
  const source = String(text || '');
  let output = '';
  let quote = null;
  let escaped = false;
  for (let index = 0; index < source.length; index += 1) {
    const char = source[index];
    if (escaped) {
      output += char;
      escaped = false;
      continue;
    }
    if (char === '\\' && quote !== "'") {
      output += char;
      escaped = true;
      continue;
    }
    if (quote) {
      output += char;
      if (char === quote) quote = null;
      continue;
    }
    if (char === "'" || char === '"') {
      quote = char;
      output += char;
      continue;
    }
    const previous = source[index - 1] || '';
    if (char === '#' && (!previous || /\s|[;&|()]/.test(previous))) {
      while (index < source.length && source[index] !== '\n') {
        output += ' ';
        index += 1;
      }
      if (index < source.length) output += '\n';
      continue;
    }
    output += char;
  }
  return output;
}

function shellCommandRecords(text) {
  const source = stripShellComments(text);
  const records = [];
  let start = 0;
  let separator = 'sequence';
  let quote = null;
  let escaped = false;
  const push = (end) => {
    const segment = source.slice(start, end).trim();
    if (segment) records.push({ segment, start, separator });
  };
  for (let index = 0; index < source.length; index += 1) {
    const char = source[index];
    if (escaped) {
      escaped = false;
      continue;
    }
    if (char === '\\' && quote !== "'") {
      escaped = true;
      continue;
    }
    if (quote) {
      if (char === quote) quote = null;
      continue;
    }
    if (char === "'" || char === '"') {
      quote = char;
      continue;
    }
    const controlLength = shellControlLengthAt(source, index);
    if (!controlLength) continue;
    push(index);
    separator = source[index] === '&' && source[index + 1] === '&'
      ? '&&'
      : source[index] === '|' && source[index + 1] === '|'
        ? '||'
        : 'sequence';
    index += controlLength - 1;
    start = index + 1;
  }
  push(source.length);
  return records;
}

function shellWords(segment) {
  const words = [];
  let word = '';
  let quote = null;
  let escaped = false;
  const push = () => {
    if (word) words.push(word);
    word = '';
  };
  for (const char of String(segment || '')) {
    if (escaped) {
      word += char;
      escaped = false;
      continue;
    }
    if (char === '\\' && quote !== "'") {
      escaped = true;
      continue;
    }
    if (quote) {
      if (char === quote) quote = null;
      else word += char;
      continue;
    }
    if (char === "'" || char === '"') {
      quote = char;
      continue;
    }
    if (/\s/.test(char)) {
      push();
      continue;
    }
    word += char;
  }
  push();
  return words;
}

function normalizedShellWord(word) {
  return String(word || '').replace(/^[!({]+/, '').replace(/[)}]+$/, '');
}

function executableInvocation(record) {
  const words = shellWords(record.segment).map(normalizedShellWord).filter(Boolean);
  let index = 0;
  while (['if', 'then', 'elif', 'else', 'do', 'while', 'until', 'time', '!'].includes(words[index]?.toLowerCase())) index += 1;
  while (/^[A-Za-z_][A-Za-z0-9_]*\+?=/.test(words[index] || '')) index += 1;
  if (words[index]?.toLowerCase() === 'env') {
    index += 1;
    while (/^-|^[A-Za-z_][A-Za-z0-9_]*\+?=/.test(words[index] || '')) index += 1;
  }
  while (['command', 'builtin', 'exec'].includes(words[index]?.toLowerCase())) index += 1;
  const invocationWords = words.slice(index);
  if (!invocationWords.length) return null;
  return {
    ...record,
    words: invocationWords,
    executable: invocationWords[0].toLowerCase(),
    invocation: invocationWords.join(' '),
  };
}

function executableShellCommands(text) {
  const passiveCommands = new Set([':', '[', 'echo', 'false', 'printf', 'test', 'true']);
  const commands = [];
  let priorStatus = 'success';
  for (const entry of shellCommandRecords(text)) {
    const mayRun = entry.separator === 'sequence' ||
      (entry.separator === '&&' && priorStatus !== 'failure') ||
      (entry.separator === '||' && priorStatus !== 'success');
    if (!mayRun) continue;
    const record = executableInvocation(entry);
    if (record && !passiveCommands.has(path.posix.basename(record.executable)) && !passiveCommands.has(commandTool(record).tool)) {
      commands.push(record);
    }
    const executable = shellWords(entry.segment).map(normalizedShellWord).filter(Boolean)[0]?.toLowerCase();
    priorStatus = executable === 'false' ? 'failure' : [':', 'echo', 'printf', 'true'].includes(executable) ? 'success' : 'unknown';
  }
  return commands;
}

function executableShellText(text) {
  return executableShellCommands(text).map((record) => record.invocation).join('\n');
}

function commandTool(record) {
  const words = [...record.words];
  let index = 0;
  let tool = path.posix.basename(words[index]?.toLowerCase() || '');
  if (['bunx', 'npx'].includes(tool)) {
    index += 1;
    while (words[index]?.startsWith('-')) index += 1;
  } else if (['npm', 'pnpm', 'yarn'].includes(tool) && ['dlx', 'exec', 'x'].includes(words[index + 1]?.toLowerCase())) {
    index += 2;
    while (words[index]?.startsWith('-')) index += 1;
  } else if (['bundle', 'poetry', 'uv'].includes(tool) && ['exec', 'run'].includes(words[index + 1]?.toLowerCase())) {
    index += 2;
  } else if (['node', 'nodejs'].includes(tool)) {
    index += 1;
    while (words[index]?.startsWith('-')) index += 1;
  } else if (/^python(?:\d+(?:\.\d+)*)?$/.test(tool) && words[index + 1] === '-m') {
    index += 2;
  }
  tool = path.posix.basename(words[index]?.toLowerCase() || '');
  return { tool, args: words.slice(index + 1).map((word) => word.toLowerCase()), words: words.slice(index) };
}

function formatterCommandMatches(record, stack) {
  const { tool, args, words } = commandTool(record);
  const invocation = words.join(' ');
  const nonMutating = args.some((arg) => [
    '--check',
    '--diff',
    '--dry-run',
    '--dryrun',
    '--list-different',
    '--lint',
    '--test',
    '--verify-no-changes',
    '-check',
    '-n',
    '-write=false',
  ].includes(arg));
  if (nonMutating) return false;
  if (stack === 'hard-eng') return tool === 'format-hard-eng.mjs';
  if (['js-ts', 'react'].includes(stack)) {
    return (tool === 'prettier' && args.some((arg) => ['--write', '-w'].includes(arg))) ||
      (tool === 'biome' && ['format', 'check'].includes(args[0]) && args.includes('--write')) ||
      (tool === 'dprint' && args[0] === 'fmt') ||
      (tool === 'deno' && args[0] === 'fmt') ||
      (tool === 'eslint' && args.includes('--fix')) ||
      tool === 'format-hard-eng.mjs';
  }
  if (['flutter', 'dart'].includes(stack)) {
    const outputIndex = args.findIndex((arg) => ['-o', '--output'].includes(arg));
    const output = args.find((arg) => arg.startsWith('--output='))?.split('=')[1] || (outputIndex === -1 ? '' : args[outputIndex + 1]);
    return ['dart', 'flutter'].includes(tool) && args[0] === 'format' &&
      (outputIndex === -1 || Boolean(args[outputIndex + 1])) && !['none', 'show'].includes(output);
  }
  if (stack === 'python') {
    if (tool === 'ruff') return args[0] === 'format';
    if (['autopep8', 'yapf'].includes(tool)) return args.some((arg) => ['-i', '--in-place'].includes(arg));
    return tool === 'black' && !args.includes('--code') && !args.includes('-');
  }
  if (stack === 'go') return (tool === 'go' && args[0] === 'fmt' && args.includes('./...')) || (tool === 'gofmt' && args.includes('-w'));
  if (stack === 'rust') return tool === 'cargo' && args[0] === 'fmt' && args.some((arg) => ['--all', '--workspace'].includes(arg));
  if (stack === 'java') return /(?:^|\s)(?:spotlessapply|spotless:apply)(?:\s|$)/i.test(invocation) ||
    tool === 'google-java-format' && args.some((arg) => ['-i', '--replace'].includes(arg));
  if (stack === 'swift') return tool === 'swiftformat' || tool === 'swift-format' && args[0] === 'format' && args.some((arg) => ['-i', '--in-place'].includes(arg));
  if (stack === 'dotnet') return tool === 'dotnet' && args[0] === 'format';
  if (stack === 'ruby') return (tool === 'rubocop' && args.some((arg) => ['-a', '--autocorrect'].includes(arg))) || (tool === 'standardrb' && args.includes('--fix'));
  if (stack === 'php') return tool === 'php-cs-fixer' && args[0] === 'fix' || tool === 'pint';
  if (stack === 'terraform') return tool === 'terraform' && args[0] === 'fmt' && args.includes('-recursive');
  return false;
}

function commandUsesFormatterForStack(command, stack) {
  return executableShellCommands(command).some((record) => formatterCommandMatches(record, stack));
}

function executablePathPresent(text, expectedPath) {
  const expectedTool = path.posix.basename(expectedPath);
  return executableShellCommands(text).some((record) => {
    const { tool, words } = commandTool(record);
    return tool === expectedTool && words[0]?.endsWith(expectedPath);
  });
}

function commandSegmentAround(text, index) {
  const start = commandBoundaryBefore(text, index);
  const end = commandBoundaryAfter(text, index);
  return text.slice(start, end);
}

function shellControlLengthAt(text, index) {
  if (text[index] === '\n' || text[index] === ';') return 1;
  if (text[index] === '&' && text[index + 1] === '&') return 2;
  if (text[index] === '|' && text[index + 1] === '|') return 2;
  if (text[index] === '&' || text[index] === '|') return 1;
  return 0;
}

function commandBoundaryBefore(text, index) {
  for (let cursor = index - 1; cursor >= 0; cursor -= 1) {
    if (text[cursor] === '\n' || text[cursor] === ';') return cursor + 1;
    if ((text[cursor] === '&' && text[cursor - 1] === '&') || (text[cursor] === '|' && text[cursor - 1] === '|')) return cursor + 1;
    if (text[cursor] === '&' || text[cursor] === '|') return cursor + 1;
  }
  return 0;
}

function commandBoundaryAfter(text, index) {
  for (let cursor = index; cursor < text.length; cursor += 1) {
    if (shellControlLengthAt(text, cursor)) return cursor;
  }
  return text.length;
}

function unquoteShellValue(value) {
  const trimmed = String(value || '').trim();
  if ((trimmed.startsWith('"') && trimmed.endsWith('"')) || (trimmed.startsWith("'") && trimmed.endsWith("'"))) {
    return trimmed.slice(1, -1);
  }
  return trimmed;
}

function shellOptionValues(segment, flags) {
  const alternatives = flags.map(escapeRegExp).join('|');
  const pattern = new RegExp(`(?:^|\\s)(?:${alternatives})(?:=|\\s+)((?:"[^"]+"|'[^']+'|[^\\s;&|)]+))`, 'g');
  return [...String(segment || '').replaceAll('\\', '/').matchAll(pattern)].map((match) => unquoteShellValue(match[1]));
}

function isAllWorkspaceSelector(value) {
  const normalized = unquoteShellValue(value).replaceAll('\\', '/').trim();
  return normalized === '*' || normalized === './*';
}

function workspaceSelectorValues(segment) {
  const values = shellOptionValues(segment, ['--filter', '-F', '--workspace', '-w', '--scope', '--projects', '-p', '--from', '--include']);
  const yarnWorkspace = String(segment || '').replaceAll('\\', '/').match(/\byarn\s+workspace\s+((?:"[^"]+"|'[^']+'|[^\s;&|)]+))/i);
  if (yarnWorkspace) values.push(unquoteShellValue(yarnWorkspace[1]));
  return values.flatMap((value) => value.split(',').map((entry) => entry.trim()).filter(Boolean));
}

function hasScopedWorkspaceSelector(segment) {
  if (workspaceSelectorValues(segment).some((value) => value && !isAllWorkspaceSelector(value))) return true;
  return /(?:^|\s)(?:--exclude|--ignore|--since)(?:=|\s)|\bnx\s+affected\b/i.test(segment);
}

function packageRootsFromInvocationOptions(segment) {
  const normalized = segment.replaceAll('\\', '/');
  const roots = [...new Set(packageScriptEntries.map((entry) => entry.root))]
    .filter((entry) => entry !== '.')
    .sort((a, b) => b.length - a.length);
  const selected = new Set();
  const selectorValues = [
    ...workspaceSelectorValues(normalized),
    ...shellOptionValues(normalized, ['--prefix', '-C']),
  ];
  for (const value of selectorValues) {
    const selector = unquoteShellValue(value).replace(/^\.\//, '');
    if (isAllWorkspaceSelector(selector)) continue;
    if (packageRootNames.has(selector)) selected.add(packageRootNames.get(selector));
    if (roots.includes(selector)) selected.add(selector);
  }
  return [...selected];
}

const unknownShellCwd = '__unknown__';

function normalizeCdArgument(value) {
  const trimmed = String(value || '').trim();
  if (!trimmed) return null;
  const unquoted = ((trimmed.startsWith('"') && trimmed.endsWith('"')) || (trimmed.startsWith("'") && trimmed.endsWith("'")))
    ? trimmed.slice(1, -1)
    : trimmed;
  const normalized = unquoted.replaceAll('\\', '/').trim();
  if (!normalized || normalized === '-' || normalized.startsWith('/') || normalized.startsWith('~') || normalized.includes('$')) return null;
  return normalized;
}

function resolveShellCwd(cwd, target) {
  const normalizedTarget = normalizeCdArgument(target);
  if (!normalizedTarget) return unknownShellCwd;
  const base = cwd === '.' ? '' : cwd;
  const resolved = path.posix.normalize(path.posix.join(base, normalizedTarget));
  if (!resolved || resolved === '.') return '.';
  if (resolved === '..' || resolved.startsWith('../')) return unknownShellCwd;
  return resolved.replace(/\/$/, '');
}

function packageRootForCwd(cwd) {
  if (!cwd || cwd === '.' || cwd === unknownShellCwd) return null;
  const roots = [...new Set(packageScriptEntries.map((entry) => entry.root))]
    .filter((entry) => entry !== '.')
    .sort((a, b) => b.length - a.length);
  for (const candidate of roots) {
    if (cwd === candidate) return candidate;
  }
  return null;
}

function shellCwdBefore(text, index) {
  const prefix = text.slice(0, index);
  const cdPattern = /(?:^|[;&|]\s*|\(\s*)cd\s+((?:"[^"]+"|'[^']+'|[^\s;&|)]+))/g;
  let cwd = '.';
  for (const match of prefix.matchAll(cdPattern)) {
    cwd = resolveShellCwd(cwd, match[1]);
    if (cwd === unknownShellCwd) return unknownShellCwd;
  }
  return cwd;
}

function isRecursiveScriptInvocation(segment, name) {
  const escaped = escapeRegExp(name);
  return [
    new RegExp(`\\bpnpm\\b(?=[^\\n;&|]*(?:^|\\s)(?:-r|--recursive)(?:\\s|$))[^\\n;&|]*\\brun\\s+${escaped}\\b`, 'i'),
    new RegExp(`\\bnpm\\b(?=[^\\n;&|]*(?:^|\\s)--workspaces?(?:\\s|$))[^\\n;&|]*\\brun\\s+${escaped}\\b`, 'i'),
    new RegExp(`\\bnpm\\s+run\\s+${escaped}\\b(?=[^\\n;&|]*(?:^|\\s)--workspaces?(?:\\s|$))`, 'i'),
    new RegExp(`\\byarn\\s+workspaces?\\b[^\\n;&|]*\\brun\\s+${escaped}\\b`, 'i'),
    new RegExp(`\\blerna\\s+run\\s+${escaped}\\b`, 'i'),
    new RegExp(`\\bturbo\\s+run\\s+${escaped}\\b`, 'i'),
    new RegExp(`\\bnx\\s+run-many\\b(?=[^\\n;&|]*(?:--target=|-t\\s+)${escaped}\\b)`, 'i'),
    new RegExp(`\\bbun\\b(?=[^\\n;&|]*(?:^|\\s)--filter(?:\\s|$))[^\\n;&|]*(?:run\\s+)?${escaped}\\b`, 'i'),
  ].some((pattern) => pattern && pattern.test(segment));
}

function packageRootsForScriptInvocation(sourceText, index, segment, name, defaultRoot) {
  const selectedRoots = packageRootsFromInvocationOptions(segment);
  if (selectedRoots.length) return selectedRoots;
  if (hasScopedWorkspaceSelector(segment)) return [];
  if (isRecursiveScriptInvocation(segment, name)) {
    return packageScriptEntries.filter((entry) => entry.name === name).map((entry) => entry.root);
  }
  return [packageRootForCwd(shellCwdBefore(sourceText, index)) || defaultRoot];
}

function queueScriptReferences(sourceText, queue, defaultRoot) {
  for (const record of executableShellCommands(sourceText)) {
    for (const name of invokedPackageScriptNames(record)) {
      for (const rootDir of packageRootsForScriptInvocation(sourceText, record.start, record.segment, name, defaultRoot)) {
        const entry = packageScripts.get(scriptKey(rootDir, name));
        if (entry) queue.push(entry);
      }
    }
  }
}

function displayScriptName(entry) {
  return entry.root === '.' ? entry.name : `${entry.root}:${entry.name}`;
}

function expandPackageScriptReferences(initialText) {
  let text = initialText || '';
  const queue = [];
  const seen = new Set();
  queueScriptReferences(text, queue, '.');
  while (queue.length) {
    const entry = queue.shift();
    if (seen.has(entry.key) || !packageScripts.has(entry.key)) continue;
    seen.add(entry.key);
    text += `\n# package script ${displayScriptName(entry)}\n${entry.body}\n`;
    queueScriptReferences(entry.body, queue, entry.root);
  }
  return {
    scriptNames: [...seen].map((key) => displayScriptName(packageScripts.get(key))),
    text,
  };
}

function hookFiles() {
  const candidates = [
    '.git/hooks/pre-push',
    '.husky/pre-push',
    '.githooks/pre-push',
    '.git-hooks/pre-push',
    'lefthook.yml',
    'lefthook.yaml',
    'pre-commit-config.yaml',
    '.pre-commit-config.yaml',
  ];
  const configured = gitOutput(['config', '--get', 'core.hooksPath']);
  if (configured) candidates.push(path.join(configured, 'pre-push'));
  return [...new Set(candidates)].filter((file) => exists(file));
}

function hookProvidesActiveEvidence(file, content) {
  if (path.basename(file) === 'pre-push') {
    try {
      fs.accessSync(path.isAbsolute(file) ? file : path.join(root, file), fs.constants.X_OK);
    } catch {
      return false;
    }
  }
  const topLevel = gitOutput(['rev-parse', '--show-toplevel']);
  if (topLevel.includes('/.no-mistakes/worktrees/')
    && /Managed by hard-eng installer/.test(content)
    && content.includes('if [[ "$(basename "$repo")" != ".agents" ]]; then')) {
    return false;
  }
  return true;
}

function collectHookEvidence() {
  const hooks = [];
  let text = '';
  for (const file of hookFiles()) {
    const content = read(file);
    if (!hookProvidesActiveEvidence(file, content)) continue;
    hooks.push(file);
    if (/pre-push/.test(file) || /pre-push/.test(content)) text += `\n# ${file}\n${content}\n`;
  }
  const expanded = expandPackageScriptReferences(text);
  return { hooks, scriptNames: expanded.scriptNames, text: expanded.text };
}

const evidence = collectHookEvidence();
const noMistakes = parseNoMistakesConfig();
const blockers = [];
const warnings = [];
const stacks = [...new Set([
  ...projectRoots.map((entry) => entry.stack),
  ...(isReact ? ['react'] : []),
  ...(isJsTs ? ['js-ts'] : []),
  ...(isFlutter ? ['flutter'] : []),
  ...(isHardEng ? ['hard-eng'] : []),
])];

function block(message) {
  blockers.push(message);
}

for (const truncation of inventoryTruncations) {
  block(`project file inventory truncated ${truncation}; reduce ignored generated content or split the repository before relying on this gate`);
}

for (const repoPath of unmanagedNestedGitRepos) {
  block(`unmanaged nested Git repo ${repoPath}; add .no-mistakes.yaml and initialize no-mistakes, convert it to a tracked submodule, or move it under an ignored artifact/cache root`);
}

if (requirePushGate && stacks.length && !evidence.text.trim()) {
  block(`detected ${stacks.join('/')} but found no pre-push gate evidence`);
}

function hasStack(stack) {
  return stacks.includes(stack);
}

function rootsFor(stack) {
  return projectRoots.filter((entry) => entry.stack === stack);
}

function anyRoot(stack, predicate) {
  return rootsFor(stack).some(predicate);
}

function hasAny(text, patterns) {
  return patterns.some((pattern) => pattern.test(text));
}

function rootPattern(rootDir) {
  const escaped = escapeRegExp(rootDir);
  return new RegExp(`(?:^|[\\s"'=:/])${escaped}(?:$|[\\s"'/;),])`);
}

function rootCoveredByCommand(text, project) {
  if (project.root === '.') return true;
  if (rootPattern(project.root).test(text)) return true;
  if (packageScriptTextCoversRoot(text, project.root)) return true;
  if (isHardEng && /\bscripts\/check-hard-eng-full-repo\.mjs\b/.test(text)) return true;
  if (['js-ts', 'react'].includes(project.stack) && hasUnscopedJsWorkspaceCommand(text)) return true;
  if (project.stack === 'python' && rootsFor('python').length === 1 && /\bpyrefly\s+check\b/.test(text)) return true;
  if (project.stack === 'go' && rootHasFile('.', 'go.work') && /\bgo\s+test\s+\.\/\.\.\./.test(text)) return true;
  if (project.stack === 'rust' && rootHasFile('.', 'Cargo.toml') && /\bcargo\s+(?:test|clippy)\b/i.test(text) && hasShellFlag(text, ['--workspace'])) return true;
  if (project.stack === 'java' && (rootHasFile('.', 'settings.gradle') || rootHasFile('.', 'settings.gradle.kts')) && /\b(?:gradle|\.\/gradlew)\s+(?:check|test|build)\b/.test(text)) return true;
  if (project.stack === 'dotnet' && files.some((file) => file.endsWith('.sln')) && /\bdotnet\s+test\b/.test(text)) return true;
  if (project.stack === 'terraform' && /\bfind\b[\s\S]*\bterraform\b[\s\S]*\bvalidate\b|\bterragrunt\b[\s\S]*\brun-all\b/i.test(text)) return true;
  return false;
}

function scannerCoveredByCommand(text, scanner) {
  if (new RegExp(`(?:^|[\\s"'])${escapeRegExp(scanner)}(?:$|[\\s"'])`).test(text)) return true;
  if (isHardEng && scanner !== 'scripts/check-hard-eng-full-repo.mjs' && /\bscripts\/check-hard-eng-full-repo\.mjs\b/.test(text)) return true;
  return false;
}

function validateScannerCoverage(label, text) {
  for (const scanner of scannerScripts) {
    if (!scannerCoveredByCommand(text, scanner)) block(`${label} must run repo scanner ${scanner}`);
  }
}

function validateProjectRootCoverage(label, text, projects = projectRoots) {
  for (const project of projects) {
    if (!rootCoveredByCommand(text, project)) {
      block(`${label} must cover ${project.stack} project root ${project.root} (${project.markers.join(', ')})`);
    }
  }
}

function hasUnscopedJsWorkspaceCommand(text) {
  const locator = /\b(?:turbo|nx|lerna|moon|pnpm|yarn|npm|bun)\b/gi;
  for (const match of text.matchAll(locator)) {
    const command = commandSegmentAround(text, match.index || 0);
    if (hasScopedWorkspaceSelector(command)) continue;
    if (/\bturbo\s+run\b|\bnx\s+run-many\b|\blerna\s+run\b|\bpnpm\b[\s\S]*?(?:-r|--recursive)\b|\byarn\s+workspaces\b|\bnpm\b[\s\S]*?--workspaces?\b|\bbun\b[\s\S]*?--filter(?:=|\s+)["']?(?:\*|\.\/\*)["']?/i.test(command)) {
      return true;
    }
  }
  return false;
}

function hasRepoRootArgument(text) {
  return /(?:^|[\s"'])(?:\.\/?|\.\/\.\.\.)(?:$|[\s"';),&|])/.test(text);
}

function hasShellFlag(text, flags) {
  const alternatives = flags.map(escapeRegExp).join('|');
  return new RegExp(`(?:^|[\\s"'])(?:${alternatives})(?:$|[\\s"';),&|])`, 'i').test(text);
}

function rootScopedPackageScriptText(text) {
  const nonRootScriptNames = new Set(packageScriptEntries.filter((entry) => entry.root !== '.').map(displayScriptName));
  let includeLine = true;
  const lines = [];
  for (const line of text.split('\n')) {
    const match = line.match(/^# package script (.+)$/);
    if (match) {
      includeLine = !nonRootScriptNames.has(match[1]);
      continue;
    }
    if (includeLine) lines.push(line);
  }
  return lines.join('\n');
}

function packageScriptTextCoversRoot(text, rootDir) {
  if (rootDir === '.') return false;
  return new RegExp(`^# package script ${escapeRegExp(rootDir)}:`, 'm').test(text);
}

function commandHasRepoWideFormatterScope(command, stack) {
  if (hasRepoRootArgument(command)) return true;
  if (stack === 'rust') return /\bcargo\s+fmt\b/i.test(command) && hasShellFlag(command, ['--all', '--workspace']);
  return false;
}

function repoWideFormatCoversProject(text, project) {
  if (project.root === '.') return false;
  const rootText = rootScopedPackageScriptText(text);
  for (const record of executableShellCommands(rootText)) {
    const command = record.segment;
    if (!formatterCommandMatches(record, project.stack)) continue;
    if (!commandHasRepoWideFormatterScope(command, project.stack)) continue;
    if (shellCwdBefore(rootText, record.start) !== '.') continue;
    return true;
  }
  return false;
}

function packageScriptFormatterCoversProject(text, project) {
  const lines = text.split('\n');
  for (let index = 0; index < lines.length; index += 1) {
    const match = lines[index].match(/^# package script (.+)$/);
    if (!match || !match[1].startsWith(`${project.root}:`)) continue;
    const body = [];
    for (let cursor = index + 1; cursor < lines.length && !lines[cursor].startsWith('# package script '); cursor += 1) {
      body.push(lines[cursor]);
    }
    if (commandUsesFormatterForStack(body.join('\n'), project.stack)) return true;
  }
  return false;
}

function explicitFormatCommandCoversProject(text, project) {
  const rootText = rootScopedPackageScriptText(text);
  for (const record of executableShellCommands(rootText)) {
    const command = record.segment;
    if (!formatterCommandMatches(record, project.stack)) continue;
    const cwd = shellCwdBefore(rootText, record.start);
    if (cwd === project.root) return true;
    if (cwd === '.' && rootPattern(project.root).test(command)) return true;
  }
  return false;
}

function loopBodyRunsCommandAtVariableRoot(body, variable, predicate) {
  const records = executableShellCommands(body);
  for (const [index, record] of records.entries()) {
    if (!predicate(record)) continue;
    const prior = records.slice(0, index);
    const lastCd = prior.findLast((entry) => commandTool(entry).tool === 'cd');
    if (!lastCd) continue;
    const cdArgs = commandTool(lastCd).args;
    const target = cdArgs[0] || '';
    if (![ `$${variable}`, `\${${variable}}` ].includes(target)) continue;
    if (/\)\s*$/.test(lastCd.segment)) continue;
    const between = body.slice(lastCd.start + lastCd.segment.length, record.start);
    if (/\n|;|\|\||(^|[^&])&([^&]|$)|(^|[^|])\|([^|]|$)/.test(between)) continue;
    return true;
  }
  return false;
}

function loopFormatCommandCoversProject(text, project) {
  const loopPattern = /\bfor\s+([A-Za-z_][A-Za-z0-9_]*)\s+in\s+([^;\n]+);\s*do([\s\S]*?)\bdone\b/g;
  for (const match of text.matchAll(loopPattern)) {
    const variable = match[1];
    const roots = match[2];
    const body = match[3].replaceAll('\\"', '"').replaceAll("\\'", "'");
    if (!rootPattern(project.root).test(roots)) continue;
    if (loopBodyRunsCommandAtVariableRoot(body, variable, (record) => formatterCommandMatches(record, project.stack))) return true;
  }
  return false;
}

function formatRootCoveredByCommand(text, project) {
  if (project.root === '.') return true;
  if (packageScriptFormatterCoversProject(text, project)) return true;
  if (explicitFormatCommandCoversProject(text, project)) return true;
  if (loopFormatCommandCoversProject(text, project)) return true;
  return repoWideFormatCoversProject(text, project);
}

function validateFormatProjectRootCoverage(label, text) {
  for (const project of projectRoots) {
    if (!formatRootCoveredByCommand(text, project)) {
      block(`${label} must cover ${project.stack} project root ${project.root} (${project.markers.join(', ')})`);
    }
  }
}

function directCommandRunsRole(record, stack, role) {
  const { tool, args } = commandTool(record);
  const invocation = record.invocation.toLowerCase();
  const passive = args.some((arg) => ['--help', '-h', '--version', 'version', 'help'].includes(arg));
  if (passive) return false;
  if (['js-ts', 'react'].includes(stack)) {
    if (role === 'lint') return ['biome', 'eslint', 'oxlint'].includes(tool) &&
      !args.some((arg) => ['--env-info', '--print-config'].includes(arg));
    if (args.some((arg) => ['--collect-only', '--list', '--listtests', '--list-tests'].includes(arg))) return false;
    return ['jest', 'vitest'].includes(tool) ||
      (tool === 'playwright' && args[0] === 'test' && !args.includes('--list')) ||
      (tool === 'cypress' && args[0] === 'run') ||
      /^node\s+--test\b/.test(invocation);
  }
  if (['flutter', 'dart'].includes(stack)) return ['dart', 'flutter'].includes(tool) && args[0] === (role === 'lint' ? 'analyze' : 'test');
  if (stack === 'python') {
    if (role === 'lint') return tool === 'pyrefly' && args[0] === 'check';
    if (tool === 'pytest') return !args.some((arg) => ['--collect-only', '--co', '--fixtures', '--fixtures-per-test', '--markers', '--setup-plan'].includes(arg));
    if (tool === 'tox') return !args.some((arg) => ['--showconfig', '--listenvs', '-l'].includes(arg));
    if (tool === 'nox') return !args.some((arg) => ['--list', '-l'].includes(arg));
    return tool === 'hatch' && args[0] === 'run' && args[1] === 'test' || /^python\s+-m\s+unittest\b/.test(invocation);
  }
  if (stack === 'go') return tool === 'go' && args[0] === 'test';
  if (stack === 'rust') return tool === 'cargo' && args[0] === (role === 'lint' ? 'clippy' : 'test') &&
    !args.some((arg) => ['--no-run', '--list'].includes(arg));
  if (stack === 'java') {
    const skipsTests = args.some((arg) => /^-d(?:skiptests|skipits|maven\.test\.skip)(?:=true)?$/.test(arg)) ||
      args.includes('--dry-run') || args.includes('-m') || args.some((arg, index) => (
        ['-x', '--exclude-task'].includes(arg) && /(?:^|:)test$/i.test(args[index + 1] || '')
      ));
    if (skipsTests) return false;
    return ['mvn', 'mvnw'].includes(tool) && args.some((arg) => ['test', 'verify', 'install'].includes(arg)) ||
      ['gradle', 'gradlew'].includes(tool) && args.some((arg) => ['test', 'check', 'build'].includes(arg));
  }
  if (stack === 'swift') return tool === 'swift' && args[0] === 'test' && !args.includes('--list-tests') ||
    tool === 'xcodebuild' && args.includes('test') && !args.includes('-list');
  if (stack === 'dotnet') return tool === 'dotnet' && args[0] === 'test' && !args.includes('--list-tests');
  if (stack === 'ruby') return ['rspec'].includes(tool) || tool === 'rake' && args[0] === 'test' || tool === 'rails' && args[0] === 'test' || /^ruby\s+-itest\b/.test(invocation);
  if (stack === 'php') return ['pest', 'phpunit'].includes(tool) || tool === 'composer' && (args[0] === 'test' || args[0] === 'run' && args[1] === 'test');
  if (stack === 'terraform') return role === 'lint' && tool === 'terraform' && ['fmt', 'validate'].includes(args[0]) || role === 'lint' && tool === 'terragrunt' && args.includes('validate');
  return false;
}

function invokedPackageScriptNames(record) {
  const words = record.words;
  const lowerWords = words.map((word) => word.toLowerCase());
  const manager = path.posix.basename(lowerWords[0] || '');
  const names = [];
  if (['bun', 'npm', 'pnpm', 'yarn'].includes(manager)) {
    const runIndex = lowerWords.lastIndexOf('run');
    if (runIndex !== -1 && words[runIndex + 1]) names.push(words[runIndex + 1]);
    else if (words[1] && !words[1].startsWith('-') && !['exec', 'x', 'dlx'].includes(lowerWords[1])) names.push(words[1]);
  } else if (['lerna', 'turbo'].includes(manager) && lowerWords[1] === 'run' && words[2]) {
    names.push(words[2]);
  } else if (manager === 'nx' && lowerWords[1] === 'run-many') {
    const targetIndexWithValue = lowerWords.findIndex((word) => /^--target=/.test(word));
    const targetIndex = lowerWords.findIndex((word) => ['--target', '-t'].includes(word));
    const target = targetIndexWithValue === -1 ? '' : words[targetIndexWithValue];
    if (target) names.push(target.slice(target.indexOf('=') + 1));
    else if (targetIndex !== -1 && words[targetIndex + 1]) names.push(words[targetIndex + 1]);
  }
  return names;
}

function packageScriptEntriesForInvocation(sourceText, record, defaultRoot) {
  const entries = [];
  for (const name of invokedPackageScriptNames(record)) {
    for (const rootDir of packageRootsForScriptInvocation(sourceText, record.start, record.segment, name, defaultRoot)) {
      const entry = packageScripts.get(scriptKey(rootDir, name));
      if (entry) entries.push(entry);
    }
  }
  return entries;
}

function packageScriptBodyProvesRole(entry, stack, role, seen = new Set()) {
  if (!entry || seen.has(entry.key)) return false;
  const nextSeen = new Set(seen).add(entry.key);
  for (const record of executableShellCommands(entry.body)) {
    if (directCommandRunsRole(record, stack, role)) return true;
    if (packageScriptEntriesForInvocation(entry.body, record, entry.root)
      .some((nested) => packageScriptBodyProvesRole(nested, stack, role, nextSeen))) return true;
  }
  return false;
}

function packageInvocationRunsRole(record, stack, role, sourceText, defaultRoot, requiredRoot = '') {
  return packageScriptEntriesForInvocation(sourceText, record, defaultRoot)
    .filter((entry) => !requiredRoot || entry.root === requiredRoot)
    .some((entry) => packageScriptBodyProvesRole(entry, stack, role));
}

function commandRunsRole(record, stack, role, sourceText = record.segment, defaultRoot = '.', requiredRoot = '') {
  if (directCommandRunsRole(record, stack, role)) return true;
  return packageInvocationRunsRole(record, stack, role, sourceText, defaultRoot, requiredRoot);
}

function textRunsRoleForStack(text, stack, role) {
  return executableShellCommands(text).some((record) => commandRunsRole(record, stack, role, text));
}

function textRunsTool(text, expectedTool, expectedArg = '') {
  return executableShellCommands(text).some((record) => {
    const { tool, args } = commandTool(record);
    return tool === expectedTool && (!expectedArg || args.includes(expectedArg));
  });
}

function expandedCommandSections(text) {
  const sections = [{ root: '.', text: '' }];
  const entriesByName = new Map(packageScriptEntries.map((entry) => [displayScriptName(entry), entry]));
  let current = sections[0];
  for (const line of String(text || '').split('\n')) {
    const match = line.match(/^# package script (.+)$/);
    if (match) {
      const entry = entriesByName.get(match[1]);
      current = { root: entry?.root || '.', text: '' };
      sections.push(current);
      continue;
    }
    current.text += `${line}\n`;
  }
  return sections;
}

function loopRoleCommandCoversProject(text, project, role) {
  const loopPattern = /\bfor\s+([A-Za-z_][A-Za-z0-9_]*)\s+in\s+([^;\n]+);\s*do([\s\S]*?)\bdone\b/g;
  for (const match of text.matchAll(loopPattern)) {
    const variable = match[1];
    const roots = match[2];
    const body = match[3].replaceAll('\\"', '"').replaceAll("\\'", "'");
    if (!rootPattern(project.root).test(roots)) continue;
    if (loopBodyRunsCommandAtVariableRoot(body, variable, (record) => commandRunsRole(record, project.stack, role, body))) return true;
  }
  return false;
}

function roleCommandCoversProject(text, project, role) {
  for (const section of expandedCommandSections(text)) {
    if (loopRoleCommandCoversProject(section.text, project, role)) return true;
    for (const record of executableShellCommands(section.text)) {
      const packageRole = packageInvocationRunsRole(record, project.stack, role, section.text, section.root, project.root);
      const repoWorkspaceRole = project.root === '.' && hasUnscopedJsWorkspaceCommand(record.segment) &&
        packageInvocationRunsRole(record, project.stack, role, section.text, section.root);
      const directRole = directCommandRunsRole(record, project.stack, role);
      if (repoWorkspaceRole) return true;
      if (!packageRole && !directRole) continue;
      if (packageRole) return true;
      const localCwd = shellCwdBefore(section.text, record.start);
      const cwd = section.root === '.' || localCwd === unknownShellCwd
        ? localCwd
        : localCwd === '.' ? section.root : resolveShellCwd(section.root, localCwd);
      if (cwd === project.root) return true;
      if (cwd === '.' && rootPattern(project.root).test(record.segment)) return true;
      if (['js-ts', 'react'].includes(project.stack) && hasUnscopedJsWorkspaceCommand(record.segment)) return true;
    }
  }
  if (isHardEng && role === 'test' && executablePathPresent(text, 'scripts/check-hard-eng-full-repo.mjs')) return true;
  if (isHardEng && role === 'lint' && executablePathPresent(text, 'scripts/check-project-quality-gates.mjs')) return true;
  if (project.stack === 'python' && role === 'lint' && rootsFor('python').length === 1 && textRunsRoleForStack(text, project.stack, role)) return true;
  if (project.stack === 'go' && rootHasFile('.', 'go.work') && textRunsRoleForStack(text, project.stack, role)) return true;
  if (project.stack === 'rust' && rootHasFile('.', 'Cargo.toml') && textRunsRoleForStack(text, project.stack, role) && hasShellFlag(executableShellText(text), ['--workspace'])) return true;
  if (project.stack === 'java' && (rootHasFile('.', 'settings.gradle') || rootHasFile('.', 'settings.gradle.kts')) && textRunsRoleForStack(text, project.stack, role)) return true;
  if (project.stack === 'dotnet' && files.some((file) => file.endsWith('.sln')) && textRunsRoleForStack(text, project.stack, role)) return true;
  return false;
}

function validateRoleProjectRootCoverage(label, text, role, projects) {
  for (const project of projects) {
    if (!roleCommandCoversProject(text, project, role)) {
      block(`${label} must cover ${project.stack} project root ${project.root} (${project.markers.join(', ')})`);
    }
  }
}

function validateStackCommands(label, text, options = {}) {
  const executableText = executableShellText(text);
  function includes(pattern) {
    return pattern.test(executableText);
  }
  if (hasStack('js-ts')) {
    if (!includes(/\b(eslint|biome|oxlint|lint)\b/i)) block(`${label} must run JS/TS lint or an equivalent scanner`);
    if ((hasTs || anyRoot('js-ts', (entry) => entry.hasTypeScript)) && !includes(/\b(tsc|vue-tsc|typecheck)\b/i)) block(`${label} must run TypeScript typecheck or tsc`);
    if (!includes(/\bfallow\b/i) || !includes(/\bfallow\b[\s\S]*\b(audit|dupes)\b|\b(audit|dupes)\b[\s\S]*\bfallow\b/i)) {
      block(`${label} must run fallow audit or fallow dupes`);
    }
  }
  if (hasStack('react') && !includes(/\breact-doctor\b/i)) block(`${label} must run react-doctor`);
  if (hasStack('flutter') || hasStack('dart')) {
    if (!includes(/\bdart-decimate\b|\b(dart|flutter)\s+analyze\b/i)) block(`${label} must run dart-decimate, dart analyze, or flutter analyze`);
    if ((hasFlutterTests || anyRoot('flutter', (entry) => entry.testsPresent) || anyRoot('dart', (entry) => entry.testsPresent)) && !includes(/\b(flutter|dart)\s+test\b/i)) block(`${label} must run flutter test or dart test when tests exist`);
  }
  if (hasStack('python')) {
    if (!includes(/\bpyrefly\s+check\b/i)) block(`${label} must run pyrefly check`);
    if (anyRoot('python', (entry) => entry.testsPresent) && !includes(/\b(pytest|python\s+-m\s+pytest|python\s+-m\s+unittest|tox|nox|hatch\s+run\s+test|poetry\s+run\s+pytest|uv\s+run\s+pytest)\b/i)) {
      block(`${label} must run Python tests when tests exist`);
    }
  }
  if (hasStack('go')) {
    if (!includes(/\bgo\s+(?:test|test\s+\.\/\.\.\.)\b/i)) block(`${label} must run go test`);
  }
  if (hasStack('rust')) {
    if (!includes(/\bcargo\s+test\b/i)) block(`${label} must run cargo test`);
    if (!includes(/\bcargo\s+clippy\b/i)) block(`${label} must run cargo clippy`);
  }
  if (hasStack('java')) {
    if (!includes(/\b(mvn|\.\/mvnw)\s+(?:test|verify|install)\b|\b(gradle|\.\/gradlew)\s+(?:test|check|build)\b/i)) block(`${label} must run Maven or Gradle tests/checks`);
  }
  if (hasStack('swift')) {
    if (!includes(/\bswift\s+test\b|\bxcodebuild\b[\s\S]*\btest\b/i)) block(`${label} must run swift test or xcodebuild test`);
  }
  if (hasStack('dotnet')) {
    if (!includes(/\bdotnet\s+test\b/i)) block(`${label} must run dotnet test`);
  }
  if (hasStack('ruby')) {
    if (!includes(/\b(bundle\s+exec\s+)?(rspec|rake\s+test)|\brails\s+test\b|\bruby\s+-Itest\b/i)) block(`${label} must run Ruby tests`);
  }
  if (hasStack('php')) {
    if (!includes(/\b(phpunit|pest|composer\s+(?:run\s+)?test)\b/i)) block(`${label} must run PHP tests`);
  }
  if (hasStack('terraform')) {
    if (!includes(/\bterraform\s+fmt\b[\s\S]*\b-check\b|\bterraform\s+fmt\s+-check\b/i)) block(`${label} must run terraform fmt -check`);
    if (!includes(/\bterraform\s+validate\b|\bterragrunt\b[\s\S]*\bvalidate\b/i)) block(`${label} must run terraform validate`);
  }
  if (isHardEng) {
    if (options.noMistakes && !includes(/\bscripts\/check-hard-eng-full-repo\.mjs\b/)) block(`${label} must run scripts/check-hard-eng-full-repo.mjs`);
    if (!includes(/\bscripts\/check-project-quality-gates\.mjs\b/)) block(`${label} must run scripts/check-project-quality-gates.mjs`);
  }
  validateProjectRootCoverage(label, executableText);
}

function validateNoMistakesCommandRoles() {
  const testText = noMistakes.commandTexts.test;
  const lintText = noMistakes.commandTexts.lint;
  const testableStacks = ['js-ts', 'react', 'flutter', 'dart', 'python', 'go', 'rust', 'java', 'swift', 'dotnet', 'ruby', 'php'];
  const testProjects = projectRoots.filter((entry) => (
    testableStacks.includes(entry.stack)
    && (entry.testsPresent || ['go', 'rust', 'java', 'swift', 'dotnet'].includes(entry.stack))
  ));
  if (isHardEng && !executablePathPresent(testText, 'scripts/check-hard-eng-full-repo.mjs')) block('.no-mistakes.yaml commands.test must run scripts/check-hard-eng-full-repo.mjs');
  if (isHardEng && !executablePathPresent(lintText, 'scripts/check-project-quality-gates.mjs')) block('.no-mistakes.yaml commands.lint must run scripts/check-project-quality-gates.mjs');
  if (hasStack('js-ts')) {
    if (!textRunsRoleForStack(lintText, 'js-ts', 'lint')) block('.no-mistakes.yaml commands.lint must run JS/TS lint or an equivalent scanner');
    if ((hasTs || anyRoot('js-ts', (entry) => entry.hasTypeScript)) && !textRunsTool(lintText, 'tsc') && !textRunsTool(lintText, 'vue-tsc')) block('.no-mistakes.yaml commands.lint must run TypeScript typecheck or tsc');
    if (!textRunsTool(lintText, 'fallow', 'audit') && !textRunsTool(lintText, 'fallow', 'dupes')) block('.no-mistakes.yaml commands.lint must run fallow audit or fallow dupes');
  }
  if (hasStack('react') && !textRunsTool(lintText, 'react-doctor')) block('.no-mistakes.yaml commands.lint must run react-doctor');
  if (hasStack('python') && !textRunsRoleForStack(lintText, 'python', 'lint')) block('.no-mistakes.yaml commands.lint must run pyrefly check for Python projects');
  for (const stack of ['flutter', 'dart', 'go', 'rust', 'java', 'swift', 'dotnet', 'ruby', 'php']) {
    if (hasStack(stack) && !textRunsRoleForStack(lintText, stack, 'lint')) block(`.no-mistakes.yaml commands.lint must run ${stack} lint, analyze, or static checks`);
  }
  if (hasStack('terraform')) {
    const activeLintText = executableShellText(lintText);
    if (!/\bterraform\s+fmt\b[^\n]*\b-check\b/i.test(activeLintText)) block('.no-mistakes.yaml commands.lint must run terraform fmt -check');
    if (!textRunsTool(lintText, 'terraform', 'validate') && !textRunsTool(lintText, 'terragrunt', 'validate')) block('.no-mistakes.yaml commands.lint must run terraform validate');
  }
  for (const stack of [...new Set(testProjects.map((project) => project.stack))]) {
    if (!textRunsRoleForStack(testText, stack, 'test')) block(`.no-mistakes.yaml commands.test must run deterministic ${stack} tests`);
  }
  validateRoleProjectRootCoverage('.no-mistakes.yaml commands.test', testText, 'test', testProjects);
  validateRoleProjectRootCoverage('.no-mistakes.yaml commands.lint', lintText, 'lint', projectRoots);
}

function validateFormatCommandRole(text) {
  if (!text.trim()) return;
  if (isHardEng && !executablePathPresent(text, 'scripts/format-hard-eng.mjs')) block('.no-mistakes.yaml commands.format must run scripts/format-hard-eng.mjs');
  else if (isHardEng && !commandUsesFormatterForStack(text, 'hard-eng')) block('.no-mistakes.yaml commands.format must mutate files with scripts/format-hard-eng.mjs');
  const labels = new Map([
    ['js-ts', 'a deterministic JS/TS formatter'],
    ['flutter', 'dart format or flutter format'],
    ['dart', 'dart format or flutter format'],
    ['python', 'a deterministic Python formatter'],
    ['go', 'gofmt or go fmt'],
    ['rust', 'cargo fmt'],
    ['java', 'a deterministic Java formatter'],
    ['swift', 'swiftformat or swift-format'],
    ['dotnet', 'dotnet format'],
    ['ruby', 'a deterministic Ruby formatter'],
    ['php', 'a deterministic PHP formatter'],
    ['terraform', 'terraform fmt'],
  ]);
  for (const [stack, label] of labels) {
    if (hasStack(stack) && !commandUsesFormatterForStack(text, stack)) block(`.no-mistakes.yaml commands.format must run ${label}`);
  }
  validateFormatProjectRootCoverage('.no-mistakes.yaml commands.format', text);
}

if (requirePushGate && stacks.length) {
  if (!noMistakes.exists) {
    block('repo must define .no-mistakes.yaml with commands.test, commands.lint, and commands.format before no-mistakes runs');
  } else {
    if (!noMistakes.commands.test) block('.no-mistakes.yaml must define commands.test for deterministic baseline tests');
    if (!noMistakes.commands.lint) block('.no-mistakes.yaml must define commands.lint for deterministic lint/static checks');
    if (!noMistakes.commands.format) block('.no-mistakes.yaml must define commands.format for deterministic formatting');
    if (noMistakes.commands.test && noMistakes.commands.lint) {
      validateNoMistakesCommandRoles();
      validateScannerCoverage('.no-mistakes.yaml commands', executableShellText(noMistakes.text));
    }
    if (noMistakes.commands.format) validateFormatCommandRole(noMistakes.commandTexts.format);
  }
}

if (evidence.text.trim()) {
  validateStackCommands('pre-push gate', evidence.text);
}

if (isFlutter && evidence.text.trim()) {
  const analysisOptions = read('analysis_options.yaml');
  if (!/flutter_skill_lints/.test(analysisOptions)) block('Flutter analysis_options.yaml must wire flutter_skill_lints');
}

if (!stacks.length) warnings.push('no supported code stack detected');
if (!evidence.hooks.length && !requirePushGate) warnings.push('no pre-push hook manager detected');

const result = {
  root,
  stacks,
  projectRoots: projectRoots.map((entry) => ({
    stack: entry.stack,
    root: entry.root,
    markers: entry.markers,
    testsPresent: entry.testsPresent,
    hasTypeScript: entry.hasTypeScript,
  })),
  scannerScripts,
  nestedGitRepos,
  submodulePaths: [...submodulePathSet],
  configuredNestedGitRepos,
  unmanagedNestedGitRepos,
  inventoryTruncations: [...inventoryTruncations],
  hooks: evidence.hooks,
  scripts: evidence.scriptNames,
  noMistakes: {
    exists: noMistakes.exists,
    scripts: noMistakes.scripts,
    commands: noMistakes.commands,
  },
  blockers,
  warnings,
};

if (json) {
  console.log(`${JSON.stringify(result, null, 2)}\n`);
} else {
  console.log(`project-quality-gates: ${blockers.length ? 'fail' : 'pass'}`);
  if (stacks.length) console.log(`stacks: ${stacks.join(', ')}`);
  if (evidence.hooks.length) console.log(`hooks: ${evidence.hooks.join(', ')}`);
  if (evidence.scriptNames.length) console.log(`hooked scripts: ${evidence.scriptNames.join(', ')}`);
  if (noMistakes.exists) console.log(`no-mistakes commands: ${Object.keys(noMistakes.commands).join(', ') || 'none'}`);
  for (const warning of warnings) console.log(`warning: ${warning}`);
  for (const blocker of blockers) console.error(`blocker: ${blocker}`);
}

process.exit(blockers.length ? 1 : 0);
