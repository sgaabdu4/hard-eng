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

const tmpProjectNoise = path.join(tmp, 'tmp-project-noise');
write(path.join(tmpProjectNoise, 'tmp', 'stale-review', 'pubspec.yaml'), 'name: stale_review\n');
write(path.join(tmpProjectNoise, 'tmp', 'stale-review', 'bin', 'main.dart'), 'void main() {}\n');
write(path.join(tmpProjectNoise, 'tmp', 'stale-repo', '.git', 'HEAD'), 'ref: refs/heads/main\n');
result = run(tmpProjectNoise, ['--json']);
assert.equal(result.status, 0, result.stderr);
let payload = JSON.parse(result.stdout);
assert.deepEqual(payload.projectRoots, []);
assert.deepEqual(payload.unmanagedNestedGitRepos, []);

const unmanagedNestedRepo = path.join(tmp, 'unmanaged-nested-repo');
write(path.join(unmanagedNestedRepo, 'external', 'checkout', '.git', 'HEAD'), 'ref: refs/heads/main\n');
write(path.join(unmanagedNestedRepo, 'external', 'checkout', 'pyproject.toml'), '[project]\nname = "external"\n');
result = run(unmanagedNestedRepo, ['--json']);
assert.notEqual(result.status, 0);
payload = JSON.parse(result.stdout);
assert.deepEqual(payload.projectRoots, []);
assert.deepEqual(payload.unmanagedNestedGitRepos, ['external/checkout']);
assert.ok(payload.blockers.some((blocker) => /unmanaged nested Git repo external\/checkout/.test(blocker)));

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

const pythonMissingPyrefly = path.join(tmp, 'python-missing-pyrefly');
write(path.join(pythonMissingPyrefly, 'pyproject.toml'), '[project]\nname = "sample"\n');
write(path.join(pythonMissingPyrefly, 'src', 'app.py'), 'def main() -> None:\n    pass\n');
write(path.join(pythonMissingPyrefly, 'tests', 'test_app.py'), 'def test_app():\n    assert True\n');
write(path.join(pythonMissingPyrefly, '.githooks', 'pre-push'), '#!/usr/bin/env sh\npytest\n', 0o755);
write(path.join(pythonMissingPyrefly, '.no-mistakes.yaml'), 'commands:\n  test: "pytest"\n  lint: "ruff check ."\n');
result = run(pythonMissingPyrefly);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /pyrefly check/);
assert.match(result.stderr, /\.no-mistakes\.yaml commands\.lint must run pyrefly check/);

const pythonGood = path.join(tmp, 'python-good');
write(path.join(pythonGood, 'pyproject.toml'), '[project]\nname = "sample"\n');
write(path.join(pythonGood, 'src', 'app.py'), 'def main() -> None:\n    pass\n');
write(path.join(pythonGood, 'tests', 'test_app.py'), 'def test_app():\n    assert True\n');
write(path.join(pythonGood, '.githooks', 'pre-push'), '#!/usr/bin/env sh\npyrefly check --summarize-errors\npython -m pytest\n', 0o755);
write(path.join(pythonGood, '.no-mistakes.yaml'), 'commands:\n  test: "python -m pytest"\n  lint: "pyrefly check --summarize-errors && ruff check ."\n');
result = run(pythonGood);
assert.equal(result.status, 0, result.stderr);

const pythonScannerMissing = path.join(tmp, 'python-scanner-missing');
write(path.join(pythonScannerMissing, 'pyproject.toml'), '[project]\nname = "sample"\n');
write(path.join(pythonScannerMissing, 'src', 'app.py'), 'def main() -> None:\n    pass\n');
write(path.join(pythonScannerMissing, 'tests', 'test_app.py'), 'def test_app():\n    assert True\n');
write(path.join(pythonScannerMissing, 'scripts', 'check-domain-rules.mjs'), '#!/usr/bin/env node\n');
write(path.join(pythonScannerMissing, '.githooks', 'pre-push'), '#!/usr/bin/env sh\npyrefly check\npytest\n', 0o755);
write(path.join(pythonScannerMissing, '.no-mistakes.yaml'), 'commands:\n  test: "pytest"\n  lint: "pyrefly check && ruff check ."\n');
result = run(pythonScannerMissing);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /must run repo scanner scripts\/check-domain-rules\.mjs/);

const pythonScannerGood = path.join(tmp, 'python-scanner-good');
write(path.join(pythonScannerGood, 'pyproject.toml'), '[project]\nname = "sample"\n');
write(path.join(pythonScannerGood, 'src', 'app.py'), 'def main() -> None:\n    pass\n');
write(path.join(pythonScannerGood, 'tests', 'test_app.py'), 'def test_app():\n    assert True\n');
write(path.join(pythonScannerGood, 'scripts', 'check-domain-rules.mjs'), '#!/usr/bin/env node\n');
write(path.join(pythonScannerGood, '.githooks', 'pre-push'), '#!/usr/bin/env sh\npyrefly check\npytest\n', 0o755);
write(path.join(pythonScannerGood, '.no-mistakes.yaml'), 'commands:\n  test: "pytest"\n  lint: "pyrefly check && ruff check . && node scripts/check-domain-rules.mjs ."\n');
result = run(pythonScannerGood);
assert.equal(result.status, 0, result.stderr);

const dartFunctionsMissingRoot = path.join(tmp, 'dart-functions-missing-root');
for (const fn of ['send-email', 'sync-user']) {
  write(path.join(dartFunctionsMissingRoot, 'functions', fn, 'pubspec.yaml'), `name: ${fn.replace('-', '_')}\n`);
  write(path.join(dartFunctionsMissingRoot, 'functions', fn, 'bin', 'main.dart'), 'void main() {}\n');
  write(path.join(dartFunctionsMissingRoot, 'functions', fn, 'test', 'main_test.dart'), 'void main() {}\n');
}
write(path.join(dartFunctionsMissingRoot, '.githooks', 'pre-push'), '#!/usr/bin/env sh\ncd functions/send-email && dart analyze && dart test\n', 0o755);
write(path.join(dartFunctionsMissingRoot, '.no-mistakes.yaml'), 'commands:\n  test: "cd functions/send-email && dart test"\n  lint: "cd functions/send-email && dart analyze"\n');
result = run(dartFunctionsMissingRoot);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /must cover dart project root functions\/sync-user/);

const dartFunctionsGood = path.join(tmp, 'dart-functions-good');
for (const fn of ['send-email', 'sync-user']) {
  write(path.join(dartFunctionsGood, 'functions', fn, 'pubspec.yaml'), `name: ${fn.replace('-', '_')}\n`);
  write(path.join(dartFunctionsGood, 'functions', fn, 'bin', 'main.dart'), 'void main() {}\n');
  write(path.join(dartFunctionsGood, 'functions', fn, 'test', 'main_test.dart'), 'void main() {}\n');
}
write(path.join(dartFunctionsGood, '.githooks', 'pre-push'), '#!/usr/bin/env sh\nfor dir in functions/send-email functions/sync-user; do (cd "$dir" && dart analyze && dart test); done\n', 0o755);
write(path.join(dartFunctionsGood, '.no-mistakes.yaml'), 'commands:\n  test: "for dir in functions/send-email functions/sync-user; do (cd \\"$dir\\" && dart test); done"\n  lint: "for dir in functions/send-email functions/sync-user; do (cd \\"$dir\\" && dart analyze); done"\n');
result = run(dartFunctionsGood);
assert.equal(result.status, 0, result.stderr);

const goMultiMissingRoot = path.join(tmp, 'go-multi-missing-root');
for (const mod of ['services/api', 'libs/core']) {
  write(path.join(goMultiMissingRoot, mod, 'go.mod'), `module example.com/${mod.replace('/', '-')}\n\ngo 1.22\n`);
  write(path.join(goMultiMissingRoot, mod, 'main.go'), 'package main\n');
  write(path.join(goMultiMissingRoot, mod, 'main_test.go'), 'package main\n\nimport "testing"\n\nfunc TestMain(t *testing.T) {}\n');
}
write(path.join(goMultiMissingRoot, '.githooks', 'pre-push'), '#!/usr/bin/env sh\ncd services/api && go test ./...\n', 0o755);
write(path.join(goMultiMissingRoot, '.no-mistakes.yaml'), 'commands:\n  test: "cd services/api && go test ./..."\n  lint: "cd services/api && go test ./..."\n');
result = run(goMultiMissingRoot);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /must cover go project root libs\/core/);

const goMultiGood = path.join(tmp, 'go-multi-good');
for (const mod of ['services/api', 'libs/core']) {
  write(path.join(goMultiGood, mod, 'go.mod'), `module example.com/${mod.replace('/', '-')}\n\ngo 1.22\n`);
  write(path.join(goMultiGood, mod, 'main.go'), 'package main\n');
  write(path.join(goMultiGood, mod, 'main_test.go'), 'package main\n\nimport "testing"\n\nfunc TestMain(t *testing.T) {}\n');
}
write(path.join(goMultiGood, '.githooks', 'pre-push'), '#!/usr/bin/env sh\nfor dir in services/api libs/core; do (cd "$dir" && go test ./...); done\n', 0o755);
write(path.join(goMultiGood, '.no-mistakes.yaml'), 'commands:\n  test: "for dir in services/api libs/core; do (cd \\"$dir\\" && go test ./...); done"\n  lint: "for dir in services/api libs/core; do (cd \\"$dir\\" && go test ./...); done"\n');
result = run(goMultiGood);
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
