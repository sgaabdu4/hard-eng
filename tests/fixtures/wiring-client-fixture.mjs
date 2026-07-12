import path from 'node:path';
import { sha256 } from '../../runtime/lib/canonical.mjs';

export function makeWiringClient({ configuredHomes = [] } = {}) {
  const configured = new Map();
  const key = (home) => path.resolve(home);
  for (const home of configuredHomes) configured.set(key(home), true);

  function inspect(home) {
    const active = configured.get(key(home)) === true;
    return {
      status: active ? 'PASS' : 'NOT_CONFIGURED',
      configured: active,
      owned: active,
      enabled: active,
      transport_type: active ? 'stdio' : null,
      evidence_digest: sha256(`${key(home)}\0${active}`),
    };
  }

  function reconcile(home, desiredConfigured) {
    const before = configured.get(key(home)) === true;
    configured.set(key(home), desiredConfigured);
    return {
      status: 'PASS',
      action: before === desiredConfigured ? 'none' : desiredConfigured ? 'add' : 'remove',
      changed: before !== desiredConfigured,
      evidence_digest: sha256(`${key(home)}\0${before}\0${desiredConfigured}`),
    };
  }

  return { inspect, reconcile };
}
