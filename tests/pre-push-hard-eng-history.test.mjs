#!/usr/bin/env node
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';

const repo = path.resolve(new URL('..', import.meta.url).pathname);
const install = fs.readFileSync(path.join(repo, 'scripts', 'install.sh'), 'utf8');
const match = install.match(/install_hook pre-push <<'EOF'\n([\s\S]*?)\nEOF/);
assert.ok(match, 'install.sh must contain a pre-push hook heredoc');
const hookBody = match[1].replace(/^__HARD_ENG_INSTALL_REFRESH_ENV__\n/m, '');

function git(root, args) {
  const result = spawnSync('git', args, { cwd: root, encoding: 'utf8' });
  assert.equal(result.status, 0, `${args.join(' ')}\n${result.stderr}`);
  return result.stdout.trim();
}

function writeNodePass(file) {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, '#!/usr/bin/env node\nprocess.exit(0);\n');
}

function makeRepo(name) {
  const parent = fs.mkdtempSync(path.join(os.tmpdir(), `${name}-`));
  fs.mkdirSync(path.join(parent, '.agents'));
  const root = fs.realpathSync(path.join(parent, '.agents'));
  git(root, ['init', '-q']);
  git(root, ['config', 'user.email', 'hard-eng@example.invalid']);
  git(root, ['config', 'user.name', 'Hard Eng Test']);
  fs.mkdirSync(path.join(root, 'scripts'), { recursive: true });
  fs.mkdirSync(path.join(root, 'tests'), { recursive: true });
  for (const scriptName of ['check-hard-eng-artifacts.mjs', 'check-hard-eng-write-safety.mjs']) {
    fs.copyFileSync(path.join(repo, 'scripts', scriptName), path.join(root, 'scripts', scriptName));
  }
  for (const scriptName of ['check-project-naming.mjs', 'check-generated-assets.mjs', 'check-ssot-guardrails.mjs', 'check-vendor-skill-integrity.mjs', 'check-project-context-gates.mjs', 'check-project-quality-gates.mjs']) {
    writeNodePass(path.join(root, 'scripts', scriptName));
  }
  fs.writeFileSync(path.join(root, 'scripts', 'install.sh'), '#!/usr/bin/env bash\nexit 0\n');
  fs.chmodSync(path.join(root, 'scripts', 'install.sh'), 0o755);
  for (const testName of ['codex-config-sync.test.mjs', 'setup-uninstall-contract.test.mjs', 'uninstall-config-cleanup.test.mjs']) {
    writeNodePass(path.join(root, 'tests', testName));
  }
  const hook = path.join(root, '.git', 'hooks', 'pre-push');
  fs.writeFileSync(hook, hookBody);
  fs.chmodSync(hook, 0o755);
  return root;
}

function commitAll(root, message) {
  git(root, ['add', '.']);
  git(root, ['commit', '-m', message]);
  return git(root, ['rev-parse', 'HEAD']);
}

function runHook(root, stdin) {
  return spawnSync(path.join(root, '.git', 'hooks', 'pre-push'), {
    cwd: root,
    input: stdin,
    encoding: 'utf8',
  });
}

let root = makeRepo('hard-eng-prepush-artifact-ref');
commitAll(root, 'initial');
const artifactBase = git(root, ['rev-parse', 'HEAD']);
git(root, ['checkout', '-q', '-b', 'unsafe-artifact']);
fs.mkdirSync(path.join(root, 'artifacts', 'e2e', 'example-feature'), { recursive: true });
fs.writeFileSync(path.join(root, 'artifacts', 'e2e', 'example-feature', 'events.jsonl'), '{"email":"person@fixture.test","event":"login"}\n');
const unsafeArtifact = commitAll(root, 'unsafe artifact');
git(root, ['checkout', '-q', '-B', 'safe-main', artifactBase]);
let result = runHook(root, `refs/heads/unsafe-artifact ${unsafeArtifact} refs/heads/unsafe-artifact ${artifactBase}\n`);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /raw email <redacted>/);
assert.doesNotMatch(result.stderr, /customer@realco\.test/);

root = makeRepo('hard-eng-prepush-write-range');
commitAll(root, 'initial');
const writeBase = git(root, ['rev-parse', 'HEAD']);
fs.writeFileSync(path.join(root, 'scripts', 'purge-users.sh'), '#!/usr/bin/env bash\nappwrite users delete "$1"\n');
commitAll(root, 'unsafe write');
fs.writeFileSync(path.join(root, 'scripts', 'purge-users.sh'), '#!/usr/bin/env bash\nappwrite users list\n');
const safeHead = commitAll(root, 'safe head');
result = runHook(root, `refs/heads/main ${safeHead} refs/heads/main ${writeBase}\n`);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /hard-eng write safety/);
assert.match(result.stderr, /dry-run default/);

root = makeRepo('hard-eng-prepush-new-branch-introduced-only');
commitAll(root, 'initial');
fs.mkdirSync(path.join(root, 'artifacts', 'e2e', 'run'), { recursive: true });
fs.writeFileSync(path.join(root, 'artifacts', 'e2e', 'run', 'events.jsonl'), '{"email":"person@fixture.test","event":"login"}\n');
commitAll(root, 'old unsafe artifact');
fs.writeFileSync(path.join(root, 'artifacts', 'e2e', 'run', 'events.jsonl'), '{"event":"redacted"}\n');
const safeRemoteHead = commitAll(root, 'redact old artifact');
git(root, ['update-ref', 'refs/remotes/origin/main', safeRemoteHead]);
git(root, ['checkout', '-q', '-b', 'feature']);
fs.writeFileSync(path.join(root, 'scripts', 'list-users.sh'), '#!/usr/bin/env bash\nappwrite users list\n');
const featureHead = commitAll(root, 'safe feature');
result = runHook(root, `refs/heads/feature ${featureHead} refs/heads/feature 0000000000000000000000000000000000000000\n`);
assert.equal(result.status, 0, result.stderr);

console.log('pre-push-hard-eng-history: pass');
