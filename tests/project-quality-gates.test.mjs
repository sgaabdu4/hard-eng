#!/usr/bin/env node
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';

const repo = path.join(process.env.HOME, '.agents');
const script = path.join(repo, 'scripts', 'check-project-quality-gates.mjs');
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'project-quality-gates-'));

function write(file, text, mode) {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, text);
  if (mode) fs.chmodSync(file, mode);
}

function run(root, extra = []) {
  return spawnSync('node', [script, '--require-push-gate', root, ...extra], { encoding: 'utf8' });
}

const plain = path.join(tmp, 'plain');
fs.mkdirSync(plain);
let result = run(plain);
assert.equal(result.status, 0, result.stderr);
assert.match(result.stdout, /project-quality-gates: pass/);

const reactMissing = path.join(tmp, 'react-missing');
write(path.join(reactMissing, 'package.json'), `${JSON.stringify({
  private: true,
  dependencies: { react: '^19.0.0', typescript: '^5.0.0' },
}, null, 2)}\n`);
write(path.join(reactMissing, 'src', 'App.tsx'), 'export function App() { return null; }\n');
result = run(reactMissing);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /no pre-push gate evidence/);

const reactGood = path.join(tmp, 'react-good');
write(path.join(reactGood, 'package.json'), `${JSON.stringify({
  private: true,
  dependencies: { react: '^19.0.0', typescript: '^5.0.0' },
  scripts: {
    qa: 'eslint . && tsc --noEmit && react-doctor --verbose --scope changed && fallow audit --base origin/main && fallow dupes --changed-since origin/main',
  },
}, null, 2)}\n`);
write(path.join(reactGood, 'src', 'App.tsx'), 'export function App() { return null; }\n');
write(path.join(reactGood, '.githooks', 'pre-push'), '#!/usr/bin/env sh\nnpm run qa\n', 0o755);
result = run(reactGood);
assert.equal(result.status, 0, result.stderr);
assert.match(result.stdout, /hooked scripts: qa/);

const flutterMissing = path.join(tmp, 'flutter-missing');
write(path.join(flutterMissing, 'pubspec.yaml'), 'name: sample_app\ndependencies:\n  flutter:\n    sdk: flutter\n');
write(path.join(flutterMissing, 'lib', 'main.dart'), 'void main() {}\n');
write(path.join(flutterMissing, '.git-hooks', 'pre-push'), '#!/usr/bin/env sh\nflutter test\n', 0o755);
result = run(flutterMissing);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /dart analyze/);
assert.match(result.stderr, /flutter_skill_lints/);

const flutterGood = path.join(tmp, 'flutter-good');
write(path.join(flutterGood, 'pubspec.yaml'), 'name: sample_app\ndependencies:\n  flutter:\n    sdk: flutter\n');
write(path.join(flutterGood, 'analysis_options.yaml'), 'analyzer:\n  plugins:\n    - flutter_skill_lints\n');
write(path.join(flutterGood, 'lib', 'main.dart'), 'void main() {}\n');
write(path.join(flutterGood, 'test', 'main_test.dart'), 'void main() {}\n');
write(path.join(flutterGood, '.git-hooks', 'pre-push'), '#!/usr/bin/env sh\ndart analyze\nflutter test\n', 0o755);
result = run(flutterGood);
assert.equal(result.status, 0, result.stderr);

console.log('project-quality-gates-test: pass');
