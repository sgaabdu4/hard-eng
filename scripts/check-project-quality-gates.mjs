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
const unmanagedNestedGitRepos = nestedGitRepos.filter((entry) => !submodulePathSet.has(entry));

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
for (const file of packageFiles) {
  const scripts = scriptsFor(file);
  for (const [name, body] of Object.entries(scripts)) {
    const existing = packageScripts.get(name);
    packageScripts.set(name, existing ? `${existing}\n${body}` : String(body));
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
  if (!text) return { exists: false, commands, scripts: [], text: '' };
  const lines = text.replace(/\r\n/g, '\n').split('\n');
  const commandsLine = lines.findIndex((line) => /^commands\s*:\s*(?:#.*)?$/.test(line));
  if (commandsLine === -1) return { exists: true, commands, scripts: [], text };
  for (let index = commandsLine + 1; index < lines.length; index += 1) {
    const line = lines[index];
    if (/^\S/.test(line) && line.trim()) break;
    const match = line.match(/^\s{2,}(test|lint)\s*:\s*(.*)$/);
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
  const expanded = expandPackageScriptReferences([commands.test, commands.lint].filter(Boolean).join('\n'));
  return { exists: true, commands, scripts: expanded.scriptNames, text: expanded.text };
}

function expandPackageScriptReferences(initialText) {
  let text = initialText || '';
  const queue = [];
  for (const [name] of packageScripts) {
    const escaped = name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const ref = new RegExp(`\\b(npm|pnpm|yarn|bun)(\\s+run)?\\s+${escaped}\\b|\\b(yarn|bun)\\s+${escaped}\\b`);
    if (ref.test(text)) queue.push(name);
  }
  const seen = new Set();
  while (queue.length) {
    const name = queue.shift();
    if (seen.has(name) || !packageScripts.has(name)) continue;
    seen.add(name);
    const body = packageScripts.get(name);
    text += `\n# package script ${name}\n${body}\n`;
    for (const [other] of packageScripts) {
      if (!seen.has(other) && new RegExp(`\\brun\\s+${other.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\b`).test(body)) queue.push(other);
    }
  }
  return { scriptNames: [...seen], text };
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

function collectHookEvidence() {
  const hooks = hookFiles();
  let text = '';
  for (const file of hooks) {
    const content = read(file);
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

for (const repoPath of unmanagedNestedGitRepos) {
  block(`unmanaged nested Git repo ${repoPath}; convert it to a tracked submodule or move it under an ignored artifact/cache root`);
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
  const escaped = rootDir.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  return new RegExp(`(?:^|[\\s"'=:/])${escaped}(?:$|[\\s"'/;),])`);
}

function rootCoveredByCommand(text, project) {
  if (project.root === '.') return true;
  if (rootPattern(project.root).test(text)) return true;
  if (isHardEng && /\bscripts\/check-hard-eng-full-repo\.mjs\b/.test(text)) return true;
  if (['js-ts', 'react'].includes(project.stack) && /\b(turbo|nx|lerna|moon)\b|\bpnpm\s+(?:-r|--recursive)\b|\byarn\s+workspaces\b|\bnpm\b[\s\S]*\b--workspaces\b|\bbun\b[\s\S]*\b--filter\b/i.test(text)) return true;
  if (project.stack === 'python' && rootsFor('python').length === 1 && /\bpyrefly\s+check\b/.test(text)) return true;
  if (project.stack === 'go' && rootHasFile('.', 'go.work') && /\bgo\s+test\s+\.\/\.\.\./.test(text)) return true;
  if (project.stack === 'rust' && rootHasFile('.', 'Cargo.toml') && /\bcargo\s+(?:test|clippy)\b[\s\S]*\b--workspace\b/.test(text)) return true;
  if (project.stack === 'java' && (rootHasFile('.', 'settings.gradle') || rootHasFile('.', 'settings.gradle.kts')) && /\b(?:gradle|\.\/gradlew)\s+(?:check|test|build)\b/.test(text)) return true;
  if (project.stack === 'dotnet' && files.some((file) => file.endsWith('.sln')) && /\bdotnet\s+test\b/.test(text)) return true;
  if (project.stack === 'terraform' && /\bfind\b[\s\S]*\bterraform\b[\s\S]*\bvalidate\b|\bterragrunt\b[\s\S]*\brun-all\b/i.test(text)) return true;
  return false;
}

function scannerCoveredByCommand(text, scanner) {
  if (new RegExp(`(?:^|[\\s"'])${scanner.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}(?:$|[\\s"'])`).test(text)) return true;
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
  const testText = expandPackageScriptReferences(noMistakes.commands.test || '').text;
  const lintText = expandPackageScriptReferences(noMistakes.commands.lint || '').text;
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

if (requirePushGate && stacks.length) {
  if (!noMistakes.exists) {
    block('repo must define .no-mistakes.yaml with commands.test and commands.lint before no-mistakes runs');
  } else {
    if (!noMistakes.commands.test) block('.no-mistakes.yaml must define commands.test for deterministic baseline tests');
    if (!noMistakes.commands.lint) block('.no-mistakes.yaml must define commands.lint for deterministic lint/static checks');
    if (noMistakes.commands.test && noMistakes.commands.lint) {
      validateStackCommands('.no-mistakes.yaml commands', noMistakes.text, { noMistakes: true });
      validateNoMistakesCommandRoles();
      validateScannerCoverage('.no-mistakes.yaml commands', noMistakes.text);
    }
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
