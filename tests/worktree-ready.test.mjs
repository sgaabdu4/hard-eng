#!/usr/bin/env node
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';

const repoRoot = path.join(process.env.HOME, '.agents');
const script = path.join(repoRoot, 'scripts', 'ensure-worktree-ready.sh');

function run(command, args, options = {}) {
  const result = spawnSync(command, args, {
    encoding: 'utf8',
    ...options,
  });
  if (options.expectFailure) return result;
  assert.equal(
    result.status,
    0,
    `${command} ${args.join(' ')} failed\nstdout:\n${result.stdout}\nstderr:\n${result.stderr}`,
  );
  return result;
}

function write(file, text, mode) {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, text);
  if (mode) fs.chmodSync(file, mode);
}

const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'agents-worktree-ready-'));
const source = path.join(tmp, 'source');
const linked = path.join(tmp, 'linked');

fs.mkdirSync(source, { recursive: true });
run('git', ['init', '-q', '-b', 'main'], { cwd: source });
run('git', ['config', 'user.email', 'agent@example.com'], { cwd: source });
run('git', ['config', 'user.name', 'Agent Test'], { cwd: source });
run('git', ['config', 'extensions.worktreeConfig', 'true'], { cwd: source });

write(path.join(source, 'package.json'), `${JSON.stringify({
  private: true,
  scripts: {
    prepare: 'node scripts/fake-husky.mjs',
  },
}, null, 2)}\n`);
write(path.join(source, 'scripts', 'fake-husky.mjs'), `
import fs from 'node:fs';
import path from 'node:path';

const dir = path.join(process.cwd(), '.husky', '_');
fs.mkdirSync(dir, { recursive: true });
fs.writeFileSync(path.join(dir, '.gitignore'), '*\\n');
fs.writeFileSync(path.join(dir, 'h'), '#!/usr/bin/env sh\\nsh -e "$(dirname "$(dirname "$0")")/$(basename "$0")" "$@"\\n');
fs.writeFileSync(path.join(dir, 'pre-push'), '#!/usr/bin/env sh\\n. "$(dirname "$0")/h"\\n');
fs.chmodSync(path.join(dir, 'h'), 0o755);
fs.chmodSync(path.join(dir, 'pre-push'), 0o755);
`);
write(path.join(source, '.husky', 'pre-push'), '#!/usr/bin/env sh\necho project pre-push\n', 0o755);

run('git', ['add', 'package.json', 'scripts/fake-husky.mjs', '.husky/pre-push'], { cwd: source });
run('git', ['commit', '-q', '-m', 'seed husky repo'], { cwd: source });
run('git', ['worktree', 'add', '-q', linked, '-b', 'feature/ready-test'], { cwd: source });

const privateHookPath = path.join(process.env.HOME, '.no-mistakes', 'repos', 'example.git', 'hooks');
run('git', ['config', '--worktree', 'core.hooksPath', privateHookPath], { cwd: linked });

const checkBefore = run(script, ['--check', linked], { expectFailure: true });
assert.notEqual(checkBefore.status, 0, '--check must fail before repair');
assert.match(checkBefore.stderr, /core\.hooksPath|private or gate-owned/);

run(script, [linked]);

assert.equal(run('git', ['config', '--get', 'core.hooksPath'], { cwd: linked }).stdout.trim(), '.husky/_');
assert.ok(fs.existsSync(path.join(linked, '.husky', '_', 'pre-push')), 'Husky pre-push shim must be generated');
assert.ok(fs.existsSync(path.join(linked, '.husky', '_', 'h')), 'Husky dispatcher must be generated');
assert.equal(run(script, ['--check', linked]).status, 0, '--check must pass after repair');

const origins = run('git', ['config', '--show-origin', '--get-all', 'core.hooksPath'], { cwd: linked }).stdout;
assert.ok(!origins.includes('/Users/'), 'hook config must not contain macOS personal paths');
assert.ok(!origins.includes('/home/'), 'hook config must not contain Linux personal paths');
assert.ok(!origins.includes('/.no-mistakes/repos/'), 'hook config must not point at no-mistakes gate hooks');

const plain = path.join(tmp, 'plain');
fs.mkdirSync(plain);
run('git', ['init', '-q', '-b', 'main'], { cwd: plain });
assert.equal(run(script, ['--check', plain]).status, 0, 'non-Husky repos should pass without mutation');

const multiRoot = path.join(tmp, 'multi');
fs.mkdirSync(path.join(multiRoot, 'a'), { recursive: true });
fs.mkdirSync(path.join(multiRoot, 'b'), { recursive: true });
run('git', ['init', '-q', '-b', 'main'], { cwd: path.join(multiRoot, 'a') });
run('git', ['init', '-q', '-b', 'main'], { cwd: path.join(multiRoot, 'b') });
assert.equal(run(script, ['--check', 'a', 'b'], { cwd: multiRoot }).status, 0, 'multiple relative targets must resolve from the invocation directory');

const generic = path.join(tmp, 'generic');
fs.mkdirSync(generic);
run('git', ['init', '-q', '-b', 'main'], { cwd: generic });
write(path.join(generic, '.githooks', 'pre-push'), '#!/usr/bin/env sh\necho generic pre-push\n', 0o755);
run('git', ['config', 'core.hooksPath', path.join(process.env.HOME, '.no-mistakes', 'repos', 'generic.git', 'hooks')], { cwd: generic });
run(script, [generic]);
assert.equal(run('git', ['config', '--get', 'core.hooksPath'], { cwd: generic }).stdout.trim(), '.githooks');
assert.equal(run(script, ['--check', '--require-pre-push', generic]).status, 0, 'generic hook repos should pass after repair');

const flutterStyle = path.join(tmp, 'flutter-style');
fs.mkdirSync(flutterStyle);
run('git', ['init', '-q', '-b', 'main'], { cwd: flutterStyle });
write(path.join(flutterStyle, 'pubspec.yaml'), 'name: sample_flutter_app\n');
write(path.join(flutterStyle, '.git-hooks', 'pre-push'), '#!/usr/bin/env sh\ndart analyze\n', 0o755);
run('git', ['config', 'core.hooksPath', '/Users/example/.no-mistakes/repos/flutter.git/hooks'], { cwd: flutterStyle });
run(script, [flutterStyle]);
assert.equal(run('git', ['config', '--get', 'core.hooksPath'], { cwd: flutterStyle }).stdout.trim(), '.git-hooks');
assert.equal(run(script, ['--check', '--require-pre-push', flutterStyle]).status, 0, 'Flutter-style tracked hook repos should pass after repair');

const externalSafe = path.join(tmp, 'external-safe');
fs.mkdirSync(externalSafe);
run('git', ['init', '-q', '-b', 'main'], { cwd: externalSafe });
write(path.join(externalSafe, 'lefthook.yml'), 'pre-push:\n  commands:\n    test:\n      run: echo ok\n');
assert.equal(run(script, ['--check', externalSafe]).status, 0, 'external manager without unsafe hook path should pass');

const externalBad = path.join(tmp, 'external-bad');
fs.mkdirSync(externalBad);
run('git', ['init', '-q', '-b', 'main'], { cwd: externalBad });
write(path.join(externalBad, '.pre-commit-config.yaml'), 'repos: []\n');
run('git', ['config', 'core.hooksPath', '/home/example/.no-mistakes/repos/pre-commit.git/hooks'], { cwd: externalBad });
const externalBadResult = run(script, ['--check', externalBad], { expectFailure: true });
assert.notEqual(externalBadResult.status, 0, 'external managers with private hook paths must fail');
assert.match(externalBadResult.stderr, /external hook manager/);

const unknownBad = path.join(tmp, 'unknown-bad');
fs.mkdirSync(unknownBad);
run('git', ['init', '-q', '-b', 'main'], { cwd: unknownBad });
run('git', ['config', 'core.hooksPath', path.join(process.env.HOME, '.no-mistakes', 'repos', 'unknown.git', 'hooks')], { cwd: unknownBad });
const unknownResult = run(script, ['--check', unknownBad], { expectFailure: true });
assert.notEqual(unknownResult.status, 0, 'unknown repos with private hook paths must fail');
assert.match(unknownResult.stderr, /no detected project hook owner/);

console.log('worktree-ready: pass');
