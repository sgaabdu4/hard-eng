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
const legacyStagePrefix = `${String.fromCharCode(97, 97)}:`;
const legacyRepoPattern = `${String.fromCharCode(97, 98, 105, 100)}[-_ ]agents`;
const legacyCommandLabel = `legacy /${legacyStagePrefix.slice(0, -1)} command`;
const denied = [
  { name: legacyCommandLabel, pattern: new RegExp(`(^|[^A-Za-z0-9_])/?${legacyStagePrefix}[a-z][a-z-]*`, 'i') },
  { name: 'legacy repo name', pattern: new RegExp(`\\b${legacyRepoPattern}\\b`, 'i') },
];
const errors = [];

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
