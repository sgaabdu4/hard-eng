#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';

const args = process.argv.slice(2);
let root = process.cwd();
let scanStaged = false;
let scanHead = false;
let scanRev = '';
let sawRev = false;
for (let index = 0; index < args.length; index += 1) {
  const arg = args[index];
  if (arg === '--staged') scanStaged = true;
  else if (arg === '--head') scanHead = true;
  else if (arg === '--rev') {
    sawRev = true;
    scanRev = args[index + 1] || '';
    index += 1;
  } else if (arg.startsWith('--rev=')) {
    sawRev = true;
    scanRev = arg.slice('--rev='.length);
  } else if (!arg.startsWith('--')) {
    root = arg;
  }
}
root = path.resolve(root);
if ([scanStaged, scanHead, Boolean(scanRev)].filter(Boolean).length > 1) {
  console.error('Usage: check-hard-eng-write-safety.mjs [--staged|--head|--rev <rev>] [repo]');
  process.exit(2);
}
if (sawRev && !scanRev) {
  console.error('Usage: check-hard-eng-write-safety.mjs --rev <rev> [repo]');
  process.exit(2);
}
const scanTreeish = scanRev || (scanHead ? 'HEAD' : '');
const scriptExts = new Set(['.sh', '.py', '.mjs', '.cjs', '.js', '.ts']);

function git(argsList) {
  return spawnSync('git', ['-C', root, ...argsList], {
    encoding: 'buffer',
    maxBuffer: 1024 * 1024 * 32,
  });
}

function gitFiles() {
  const result = scanTreeish ? git(['ls-tree', '-r', '-z', '--name-only', scanTreeish]) : git(['ls-files', '-z']);
  if (result.status !== 0) return [];
  return result.stdout.toString('utf8').split('\0').filter(Boolean);
}

function readFile(file) {
  if (scanStaged || scanTreeish) {
    const spec = scanStaged ? `:${file}` : `${scanTreeish}:${file}`;
    const result = git(['show', spec]);
    if (result.status === 0) return result.stdout.toString('utf8');
  }
  return fs.readFileSync(path.join(root, file), 'utf8');
}

function candidate(file) {
  const normalized = file.replaceAll('\\', '/');
  if (/^(?:vendor|node_modules|tests)\//.test(normalized)) return false;
  if (!/^(?:scripts\/|skills\/[^/]+\/scripts\/)/.test(normalized)) return false;
  return scriptExts.has(path.extname(normalized).toLowerCase());
}

const cliMutationPattern = /\b(?:appwrite|aw)\b[^\n]*(?:create|update|delete|patch|deploy|grant|revoke|purge|restore|execute)\b/i;
const appwriteSdkObjectMutationPattern = /\b(?:account|avatars|bucket|buckets|client|database|databases|executions|functions|graphql|messaging|rows|storage|tables|teams|users)\s*\.\s*(?:create|update|delete|patch)\s*\(/i;
const appwriteSdkMethodMutationPattern = /\.(?:create|update|delete|patch)(?:Document|Row|User|File|Bucket|Execution|Function|Deployment|Index|Attribute|Collection|Table)\s*\(/i;
const ghApiMutationPattern = /\bgh\s+api\b[^\n]*(?:-X|--method)(?:=|\s+)?(?:POST|PATCH|PUT|DELETE)\b/i;
const curlMutationPattern = /\bcurl\b[\s\S]{0,240}(?:-X|--request)(?:=|\s+)?(?:POST|PATCH|PUT|DELETE)\b/i;
const fetchMutationPattern = /\bfetch\s*\([\s\S]{0,500}\bmethod\s*:\s*['"`](?:POST|PATCH|PUT|DELETE)['"`]/i;
const graphqlMutationPattern = /\b(?:graphql|gql|client|request|fetch)\b[\s\S]{0,500}\bmutation\b[\s\S]{0,200}(?:\{|[A-Za-z_][\w]*\s*\()/i;

const requirementChecks = [
  ['dry-run default', /\b(?:--dry-run|dryRun|dry_run|DRY_RUN|dry run|no-write|read-only)\b/i],
  ['explicit write flag', /\b(?:--write|--apply|--execute|--confirm|--yes|WRITE_ENABLED|APPLY_CHANGES|CONFIRM_WRITE)\b/i],
  ['scoped allowlist or reviewed input', /\b(?:allowlist|allow-list|scope|scoped|--company|--tenant|--ids|--input|--file|reviewed input|approved input)\b/i],
  ['approval-boundary evidence', /\b(?:approvalBoundaries|approval boundaries|approved side effect|human approval|approval receipt)\b/i],
  ['post-write verification', /\b(?:post-write|post write|verify|verification|audit|cleanupProof|cleanup proof|read-back|readback)\b/i],
];

function executableLine(line) {
  const trimmed = line.trim();
  if (!trimmed || trimmed.startsWith('#') || trimmed.startsWith('//') || trimmed.startsWith('*')) return false;
  if (/^(?:\/|[A-Za-z_$][\w$]*\s*[:=]\s*\/|['"][^'"]*\/)/.test(trimmed) && /\\b|\\s|\.\*/.test(trimmed)) return false;
  return true;
}

function stripInlineComment(line) {
  const hashIndex = line.search(/\s#/);
  const slashIndex = line.search(/\s\/\//);
  const indexes = [hashIndex, slashIndex].filter((index) => index >= 0);
  if (indexes.length === 0) return line;
  return line.slice(0, Math.min(...indexes));
}

function executableText(text) {
  const lines = [];
  let inBlockComment = false;
  for (const line of text.split(/\r?\n/)) {
    let current = line;
    if (inBlockComment) {
      const end = current.indexOf('*/');
      if (end === -1) continue;
      current = current.slice(end + 2);
      inBlockComment = false;
    }
    while (current.includes('/*')) {
      const start = current.indexOf('/*');
      const end = current.indexOf('*/', start + 2);
      if (end === -1) {
        current = current.slice(0, start);
        inBlockComment = true;
        break;
      }
      current = `${current.slice(0, start)} ${current.slice(end + 2)}`;
    }
    current = stripInlineComment(current);
    if (executableLine(current)) lines.push(current);
  }
  return lines.join('\n').replace(/\\\r?\n\s*/g, ' ');
}

function risky(executable) {
  return [
    cliMutationPattern,
    appwriteSdkObjectMutationPattern,
    appwriteSdkMethodMutationPattern,
    ghApiMutationPattern,
    curlMutationPattern,
    fetchMutationPattern,
    graphqlMutationPattern,
  ].some((pattern) => pattern.test(executable));
}

const failures = [];
for (const file of gitFiles().filter(candidate)) {
  const text = readFile(file);
  const executable = executableText(text);
  if (!risky(executable)) continue;
  const missing = requirementChecks
    .filter(([, pattern]) => !pattern.test(executable))
    .map(([label]) => label);
  if (missing.length) failures.push({ file, missing });
}

if (failures.length) {
  console.error(`hard-eng write safety: ${failures.length} issue(s)`);
  for (const failure of failures) {
    console.error(`- ${failure.file}: risky mutation script missing ${failure.missing.join(', ')}`);
  }
  console.error('Risky backend/prod/customer mutation scripts must be dry-run by default, require an explicit write flag, use scoped allowlist/input, record approvalBoundaries, and verify after writes.');
  process.exit(1);
}

console.log('hard-eng write safety: pass');
