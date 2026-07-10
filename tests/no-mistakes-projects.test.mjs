#!/usr/bin/env node
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';

const repo = process.cwd();
const script = path.join(repo, 'scripts', 'check-no-mistakes-projects.mjs');
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'no-mistakes-projects-'));

function run(command, args, options = {}) {
  const result = spawnSync(command, args, { encoding: 'utf8', ...options });
  if (options.expectFailure) return result;
  assert.equal(result.status, 0, `${command} ${args.join(' ')}\n${result.stdout}\n${result.stderr}`);
  return result;
}

function write(file, text, mode) {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, text);
  if (mode) fs.chmodSync(file, mode);
}

function initRepo(root) {
  fs.mkdirSync(root, { recursive: true });
  run('git', ['init', '-q', '-b', 'main'], { cwd: root });
  run('git', ['remote', 'add', 'origin', 'https://github.com/example/repo.git'], { cwd: root });
  run('git', ['remote', 'add', 'no-mistakes', path.join(root, '.gate.git')], { cwd: root });
  write(path.join(root, '.no-mistakes.yaml'), 'commands:\n  test: "echo test"\n  lint: "echo lint"\n  format: "echo format"\n');
}

function commitAll(root, message) {
  run('git', ['config', 'user.email', 'hard-eng@example.invalid'], { cwd: root });
  run('git', ['config', 'user.name', 'Hard Eng Test'], { cwd: root });
  run('git', ['add', '.'], { cwd: root });
  run('git', ['commit', '-m', message], { cwd: root });
  return run('git', ['rev-parse', 'HEAD'], { cwd: root }).stdout.trim();
}

const clean = path.join(tmp, 'clean');
initRepo(clean);
let result = run(process.execPath, [script, '--json', clean]);
let payload = JSON.parse(result.stdout);
assert.deepEqual(payload.blockers, []);
assert.equal(payload.repos[0].path, '.');
assert.equal(payload.repos[0].hasNoMistakesConfig, true);
assert.equal(payload.repos[0].hasNoMistakesRemote, true);

const missingRemote = path.join(tmp, 'missing-remote');
initRepo(missingRemote);
run('git', ['remote', 'remove', 'no-mistakes'], { cwd: missingRemote });
result = run(process.execPath, [script, '--json', missingRemote], { expectFailure: true });
assert.notEqual(result.status, 0);
payload = JSON.parse(result.stdout);
assert.ok(payload.blockers.some((blocker) => /initialized with no-mistakes init/.test(blocker)));
result = run(process.execPath, [script, '--allow-missing-no-mistakes-remote', '--json', missingRemote]);
payload = JSON.parse(result.stdout);
assert.deepEqual(payload.blockers, []);
assert.equal(payload.repos[0].hasNoMistakesRemote, false);

const missingConfig = path.join(tmp, 'missing-config');
initRepo(missingConfig);
fs.rmSync(path.join(missingConfig, '.no-mistakes.yaml'));
result = run(process.execPath, [script, '--json', missingConfig], { expectFailure: true });
assert.notEqual(result.status, 0);
payload = JSON.parse(result.stdout);
assert.ok(payload.blockers.some((blocker) => /must define \.no-mistakes\.yaml/.test(blocker)));

const unmanaged = path.join(tmp, 'unmanaged');
initRepo(unmanaged);
write(path.join(unmanaged, 'nested', '.git', 'HEAD'), 'ref: refs/heads/main\n');
result = run(process.execPath, [script, '--json', unmanaged], { expectFailure: true });
assert.notEqual(result.status, 0);
payload = JSON.parse(result.stdout);
assert.ok(payload.blockers.some((blocker) => /unmanaged nested Git repo nested/.test(blocker)));

const configuredNested = path.join(tmp, 'configured-nested');
initRepo(configuredNested);
initRepo(path.join(configuredNested, 'nested'));
initRepo(path.join(configuredNested, 'nested', 'child'));
result = run(process.execPath, [script, '--json', configuredNested]);
payload = JSON.parse(result.stdout);
assert.deepEqual(payload.blockers, []);
assert.ok(payload.repos.some((repo) => repo.path === 'nested' && repo.type === 'project'));
assert.ok(payload.repos.some((repo) => repo.path === 'nested' && repo.hasNoMistakesConfig));
assert.ok(payload.repos.some((repo) => repo.path === 'nested' && repo.hasNoMistakesRemote));
assert.ok(payload.repos.some((repo) => repo.path === 'nested/child' && repo.type === 'project'));

const trackedSubmodule = path.join(tmp, 'tracked-submodule');
initRepo(trackedSubmodule);
const trackedSubmoduleRoot = path.join(trackedSubmodule, 'third-party', 'upstream');
initRepo(trackedSubmoduleRoot);
const submoduleHead = commitAll(trackedSubmoduleRoot, 'tracked upstream');
run('git', ['update-index', '--add', '--cacheinfo', `160000,${submoduleHead},third-party/upstream`], { cwd: trackedSubmodule });
write(path.join(trackedSubmoduleRoot, 'nested', 'checkout', '.git', 'HEAD'), 'ref: refs/heads/main\n');
write(path.join(trackedSubmoduleRoot, 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', '.git', 'HEAD'), 'ref: refs/heads/main\n');
result = run(process.execPath, [script, '--json', trackedSubmodule], { expectFailure: true });
payload = JSON.parse(result.stdout);
assert.equal(result.status, 0, result.stderr);
assert.deepEqual(payload.blockers, []);
assert.deepEqual(payload.repos.filter((repo) => repo.type === 'tracked-submodule').map((repo) => repo.path), ['third-party/upstream']);

const truncated = path.join(tmp, 'truncated');
initRepo(truncated);
write(path.join(truncated, 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', '.git', 'HEAD'), 'ref: refs/heads/main\n');
result = run(process.execPath, [script, '--json', truncated], { expectFailure: true });
assert.notEqual(result.status, 0);
payload = JSON.parse(result.stdout);
assert.ok(payload.blockers.some((blocker) => /nested repository inventory truncated/.test(blocker)));

const gateWorktree = path.join(tmp, '.no-mistakes', 'worktrees', 'gate');
initRepo(gateWorktree);
const gateHooks = path.join(tmp, '.no-mistakes', 'repos', 'sample.git', 'hooks');
run('git', ['config', 'core.hooksPath', gateHooks], { cwd: gateWorktree });
write(path.join(gateWorktree, 'scripts', 'check-hard-eng-full-repo.mjs'), '#!/usr/bin/env node\n');
write(path.join(gateWorktree, 'scripts', 'check-project-quality-gates.mjs'), '#!/usr/bin/env node\n');
write(path.join(gateWorktree, 'scripts', 'format-hard-eng.mjs'), '#!/usr/bin/env node\n');
write(path.join(gateWorktree, 'skills', 'workflow-help', 'references', 'route-map.md'), '# route\n');
write(path.join(gateWorktree, 'scripts', 'install.sh'), `#!/usr/bin/env bash
install_hook pre-push <<'EOF'
#!/usr/bin/env bash
node "$repo/scripts/check-project-quality-gates.mjs" --require-push-gate "$repo"
EOF
`);
write(path.join(gateHooks, 'pre-push'), `#!/usr/bin/env bash
repo="$(git rev-parse --show-toplevel)"
node "$repo/scripts/check-project-quality-gates.mjs" --require-push-gate "$repo"
`, 0o755);
write(path.join(gateWorktree, '.no-mistakes.yaml'), 'commands:\n  test: "node scripts/check-hard-eng-full-repo.mjs"\n  lint: "node scripts/check-project-quality-gates.mjs --require-push-gate ."\n  format: "node scripts/format-hard-eng.mjs ."\n');
result = run(process.execPath, [script, '--allow-missing-no-mistakes-remote', '--json', gateWorktree]);
payload = JSON.parse(result.stdout);
assert.deepEqual(payload.blockers, []);
assert.equal(payload.repos[0].hookReady, true);
assert.equal(payload.repos[0].qualityGate, true);

const helperScriptsWithSpaces = path.join(tmp, 'helper scripts with spaces', 'scripts');
const spacedHelper = path.join(helperScriptsWithSpaces, 'check-no-mistakes-projects.mjs');
fs.mkdirSync(helperScriptsWithSpaces, { recursive: true });
fs.copyFileSync(script, spacedHelper);
write(path.join(helperScriptsWithSpaces, 'ensure-worktree-ready.sh'), '#!/usr/bin/env sh\nexit 0\n', 0o755);
write(path.join(helperScriptsWithSpaces, 'check-project-quality-gates.mjs'), '#!/usr/bin/env node\nprocess.exit(0);\n', 0o755);
const spacedHelperRepo = path.join(tmp, 'spaced-helper-repo');
initRepo(spacedHelperRepo);
result = run(process.execPath, [spacedHelper, '--json', spacedHelperRepo]);
payload = JSON.parse(result.stdout);
assert.deepEqual(payload.blockers, []);
assert.equal(payload.repos[0].hookReady, true);
assert.equal(payload.repos[0].qualityGate, true);

console.log('no-mistakes-projects: pass');
