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
const excludedPathPattern = /^(?:vendor|node_modules|tests)\//;
const repoOwnedScriptRootPattern = /^(?:scripts\/|hooks\/|integrations\/[^/]+\/scripts\/|skills\/[^/]+\/scripts\/)/;

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
  if (excludedPathPattern.test(normalized)) return false;
  const ext = path.extname(normalized).toLowerCase();
  if (scriptExts.has(ext)) return true;
  return ext === '' && repoOwnedScriptRootPattern.test(normalized);
}

const cliMutationPattern = /\b(?:appwrite|aw)\b[^\n]*\b(?:create|update|delete|patch|deploy|grant|revoke|purge|restore|execute)\w*\b/i;
const appwriteSdkObjectMutationPattern = /\b(?:account|avatars|bucket|buckets|client|database|databases|executions|functions|graphql|messaging|rows|storage|tables|teams|users)\s*\.\s*(?:create|update|delete|patch)\s*\(/i;
const appwriteSdkMethodMutationPattern = /\.(?:create|update|delete|patch)(?:Document|Row|User|File|Bucket|Execution|Function|Deployment|Index|Attribute|Collection|Table)\s*\(/i;
const ghApiMutationPattern = /\bgh\s+api\b[^\n]*(?:-X|--method)(?:=|\s+)?(?:POST|PATCH|PUT|DELETE)\b/i;
const curlMutationPattern = /\bcurl\b[\s\S]{0,240}(?:-X|--request)(?:=|\s+)?(?:POST|PATCH|PUT|DELETE)\b/i;
const fetchMutationPattern = /\bfetch\s*\([\s\S]{0,500}\bmethod\s*:\s*['"`](?:POST|PATCH|PUT|DELETE)['"`]/i;
const graphqlMutationPattern = /\b(?:graphql|gql|client|request|fetch)\b[\s\S]{0,500}\bmutation\b[\s\S]{0,200}(?:\{|[A-Za-z_][\w]*\s*\()/i;
const subprocessAppwriteMutationPattern = /\b(?:spawn|spawnSync|execFile|execFileSync|execa|execaSync)\s*\(\s*['"`](?:appwrite|aw)['"`]\s*,\s*\[[\s\S]{0,800}['"`](?:create|update|delete|patch|deploy|grant|revoke|purge|restore|execute)\w*['"`]/i;
const subprocessGhApiMutationPattern = /\b(?:spawn|spawnSync|execFile|execFileSync|execa|execaSync)\s*\(\s*['"`]gh['"`]\s*,\s*\[[\s\S]{0,800}['"`]api['"`][\s\S]{0,800}(?:['"`](?:-X|--method)['"`]\s*,\s*['"`](?:POST|PATCH|PUT|DELETE)['"`]|['"`](?:-X|--method)=(?:POST|PATCH|PUT|DELETE)['"`])/i;
const subprocessCurlMutationPattern = /\b(?:spawn|spawnSync|execFile|execFileSync|execa|execaSync)\s*\(\s*['"`]curl['"`]\s*,\s*\[[\s\S]{0,800}(?:['"`](?:-X|--request)['"`]\s*,\s*['"`](?:POST|PATCH|PUT|DELETE)['"`]|['"`](?:-X|--request)=(?:POST|PATCH|PUT|DELETE)['"`])/i;
const writeControlTokenPattern = '(?:WRITE_ENABLED|APPLY_CHANGES|CONFIRM_WRITE|DRY_RUN|writeEnabled|applyChanges|confirmWrite|dryRun|write_enabled|apply_changes|confirm_write|dry_run)';
const shellGuardConditionPattern = `(?:\\[\\[[^\\]\\n]*\\b${writeControlTokenPattern}\\b[^\\]\\n]*\\]\\]|\\[[^\\]\\n]*\\b${writeControlTokenPattern}\\b[^\\]\\n]*\\])`;
const jsGuardConditionPattern = `\\([^\\)\\n]*\\b${writeControlTokenPattern}\\b[^\\)\\n]*\\)`;
const guardedWritePatterns = [
  new RegExp(`\\bif\\s+${shellGuardConditionPattern}\\s*;?\\s*then[\\s\\S]{0,360}\\b(?:exit|return)\\b`, 'i'),
  new RegExp(`\\bif\\s*${jsGuardConditionPattern}\\s*\\{?[\\s\\S]{0,360}\\b(?:return|throw|process\\s*\\.\\s*exit\\s*\\()`, 'i'),
  new RegExp(`${shellGuardConditionPattern}\\s*(?:\\|\\||&&)\\s*(?:exit|return)\\b`, 'i'),
  new RegExp(`\\b${writeControlTokenPattern}\\b[^\\n]{0,140}(?:\\|\\||&&)\\s*(?:return|throw|process\\s*\\.\\s*exit\\s*\\()`, 'i'),
];
const mutationPatterns = [
  cliMutationPattern,
  appwriteSdkObjectMutationPattern,
  appwriteSdkMethodMutationPattern,
  ghApiMutationPattern,
  curlMutationPattern,
  fetchMutationPattern,
  graphqlMutationPattern,
  subprocessAppwriteMutationPattern,
  subprocessGhApiMutationPattern,
  subprocessCurlMutationPattern,
];

const requirementChecks = [
  ['dry-run default', /(?:\b(?:dryRun|dry_run|DRY_RUN|dry run|no-write|read-only)\b|--dry-run\b)/i],
  ['explicit write flag', /(?:\b(?:WRITE_ENABLED|APPLY_CHANGES|CONFIRM_WRITE)\b|--(?:write|apply|execute|confirm|yes)\b)/i],
  ['scoped allowlist or reviewed input', /(?:\b(?:allowlist|allow-list|allowList|scope|scoped|reviewedInput|approvedInput|scopedInput|reviewed input|approved input)\b|--(?:company|tenant|ids|input|file)\b)/i],
  ['approval-boundary evidence', /\b(?:approvalBoundaries|approval boundaries|approved side effect|human approval|approval receipt)\b/i],
  ['post-write verification', /\b(?:post-write|post write|verify|verification|audit|cleanupProof|cleanup proof|read-back|readback)\b/i],
];

function executableLine(line) {
  const trimmed = line.trim();
  if (!trimmed || trimmed.startsWith('#') || trimmed.startsWith('//') || trimmed.startsWith('*')) return false;
  if (/^(?:const|let|var)\s+[A-Za-z_$][\w$]*(?:Pattern|Patterns|PatternSource|Regex)[A-Za-z_$\d]*\s*=\s*(?:\/|'|")/.test(trimmed)) return false;
  if (/^(?:const|let|var)\s+[A-Za-z_$][\w$]*\s*=\s*\/(?!\/)/.test(trimmed) && /\\b|\\s|\.\*/.test(trimmed)) return false;
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

function globalPattern(pattern) {
  return new RegExp(pattern.source, pattern.flags.includes('g') ? pattern.flags : `${pattern.flags}g`);
}

function mutationFindings(executable) {
  return mutationPatterns
    .flatMap((pattern) => [...executable.matchAll(globalPattern(pattern))].map((match) => ({ index: match.index || 0 })))
    .sort((left, right) => left.index - right.index);
}

function hasGuardedWriteBefore(executable, mutationIndex) {
  const preceding = executable.slice(Math.max(0, mutationIndex - 4000), mutationIndex);
  return guardedWritePatterns.some((pattern) => pattern.test(preceding));
}

const failures = [];
for (const file of gitFiles().filter(candidate)) {
  const text = readFile(file);
  const executable = executableText(text);
  const mutations = mutationFindings(executable);
  if (!mutations.length) continue;
  const missing = requirementChecks
    .filter(([, pattern]) => !pattern.test(executable))
    .map(([label]) => label);
  if (mutations.some((mutation) => !hasGuardedWriteBefore(executable, mutation.index))) {
    missing.push('guarded write execution');
  }
  if (missing.length) failures.push({ file, missing });
}

if (failures.length) {
  console.error(`hard-eng write safety: ${failures.length} issue(s)`);
  for (const failure of failures) {
    console.error(`- ${failure.file}: risky mutation script missing ${failure.missing.join(', ')}`);
  }
  console.error('Risky backend/prod/customer mutation scripts must be dry-run by default, require an explicit write flag, use scoped allowlist/input, record approvalBoundaries, verify after writes, and guard mutation commands behind the write control.');
  process.exit(1);
}

console.log('hard-eng write safety: pass');
