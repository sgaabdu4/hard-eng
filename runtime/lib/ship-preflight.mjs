import fs from 'node:fs';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { digestValue, sha256 } from './canonical.mjs';
import { validatePlanFile } from './plan.mjs';
import { resolveContainedPath } from './safe-path.mjs';
import { validateSupportReceipt } from './schema.mjs';

const sensitivePath = /(?:^|\/)(?:\.env(?:\..*)?|id_(?:rsa|dsa|ecdsa|ed25519)|[^/]*\.(?:pem|key|p12)|credentials?(?:\.[^/]*)?|secrets?(?:\.[^/]*)?)$/i;
const generatedPath = /(?:^|\/)(?:generated|auto-generated)(?:\/|$)|(?:^|\/)CHANGELOG\.md$/i;
const secretLike = /(?:-----BEGIN [A-Z ]*PRIVATE KEY-----|\bsk-[A-Za-z0-9_-]{20,}|\bgh[pousr]_[A-Za-z0-9]{20,}|\bxox[baprs]-[A-Za-z0-9-]{20,}|\bAKIA[A-Z0-9]{16}\b|\bBearer\s+[A-Za-z0-9._-]{20,})/;

function gitBuffer(repo, args) {
  return execFileSync('git', ['-C', repo, ...args], { maxBuffer: 32 * 1024 * 1024 });
}

function zeroParts(buffer) {
  return buffer.toString('utf8').split('\0').filter(Boolean);
}

function changedEntries(repo) {
  const parts = zeroParts(gitBuffer(repo, ['diff', '--name-status', '-z', 'HEAD', '--']));
  const entries = [];
  for (let index = 0; index < parts.length;) {
    const status = parts[index++];
    const first = parts[index++];
    if (!status || !first) break;
    if (/^[RC]/.test(status)) entries.push({ status, source_path: first, path: parts[index++] ?? first });
    else entries.push({ status, path: first });
  }
  for (const relative of zeroParts(gitBuffer(repo, ['ls-files', '--others', '--exclude-standard', '-z']))) {
    entries.push({ status: '?', path: relative });
  }
  return entries;
}

function finding(code, severity, summary, relative = null) {
  return {
    code,
    severity,
    action: 'manual',
    summary,
    ...(relative ? { path_digest: sha256(relative) } : {}),
  };
}

function scanUntracked(repo, entries, allowed, findings) {
  for (const entry of entries.filter((item) => item.status === '?')) {
    if (!allowed.has(entry.path)) {
      findings.push(finding('unexpected-untracked', 'high', 'An untracked candidate path was not explicitly allowed.', entry.path));
      continue;
    }
    if (sensitivePath.test(entry.path)) continue;
    let target;
    let stat;
    try {
      ({ target, stat } = resolveContainedPath(repo, entry.path, { label: 'Untracked candidate' }));
    } catch {
      findings.push(finding('unsafe-untracked', 'high', 'An allowed untracked candidate has an unsafe path.', entry.path));
      continue;
    }
    if (!stat.isFile() || stat.isSymbolicLink()) {
      findings.push(finding('unsafe-untracked', 'high', 'An allowed untracked candidate is not a regular file.', entry.path));
      continue;
    }
    if (stat.size > 4 * 1024 * 1024) {
      findings.push(finding('untracked-too-large', 'high', 'An untracked candidate exceeds the 4 MiB content-scan limit.', entry.path));
      continue;
    }
    if (secretLike.test(fs.readFileSync(target, 'utf8'))) {
      findings.push(finding('secret-content', 'critical', 'Secret-like content was detected in an untracked candidate.', entry.path));
    }
  }
}

function supportToolChecks(run, findings) {
  for (const tool of ['codebase-memory', 'context-mode']) {
    const receipt = [...run.support_tools].reverse().find((item) => item.tool === tool);
    try {
      validateSupportReceipt(receipt);
      if (tool === 'codebase-memory' && receipt.operation !== 'detect_changes') {
        throw new Error('Ship requires Codebase Memory detect_changes evidence.');
      }
    } catch {
      findings.push(finding('support-tool-disposition', 'high', `Ship requires a bounded ${tool} applicability receipt.`));
    }
  }
}

export function runShipPreflight(repo, run, { allowedUntracked = [] } = {}) {
  const findings = [];
  if (run.phase !== 'Ship' || run.cursor.step !== 'preflight') {
    findings.push(finding('lifecycle', 'critical', 'Ship preflight requires the exact Ship:preflight cursor.'));
  }
  if (run.findings.some((item) => item.admission === 'open')) {
    findings.push(finding('open-finding', 'critical', 'An admitted Learn finding is still open.'));
  }
  if (run.plan) {
    try {
      const plan = validatePlanFile(repo, { runId: run.run_id, requireAccepted: true });
      if (plan.digest !== run.plan.digest) findings.push(finding('plan-drift', 'critical', 'Accepted plan digest is stale.'));
    } catch {
      findings.push(finding('plan-drift', 'critical', 'Accepted plan currentness could not be proven.'));
    }
  }
  supportToolChecks(run, findings);

  const entries = changedEntries(repo);
  const allowed = new Set(allowedUntracked);
  const conflicted = zeroParts(gitBuffer(repo, ['diff', '--name-only', '-z', '--diff-filter=U', '--']));
  if (conflicted.length) findings.push(finding('unmerged', 'critical', 'Unmerged Git paths block Ship.'));
  for (const entry of entries) {
    for (const candidatePath of [entry.source_path, entry.path].filter(Boolean)) {
      if (sensitivePath.test(candidatePath)) {
        findings.push(finding('sensitive-path', 'critical', 'Environment, credential, key, or secret-bearing paths cannot enter the candidate.', candidatePath));
      }
      if (generatedPath.test(candidatePath)) {
        findings.push(finding('generated-owner', 'high', 'Generated or changelog output was edited instead of its source owner.', candidatePath));
      }
    }
    if (entry.status.startsWith('D') && run.intent.kind === 'direct') {
      findings.push(finding('direct-deletion', 'high', 'Deletion requires accepted Plan scope rather than Direct Build.', entry.path));
    }
  }
  const hasSensitivePath = entries.some((entry) => (
    sensitivePath.test(entry.path) || sensitivePath.test(entry.source_path ?? '')
  ));
  const diff = hasSensitivePath
    ? Buffer.from('content-scan-blocked-by-sensitive-path')
    : gitBuffer(repo, ['diff', '--binary', '--no-ext-diff', 'HEAD', '--']);
  if (secretLike.test(diff.toString('utf8'))) {
    findings.push(finding('secret-content', 'critical', 'Secret-like content was detected in the tracked candidate.'));
  }
  scanUntracked(repo, entries, allowed, findings);
  const core = {
    schema: 'hard-eng/ship-preflight/v1',
    status: findings.length ? 'FAIL' : 'PASS',
    changed_path_count: entries.length,
    changed_paths_digest: digestValue(entries.map((entry) => ({
      status: entry.status,
      source_path_digest: entry.source_path ? sha256(entry.source_path) : null,
      path_digest: sha256(entry.path),
    }))),
    diff_digest: sha256(diff),
    support_tools_digest: digestValue(run.support_tools),
    findings,
  };
  return { ...core, digest: digestValue(core) };
}
