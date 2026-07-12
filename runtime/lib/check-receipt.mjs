import { canonicalJson } from './canonical.mjs';
import { hmacHex, safeEqualHex } from './crypto.mjs';
import { validateCandidate } from './candidate.mjs';

export const CHECK_RECEIPT_SCHEMA = 'hard-eng/check-receipt/v1';
const receiptKeys = [
  'schema', 'run_id', 'revision', 'repo_id', 'checkout_id', 'intent_digest',
  'status', 'registry_digest', 'results_digest', 'preflight_digest', 'candidate',
  'issued_at', 'expires_at', 'signature',
];

function assertDigest(value, label) {
  if (!/^[a-f0-9]{64}$/i.test(value ?? '')) throw new Error(`${label} must be a SHA-256 digest.`);
}

function unsigned(receipt) {
  const { signature: ignored, ...body } = receipt;
  return body;
}

function signature(key, body) {
  return hmacHex(key, 'hard-eng-check-receipt/v1', canonicalJson(body));
}

export function signCheckReceipt(key, { run, report, preflight }, { now = Date.now(), ttlMs = 5 * 60_000 } = {}) {
  if (run.phase !== 'Ship' || run.cursor.step !== 'preflight') throw new Error('Check receipt requires Ship:preflight.');
  if (preflight?.status !== 'PASS') throw new Error('A failing Ship preflight cannot be signed.');
  assertDigest(preflight.digest, 'Ship preflight digest');
  if (report.status !== 'PASS') throw new Error('A failing check report cannot be signed for Ship.');
  if (!Number.isInteger(ttlMs) || ttlMs < 1_000 || ttlMs > 10 * 60_000) {
    throw new Error('Check receipt TTL must be between one and ten minutes.');
  }
  validateCandidate(report.candidate);
  const body = {
    schema: CHECK_RECEIPT_SCHEMA,
    run_id: run.run_id,
    revision: run.revision,
    repo_id: run.repo_id,
    checkout_id: run.checkout_id,
    intent_digest: run.intent.digest,
    status: report.status,
    registry_digest: report.registry_digest,
    results_digest: report.results_digest,
    preflight_digest: preflight.digest,
    candidate: report.candidate,
    issued_at: new Date(now).toISOString(),
    expires_at: new Date(now + ttlMs).toISOString(),
  };
  return { ...body, signature: signature(key, body) };
}

export function verifyCheckReceipt(receipt, { key, run, repoId, checkoutId, now = Date.now() } = {}) {
  if (!receipt || receipt.schema !== CHECK_RECEIPT_SCHEMA) throw new Error('Check receipt schema is invalid.');
  if (JSON.stringify(Object.keys(receipt).sort()) !== JSON.stringify([...receiptKeys].sort())) {
    throw new Error('Check receipt fields are invalid.');
  }
  const expectedSignature = signature(key, unsigned(receipt));
  if (!safeEqualHex(receipt.signature, expectedSignature)) throw new Error('Check receipt signature is invalid.');
  if (Buffer.byteLength(canonicalJson(receipt)) >= 8 * 1024) throw new Error('Check receipt exceeds 8 KiB.');
  const issuedAt = Date.parse(receipt.issued_at);
  const expiresAt = Date.parse(receipt.expires_at);
  if (!Number.isFinite(issuedAt) || !Number.isFinite(expiresAt) || expiresAt <= issuedAt) {
    throw new Error('Check receipt timestamps are invalid.');
  }
  if (expiresAt - issuedAt > 10 * 60_000) throw new Error('Check receipt lifetime is invalid.');
  if (expiresAt <= now) throw new Error('Check receipt has expired.');
  if (issuedAt > now + 30_000) throw new Error('Check receipt issue time is invalid.');
  if (receipt.run_id !== run.run_id) throw new Error('Check receipt run does not match.');
  if (receipt.revision !== run.revision) throw new Error('Check receipt revision does not match current state.');
  if (receipt.repo_id !== repoId || receipt.repo_id !== run.repo_id) throw new Error('Check receipt repository does not match.');
  if (receipt.checkout_id !== checkoutId || receipt.checkout_id !== run.checkout_id) throw new Error('Check receipt checkout does not match.');
  if (receipt.intent_digest !== run.intent.digest) throw new Error('Check receipt intent is stale.');
  if (receipt.status !== 'PASS') throw new Error('Check receipt is not green.');
  assertDigest(receipt.registry_digest, 'Check registry digest');
  assertDigest(receipt.results_digest, 'Check results digest');
  assertDigest(receipt.preflight_digest, 'Ship preflight digest');
  validateCandidate(receipt.candidate);
  return receipt;
}
