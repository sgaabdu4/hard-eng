import path from 'node:path';
import { createHash } from 'node:crypto';

export function isPlainObject(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

export function canonicalValue(value) {
  if (Array.isArray(value)) return value.map(canonicalValue);
  if (!isPlainObject(value)) return value;
  return Object.fromEntries(
    Object.keys(value).sort().map((key) => [key, canonicalValue(value[key])]),
  );
}

export function canonicalJson(value) {
  return JSON.stringify(canonicalValue(value));
}

export function sha256(value) {
  const input = Buffer.isBuffer(value) ? value : Buffer.from(String(value));
  return createHash('sha256').update(input).digest('hex');
}

export function digestValue(value) {
  return sha256(canonicalJson(value));
}

export function clone(value) {
  return structuredClone(value);
}

const absoluteHomePath = /^(?:\/Users\/|\/home\/|\/private\/|\/tmp\/|\/var\/|[A-Za-z]:[\\/])/;

export function findAbsolutePath(value, trail = []) {
  if (typeof value === 'string') {
    if (absoluteHomePath.test(value) || (path.isAbsolute(value) && trail.at(-1)?.match(/(?:path|root|dir)$/i))) {
      return { trail, value };
    }
    return null;
  }
  if (Array.isArray(value)) {
    for (let index = 0; index < value.length; index += 1) {
      const found = findAbsolutePath(value[index], [...trail, String(index)]);
      if (found) return found;
    }
    return null;
  }
  if (isPlainObject(value)) {
    for (const [key, child] of Object.entries(value)) {
      const found = findAbsolutePath(child, [...trail, key]);
      if (found) return found;
    }
  }
  return null;
}

export function assertNoAbsolutePaths(value) {
  const found = findAbsolutePath(value);
  if (found) throw new Error(`Checkpoint contains an absolute path at ${found.trail.join('.') || '<root>'}.`);
}
