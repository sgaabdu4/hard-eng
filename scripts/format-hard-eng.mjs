#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';

const args = process.argv.slice(2);
let root = process.cwd();
let check = false;

for (const arg of args) {
  if (arg === '--check') check = true;
  else if (arg === '--help' || arg === '-h') {
    console.log(`Usage: format-hard-eng.mjs [--check] [repo]

Normalizes repo-owned text files with deterministic whitespace rules:
- LF line endings
- no trailing spaces or tabs
- final newline for non-empty files`);
    process.exit(0);
  } else {
    root = path.resolve(arg);
  }
}

root = path.resolve(root);

const ignoredDirectoryNames = new Set([
  '.cache',
  '.codebase',
  '.codebase-memory',
  '.git',
  '.no-mistakes',
  'backups',
  'coverage',
  'dist',
  'logs',
  'node_modules',
  'outputs',
  'target',
  'tmp',
  'vendor',
]);

const ignoredBasenames = new Set([
  'CHANGELOG.md',
]);

const formattedExtensions = new Set([
  '.cjs',
  '.css',
  '.cts',
  '.html',
  '.js',
  '.jsx',
  '.json',
  '.md',
  '.mjs',
  '.mts',
  '.sh',
  '.ts',
  '.tsx',
  '.toml',
  '.txt',
  '.xml',
  '.yaml',
  '.yml',
]);

const formattedBasenames = new Set([
  '.gitignore',
  '.gitmodules',
  'AGENTS.md',
  'COPILOT.md',
  'DESIGN.md',
  'LICENSE',
  'PRODUCT.md',
  'README.md',
  'VERSION',
]);

function shouldFormat(file) {
  const base = path.basename(file);
  if (ignoredBasenames.has(base)) return false;
  if (formattedBasenames.has(base)) return true;
  return formattedExtensions.has(path.extname(file));
}

function shouldSkipPath(file) {
  const parts = file.split('/');
  if (parts.some((part) => ignoredDirectoryNames.has(part))) return true;
  if (parts.some((part) => part === 'generated')) return true;
  return /(?:^|\/)evals\/results(?:\/|$)/.test(file);
}

function normalize(text) {
  let next = text.replace(/\r\n?/g, '\n');
  next = next
    .split('\n')
    .map((line) => line.replace(/[ \t]+$/g, ''))
    .join('\n');
  if (next.length > 0 && !next.endsWith('\n')) next += '\n';
  return next;
}

function walk(dir = '', out = []) {
  let entries = [];
  try {
    entries = fs.readdirSync(path.join(root, dir), { withFileTypes: true });
  } catch {
    return out;
  }
  for (const entry of entries) {
    const rel = path.join(dir, entry.name).split(path.sep).join('/');
    if (shouldSkipPath(rel)) continue;
    if (entry.isDirectory()) {
      walk(rel, out);
      continue;
    }
    if (!entry.isFile()) continue;
    if (shouldFormat(rel)) out.push(rel);
  }
  return out;
}

function gitFiles() {
  const result = spawnSync('git', ['-C', root, 'ls-files', '-z', '--cached', '--others', '--exclude-standard'], {
    encoding: 'buffer',
  });
  if (result.status !== 0) return null;
  return result.stdout
    .toString('utf8')
    .split('\0')
    .filter(Boolean)
    .map((file) => file.split(path.sep).join('/'));
}

function filesToFormat() {
  const files = gitFiles();
  if (!files) return walk();
  return files.filter((file) => !shouldSkipPath(file) && shouldFormat(file));
}

const changed = [];
const generatedMarker = ['AUTO', 'GENERATED'].join('-');
const generatedMarkerPattern = new RegExp(`^${generatedMarker}\\b`);

function hasGeneratedMarker(text) {
  return text
    .split(/\r\n|\n|\r/)
    .slice(0, 5)
    .some((line) => generatedMarkerPattern.test(
      line.trim().replace(/^(?:<!--|\/\/|#|\/\*+|\*|;)\s*/, ''),
    ));
}

for (const file of filesToFormat()) {
  const fullPath = path.join(root, file);
  const stat = fs.lstatSync(fullPath, { throwIfNoEntry: false });
  if (!stat?.isFile()) continue;
  const original = fs.readFileSync(fullPath);
  if (original.includes(0)) continue;
  const text = original.toString('utf8');
  if (!Buffer.from(text, 'utf8').equals(original)) continue;
  if (hasGeneratedMarker(text)) continue;
  const next = normalize(text);
  if (next === text) continue;
  changed.push(file);
  if (!check) fs.writeFileSync(fullPath, next);
}

if (changed.length) {
  if (check) {
    console.error('format-hard-eng: files need formatting');
    for (const file of changed) console.error(file);
    process.exit(1);
  }
  console.log(`format-hard-eng: formatted ${changed.length} file${changed.length === 1 ? '' : 's'}`);
} else {
  console.log('format-hard-eng: pass');
}
