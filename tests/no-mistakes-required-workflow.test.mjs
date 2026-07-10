import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';

const repo = process.cwd();
const workflow = fs.readFileSync(path.join(repo, '.github', 'workflows', 'no-mistakes-required.yml'), 'utf8');
const marker = '          script: |\n';
const start = workflow.indexOf(marker);
assert.notEqual(start, -1, 'workflow must contain github-script body');

const script = workflow
  .slice(start + marker.length)
  .split('\n')
  .map((line) => line.startsWith('            ') ? line.slice(12) : line)
  .join('\n');

const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor;
const runWorkflowScript = new AsyncFunction('github', 'context', 'core', 'process', script);

const oldSha = 'a'.repeat(40);
const newSha = 'b'.repeat(40);
const headSha = 'c'.repeat(40);

const submoduleFile = {
  filename: 'vendor/skill-upstreams/appwrite-backend',
  status: 'modified',
  patch: `@@ -1 +1 @@\n-Subproject commit ${oldSha}\n+Subproject commit ${newSha}`,
};

function makeVersionFile(from, to) {
  return {
    filename: 'VERSION',
    status: 'modified',
    patch: `@@ -1 +1 @@\n-${from}\n+${to}`,
  };
}

function badgeValue(version) {
  return version.replace('-alpha.', '--alpha.');
}

function makeReadmeVersionFile(from, to) {
  return {
    filename: 'README.md',
    status: 'modified',
    patch: [
      '@@ -27,7 +27,7 @@',
      `-[![Version](https://img.shields.io/badge/version-${badgeValue(from)}-f59e0b)](#versioning)`,
      `+[![Version](https://img.shields.io/badge/version-${badgeValue(to)}-f59e0b)](#versioning)`,
      '@@ -199,7 +199,7 @@',
      `-Current version: \`${from}\` from [VERSION](VERSION). The matching Git tag is \`v${from}\`.`,
      `+Current version: \`${to}\` from [VERSION](VERSION). The matching Git tag is \`v${to}\`.`,
    ].join('\n'),
  };
}

const versionFile = makeVersionFile('0.1.0-alpha.11', '0.1.0-alpha.14');
const readmeVersionFile = makeReadmeVersionFile('0.1.0-alpha.11', '0.1.0-alpha.14');

function buildGithub({ files, prUser = 'sgaabdu4', headRepo = 'sgaabdu4/hard-eng' }) {
  const statuses = [];
  return {
    statuses,
    rest: {
      pulls: {
        get: async () => ({
          data: {
            head: { sha: headSha, repo: { full_name: headRepo } },
            user: { login: prUser },
            body: '',
          },
        }),
        listFiles: async () => files,
        listReviews: async () => [],
      },
      issues: {
        listComments: async () => [],
      },
      repos: {
        createCommitStatus: async (status) => {
          statuses.push(status);
        },
      },
    },
    paginate: async (method, params) => method(params),
  };
}

async function runCase(options) {
  const prNumber = options.prNumber ?? 14;
  const github = buildGithub(options);
  const failures = [];
  const core = {
    info() {},
    warning() {},
    setFailed(message) {
      failures.push(message);
    },
  };
  await runWorkflowScript(
    github,
    {
      payload: { pull_request: { number: prNumber } },
      repo: { owner: 'sgaabdu4', repo: 'hard-eng' },
      runId: 123,
    },
    core,
    { env: { REQUIRED_AUTHOR: 'sgaabdu4', GITHUB_SERVER_URL: 'https://github.com' } },
  );
  return { failures, statuses: github.statuses };
}

let result = await runCase({ files: [submoduleFile, versionFile, readmeVersionFile] });
assert.deepEqual(result.failures, []);
assert.equal(result.statuses.at(-1).state, 'success');
assert.match(result.statuses.at(-1).description, /submodule-only update/);

result = await runCase({ files: [submoduleFile] });
assert.deepEqual(result.failures, []);
assert.equal(result.statuses.at(-1).state, 'success');
assert.match(result.statuses.at(-1).description, /submodule-only update/);

result = await runCase({
  files: [
    submoduleFile,
    makeVersionFile('0.1.0-alpha.14', '0.1.0-alpha.15'),
    makeReadmeVersionFile('0.1.0-alpha.14', '0.1.0-alpha.15'),
  ],
});
assert.deepEqual(result.failures, []);
assert.equal(result.statuses.at(-1).state, 'success');
assert.match(result.statuses.at(-1).description, /submodule-only update/);

for (const [name, from, to] of [
  ['downgrade', '0.1.0-alpha.11', '0.1.0-alpha.10'],
  ['patch change', '0.1.0-alpha.11', '0.1.1-alpha.14'],
  ['minor change', '0.1.0-alpha.11', '0.2.0-alpha.14'],
  ['arbitrary alpha jump', '0.1.0-alpha.11', '0.1.0-alpha.15'],
  ['missing PR-number floor', '0.1.0-alpha.11', '0.1.0-alpha.12'],
]) {
  result = await runCase({
    files: [
      submoduleFile,
      makeVersionFile(from, to),
      makeReadmeVersionFile(from, to),
    ],
  });
  assert.equal(result.statuses.at(-1).state, 'failure', name);
  assert.match(result.failures.at(-1), /Missing passed no-mistakes evidence/, name);
}

result = await runCase({
  files: [
    submoduleFile,
    versionFile,
    {
      filename: 'README.md',
      status: 'modified',
      patch: [
        '@@ -27,7 +27,7 @@',
        '-[![Version](https://img.shields.io/badge/version-0.1.0--alpha.11-f59e0b)](#versioning)',
        '+[![Version](https://img.shields.io/badge/version-0.1.0--alpha.14-f59e0b)](#versioning)',
      ].join('\n'),
    },
  ],
});
assert.equal(result.statuses.at(-1).state, 'failure');
assert.match(result.failures.at(-1), /Missing passed no-mistakes evidence/);

result = await runCase({
  files: [
    submoduleFile,
    versionFile,
    {
      filename: 'README.md',
      status: 'modified',
      patch: [
        '@@ -27,7 +27,7 @@',
        '-[![Version](https://img.shields.io/badge/version-0.1.0--alpha.11-f59e0b)](#versioning)',
        '+[![Version](https://img.shields.io/badge/version-0.1.0--alpha.13-f59e0b)](#versioning)',
        '@@ -199,7 +199,7 @@',
        '-Current version: `0.1.0-alpha.11` from [VERSION](VERSION). The matching Git tag is `v0.1.0-alpha.11`.',
        '+Current version: `0.1.0-alpha.13` from [VERSION](VERSION). The matching Git tag is `v0.1.0-alpha.13`.',
      ].join('\n'),
    },
  ],
});
assert.equal(result.statuses.at(-1).state, 'failure');
assert.match(result.failures.at(-1), /Missing passed no-mistakes evidence/);

result = await runCase({
  files: [
    submoduleFile,
    versionFile,
    {
      filename: 'README.md',
      status: 'modified',
      patch: [
        '@@ -27,7 +27,7 @@',
        '-[![Version](https://img.shields.io/badge/version-0.1.0--alpha.11-f59e0b)](#versioning)',
        '+[![Version](https://img.shields.io/badge/version-0.1.0--alpha.14-f59e0b)](#versioning)',
        '@@ -199,7 +199,7 @@',
        '-Current version: `0.1.0-alpha.11` from [VERSION](VERSION). The matching Git tag is `v0.1.0-alpha.11`.',
        '+Current version: `0.1.0-alpha.13` from [VERSION](VERSION). The matching Git tag is `v0.1.0-alpha.13`.',
      ].join('\n'),
    },
  ],
});
assert.equal(result.statuses.at(-1).state, 'failure');
assert.match(result.failures.at(-1), /Missing passed no-mistakes evidence/);

result = await runCase({ files: [submoduleFile, readmeVersionFile] });
assert.equal(result.statuses.at(-1).state, 'failure');
assert.match(result.failures.at(-1), /Missing passed no-mistakes evidence/);

result = await runCase({ files: [submoduleFile, versionFile] });
assert.equal(result.statuses.at(-1).state, 'failure');
assert.match(result.failures.at(-1), /Missing passed no-mistakes evidence/);

result = await runCase({
  files: [
    submoduleFile,
    {
      filename: '.github/workflows/no-mistakes-required.yml',
      status: 'modified',
      patch: '@@ -48,1 +48,1 @@\n-const oldPolicy = true;\n+const newPolicy = true;',
    },
  ],
});
assert.equal(result.statuses.at(-1).state, 'failure');
assert.match(result.failures.at(-1), /Missing passed no-mistakes evidence/);

result = await runCase({
  files: [
    submoduleFile,
    {
      filename: 'README.md',
      status: 'modified',
      patch: '@@ -1 +1 @@\n-# Hard Eng\n+# Hard Eng changed',
    },
  ],
});
assert.equal(result.statuses.at(-1).state, 'failure');
assert.match(result.failures.at(-1), /Missing passed no-mistakes evidence/);

result = await runCase({
  files: [submoduleFile, versionFile, readmeVersionFile],
  headRepo: 'someone-else/hard-eng',
});
assert.equal(result.statuses.at(-1).state, 'failure');

result = await runCase({
  files: [submoduleFile, versionFile, readmeVersionFile],
  prUser: 'someone-else',
});
assert.equal(result.statuses.at(-1).state, 'failure');

console.log('no-mistakes-required-workflow: pass');
