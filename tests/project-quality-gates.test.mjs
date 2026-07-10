#!/usr/bin/env node
// HARD_ENG_LARGE_OWNER: dense project quality behavior tests with focused coverage.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const repo = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
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

function writeJsGate(root, options = {}) {
  const test = options.test || 'vitest run';
  const lint = options.lint || 'eslint . && tsc --noEmit && fallow audit && fallow dupes';
  const format = options.format || 'prettier --write .';
  const dependencies = options.react
    ? { react: '^19.0.0', typescript: '^5.0.0' }
    : { typescript: '^5.0.0' };
  write(path.join(root, 'package.json'), `${JSON.stringify({ private: true, dependencies }, null, 2)}\n`);
  write(path.join(root, 'src', options.react ? 'App.tsx' : 'index.ts'), 'export const value = 1;\n');
  write(path.join(root, 'test', 'index.test.ts'), 'export const tested = true;\n');
  write(path.join(root, '.githooks', 'pre-push'), `#!/usr/bin/env sh\nset -eu\n${options.hookTest || 'vitest run'}\n${options.hookLint || (options.react ? 'eslint . && tsc --noEmit && react-doctor --verbose && fallow audit && fallow dupes' : 'eslint . && tsc --noEmit && fallow audit && fallow dupes')}\n`, 0o755);
  write(path.join(root, '.no-mistakes.yaml'), `commands:\n  test: ${JSON.stringify(test)}\n  lint: ${JSON.stringify(lint)}\n  format: ${JSON.stringify(format)}\n`);
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

const deepInventory = path.join(tmp, 'deep-inventory');
write(path.join(deepInventory, 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'package.json'), '{"private":true}\n');
result = run(deepInventory, ['--json']);
assert.notEqual(result.status, 0);
payload = JSON.parse(result.stdout);
assert.ok(payload.blockers.some((blocker) => /project file inventory truncated at depth/.test(blocker)));

const unmanagedNestedRepo = path.join(tmp, 'unmanaged-nested-repo');
write(path.join(unmanagedNestedRepo, 'external', 'checkout', '.git', 'HEAD'), 'ref: refs/heads/main\n');
write(path.join(unmanagedNestedRepo, 'external', 'checkout', 'pyproject.toml'), '[project]\nname = "external"\n');
result = run(unmanagedNestedRepo, ['--json']);
assert.notEqual(result.status, 0);
payload = JSON.parse(result.stdout);
assert.deepEqual(payload.projectRoots, []);
assert.deepEqual(payload.unmanagedNestedGitRepos, ['external/checkout']);
assert.ok(payload.blockers.some((blocker) => /unmanaged nested Git repo external\/checkout/.test(blocker)));

const configuredNestedRepo = path.join(tmp, 'configured-nested-repo');
write(path.join(configuredNestedRepo, 'external', 'checkout', '.git', 'HEAD'), 'ref: refs/heads/main\n');
write(path.join(configuredNestedRepo, 'external', 'checkout', '.no-mistakes.yaml'), 'commands:\n  test: "echo test"\n  lint: "echo lint"\n  format: "echo format"\n');
write(path.join(configuredNestedRepo, 'external', 'checkout', 'pyproject.toml'), '[project]\nname = "external"\n');
result = run(configuredNestedRepo, ['--json']);
assert.equal(result.status, 0, result.stderr);
payload = JSON.parse(result.stdout);
assert.deepEqual(payload.projectRoots, []);
assert.deepEqual(payload.configuredNestedGitRepos, ['external/checkout']);
assert.deepEqual(payload.unmanagedNestedGitRepos, []);

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
    test: 'vitest run',
    qa: 'eslint . && tsc --noEmit && react-doctor --verbose --scope changed && fallow audit --base origin/main && fallow dupes --changed-since origin/main',
  },
}, null, 2)}\n`);
write(path.join(reactGood, 'src', 'App.tsx'), 'export function App() { return null; }\n');
write(path.join(reactGood, '.githooks', 'pre-push'), '#!/usr/bin/env sh\nnpm run qa\n', 0o755);
write(path.join(reactGood, '.no-mistakes.yaml'), 'commands:\n  test: "npm test"\n  lint: "npm run qa"\n  format: "prettier --write ."\n');
result = run(reactGood);
assert.equal(result.status, 0, result.stderr);
assert.match(result.stdout, /hooked scripts: qa/);
assert.match(result.stdout, /no-mistakes commands: test, lint, format/);

const reactNoopPackageTest = path.join(tmp, 'react-noop-package-test');
write(path.join(reactNoopPackageTest, 'package.json'), `${JSON.stringify({
  private: true,
  dependencies: { react: '^19.0.0', typescript: '^5.0.0' },
  scripts: {
    test: 'echo ok',
    qa: 'eslint . && tsc --noEmit && react-doctor --verbose --scope changed && fallow audit && fallow dupes',
  },
}, null, 2)}\n`);
write(path.join(reactNoopPackageTest, 'src', 'App.tsx'), 'export function App() { return null; }\n');
write(path.join(reactNoopPackageTest, 'test', 'App.test.ts'), 'export const tested = true;\n');
write(path.join(reactNoopPackageTest, '.githooks', 'pre-push'), '#!/usr/bin/env sh\nnpm run qa\n', 0o755);
write(path.join(reactNoopPackageTest, '.no-mistakes.yaml'), 'commands:\n  test: "npm test"\n  lint: "npm run qa"\n  format: "prettier --write ."\n');
result = run(reactNoopPackageTest);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /commands\.test must run deterministic js-ts tests/i);

const packageReferenceEchoSpoof = path.join(tmp, 'package-reference-echo-spoof');
write(path.join(packageReferenceEchoSpoof, 'package.json'), `${JSON.stringify({
  private: true,
  dependencies: { typescript: '^5.0.0' },
  scripts: {
    test: 'vitest run',
    qa: 'eslint . && tsc --noEmit && fallow audit && fallow dupes',
    format: 'echo "npm run mutate"',
    mutate: 'prettier --write .',
  },
}, null, 2)}\n`);
write(path.join(packageReferenceEchoSpoof, 'src', 'index.ts'), 'export const value = 1;\n');
write(path.join(packageReferenceEchoSpoof, 'test', 'index.test.ts'), 'export const tested = true;\n');
write(path.join(packageReferenceEchoSpoof, '.githooks', 'pre-push'), '#!/usr/bin/env sh\nnpm test && npm run qa\n', 0o755);
write(path.join(packageReferenceEchoSpoof, '.no-mistakes.yaml'), 'commands:\n  test: "npm test"\n  lint: "npm run qa"\n  format: "npm run format"\n');
result = run(packageReferenceEchoSpoof);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /commands\.format must run a deterministic JS\/TS formatter/);

const passiveJsRoles = path.join(tmp, 'passive-js-roles');
write(path.join(passiveJsRoles, 'package.json'), `${JSON.stringify({
  private: true,
  dependencies: { typescript: '^5.0.0' },
}, null, 2)}\n`);
write(path.join(passiveJsRoles, 'src', 'index.ts'), 'export const value = 1;\n');
write(path.join(passiveJsRoles, 'test', 'index.test.ts'), 'export const tested = true;\n');
const passiveJsCommand = 'vitest --list && eslint --version && tsc --noEmit && fallow audit && fallow dupes';
write(path.join(passiveJsRoles, '.githooks', 'pre-push'), `#!/usr/bin/env sh\n${passiveJsCommand}\n`, 0o755);
write(path.join(passiveJsRoles, '.no-mistakes.yaml'), `commands:\n  test: "vitest --list"\n  lint: "eslint --version && tsc --noEmit && fallow audit && fallow dupes"\n  format: "prettier --write ."\n`);
result = run(passiveJsRoles);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /commands\.(?:test must run deterministic js-ts tests|lint must run JS\/TS lint)/i);

for (const [fixtureName, testCommand] of [
  ['test-after-exit', 'exit 0; vitest run'],
  ['test-inside-false-if', 'if false; then vitest run; fi'],
]) {
  const controlFlowSpoof = path.join(tmp, fixtureName);
  writeJsGate(controlFlowSpoof, { test: testCommand });
  result = run(controlFlowSpoof);
  assert.notEqual(result.status, 0, testCommand);
  assert.match(result.stderr, /commands\.test must run deterministic js-ts tests/i);
}

const swallowedLintFailure = path.join(tmp, 'swallowed-lint-failure');
writeJsGate(swallowedLintFailure, {
  lint: 'eslint . || true; tsc --noEmit && fallow audit && fallow dupes',
});
result = run(swallowedLintFailure);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /commands\.lint must run JS\/TS lint/i);

for (const [fixtureName, lint] of [
  ['errexit-after-lint', 'eslint .; set -e; tsc --noEmit && fallow audit && fallow dupes'],
  ['errexit-disabled-before-lint', 'set -e; set +e; eslint .; true; tsc --noEmit && fallow audit && fallow dupes'],
  ['errexit-in-subshell', '(set -e); eslint .; true; tsc --noEmit && fallow audit && fallow dupes'],
]) {
  const failFastSpoof = path.join(tmp, fixtureName);
  writeJsGate(failFastSpoof, { lint });
  result = run(failFastSpoof);
  assert.notEqual(result.status, 0, lint);
  assert.match(result.stderr, /commands\.lint must run JS\/TS lint/i);
}

const passiveAuxTools = path.join(tmp, 'passive-aux-tools');
writeJsGate(passiveAuxTools, {
  react: true,
  lint: 'eslint . && tsc --version && fallow audit --help && react-doctor --version',
});
result = run(passiveAuxTools);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /commands\.lint must run (?:TypeScript typecheck|fallow audit|react-doctor)/i);

for (const [fixtureName, typecheck] of [
  ['tsc-init', 'tsc --init'],
  ['tsc-show-config', 'tsc --showConfig'],
  ['tsc-clean-build', 'tsc --build --clean'],
]) {
  const passiveTypecheck = path.join(tmp, fixtureName);
  writeJsGate(passiveTypecheck, {
    lint: `eslint . && ${typecheck} && fallow audit && fallow dupes`,
  });
  result = run(passiveTypecheck);
  assert.notEqual(result.status, 0, typecheck);
  assert.match(result.stderr, /commands\.lint must run TypeScript typecheck or tsc/i);
}

for (const [fixtureName, formatCommand] of [
  ['format-echo-spoof', 'echo "prettier --write ."'],
  ['format-comment-spoof', '# prettier --write .\necho no-format'],
  ['format-false-branch-spoof', 'false && prettier --write .'],
  ['format-true-fallback-spoof', 'true || prettier --write .'],
  ['format-prettier-check', 'prettier --check .'],
  ['format-prettier-version', 'prettier --version'],
  ['format-biome-check', 'biome check .'],
  ['format-dprint-check', 'dprint check'],
]) {
  const formatSpoof = path.join(tmp, fixtureName);
  write(path.join(formatSpoof, 'package.json'), `${JSON.stringify({
    private: true,
    dependencies: { typescript: '^5.0.0' },
    scripts: {
      qa: 'eslint . && tsc --noEmit && fallow audit && fallow dupes',
    },
  }, null, 2)}\n`);
  write(path.join(formatSpoof, 'src', 'index.ts'), 'export const value = 1;\n');
  write(path.join(formatSpoof, '.githooks', 'pre-push'), '#!/usr/bin/env sh\nnpm run qa\n', 0o755);
  write(path.join(formatSpoof, '.no-mistakes.yaml'), `commands:\n  test: "npm test"\n  lint: "npm run qa"\n  format: >-\n    ${formatCommand.replaceAll('\n', '\n    ')}\n`);
  result = run(formatSpoof);
  assert.notEqual(result.status, 0, formatCommand);
  assert.match(result.stderr, /commands\.format must run a deterministic JS\/TS formatter/);
}

for (const [fixtureName, indent] of [['folded-format-spoof', '    '], ['folded-format-deep-indent-spoof', '      ']]) {
  const foldedFormatSpoof = path.join(tmp, fixtureName);
  writeJsGate(foldedFormatSpoof);
  write(path.join(foldedFormatSpoof, '.no-mistakes.yaml'), `commands:\n  test: "vitest run"\n  lint: "eslint . && tsc --noEmit && fallow audit && fallow dupes"\n  format: >-\n${indent}echo setup\n${indent}prettier --write .\n`);
  result = run(foldedFormatSpoof);
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /commands\.format must run a deterministic JS\/TS formatter/);
}

const pythonPassiveTest = path.join(tmp, 'python-passive-test');
write(path.join(pythonPassiveTest, 'pyproject.toml'), '[project]\nname = "passive"\n');
write(path.join(pythonPassiveTest, 'src', 'app.py'), 'def main() -> None:\n    pass\n');
write(path.join(pythonPassiveTest, 'tests', 'test_app.py'), 'def test_app():\n    assert True\n');
write(path.join(pythonPassiveTest, '.githooks', 'pre-push'), '#!/usr/bin/env sh\npytest --collect-only && pyrefly check\n', 0o755);
write(path.join(pythonPassiveTest, '.no-mistakes.yaml'), 'commands:\n  test: "pytest --collect-only"\n  lint: "pyrefly check"\n  format: "ruff format ."\n');
result = run(pythonPassiveTest);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /commands\.test must run deterministic python tests/);

const pythonCheckOnlyFormat = path.join(tmp, 'python-check-only-format');
write(path.join(pythonCheckOnlyFormat, 'pyproject.toml'), '[project]\nname = "format_check"\n');
write(path.join(pythonCheckOnlyFormat, 'src', 'app.py'), 'def main() -> None:\n    pass\n');
write(path.join(pythonCheckOnlyFormat, 'tests', 'test_app.py'), 'def test_app():\n    assert True\n');
write(path.join(pythonCheckOnlyFormat, '.githooks', 'pre-push'), '#!/usr/bin/env sh\npytest && pyrefly check\n', 0o755);
write(path.join(pythonCheckOnlyFormat, '.no-mistakes.yaml'), 'commands:\n  test: "pytest"\n  lint: "pyrefly check"\n  format: "ruff format --check ."\n');
result = run(pythonCheckOnlyFormat);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /commands\.format must run a deterministic Python formatter/);

const unreachablePackageReference = path.join(tmp, 'unreachable-package-reference');
write(path.join(unreachablePackageReference, 'package.json'), `${JSON.stringify({
  private: true,
  dependencies: { typescript: '^5.0.0' },
  scripts: {
    test: 'vitest run',
    qa: 'eslint . && tsc --noEmit && fallow audit && fallow dupes',
    format: 'false && npm run mutate',
    mutate: 'prettier --write .',
  },
}, null, 2)}\n`);
write(path.join(unreachablePackageReference, 'src', 'index.ts'), 'export const value = 1;\n');
write(path.join(unreachablePackageReference, 'test', 'index.test.ts'), 'export const tested = true;\n');
write(path.join(unreachablePackageReference, '.githooks', 'pre-push'), '#!/usr/bin/env sh\nnpm test && npm run qa\n', 0o755);
write(path.join(unreachablePackageReference, '.no-mistakes.yaml'), 'commands:\n  test: "npm test"\n  lint: "npm run qa"\n  format: "npm run format"\n');
result = run(unreachablePackageReference);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /commands\.format must run a deterministic JS\/TS formatter/);

for (const [fixtureName, formatCommand] of [
  ['python-autopep8-output-only', 'autopep8 .'],
  ['python-yapf-output-only', 'yapf .'],
  ['python-black-code-output-only', 'black --code "value=1"'],
]) {
  const pythonOutputOnlyFormat = path.join(tmp, fixtureName);
  write(path.join(pythonOutputOnlyFormat, 'pyproject.toml'), '[project]\nname = "output_only"\n');
  write(path.join(pythonOutputOnlyFormat, 'src', 'app.py'), 'def main() -> None:\n    pass\n');
  write(path.join(pythonOutputOnlyFormat, 'tests', 'test_app.py'), 'def test_app():\n    assert True\n');
  write(path.join(pythonOutputOnlyFormat, '.githooks', 'pre-push'), '#!/usr/bin/env sh\npytest && pyrefly check\n', 0o755);
  write(path.join(pythonOutputOnlyFormat, '.no-mistakes.yaml'), `commands:\n  test: "pytest"\n  lint: "pyrefly check"\n  format: '${formatCommand}'\n`);
  result = run(pythonOutputOnlyFormat);
  assert.notEqual(result.status, 0, formatCommand);
  assert.match(result.stderr, /commands\.format must run a deterministic Python formatter/);
}

const monorepoLintRoleSpoof = path.join(tmp, 'monorepo-lint-role-spoof');
write(path.join(monorepoLintRoleSpoof, 'package.json'), `${JSON.stringify({
  private: true,
  dependencies: { typescript: '^5.0.0' },
}, null, 2)}\n`);
for (const [name, rootDir] of [['@sample/app', 'packages/app'], ['@sample/lib', 'packages/lib']]) {
  write(path.join(monorepoLintRoleSpoof, rootDir, 'package.json'), `${JSON.stringify({ name }, null, 2)}\n`);
  write(path.join(monorepoLintRoleSpoof, rootDir, 'src', 'index.ts'), 'export const value = 1;\n');
  write(path.join(monorepoLintRoleSpoof, rootDir, 'test', 'index.test.ts'), 'export const tested = true;\n');
}
const leakedLintTools = 'vitest run packages/app packages/lib && eslint packages/app packages/lib && tsc --noEmit && fallow audit && fallow dupes';
write(path.join(monorepoLintRoleSpoof, '.githooks', 'pre-push'), `#!/usr/bin/env sh\n${leakedLintTools}\n`, 0o755);
write(path.join(monorepoLintRoleSpoof, '.no-mistakes.yaml'), `commands:\n  test: "${leakedLintTools}"\n  lint: "echo packages/app packages/lib"\n  format: "prettier --write ."\n`);
result = run(monorepoLintRoleSpoof);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /commands\.lint must run JS\/TS lint/);
write(path.join(monorepoLintRoleSpoof, '.no-mistakes.yaml'), `commands:\n  test: "${leakedLintTools}"\n  lint: "npm exec echo eslint packages/app packages/lib"\n  format: "prettier --write ."\n`);
result = run(monorepoLintRoleSpoof);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /commands\.lint must run JS\/TS lint/);

const monorepoRootFormatFalsePositive = path.join(tmp, 'monorepo-root-format-false-positive');
write(path.join(monorepoRootFormatFalsePositive, 'package.json'), `${JSON.stringify({
  private: true,
  dependencies: { typescript: '^5.0.0' },
  scripts: {
    qa: 'eslint . packages/app && tsc --noEmit && fallow audit && fallow dupes',
  },
}, null, 2)}\n`);
write(path.join(monorepoRootFormatFalsePositive, 'packages', 'app', 'package.json'), `${JSON.stringify({
  name: '@sample/app',
  scripts: {
    format: 'prettier --write packages/app',
  },
}, null, 2)}\n`);
write(path.join(monorepoRootFormatFalsePositive, 'packages', 'app', 'src', 'index.ts'), 'export const value = 1;\n');
write(path.join(monorepoRootFormatFalsePositive, '.githooks', 'pre-push'), '#!/usr/bin/env sh\nnpm run qa\n', 0o755);
write(path.join(monorepoRootFormatFalsePositive, '.no-mistakes.yaml'), 'commands:\n  test: "npm test"\n  lint: "npm run qa"\n  format: "npm run format"\n');
result = run(monorepoRootFormatFalsePositive);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /\.no-mistakes\.yaml commands\.format must run a deterministic JS\/TS formatter/);

const monorepoRecursiveFormat = path.join(tmp, 'monorepo-recursive-format');
write(path.join(monorepoRecursiveFormat, 'package.json'), `${JSON.stringify({
  private: true,
  workspaces: ['packages/*'],
  dependencies: { typescript: '^5.0.0' },
  scripts: {
    qa: 'eslint . packages/app && tsc --noEmit && fallow audit && fallow dupes',
    format: 'prettier --write package.json && pnpm -r run format',
  },
}, null, 2)}\n`);
write(path.join(monorepoRecursiveFormat, 'packages', 'app', 'package.json'), `${JSON.stringify({
  name: '@sample/app',
  scripts: {
    format: 'prettier --write packages/app',
  },
}, null, 2)}\n`);
write(path.join(monorepoRecursiveFormat, 'packages', 'app', 'src', 'index.ts'), 'export const value = 1;\n');
write(path.join(monorepoRecursiveFormat, '.githooks', 'pre-push'), '#!/usr/bin/env sh\nnpm run qa\n', 0o755);
write(path.join(monorepoRecursiveFormat, '.no-mistakes.yaml'), 'commands:\n  test: "npm test"\n  lint: "npm run qa"\n  format: "npm run format"\n');
result = run(monorepoRecursiveFormat);
assert.equal(result.status, 0, result.stderr);

const monorepoFutureCdScope = path.join(tmp, 'monorepo-future-cd-scope');
write(path.join(monorepoFutureCdScope, 'package.json'), `${JSON.stringify({
  private: true,
  dependencies: { typescript: '^5.0.0' },
  scripts: {
    qa: 'eslint . packages/app && tsc --noEmit && fallow audit && fallow dupes',
  },
}, null, 2)}\n`);
write(path.join(monorepoFutureCdScope, 'packages', 'app', 'package.json'), `${JSON.stringify({
  name: '@sample/app',
  scripts: {
    format: 'prettier --write .',
  },
}, null, 2)}\n`);
write(path.join(monorepoFutureCdScope, 'packages', 'app', 'src', 'index.ts'), 'export const value = 1;\n');
write(path.join(monorepoFutureCdScope, '.githooks', 'pre-push'), '#!/usr/bin/env sh\nnpm run qa && cd packages/app && npm run format\n', 0o755);
write(path.join(monorepoFutureCdScope, '.no-mistakes.yaml'), 'commands:\n  test: "npm test"\n  lint: "npm run qa"\n  format: "prettier --write package.json && prettier --write packages/app"\n');
result = run(monorepoFutureCdScope);
assert.equal(result.status, 0, result.stderr);
assert.match(result.stdout, /hooked scripts: qa, packages\/app:format/);

const monorepoRootWideFormat = path.join(tmp, 'monorepo-root-wide-format');
write(path.join(monorepoRootWideFormat, 'package.json'), `${JSON.stringify({
  private: true,
  dependencies: { typescript: '^5.0.0' },
  scripts: {
    qa: 'eslint . packages/app && tsc --noEmit && fallow audit && fallow dupes',
  },
}, null, 2)}\n`);
write(path.join(monorepoRootWideFormat, 'packages', 'app', 'package.json'), `${JSON.stringify({
  name: '@sample/app',
}, null, 2)}\n`);
write(path.join(monorepoRootWideFormat, 'packages', 'app', 'src', 'index.ts'), 'export const value = 1;\n');
write(path.join(monorepoRootWideFormat, '.githooks', 'pre-push'), '#!/usr/bin/env sh\nnpm run qa\n', 0o755);
write(path.join(monorepoRootWideFormat, '.no-mistakes.yaml'), 'commands:\n  test: "npm test"\n  lint: "npm run qa"\n  format: "prettier --write ."\n');
result = run(monorepoRootWideFormat);
assert.equal(result.status, 0, result.stderr);

const monorepoPackageLocalFormat = path.join(tmp, 'monorepo-package-local-format');
write(path.join(monorepoPackageLocalFormat, 'package.json'), `${JSON.stringify({
  private: true,
  dependencies: { typescript: '^5.0.0' },
  scripts: {
    qa: 'eslint . packages/app packages/lib && tsc --noEmit && fallow audit && fallow dupes',
  },
}, null, 2)}\n`);
write(path.join(monorepoPackageLocalFormat, 'packages', 'app', 'package.json'), `${JSON.stringify({
  name: '@sample/app',
  scripts: {
    format: 'prettier --write .',
  },
}, null, 2)}\n`);
write(path.join(monorepoPackageLocalFormat, 'packages', 'app', 'src', 'index.ts'), 'export const value = 1;\n');
write(path.join(monorepoPackageLocalFormat, 'packages', 'lib', 'package.json'), `${JSON.stringify({
  name: '@sample/lib',
}, null, 2)}\n`);
write(path.join(monorepoPackageLocalFormat, 'packages', 'lib', 'src', 'index.ts'), 'export const value = 1;\n');
write(path.join(monorepoPackageLocalFormat, '.githooks', 'pre-push'), '#!/usr/bin/env sh\nnpm run qa\n', 0o755);
write(path.join(monorepoPackageLocalFormat, '.no-mistakes.yaml'), 'commands:\n  test: "npm test"\n  lint: "npm run qa"\n  format: "cd packages/app && npm run format"\n');
result = run(monorepoPackageLocalFormat);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /\.no-mistakes\.yaml commands\.format must cover js-ts project root packages\/lib/);

for (const [fixtureName, formatCommand] of [
  ['monorepo-filtered-turbo-format', 'turbo run format --filter=@sample/app'],
  ['monorepo-filtered-bun-format', 'bun --filter @sample/app run format'],
]) {
  const monorepoFilteredWorkspaceFormat = path.join(tmp, fixtureName);
  write(path.join(monorepoFilteredWorkspaceFormat, 'package.json'), `${JSON.stringify({
    private: true,
    dependencies: { typescript: '^5.0.0' },
    scripts: {
      qa: 'eslint . packages/app packages/lib && tsc --noEmit && fallow audit && fallow dupes',
    },
  }, null, 2)}\n`);
  write(path.join(monorepoFilteredWorkspaceFormat, 'packages', 'app', 'package.json'), `${JSON.stringify({
    name: '@sample/app',
    scripts: {
      format: 'prettier --write .',
    },
  }, null, 2)}\n`);
  write(path.join(monorepoFilteredWorkspaceFormat, 'packages', 'app', 'src', 'index.ts'), 'export const value = 1;\n');
  write(path.join(monorepoFilteredWorkspaceFormat, 'packages', 'lib', 'package.json'), `${JSON.stringify({
    name: '@sample/lib',
    scripts: {
      format: 'prettier --write .',
    },
  }, null, 2)}\n`);
  write(path.join(monorepoFilteredWorkspaceFormat, 'packages', 'lib', 'src', 'index.ts'), 'export const value = 1;\n');
  write(path.join(monorepoFilteredWorkspaceFormat, '.githooks', 'pre-push'), '#!/usr/bin/env sh\nnpm run qa\n', 0o755);
  write(path.join(monorepoFilteredWorkspaceFormat, '.no-mistakes.yaml'), `commands:\n  test: "npm test"\n  lint: "npm run qa"\n  format: "${formatCommand}"\n`);
  result = run(monorepoFilteredWorkspaceFormat);
  assert.notEqual(result.status, 0, formatCommand);
  assert.match(result.stderr, /\.no-mistakes\.yaml commands\.format must cover js-ts project root packages\/lib/);
}

const monorepoUnfilteredTurboFormat = path.join(tmp, 'monorepo-unfiltered-turbo-format');
write(path.join(monorepoUnfilteredTurboFormat, 'package.json'), `${JSON.stringify({
  private: true,
  workspaces: ['packages/*'],
  dependencies: { typescript: '^5.0.0' },
  scripts: {
    qa: 'eslint . packages/app packages/lib && tsc --noEmit && fallow audit && fallow dupes',
  },
}, null, 2)}\n`);
for (const [name, rootDir] of [['@sample/app', 'packages/app'], ['@sample/lib', 'packages/lib']]) {
  write(path.join(monorepoUnfilteredTurboFormat, rootDir, 'package.json'), `${JSON.stringify({
    name,
    scripts: {
      format: 'prettier --write .',
    },
  }, null, 2)}\n`);
  write(path.join(monorepoUnfilteredTurboFormat, rootDir, 'src', 'index.ts'), 'export const value = 1;\n');
}
write(path.join(monorepoUnfilteredTurboFormat, '.githooks', 'pre-push'), '#!/usr/bin/env sh\nnpm run qa\n', 0o755);
write(path.join(monorepoUnfilteredTurboFormat, '.no-mistakes.yaml'), 'commands:\n  test: "npm test"\n  lint: "npm run qa"\n  format: "prettier --write package.json && turbo run format"\n');
result = run(monorepoUnfilteredTurboFormat);
assert.equal(result.status, 0, result.stderr);

const monorepoTestRoleMissingRoot = path.join(tmp, 'monorepo-test-role-missing-root');
write(path.join(monorepoTestRoleMissingRoot, 'package.json'), `${JSON.stringify({
  private: true,
  dependencies: { typescript: '^5.0.0' },
  scripts: {
    qa: 'eslint packages/app packages/lib && tsc --noEmit && fallow audit && fallow dupes',
  },
}, null, 2)}\n`);
for (const [name, rootDir] of [['@sample/app', 'packages/app'], ['@sample/lib', 'packages/lib']]) {
  write(path.join(monorepoTestRoleMissingRoot, rootDir, 'package.json'), `${JSON.stringify({
    name,
    scripts: { test: 'vitest run' },
  }, null, 2)}\n`);
  write(path.join(monorepoTestRoleMissingRoot, rootDir, 'src', 'index.ts'), 'export const value = 1;\n');
  write(path.join(monorepoTestRoleMissingRoot, rootDir, 'test', 'index.test.ts'), 'export const tested = true;\n');
}
write(path.join(monorepoTestRoleMissingRoot, '.githooks', 'pre-push'), '#!/usr/bin/env sh\nnpm run qa && turbo run test --filter=@sample/app\n', 0o755);
write(path.join(monorepoTestRoleMissingRoot, '.no-mistakes.yaml'), 'commands:\n  test: "turbo run test --filter=@sample/app"\n  lint: "npm run qa"\n  format: "prettier --write ."\n');
result = run(monorepoTestRoleMissingRoot);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /commands\.test must cover js-ts project root packages\/lib/);

const monorepoLintRoleMissingRoot = path.join(tmp, 'monorepo-lint-role-missing-root');
write(path.join(monorepoLintRoleMissingRoot, 'package.json'), `${JSON.stringify({
  private: true,
  dependencies: { typescript: '^5.0.0' },
}, null, 2)}\n`);
for (const [name, rootDir] of [['@sample/app', 'packages/app'], ['@sample/lib', 'packages/lib']]) {
  write(path.join(monorepoLintRoleMissingRoot, rootDir, 'package.json'), `${JSON.stringify({
    name,
    scripts: { lint: 'eslint . && tsc --noEmit && fallow audit && fallow dupes' },
  }, null, 2)}\n`);
  write(path.join(monorepoLintRoleMissingRoot, rootDir, 'src', 'index.ts'), 'export const value = 1;\n');
  write(path.join(monorepoLintRoleMissingRoot, rootDir, 'test', 'index.test.ts'), 'export const tested = true;\n');
}
write(path.join(monorepoLintRoleMissingRoot, '.githooks', 'pre-push'), '#!/usr/bin/env sh\nvitest run packages/app packages/lib && turbo run lint --filter=@sample/app\n', 0o755);
write(path.join(monorepoLintRoleMissingRoot, '.no-mistakes.yaml'), 'commands:\n  test: "vitest run packages/app packages/lib"\n  lint: "turbo run lint --filter=@sample/app"\n  format: "prettier --write ."\n');
result = run(monorepoLintRoleMissingRoot);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /commands\.lint must cover js-ts project root packages\/lib/);

const monorepoUnfilteredRoles = path.join(tmp, 'monorepo-unfiltered-roles');
write(path.join(monorepoUnfilteredRoles, 'package.json'), `${JSON.stringify({
  private: true,
  workspaces: ['packages/*'],
  dependencies: { typescript: '^5.0.0' },
}, null, 2)}\n`);
for (const [name, rootDir] of [['@sample/app', 'packages/app'], ['@sample/lib', 'packages/lib']]) {
  write(path.join(monorepoUnfilteredRoles, rootDir, 'package.json'), `${JSON.stringify({
    name,
    scripts: {
      test: 'vitest run',
      lint: 'eslint . && tsc --noEmit && fallow audit && fallow dupes',
    },
  }, null, 2)}\n`);
  write(path.join(monorepoUnfilteredRoles, rootDir, 'src', 'index.ts'), 'export const value = 1;\n');
  write(path.join(monorepoUnfilteredRoles, rootDir, 'test', 'index.test.ts'), 'export const tested = true;\n');
}
write(path.join(monorepoUnfilteredRoles, '.githooks', 'pre-push'), '#!/usr/bin/env sh\nturbo run test && turbo run lint\n', 0o755);
write(path.join(monorepoUnfilteredRoles, '.no-mistakes.yaml'), 'commands:\n  test: "turbo run test"\n  lint: "turbo run lint"\n  format: "prettier --write ."\n');
result = run(monorepoUnfilteredRoles);
assert.equal(result.status, 0, result.stderr);

const monorepoExcludedWorkspace = path.join(tmp, 'monorepo-excluded-workspace');
write(path.join(monorepoExcludedWorkspace, 'package.json'), `${JSON.stringify({
  private: true,
  workspaces: ['packages/*', '!packages/legacy'],
  dependencies: { typescript: '^5.0.0' },
}, null, 2)}\n`);
for (const [name, rootDir] of [['@sample/app', 'packages/app'], ['@sample/legacy', 'packages/legacy']]) {
  write(path.join(monorepoExcludedWorkspace, rootDir, 'package.json'), `${JSON.stringify({
    name,
    scripts: {
      test: 'vitest run',
      lint: 'eslint .',
    },
  }, null, 2)}\n`);
  write(path.join(monorepoExcludedWorkspace, rootDir, 'src', 'index.ts'), 'export const value = 1;\n');
  write(path.join(monorepoExcludedWorkspace, rootDir, 'test', 'index.test.ts'), 'export const tested = true;\n');
}
write(path.join(monorepoExcludedWorkspace, '.githooks', 'pre-push'), '#!/usr/bin/env sh\nvitest run packages/app packages/legacy && eslint packages/app packages/legacy && tsc --noEmit && fallow audit && fallow dupes\n', 0o755);
write(path.join(monorepoExcludedWorkspace, '.no-mistakes.yaml'), 'commands:\n  test: "turbo run test"\n  lint: "eslint packages/app packages/legacy && tsc --noEmit && fallow audit && fallow dupes"\n  format: "prettier --write ."\n');
result = run(monorepoExcludedWorkspace);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /commands\.test must cover js-ts project root packages\/legacy/);

const monorepoOrphanWorkspace = path.join(tmp, 'monorepo-orphan-workspace');
write(path.join(monorepoOrphanWorkspace, 'package.json'), `${JSON.stringify({
  private: true,
  workspaces: ['packages/app'],
  dependencies: { typescript: '^5.0.0' },
}, null, 2)}\n`);
for (const [name, rootDir] of [['@sample/app', 'packages/app'], ['@sample/orphan', 'packages/orphan']]) {
  write(path.join(monorepoOrphanWorkspace, rootDir, 'package.json'), `${JSON.stringify({
    name,
    scripts: { test: 'vitest run' },
  }, null, 2)}\n`);
  write(path.join(monorepoOrphanWorkspace, rootDir, 'src', 'index.ts'), 'export const value = 1;\n');
  write(path.join(monorepoOrphanWorkspace, rootDir, 'test', 'index.test.ts'), 'export const tested = true;\n');
}
const orphanWorkspaceLint = 'eslint . && tsc --noEmit && fallow audit && fallow dupes';
write(path.join(monorepoOrphanWorkspace, '.githooks', 'pre-push'), `#!/usr/bin/env sh\nvitest run packages/app packages/orphan\n${orphanWorkspaceLint}\n`, 0o755);
write(path.join(monorepoOrphanWorkspace, '.no-mistakes.yaml'), `commands:\n  test: "turbo run test"\n  lint: "${orphanWorkspaceLint}"\n  format: "prettier --write ."\n`);
result = run(monorepoOrphanWorkspace);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /commands\.test must cover js-ts project root packages\/orphan/);

const monorepoOptionValueSpoof = path.join(tmp, 'monorepo-option-value-spoof');
write(path.join(monorepoOptionValueSpoof, 'package.json'), `${JSON.stringify({
  private: true,
  workspaces: ['packages/*'],
  dependencies: { typescript: '^5.0.0' },
}, null, 2)}\n`);
for (const [name, rootDir] of [['@sample/app', 'packages/app'], ['@sample/lib', 'packages/lib']]) {
  write(path.join(monorepoOptionValueSpoof, rootDir, 'package.json'), `${JSON.stringify({ name }, null, 2)}\n`);
  write(path.join(monorepoOptionValueSpoof, rootDir, 'src', 'index.ts'), 'export const value = 1;\n');
  write(path.join(monorepoOptionValueSpoof, rootDir, 'test', 'index.test.ts'), 'export const tested = true;\n');
}
write(path.join(monorepoOptionValueSpoof, '.githooks', 'pre-push'), '#!/usr/bin/env sh\nvitest run packages/app packages/lib\neslint packages/app packages/lib && tsc --noEmit && fallow audit && fallow dupes\n', 0o755);
write(path.join(monorepoOptionValueSpoof, '.no-mistakes.yaml'), 'commands:\n  test: "vitest run packages/app packages/lib"\n  lint: "eslint packages/app --cache-location packages/lib/.cache && tsc --noEmit && fallow audit && fallow dupes"\n  format: "prettier --write ."\n');
result = run(monorepoOptionValueSpoof);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /commands\.lint must cover js-ts project root packages\/lib/);

const monorepoRootFormatScope = path.join(tmp, 'monorepo-root-format-scope');
write(path.join(monorepoRootFormatScope, 'package.json'), `${JSON.stringify({
  private: true,
  workspaces: ['packages/*'],
  dependencies: { typescript: '^5.0.0' },
}, null, 2)}\n`);
write(path.join(monorepoRootFormatScope, 'src', 'root.ts'), 'export const root = true;\n');
write(path.join(monorepoRootFormatScope, 'test', 'root.test.ts'), 'export const tested = true;\n');
write(path.join(monorepoRootFormatScope, 'packages', 'app', 'package.json'), '{"name":"@sample/app"}\n');
write(path.join(monorepoRootFormatScope, 'packages', 'app', 'src', 'index.ts'), 'export const value = 1;\n');
write(path.join(monorepoRootFormatScope, '.githooks', 'pre-push'), '#!/usr/bin/env sh\nvitest run .\neslint . && tsc --noEmit && fallow audit && fallow dupes\n', 0o755);
write(path.join(monorepoRootFormatScope, '.no-mistakes.yaml'), 'commands:\n  test: "vitest run ."\n  lint: "eslint . && tsc --noEmit && fallow audit && fallow dupes"\n  format: "prettier --write packages/app"\n');
result = run(monorepoRootFormatScope);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /commands\.format must cover js-ts project root \. /);

const monorepoSameNameNoopRole = path.join(tmp, 'monorepo-same-name-noop-role');
write(path.join(monorepoSameNameNoopRole, 'package.json'), `${JSON.stringify({
  private: true,
  dependencies: { typescript: '^5.0.0' },
}, null, 2)}\n`);
for (const [name, rootDir, test] of [
  ['@sample/app', 'packages/app', 'vitest run'],
  ['@sample/lib', 'packages/lib', 'echo no tests'],
]) {
  write(path.join(monorepoSameNameNoopRole, rootDir, 'package.json'), `${JSON.stringify({ name, scripts: { test } }, null, 2)}\n`);
  write(path.join(monorepoSameNameNoopRole, rootDir, 'src', 'index.ts'), 'export const value = 1;\n');
  write(path.join(monorepoSameNameNoopRole, rootDir, 'test', 'index.test.ts'), 'export const tested = true;\n');
}
const monorepoSameNameLint = 'eslint packages/app packages/lib && tsc --noEmit && fallow audit && fallow dupes';
write(path.join(monorepoSameNameNoopRole, '.githooks', 'pre-push'), `#!/usr/bin/env sh\nturbo run test\n${monorepoSameNameLint}\n`, 0o755);
write(path.join(monorepoSameNameNoopRole, '.no-mistakes.yaml'), `commands:\n  test: "turbo run test"\n  lint: "${monorepoSameNameLint}"\n  format: "prettier --write ."\n`);
result = run(monorepoSameNameNoopRole);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /commands\.test must cover js-ts project root packages\/lib/);

for (const [fixtureName, scopedTestCommand] of [
  ['pnpm', 'pnpm -r --filter @sample/app run test'],
  ['npm', 'npm run test --workspaces --workspace @sample/app'],
  ['yarn', 'yarn workspaces foreach --from @sample/app run test'],
  ['lerna', 'lerna run test --scope @sample/app'],
  ['nx', 'nx run-many --target=test --projects=@sample/app'],
]) {
  const scopedWorkspace = path.join(tmp, `monorepo-scoped-${fixtureName}`);
  write(path.join(scopedWorkspace, 'package.json'), `${JSON.stringify({
    private: true,
    dependencies: { typescript: '^5.0.0' },
  }, null, 2)}\n`);
  for (const [name, rootDir] of [['@sample/app', 'packages/app'], ['@sample/lib', 'packages/lib']]) {
    write(path.join(scopedWorkspace, rootDir, 'package.json'), `${JSON.stringify({
      name,
      scripts: { test: 'vitest run' },
    }, null, 2)}\n`);
    write(path.join(scopedWorkspace, rootDir, 'src', 'index.ts'), 'export const value = 1;\n');
    write(path.join(scopedWorkspace, rootDir, 'test', 'index.test.ts'), 'export const tested = true;\n');
  }
  const lintCommand = 'eslint packages/app packages/lib && tsc --noEmit && fallow audit && fallow dupes';
  write(path.join(scopedWorkspace, '.githooks', 'pre-push'), `#!/usr/bin/env sh\n${scopedTestCommand}\n${lintCommand}\n`, 0o755);
  write(path.join(scopedWorkspace, '.no-mistakes.yaml'), `commands:\n  test: "${scopedTestCommand}"\n  lint: "${lintCommand}"\n  format: "prettier --write ."\n`);
  result = run(scopedWorkspace);
  assert.notEqual(result.status, 0, scopedTestCommand);
  assert.match(result.stderr, /commands\.test must cover js-ts project root packages\/lib/, scopedTestCommand);
}

const monorepoUnrelatedFormatPath = path.join(tmp, 'monorepo-unrelated-format-path');
write(path.join(monorepoUnrelatedFormatPath, 'package.json'), `${JSON.stringify({
  private: true,
  dependencies: { typescript: '^5.0.0' },
}, null, 2)}\n`);
for (const [name, rootDir] of [['@sample/app', 'packages/app'], ['@sample/lib', 'packages/lib']]) {
  write(path.join(monorepoUnrelatedFormatPath, rootDir, 'package.json'), `${JSON.stringify({ name }, null, 2)}\n`);
  write(path.join(monorepoUnrelatedFormatPath, rootDir, 'src', 'index.ts'), 'export const value = 1;\n');
}
const unrelatedLint = 'eslint packages/app packages/lib && tsc --noEmit && fallow audit && fallow dupes';
write(path.join(monorepoUnrelatedFormatPath, '.githooks', 'pre-push'), `#!/usr/bin/env sh\n${unrelatedLint}\n`, 0o755);
write(path.join(monorepoUnrelatedFormatPath, '.no-mistakes.yaml'), `commands:\n  test: "npm test"\n  lint: "${unrelatedLint}"\n  format: "prettier --write packages/app && echo packages/lib"\n`);
result = run(monorepoUnrelatedFormatPath);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /commands\.format must cover js-ts project root packages\/lib/);

const monorepoNonFormatterPackageScript = path.join(tmp, 'monorepo-non-formatter-package-script');
write(path.join(monorepoNonFormatterPackageScript, 'package.json'), `${JSON.stringify({
  private: true,
  dependencies: { typescript: '^5.0.0' },
  scripts: { format: 'pnpm -r run format' },
}, null, 2)}\n`);
for (const [name, rootDir, format] of [
  ['@sample/app', 'packages/app', 'prettier --write .'],
  ['@sample/lib', 'packages/lib', 'echo packages/lib'],
]) {
  write(path.join(monorepoNonFormatterPackageScript, rootDir, 'package.json'), `${JSON.stringify({ name, scripts: { format } }, null, 2)}\n`);
  write(path.join(monorepoNonFormatterPackageScript, rootDir, 'src', 'index.ts'), 'export const value = 1;\n');
}
write(path.join(monorepoNonFormatterPackageScript, '.githooks', 'pre-push'), `#!/usr/bin/env sh\n${unrelatedLint}\n`, 0o755);
write(path.join(monorepoNonFormatterPackageScript, '.no-mistakes.yaml'), `commands:\n  test: "npm test"\n  lint: "${unrelatedLint}"\n  format: "npm run format"\n`);
result = run(monorepoNonFormatterPackageScript);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /commands\.format must cover js-ts project root packages\/lib/);

for (const [fixtureName, formatCommand] of [
  ['monorepo-package-local-dot-format-control', 'cd ./packages/app && prettier --write .'],
  ['monorepo-package-local-dot-format-semicolon', 'cd packages/app; prettier --write .'],
]) {
  const monorepoPackageLocalDotFormat = path.join(tmp, fixtureName);
  write(path.join(monorepoPackageLocalDotFormat, 'package.json'), `${JSON.stringify({
    private: true,
    dependencies: { typescript: '^5.0.0' },
    scripts: {
      qa: 'eslint . packages/app packages/lib && tsc --noEmit && fallow audit && fallow dupes',
    },
  }, null, 2)}\n`);
  write(path.join(monorepoPackageLocalDotFormat, 'packages', 'app', 'package.json'), `${JSON.stringify({
    name: '@sample/app',
  }, null, 2)}\n`);
  write(path.join(monorepoPackageLocalDotFormat, 'packages', 'app', 'src', 'index.ts'), 'export const value = 1;\n');
  write(path.join(monorepoPackageLocalDotFormat, 'packages', 'lib', 'package.json'), `${JSON.stringify({
    name: '@sample/lib',
  }, null, 2)}\n`);
  write(path.join(monorepoPackageLocalDotFormat, 'packages', 'lib', 'src', 'index.ts'), 'export const value = 1;\n');
  write(path.join(monorepoPackageLocalDotFormat, '.githooks', 'pre-push'), '#!/usr/bin/env sh\nnpm run qa\n', 0o755);
  write(path.join(monorepoPackageLocalDotFormat, '.no-mistakes.yaml'), `commands:\n  test: "npm test"\n  lint: "npm run qa"\n  format: "${formatCommand}"\n`);
  result = run(monorepoPackageLocalDotFormat);
  assert.notEqual(result.status, 0, formatCommand);
  assert.match(result.stderr, /\.no-mistakes\.yaml commands\.format must cover js-ts project root packages\/lib/);
}

const monorepoFormatDoesNotCoverLint = path.join(tmp, 'monorepo-format-does-not-cover-lint');
write(path.join(monorepoFormatDoesNotCoverLint, 'package.json'), `${JSON.stringify({
  private: true,
  dependencies: { typescript: '^5.0.0' },
  scripts: {
    qa: 'eslint root.js && tsc --noEmit && fallow audit && fallow dupes',
  },
}, null, 2)}\n`);
write(path.join(monorepoFormatDoesNotCoverLint, 'root.js'), 'export const root = true;\n');
write(path.join(monorepoFormatDoesNotCoverLint, 'packages', 'app', 'package.json'), `${JSON.stringify({
  name: '@sample/app',
}, null, 2)}\n`);
write(path.join(monorepoFormatDoesNotCoverLint, 'packages', 'app', 'src', 'index.ts'), 'export const value = 1;\n');
write(path.join(monorepoFormatDoesNotCoverLint, '.githooks', 'pre-push'), '#!/usr/bin/env sh\neslint root.js && tsc --noEmit && fallow audit && fallow dupes\n', 0o755);
write(path.join(monorepoFormatDoesNotCoverLint, '.no-mistakes.yaml'), 'commands:\n  test: "npm test"\n  lint: "npm run qa"\n  format: "prettier --write ."\n');
result = run(monorepoFormatDoesNotCoverLint);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /\.no-mistakes\.yaml commands\.lint must cover js-ts project root packages\/app/);

const rustWorkspaceFormat = path.join(tmp, 'rust-workspace-format');
write(path.join(rustWorkspaceFormat, 'Cargo.toml'), '[workspace]\nmembers = ["crates/app"]\n');
write(path.join(rustWorkspaceFormat, 'crates', 'app', 'Cargo.toml'), '[package]\nname = "sample-app"\nversion = "0.1.0"\nedition = "2021"\n');
write(path.join(rustWorkspaceFormat, 'crates', 'app', 'src', 'lib.rs'), 'pub fn value() -> u8 { 1 }\n');
write(path.join(rustWorkspaceFormat, '.githooks', 'pre-push'), '#!/usr/bin/env sh\ncargo test --workspace && cargo clippy --workspace\n', 0o755);
write(path.join(rustWorkspaceFormat, '.no-mistakes.yaml'), 'commands:\n  test: "cargo test --workspace"\n  lint: "cargo clippy --workspace"\n  format: "cargo fmt --all"\n');
result = run(rustWorkspaceFormat);
assert.equal(result.status, 0, result.stderr);

const rustPassiveAndCheckOnly = path.join(tmp, 'rust-passive-and-check-only');
write(path.join(rustPassiveAndCheckOnly, 'Cargo.toml'), '[package]\nname = "sample"\nversion = "0.1.0"\nedition = "2021"\n');
write(path.join(rustPassiveAndCheckOnly, 'src', 'lib.rs'), 'pub fn value() -> u8 { 1 }\n');
write(path.join(rustPassiveAndCheckOnly, 'tests', 'sample.rs'), '#[test]\nfn sample() { assert_eq!(1, 1); }\n');
write(path.join(rustPassiveAndCheckOnly, '.githooks', 'pre-push'), '#!/usr/bin/env sh\ncargo test --no-run && cargo clippy\n', 0o755);
write(path.join(rustPassiveAndCheckOnly, '.no-mistakes.yaml'), 'commands:\n  test: "cargo test --no-run"\n  lint: "cargo clippy"\n  format: "cargo fmt --all -- --check"\n');
result = run(rustPassiveAndCheckOnly);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /commands\.test must run deterministic rust tests/);
assert.match(result.stderr, /commands\.format must run cargo fmt/);

const javaSkippedTests = path.join(tmp, 'java-skipped-tests');
write(path.join(javaSkippedTests, 'pom.xml'), '<project></project>\n');
write(path.join(javaSkippedTests, 'src', 'main', 'java', 'App.java'), 'class App {}\n');
write(path.join(javaSkippedTests, 'src', 'test', 'java', 'AppTest.java'), 'class AppTest {}\n');
write(path.join(javaSkippedTests, '.githooks', 'pre-push'), '#!/usr/bin/env sh\nmvn verify -DskipTests\n', 0o755);
write(path.join(javaSkippedTests, '.no-mistakes.yaml'), 'commands:\n  test: "mvn test -DskipTests"\n  lint: "mvn verify -Dmaven.test.skip=true"\n  format: "mvn spotless:apply"\n');
result = run(javaSkippedTests);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /commands\.test must run deterministic java tests/);

const terraformMissingFormatCheck = path.join(tmp, 'terraform-missing-format-check');
write(path.join(terraformMissingFormatCheck, 'main.tf'), 'terraform {}\n');
write(path.join(terraformMissingFormatCheck, '.githooks', 'pre-push'), '#!/usr/bin/env sh\nterraform fmt -check -recursive && terraform validate\n', 0o755);
write(path.join(terraformMissingFormatCheck, '.no-mistakes.yaml'), 'commands:\n  test: "echo no-tests"\n  lint: "terraform validate"\n  format: "terraform fmt -recursive"\n');
result = run(terraformMissingFormatCheck);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /commands\.lint must run terraform fmt -check/);

const terraformCheckOnlyFormat = path.join(tmp, 'terraform-check-only-format');
write(path.join(terraformCheckOnlyFormat, 'main.tf'), 'terraform {}\n');
write(path.join(terraformCheckOnlyFormat, '.githooks', 'pre-push'), '#!/usr/bin/env sh\nterraform fmt -check -recursive && terraform validate\n', 0o755);
write(path.join(terraformCheckOnlyFormat, '.no-mistakes.yaml'), 'commands:\n  test: "echo no-tests"\n  lint: "terraform fmt -check -recursive && terraform validate"\n  format: "terraform fmt -check -recursive"\n');
result = run(terraformCheckOnlyFormat);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /commands\.format must run terraform fmt/);

const swiftLintOnlyFormat = path.join(tmp, 'swift-lint-only-format');
write(path.join(swiftLintOnlyFormat, 'Package.swift'), '// swift-tools-version: 6.0\n');
write(path.join(swiftLintOnlyFormat, 'Sources', 'App', 'App.swift'), 'public let value = 1\n');
write(path.join(swiftLintOnlyFormat, 'Tests', 'AppTests', 'AppTests.swift'), 'import Testing\n@Test func sample() {}\n');
write(path.join(swiftLintOnlyFormat, '.githooks', 'pre-push'), '#!/usr/bin/env sh\nswift test\n', 0o755);
write(path.join(swiftLintOnlyFormat, '.no-mistakes.yaml'), 'commands:\n  test: "swift test"\n  lint: "swift test"\n  format: "swiftformat --lint ."\n');
result = run(swiftLintOnlyFormat);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /commands\.format must run swiftformat or swift-format/);

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
assert.match(result.stderr, /\.no-mistakes\.yaml commands\.lint must run JS\/TS lint/);
assert.match(result.stderr, /\.no-mistakes\.yaml commands\.lint must run fallow audit or fallow dupes/);
assert.match(result.stderr, /\.no-mistakes\.yaml must define commands\.format/);

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
write(path.join(flutterGood, '.git-hooks', 'pre-push'), '#!/usr/bin/env sh\ndart analyze && flutter test\n', 0o755);
write(path.join(flutterGood, '.no-mistakes.yaml'), 'commands:\n  test: "flutter test"\n  lint: "dart analyze && flutter test"\n  format: "dart format ."\n');
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
write(path.join(pythonGood, '.githooks', 'pre-push'), '#!/usr/bin/env sh\npyrefly check --summarize-errors && python -m pytest\n', 0o755);
write(path.join(pythonGood, '.no-mistakes.yaml'), 'commands:\n  test: "python -m pytest"\n  lint: "pyrefly check --summarize-errors && ruff check ."\n  format: "ruff format ."\n');
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
write(path.join(pythonScannerGood, '.githooks', 'pre-push'), '#!/usr/bin/env sh\npyrefly check && pytest\n', 0o755);
write(path.join(pythonScannerGood, '.no-mistakes.yaml'), 'commands:\n  test: "pytest"\n  lint: "pyrefly check && ruff check . && node scripts/check-domain-rules.mjs ."\n  format: "ruff format ."\n');
result = run(pythonScannerGood);
assert.equal(result.status, 0, result.stderr);

const pythonScannerArgumentSpoof = path.join(tmp, 'python-scanner-argument-spoof');
write(path.join(pythonScannerArgumentSpoof, 'pyproject.toml'), '[project]\nname = "scanner_spoof"\n');
write(path.join(pythonScannerArgumentSpoof, 'src', 'app.py'), 'def main() -> None:\n    pass\n');
write(path.join(pythonScannerArgumentSpoof, 'tests', 'test_app.py'), 'def test_app():\n    assert True\n');
write(path.join(pythonScannerArgumentSpoof, 'scripts', 'check-domain-rules.mjs'), '#!/usr/bin/env node\n');
write(path.join(pythonScannerArgumentSpoof, 'scripts', 'noop.mjs'), '#!/usr/bin/env node\n');
write(path.join(pythonScannerArgumentSpoof, '.githooks', 'pre-push'), '#!/usr/bin/env sh\npytest && pyrefly check && node scripts/check-domain-rules.mjs\n', 0o755);
write(path.join(pythonScannerArgumentSpoof, '.no-mistakes.yaml'), 'commands:\n  test: "pytest"\n  lint: "pyrefly check && ruff check . && node scripts/noop.mjs scripts/check-domain-rules.mjs"\n  format: "ruff format ."\n');
result = run(pythonScannerArgumentSpoof);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /commands must run repo scanner scripts\/check-domain-rules\.mjs/);

for (const [fixtureName, marker, source, testCommand, lintCommand, formatCommand, expected] of [
  ['go-list-only', ['go.mod', 'module example.com/list-only\n\ngo 1.22\n'], ['main_test.go', 'package main\n'], 'go test -list .', 'go test ./...', 'go fmt ./...', /commands\.test must run deterministic go tests/],
  ['ruby-dry-run', ['Gemfile', "source 'https://rubygems.org'\n"], ['spec/app_spec.rb', 'RSpec.describe :app do; it { expect(true).to be(true) }; end\n'], 'rspec --dry-run', 'rspec', 'rubocop -a', /commands\.test must run deterministic ruby tests/],
  ['php-list-only', ['composer.json', '{"name":"sample/app"}\n'], ['tests/AppTest.php', '<?php\n'], 'phpunit --list-tests', 'phpunit', 'pint', /commands\.test must run deterministic php tests/],
]) {
  const passiveRunner = path.join(tmp, fixtureName);
  write(path.join(passiveRunner, marker[0]), marker[1]);
  write(path.join(passiveRunner, source[0]), source[1]);
  write(path.join(passiveRunner, '.githooks', 'pre-push'), `#!/usr/bin/env sh\n${lintCommand}\n`, 0o755);
  write(path.join(passiveRunner, '.no-mistakes.yaml'), `commands:\n  test: ${JSON.stringify(testCommand)}\n  lint: ${JSON.stringify(lintCommand)}\n  format: ${JSON.stringify(formatCommand)}\n`);
  result = run(passiveRunner);
  assert.notEqual(result.status, 0, testCommand);
  assert.match(result.stderr, expected);
}

for (const [fixtureName, testCommand] of [
  ['go-exec-override', 'go test -exec true ./...'],
  ['go-overlay-override', 'go test -overlay fake-overlay.json ./...'],
  ['go-modfile-override', 'go test -modfile fake.mod ./...'],
]) {
  const goOverride = path.join(tmp, fixtureName);
  write(path.join(goOverride, 'go.mod'), 'module example.com/override\n\ngo 1.22\n');
  write(path.join(goOverride, 'main.go'), 'package main\n');
  write(path.join(goOverride, 'main_test.go'), 'package main\n\nimport "testing"\n\nfunc TestMain(t *testing.T) {}\n');
  write(path.join(goOverride, '.githooks', 'pre-push'), '#!/usr/bin/env sh\ngo test ./... && go vet ./...\n', 0o755);
  write(path.join(goOverride, '.no-mistakes.yaml'), `commands:\n  test: ${JSON.stringify(testCommand)}\n  lint: "go vet ./..."\n  format: "go fmt ./..."\n`);
  result = run(goOverride);
  assert.notEqual(result.status, 0, testCommand);
  assert.match(result.stderr, /commands\.test must run deterministic go tests/);
}

for (const [fixtureName, marker, source, testCommand, formatCommand, expected] of [
  ['go-test-as-lint', ['go.mod', 'module example.com/lint\n\ngo 1.22\n'], ['main_test.go', 'package main\n'], 'go test ./...', 'go fmt ./...', /commands\.lint must run go lint/i],
  ['swift-test-as-lint', ['Package.swift', '// swift-tools-version: 6.0\n'], ['Tests/AppTests/AppTests.swift', 'import Testing\n@Test func sample() {}\n'], 'swift test', 'swiftformat .', /commands\.lint must run swift lint/i],
  ['ruby-test-as-lint', ['Gemfile', "source 'https://rubygems.org'\n"], ['spec/app_spec.rb', 'RSpec.describe :app do; it { expect(true).to be(true) }; end\n'], 'rspec', 'rubocop -a', /commands\.lint must run ruby lint/i],
  ['php-test-as-lint', ['composer.json', '{"name":"sample/app"}\n'], ['tests/AppTest.php', '<?php\n'], 'phpunit', 'pint', /commands\.lint must run php lint/i],
]) {
  const testAsLint = path.join(tmp, fixtureName);
  write(path.join(testAsLint, marker[0]), marker[1]);
  write(path.join(testAsLint, source[0]), source[1]);
  write(path.join(testAsLint, '.githooks', 'pre-push'), `#!/usr/bin/env sh\n${testCommand}\n`, 0o755);
  write(path.join(testAsLint, '.no-mistakes.yaml'), `commands:\n  test: ${JSON.stringify(testCommand)}\n  lint: ${JSON.stringify(testCommand)}\n  format: ${JSON.stringify(formatCommand)}\n`);
  result = run(testAsLint);
  assert.notEqual(result.status, 0, testCommand);
  assert.match(result.stderr, expected);
}

const stackStaticLintGood = path.join(tmp, 'stack-static-lint-good');
write(path.join(stackStaticLintGood, 'Package.swift'), '// swift-tools-version: 6.0\n');
write(path.join(stackStaticLintGood, 'Tests', 'AppTests', 'AppTests.swift'), 'import Testing\n@Test func sample() {}\n');
write(path.join(stackStaticLintGood, 'Gemfile'), "source 'https://rubygems.org'\n");
write(path.join(stackStaticLintGood, 'spec', 'app_spec.rb'), 'RSpec.describe :app do; it { expect(true).to be(true) }; end\n');
write(path.join(stackStaticLintGood, 'composer.json'), '{"name":"sample/app"}\n');
write(path.join(stackStaticLintGood, 'tests', 'AppTest.php'), '<?php\n');
write(path.join(stackStaticLintGood, '.githooks', 'pre-push'), '#!/usr/bin/env sh\nswift test && rspec && phpunit && swiftlint && rubocop && phpstan analyse\n', 0o755);
write(path.join(stackStaticLintGood, '.no-mistakes.yaml'), 'commands:\n  test: "swift test && rspec && phpunit"\n  lint: "swiftlint && rubocop && phpstan analyse"\n  format: "swiftformat . && rubocop -a && pint"\n');
result = run(stackStaticLintGood);
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
write(path.join(dartFunctionsGood, '.githooks', 'pre-push'), '#!/usr/bin/env sh\nset -e\nfor dir in functions/send-email functions/sync-user; do (cd "$dir" && dart analyze && dart test); done\n', 0o755);
write(path.join(dartFunctionsGood, '.no-mistakes.yaml'), 'commands:\n  test: "set -e; for dir in functions/send-email functions/sync-user; do (cd \\"$dir\\" && dart test); done"\n  lint: "set -e; for dir in functions/send-email functions/sync-user; do (cd \\"$dir\\" && dart analyze); done"\n  format: "set -e; for dir in functions/send-email functions/sync-user; do (cd \\"$dir\\" && dart format .); done"\n');
result = run(dartFunctionsGood);
assert.equal(result.status, 0, result.stderr);

const dartFunctionsUnboundLoop = path.join(tmp, 'dart-functions-unbound-loop');
for (const fn of ['send-email', 'sync-user']) {
  write(path.join(dartFunctionsUnboundLoop, 'functions', fn, 'pubspec.yaml'), `name: ${fn.replace('-', '_')}\n`);
  write(path.join(dartFunctionsUnboundLoop, 'functions', fn, 'bin', 'main.dart'), 'void main() {}\n');
  write(path.join(dartFunctionsUnboundLoop, 'functions', fn, 'test', 'main_test.dart'), 'void main() {}\n');
}
write(path.join(dartFunctionsUnboundLoop, '.githooks', 'pre-push'), '#!/usr/bin/env sh\nset -e\nfor dir in functions/send-email functions/sync-user; do (cd "$dir" && dart analyze && dart test); done\n', 0o755);
write(path.join(dartFunctionsUnboundLoop, '.no-mistakes.yaml'), 'commands:\n  test: "set -e; for dir in functions/send-email functions/sync-user; do (cd \\"$dir\\" && cd .. && dart test); done"\n  lint: "set -e; for dir in functions/send-email functions/sync-user; do (cd \\"$dir\\" && cd .. && dart analyze); done"\n  format: "set -e; for dir in functions/send-email functions/sync-user; do (cd \\"$dir\\" && dart format .); done"\n');
result = run(dartFunctionsUnboundLoop);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /commands\.(?:test|lint) must cover dart project root/);

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
write(path.join(goMultiGood, '.githooks', 'pre-push'), '#!/usr/bin/env sh\nset -e\nfor dir in services/api libs/core; do (cd "$dir" && go vet ./... && go test ./...); done\n', 0o755);
write(path.join(goMultiGood, '.no-mistakes.yaml'), 'commands:\n  test: "set -e; for dir in services/api libs/core; do (cd \\"$dir\\" && go test ./...); done"\n  lint: "set -e; for dir in services/api libs/core; do (cd \\"$dir\\" && go vet ./...); done"\n  format: "set -e; for dir in services/api libs/core; do (cd \\"$dir\\" && go fmt ./...); done"\n');
result = run(goMultiGood);
assert.equal(result.status, 0, result.stderr);

const hardEngGood = path.join(tmp, 'hard-eng-good');
write(path.join(hardEngGood, 'scripts', 'check-hard-eng-full-repo.mjs'), '#!/usr/bin/env node\n');
write(path.join(hardEngGood, 'skills', 'workflow-help', 'references', 'route-map.md'), '# route\n');
write(path.join(hardEngGood, '.git', 'hooks', 'pre-push'), '#!/usr/bin/env sh\nnode scripts/check-project-quality-gates.mjs --require-push-gate .\n', 0o755);
write(path.join(hardEngGood, '.no-mistakes.yaml'), 'commands:\n  test: "node scripts/check-hard-eng-full-repo.mjs"\n  lint: >-\n    node scripts/check-project-quality-gates.mjs --require-push-gate . &&\n    node scripts/format-hard-eng.mjs --check .\n  format: "node scripts/format-hard-eng.mjs ."\n');
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
assert.match(result.stderr, /\.no-mistakes\.yaml must define commands\.format/);

const hardEngFormatSpoof = path.join(tmp, 'hard-eng-format-spoof');
write(path.join(hardEngFormatSpoof, 'scripts', 'check-hard-eng-full-repo.mjs'), '#!/usr/bin/env node\n');
write(path.join(hardEngFormatSpoof, 'scripts', 'check-project-quality-gates.mjs'), '#!/usr/bin/env node\n');
write(path.join(hardEngFormatSpoof, 'skills', 'workflow-help', 'references', 'route-map.md'), '# route\n');
write(path.join(hardEngFormatSpoof, '.git', 'hooks', 'pre-push'), '#!/usr/bin/env sh\nnode scripts/check-project-quality-gates.mjs --require-push-gate .\n', 0o755);
write(path.join(hardEngFormatSpoof, '.no-mistakes.yaml'), 'commands:\n  test: "node scripts/check-hard-eng-full-repo.mjs"\n  lint: "node scripts/check-project-quality-gates.mjs --require-push-gate ."\n  format: "npm exec echo scripts/format-hard-eng.mjs ."\n');
result = run(hardEngFormatSpoof);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /commands\.format must run scripts\/format-hard-eng\.mjs/);

write(path.join(hardEngFormatSpoof, '.no-mistakes.yaml'), 'commands:\n  test: "node scripts/check-hard-eng-full-repo.mjs"\n  lint: "node scripts/check-project-quality-gates.mjs --require-push-gate ."\n  format: "node scripts/format-hard-eng.mjs --check ."\n');
result = run(hardEngFormatSpoof);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /commands\.format must mutate files with scripts\/format-hard-eng\.mjs/);

write(path.join(hardEngFormatSpoof, '.no-mistakes.yaml'), 'commands:\n  test: "node scripts/check-hard-eng-full-repo.mjs"\n  lint: "node scripts/check-project-quality-gates.mjs --require-push-gate ."\n  format: "node scripts/format-hard-eng.mjs --help"\n');
result = run(hardEngFormatSpoof);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /commands\.format must mutate files with scripts\/format-hard-eng\.mjs/);

console.log('project-quality-gates-test: pass');
