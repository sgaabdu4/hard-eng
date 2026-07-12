import test from 'node:test';
import assert from 'node:assert/strict';
import {
  observePublicationPreparation,
  observeRemotePublication,
} from '../../plugins/hard-eng/runtime/lib/publication-observer.mjs';
import { sha256 } from '../../plugins/hard-eng/runtime/lib/canonical.mjs';

const commit = 'a'.repeat(40);
const baseCommit = 'b'.repeat(40);
const githubRemote = 'git@github.com:example/hard-eng.git';

function publication(overrides = {}) {
  return {
    mode: 'direct-main',
    commit,
    remote_ref: 'refs/remotes/origin/main',
    ...overrides,
  };
}

function githubGit(repo, args) {
  if (args[0] === 'remote') return githubRemote;
  if (args[0] === 'ls-remote') return `${commit}\trefs/heads/main`;
  throw new Error(`Unexpected Git fixture: ${repo} ${args.join(' ')}`);
}

function greenGitHub(endpoint) {
  if (endpoint.includes('/check-runs')) return {
    check_runs: [
      { name: 'check', status: 'completed', conclusion: 'success', app: { slug: 'github-actions' } },
      { name: 'security', status: 'completed', conclusion: 'success', app: { slug: 'github-actions' } },
    ],
  };
  if (endpoint.endsWith('/branches/main/protection')) return {
    required_status_checks: { strict: true, contexts: ['check'] },
    enforce_admins: { enabled: true },
    allow_force_pushes: { enabled: false },
    allow_deletions: { enabled: false },
  };
  if (endpoint.includes('/rules/branches/main')) return [
    { type: 'required_status_checks', ruleset_source_type: 'Repository', ruleset_id: 42 },
  ];
  throw new Error(`Unexpected GitHub fixture: ${endpoint}`);
}

function greenPullRequest(endpoint, options) {
  if (endpoint.includes('/check-runs')) return greenGitHub(endpoint);
  if (endpoint.endsWith('/pulls/42')) return {
    number: 42,
    state: 'open',
    draft: false,
    head: { sha: commit, ref: 'feature/hard-eng' },
    base: { ref: 'main' },
  };
  if (endpoint === 'graphql') {
    assert.equal(options.variables.number, 42);
    return {
      data: { repository: { pullRequest: { reviewThreads: {
        nodes: [{ isResolved: true }, { isResolved: true }],
        pageInfo: { hasNextPage: false, endCursor: null },
      } } } },
    };
  }
  throw new Error(`Unexpected GitHub fixture: ${endpoint}`);
}

function directPreflight() {
  return observePublicationPreparation('/fixture', publication(), {
    head: baseCommit,
    origin_main: baseCommit,
    remote: { url_digest: sha256(githubRemote) },
  }, {
    readGit: (repo, args) => args[0] === 'remote'
      ? githubRemote
      : `${baseCommit}\trefs/heads/main`,
    readGh: greenGitHub,
  });
}

function nonMainPreflight(value, remoteUrl) {
  return observePublicationPreparation('/fixture', value, {
    remote: { url_digest: sha256(remoteUrl) },
  }, { readGit: () => remoteUrl });
}

test('GitHub observer replaces caller assertions with exact-SHA checks and live protection evidence', () => {
  const preflight = directPreflight();
  const observed = observeRemotePublication('/fixture', publication({
    ci: { status: 'pass', commit, evidence_digest: 'f'.repeat(64) },
    protections: { status: 'restored', evidence_digest: 'e'.repeat(64) },
  }), { readGit: githubGit, readGh: greenGitHub, preflight });
  assert.equal(observed.remote_head, commit);
  assert.equal(observed.current, true);
  assert.equal(observed.ci.observer, 'github');
  assert.equal(observed.ci.status, 'pass');
  assert.equal(observed.protections.observer, 'github');
  assert.equal(observed.protections.status, 'restored');
  assert.equal(observed.protections.before_evidence_digest, observed.protections.evidence_digest);
  assert.match(observed.remote_observation_digest, /^[a-f0-9]{64}$/);
  assert.notEqual(observed.ci.evidence_digest, 'f'.repeat(64));
  assert.notEqual(observed.protections.evidence_digest, 'e'.repeat(64));
});

test('direct-main preparation binds current main and protection/rules restoration', () => {
  const preflight = directPreflight();
  assert.equal(preflight.remote_head_before, baseCommit);
  assert.equal(preflight.protections.status, 'captured');
  assert.match(preflight.evidence_digest, /^[a-f0-9]{64}$/);

  assert.throws(() => observeRemotePublication('/fixture', publication(), {
    readGit: githubGit,
    preflight,
    readGh: (endpoint) => {
      if (endpoint.includes('/rules/branches/main')) return [{ type: 'changed-rule' }];
      return greenGitHub(endpoint);
    },
  }), /protection|rules.*restored/i);
  assert.throws(() => observePublicationPreparation('/fixture', publication(), {
    head: 'c'.repeat(40),
    origin_main: baseCommit,
    remote: { url_digest: sha256(githubRemote) },
  }, { readGit: githubGit, readGh: greenGitHub }), /current origin\/main|candidate head/i);
});

test('direct-main snapshot supports rulesets without classic branch protection', () => {
  const noClassic = (endpoint) => {
    if (endpoint.includes('/check-runs')) return greenGitHub(endpoint);
    if (endpoint.endsWith('/branches/main/protection')) return null;
    if (endpoint.includes('/rules/branches/main')) return [{ type: 'pull_request' }];
    throw new Error(`Unexpected GitHub fixture: ${endpoint}`);
  };
  const preflight = observePublicationPreparation('/fixture', publication(), {
    head: baseCommit,
    origin_main: baseCommit,
    remote: { url_digest: sha256(githubRemote) },
  }, {
    readGit: (repo, args) => args[0] === 'remote'
      ? githubRemote
      : `${baseCommit}\trefs/heads/main`,
    readGh: noClassic,
  });
  const observed = observeRemotePublication('/fixture', publication(), {
    readGit: githubGit,
    readGh: noClassic,
    preflight,
  });
  assert.equal(observed.protections.status, 'restored');
});

test('GitHub observer fails closed on pending CI, wrong main mode, or unsupported providers', () => {
  assert.throws(() => observeRemotePublication('/fixture', publication(), {
    readGit: githubGit,
    preflight: directPreflight(),
    readGh: (endpoint) => endpoint.includes('/check-runs')
      ? { check_runs: [{ name: 'check', status: 'in_progress', conclusion: null, app: { slug: 'github-actions' } }] }
      : {},
  }), /checks.*green/i);
  assert.throws(() => observeRemotePublication('/fixture', publication({
    mode: 'branch', remote_ref: 'refs/remotes/origin/main',
  }), { readGit: githubGit, readGh: greenGitHub }), /cannot bypass|cannot target/i);
  assert.throws(() => observePublicationPreparation('/fixture', publication(), {
    head: baseCommit,
    origin_main: baseCommit,
    remote: { url_digest: sha256('https://gitlab.example.invalid/example/repo.git') },
  }, {
    readGit: (repo, args) => args[0] === 'remote'
      ? 'https://gitlab.example.invalid/example/repo.git'
      : `${baseCommit}\trefs/heads/main`,
    readGh: greenGitHub,
  }), /GitHub origin observer/i);
});

test('GitHub observer consumes every paginated check-run page', () => {
  const preflight = directPreflight();
  const pages = [{
    total_count: 2,
    check_runs: [{ name: 'check', status: 'completed', conclusion: 'success', app: { slug: 'github-actions' } }],
  }, {
    total_count: 2,
    check_runs: [{ name: 'security', status: 'completed', conclusion: 'success', app: { slug: 'github-actions' } }],
  }];
  const observed = observeRemotePublication('/fixture', publication(), {
    readGit: githubGit,
    preflight,
    readGh: (endpoint) => endpoint.includes('/check-runs') ? pages : greenGitHub(endpoint),
  });
  assert.equal(observed.ci.status, 'pass');
  assert.throws(() => observeRemotePublication('/fixture', publication(), {
    readGit: githubGit,
    preflight,
    readGh: (endpoint) => endpoint.includes('/check-runs')
      ? [{ total_count: 2, check_runs: pages[0].check_runs }]
      : greenGitHub(endpoint),
  }), /complete|check.*green/i);
});

test('local Git can prove a non-main branch without pretending to observe hosted CI', () => {
  const value = publication({
    mode: 'branch', remote_ref: 'refs/remotes/origin/fixture',
  });
  const branch = observeRemotePublication('/fixture', value, {
    readGit: (repo, args) => args[0] === 'remote'
      ? '/tmp/local.git'
      : `${commit}\trefs/heads/fixture`,
    preflight: nonMainPreflight(value, '/tmp/local.git'),
  });
  assert.equal(branch.ci.observer, 'local-git');
  assert.equal(branch.protections.status, 'not-applicable');
  assert.throws(() => observePublicationPreparation('/fixture', publication(), {
    head: baseCommit,
    origin_main: baseCommit,
    remote: { url_digest: sha256('/tmp/local.git') },
  }, { readGit: () => '/tmp/local.git' }), /GitHub origin observer/i);
});

test('GitHub PR observer binds the exact head and rejects unresolved review threads', () => {
  const pr = publication({
    mode: 'pr',
    remote_ref: 'refs/remotes/origin/feature/hard-eng',
    pr_number: 42,
  });
  const readGit = (repo, args) => args[0] === 'remote'
    ? 'git@github.com:example/hard-eng.git'
    : `${commit}\trefs/heads/feature/hard-eng`;
  const preflight = nonMainPreflight(pr, githubRemote);
  const observed = observeRemotePublication('/fixture', pr, { readGit, readGh: greenPullRequest, preflight });
  assert.deepEqual(observed.pull_request, {
    number: 42,
    state: 'open',
    draft: false,
    head_commit: commit,
    head_ref: 'feature/hard-eng',
    base_ref: 'main',
    unresolved_review_threads: 0,
    evidence_digest: observed.pull_request.evidence_digest,
  });
  assert.match(observed.pull_request.evidence_digest, /^[a-f0-9]{64}$/);

  assert.throws(() => observeRemotePublication('/fixture', pr, {
    readGit,
    preflight,
    readGh: (endpoint, options) => {
      const value = greenPullRequest(endpoint, options);
      if (endpoint === 'graphql') value.data.repository.pullRequest.reviewThreads.nodes[0].isResolved = false;
      return value;
    },
  }), /unresolved review thread/i);
  assert.throws(() => observePublicationPreparation('/fixture', { ...pr, pr_number: undefined }, {
    remote: { url_digest: sha256(githubRemote) },
  }, { readGit: () => githubRemote, readGh: greenPullRequest }), /pull request number/i);
});
