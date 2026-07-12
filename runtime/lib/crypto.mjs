import { createHmac, randomBytes, timingSafeEqual } from 'node:crypto';
import { sha256 } from './canonical.mjs';

export function hmacHex(key, namespace, value) {
  return createHmac('sha256', key).update(namespace).update('\0').update(String(value)).digest('hex');
}

export function randomId(prefix = 'he') {
  return `${prefix}-${randomBytes(10).toString('hex')}`;
}

export function randomKey() {
  return randomBytes(32);
}

export function safeEqualHex(left, right) {
  if (typeof left !== 'string' || typeof right !== 'string') return false;
  if (!/^[a-f0-9]+$/i.test(left) || !/^[a-f0-9]+$/i.test(right) || left.length !== right.length) return false;
  return timingSafeEqual(Buffer.from(left, 'hex'), Buffer.from(right, 'hex'));
}

export function identityHash(value) {
  return sha256(value);
}
