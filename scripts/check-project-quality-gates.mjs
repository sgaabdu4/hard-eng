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

function walk(dir, depth, out) {
  if (depth > 4 || out.length > 1000) return;
  let entries = [];
  try {
    entries = fs.readdirSync(path.join(root, dir), { withFileTypes: true });
  } catch {
    return;
  }
  for (const entry of entries) {
    if (['.git', '.dart_tool', '.next', '.turbo', 'build', 'coverage', 'dist', 'node_modules', 'vendor'].includes(entry.name)) continue;
    const rel = path.join(dir, entry.name);
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
  for (const [name, body] of Object.entries(scripts)) packageScripts.set(name, String(body));
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
const stacks = [];

function block(message) {
  blockers.push(message);
}

if (isReact) stacks.push('react');
if (isJsTs) stacks.push('js-ts');
if (isFlutter) stacks.push('flutter');
if (isHardEng) stacks.push('hard-eng');

if (requirePushGate && stacks.length && !evidence.text.trim()) {
  block(`detected ${stacks.join('/')} but found no pre-push gate evidence`);
}

function validateStackCommands(label, text, options = {}) {
  function includes(pattern) {
    return pattern.test(text);
  }
  if (isJsTs) {
    if (!includes(/\b(eslint|biome|oxlint|lint)\b/i)) block(`${label} must run JS/TS lint or an equivalent scanner`);
    if (hasTs && !includes(/\b(tsc|vue-tsc|typecheck)\b/i)) block(`${label} must run TypeScript typecheck or tsc`);
    if (!includes(/\bfallow\b/i) || !includes(/\bfallow\b[\s\S]*\b(audit|dupes)\b|\b(audit|dupes)\b[\s\S]*\bfallow\b/i)) {
      block(`${label} must run fallow audit or fallow dupes`);
    }
  }
  if (isReact && !includes(/\breact-doctor\b/i)) block(`${label} must run react-doctor`);
  if (isFlutter) {
    if (!includes(/\bdart-decimate\b|\b(dart|flutter)\s+analyze\b/i)) block(`${label} must run dart-decimate, dart analyze, or flutter analyze`);
    if (hasFlutterTests && !includes(/\b(flutter|dart)\s+test\b/i)) block(`${label} must run flutter test or dart test when tests exist`);
  }
  if (isHardEng) {
    if (options.noMistakes && !includes(/\bscripts\/check-hard-eng-full-repo\.mjs\b/)) block(`${label} must run scripts/check-hard-eng-full-repo.mjs`);
    if (!includes(/\bscripts\/check-project-quality-gates\.mjs\b/)) block(`${label} must run scripts/check-project-quality-gates.mjs`);
  }
}

if (requirePushGate && stacks.length) {
  if (!noMistakes.exists) {
    block('repo must define .no-mistakes.yaml with commands.test and commands.lint before no-mistakes runs');
  } else {
    if (!noMistakes.commands.test) block('.no-mistakes.yaml must define commands.test for deterministic baseline tests');
    if (!noMistakes.commands.lint) block('.no-mistakes.yaml must define commands.lint for deterministic lint/static checks');
    if (noMistakes.commands.test && noMistakes.commands.lint) validateStackCommands('.no-mistakes.yaml commands', noMistakes.text, { noMistakes: true });
  }
}

if (evidence.text.trim()) {
  validateStackCommands('pre-push gate', evidence.text);
}

if (isFlutter && evidence.text.trim()) {
  const analysisOptions = read('analysis_options.yaml');
  if (!/flutter_skill_lints/.test(analysisOptions)) block('Flutter analysis_options.yaml must wire flutter_skill_lints');
}

if (!stacks.length) warnings.push('no React/JS/TS/Flutter stack detected');
if (!evidence.hooks.length && !requirePushGate) warnings.push('no pre-push hook manager detected');

const result = {
  root,
  stacks,
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
