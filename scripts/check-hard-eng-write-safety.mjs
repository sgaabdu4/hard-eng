#!/usr/bin/env node
// HARD_ENG_SCANNER_OWNER: write-safety scanner with focused behavior coverage.
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
const excludedPathPattern = /(?:^|\/)(?:vendor|node_modules|tests)\//;
const repoOwnedScriptRootPattern = /(?:^|\/)scripts\/|^(?:hooks\/|codex\/bin\/|tools\/)/;

function git(argsList) {
  return spawnSync('git', ['-C', root, ...argsList], {
    encoding: 'buffer',
    maxBuffer: 1024 * 1024 * 32,
  });
}

function gitFailureDetail(result) {
  if (result.error?.code === 'ENOBUFS') return 'git output exceeded scanner buffer';
  return result.stderr.toString('utf8').trim() || result.error?.message || `git exited with status ${result.status ?? 'unknown'}`;
}

function gitFileEntries() {
  const result = scanTreeish ? git(['ls-tree', '-r', '-z', scanTreeish]) : git(['ls-files', '-s', '-z']);
  if (result.status !== 0) return [];
  return result.stdout.toString('utf8').split('\0').filter(Boolean).flatMap((entry) => {
    if (scanTreeish) {
      const separator = entry.indexOf('\t');
      if (separator === -1) return [];
      const [mode, type] = entry.slice(0, separator).split(/\s+/);
      return [{ mode, type, file: entry.slice(separator + 1) }];
    }
    const match = entry.match(/^(\d+)\s+\S+\s+\d+\t(.+)$/);
    if (!match) return [];
    return [{ mode: match[1], type: 'blob', file: match[2] }];
  });
}

function readFile(file) {
  if (scanStaged || scanTreeish) {
    const spec = scanStaged ? `:${file}` : `${scanTreeish}:${file}`;
    const result = git(['show', spec]);
    if (result.status !== 0) return { ok: false, detail: gitFailureDetail(result) };
    return { ok: true, text: result.stdout.toString('utf8') };
  }
  return { ok: true, text: fs.readFileSync(path.join(root, file), 'utf8') };
}

function regularBlob(entry) {
  return entry.type === 'blob' && ['100644', '100755'].includes(entry.mode);
}

function executableMode(entry) {
  return entry.mode === '100755';
}

function hasShebang(text) {
  return /^#!/.test(text);
}

function candidatePath(entry) {
  const file = entry.file || '';
  const normalized = file.replaceAll('\\', '/');
  if (excludedPathPattern.test(normalized)) return false;
  const ext = path.extname(normalized).toLowerCase();
  if (repoOwnedScriptRootPattern.test(normalized)) return scriptExts.has(ext) || ext === '';
  return executableMode(entry) && (scriptExts.has(ext) || ext === '');
}

function candidate(entry, text) {
  if (!regularBlob(entry) || !candidatePath(entry)) return false;
  const normalized = entry.file.replaceAll('\\', '/');
  const ext = path.extname(normalized).toLowerCase();
  if (repoOwnedScriptRootPattern.test(normalized)) return scriptExts.has(ext) || ext === '' || hasShebang(text);
  return executableMode(entry) || hasShebang(text);
}

const appwriteMutationVerbPatternSource = '(?:create|update|delete|patch|deploy|grant|revoke|purge|restore|execute|upsert)';
const appwriteSdkMutationVerbPatternSource = '(?:create|update|delete|patch|upsert|increment|decrement)';
const appwriteServicePattern = /^(?:account|avatars|buckets?|databases?|documents?|rows?|storage|tables?|teams?|users?|executions?|functions?|graphql|messaging)$/i;
const appwriteGlobalOptionsWithValues = new Set(['--endpoint', '--project-id', '--project', '--key', '--jwt', '--locale', '--profile', '--config']);
const cliMutationPattern = new RegExp(`\\b(?:appwrite|aw)\\b[^\\n]*\\b${appwriteMutationVerbPatternSource}\\w*\\b`, 'i');
const appwriteSdkObjectMutationPattern = new RegExp(`\\b(?:account|avatars|buckets?|client|database|databases|executions|functions|graphql|messaging|rows|storage|tables|tablesDB|tablesDb|teams|users)(?:[A-Z_$][\\w$]*)?\\s*\\.\\s*${appwriteSdkMutationVerbPatternSource}(?:[A-Z]\\w*)?\\s*\\(`, 'i');
const appwriteSdkMethodMutationPattern = new RegExp(`\\.${appwriteSdkMutationVerbPatternSource}(?:Documents?|Rows?|Users?|Files?|Buckets?|Executions?|Functions?|Deployments?|Indexes?|Attributes?|Collections?|Tables?|Memberships?|Sessions?|Teams?|Topics?|Subscribers?|Emails?|Sms|SMS|Push|Messages?|Targets?|Identities?|Tokens?|JWT|Recovery|Verification|Phone|Prefs)\\s*\\(`, 'i');
const ghApiMutatingMethodPatternSource = '(?:-X|--method)(?:=|\\s+)?(?:POST|PATCH|PUT|DELETE)\\b';
const ghApiReadOnlyMethodPatternSource = '(?:-X|--method)(?:=|\\s+)?(?:GET|HEAD|OPTIONS)\\b';
const ghApiDefaultPostOptionPatternSource = "(?:^|[\\s,])(?:-f(?:\\b|[^\\s'\"`,\\]]*)|-F(?:\\b|[^\\s'\"`,\\]]*)|--(?:raw-field|field|input)(?:=|\\b))";
const ghApiMutationPattern = new RegExp(`\\bgh\\s+api\\b(?:(?=[\\s\\S]{0,240}${ghApiMutatingMethodPatternSource})|(?=[\\s\\S]{0,240}${ghApiDefaultPostOptionPatternSource})(?![\\s\\S]{0,240}${ghApiReadOnlyMethodPatternSource}))`, 'i');
const curlBodyOptionPatternSource = "(?:^|[\\s,])(?:-d(?:\\b|[^\\s'\"`,\\]]*)|-F(?:\\b|[^\\s'\"`,\\]]*)|--(?:data(?:-raw|-binary|-urlencode)?|json|form(?:-string)?)(?:=|\\b))";
const curlGetOptionPatternSource = "(?:^|[\\s,])(?:-G\\b|--get(?:=|\\b))";
const curlBodyArgOptionPatternSource = "['\"`](?:-d(?:\\b|[^'\"`,\\]]*)|-F(?:\\b|[^'\"`,\\]]*)|--(?:data(?:-raw|-binary|-urlencode)?|json|form(?:-string)?)(?:=|\\b)[^'\"`,\\]]*)['\"`]";
const curlGetArgOptionPatternSource = "['\"`](?:-G|--get(?:=.*)?)['\"`]";
const curlMutationPattern = /\bcurl\b[\s\S]{0,240}(?:-X|--request)(?:=|\s+)?(?:POST|PATCH|PUT|DELETE)\b/i;
const curlBodyMutationPattern = new RegExp(`\\bcurl\\b(?=[\\s\\S]{0,240}${curlBodyOptionPatternSource})(?![\\s\\S]{0,240}${curlGetOptionPatternSource})`);
const fetchMutationPattern = /\bfetch\s*\([\s\S]{0,500}\bmethod\s*:\s*['"`](?:POST|PATCH|PUT|DELETE)['"`]/i;
const graphqlMutationPattern = /\b(?:graphql|gql|client|request|fetch)\b[\s\S]{0,500}\bmutation\b[\s\S]{0,200}(?:\{|[A-Za-z_][\w]*\s*\()/i;
const subprocessAppwriteMutationPattern = new RegExp(`\\b(?:spawn|spawnSync|execFile|execFileSync|execa|execaSync)\\s*\\(\\s*['"\`](?:appwrite|aw)['"\`]\\s*,\\s*\\[[\\s\\S]{0,800}['"\`]${appwriteMutationVerbPatternSource}\\w*['"\`]`, 'i');
const subprocessGhApiMutationPattern = /\b(?:spawn|spawnSync|execFile|execFileSync|execa|execaSync)\s*\(\s*['"`]gh['"`]\s*,\s*\[[\s\S]{0,800}['"`]api['"`][\s\S]{0,800}(?:['"`](?:-X|--method)['"`]\s*,\s*['"`](?:POST|PATCH|PUT|DELETE)['"`]|['"`](?:-X|--method)=(?:POST|PATCH|PUT|DELETE)['"`])/i;
const subprocessCurlMutationPattern = /\b(?:spawn|spawnSync|execFile|execFileSync|execa|execaSync)\s*\(\s*['"`]curl['"`]\s*,\s*\[[\s\S]{0,800}(?:['"`](?:-X|--request)['"`]\s*,\s*['"`](?:POST|PATCH|PUT|DELETE)['"`]|['"`](?:-X|--request)=(?:POST|PATCH|PUT|DELETE)['"`])/i;
const subprocessCurlBodyMutationPattern = new RegExp(`\\b(?:spawn|spawnSync|execFile|execFileSync|execa|execaSync)\\s*\\(\\s*['"\`]curl['"\`]\\s*,\\s*\\[(?=[\\s\\S]{0,800}${curlBodyArgOptionPatternSource})(?![\\s\\S]{0,800}${curlGetArgOptionPatternSource})[\\s\\S]{0,800}\\]`);
const writeEnabledTokenNames = ['WRITE_ENABLED', 'APPLY_CHANGES', 'CONFIRM_WRITE', 'writeEnabled', 'applyChanges', 'confirmWrite', 'write_enabled', 'apply_changes', 'confirm_write'];
const dryRunTokenNames = ['DRY_RUN', 'dryRun', 'dry_run'];
const writeEnabledTokenPattern = `(?:${writeEnabledTokenNames.join('|')})`;
const dryRunTokenPattern = `(?:${dryRunTokenNames.join('|')})`;
const writeEnabledAllowedValuePattern = String.raw`(?:(?:"|')?(?:1|true|yes|write|apply|execute|confirm)(?:"|'|\b))`;
const writeEnabledDisabledValuePattern = String.raw`(?:(?:"|')?(?:0|false|no)(?:"|'|\b))`;
const dryRunEnabledValuePattern = String.raw`(?:(?:"|')?(?:1|true|yes)(?:"|'|\b))`;
const dryRunDisabledValuePattern = String.raw`(?:(?:"|')?(?:0|false|no)(?:"|'|\b))`;
const shellEqualsPattern = '(?<!!)==?';
const disabledExitPattern = String.raw`\b(?:exit|return|throw|process\s*\.\s*exit\s*\()`;
const shellWriteDisabledConditionPattern = `(?:\\[\\[[^\\]\\n]*\\b${writeEnabledTokenPattern}\\b[^\\]\\n]*(?:!=\\s*${writeEnabledAllowedValuePattern}|${shellEqualsPattern}\\s*${writeEnabledDisabledValuePattern}|-z\\s+['"]?\\$?\\{?\\b${writeEnabledTokenPattern}\\b\\}?['"]?)[^\\]\\n]*\\]\\]|\\[[^\\]\\n]*\\b${writeEnabledTokenPattern}\\b[^\\]\\n]*(?:!=\\s*${writeEnabledAllowedValuePattern}|${shellEqualsPattern}\\s*${writeEnabledDisabledValuePattern}|-z\\s+['"]?\\$?\\{?\\b${writeEnabledTokenPattern}\\b\\}?['"]?)[^\\]\\n]*\\])`;
const shellWriteEnabledConditionPattern = `(?:\\[\\[[^\\]\\n]*\\b${writeEnabledTokenPattern}\\b[^\\]\\n]*(?:${shellEqualsPattern}\\s*${writeEnabledAllowedValuePattern})[^\\]\\n]*\\]\\]|\\[[^\\]\\n]*\\b${writeEnabledTokenPattern}\\b[^\\]\\n]*(?:${shellEqualsPattern}\\s*${writeEnabledAllowedValuePattern})[^\\]\\n]*\\])`;
const shellDryRunEnabledConditionPattern = `(?:\\[\\[[^\\]\\n]*\\b${dryRunTokenPattern}\\b[^\\]\\n]*(?:${shellEqualsPattern}\\s*${dryRunEnabledValuePattern}|!=\\s*${dryRunDisabledValuePattern})[^\\]\\n]*\\]\\]|\\[[^\\]\\n]*\\b${dryRunTokenPattern}\\b[^\\]\\n]*(?:${shellEqualsPattern}\\s*${dryRunEnabledValuePattern}|!=\\s*${dryRunDisabledValuePattern})[^\\]\\n]*\\])`;
const shellDryRunDisabledConditionPattern = `(?:\\[\\[[^\\]\\n]*\\b${dryRunTokenPattern}\\b[^\\]\\n]*(?:${shellEqualsPattern}\\s*${dryRunDisabledValuePattern})[^\\]\\n]*\\]\\]|\\[[^\\]\\n]*\\b${dryRunTokenPattern}\\b[^\\]\\n]*(?:${shellEqualsPattern}\\s*${dryRunDisabledValuePattern})[^\\]\\n]*\\])`;
const jsWriteDisabledConditionPattern = `\\([^\\)\\n]*(?:!\\s*\\b${writeEnabledTokenPattern}\\b|\\b${writeEnabledTokenPattern}\\b\\s*(?:!==|!=)\\s*${writeEnabledAllowedValuePattern}|\\b${writeEnabledTokenPattern}\\b\\s*===?\\s*(?:false|0))[^\\)\\n]*\\)`;
const jsWriteEnabledConditionPattern = `\\([^\\)\\n]*\\b${writeEnabledTokenPattern}\\b\\s*===?\\s*${writeEnabledAllowedValuePattern}[^\\)\\n]*\\)`;
const jsDryRunEnabledConditionPattern = `(?:\\(\\s*\\b${dryRunTokenPattern}\\b\\s*\\)|\\([^\\)\\n]*\\b${dryRunTokenPattern}\\b\\s*===?\\s*${dryRunEnabledValuePattern}[^\\)\\n]*\\)|\\([^\\)\\n]*\\b${dryRunTokenPattern}\\b\\s*!==?\\s*${dryRunDisabledValuePattern}[^\\)\\n]*\\))`;
const jsDryRunDisabledConditionPattern = `\\([^\\)\\n]*\\b${dryRunTokenPattern}\\b\\s*===?\\s*${dryRunDisabledValuePattern}[^\\)\\n]*\\)`;
const failClosedGuardPatterns = [
  { kind: 'write-control', pattern: new RegExp(`\\bif\\s+${shellWriteDisabledConditionPattern}\\s*;?\\s*then(?:(?!\\b(?:else|fi)\\b)[\\s\\S]){0,360}${disabledExitPattern}`, 'i') },
  { kind: 'write-control', pattern: new RegExp(`${shellWriteEnabledConditionPattern}\\s*\\|\\|\\s*(?:exit|return)\\b`, 'i') },
  { kind: 'write-control', pattern: new RegExp(`${shellWriteDisabledConditionPattern}\\s*&&\\s*(?:exit|return)\\b`, 'i') },
  { kind: 'dry-run', pattern: new RegExp(`\\bif\\s+${shellDryRunEnabledConditionPattern}\\s*;?\\s*then(?:(?!\\b(?:else|fi)\\b)[\\s\\S]){0,360}${disabledExitPattern}`, 'i') },
  { kind: 'dry-run', pattern: new RegExp(`${shellDryRunDisabledConditionPattern}\\s*\\|\\|\\s*(?:exit|return)\\b`, 'i') },
  { kind: 'dry-run', pattern: new RegExp(`${shellDryRunEnabledConditionPattern}\\s*&&\\s*(?:exit|return)\\b`, 'i') },
  { kind: 'write-control', pattern: new RegExp(`\\bif\\s*${jsWriteDisabledConditionPattern}\\s*\\{?[\\s\\S]{0,360}${disabledExitPattern}`, 'i') },
  { kind: 'write-control', pattern: new RegExp(`\\b${writeEnabledTokenPattern}\\b\\s*\\|\\|\\s*(?:return|throw|process\\s*\\.\\s*exit\\s*\\()`, 'i') },
  { kind: 'write-control', pattern: new RegExp(`!\\s*\\b${writeEnabledTokenPattern}\\b\\s*&&\\s*(?:return|throw|process\\s*\\.\\s*exit\\s*\\()`, 'i') },
  { kind: 'dry-run', pattern: new RegExp(`\\bif\\s*${jsDryRunEnabledConditionPattern}\\s*\\{?[\\s\\S]{0,360}${disabledExitPattern}`, 'i') },
  { kind: 'dry-run', pattern: new RegExp(`\\bif\\s*${jsDryRunDisabledConditionPattern}\\s*\\{?[\\s\\S]{0,360}\\b(?:[^}]{0,240}\\b)?(?:else\\s*\\{?[\\s\\S]{0,240}${disabledExitPattern})`, 'i') },
  { kind: 'dry-run', pattern: new RegExp(`\\b${dryRunTokenPattern}\\b\\s*&&\\s*(?:return|throw|process\\s*\\.\\s*exit\\s*\\()`, 'i') },
];
const mutationPatterns = [
  cliMutationPattern,
  appwriteSdkObjectMutationPattern,
  appwriteSdkMethodMutationPattern,
  ghApiMutationPattern,
  curlMutationPattern,
  curlBodyMutationPattern,
  fetchMutationPattern,
  graphqlMutationPattern,
  subprocessAppwriteMutationPattern,
  subprocessGhApiMutationPattern,
  subprocessCurlMutationPattern,
  subprocessCurlBodyMutationPattern,
];

const explicitWriteFlagPattern = /(?:process\s*\.\s*argv[\s\S]{0,160}\b(?:includes|indexOf|some|find)\s*\([\s\S]{0,80}['"`]--(?:write|apply|execute|confirm|yes)['"`]|\b(?:argv|args)\b\s*\.\s*(?:includes|indexOf|some|find)\s*\([\s\S]{0,80}['"`]--(?:write|apply|execute|confirm|yes)['"`]|(?:\$(?:\{?1\b|@|arg\b|args\b|argv\b)|\b(?:arg|args|argv)\b)[^\n]{0,120}(?:==|=|=~|\bin\b|\bincludes\b|\))[^\n]{0,80}['"`]?--(?:write|apply|execute|confirm|yes)\b)/i;
const explicitWriteEnvPattern = new RegExp(String.raw`(?:process\s*\.\s*env\s*\.\s*${writeEnabledTokenPattern}|\$\{\s*${writeEnabledTokenPattern}\s*:-|\b(?:env|os\.environ)\b[\s\S]{0,120}\b${writeEnabledTokenPattern}\b)`, 'i');
const requirementChecks = [
  ['explicit write flag', hasExplicitWriteControl],
];
const mutationRequirementChecks = [
  ['scoped allowlist or reviewed input', hasScopedMutationInput],
  ['approval-boundary evidence', hasMutationApprovalBoundary],
  ['post-write verification', hasPostWriteVerification],
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

function escapeRegExp(value) {
  return String(value).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function findMatching(text, openIndex, openChar, closeChar) {
  let depth = 0;
  let quote = '';
  let escaped = false;
  for (let index = openIndex; index < text.length; index += 1) {
    const char = text[index];
    if (quote) {
      if (escaped) {
        escaped = false;
      } else if (char === '\\') {
        escaped = true;
      } else if (char === quote) {
        quote = '';
      }
      continue;
    }
    if (char === '"' || char === "'" || char === '`') {
      quote = char;
    } else if (char === openChar) {
      depth += 1;
    } else if (char === closeChar) {
      depth -= 1;
      if (depth === 0) return index;
    }
  }
  return -1;
}

function splitTopLevelArgs(text) {
  const args = [];
  let start = 0;
  let quote = '';
  let escaped = false;
  const stack = [];
  const push = (end) => {
    const value = text.slice(start, end).trim();
    if (value) args.push(value);
    start = end + 1;
  };
  for (let index = 0; index < text.length; index += 1) {
    const char = text[index];
    if (quote) {
      if (escaped) {
        escaped = false;
      } else if (char === '\\') {
        escaped = true;
      } else if (char === quote) {
        quote = '';
      }
      continue;
    }
    if (char === '"' || char === "'" || char === '`') {
      quote = char;
    } else if ('({['.includes(char)) {
      stack.push(char);
    } else if (')}]'.includes(char)) {
      stack.pop();
    } else if (char === ',' && stack.length === 0) {
      push(index);
    }
  }
  push(text.length);
  return args;
}

function skipHorizontalWhitespaceAndBlockComments(text, index) {
  let cursor = index;
  for (;;) {
    while (cursor < text.length && /[ \t\r]/.test(text[cursor])) cursor += 1;
    if (!text.startsWith('/*', cursor)) return cursor;
    const closeIndex = text.indexOf('*/', cursor + 2);
    if (closeIndex === -1) return text.length;
    cursor = closeIndex + 2;
  }
}

function nextExpressionToken(text, index) {
  let cursor = index;
  let crossedNewline = false;
  for (;;) {
    while (cursor < text.length && /[ \t\r]/.test(text[cursor])) cursor += 1;
    if (text[cursor] === '\n') {
      crossedNewline = true;
      cursor += 1;
      continue;
    }
    if (text.startsWith('//', cursor)) {
      const newline = text.indexOf('\n', cursor + 2);
      if (newline === -1) return { cursor: text.length, crossedNewline: true };
      crossedNewline = true;
      cursor = newline + 1;
      continue;
    }
    if (text.startsWith('/*', cursor)) {
      const closeIndex = text.indexOf('*/', cursor + 2);
      if (closeIndex === -1) return { cursor: text.length, crossedNewline };
      crossedNewline = crossedNewline || text.slice(cursor, closeIndex).includes('\n');
      cursor = closeIndex + 2;
      continue;
    }
    return { cursor, crossedNewline };
  }
}

function expressionContinuesAfterNewline(text, index) {
  const { cursor } = nextExpressionToken(text, index + 1);
  return cursor < text.length && /[.()[+\-*/%|&?:,]/.test(text[cursor]);
}

function expressionEnd(executable, start) {
  let quote = '';
  let escaped = false;
  const stack = [];
  for (let index = start; index < executable.length; index += 1) {
    const char = executable[index];
    if (quote) {
      if (escaped) {
        escaped = false;
      } else if (char === '\\') {
        escaped = true;
      } else if (char === quote) {
        quote = '';
      }
      continue;
    }
    if (char === '"' || char === "'" || char === '`') {
      quote = char;
    } else if (executable.startsWith('//', index) && stack.length === 0) {
      return index;
    } else if (executable.startsWith('/*', index)) {
      const closeIndex = executable.indexOf('*/', index + 2);
      if (closeIndex === -1) return index;
      index = closeIndex + 1;
    } else if ('({['.includes(char)) {
      stack.push(char);
    } else if (')}]'.includes(char)) {
      stack.pop();
    } else if (stack.length === 0 && char === ';') {
      return index;
    } else if (stack.length === 0 && char === '\n' && !expressionContinuesAfterNewline(executable, index)) {
      return index;
    }
  }
  return executable.length;
}

function arrayLiteralHasTrailingExpression(executable, literalEnd) {
  const { cursor, crossedNewline } = nextExpressionToken(executable, literalEnd + 1);
  if (cursor >= executable.length || executable[cursor] === ';') return false;
  if (crossedNewline) return /[.()[+\-*/%|&?:,]/.test(executable[cursor]);
  return true;
}

function expressionAt(executable, valueStart) {
  const first = executable.slice(valueStart).match(/\S/);
  if (!first) return { value: '', end: valueStart };
  const start = valueStart + (first.index || 0);
  if (executable[start] === '{') {
    const end = findMatching(executable, start, '{', '}');
    return end === -1 ? { value: '', end: start } : { value: executable.slice(start, end + 1), end: end + 1 };
  }
  if (executable[start] === '[') {
    const end = findMatching(executable, start, '[', ']');
    if (end === -1) return { value: '', end: start };
    if (arrayLiteralHasTrailingExpression(executable, end)) {
      const valueEnd = expressionEnd(executable, start);
      return { value: executable.slice(start, valueEnd).trim(), end: valueEnd };
    }
    return { value: executable.slice(start, end + 1), end: end + 1 };
  }
  const parenIndex = executable.indexOf('(', start);
  const lineEnd = executable.slice(start).search(/[;\n]/);
  if (parenIndex >= 0 && (lineEnd === -1 || parenIndex < start + lineEnd)) {
    const end = findMatching(executable, parenIndex, '(', ')');
    if (end >= 0) return { value: executable.slice(start, end + 1).trim(), end: end + 1 };
  }
  const end = executable.slice(start).search(/[;\n]/);
  const absoluteEnd = end === -1 ? executable.length : start + end;
  return { value: executable.slice(start, absoluteEnd).trim(), end: absoluteEnd };
}

function assignmentInfoBefore(executable, name, targetIndex) {
  const pattern = new RegExp(String.raw`(?:^|[;\n])\s*(?:(?:const|let|var)\s+)?${escapeRegExp(name)}\b\s*=(?!=)\s*`, 'g');
  let last = null;
  for (const match of executable.matchAll(pattern)) {
    if ((match.index || 0) >= targetIndex) break;
    last = match;
  }
  if (!last) return '';
  const valueStart = (last.index || 0) + last[0].length;
  return { ...expressionAt(executable, valueStart), index: last.index || 0 };
}

function assignedValueBefore(executable, name, targetIndex) {
  return assignmentInfoBefore(executable, name, targetIndex)?.value || '';
}

function stringLiteralValue(value) {
  const trimmed = String(value || '').trim();
  const quote = trimmed[0];
  if (!['"', "'", '`'].includes(quote) || trimmed.at(-1) !== quote) return null;
  const body = trimmed.slice(1, -1);
  if (quote === '`' && /\$\{/.test(body)) return null;
  return body;
}

function resolvedExpression(executable, expression, targetIndex, seen = new Set()) {
  const trimmed = String(expression || '').trim();
  if (trimmed.startsWith('...')) return { kind: 'unknown', spread: true };
  const literal = stringLiteralValue(trimmed);
  if (literal !== null) return { kind: 'string', value: literal };
  if (trimmed.startsWith('[')) return resolvedArgvArray(executable, trimmed, targetIndex, seen);
  const identifier = trimmed.match(/^[A-Za-z_$][\w$]*$/)?.[0];
  if (identifier && !seen.has(identifier)) {
    seen.add(identifier);
    const assigned = assignedValueBefore(executable, identifier, targetIndex);
    if (assigned) return resolvedExpression(executable, assigned, targetIndex, seen);
  }
  return { kind: 'unknown' };
}

function protectedCommandLiteral(value) {
  const literal = stringLiteralValue(value);
  return literal !== null && /^(?:appwrite|aw|gh|curl)$/i.test(literal) ? literal : '';
}

function commandFallbackString(executable, expression, targetIndex, seen = new Set()) {
  const trimmed = String(expression || '').trim();
  if (!trimmed) return '';
  const literal = protectedCommandLiteral(trimmed);
  if (literal) return literal;
  const identifier = trimmed.match(/^[A-Za-z_$][\w$]*$/)?.[0];
  if (identifier && !seen.has(identifier)) {
    seen.add(identifier);
    const assigned = assignedValueBefore(executable, identifier, targetIndex);
    if (assigned) return commandFallbackString(executable, assigned, targetIndex, seen);
  }
  const fallback = trimmed.match(/(?:\|\||\?\?)\s*(['"`][^'"`]+['"`])\s*$/);
  return fallback ? protectedCommandLiteral(fallback[1]) : '';
}

function resolvedArgvArray(executable, expression, targetIndex, seen = new Set()) {
  const trimmed = String(expression || '').trim();
  if (!trimmed.startsWith('[')) return { kind: 'unknown' };
  const end = findMatching(trimmed, 0, '[', ']');
  if (end === -1) return { kind: 'unknown' };
  const values = splitTopLevelArgs(trimmed.slice(1, end)).map((item) => resolvedExpression(executable, item, targetIndex, new Set(seen)));
  const trailing = strippedArrayTrailing(trimmed.slice(end + 1));
  if (!trailing) return { kind: 'array', values };
  const concatenated = appendedArrayConcatValues(executable, values, trailing, targetIndex, new Set(seen));
  if (concatenated) return { kind: 'array', values: concatenated };
  if (/^(?:as|satisfies)\b/.test(trailing)) return { kind: 'array', values };
  return { kind: 'unknown' };
}

function resolvedArgvTuple(executable, expression, targetIndex, seen = new Set()) {
  const trimmed = String(expression || '').trim();
  if (!trimmed.startsWith('(')) return { kind: 'unknown' };
  const end = findMatching(trimmed, 0, '(', ')');
  if (end === -1) return { kind: 'unknown' };
  if (strippedArrayTrailing(trimmed.slice(end + 1))) return { kind: 'unknown' };
  return { kind: 'array', values: splitTopLevelArgs(trimmed.slice(1, end)).map((item) => resolvedExpression(executable, item, targetIndex, new Set(seen))) };
}

function strippedArrayTrailing(value) {
  let cursor = 0;
  const text = String(value || '');
  for (;;) {
    cursor = skipHorizontalWhitespaceAndBlockComments(text, cursor);
    if (!text.startsWith('//', cursor)) break;
    const newline = text.indexOf('\n', cursor + 2);
    if (newline === -1) return '';
    cursor = newline + 1;
  }
  return text.slice(cursor).trim();
}

function appendedArrayConcatValues(executable, current, trailing, targetIndex, seen = new Set()) {
  let rest = trailing;
  let values = current;
  for (;;) {
    const match = rest.match(/^\.concat\s*\(/);
    if (!match) break;
    const openIndex = rest.indexOf('(');
    const closeIndex = findMatching(rest, openIndex, '(', ')');
    if (closeIndex === -1) return null;
    const args = splitTopLevelArgs(rest.slice(openIndex + 1, closeIndex));
    const appended = [];
    for (const arg of args) {
      const arrayValues = valuesFromArrayExpression(executable, arg, targetIndex, new Set(seen));
      if (arrayValues) appended.push(...arrayValues);
      else appended.push(resolvedExpression(executable, arg, targetIndex, new Set(seen)));
    }
    values = [...values, ...appended];
    rest = strippedArrayTrailing(rest.slice(closeIndex + 1));
  }
  if (!rest || /^(?:as|satisfies)\b/.test(rest)) return values;
  return null;
}

function arrayValuesFromItems(executable, items, targetIndex, seen = new Set()) {
  return splitTopLevelArgs(items).map((item) => resolvedExpression(executable, item, targetIndex, new Set(seen)));
}

function valuesFromArrayExpression(executable, expression, targetIndex, seen = new Set()) {
  const array = resolvedArgvArray(executable, expression, targetIndex, seen);
  return array.kind === 'array' ? array.values : null;
}

function argvBuilderEvents(executable, name, targetIndex) {
  const events = [];
  const assignmentPattern = new RegExp(String.raw`(?:^|[;\n])\s*(?:(?:const|let|var)\s+)?${escapeRegExp(name)}\b\s*=(?!=)\s*`, 'g');
  for (const match of executable.matchAll(assignmentPattern)) {
    const index = match.index || 0;
    if (index >= targetIndex) break;
    const expression = expressionAt(executable, index + match[0].length);
    events.push({ type: 'assign', index, value: expression.value });
  }

  const pushPattern = new RegExp(String.raw`(?:^|[;\n])\s*${escapeRegExp(name)}\s*\.\s*push\s*\(`, 'g');
  for (const match of executable.matchAll(pushPattern)) {
    const index = match.index || 0;
    if (index >= targetIndex) break;
    const openIndex = executable.indexOf('(', index);
    const closeIndex = findMatching(executable, openIndex, '(', ')');
    if (closeIndex === -1 || closeIndex >= targetIndex) continue;
    events.push({ type: 'push', index, value: executable.slice(openIndex + 1, closeIndex) });
  }

  return events.sort((left, right) => left.index - right.index);
}

function appendConcatValues(executable, current, name, value, targetIndex, seen = new Set()) {
  const pattern = new RegExp(String.raw`^${escapeRegExp(name)}\s*\.\s*concat\s*\(`);
  const match = value.trim().match(pattern);
  if (!match || current === null) return null;
  const openIndex = value.indexOf('(');
  const closeIndex = findMatching(value, openIndex, '(', ')');
  if (closeIndex === -1) return null;
  const args = splitTopLevelArgs(value.slice(openIndex + 1, closeIndex));
  const appended = [];
  for (const arg of args) {
    const arrayValues = valuesFromArrayExpression(executable, arg, targetIndex, new Set(seen));
    if (arrayValues) appended.push(...arrayValues);
    else appended.push(resolvedExpression(executable, arg, targetIndex, new Set(seen)));
  }
  return [...current, ...appended];
}

function resolvedIdentifierArgvArray(executable, name, targetIndex, seen = new Set()) {
  let current = null;
  for (const event of argvBuilderEvents(executable, name, targetIndex)) {
    if (event.type === 'assign') {
      const direct = valuesFromArrayExpression(executable, event.value, event.index, new Set(seen));
      if (direct) {
        current = direct;
        continue;
      }
      const concatenated = appendConcatValues(executable, current, name, event.value, event.index, new Set(seen));
      current = concatenated || null;
    } else if (event.type === 'push') {
      if (current === null) return { kind: 'unknown' };
      current = [...current, ...arrayValuesFromItems(executable, event.value, event.index, new Set(seen))];
    }
  }
  return current === null ? { kind: 'unknown' } : { kind: 'array', values: current };
}

function resolvedArgvExpression(executable, expression, targetIndex) {
  const trimmed = String(expression || '').trim();
  if (trimmed.startsWith('[')) return resolvedArgvArray(executable, trimmed, targetIndex);
  const identifier = trimmed.match(/^[A-Za-z_$][\w$]*$/)?.[0];
  if (identifier) return resolvedIdentifierArgvArray(executable, identifier, targetIndex);
  return { kind: 'unknown' };
}

function resolvedPythonArgvExpression(executable, expression, targetIndex, seen = new Set()) {
  const trimmed = String(expression || '').trim();
  if (trimmed.startsWith('[')) return resolvedArgvArray(executable, trimmed, targetIndex, seen);
  if (trimmed.startsWith('(')) return resolvedArgvTuple(executable, trimmed, targetIndex, seen);
  const identifier = trimmed.match(/^[A-Za-z_]\w*$/)?.[0];
  if (identifier && !seen.has(identifier)) {
    seen.add(identifier);
    const assigned = assignedValueBefore(executable, identifier, targetIndex);
    if (assigned) return resolvedPythonArgvExpression(executable, assigned, targetIndex, seen);
  }
  return { kind: 'unknown' };
}

function resolvedCommandString(executable, expression, targetIndex) {
  const command = resolvedExpression(executable, expression, targetIndex);
  return command.kind === 'string' ? command.value : commandFallbackString(executable, expression, targetIndex);
}

function resolvedArgStrings(argv) {
  return argv.kind === 'array'
    ? argv.values.map((item) => (item.kind === 'string' ? item.value : null))
    : [];
}

function hasMutationVerb(tokens) {
  const mutationVerbPattern = new RegExp(`^${appwriteMutationVerbPatternSource}\\w*$`, 'i');
  return tokens.some((token) => typeof token === 'string' && mutationVerbPattern.test(token));
}

function appwriteServiceArgvMutates(argv) {
  if (argv.kind !== 'array') return false;
  const tokens = resolvedArgStrings(argv);
  for (let index = 0; index < tokens.length; index += 1) {
    const token = tokens[index];
    if (typeof token !== 'string') continue;
    if (token.startsWith('-')) {
      const optionName = token.split('=', 1)[0];
      if (!token.includes('=') && appwriteGlobalOptionsWithValues.has(optionName)) index += 1;
      continue;
    }
    if (appwriteServicePattern.test(token)) return appwriteArgvMutates({ kind: 'array', values: argv.values.slice(index) });
  }
  return false;
}

function curlArgvHasMutationOption(argv) {
  if (argv.kind !== 'array') return false;
  return resolvedArgStrings(argv).some((token) => typeof token === 'string' &&
    (/^(?:(?:-X(?:POST|PATCH|PUT|DELETE))|(?:-X|--request)(?:=(?:POST|PATCH|PUT|DELETE))?)$/i.test(token) ||
      curlBodyArgToken(token)));
}

function curlBodyArgToken(token) {
  return /^(?:-d|-F)(?:\b|.+)/.test(String(token || '')) ||
    /^--(?:data(?:-raw|-binary|-urlencode)?|json|form(?:-string)?)(?:=.*)?$/i.test(String(token || ''));
}

function unresolvedSubprocessArgvMutates(argv) {
  if (argv.kind !== 'array') return false;
  const tokens = resolvedArgStrings(argv);
  if (appwriteServiceArgvMutates(argv)) return true;
  if (tokens.includes('api') && ghApiArgvMutates(argv)) return true;
  return curlArgvHasMutationOption(argv) && curlArgvMutates(argv);
}

function hasReadVerb(tokens) {
  return tokens.some((token) => typeof token === 'string' && /^(?:get|list|read|show|view|describe)\w*$/i.test(token));
}

function hasUnknownArg(tokens) {
  return tokens.some((token) => token === null);
}

function appwriteArgvMutates(argv) {
  if (argv.kind === 'unknown') return true;
  const tokens = resolvedArgStrings(argv);
  if (hasMutationVerb(tokens)) return true;
  return hasUnknownArg(tokens) && !hasReadVerb(tokens);
}

function ghApiArgvMutates(argv) {
  if (argv.kind === 'unknown') return true;
  const tokens = resolvedArgStrings(argv);
  if (!tokens.includes('api')) return false;
  let hasReadOnlyMethod = false;
  let hasDefaultPostOption = false;
  for (let index = 0; index < tokens.length; index += 1) {
    const token = tokens[index];
    if (typeof token !== 'string') continue;
    const next = tokens[index + 1];
    if (/^(?:-X|--method)=(?:GET|HEAD|OPTIONS)$/i.test(token)) hasReadOnlyMethod = true;
    if (/^(?:-X|--method)$/i.test(token) && /^(?:GET|HEAD|OPTIONS)$/i.test(String(next || ''))) hasReadOnlyMethod = true;
    if (token === '-f' || token === '-F' || /^--(?:raw-field|field|input)(?:=.*)?$/i.test(token)) hasDefaultPostOption = true;
    if (/^(?:-X|--method)=(?:POST|PATCH|PUT|DELETE)$/i.test(token)) return true;
    if (/^(?:-X|--method)$/i.test(token)) {
      if (typeof next !== 'string') return true;
      if (/^(?:POST|PATCH|PUT|DELETE)$/i.test(next)) return true;
    }
  }
  if (hasDefaultPostOption && !hasReadOnlyMethod) return true;
  return hasUnknownArg(tokens) && !hasReadOnlyMethod;
}

function curlArgvMutates(argv) {
  if (argv.kind === 'unknown') return true;
  const tokens = resolvedArgStrings(argv);
  let hasBody = false;
  let hasGet = false;
  for (let index = 0; index < tokens.length; index += 1) {
    const token = tokens[index];
    if (typeof token !== 'string') continue;
    const next = tokens[index + 1];
    if (/^(?:-G|--get)(?:=.*)?$/i.test(token)) hasGet = true;
    if (curlBodyArgToken(token)) hasBody = true;
    if (/^-X(?:POST|PATCH|PUT|DELETE)$/i.test(token)) return true;
    if (/^(?:-X|--request)=(?:POST|PATCH|PUT|DELETE)$/i.test(token)) return true;
    if (/^(?:-X|--request)$/i.test(token)) {
      if (typeof next !== 'string') return true;
      if (/^(?:POST|PATCH|PUT|DELETE)$/i.test(next)) return true;
    }
  }
  if (hasUnknownArg(tokens) && !hasGet) return true;
  return hasBody && !hasGet;
}

const shellCommandLiteralPattern = /^(?:appwrite|aw|gh|curl)$/i;

function shellSegments(line) {
  const segments = [];
  let start = 0;
  let quote = '';
  let escaped = false;
  for (let index = 0; index < line.length; index += 1) {
    const char = line[index];
    if (quote) {
      if (escaped) {
        escaped = false;
      } else if (char === '\\') {
        escaped = true;
      } else if (char === quote) {
        quote = '';
      }
      continue;
    }
    if (char === '"' || char === "'") {
      quote = char;
    } else if (char === ';') {
      segments.push({ text: line.slice(start, index), index: start });
      start = index + 1;
    }
  }
  segments.push({ text: line.slice(start), index: start });
  return segments;
}

function shellParameterDefaultWordValue(value) {
  const match = String(value || '').match(/\$\{[A-Za-z_]\w*(?::?[-=])(?:"([^"]+)"|'([^']+)'|([^}]+))\}/);
  if (!match) return '';
  const candidate = String(match[1] || match[2] || match[3] || '').trim();
  return /^[A-Za-z0-9_.-]+$/.test(candidate) ? candidate : '';
}

function singleShellWord(value) {
  const trimmed = String(value || '').trim();
  const quote = trimmed[0];
  if ((quote === '"' || quote === "'") && trimmed.at(-1) === quote) return true;
  return !/\s/.test(trimmed);
}

function shellLiteralWordValue(value) {
  const trimmed = String(value || '').trim();
  if (!trimmed) return null;
  const quote = trimmed[0];
  if ((quote === '"' || quote === "'") && trimmed.at(-1) === quote) {
    const body = trimmed.slice(1, -1);
    if (quote === '"' && /[$`\\]/.test(body)) {
      const defaultValue = shellParameterDefaultWordValue(body);
      return defaultValue || null;
    }
    return body;
  }
  const defaultValue = shellParameterDefaultWordValue(trimmed);
  if (defaultValue) return defaultValue;
  return /^[A-Za-z0-9_.:/@-]+$/.test(trimmed) ? trimmed : null;
}

function shellWordAssignment(segment) {
  const trimmed = segment.trim();
  const match = trimmed.match(/^(?:(?:export|local|readonly)\s+|(?:declare|typeset)(?:\s+-[A-Za-z]+)*\s+)([A-Za-z_]\w*)=(.+)$/) ||
    trimmed.match(/^([A-Za-z_]\w*)=(.+)$/);
  if (!match) return null;
  if (!singleShellWord(match[2])) return null;
  return { name: match[1], value: shellLiteralWordValue(match[2]) };
}

function applyShellAssignment(segment, assignments) {
  const assignment = shellWordAssignment(segment);
  if (!assignment) return;
  if (assignment.value !== null) assignments.set(assignment.name, assignment.value);
  else assignments.delete(assignment.name);
}

function normalizedShellVariableCommand(segment, assignments) {
  const trimmed = segment.trim();
  const match = trimmed.match(/^(?<lead>(?:if|while|until)\s+)?(?<prefix>(?:(?:env\s+)?[A-Za-z_]\w*=(?:"[^"]*"|'[^']*'|\S+)\s+|sudo\s+|command\s+)*)(?:"\$(?<quoted>[A-Za-z_]\w*)"|"\$\{(?<quotedBrace>[A-Za-z_]\w*)\}"|\$(?<bare>[A-Za-z_]\w*)|\$\{(?<brace>[A-Za-z_]\w*)\})(?<rest>(?:\s|;|$)[\s\S]*)$/);
  if (!match) return '';
  const variable = match.groups.quoted || match.groups.quotedBrace || match.groups.bare || match.groups.brace;
  const value = assignments.get(variable) || '';
  const command = shellCommandLiteralPattern.test(value) ? value : '';
  if (!command) return '';
  return `${match.groups.lead || ''}${match.groups.prefix || ''}${command}${match.groups.rest || ''}`;
}

function resolveShellVariablesInLine(line, assignments) {
  return String(line || '').replace(/"\$([A-Za-z_]\w*)"|"\$\{([A-Za-z_]\w*)\}"|\$([A-Za-z_]\w*)|\$\{([A-Za-z_]\w*)\}/g, (_match, quoted, quotedBrace, bare, brace) => {
    const name = quoted || quotedBrace || bare || brace;
    return assignments.has(name) ? assignments.get(name) : '__UNKNOWN__';
  });
}

function shellResolvedCommandLines(executable) {
  const assignments = new Map();
  const commands = [];
  let lineStart = 0;
  for (const line of String(executable || '').split('\n')) {
    for (const segment of shellSegments(line)) {
      const normalized = normalizedShellVariableCommand(segment.text, assignments);
      const resolved = resolveShellVariablesInLine(normalized || segment.text, assignments);
      const firstToken = segment.text.search(/\S/);
      if (resolved.trim() && firstToken >= 0) commands.push({ index: lineStart + segment.index + firstToken, line: resolved });
      applyShellAssignment(segment.text, assignments);
    }
    lineStart += line.length + 1;
  }
  return commands;
}

function shellVariableCommandLines(executable) {
  return shellResolvedCommandLines(executable)
    .filter(({ line }) => /^\s*(?:if|while|until\s+)?(?:(?:env\s+)?[A-Za-z_]\w*=(?:"[^"]*"|'[^']*'|\S+)\s+|sudo\s+|command\s+)*\b(?:appwrite|aw|gh|curl)\b/i.test(line));
}

function shellTokenValue(token) {
  const trimmed = String(token || '').trim();
  if (!trimmed || trimmed.includes('__UNKNOWN__')) return null;
  if ((trimmed.startsWith('"') && trimmed.endsWith('"')) || (trimmed.startsWith("'") && trimmed.endsWith("'"))) {
    return trimmed.slice(1, -1);
  }
  return trimmed;
}

function shellCommandParts(line) {
  const tokens = String(line || '').trim().split(/\s+/).filter(Boolean);
  let index = 0;
  for (;;) {
    const token = tokens[index];
    if (!token) return null;
    if (token === 'sudo' || token === 'command' || /^(?:if|while|until)$/.test(token)) {
      index += 1;
      continue;
    }
    if (token === 'env') {
      index += 1;
      while (/^[A-Za-z_]\w*=/.test(tokens[index] || '')) index += 1;
      continue;
    }
    if (/^[A-Za-z_]\w*=/.test(token)) {
      index += 1;
      continue;
    }
    break;
  }
  const command = shellTokenValue(tokens[index]);
  const values = tokens.slice(index + 1).map((token) => {
    const value = shellTokenValue(token);
    return value === null ? { kind: 'unknown' } : { kind: 'string', value };
  });
  return { command, argv: { kind: 'array', values } };
}

function ghApiShellArgvMutates(argv) {
  if (argv.kind !== 'array') return false;
  const tokens = resolvedArgStrings(argv);
  if (!tokens.includes('api')) return false;
  let hasReadOnlyMethod = false;
  let hasDefaultPostOption = false;
  for (let index = 0; index < tokens.length; index += 1) {
    const token = tokens[index];
    const next = tokens[index + 1];
    if (typeof token !== 'string') continue;
    if (/^(?:-X|--method)=(?:GET|HEAD|OPTIONS)$/i.test(token)) hasReadOnlyMethod = true;
    if (/^(?:-X|--method)$/i.test(token) && /^(?:GET|HEAD|OPTIONS)$/i.test(String(next || ''))) hasReadOnlyMethod = true;
    if (token === '-f' || token === '-F' || /^--(?:raw-field|field|input)(?:=.*)?$/i.test(token)) hasDefaultPostOption = true;
    if (/^(?:-X|--method)=(?:POST|PATCH|PUT|DELETE|__UNKNOWN__)$/i.test(token)) return true;
    if (/^(?:-X|--method)$/i.test(token)) {
      if (typeof next !== 'string') return true;
      if (/^(?:POST|PATCH|PUT|DELETE)$/i.test(next)) return true;
    }
  }
  return hasDefaultPostOption && !hasReadOnlyMethod;
}

function curlShellArgvMutates(argv) {
  if (argv.kind !== 'array') return false;
  const tokens = resolvedArgStrings(argv);
  let hasBody = false;
  let hasGet = false;
  for (let index = 0; index < tokens.length; index += 1) {
    const token = tokens[index];
    const next = tokens[index + 1];
    if (typeof token !== 'string') continue;
    if (/^(?:-G|--get)(?:=.*)?$/i.test(token)) hasGet = true;
    if (curlBodyArgToken(token)) hasBody = true;
    if (/^-X(?:POST|PATCH|PUT|DELETE)$/i.test(token)) return true;
    if (/^(?:-X|--request)=(?:POST|PATCH|PUT|DELETE|__UNKNOWN__)$/i.test(token)) return true;
    if (/^(?:-X|--request)$/i.test(token)) {
      if (typeof next !== 'string') return true;
      if (/^(?:POST|PATCH|PUT|DELETE)$/i.test(next)) return true;
    }
  }
  return hasBody && !hasGet;
}

function shellCommandLineArgvMutates(line) {
  const parts = shellCommandParts(line);
  if (!parts?.command) return unknownShellCommandLineMayMutate(line);
  if (/^(?:appwrite|aw)$/i.test(parts.command)) return appwriteArgvMutates(parts.argv);
  if (/^gh$/i.test(parts.command)) return ghApiShellArgvMutates(parts.argv);
  if (/^curl$/i.test(parts.command)) return curlShellArgvMutates(parts.argv);
  return false;
}

function shellCommandLineMutates(line) {
  return cliMutationPattern.test(line) ||
    ghApiMutationPattern.test(line) ||
    curlMutationPattern.test(line) ||
    curlBodyMutationPattern.test(line) ||
    shellCommandLineArgvMutates(line);
}

function shellVariableCommandMutationFindings(executable) {
  return shellResolvedCommandLines(executable)
    .filter(({ line }) => shellCommandLineMutates(line))
    .map(({ index }) => ({ index }));
}

function splitTopLevelPlus(text) {
  const parts = [];
  let start = 0;
  let quote = '';
  let escaped = false;
  const stack = [];
  const push = (end) => {
    const value = text.slice(start, end).trim();
    if (value) parts.push(value);
    start = end + 1;
  };
  for (let index = 0; index < text.length; index += 1) {
    const char = text[index];
    if (quote) {
      if (escaped) {
        escaped = false;
      } else if (char === '\\') {
        escaped = true;
      } else if (char === quote) {
        quote = '';
      }
      continue;
    }
    if (char === '"' || char === "'" || char === '`') {
      quote = char;
    } else if ('({['.includes(char)) {
      stack.push(char);
    } else if (')}]'.includes(char)) {
      stack.pop();
    } else if (char === '+' && stack.length === 0) {
      push(index);
    }
  }
  push(text.length);
  return parts;
}

function templateLiteralShellValue(executable, expression, targetIndex, seen = new Set()) {
  const trimmed = String(expression || '').trim();
  if (!trimmed.startsWith('`') || !trimmed.endsWith('`')) return null;
  const body = trimmed.slice(1, -1);
  let value = '';
  let unknown = false;
  let escaped = false;
  for (let index = 0; index < body.length; index += 1) {
    const char = body[index];
    if (escaped) {
      value += char;
      escaped = false;
      continue;
    }
    if (char === '\\') {
      escaped = true;
      continue;
    }
    if (char === '$' && body[index + 1] === '{') {
      const closeIndex = findMatching(body, index + 1, '{', '}');
      if (closeIndex === -1) return { kind: 'unknown', value, unknown: true };
      const inner = body.slice(index + 2, closeIndex);
      const resolved = resolvedExpression(executable, inner, targetIndex, new Set(seen));
      if (resolved.kind === 'string') value += resolved.value;
      else {
        value += '__UNKNOWN__';
        unknown = true;
      }
      index = closeIndex;
      continue;
    }
    value += char;
  }
  return { kind: unknown ? 'dynamic' : 'string', value, unknown };
}

function resolvedShellStringExpression(executable, expression, targetIndex, seen = new Set()) {
  const trimmed = String(expression || '').trim();
  if (!trimmed) return { kind: 'unknown', value: '', unknown: true };
  const literal = stringLiteralValue(trimmed);
  if (literal !== null) return { kind: 'string', value: literal, unknown: false };
  const template = templateLiteralShellValue(executable, trimmed, targetIndex, seen);
  if (template) return template;
  const parts = splitTopLevelPlus(trimmed);
  if (parts.length > 1) {
    let value = '';
    let unknown = false;
    for (const part of parts) {
      const resolved = resolvedShellStringExpression(executable, part, targetIndex, new Set(seen));
      if (resolved.kind === 'unknown' && !resolved.value) {
        value += '__UNKNOWN__';
        unknown = true;
      } else {
        value += resolved.value;
        unknown = unknown || resolved.unknown;
      }
    }
    return { kind: unknown ? 'dynamic' : 'string', value, unknown };
  }
  const identifier = trimmed.match(/^[A-Za-z_$][\w$]*$/)?.[0];
  if (identifier && !seen.has(identifier)) {
    seen.add(identifier);
    const assigned = assignedValueBefore(executable, identifier, targetIndex);
    if (assigned) return resolvedShellStringExpression(executable, assigned, targetIndex, seen);
  }
  return { kind: 'unknown', value: '', unknown: true };
}

function unknownShellCommandLineMayMutate(line) {
  const normalized = String(line || '').trim().replace(/\s+/g, ' ');
  const match = normalized.match(/^(?:env\s+\S+=\S+\s+|sudo\s+|command\s+)*__UNKNOWN__(?:\s+(.*)|$)/);
  if (!match) return false;
  const rest = match[1] || '';
  if (/^(?:account|avatars|buckets?|databases?|documents?|rows?|storage|tables?|teams?|users?|executions?|functions?|graphql|messaging)\b/i.test(rest) && hasMutationVerb(rest.split(/\s+/))) return true;
  if (/^api\b/i.test(rest) && ghApiCliMutates(`gh ${rest}`)) return true;
  return curlCliMutates(`curl ${rest}`);
}

function shellCommandTextMutates(text) {
  const commandLines = [
    ...directCommandLines(text),
    ...shellVariableCommandLines(text).map(({ line }) => line.trim()),
  ];
  return commandLines.some((line) => shellCommandLineMutates(line) || unknownShellCommandLineMayMutate(line));
}

function shellExecMutationFindings(executable) {
  const findings = [];
  const callPattern = /\b(?:exec|execSync|execaCommand|execaCommandSync)\s*\(|\bexeca\s*\.\s*(?:command|commandSync)\s*\(/g;
  for (const match of executable.matchAll(callPattern)) {
    const callIndex = match.index || 0;
    if (insideQuoteAt(executable, callIndex)) continue;
    const openIndex = executable.indexOf('(', callIndex);
    const closeIndex = findMatching(executable, openIndex, '(', ')');
    if (closeIndex === -1) continue;
    const args = splitTopLevelArgs(executable.slice(openIndex + 1, closeIndex));
    const command = resolvedShellStringExpression(executable, args[0] || '', callIndex);
    if (command.value && shellCommandTextMutates(command.value)) findings.push({ index: callIndex });
  }
  return findings;
}

function methodValueStatus(value, executable, targetIndex) {
  const trimmed = String(value || '').trim();
  if (!trimmed) return 'unknown';
  if (/^['"`](?:POST|PATCH|PUT|DELETE)['"`]$/i.test(trimmed)) return 'mutating';
  if (/^['"`](?:GET|HEAD|OPTIONS)['"`]$/i.test(trimmed)) return 'readonly';
  if (/\b(?:POST|PATCH|PUT|DELETE)\b/i.test(trimmed)) return 'mutating';
  if (/\b(?:GET|HEAD|OPTIONS)\b/i.test(trimmed) && !/[?:]|process\.|argv|env|METHOD|method/i.test(trimmed)) return 'readonly';
  const identifier = trimmed.match(/^[A-Za-z_$][\w$]*$/)?.[0];
  if (identifier) {
    const assigned = assignedValueBefore(executable, identifier, targetIndex);
    if (assigned) return methodValueStatus(assigned, executable, targetIndex);
  }
  return 'unknown';
}

function objectMethodBodyStatus(body, executable, targetIndex) {
  let status = 'none';
  for (const propertyText of splitTopLevelArgs(body)) {
    const property = propertyText.trim();
    if (/^\.\.\./.test(property)) return 'unknown';
    const methodProperty = property.match(/^(?:method|['"`]method['"`])\s*:\s*([\s\S]+)$/i);
    if (methodProperty) {
      status = methodValueStatus(methodProperty[1], executable, targetIndex);
    } else if (/^method$/i.test(property)) {
      status = methodValueStatus('method', executable, targetIndex);
    } else if (/^\[[^\]]+\]\s*:/.test(property)) {
      return 'unknown';
    }
  }
  return status;
}

function methodAssignmentStatus(executable, identifier, targetIndex) {
  const events = [];
  const propertyPattern = new RegExp(String.raw`(?:^|[;\n])\s*${escapeRegExp(identifier)}\s*(?:\.\s*method|\[\s*['"\`]method['"\`]\s*\])\s*=(?!=)\s*`, 'g');
  for (const match of executable.matchAll(propertyPattern)) {
    const index = match.index || 0;
    if (index >= targetIndex) break;
    const expression = expressionAt(executable, index + match[0].length);
    events.push({ position: index, status: methodValueStatus(expression.value, executable, targetIndex) });
  }

  const assignPattern = /\bObject\s*\.\s*assign\s*\(/g;
  for (const match of executable.matchAll(assignPattern)) {
    const index = match.index || 0;
    if (index >= targetIndex) break;
    const openIndex = executable.indexOf('(', index);
    const closeIndex = findMatching(executable, openIndex, '(', ')');
    if (closeIndex === -1 || closeIndex >= targetIndex) continue;
    const args = splitTopLevelArgs(executable.slice(openIndex + 1, closeIndex));
    if (args[0]?.trim() !== identifier) continue;
    for (let sourceIndex = 1; sourceIndex < args.length; sourceIndex += 1) {
      const source = args[sourceIndex].trim();
      if (!source.startsWith('{')) continue;
      const end = findMatching(source, 0, '{', '}');
      const body = end === -1 ? source.slice(1) : source.slice(1, end);
      const status = objectMethodBodyStatus(body, executable, targetIndex);
      if (status !== 'none') events.push({ position: index + sourceIndex / 1000, status });
    }
  }
  events.sort((left, right) => left.position - right.position);
  let status = 'none';
  for (const event of events) {
    if (event.status !== 'none') status = event.status;
  }
  return status;
}

function fetchOptionsMethodStatus(options, executable, targetIndex) {
  const trimmed = String(options || '').trim();
  if (!trimmed) return 'none';
  let body = '';
  if (trimmed.startsWith('{')) {
    const end = findMatching(trimmed, 0, '{', '}');
    body = end === -1 ? trimmed.slice(1) : trimmed.slice(1, end);
  } else {
    const identifier = trimmed.match(/^[A-Za-z_$][\w$]*$/)?.[0];
    if (!identifier) return 'unknown';
    const assigned = assignedValueBefore(executable, identifier, targetIndex);
    if (!assigned) return 'unknown';
    if (!assigned.trim().startsWith('{')) return methodValueStatus(assigned, executable, targetIndex);
    const end = findMatching(assigned, 0, '{', '}');
    body = end === -1 ? assigned.slice(1) : assigned.slice(1, end);
    const assignedMethod = methodAssignmentStatus(executable, identifier, targetIndex);
    if (assignedMethod !== 'none') return assignedMethod;
  }
  return objectMethodBodyStatus(body, executable, targetIndex);
}

function requestMethodStatus(expression, executable, targetIndex, seen = new Set()) {
  const trimmed = String(expression || '').trim();
  if (!trimmed) return 'none';
  if (/^new\s+Request\s*\(/.test(trimmed)) {
    const openIndex = trimmed.indexOf('(');
    const closeIndex = findMatching(trimmed, openIndex, '(', ')');
    if (closeIndex === -1) return 'unknown';
    const args = splitTopLevelArgs(trimmed.slice(openIndex + 1, closeIndex));
    if (args.length < 2) return 'readonly';
    const status = fetchOptionsMethodStatus(args[1], executable, targetIndex);
    return status === 'none' ? 'readonly' : status;
  }
  const identifier = trimmed.match(/^[A-Za-z_$][\w$]*$/)?.[0];
  if (identifier && !seen.has(identifier)) {
    seen.add(identifier);
    const assigned = assignmentInfoBefore(executable, identifier, targetIndex);
    if (assigned?.value) return requestMethodStatus(assigned.value, executable, assigned.index, seen);
  }
  return 'none';
}

function fetchMutationFindings(executable) {
  const findings = [];
  for (const match of executable.matchAll(/\bfetch\s*\(/g)) {
    const callIndex = match.index || 0;
    const openIndex = executable.indexOf('(', callIndex);
    const closeIndex = findMatching(executable, openIndex, '(', ')');
    if (closeIndex === -1) continue;
    const args = splitTopLevelArgs(executable.slice(openIndex + 1, closeIndex));
    let status = fetchOptionsMethodStatus(args[1], executable, callIndex);
    if (status === 'none') status = requestMethodStatus(args[0], executable, callIndex);
    if (status === 'mutating' || status === 'unknown') findings.push({ index: callIndex });
  }
  return findings;
}

function subprocessMutationFindings(executable) {
  const findings = [];
  const callPattern = /\b(?:spawn|spawnSync|execFile|execFileSync|execa|execaSync)\s*\(/g;
  for (const match of executable.matchAll(callPattern)) {
    const callIndex = match.index || 0;
    const openIndex = executable.indexOf('(', callIndex);
    const closeIndex = findMatching(executable, openIndex, '(', ')');
    if (closeIndex === -1) continue;
    const args = splitTopLevelArgs(executable.slice(openIndex + 1, closeIndex));
    const command = resolvedCommandString(executable, args[0] || '', callIndex);
    const argv = resolvedArgvExpression(executable, args[1] || '', callIndex);
    if (!command) {
      if (unresolvedSubprocessArgvMutates(argv)) findings.push({ index: callIndex });
      continue;
    }
    let mutates = false;
    if (/^(?:appwrite|aw)$/i.test(command)) {
      mutates = appwriteArgvMutates(argv);
    } else if (/^gh$/i.test(command)) {
      mutates = argv.kind === 'unknown' || ghApiArgvMutates(argv);
    } else if (/^curl$/i.test(command)) {
      mutates = argv.kind === 'unknown' || curlArgvMutates(argv);
    }
    if (mutates) findings.push({ index: callIndex });
  }
  return findings;
}

function argvWithoutCommand(argv) {
  return argv.kind === 'array' ? { kind: 'array', values: argv.values.slice(1) } : argv;
}

const pythonSubprocessMethodNames = ['run', 'call', 'check_call', 'check_output', 'Popen'];

function pythonSubprocessImports(executable) {
  const modules = new Set(['subprocess']);
  const functions = new Set();
  for (const match of executable.matchAll(/(?:^|[;\n])\s*import\s+([^\n;]+)/g)) {
    for (const imported of match[1].split(',')) {
      const module = imported.trim().match(/^subprocess(?:\s+as\s+([A-Za-z_]\w*))?$/);
      if (module) modules.add(module[1] || 'subprocess');
    }
  }
  for (const match of executable.matchAll(/(?:^|[;\n])\s*from\s+subprocess\s+import\s+([^\n;]+)/g)) {
    for (const imported of match[1].split(',')) {
      const name = imported.trim();
      if (name === '*') {
        for (const method of pythonSubprocessMethodNames) functions.add(method);
        continue;
      }
      const importedFunction = name.match(/^([A-Za-z_]\w*)(?:\s+as\s+([A-Za-z_]\w*))?$/);
      if (importedFunction && pythonSubprocessMethodNames.includes(importedFunction[1])) {
        functions.add(importedFunction[2] || importedFunction[1]);
      }
    }
  }
  return { modules, functions };
}

function pythonSubprocessCallPattern(executable) {
  const { modules, functions } = pythonSubprocessImports(executable);
  const methodSource = `(?:${pythonSubprocessMethodNames.map(escapeRegExp).join('|')})`;
  const parts = [`(?:${[...modules].map(escapeRegExp).join('|')})\\s*\\.\\s*${methodSource}`];
  if (functions.size) parts.push(`(?:${[...functions].map(escapeRegExp).join('|')})`);
  return new RegExp(`\\b(?:${parts.join('|')})\\s*\\(`, 'g');
}

function keywordArgValue(args, name) {
  const pattern = new RegExp(String.raw`^${escapeRegExp(name)}\s*=\s*([\s\S]+)$`);
  for (const arg of args) {
    const match = String(arg || '').trim().match(pattern);
    if (match) return match[1].trim();
  }
  return '';
}

function firstPositionalArg(args) {
  return args.find((arg) => !/^[A-Za-z_]\w*\s*=/.test(String(arg || '').trim())) || '';
}

function pythonSubprocessArgExpression(args) {
  return keywordArgValue(args, 'args') || firstPositionalArg(args);
}

function pythonShellEnabled(args) {
  return /^True\b/.test(keywordArgValue(args, 'shell'));
}

function pythonStringLiteralParts(expression) {
  const trimmed = String(expression || '').trim();
  const match = trimmed.match(/^([A-Za-z]*)(['"])([\s\S]*)\2$/);
  if (!match) return null;
  return { prefixes: match[1].toLowerCase(), body: match[3] };
}

function resolvedPythonShellStringExpression(executable, expression, targetIndex, seen = new Set()) {
  const trimmed = String(expression || '').trim();
  if (!trimmed) return { kind: 'unknown', value: '', unknown: true };
  const literal = pythonStringLiteralParts(trimmed);
  if (literal) {
    if (!literal.prefixes.includes('f')) return { kind: 'string', value: literal.body, unknown: false };
    let value = '';
    let unknown = false;
    for (let index = 0; index < literal.body.length; index += 1) {
      const char = literal.body[index];
      if (char === '{' && literal.body[index + 1] === '{') {
        value += '{';
        index += 1;
        continue;
      }
      if (char === '}' && literal.body[index + 1] === '}') {
        value += '}';
        index += 1;
        continue;
      }
      if (char === '{') {
        const closeIndex = findMatching(literal.body, index, '{', '}');
        if (closeIndex === -1) return { kind: 'unknown', value, unknown: true };
        const inner = literal.body.slice(index + 1, closeIndex);
        const resolved = resolvedExpression(executable, inner, targetIndex, new Set(seen));
        if (resolved.kind === 'string') value += resolved.value;
        else {
          value += '__UNKNOWN__';
          unknown = true;
        }
        index = closeIndex;
        continue;
      }
      value += char;
    }
    return { kind: unknown ? 'dynamic' : 'string', value, unknown };
  }
  const identifier = trimmed.match(/^[A-Za-z_]\w*$/)?.[0];
  if (identifier && !seen.has(identifier)) {
    seen.add(identifier);
    const assigned = assignedValueBefore(executable, identifier, targetIndex);
    if (assigned) return resolvedPythonShellStringExpression(executable, assigned, targetIndex, seen);
  }
  return { kind: 'unknown', value: '', unknown: true };
}

function pythonSubprocessMutationFindings(executable) {
  const findings = [];
  const callPattern = pythonSubprocessCallPattern(executable);
  for (const match of executable.matchAll(callPattern)) {
    const callIndex = match.index || 0;
    const openIndex = executable.indexOf('(', callIndex);
    const closeIndex = findMatching(executable, openIndex, '(', ')');
    if (closeIndex === -1) continue;
    const args = splitTopLevelArgs(executable.slice(openIndex + 1, closeIndex));
    const argExpression = pythonSubprocessArgExpression(args);
    if (pythonShellEnabled(args)) {
      const command = resolvedPythonShellStringExpression(executable, argExpression, callIndex);
      if (command.value && shellCommandTextMutates(command.value)) findings.push({ index: callIndex });
      continue;
    }
    const argv = resolvedPythonArgvExpression(executable, argExpression, callIndex);
    if (argv.kind !== 'array' || argv.values.length === 0) continue;
    const command = argv.values[0].kind === 'string' ? argv.values[0].value : '';
    const commandArgs = argvWithoutCommand(argv);
    if (!command) {
      if (unresolvedSubprocessArgvMutates(commandArgs)) findings.push({ index: callIndex });
      continue;
    }
    let mutates = false;
    if (/^(?:appwrite|aw)$/i.test(command)) {
      mutates = appwriteArgvMutates(commandArgs);
    } else if (/^gh$/i.test(command)) {
      mutates = ghApiArgvMutates(commandArgs);
    } else if (/^curl$/i.test(command)) {
      mutates = curlArgvMutates(commandArgs);
    }
    if (mutates) findings.push({ index: callIndex });
  }
  return findings;
}

function defaultStatusFromRhs(rhs, kind = '') {
  rhs = String(rhs || '').trim();
  const compact = rhs.replace(/\s+/g, '');
  if (/^["']?(?:1|true|yes)["']?$/i.test(compact) ||
    /^["']?\$\{[^}]*:-["']?(?:1|true|yes)["']?[^}]*\}["']?$/i.test(compact) ||
    /(?:\?\?|\|\|)\s*["'](?:1|true|yes)["']/i.test(rhs)) {
    return 'enabled';
  }
  if (/^["']?(?:0|false|no)["']?$/i.test(compact) ||
    /^["']?\$\{[^}]*:-["']?(?:0|false|no)["']?[^}]*\}["']?$/i.test(compact) ||
    /(?:\?\?|\|\|)\s*["'](?:0|false|no)["']/i.test(rhs)) {
    return 'disabled';
  }
  if (kind === 'write-control' && new RegExp(String.raw`\bprocess\s*\.\s*env\s*\.\s*${writeEnabledTokenPattern}\b\s*===?\s*${writeEnabledAllowedValuePattern}`, 'i').test(rhs)) {
    return 'disabled';
  }
  if (kind === 'write-control' && new RegExp(String.raw`\bprocess\s*\.\s*env\s*\.\s*${writeEnabledTokenPattern}\b\s*!==?\s*${writeEnabledDisabledValuePattern}`, 'i').test(rhs)) return 'enabled';
  if (kind === 'dry-run' && new RegExp(String.raw`\bprocess\s*\.\s*env\s*\.\s*${dryRunTokenPattern}\b\s*!==?\s*${dryRunDisabledValuePattern}`, 'i').test(rhs)) return 'enabled';
  if (kind === 'dry-run' && new RegExp(String.raw`\bprocess\s*\.\s*env\s*\.\s*${dryRunTokenPattern}\b\s*===?\s*${dryRunEnabledValuePattern}`, 'i').test(rhs)) return 'disabled';
  return '';
}

function assignmentDefaultBefore(executable, tokenPattern, kind = '', targetIndex = executable.length) {
  const assignmentPattern = new RegExp(String.raw`(?:^|[;\n])\s*(?:(?:const|let|var)\s+)?${tokenPattern}\b\s*=(?!=)\s*`, 'ig');
  let status = '';
  for (const match of executable.matchAll(assignmentPattern)) {
    const index = match.index || 0;
    if (index >= targetIndex) break;
    if (!sameGuardStack(executable, index, targetIndex)) continue;
    const expression = expressionAt(executable, index + match[0].length);
    if (expression.end > targetIndex) continue;
    status = defaultStatusFromRhs(expression.value, kind) || 'unknown';
  }
  return status;
}

function firstAssignmentDefault(executable, tokenPattern, kind = '') {
  return assignmentDefaultBefore(executable, tokenPattern, kind);
}

function firstAssignmentDefaultForName(executable, name, kind, targetIndex = executable.length) {
  return assignmentDefaultBefore(executable, escapeRegExp(name), kind, targetIndex);
}

function hasDryRunEnabledDefault(executable) {
  return firstAssignmentDefault(executable, dryRunTokenPattern, 'dry-run') === 'enabled';
}

function hasSafeDryRunDefault(executable) {
  if (firstAssignmentDefault(executable, dryRunTokenPattern, 'dry-run') === 'disabled') return false;
  if (firstAssignmentDefault(executable, writeEnabledTokenPattern, 'write-control') === 'enabled') return false;
  return hasDryRunEnabledDefault(executable) || firstAssignmentDefault(executable, writeEnabledTokenPattern, 'write-control') === 'disabled';
}

function hasExplicitWriteControl(executable) {
  return explicitWriteFlagPattern.test(executable) || explicitWriteEnvPattern.test(executable);
}

function mutationFindings(executable) {
  return [
    ...mutationPatterns
    .flatMap((pattern) => [...executable.matchAll(globalPattern(pattern))].map((match) => ({ index: match.index || 0 })))
    .filter((finding) => finding.index >= 0),
    ...fetchMutationFindings(executable),
    ...shellExecMutationFindings(executable),
    ...subprocessMutationFindings(executable),
    ...pythonSubprocessMutationFindings(executable),
    ...shellVariableCommandMutationFindings(executable),
  ]
    .sort((left, right) => left.index - right.index);
}

function structuralStackAt(text, targetIndex) {
  const stack = [];
  let quote = '';
  let escaped = false;
  for (let index = 0; index < targetIndex; index += 1) {
    const char = text[index];
    if (quote) {
      if (escaped) {
        escaped = false;
      } else if (char === '\\') {
        escaped = true;
      } else if (char === quote) {
        quote = '';
      }
      continue;
    }
    if (char === '"' || char === "'" || char === '`') {
      quote = char;
    } else if (char === '{') {
      stack.push(index);
    } else if (char === '}') {
      stack.pop();
    }
  }
  return stack;
}

function sameStructuralStack(left, right) {
  if (left.length !== right.length) return false;
  return left.every((item, index) => item === right[index]);
}

function shellControlStackAt(text, targetIndex) {
  const stack = [];
  const controlPattern = /\bif\b[\s\S]{0,240}?\bthen\b|\b(?:for|while|until)\b[\s\S]{0,240}?\bdo\b|\bcase\b[\s\S]{0,240}?\bin\b|\b(?:fi|done|esac)\b/g;
  for (const match of text.slice(0, targetIndex).matchAll(controlPattern)) {
    const token = match[0].trim().toLowerCase();
    if (/^(?:if|for|while|until|case)\b/.test(token)) {
      stack.push(match.index || 0);
    } else {
      stack.pop();
    }
  }
  return stack;
}

function sameGuardStack(executable, guardIndex, mutationIndex) {
  return sameStructuralStack(structuralStackAt(executable, guardIndex), structuralStackAt(executable, mutationIndex)) &&
    sameStructuralStack(shellControlStackAt(executable, guardIndex), shellControlStackAt(executable, mutationIndex));
}

function insideQuoteAt(text, targetIndex) {
  let quote = '';
  let escaped = false;
  for (let index = 0; index < targetIndex; index += 1) {
    const char = text[index];
    if (quote) {
      if (escaped) {
        escaped = false;
      } else if (char === '\\') {
        escaped = true;
      } else if (char === quote) {
        quote = '';
      }
      continue;
    }
    if (char === '"' || char === "'" || char === '`') quote = char;
  }
  return Boolean(quote);
}

function executedGuardStatement(executable, guardIndex) {
  if (insideQuoteAt(executable, guardIndex)) return false;
  const lineStart = executable.lastIndexOf('\n', guardIndex) + 1;
  const prefix = executable.slice(lineStart, guardIndex);
  const statementStart = Math.max(prefix.lastIndexOf(';'), prefix.lastIndexOf('{')) + 1;
  return prefix.slice(statementStart).trim() === '';
}

function guardExitInsideBranch(executable, guardIndex) {
  const rest = executable.slice(guardIndex);
  if (!/^\s*if\b/.test(rest)) return true;
  const thenMatch = rest.match(/\bthen\b/i);
  if (thenMatch) {
    const branchStart = guardIndex + (thenMatch.index || 0) + thenMatch[0].length;
    const branchTail = executable.slice(branchStart);
    const branchEndMatch = branchTail.search(/\b(?:else|fi)\b/i);
    const branch = branchTail.slice(0, branchEndMatch === -1 ? Math.min(branchTail.length, 500) : branchEndMatch);
    return new RegExp(disabledExitPattern, 'i').test(branch);
  }
  const openBrace = executable.indexOf('{', guardIndex);
  if (openBrace >= 0) {
    const closeBrace = findMatching(executable, openBrace, '{', '}');
    if (closeBrace === -1) return false;
    return new RegExp(disabledExitPattern, 'i').test(executable.slice(openBrace + 1, closeBrace));
  }
  return true;
}

function guardVariableNames(text, kind) {
  const names = kind === 'dry-run' ? dryRunTokenNames : writeEnabledTokenNames;
  return names.filter((name) => new RegExp(String.raw`\b${escapeRegExp(name)}\b`).test(text));
}

function guardHasSafeDefault(executable, kind, text, guardIndex) {
  return guardVariableNames(text, kind).some((name) => {
    const status = firstAssignmentDefaultForName(executable, name, kind, guardIndex ?? executable.length);
    return kind === 'dry-run' ? status === 'enabled' : status === 'disabled';
  });
}

function hasUnsafeGuardReassignment(executable, names, kind, guardEnd, mutationIndex) {
  for (const name of names) {
    const assignmentPattern = new RegExp(String.raw`(?:^|[;\n])\s*(?:(?:const|let|var)\s+)?${escapeRegExp(name)}\b\s*=(?!=)\s*`, 'ig');
    for (const match of executable.matchAll(assignmentPattern)) {
      const index = match.index || 0;
      if (index <= guardEnd) continue;
      if (index >= mutationIndex) break;
      if (!sameGuardStack(executable, index, mutationIndex)) continue;
      const expression = expressionAt(executable, index + match[0].length);
      const status = defaultStatusFromRhs(expression.value, kind) || 'unknown';
      if (kind === 'dry-run' ? status !== 'enabled' : status !== 'disabled') return true;
    }
  }
  return false;
}

function guardedWriteBefore(executable, mutationIndex) {
  const windowStart = Math.max(0, mutationIndex - 4000);
  const preceding = executable.slice(windowStart, mutationIndex);
  let firstGuard = null;
  for (const { kind, pattern } of failClosedGuardPatterns) {
    for (const match of preceding.matchAll(globalPattern(pattern))) {
      const guardIndex = windowStart + (match.index || 0);
      if (executedGuardStatement(executable, guardIndex) &&
        guardExitInsideBranch(executable, guardIndex) &&
        sameGuardStack(executable, guardIndex, mutationIndex)) {
        const names = guardVariableNames(match[0], kind);
        const defaultSafe = guardHasSafeDefault(executable, kind, match[0], guardIndex) &&
          !hasUnsafeGuardReassignment(executable, names, kind, guardIndex + match[0].length, mutationIndex);
        const guard = { kind, defaultSafe };
        if (defaultSafe) return guard;
        if (!firstGuard) firstGuard = guard;
      }
    }
  }
  return firstGuard;
}

function statementBoundsAt(text, targetIndex) {
  const lineStart = text.lastIndexOf('\n', targetIndex) + 1;
  const semicolonStart = text.lastIndexOf(';', targetIndex) + 1;
  const start = Math.max(lineStart, semicolonStart);
  const nextLine = text.indexOf('\n', targetIndex);
  const nextSemicolon = text.indexOf(';', targetIndex);
  const candidates = [nextLine, nextSemicolon].filter((index) => index >= 0);
  const end = candidates.length ? Math.min(...candidates) : text.length;
  return { start, end };
}

function statementAt(text, targetIndex) {
  const { start, end } = statementBoundsAt(text, targetIndex);
  return text.slice(start, end);
}

function nonAssignmentEvidence(text, pattern) {
  return String(text || '').split('\n').some((line) => {
    const trimmed = line.trim();
    if (!trimmed) return false;
    if (/^(?:const|let|var)\s+[A-Za-z_$][\w$]*\s*=/.test(trimmed)) return false;
    if (/^[A-Za-z_$][\w$]*\s*=/.test(trimmed)) return false;
    return pattern.test(trimmed);
  });
}

const scopedInputEvidencePattern = /(?:\b(?:allowlist|allow-list|allowList|scoped|reviewedInput|reviewed_input|approvedInput|approved_input|scopedInput|scoped_input|reviewed input|approved input|HARD_ENG_REVIEWED_INPUT)\b|--(?:company|tenant|ids|input|file)\b)/i;
const approvalBoundaryEvidencePattern = /\b(?:approvalBoundaries|approval_boundaries|approval boundaries|approved side effect|human approval|approval receipt)\b/i;
const appwriteReadCliPattern = /^(?:env\s+\S+=\S+\s+|sudo\s+)*(?:appwrite|aw)\b.*\b(?:get|list|read|show|view|describe)\w*\b/i;
const ghApiCliPattern = /^(?:env\s+\S+=\S+\s+|sudo\s+)*gh\s+api\b/i;
const curlCliPattern = /^(?:env\s+\S+=\S+\s+|sudo\s+)*curl\b/i;

function ghApiCliMutates(command) {
  return ghApiMutationPattern.test(command);
}

function curlCliMutates(command) {
  return curlMutationPattern.test(command) || curlBodyMutationPattern.test(command);
}

function directCommandLines(context) {
  return String(context || '').split('\n')
    .map((line) => line.trim())
    .filter((line) => line && !/^(?:const|let|var|echo|printf|console\s*\.)\b/i.test(line));
}

function fetchReadVerificationFindings(executable) {
  const findings = [];
  for (const match of executable.matchAll(/\bfetch\s*\(/g)) {
    const callIndex = match.index || 0;
    if (insideQuoteAt(executable, callIndex)) continue;
    const openIndex = executable.indexOf('(', callIndex);
    const closeIndex = findMatching(executable, openIndex, '(', ')');
    if (closeIndex === -1) continue;
    const args = splitTopLevelArgs(executable.slice(openIndex + 1, closeIndex));
    const status = fetchOptionsMethodStatus(args[1], executable, callIndex);
    if (status === 'none' || status === 'readonly') findings.push({ index: callIndex });
  }
  return findings;
}

function subprocessReadVerificationFindings(executable) {
  const findings = [];
  const callPattern = /\b(?:spawn|spawnSync|execFile|execFileSync|execa|execaSync)\s*\(/g;
  for (const match of executable.matchAll(callPattern)) {
    const callIndex = match.index || 0;
    if (insideQuoteAt(executable, callIndex)) continue;
    const openIndex = executable.indexOf('(', callIndex);
    const closeIndex = findMatching(executable, openIndex, '(', ')');
    if (closeIndex === -1) continue;
    const args = splitTopLevelArgs(executable.slice(openIndex + 1, closeIndex));
    const command = resolvedCommandString(executable, args[0] || '', callIndex);
    if (!command) continue;
    const argv = resolvedArgvExpression(executable, args[1] || '', callIndex);
    const tokens = resolvedArgStrings(argv);
    if (/^(?:appwrite|aw)$/i.test(command) && argv.kind === 'array' && hasReadVerb(tokens)) findings.push({ index: callIndex });
    else if (/^gh$/i.test(command) && argv.kind === 'array' && tokens.includes('api') && !ghApiArgvMutates(argv)) findings.push({ index: callIndex });
    else if (/^curl$/i.test(command) && argv.kind === 'array' && !curlArgvMutates(argv)) findings.push({ index: callIndex });
  }
  return findings;
}

function pythonSubprocessReadVerificationFindings(executable) {
  const findings = [];
  const callPattern = pythonSubprocessCallPattern(executable);
  for (const match of executable.matchAll(callPattern)) {
    const callIndex = match.index || 0;
    if (insideQuoteAt(executable, callIndex)) continue;
    const openIndex = executable.indexOf('(', callIndex);
    const closeIndex = findMatching(executable, openIndex, '(', ')');
    if (closeIndex === -1) continue;
    const args = splitTopLevelArgs(executable.slice(openIndex + 1, closeIndex));
    const argExpression = pythonSubprocessArgExpression(args);
    if (pythonShellEnabled(args)) {
      const command = resolvedPythonShellStringExpression(executable, argExpression, callIndex);
      const commandLines = command.value
        ? [...directCommandLines(command.value), ...shellVariableCommandLines(command.value).map(({ line }) => line.trim())]
        : [];
      if (commandLines.some((line) => appwriteReadCliPattern.test(line))) findings.push({ index: callIndex });
      else if (commandLines.some((line) => ghApiCliPattern.test(line) && !ghApiCliMutates(line))) findings.push({ index: callIndex });
      else if (commandLines.some((line) => curlCliPattern.test(line) && !curlCliMutates(line))) findings.push({ index: callIndex });
      continue;
    }
    const argv = resolvedPythonArgvExpression(executable, argExpression, callIndex);
    if (argv.kind !== 'array' || argv.values.length === 0) continue;
    const command = argv.values[0].kind === 'string' ? argv.values[0].value : '';
    const commandArgs = argvWithoutCommand(argv);
    const tokens = resolvedArgStrings(commandArgs);
    if (/^(?:appwrite|aw)$/i.test(command) && hasReadVerb(tokens)) findings.push({ index: callIndex });
    else if (/^gh$/i.test(command) && tokens.includes('api') && !ghApiArgvMutates(commandArgs)) findings.push({ index: callIndex });
    else if (/^curl$/i.test(command) && !curlArgvMutates(commandArgs)) findings.push({ index: callIndex });
  }
  return findings;
}

function hasReadVerificationOperation(context) {
  const commandLines = [
    ...directCommandLines(context),
    ...shellVariableCommandLines(context).map(({ line }) => line.trim()),
  ];
  if (commandLines.some((line) => appwriteReadCliPattern.test(line))) return true;
  if (commandLines.some((line) => ghApiCliPattern.test(line) && !ghApiCliMutates(line))) return true;
  if (commandLines.some((line) => curlCliPattern.test(line) && !curlCliMutates(line))) return true;
  if (fetchReadVerificationFindings(context).length) return true;
  return subprocessReadVerificationFindings(context).length > 0 || pythonSubprocessReadVerificationFindings(context).length > 0;
}

function hasScopedMutationInput(executable, mutation) {
  return nonAssignmentEvidence(statementAt(executable, mutation.index), scopedInputEvidencePattern);
}

function hasMutationApprovalBoundary(executable, mutation) {
  const windowStart = Math.max(0, mutation.index - 1200);
  const context = `${executable.slice(windowStart, mutation.index)}\n${statementAt(executable, mutation.index)}`;
  return nonAssignmentEvidence(context, approvalBoundaryEvidencePattern);
}

function hasPostWriteVerification(executable, mutation) {
  const { end } = statementBoundsAt(executable, mutation.index);
  const context = executable.slice(end, Math.min(executable.length, end + 1600));
  return hasReadVerificationOperation(context);
}

const failures = [];
for (const entry of gitFileEntries()) {
  if (!regularBlob(entry) || !candidatePath(entry)) continue;
  const file = entry.file;
  const source = readFile(file);
  if (!source.ok) {
    failures.push({ file, issue: 'source blob read failed', detail: source.detail });
    continue;
  }
  const text = source.text;
  if (!candidate(entry, text)) continue;
  const executable = executableText(text);
  const mutations = mutationFindings(executable);
  if (!mutations.length) continue;
  const missing = new Set(requirementChecks
    .filter(([, check]) => !check(executable))
    .map(([label]) => label));
  for (const mutation of mutations) {
    for (const [label, check] of mutationRequirementChecks) {
      if (!check(executable, mutation)) missing.add(label);
    }
    const guard = guardedWriteBefore(executable, mutation.index);
    if (!guard?.defaultSafe) {
      missing.add('guarded write execution');
      if (guard && !guard.defaultSafe) missing.add('dry-run default');
      else if (!hasSafeDryRunDefault(executable)) missing.add('dry-run default');
    }
  }
  if (missing.size) failures.push({ file, missing: [...missing] });
}

if (failures.length) {
  console.error(`hard-eng write safety: ${failures.length} issue(s)`);
  for (const failure of failures) {
    if (failure.issue) console.error(`- ${failure.file}: ${failure.issue}; ${failure.detail}`);
    else console.error(`- ${failure.file}: risky mutation script missing ${failure.missing.join(', ')}`);
  }
  console.error('Risky backend/prod/customer mutation scripts must be dry-run by default, require an explicit write flag, use scoped allowlist/input, record approvalBoundaries, verify after writes, and guard mutation commands behind the write control.');
  process.exit(1);
}

console.log('hard-eng write safety: pass');
