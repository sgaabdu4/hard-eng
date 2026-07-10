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

const oldPolicyLine = '-| `no-mistakes-required` | The PR contains passed no-mistakes evidence from `sgaabdu4` for the current head before review or merge. Owner PRs can use the managed PR body block from `integrations/no-mistakes/scripts/repair-pr-evidence.mjs` when it says `No open no-mistakes findings`; outside PRs need a `sgaabdu4` PR comment or review with the current head SHA plus `No open no-mistakes findings` or `outcome: checks-passed`. Same-repo owner PRs that only update `vendor/skill-upstreams/<name>` gitlinks, plus the automated `VERSION` and README alpha-version bump, pass this check without no-mistakes evidence. |';
const newPolicyLine = '+| `no-mistakes-required` | Code/config PRs require passed no-mistakes evidence from `sgaabdu4` for the current head before review or merge. Owner PRs can use the managed PR body block from `integrations/no-mistakes/scripts/repair-pr-evidence.mjs` when it says `No open no-mistakes findings`; outside PRs need a `sgaabdu4` PR comment or review with the current head SHA plus `No open no-mistakes findings` or `outcome: checks-passed`. Same-repo owner PRs that update pinned skill gitlinks and exact deterministic refresh companions use deterministic vendor-integrity and CI proof instead; matching `VERSION` and README alpha-version bumps may be omitted, but if included they must pass the version contract. Other code/config changes still require no-mistakes. |';

function makeReadmePolicyVersionFile(from, to) {
  return {
    filename: 'README.md',
    status: 'modified',
    patch: [oldPolicyLine, newPolicyLine, makeReadmeVersionFile(from, to).patch].join('\n'),
  };
}

const refreshSdkRouteFile = {
  filename: 'skills/sentry-sdk-setup/SKILL.md',
  status: 'modified',
  patch: '@@ -11 +11 @@\n-`../../vendor/skill-upstreams/sentry-for-ai/skills/sentry-sdk-setup/SKILL.md`.\n+`../../vendor/skill-upstreams/sentry-for-ai/skills/sentry-get-started/SKILL.md`.',
};

const refreshWorkflowRouteFile = {
  filename: 'skills/sentry-workflow/references/upstream-routing.md',
  status: 'modified',
  patch: '@@ -8 +8 @@\n-| SDK installation or basic error monitoring | `../../../vendor/skill-upstreams/sentry-for-ai/skills/sentry-sdk-setup/SKILL.md` |\n+| SDK installation or basic error monitoring | `../../../vendor/skill-upstreams/sentry-for-ai/skills/sentry-get-started/SKILL.md` |',
};

const refreshProductFile = {
  filename: 'PRODUCT.md',
  status: 'modified',
  patch: '@@ -102 +102,2 @@\n-  submodule-only exemption, and `integrations/no-mistakes` guardrail helpers\n+  exemption for pure gitlink refreshes and exact deterministic refresh\n+  companions, plus `integrations/no-mistakes` guardrail helpers',
};

const refreshSetupContractFile = {
  filename: 'tests/setup-uninstall-contract.test.mjs',
  status: 'modified',
  patch: "@@ -125 +125 @@\n-assertIncludes(readme, 'The PR contains passed no-mistakes evidence from `sgaabdu4` for the current head before review or merge.', 'README must document owner-authored no-mistakes evidence');\n+assertIncludes(readme, 'Code/config PRs require passed no-mistakes evidence from `sgaabdu4` for the current head before review or merge.', 'README must document owner-authored no-mistakes evidence');",
};

const refreshAgentsContractFile = {
  filename: 'tests/agents-md-contract.test.mjs',
  status: 'modified',
  patch: [
    '@@ -291,2 +291,2 @@',
    "-assertIncludes(readmeText, '| `no-mistakes-required` | The PR contains passed no-mistakes evidence from `sgaabdu4` for the current head before review or merge.');",
    "-assertIncludes(readmeText, 'Same-repo owner PRs that only update `vendor/skill-upstreams/<name>` gitlinks, plus the automated `VERSION` and README alpha-version bump, pass this check without no-mistakes evidence.');",
    "+assertIncludes(readmeText, '| `no-mistakes-required` | Code/config PRs require passed no-mistakes evidence from `sgaabdu4` for the current head before review or merge.');",
    "+assertIncludes(readmeText, 'Same-repo owner PRs that update pinned skill gitlinks and exact deterministic refresh companions use deterministic vendor-integrity and CI proof instead; matching `VERSION` and README alpha-version bumps may be omitted, but if included they must pass the version contract. Other code/config changes still require no-mistakes.');",
  ].join('\n'),
};

const refreshPolicyWorkflowFile = {
  filename: '.github/workflows/no-mistakes-required.yml',
  status: 'modified',
  patch: [
    '@@ -117 +117,10 @@',
    '-              const lines = changedPatchLines(file);',
    '+              let lines = changedPatchLines(file);',
    '@@ -134,0 +144,60 @@',
    '+            function isDeterministicRefreshCompanionFile(file) {',
    '@@ -138 +207,2 @@',
    '-                || isReadmeVersionBump(file);',
    '+                || isReadmeVersionBump(file)',
    '+                || isDeterministicRefreshCompanionFile(file);',
    '@@ -152,0 +223,9 @@',
    '+              const hasVersionMetadata = files.some((file) => file.filename === `VERSION`);',
    '+              const releaseMetadataValid = !hasVersionMetadata;',
    '@@ -155,4 +234 @@',
    '-                && Boolean(versionBump)',
    '-                && Boolean(readmeVersionBump)',
    '-                && versionBump.from === readmeVersionBump.from',
    '-                && versionBump.to === readmeVersionBump.to',
    '+                && releaseMetadataValid',
  ].join('\n'),
};

const refreshTestFile = {
  filename: 'tests/no-mistakes-required-workflow.test.mjs',
  status: 'modified',
  patch: "@@ -117,0 +118,5 @@\n+result = await runCase({ files: [submoduleFile] });\n+assert.deepEqual(result.failures, []);\n+assert.equal(result.statuses.at(-1).state, 'success');\n+assert.match(result.statuses.at(-1).description, /submodule-only update/);\n+\n@@ -214,0 +220,13 @@\n+result = await runCase({\n+  files: [\n+    submoduleFile,\n+    {\n+      filename: '.github/workflows/no-mistakes-required.yml',\n+      status: 'modified',\n+      patch: '@@ -48,1 +48,1 @@\\n-const oldPolicy = true;\\n+const newPolicy = true;',\n+    },\n+  ],\n+});\n+assert.equal(result.statuses.at(-1).state, 'failure');\n+assert.match(result.failures.at(-1), /Missing passed no-mistakes evidence/);\n+",
};

const versionFile = makeVersionFile('0.1.0-alpha.11', '0.1.0-alpha.14');
const readmeVersionFile = makeReadmeVersionFile('0.1.0-alpha.11', '0.1.0-alpha.14');
const readmePolicyVersionFile = makeReadmePolicyVersionFile('0.1.0-alpha.11', '0.1.0-alpha.14');

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

for (const [name, companion] of [
  ['Sentry SDK route', refreshSdkRouteFile],
  ['Sentry workflow route', refreshWorkflowRouteFile],
  ['PRODUCT companion', refreshProductFile],
  ['setup contract companion', refreshSetupContractFile],
  ['agents contract companion', refreshAgentsContractFile],
  ['policy workflow companion', refreshPolicyWorkflowFile],
  ['workflow test companion', refreshTestFile],
]) {
  result = await runCase({ files: [submoduleFile, versionFile, readmePolicyVersionFile, companion] });
  assert.deepEqual(result.failures, [], name);
  assert.equal(result.statuses.at(-1).state, 'success', name);
  assert.match(result.statuses.at(-1).description, /submodule-only update/, name);
}

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
