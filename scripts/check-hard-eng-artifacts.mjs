#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { TextDecoder } from 'node:util';

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
  console.error('Usage: check-hard-eng-artifacts.mjs [--staged|--head|--rev <rev>] [repo]');
  process.exit(2);
}
if (sawRev && !scanRev) {
  console.error('Usage: check-hard-eng-artifacts.mjs --rev <rev> [repo]');
  process.exit(2);
}
const scanTreeish = scanRev || (scanHead ? 'HEAD' : '');
const maxTextArtifactBytes = 512 * 1024;
const maxBinaryArtifactBytes = 8 * 1024 * 1024;
const utf8Decoder = new TextDecoder('utf-8', { fatal: true });
const artifactDirectorySegments = ['artifacts', 'evidence', 'outputs', 'tmp', 'logs', 'screenshots', 'traces', 'videos'];
const artifactFileExtensions = ['.log', '.jsonl', '.har', '.trace', '.webm', '.mp4', '.zip', '.tar', '.tar.gz'];
const ignoredUntrackedNoiseRoots = ['vendor', 'node_modules', '.git', 'tests', 'cache', '.cache', '.codebase', '.codebase-memory', '.dart_tool', '.next', '.turbo', 'build', 'coverage', 'dist', '__pycache__'];
const ignoredUntrackedArtifactPathspecs = [
  'artifacts/e2e',
  'docs/planning',
  ...artifactDirectorySegments.flatMap((segment) => [segment, `:(glob)**/${segment}/**`]),
  ...artifactFileExtensions.flatMap((extension) => [`*${extension}`, `:(glob)**/*${extension}`]),
];

function git(argsList, options = {}) {
  return spawnSync('git', ['-C', root, ...argsList], {
    encoding: 'buffer',
    maxBuffer: options.maxBuffer || 1024 * 1024 * 32,
  });
}

function gitPaths(argsList) {
  const result = git(argsList);
  if (result.status !== 0) return [];
  return result.stdout.toString('utf8').split('\0').filter(Boolean);
}

function gitFailureDetail(result) {
  if (result.error?.code === 'ENOBUFS') return 'git output exceeded scanner buffer';
  return result.stderr.toString('utf8').trim() || result.error?.message || `git exited with status ${result.status ?? 'unknown'}`;
}

function gitBlobSpec(file) {
  return scanStaged ? `:${file}` : `${scanTreeish}:${file}`;
}

function gitBlobSize(file) {
  const result = git(['cat-file', '-s', gitBlobSpec(file)], { maxBuffer: 1024 * 1024 });
  if (result.status !== 0) return { ok: false, detail: gitFailureDetail(result) };
  const size = Number.parseInt(result.stdout.toString('utf8').trim(), 10);
  if (!Number.isSafeInteger(size) || size < 0) return { ok: false, detail: 'git returned an invalid blob size' };
  return { ok: true, size };
}

function gitBlob(file) {
  const result = git(['cat-file', 'blob', gitBlobSpec(file)], { maxBuffer: maxTextArtifactBytes + 1024 });
  if (result.status !== 0) return { ok: false, detail: gitFailureDetail(result) };
  return { ok: true, blob: result.stdout };
}

function extname(file) {
  const base = path.basename(file).toLowerCase();
  if (base.endsWith('.tar.gz')) return '.tar.gz';
  return path.extname(base);
}

function hasSegment(file, segments) {
  const parts = file.split(/[\\/]+/).map((part) => part.toLowerCase());
  return segments.some((segment) => parts.includes(segment));
}

function firstSegmentIndex(file, segments) {
  const parts = file.split(/[\\/]+/).map((part) => part.toLowerCase());
  let first = -1;
  for (const segment of segments) {
    const index = parts.indexOf(segment);
    if (index !== -1 && (first === -1 || index < first)) first = index;
  }
  return first;
}

function firstArtifactRootIndex(file) {
  const normalized = file.replaceAll('\\', '/');
  if (/^docs\/planning\//.test(normalized)) return 0;
  return firstSegmentIndex(normalized, artifactDirectorySegments);
}

function hasIgnoredUntrackedNoiseSegment(file) {
  const normalized = file.replaceAll('\\', '/');
  const artifactIndex = firstArtifactRootIndex(normalized);
  if (artifactIndex === -1) return hasSegment(normalized, ignoredUntrackedNoiseRoots);
  const parts = normalized.split(/[\\/]+/).map((part) => part.toLowerCase());
  return parts.some((part, index) => index < artifactIndex && ignoredUntrackedNoiseRoots.includes(part));
}

function isArtifactPath(file) {
  const normalized = file.replaceAll('\\', '/');
  if (/^(?:vendor|node_modules|\.git|tests)\//.test(normalized)) return false;
  if (/^docs\/planning\//.test(normalized)) return true;
  if (hasSegment(normalized, artifactDirectorySegments)) return true;
  return artifactFileExtensions.includes(extname(normalized));
}

function isIgnoredUntrackedArtifactPath(file) {
  const normalized = file.replaceAll('\\', '/');
  if (hasIgnoredUntrackedNoiseSegment(normalized)) return false;
  return isArtifactPath(normalized);
}

function isTextArtifact(file) {
  return ['.txt', '.md', '.json', '.jsonl', '.log', '.html', '.csv', '.tsv', '.yaml', '.yml'].includes(extname(file));
}

function isSmallExtensionlessArtifact(file, size) {
  return extname(file) === '' && size <= maxTextArtifactBytes;
}

function decodeUtf8(blob) {
  try {
    return utf8Decoder.decode(blob);
  } catch {
    return null;
  }
}

function reservedEmail(value) {
  const domain = value.split('@')[1]?.toLowerCase() || '';
  return ['example.com', 'example.org', 'example.net', 'example.invalid', 'test.invalid', 'localhost'].includes(domain);
}

function rawDataFindings(text) {
  const findings = [];
  for (const match of text.matchAll(/\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b/gi)) {
    if (!reservedEmail(match[0])) findings.push('raw email <redacted>');
  }
  if (/["']?\b(?:session|token|secret|api[_-]?key|password|credential)[A-Za-z0-9_-]*["']?\s*[:=]\s*["']?[A-Za-z0-9_./+=-]{16,}/i.test(text)) {
    findings.push('session/token/credential-like value');
  }
  if (/\b(?:prod|production|customer|user|account|tenant|task|session)\b[\s\S]{0,80}\b[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\b/i.test(text)) {
    findings.push('raw operational UUID');
  }
  return findings;
}

const scanGitOnly = scanStaged || Boolean(scanTreeish);
const tracked = new Set(scanTreeish ? gitPaths(['ls-tree', '-r', '-z', '--name-only', scanTreeish]) : gitPaths(['ls-files', '-z']));
const untracked = new Set(scanGitOnly ? [] : gitPaths(['ls-files', '--others', '--exclude-standard', '-z']));
const ignoredUntracked = new Set(scanGitOnly ? [] : gitPaths(['ls-files', '--others', '--ignored', '--exclude-standard', '-z', '--', ...ignoredUntrackedArtifactPathspecs]).filter(isIgnoredUntrackedArtifactPath));
const files = [...new Set([...tracked, ...untracked, ...ignoredUntracked])].filter(isArtifactPath).sort();
const failures = [];

for (const file of files) {
  const fullPath = path.join(root, file);
  const useGitBlob = tracked.has(file) && (scanStaged || Boolean(scanTreeish));
  let size = 0;
  if (useGitBlob) {
    const sizeResult = gitBlobSize(file);
    if (!sizeResult.ok) {
      failures.push({ file, issue: 'artifact metadata read failed', detail: sizeResult.detail });
      continue;
    }
    size = sizeResult.size;
  } else {
    let stat;
    try {
      stat = fs.statSync(fullPath);
    } catch {
      continue;
    }
    if (!stat.isFile()) continue;
    size = stat.size;
  }
  if (untracked.has(file) || ignoredUntracked.has(file)) {
    failures.push({ file, issue: 'untracked artifact file', detail: 'record it intentionally, ignore it intentionally, move it outside the repo, or request scoped cleanup approval' });
  }
  const textArtifact = isTextArtifact(file);
  const smallExtensionlessArtifact = !textArtifact && isSmallExtensionlessArtifact(file, size);
  if (textArtifact || smallExtensionlessArtifact) {
    if (textArtifact && size > maxTextArtifactBytes) {
      failures.push({ file, issue: 'large text payload artifact', detail: `size ${size} bytes exceeds ${maxTextArtifactBytes}` });
      continue;
    }
    const textResult = useGitBlob ? gitBlob(file) : { ok: true, blob: fs.readFileSync(fullPath) };
    if (!textResult.ok) {
      failures.push({ file, issue: 'artifact blob read failed', detail: textResult.detail });
      continue;
    }
    const text = smallExtensionlessArtifact ? decodeUtf8(textResult.blob) : textResult.blob.toString('utf8');
    if (text !== null) {
      for (const finding of rawDataFindings(text)) {
        failures.push({ file, issue: 'raw operational data in artifact', detail: finding });
      }
    }
  } else if (size > maxBinaryArtifactBytes) {
    failures.push({ file, issue: 'large binary artifact', detail: `size ${size} bytes exceeds ${maxBinaryArtifactBytes}` });
  }
}

if (failures.length) {
  console.error(`hard-eng artifacts: ${failures.length} issue(s)`);
  for (const failure of failures) {
    console.error(`- ${failure.file}: ${failure.issue}; ${failure.detail}`);
  }
  console.error('Remediate by recording intentional artifacts, ignoring temp/heavy outputs, moving raw artifacts outside the repo, or committing only redacted aggregate summaries.');
  process.exit(1);
}

console.log('hard-eng artifacts: pass');
