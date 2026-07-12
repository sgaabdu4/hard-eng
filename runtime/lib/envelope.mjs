import { canonicalJson, digestValue } from './canonical.mjs';
import { hmacHex, safeEqualHex } from './crypto.mjs';

const ENVELOPE_VERSION = 1;
const DEFAULT_TTL_MS = 30_000;

function encodePayload(payload) {
  return Buffer.from(canonicalJson(payload)).toString('base64url');
}

function decodePayload(encoded) {
  try {
    return JSON.parse(Buffer.from(encoded, 'base64url').toString('utf8'));
  } catch {
    throw new Error('Hard Eng envelope payload is invalid.');
  }
}

export function taskHash(key, sessionId) {
  if (!sessionId) throw new Error('Hook session identity is missing.');
  return hmacHex(key, 'task', sessionId);
}

export function unsignedToolInput(input) {
  if (!input || typeof input !== 'object' || Array.isArray(input)) throw new Error('State tool input must be an object.');
  const { _he: ignored, ...unsigned } = input;
  return unsigned;
}

export function createEnvelope({ key, store, hookInput, toolInput, now = Date.now(), ttlMs = DEFAULT_TTL_MS }) {
  const unsigned = unsignedToolInput(toolInput);
  const action = unsigned.action;
  if (!['start', 'status', 'resume', 'event'].includes(action)) throw new Error('State action is invalid.');
  if (!hookInput.turn_id || !hookInput.tool_use_id) throw new Error('Hook turn/tool identity is missing.');
  const payload = {
    version: ENVELOPE_VERSION,
    repo_id: store.repoId,
    checkout_id: store.checkoutId,
    checkout_root: store.checkoutRoot,
    store_root: store.root,
    task_hash: taskHash(key, hookInput.session_id),
    turn_hash: hmacHex(key, 'turn', hookInput.turn_id),
    tool_use_hash: hmacHex(key, 'tool-use', hookInput.tool_use_id),
    operation: action,
    run_id: unsigned.payload?.run_id ?? null,
    revision: unsigned.payload?.expected_revision ?? null,
    input_digest: digestValue(unsigned),
    issued_at_ms: now,
    expires_at_ms: now + ttlMs,
  };
  const encoded = encodePayload(payload);
  return { payload: encoded, signature: hmacHex(key, 'envelope', encoded) };
}

export function peekEnvelope(envelope) {
  if (!envelope || typeof envelope.payload !== 'string' || typeof envelope.signature !== 'string') {
    throw new Error('Signed Hard Eng envelope is required.');
  }
  return decodePayload(envelope.payload);
}

export function verifyEnvelope(envelope, { key, action, args, now = Date.now() }) {
  const payload = peekEnvelope(envelope);
  const expected = hmacHex(key, 'envelope', envelope.payload);
  if (!safeEqualHex(envelope.signature, expected)) throw new Error('Hard Eng envelope signature is invalid.');
  if (payload.version !== ENVELOPE_VERSION) throw new Error('Hard Eng envelope version is unsupported.');
  if (payload.operation !== action) throw new Error('Hard Eng envelope operation does not match the tool action.');
  if (!Number.isFinite(payload.expires_at_ms) || now > payload.expires_at_ms) throw new Error('Hard Eng envelope has expired.');
  if (!Number.isFinite(payload.issued_at_ms) || payload.issued_at_ms > now + 5_000) throw new Error('Hard Eng envelope issue time is invalid.');
  for (const field of ['repo_id', 'checkout_id', 'task_hash', 'turn_hash', 'tool_use_hash', 'input_digest']) {
    if (!/^[a-f0-9]{64}$/i.test(payload[field] ?? '')) throw new Error(`Hard Eng envelope ${field} is invalid.`);
  }
  if (typeof payload.checkout_root !== 'string' || !payload.checkout_root.startsWith('/')) {
    throw new Error('Hard Eng envelope checkout root is invalid.');
  }
  if (args && payload.input_digest !== digestValue(unsignedToolInput(args))) {
    throw new Error('Hard Eng envelope input digest does not match the tool arguments.');
  }
  return payload;
}

export function replayKey(payload) {
  return digestValue({
    task_hash: payload.task_hash,
    turn_hash: payload.turn_hash,
    tool_use_hash: payload.tool_use_hash,
    operation: payload.operation,
    input_digest: payload.input_digest,
  });
}
