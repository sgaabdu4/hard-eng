import { isPlainObject } from './canonical.mjs';

const digestPattern = /^[a-f0-9]{64}$/;

export function assertExactObject(value, expectedKeys, label) {
  if (!isPlainObject(value)) throw new Error(`${label} must be an object.`);
  const actual = Object.keys(value).sort();
  const expected = [...expectedKeys].sort();
  if (JSON.stringify(actual) !== JSON.stringify(expected)) {
    throw new Error(`${label} fields are invalid.`);
  }
}

export function assertSha256Digest(value, label) {
  if (!digestPattern.test(value ?? '')) throw new Error(`${label} must be a SHA-256 digest.`);
}

export function validateSetupSnapshot(value, label) {
  if (value === null) return;
  if (!isPlainObject(value) || !['file', 'directory', 'symlink'].includes(value.type)) {
    throw new Error(`${label} type is invalid.`);
  }
  const expectedKeys = value.type === 'symlink'
    ? ['type', 'hash', 'mode', 'link_target']
    : ['type', 'hash', 'mode'];
  assertExactObject(value, expectedKeys, label);
  assertSha256Digest(value.hash, `${label} hash`);
  if (value.type === 'symlink') {
    if (
      value.mode !== null
      || typeof value.link_target !== 'string'
      || value.link_target.length < 1
      || value.link_target.length > 4096
      || value.link_target.includes('\0')
    ) throw new Error(`${label} symlink metadata is invalid.`);
    return;
  }
  if (!Number.isInteger(value.mode) || value.mode < 0 || value.mode > 0o777) {
    throw new Error(`${label} file metadata is invalid.`);
  }
}

export function sameSetupSnapshot(actual, expected) {
  if (!actual || !expected) return actual === expected;
  return actual.type === expected.type
    && actual.hash === expected.hash
    && (actual.mode ?? null) === expected.mode
    && (actual.link_target ?? null) === (expected.link_target ?? null);
}
