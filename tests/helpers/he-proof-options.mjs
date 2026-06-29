import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'he-state-proof-'));
export const emptyRepo = path.join(tmp, 'empty-repo');
fs.mkdirSync(emptyRepo);
const proofRepo = path.join(tmp, 'proof-repo');
fs.mkdirSync(path.join(proofRepo, 'tests'), { recursive: true });
fs.writeFileSync(path.join(proofRepo, 'tests', 'owner.test.mjs'), 'import "node:test";\n');

export const proofOptions = {
  root: proofRepo,
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
