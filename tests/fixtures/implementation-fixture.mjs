export function implementationReceipt(character = 'f', overrides = {}) {
  return {
    owner_digest: character.repeat(64),
    strategy: 'root-fix',
    wrapper: 'none',
    legacy: 'none',
    blast_radius_digest: character.repeat(64),
    ...overrides,
  };
}
