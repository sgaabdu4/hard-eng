import path from 'node:path';
import { sha256 } from '../../plugins/hard-eng/runtime/lib/canonical.mjs';

export function makePluginClient({ installedHomes = [] } = {}) {
  const installed = new Map();
  function key(home) {
    return path.resolve(home);
  }
  for (const home of installedHomes) installed.set(key(home), true);
  function inspect(home) {
    const active = installed.get(key(home)) === true;
    return {
      status: active ? 'PASS' : 'FAIL',
      core: {
        installed: active,
        enabled: active,
        source_matches: active,
        version_matches: active,
        version: active ? '1.0.0' : null,
      },
      optional_packs: { discovered: 6, expected: 6, disabled: true },
      hooks_feature: true,
      conflicting_owners: 0,
      evidence_digest: sha256(`${key(home)}\0${active}`),
    };
  }
  function reconcile(home, desiredInstalled) {
    const before = installed.get(key(home)) === true;
    installed.set(key(home), desiredInstalled);
    return {
      status: 'PASS',
      action: desiredInstalled ? 'add' : 'remove',
      changed: before !== desiredInstalled,
      evidence_digest: sha256(`${key(home)}\0${before}\0${desiredInstalled}`),
    };
  }
  return { inspect, reconcile };
}
