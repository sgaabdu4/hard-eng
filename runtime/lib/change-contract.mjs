function assertDigest(value, label) {
  if (!/^[a-f0-9]{64}$/i.test(value ?? '')) throw new Error(`${label} must be a SHA-256 digest.`);
}

export function validateImplementationReceipt(receipt) {
  if (!receipt || typeof receipt !== 'object' || Array.isArray(receipt)) {
    throw new Error('Implementation requires a root-owner and blast-radius receipt.');
  }
  const expected = ['blast_radius_digest', 'legacy', 'owner_digest', 'strategy', 'wrapper'];
  if (JSON.stringify(Object.keys(receipt).sort()) !== JSON.stringify(expected)) {
    throw new Error('Implementation root-owner receipt shape is invalid.');
  }
  assertDigest(receipt.owner_digest, 'Implementation root owner');
  assertDigest(receipt.blast_radius_digest, 'Implementation blast radius');
  if (!['root-fix', 'full-migration'].includes(receipt.strategy)) {
    throw new Error('Implementation strategy must fix the root owner or complete a full migration.');
  }
  if (receipt.wrapper !== 'none') throw new Error('Implementation cannot introduce a pass-through wrapper.');
  if (receipt.legacy !== 'none') throw new Error('Implementation cannot leave a legacy or parallel runtime owner.');
  return receipt;
}
