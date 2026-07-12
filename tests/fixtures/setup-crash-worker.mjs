import { runSetup } from '../../scripts/setup.mjs';
import { makeWiringClient } from './wiring-client-fixture.mjs';

const [sourceRoot, home, planDigest] = process.argv.slice(2);
runSetup(['install', '--home', home, '--confirm', planDigest], {
  sourceRoot,
  now: Date.parse('2026-07-12T00:00:00.000Z'),
  wiringClient: makeWiringClient(),
  crashAfter: 2,
});
