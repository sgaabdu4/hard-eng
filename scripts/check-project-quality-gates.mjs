#!/usr/bin/env node
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
  return fs.existsSync(path.join(root, file));
}

function read(file) {
  try {
    return fs.readFileSync(path.join(root, file), 'utf8');
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

function walk(dir, depth, out) {
  if (depth > 7 || out.length > 5000) return;
  let entries = [];
  try {
    entries = fs.readdirSync(path.join(root, dir), { withFileTypes: true });
  } catch {
    return;
  }
  for (const entry of entries) {
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

function commandSequencePrefixBefore(text, index) {
  const lineStart = text.lastIndexOf('\n', index);
  const commandStart = text.lastIndexOf(';', index);
  const start = Math.max(lineStart, commandStart) + 1;
  return text.slice(start, index);
}

function packageRootFromInvocationOptions(segment) {
  const normalized = segment.replaceAll('\\', '/');
  const roots = [...new Set(packageScriptEntries.map((entry) => entry.root))]
    .filter((entry) => entry !== '.')
    .sort((a, b) => b.length - a.length);
  for (const rootDir of roots) {
    const escaped = escapeRegExp(rootDir);
    if (new RegExp(`(?:^|\\s)(?:--workspace|--filter|--prefix|-C|-w)(?:=|\\s+)["']?${escaped}["']?(?:\\s|$|[;&)])`).test(normalized)) return rootDir;
    if (new RegExp(`\\bworkspace\\s+["']?${escaped}["']?(?:\\s|$|[;&)])`).test(normalized)) return rootDir;
  }
  for (const [packageName, rootDir] of packageRootNames) {
    const escaped = escapeRegExp(packageName);
    if (new RegExp(`(?:^|\\s)(?:--workspace|--filter|-F)(?:=|\\s+)["']?${escaped}["']?(?:\\s|$|[;&)])`).test(normalized)) return rootDir;
    if (new RegExp(`\\bworkspace\\s+["']?${escaped}["']?(?:\\s|$|[;&)])`).test(normalized)) return rootDir;
  }
  return null;
}

function packageRootFromCdPrefix(prefix) {
  const normalized = prefix.replaceAll('\\', '/');
  const roots = [...new Set(packageScriptEntries.map((entry) => entry.root))]
    .filter((entry) => entry !== '.')
    .sort((a, b) => b.length - a.length);
  let rootDir = null;
  let rootIndex = -1;
  for (const candidate of roots) {
    const escaped = escapeRegExp(candidate);
    const pattern = new RegExp(`\\bcd\\s+["']?${escaped}["']?(?:\\s|$|[;&|)])`, 'g');
    for (const match of normalized.matchAll(pattern)) {
      if ((match.index || 0) > rootIndex) {
        rootIndex = match.index || 0;
        rootDir = candidate;
      }
    }
  }
  return rootDir;
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
  ].some((pattern) => pattern.test(segment));
}

function packageRootsForScriptInvocation(sourceText, index, segment, name, defaultRoot) {
  if (isRecursiveScriptInvocation(segment, name)) {
    return packageScriptEntries.filter((entry) => entry.name === name).map((entry) => entry.root);
  }
  return [packageRootFromInvocationOptions(segment) || packageRootFromCdPrefix(commandSequencePrefixBefore(sourceText, index)) || defaultRoot];
}

function queueScriptReferences(sourceText, queue, defaultRoot) {
  const names = [...new Set(packageScriptEntries.map((entry) => entry.name))];
  for (const name of names) {
    const escaped = escapeRegExp(name);
    const ref = new RegExp(`\\b(?:npm|pnpm|yarn|bun)(?:\\s+(?!&&|\\|\\||;)[^\\s;&|]+){0,10}\\s+(?:run\\s+)?${escaped}\\b|\\b(?:lerna|turbo)\\s+run\\s+${escaped}\\b`, 'g');
    for (const match of sourceText.matchAll(ref)) {
      const segment = commandSegmentAround(sourceText, match.index || 0);
      for (const rootDir of packageRootsForScriptInvocation(sourceText, match.index || 0, segment, name, defaultRoot)) {
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
  if (configured && !path.isAbsolute(configured)) candidates.push(`${configured}/pre-push`);
  return [...new Set(candidates)].filter((file) => exists(file));
}

function isNoMistakesGateWorktree() {
  const topLevel = gitOutput(['rev-parse', '--show-toplevel']);
  const configuredHooks = gitOutput(['config', '--get', 'core.hooksPath']);
  return topLevel.includes('/.no-mistakes/worktrees/')
    && configuredHooks.includes('/.no-mistakes/repos/')
    && configuredHooks.endsWith('/hooks');
}

function hardEngInstallerHookTemplate() {
  if (!isHardEng || !isNoMistakesGateWorktree()) return null;
  const installScript = read('scripts/install.sh');
  const match = installScript.match(/install_hook pre-push <<'EOF'\n([\s\S]*?)\nEOF/);
  if (!match || !/check-project-quality-gates\.mjs/.test(match[1])) return null;
  return {
    file: 'scripts/install.sh:pre-push-template',
    content: match[1],
  };
}

function collectHookEvidence() {
  const hooks = hookFiles();
  let text = '';
  for (const file of hooks) {
    const content = read(file);
    if (/pre-push/.test(file) || /pre-push/.test(content)) text += `\n# ${file}\n${content}\n`;
  }
  const template = hardEngInstallerHookTemplate();
  if (template) {
    hooks.push(template.file);
    text += `\n# ${template.file}\n${template.content}\n`;
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
  if (isHardEng && /\bscripts\/check-hard-eng-full-repo\.mjs\b/.test(text)) return true;
  if (['js-ts', 'react'].includes(project.stack) && /\b(turbo|nx|lerna|moon)\b|\bpnpm\s+(?:-r|--recursive)\b|\byarn\s+workspaces\b|\bnpm\b[\s\S]*\b--workspaces\b|\bbun\b[\s\S]*\b--filter\b/i.test(text)) return true;
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

function validateProjectRootCoverage(label, text) {
  for (const project of projectRoots) {
    if (!rootCoveredByCommand(text, project)) {
      block(`${label} must cover ${project.stack} project root ${project.root} (${project.markers.join(', ')})`);
    }
  }
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

function formatterLocatorPattern(stack) {
  if (['js-ts', 'react'].includes(stack)) return /\b(?:prettier|biome|dprint|deno|eslint|scripts\/format-hard-eng\.mjs)\b/gi;
  if (['flutter', 'dart'].includes(stack)) return /\b(?:dart|flutter)\b/gi;
  if (stack === 'python') return /\b(?:ruff|black|yapf|autopep8)\b/gi;
  if (stack === 'go') return /\b(?:go|gofmt)\b/gi;
  if (stack === 'rust') return /\bcargo\b/gi;
  if (stack === 'java') return /\b(?:spotlessApply|google-java-format|spotless:apply)\b/gi;
  if (stack === 'swift') return /\b(?:swiftformat|swift-format)\b/gi;
  if (stack === 'dotnet') return /\bdotnet\b/gi;
  if (stack === 'ruby') return /\b(?:rubocop|standardrb)\b/gi;
  if (stack === 'php') return /\b(?:php-cs-fixer|pint)\b/gi;
  if (stack === 'terraform') return /\bterraform\b/gi;
  return null;
}

function commandUsesFormatterForStack(command, stack) {
  if (['js-ts', 'react'].includes(stack)) return /\b(prettier|biome|dprint|deno\s+fmt|eslint\b[\s\S]*\b--fix|scripts\/format-hard-eng\.mjs)\b/i.test(command);
  if (['flutter', 'dart'].includes(stack)) return /\bdart\s+format\b|\bflutter\s+format\b/i.test(command);
  if (stack === 'python') return /\b(ruff\s+format|black|yapf|autopep8)\b/i.test(command);
  if (stack === 'go') return /\bgo\s+fmt\s+\.\/\.\.\.(?:$|[\s"';),&|])|\bgofmt\b[\s\S]*\b-w\b/i.test(command);
  if (stack === 'rust') return /\bcargo\s+fmt\b/i.test(command) && hasShellFlag(command, ['--all', '--workspace']);
  if (stack === 'java') return /\b(spotlessApply|google-java-format|spotless:apply)\b/i.test(command);
  if (stack === 'swift') return /\b(swiftformat|swift-format)\b/i.test(command);
  if (stack === 'dotnet') return /\bdotnet\s+format\b/i.test(command);
  if (stack === 'ruby') return /\b(rubocop\b[\s\S]*\b-a|rubocop\b[\s\S]*\b--autocorrect|standardrb\b[\s\S]*\b--fix)\b/i.test(command);
  if (stack === 'php') return /\b(php-cs-fixer|pint)\b/i.test(command);
  if (stack === 'terraform') return /\bterraform\s+fmt\b[\s\S]*\b-recursive\b/i.test(command);
  return false;
}

function commandHasRepoWideFormatterScope(command, stack) {
  if (hasRepoRootArgument(command)) return true;
  if (stack === 'rust') return /\bcargo\s+fmt\b/i.test(command) && hasShellFlag(command, ['--all', '--workspace']);
  return false;
}

function repoWideFormatCoversProject(text, project) {
  if (project.root === '.') return false;
  const rootText = rootScopedPackageScriptText(text);
  const locator = formatterLocatorPattern(project.stack);
  if (!locator) return false;
  for (const match of rootText.matchAll(locator)) {
    const index = match.index || 0;
    const command = commandSegmentAround(rootText, index);
    if (!commandHasRepoWideFormatterScope(command, project.stack)) continue;
    if (packageRootFromCdPrefix(commandSequencePrefixBefore(rootText, index))) continue;
    if (commandUsesFormatterForStack(command, project.stack)) return true;
  }
  return false;
}

function validateFormatProjectRootCoverage(label, text) {
  for (const project of projectRoots) {
    if (!rootCoveredByCommand(text, project) && !repoWideFormatCoversProject(text, project)) {
      block(`${label} must cover ${project.stack} project root ${project.root} (${project.markers.join(', ')})`);
    }
  }
}

function validateStackCommands(label, text, options = {}) {
  function includes(pattern) {
    return pattern.test(text);
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
  validateProjectRootCoverage(label, text);
}

function validateNoMistakesCommandRoles() {
  const testText = noMistakes.commandTexts.test;
  const lintText = noMistakes.commandTexts.lint;
  if (!isHardEng) {
    const testableStacks = ['js-ts', 'react', 'flutter', 'dart', 'python', 'go', 'rust', 'java', 'swift', 'dotnet', 'ruby', 'php'];
    const hasTests = projectRoots.some((entry) => testableStacks.includes(entry.stack) && (entry.testsPresent || ['go', 'rust', 'java', 'swift', 'dotnet'].includes(entry.stack)));
    if (hasTests && !hasAny(testText, [
      /\b(npm|pnpm|yarn|bun)\s+(?:run\s+)?test\b/i,
      /\b(vitest|jest|playwright\s+test|cypress\s+run)\b/i,
      /\b(flutter|dart)\s+test\b/i,
      /\b(pytest|python\s+-m\s+pytest|python\s+-m\s+unittest|tox|nox)\b/i,
      /\bgo\s+test\b/i,
      /\bcargo\s+test\b/i,
      /\b(mvn|\.\/mvnw)\s+(?:test|verify|install)\b|\b(gradle|\.\/gradlew)\s+(?:test|check|build)\b/i,
      /\bswift\s+test\b|\bxcodebuild\b[\s\S]*\btest\b/i,
      /\bdotnet\s+test\b/i,
      /\b(bundle\s+exec\s+)?(rspec|rake\s+test)|\brails\s+test\b|\bruby\s+-Itest\b/i,
      /\b(phpunit|pest|composer\s+(?:run\s+)?test)\b/i,
    ])) {
      block('.no-mistakes.yaml commands.test must run deterministic tests for detected testable projects');
    }
    if (hasStack('python') && !/\bpyrefly\s+check\b/i.test(lintText)) block('.no-mistakes.yaml commands.lint must run pyrefly check for Python projects');
  }
}

function validateFormatCommandRole(text) {
  function includes(pattern) {
    return pattern.test(text);
  }
  if (!text.trim()) return;
  if (isHardEng && !includes(/\bscripts\/format-hard-eng\.mjs\b/)) block('.no-mistakes.yaml commands.format must run scripts/format-hard-eng.mjs');
  if (hasStack('js-ts') && !includes(/\b(prettier|biome|dprint|deno\s+fmt|eslint\b[\s\S]*\b--fix|scripts\/format-hard-eng\.mjs)\b/i)) {
    block('.no-mistakes.yaml commands.format must run a deterministic JS/TS formatter');
  }
  if ((hasStack('flutter') || hasStack('dart')) && !includes(/\bdart\s+format\b|\bflutter\s+format\b/i)) {
    block('.no-mistakes.yaml commands.format must run dart format or flutter format');
  }
  if (hasStack('python') && !includes(/\b(ruff\s+format|black|yapf|autopep8)\b/i)) {
    block('.no-mistakes.yaml commands.format must run a deterministic Python formatter');
  }
  if (hasStack('go') && !includes(/\b(gofmt|go\s+fmt)\b/i)) block('.no-mistakes.yaml commands.format must run gofmt or go fmt');
  if (hasStack('rust') && !includes(/\bcargo\s+fmt\b/i)) block('.no-mistakes.yaml commands.format must run cargo fmt');
  if (hasStack('java') && !includes(/\b(spotlessApply|google-java-format|spotless:apply)\b/i)) {
    block('.no-mistakes.yaml commands.format must run a deterministic Java formatter');
  }
  if (hasStack('swift') && !includes(/\b(swiftformat|swift-format)\b/i)) block('.no-mistakes.yaml commands.format must run a deterministic Swift formatter');
  if (hasStack('dotnet') && !includes(/\bdotnet\s+format\b/i)) block('.no-mistakes.yaml commands.format must run dotnet format');
  if (hasStack('ruby') && !includes(/\b(rubocop\b[\s\S]*\b-a|rubocop\b[\s\S]*\b--autocorrect|standardrb\b[\s\S]*\b--fix)\b/i)) {
    block('.no-mistakes.yaml commands.format must run a deterministic Ruby formatter');
  }
  if (hasStack('php') && !includes(/\b(php-cs-fixer|pint)\b/i)) block('.no-mistakes.yaml commands.format must run a deterministic PHP formatter');
  if (hasStack('terraform') && !includes(/\bterraform\s+fmt\b/i)) block('.no-mistakes.yaml commands.format must run terraform fmt');
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
      validateStackCommands('.no-mistakes.yaml commands', noMistakes.text, { noMistakes: true });
      validateNoMistakesCommandRoles();
      validateScannerCoverage('.no-mistakes.yaml commands', noMistakes.text);
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
