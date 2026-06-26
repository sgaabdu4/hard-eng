#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';

const args = process.argv.slice(2);
let root = process.cwd();
let json = false;
let limit = 30;
const queryParts = [];

for (let index = 0; index < args.length; index += 1) {
  const arg = args[index];
  if (arg === '--root') {
    root = path.resolve(args[++index] || '');
  } else if (arg === '--json') {
    json = true;
  } else if (arg === '--limit') {
    limit = Number.parseInt(args[++index] || '30', 10);
  } else if (arg === '--help' || arg === '-h') {
    console.log(`Usage: find-deterministic-owner.mjs [--root path] [--json] [--limit n] [query...]

Lists existing deterministic owners in a repo: package scripts, scripts, tests, hooks,
workflows, and skill scripts. Run matching owners before fresh LLM reasoning.`);
    process.exit(0);
  } else {
    queryParts.push(arg);
  }
}

if (!fs.existsSync(root) || !fs.statSync(root).isDirectory()) {
  console.error(`Root is not a directory: ${root}`);
  process.exit(2);
}

const query = queryParts.join(' ').trim();
const ignoredDirs = new Set(['.git', '.dart_tool', '.next', '.turbo', 'build', 'coverage', 'dist', 'node_modules', 'vendor']);
const executableExts = new Set(['', '.cjs', '.dart', '.js', '.mjs', '.py', '.rb', '.sh', '.ts', '.yaml', '.yml']);
const candidates = [];

function rel(file) {
  return path.relative(root, file).split(path.sep).join('/') || '.';
}

function readJson(file) {
  try {
    return JSON.parse(fs.readFileSync(file, 'utf8'));
  } catch {
    return null;
  }
}

function packageManager(dir) {
  const pkg = readJson(path.join(dir, 'package.json'));
  if (pkg?.packageManager?.startsWith('pnpm@') || fs.existsSync(path.join(root, 'pnpm-lock.yaml'))) return 'pnpm';
  if (pkg?.packageManager?.startsWith('yarn@') || fs.existsSync(path.join(root, 'yarn.lock'))) return 'yarn';
  return 'npm';
}

function add(candidate) {
  candidates.push({
    kind: candidate.kind,
    path: candidate.path,
    command: candidate.command,
    label: candidate.label,
    detail: candidate.detail || '',
  });
}

function walk(dir, depth, maxDepth, visit) {
  if (depth > maxDepth) return;
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    if (ignoredDirs.has(entry.name)) continue;
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      walk(full, depth + 1, maxDepth, visit);
    } else if (entry.isFile()) {
      visit(full);
    }
  }
}

function packageScriptCommand(manager, packageDir, name) {
  const packageRel = rel(packageDir);
  if (manager === 'pnpm') return packageRel === '.' ? `pnpm run ${name}` : `pnpm -C ${packageRel} run ${name}`;
  if (manager === 'yarn') return packageRel === '.' ? `yarn ${name}` : `(cd ${packageRel} && yarn ${name})`;
  return packageRel === '.' ? `npm run ${name}` : `npm --prefix ${packageRel} run ${name}`;
}

function addPackageScripts(packageJson) {
  const pkg = readJson(packageJson);
  if (!pkg?.scripts || typeof pkg.scripts !== 'object') return;
  const dir = path.dirname(packageJson);
  const manager = packageManager(dir);
  for (const [name, script] of Object.entries(pkg.scripts)) {
    add({
      kind: 'package-script',
      path: rel(packageJson),
      command: packageScriptCommand(manager, dir, name),
      label: name,
      detail: String(script),
    });
  }
}

function commandFor(file) {
  const relative = rel(file);
  const ext = path.extname(file);
  if (ext === '.mjs' || ext === '.js' || ext === '.cjs') return `node ${relative}`;
  if (ext === '.py') return `python3 ${relative}`;
  if (ext === '.ts') return `npx tsx ${relative}`;
  if (ext === '.sh' || ext === '.rb' || ext === '.dart' || ext === '') return relative;
  return relative;
}

function kindFor(relative) {
  if (relative.startsWith('.github/workflows/')) return 'workflow';
  if (/^(tests?|e2e|playwright|cypress)\//.test(relative) || /\/(tests?|e2e)\//.test(relative)) return 'test';
  if (/^(\.githooks|\.husky|hooks)\//.test(relative) || /\/hooks\//.test(relative)) return 'hook';
  if (/^skills\/[^/]+\/scripts\//.test(relative)) return 'skill-script';
  return 'script';
}

function isOwnerPath(relative) {
  return (
    /^(\.github\/workflows|scripts|tools?|bin|hooks|\.githooks|\.husky|tests?|e2e|playwright|cypress)\//.test(relative) ||
    /^skills\/[^/]+\/scripts\//.test(relative)
  );
}

function addFileOwner(file) {
  const relative = rel(file);
  if (!isOwnerPath(relative)) return;
  if (!executableExts.has(path.extname(file))) return;
  add({
    kind: kindFor(relative),
    path: relative,
    command: commandFor(file),
    label: path.basename(file),
  });
}

function addTaskTargets(file, runner) {
  const text = fs.readFileSync(file, 'utf8');
  for (const line of text.split('\n')) {
    const match = line.match(/^([A-Za-z0-9_.-]+):(?:\s|$)/);
    if (!match || match[1].startsWith('.')) continue;
    add({
      kind: 'task',
      path: rel(file),
      command: `${runner} ${match[1]}`,
      label: match[1],
    });
  }
}

walk(root, 0, 4, (file) => {
  if (path.basename(file) === 'package.json') addPackageScripts(file);
  addFileOwner(file);
});

for (const name of ['Makefile', 'makefile']) {
  const file = path.join(root, name);
  if (fs.existsSync(file)) addTaskTargets(file, 'make');
}
for (const name of ['justfile', 'Justfile']) {
  const file = path.join(root, name);
  if (fs.existsSync(file)) addTaskTargets(file, 'just');
}

const stopWords = new Set(['a', 'an', 'and', 'for', 'in', 'of', 'or', 'the', 'to', 'with']);
const terms = query
  .toLowerCase()
  .split(/[^a-z0-9_.-]+/)
  .filter((term) => term.length > 1 && !stopWords.has(term));

function score(candidate) {
  if (terms.length === 0) return 0;
  const text = `${candidate.kind} ${candidate.path} ${candidate.command} ${candidate.label} ${candidate.detail}`.toLowerCase();
  return terms.reduce((sum, term) => sum + (text.includes(term) ? 1 : 0), 0);
}

const ranked = candidates
  .map((candidate) => ({ ...candidate, score: score(candidate) }))
  .filter((candidate) => terms.length === 0 || candidate.score > 0)
  .sort((a, b) => b.score - a.score || a.path.localeCompare(b.path) || a.command.localeCompare(b.command))
  .slice(0, Number.isFinite(limit) && limit > 0 ? limit : 30);

if (json) {
  console.log(`${JSON.stringify({ root, query, count: ranked.length, candidates: ranked }, null, 2)}\n`);
} else {
  console.log(`deterministic owners: ${root}`);
  if (query) console.log(`query: ${query}`);
  if (ranked.length === 0) {
    console.log('no matching deterministic owners found');
  } else {
    for (const candidate of ranked) {
      const scoreText = query ? ` score=${candidate.score}` : '';
      console.log(`${candidate.kind}${scoreText}\t${candidate.command}\t${candidate.path}`);
    }
  }
}
