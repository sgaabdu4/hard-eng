import { runSetup } from '../../scripts/setup.mjs';
import { makePluginClient } from './plugin-client-fixture.mjs';

const [sourceRoot, home, bundle, planDigest] = process.argv.slice(2);
runSetup(['rollback', '--home', home, '--backup', bundle, '--confirm', planDigest], {
  sourceRoot,
  now: Date.parse('2026-07-12T00:00:01.000Z'),
  pluginClient: makePluginClient({ installedHomes: [home] }),
  crashAfter: 2,
});
