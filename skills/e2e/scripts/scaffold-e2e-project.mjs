#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';

const args = process.argv.slice(2);
const rootIndex = args.indexOf('--root');
const repoRoot = path.resolve(rootIndex === -1 ? process.cwd() : args[rootIndex + 1]);
const skillDir = path.resolve(new URL('..', import.meta.url).pathname);
const templateDir = path.join(skillDir, 'templates');
const docsDir = path.join(repoRoot, 'docs/e2e');

const files = [
  ['project.json', 'project.json'],
  ['auth.md', 'auth.md'],
  ['automation.md', 'automation.md'],
  ['logging.md', 'logging.md'],
  ['regression.md', 'regression.md'],
  ['issues.md', 'issues.md'],
  ['flow.md', 'flows/README.md'],
];

const written = [];
const kept = [];

for (const [templateName, targetRel] of files) {
  const target = path.join(docsDir, targetRel);
  if (fs.existsSync(target)) {
    kept.push(path.relative(repoRoot, target));
    continue;
  }
  fs.mkdirSync(path.dirname(target), { recursive: true });
  fs.copyFileSync(path.join(templateDir, templateName), target);
  written.push(path.relative(repoRoot, target));
}

console.log(JSON.stringify({
  status: written.length ? 'scaffolded' : 'already-present',
  root: repoRoot,
  written,
  kept,
}, null, 2));
