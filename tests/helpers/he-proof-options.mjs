import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'he-state-proof-'));
export const emptyRepo = path.join(tmp, 'empty-repo');
fs.mkdirSync(emptyRepo);

export const proofOptions = {
  root: emptyRepo,
  proofStacks: ['js-package', 'node', 'python', 'gradle', 'maven', 'go', 'cargo', 'dart-flutter', 'make', 'mutation'],
  packageScripts: {
    test: 'node --test tests/owner.test.mjs',
    'test:unit': 'node --test tests/unit.test.mjs',
    jest: 'jest',
    vitest: 'vitest',
    mutation: 'stryker run',
    'make-it-fail': 'node --test tests/make-it-fail.test.mjs',
  },
};
