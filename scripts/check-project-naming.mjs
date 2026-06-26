#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';

const root = path.resolve(process.argv[2] || process.env.HARD_ENG_NAMING_ROOT || process.cwd());
const ignoredDirs = new Set(['.git', 'backups', 'node_modules', 'vendor']);
const ignoredFiles = new Set([
  'CHANGELOG.md',
  'scripts/check-project-naming.mjs',
  'tests/project-naming.test.mjs',
]);
const binaryExtensions = new Set([
  '.avif',
  '.gif',
  '.icns',
  '.ico',
  '.jpeg',
  '.jpg',
  '.pdf',
  '.png',
  '.webp',
]);
const oldStagePrefix = `${String.fromCharCode(97, 97)}:`;
const oldRepoPattern = `${String.fromCharCode(97, 98, 105, 100)}[-_ ]agents`;
const oldCommandLabel = `old /${oldStagePrefix.slice(0, -1)} command`;
const denylistFiles = [
  'private-denylist.example.txt',
  'private-denylist.txt',
];
const denied = [
  { name: oldCommandLabel, pattern: new RegExp(`(^|[^A-Za-z0-9_])/?${oldStagePrefix}[a-z][a-z-]*`, 'i') },
  { name: 'old repo name', pattern: new RegExp(`\\b${oldRepoPattern}\\b`, 'i') },
];
const errors = [];

for (const file of denylistFiles) {
  const absolutePath = path.join(root, file);
  if (!fs.existsSync(absolutePath)) continue;
  const lines = fs.readFileSync(absolutePath, 'utf8').split(/\r?\n/);
  for (const [index, raw] of lines.entries()) {
    const pattern = raw.trim();
    if (!pattern || pattern.startsWith('#')) continue;
    try {
      denied.push({ name: `${file}:${index + 1}`, pattern: new RegExp(pattern, 'i') });
    } catch (error) {
      errors.push(`${file}:${index + 1}: invalid private denylist regex: ${error.message}`);
    }
  }
}

function relative(file) {
  return path.relative(root, file).split(path.sep).join('/');
}

function isProbablyText(buffer) {
  return !buffer.includes(0);
}

function walk(dir, files = []) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    if (ignoredDirs.has(entry.name)) continue;
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      walk(fullPath, files);
      continue;
    }
    if (!entry.isFile()) continue;
    const rel = relative(fullPath);
    if (ignoredFiles.has(rel)) continue;
    if (binaryExtensions.has(path.extname(entry.name).toLowerCase())) continue;
    files.push(fullPath);
  }
  return files;
}

for (const absolutePath of walk(root)) {
  const buffer = fs.readFileSync(absolutePath);
  if (!isProbablyText(buffer)) continue;
  const file = relative(absolutePath);
  const lines = buffer.toString('utf8').split(/\r?\n/);
  for (const [index, line] of lines.entries()) {
    for (const rule of denied) {
      if (rule.pattern.test(line)) {
        errors.push(`${file}:${index + 1}: ${rule.name}`);
      }
    }
  }
}

if (errors.length > 0) {
  console.error(`project-naming: ${errors.length} failure(s)`);
  for (const error of errors) console.error(`- ${error}`);
  process.exit(1);
}

console.log('project-naming: pass');
