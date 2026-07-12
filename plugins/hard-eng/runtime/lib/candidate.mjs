import fs from 'node:fs';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { digestValue, sha256 } from './canonical.mjs';
import { git } from './git.mjs';
import { resolveContainedPath } from './safe-path.mjs';

const sensitiveCandidatePath = /(?:^|\/)(?:\.env(?:\..*)?|id_(?:rsa|dsa|ecdsa|ed25519)|[^/]*\.(?:pem|key|p12)|credentials?(?:\.[^/]*)?|secrets?(?:\.[^/]*)?)$/i;

function gitBuffer(cwd, args) {
  return execFileSync('git', ['-C', cwd, ...args], { maxBuffer: 32 * 1024 * 1024 });
}

function optionalGit(cwd, args) {
  const value = git(cwd, args, { allowFailure: true, quiet: true });
  return value === null ? null : value.trim();
}

function untrackedPaths(cwd) {
  const output = gitBuffer(cwd, ['ls-files', '--others', '--exclude-standard', '-z']);
  return output.toString('utf8').split('\0').filter(Boolean).sort();
}

function zeroParts(buffer) {
  return buffer.toString('utf8').split('\0').filter(Boolean);
}

function objectFormat(cwd) {
  const value = git(cwd, ['rev-parse', '--show-object-format']).trim();
  if (!['sha1', 'sha256'].includes(value)) throw new Error('Git object format is unsupported.');
  return value;
}

function blobOid(bytes, algorithm) {
  return createHash(algorithm).update(Buffer.from(`blob ${bytes.length}\0`)).update(bytes).digest('hex');
}

function worktreeEntry(cwd, relative, indexMode, algorithm) {
  const target = path.join(cwd, relative);
  let stat;
  try {
    stat = fs.lstatSync(target);
  } catch (error) {
    if (error.code === 'ENOENT') return null;
    throw error;
  }
  if (indexMode === '160000') {
    if (!stat.isDirectory() || stat.isSymbolicLink()) throw new Error(`Changed gitlink is invalid: ${relative}.`);
    return { path: relative, mode: '160000', oid: git(target, ['rev-parse', 'HEAD']).trim() };
  }
  if (stat.isSymbolicLink()) {
    const bytes = Buffer.from(fs.readlinkSync(target));
    return { path: relative, mode: '120000', oid: blobOid(bytes, algorithm) };
  }
  if (!stat.isFile()) throw new Error(`Tracked candidate path has an unsupported type: ${relative}.`);
  const mode = (stat.mode & 0o111) !== 0 ? '100755' : '100644';
  return { path: relative, mode, oid: blobOid(fs.readFileSync(target), algorithm) };
}

function candidateTreeEntries(cwd, untracked) {
  const algorithm = objectFormat(cwd);
  const changed = new Set(zeroParts(gitBuffer(cwd, ['diff-files', '--name-only', '-z', '--'])));
  const entries = [];
  for (const record of zeroParts(gitBuffer(cwd, ['ls-files', '--stage', '-z']))) {
    const separator = record.indexOf('\t');
    if (separator < 0) throw new Error('Git index entry is malformed.');
    const [mode, oid, stage] = record.slice(0, separator).split(' ');
    const relative = record.slice(separator + 1);
    if (stage !== '0') throw new Error('Unmerged Git index entries block candidate fingerprinting.');
    const entry = changed.has(relative)
      ? worktreeEntry(cwd, relative, mode, algorithm)
      : { path: relative, mode, oid };
    if (entry) entries.push(entry);
  }
  for (const relative of untracked) {
    const { target, stat } = resolveContainedPath(cwd, relative, { label: 'Untracked candidate' });
    if (!stat.isFile()) throw new Error(`Untracked candidate must be a regular file: ${relative}.`);
    entries.push({
      path: relative,
      mode: (stat.mode & 0o111) !== 0 ? '100755' : '100644',
      oid: blobOid(fs.readFileSync(target), algorithm),
    });
  }
  return entries.sort((left, right) => left.path.localeCompare(right.path));
}

export function fingerprintCommitTree(cwd, commit) {
  const resolved = git(cwd, ['rev-parse', '--verify', `${commit}^{commit}`]).trim();
  const entries = zeroParts(gitBuffer(cwd, ['ls-tree', '-r', '-z', '--full-tree', resolved])).map((record) => {
    const separator = record.indexOf('\t');
    if (separator < 0) throw new Error('Git tree entry is malformed.');
    const [mode, type, oid] = record.slice(0, separator).split(' ');
    if (!['blob', 'commit'].includes(type)) throw new Error('Git tree contains an unsupported entry type.');
    return { path: record.slice(separator + 1), mode, oid };
  });
  return digestValue(entries.sort((left, right) => left.path.localeCompare(right.path)));
}

function manifestEntry(cwd, relative) {
  if (path.isAbsolute(relative) || relative.split(path.sep).includes('..')) throw new Error('Untracked candidate path is unsafe.');
  const { target: file, stat } = resolveContainedPath(cwd, relative, { label: 'Untracked candidate' });
  if (!stat.isFile()) throw new Error(`Untracked candidate must be a regular file: ${relative}.`);
  return {
    path: relative.split(path.sep).join('/'),
    mode: stat.mode & 0o777,
    size: stat.size,
    digest: sha256(fs.readFileSync(file)),
  };
}

function assertDigest(value, label) {
  if (!/^[a-f0-9]{64}$/i.test(value ?? '')) throw new Error(`${label} must be a SHA-256 digest.`);
}

function assertKeys(value, allowed, label) {
  for (const key of Object.keys(value)) if (!allowed.has(key)) throw new Error(`${label} contains unknown field ${key}.`);
}

export function validateEvidenceSummary(evidence) {
  if (!evidence || typeof evidence !== 'object' || Array.isArray(evidence)) throw new Error('Candidate evidence summary is invalid.');
  if (evidence.applicability === 'not-applicable') {
    assertKeys(evidence, new Set(['applicability', 'reason_digest', 'evidence_digest']), 'Candidate evidence');
    assertDigest(evidence.reason_digest, 'Candidate evidence reason digest');
    assertDigest(evidence.evidence_digest, 'Candidate evidence digest');
    return true;
  }
  assertKeys(evidence, new Set([
    'kind', 'applicability', 'candidate_fingerprint', 'evidence_digest', 'scenario_digest',
    'approved_direction_digest', 'baseline_status', 'baseline_digest', 'implementation_digest',
    'video_required', 'video_present', 'video_unavailable', 'known_gaps_digest', 'artifact_count',
  ]), 'Candidate visual evidence');
  if (evidence.applicability !== 'applicable' || !['milestone', 'final'].includes(evidence.kind)) {
    throw new Error('Candidate visual evidence kind is invalid.');
  }
  for (const field of [
    'candidate_fingerprint', 'evidence_digest', 'scenario_digest', 'approved_direction_digest',
    'baseline_digest', 'implementation_digest', 'known_gaps_digest',
  ]) assertDigest(evidence[field], `Candidate visual evidence ${field}`);
  if (!['captured', 'not-applicable'].includes(evidence.baseline_status)) throw new Error('Candidate baseline status is invalid.');
  for (const field of ['video_required', 'video_present', 'video_unavailable']) {
    if (typeof evidence[field] !== 'boolean') throw new Error(`Candidate visual evidence ${field} is invalid.`);
  }
  if (!Number.isInteger(evidence.artifact_count) || evidence.artifact_count < 1 || evidence.artifact_count > 24) {
    throw new Error('Candidate visual evidence artifact count is invalid.');
  }
  return true;
}

export function validateCandidate(candidate) {
  if (!candidate || typeof candidate !== 'object' || Array.isArray(candidate)) throw new Error('Candidate identity is required.');
  assertKeys(candidate, new Set([
    'base_commit', 'head', 'origin_main', 'branch', 'tree_fingerprint',
    'tracked_diff_digest', 'untracked_manifest_digest', 'remote', 'fingerprint',
    'check', 'user_visible', 'evidence', 'approval', 'approved_by', 'approved_at',
  ]), 'Candidate');
  for (const field of ['base_commit', 'head']) {
    if (!/^[a-f0-9]{40,64}$/i.test(candidate[field] ?? '')) throw new Error(`Candidate ${field} is invalid.`);
  }
  if (candidate.origin_main !== null && !/^[a-f0-9]{40,64}$/i.test(candidate.origin_main ?? '')) {
    throw new Error('Candidate origin_main is invalid.');
  }
  if (typeof candidate.branch !== 'string' || !candidate.branch || candidate.branch.length > 240) throw new Error('Candidate branch is invalid.');
  for (const field of ['tree_fingerprint', 'tracked_diff_digest', 'untracked_manifest_digest', 'fingerprint']) {
    assertDigest(candidate[field], `Candidate ${field}`);
  }
  if (candidate.remote !== null) {
    assertKeys(candidate.remote, new Set(['name', 'url_digest']), 'Candidate remote');
    if (candidate.remote?.name !== 'origin') throw new Error('Candidate remote must be origin.');
    assertDigest(candidate.remote.url_digest, 'Candidate remote URL digest');
  }
  if (candidate.check !== undefined) {
    assertKeys(candidate.check, new Set(['registry_digest', 'results_digest', 'preflight_digest']), 'Candidate check');
    for (const [field, value] of Object.entries(candidate.check)) assertDigest(value, `Candidate check ${field}`);
  }
  if (candidate.user_visible !== undefined && typeof candidate.user_visible !== 'boolean') throw new Error('Candidate visibility is invalid.');
  if (candidate.approval !== undefined && !['pending', 'approved', 'not-required'].includes(candidate.approval)) {
    throw new Error('Candidate approval is invalid.');
  }
  if (candidate.approved_by !== undefined && candidate.approved_by !== 'user') throw new Error('Candidate approver is invalid.');
  if (candidate.approved_at !== undefined && Number.isNaN(Date.parse(candidate.approved_at))) throw new Error('Candidate approval time is invalid.');
  if (candidate.evidence !== undefined) validateEvidenceSummary(candidate.evidence);
  if (candidate.user_visible !== undefined) {
    if (!candidate.check || !candidate.evidence || !candidate.approval) throw new Error('Stored candidate lacks check, evidence, or approval state.');
    if (candidate.user_visible !== (candidate.evidence.applicability === 'applicable')) {
      throw new Error('Candidate visibility and evidence applicability disagree.');
    }
  }
  return true;
}

export function fingerprintCandidate(cwd, { allowedUntracked = [], allowAllUntracked = false } = {}) {
  const head = git(cwd, ['rev-parse', 'HEAD']).trim();
  const originMain = optionalGit(cwd, ['rev-parse', '--verify', 'origin/main']);
  const baseCommit = originMain ? git(cwd, ['merge-base', 'HEAD', 'origin/main']).trim() : head;
  const branch = optionalGit(cwd, ['symbolic-ref', '--short', '-q', 'HEAD']) ?? 'detached';
  const changedPaths = gitBuffer(cwd, ['diff', '--name-only', '-z', 'HEAD', '--'])
    .toString('utf8').split('\0').filter(Boolean);
  const allUntracked = untrackedPaths(cwd);
  if ([...changedPaths, ...allUntracked].some((relative) => sensitiveCandidatePath.test(relative))) {
    throw new Error('Sensitive environment, credential, or key path blocks candidate fingerprinting before content read.');
  }
  const trackedDiffDigest = sha256(gitBuffer(cwd, ['diff', '--binary', '--no-ext-diff', 'HEAD', '--']));
  const allowed = new Set(allowedUntracked);
  const unexpected = allowAllUntracked ? [] : allUntracked.filter((file) => !allowed.has(file));
  if (unexpected.length) throw new Error(`Unapproved untracked candidate files: ${unexpected.join(', ')}.`);
  const manifest = allUntracked.map((file) => manifestEntry(cwd, file));
  const remoteUrl = optionalGit(cwd, ['config', '--get', 'remote.origin.url']);
  const content = {
    tracked_diff_digest: trackedDiffDigest,
    untracked_manifest_digest: digestValue(manifest),
  };
  const facts = {
    base_commit: baseCommit,
    head,
    origin_main: originMain,
    branch,
    tree_fingerprint: digestValue(candidateTreeEntries(cwd, allUntracked)),
    tracked_diff_digest: trackedDiffDigest,
    untracked_manifest_digest: content.untracked_manifest_digest,
    remote: remoteUrl ? { name: 'origin', url_digest: sha256(remoteUrl) } : null,
  };
  const candidate = { ...facts, fingerprint: digestValue(facts) };
  validateCandidate(candidate);
  return candidate;
}
