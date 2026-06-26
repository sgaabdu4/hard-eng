#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';

const args = process.argv.slice(2);
const rootIndex = args.indexOf('--root');
const strict = args.includes('--strict');
const repoRoot = path.resolve(rootIndex === -1 ? process.cwd() : args[rootIndex + 1]);
const docsDir = path.join(repoRoot, 'docs/e2e');

const required = [
  'project.json',
  'auth.md',
  'automation.md',
  'logging.md',
  'regression.md',
  'issues.md',
  'flows/README.md',
];

const missing = required.filter((rel) => !fs.existsSync(path.join(docsDir, rel)));
const unknowns = [];
let project = null;

if (!missing.includes('project.json')) {
  try {
    project = JSON.parse(fs.readFileSync(path.join(docsDir, 'project.json'), 'utf8'));
    if (!Array.isArray(project.targets) || !project.targets.some((target) => target.url || target.startCommand)) {
      unknowns.push('target url/startCommand');
    }
    if (!project.auth || project.auth.method === 'unknown') unknowns.push('auth method');
    if (!project.dataMode || project.dataMode.mode === 'unknown') unknowns.push('data mode');
    if (!project.logging || !Array.isArray(project.logging.commands)) unknowns.push('logging commands');
    if (!project.regression || !Array.isArray(project.regression.commands)) unknowns.push('regression commands');
    if (!Array.isArray(project.flows) || !project.flows.length) unknowns.push('flows');
    if (!project.automation || !Array.isArray(project.automation.commands) || !project.automation.commands.length) {
      unknowns.push('automated E2E commands');
    }
    if (Array.isArray(project.flows) && project.flows.some((flow) => !flow.automationCommand)) {
      unknowns.push('flow automation commands');
    }
  } catch (error) {
    missing.push(`project.json parseable (${error.message})`);
  }
}

const status = missing.length ? 'missing' : unknowns.length ? 'needs-input' : 'ready';
const result = {
  status,
  root: repoRoot,
  missing,
  unknowns,
  files: required.map((rel) => path.join('docs/e2e', rel)),
};

console.log(JSON.stringify(result, null, 2));
if (strict && status !== 'ready') process.exit(1);
