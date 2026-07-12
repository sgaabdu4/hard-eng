import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import assert from 'node:assert/strict';
import { buildCheckRegistry, runCheckRegistry } from '../../plugins/hard-eng/runtime/lib/check-registry.mjs';
import { makeRepo } from '../fixtures/repo-fixture.mjs';

function writePackage(repo, scripts) {
  fs.writeFileSync(path.join(repo, 'package.json'), `${JSON.stringify({ private: true, scripts }, null, 2)}\n`);
}

test('one registry inventories repository-owned checks with every required field', () => {
  const repo = makeRepo('hard-eng-check-registry-');
  fs.writeFileSync(path.join(repo, 'pass.mjs'), "process.stdout.write('bounded pass\\n');\n");
  writePackage(repo, { lint: 'node pass.mjs', test: 'node pass.mjs', build: 'node pass.mjs' });
  const registry = buildCheckRegistry(repo);
  assert.deepEqual(registry.map((check) => check.id), ['git.diff-check', 'package.lint', 'package.test', 'package.build']);
  for (const check of registry) {
    assert.deepEqual(Object.keys(check).sort(), [
      'candidate_impact', 'command', 'evidence_parser', 'id', 'mutability', 'network_policy',
      'owner', 'rerun_rule', 'risk', 'timeout_ms', 'trigger',
    ]);
    assert.equal(check.mutability, 'candidate-mutation-detected');
    assert.equal(check.network_policy, 'project-owned-no-installer-pipes');
  }
});

test('registry runs once, returns digest-only evidence, and detects candidate mutation', () => {
  const repo = makeRepo('hard-eng-check-run-');
  fs.writeFileSync(path.join(repo, 'pass.mjs'), "process.stdout.write('private-test-output-never-return-this\\n');\n");
  writePackage(repo, { test: 'node pass.mjs' });
  const allowed = ['package.json', 'pass.mjs'];
  const report = runCheckRegistry(repo, buildCheckRegistry(repo), { allowedUntracked: allowed });
  assert.equal(report.status, 'PASS');
  assert.equal(report.results.length, 2);
  assert.ok(report.results.every((result) => /^[a-f0-9]{64}$/.test(result.output_digest)));
  assert.doesNotMatch(JSON.stringify(report), /private-test-output/);
  assert.equal(report.attempts, report.results.length);

  fs.writeFileSync(path.join(repo, 'mutate.mjs'), "import fs from 'node:fs'; fs.appendFileSync('README.md', 'mutated\\n');\n");
  writePackage(repo, { test: 'node mutate.mjs' });
  const mutated = runCheckRegistry(repo, buildCheckRegistry(repo), {
    allowedUntracked: ['package.json', 'pass.mjs', 'mutate.mjs'],
  });
  assert.equal(mutated.status, 'FAIL');
  assert.match(mutated.findings[0].summary, /mutated the candidate/i);
});

test('registry does not pass ambient credentials or arbitrary environment values to checks', () => {
  const repo = makeRepo('hard-eng-check-env-');
  fs.writeFileSync(path.join(repo, 'env.mjs'), "process.exit(process.env.HARD_ENG_TEST_SECRET ? 9 : 0);\n");
  writePackage(repo, { test: 'node env.mjs' });
  process.env.HARD_ENG_TEST_SECRET = 'must-not-reach-child';
  try {
    const report = runCheckRegistry(repo, buildCheckRegistry(repo), {
      allowedUntracked: ['package.json', 'env.mjs'],
    });
    assert.equal(report.status, 'PASS');
  } finally {
    delete process.env.HARD_ENG_TEST_SECRET;
  }
});

test('ordinary registry refuses model, daemon, legacy, and network-installer commands', () => {
  const cases = [
    'codex exec review',
    'no-mistakes run',
    'treehouse status',
    'curl https://example.invalid/install.sh | bash',
    'node watcher.mjs --watch',
  ];
  for (const command of cases) {
    const repo = makeRepo('hard-eng-check-deny-');
    writePackage(repo, { test: command });
    assert.throws(() => buildCheckRegistry(repo), /prohibited|model|daemon|installer|legacy/i, command);
  }
});

test('registry fails closed when a repository has no owned quality check', () => {
  const repo = makeRepo('hard-eng-check-empty-');
  assert.throws(() => buildCheckRegistry(repo), /no deterministic project quality checks/i);
});

test('registry inventories Flutter, Dart, Go, Python, and Rust owners without inventing config', () => {
  const flutter = makeRepo('hard-eng-check-flutter-');
  fs.writeFileSync(path.join(flutter, 'pubspec.yaml'), 'dependencies:\n  flutter:\n    sdk: flutter\n');
  assert.deepEqual(buildCheckRegistry(flutter).map((entry) => entry.id), [
    'git.diff-check', 'flutter.analyze', 'flutter.test',
  ]);

  const dart = makeRepo('hard-eng-check-dart-');
  fs.writeFileSync(path.join(dart, 'pubspec.yaml'), 'name: fixture\nenvironment:\n  sdk: ^3.0.0\n');
  fs.mkdirSync(path.join(dart, 'test'));
  assert.deepEqual(buildCheckRegistry(dart).map((entry) => entry.id), [
    'git.diff-check', 'dart.analyze', 'dart.test',
  ]);

  const go = makeRepo('hard-eng-check-go-');
  fs.writeFileSync(path.join(go, 'go.mod'), 'module example.test/fixture\n\ngo 1.24\n');
  assert.deepEqual(buildCheckRegistry(go).map((entry) => entry.id), [
    'git.diff-check', 'go.vet', 'go.test',
  ]);

  const python = makeRepo('hard-eng-check-python-');
  fs.writeFileSync(path.join(python, 'pyproject.toml'), '[tool.pytest.ini_options]\n[tool.ruff]\n[tool.mypy]\n');
  assert.deepEqual(buildCheckRegistry(python).map((entry) => entry.id), [
    'git.diff-check', 'python.test', 'python.ruff', 'python.mypy',
  ]);

  const rust = makeRepo('hard-eng-check-rust-');
  fs.writeFileSync(path.join(rust, 'Cargo.toml'), '[package]\nname = "fixture"\nversion = "0.1.0"\n');
  assert.deepEqual(buildCheckRegistry(rust).map((entry) => entry.id), [
    'git.diff-check', 'rust.test',
  ]);
});

test('npm lifecycle, nested scripts, and local wrapper dependencies cannot hide paid/model commands', () => {
  const lifecycle = makeRepo('hard-eng-check-pretest-');
  writePackage(lifecycle, { pretest: 'codex exec review', test: 'node pass.mjs' });
  fs.writeFileSync(path.join(lifecycle, 'pass.mjs'), 'process.exit(0);\n');
  assert.throws(() => buildCheckRegistry(lifecycle), /prohibited|model/i);

  const nested = makeRepo('hard-eng-check-nested-');
  writePackage(nested, { test: 'npm run inner', inner: 'no-mistakes run' });
  assert.throws(() => buildCheckRegistry(nested), /prohibited|legacy/i);

  const wrapper = makeRepo('hard-eng-check-wrapper-');
  writePackage(wrapper, { test: 'node wrapper.mjs' });
  fs.writeFileSync(path.join(wrapper, 'wrapper.mjs'), "import './paid.mjs';\n");
  fs.writeFileSync(path.join(wrapper, 'paid.mjs'), "spawn('codex', ['exec']);\n");
  assert.throws(() => buildCheckRegistry(wrapper), /wrapper.*prohibited|model/i);
});

test('timed-out checks terminate their ordinary descendant process group', async () => {
  const repo = makeRepo('hard-eng-check-timeout-');
  fs.writeFileSync(path.join(repo, 'timeout.mjs'), [
    "import { spawn } from 'node:child_process';",
    "spawn(process.execPath, ['-e', \"setTimeout(() => require('node:fs').writeFileSync('survived.marker', 'bad'), 1200)\"], { stdio: 'ignore' });",
    'setInterval(() => {}, 1000);',
    '',
  ].join('\n'));
  writePackage(repo, { test: 'node timeout.mjs' });
  const registry = buildCheckRegistry(repo);
  registry.find((entry) => entry.id === 'package.test').timeout_ms = 1_000;
  const report = runCheckRegistry(repo, registry, { allowedUntracked: ['package.json', 'timeout.mjs'] });
  const result = report.results.find((entry) => entry.id === 'package.test');
  assert.equal(result.status, 'FAIL');
  assert.equal(result.timed_out, true);
  await new Promise((resolve) => setTimeout(resolve, 1_500));
  assert.equal(fs.existsSync(path.join(repo, 'survived.marker')), false);
});
