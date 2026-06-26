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
It inspects tracked hook managers and hook-referenced package scripts.`);
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

function hookFiles() {
  const candidates = [
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
  return { hooks, scriptNames: [...seen], text };
}

const evidence = collectHookEvidence();
const blockers = [];
const warnings = [];
const stacks = [];

function has(pattern) {
  return pattern.test(evidence.text);
}

function block(message) {
  blockers.push(message);
}

if (isReact) stacks.push('react');
if (isJsTs) stacks.push('js-ts');
if (isFlutter) stacks.push('flutter');

if (requirePushGate && stacks.length && !evidence.text.trim()) {
  block(`detected ${stacks.join('/')} but found no pre-push gate evidence`);
}

if (isJsTs && evidence.text.trim()) {
  if (!has(/\b(eslint|biome|oxlint|lint)\b/i)) block('JS/TS gate must run lint or an equivalent scanner');
  if (hasTs && !has(/\b(tsc|vue-tsc|typecheck)\b/i)) block('TypeScript gate must run typecheck or tsc');
  if (!has(/\bfallow\b/i) || !has(/\bfallow\b[\s\S]*\b(audit|dupes)\b|\b(audit|dupes)\b[\s\S]*\bfallow\b/i)) {
    block('JS/TS gate must run fallow audit or fallow dupes');
  }
}

if (isReact && evidence.text.trim() && !has(/\breact-doctor\b/i)) {
  block('React/Next gate must run react-doctor');
}

if (isFlutter && evidence.text.trim()) {
  if (!has(/\bdart\s+analyze\b/i)) block('Flutter gate must run package-root dart analyze');
  if (hasFlutterTests && !has(/\b(flutter|dart)\s+test\b/i)) block('Flutter gate must run flutter test or dart test when tests exist');
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
  for (const warning of warnings) console.log(`warning: ${warning}`);
  for (const blocker of blockers) console.error(`blocker: ${blocker}`);
}

process.exit(blockers.length ? 1 : 0);
