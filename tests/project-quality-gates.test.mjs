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
assert.match(result.stderr, /\.no-mistakes\.yaml/);

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
write(path.join(reactGood, '.no-mistakes.yaml'), 'commands:\n  test: "npm test"\n  lint: "npm run qa"\n');
result = run(reactGood);
assert.equal(result.status, 0, result.stderr);
assert.match(result.stdout, /hooked scripts: qa/);
assert.match(result.stdout, /no-mistakes commands: test, lint/);

const reactWeakNoMistakes = path.join(tmp, 'react-weak-no-mistakes');
write(path.join(reactWeakNoMistakes, 'package.json'), `${JSON.stringify({
  private: true,
  dependencies: { react: '^19.0.0', typescript: '^5.0.0' },
  scripts: {
    qa: 'eslint . && tsc --noEmit && react-doctor --verbose --scope changed && fallow audit --base origin/main && fallow dupes --changed-since origin/main',
  },
}, null, 2)}\n`);
write(path.join(reactWeakNoMistakes, 'src', 'App.tsx'), 'export function App() { return null; }\n');
write(path.join(reactWeakNoMistakes, '.githooks', 'pre-push'), '#!/usr/bin/env sh\nnpm run qa\n', 0o755);
write(path.join(reactWeakNoMistakes, '.no-mistakes.yaml'), 'commands:\n  test: "npm test"\n  lint: "echo ok"\n');
result = run(reactWeakNoMistakes);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /\.no-mistakes\.yaml commands must run JS\/TS lint/);
assert.match(result.stderr, /\.no-mistakes\.yaml commands must run fallow audit or fallow dupes/);

const flutterMissing = path.join(tmp, 'flutter-missing');
write(path.join(flutterMissing, 'pubspec.yaml'), 'name: sample_app\ndependencies:\n  flutter:\n    sdk: flutter\n');
write(path.join(flutterMissing, 'lib', 'main.dart'), 'void main() {}\n');
write(path.join(flutterMissing, '.git-hooks', 'pre-push'), '#!/usr/bin/env sh\nflutter test\n', 0o755);
write(path.join(flutterMissing, '.no-mistakes.yaml'), 'commands:\n  test: "flutter test"\n  lint: "flutter test"\n');
result = run(flutterMissing);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /dart-decimate, dart analyze, or flutter analyze/);
assert.match(result.stderr, /flutter_skill_lints/);

const flutterGood = path.join(tmp, 'flutter-good');
write(path.join(flutterGood, 'pubspec.yaml'), 'name: sample_app\ndependencies:\n  flutter:\n    sdk: flutter\n');
write(path.join(flutterGood, 'analysis_options.yaml'), 'analyzer:\n  plugins:\n    - flutter_skill_lints\n');
write(path.join(flutterGood, 'lib', 'main.dart'), 'void main() {}\n');
write(path.join(flutterGood, 'test', 'main_test.dart'), 'void main() {}\n');
write(path.join(flutterGood, '.git-hooks', 'pre-push'), '#!/usr/bin/env sh\ndart analyze\nflutter test\n', 0o755);
write(path.join(flutterGood, '.no-mistakes.yaml'), 'commands:\n  test: "flutter test"\n  lint: "dart analyze && flutter test"\n');
result = run(flutterGood);
assert.equal(result.status, 0, result.stderr);

const hardEngGood = path.join(tmp, 'hard-eng-good');
write(path.join(hardEngGood, 'scripts', 'check-hard-eng-full-repo.mjs'), '#!/usr/bin/env node\n');
write(path.join(hardEngGood, 'skills', 'workflow-help', 'references', 'route-map.md'), '# route\n');
write(path.join(hardEngGood, '.git', 'hooks', 'pre-push'), '#!/usr/bin/env sh\nnode scripts/check-project-quality-gates.mjs --require-push-gate .\n', 0o755);
write(path.join(hardEngGood, '.no-mistakes.yaml'), 'commands:\n  test: "node scripts/check-hard-eng-full-repo.mjs"\n  lint: "node scripts/check-project-quality-gates.mjs --require-push-gate ."\n');
result = run(hardEngGood);
assert.equal(result.status, 0, result.stderr);

const hardEngWeakNoMistakes = path.join(tmp, 'hard-eng-weak-no-mistakes');
write(path.join(hardEngWeakNoMistakes, 'scripts', 'check-hard-eng-full-repo.mjs'), '#!/usr/bin/env node\n');
write(path.join(hardEngWeakNoMistakes, 'skills', 'workflow-help', 'references', 'route-map.md'), '# route\n');
write(path.join(hardEngWeakNoMistakes, '.git', 'hooks', 'pre-push'), '#!/usr/bin/env sh\nnode scripts/check-project-quality-gates.mjs --require-push-gate .\n', 0o755);
write(path.join(hardEngWeakNoMistakes, '.no-mistakes.yaml'), 'commands:\n  test: "node tests/unit.mjs"\n  lint: "node scripts/check-project-quality-gates.mjs --require-push-gate ."\n');
result = run(hardEngWeakNoMistakes);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /scripts\/check-hard-eng-full-repo\.mjs/);

console.log('project-quality-gates-test: pass');
