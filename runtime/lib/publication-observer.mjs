import { execFileSync } from 'node:child_process';
import { digestValue, sha256 } from './canonical.mjs';

function git(repo, args) {
  const env = Object.fromEntries(
    [
      'PATH', 'HOME', 'TMPDIR', 'TMP', 'TEMP', 'SHELL', 'LANG', 'LC_ALL',
      'SSH_AUTH_SOCK', 'GIT_SSH_COMMAND', 'GIT_ASKPASS',
    ]
      .filter((key) => process.env[key] !== undefined)
      .map((key) => [key, process.env[key]]),
  );
  try {
    return execFileSync('git', ['-C', repo, ...args], {
      encoding: 'utf8',
      timeout: 30_000,
      maxBuffer: 1024 * 1024,
      env: { ...env, GIT_TERMINAL_PROMPT: '0' },
      stdio: ['ignore', 'pipe', 'pipe'],
    }).trim();
  } catch {
    throw new Error('Live origin observation failed; publication currentness is unproven.');
  }
}

function githubRepository(remoteUrl) {
  const match = /^(?:https?:\/\/github\.com\/|git@github\.com:|ssh:\/\/git@github\.com\/)([^/\s:]+)\/([^/\s]+?)(?:\.git)?$/.exec(remoteUrl);
  return match ? { owner: match[1], repo: match[2] } : null;
}

const REVIEW_THREADS_QUERY = `
query($owner: String!, $repo: String!, $number: Int!, $cursor: String) {
  repository(owner: $owner, name: $repo) {
    pullRequest(number: $number) {
      reviewThreads(first: 100, after: $cursor) {
        nodes { isResolved }
        pageInfo { hasNextPage endCursor }
      }
    }
  }
}`;

function ghJson(endpoint, {
  query,
  variables = {},
  allowNotFound = false,
  paginate = false,
} = {}) {
  const env = Object.fromEntries(
    ['PATH', 'HOME', 'GH_HOST', 'GH_TOKEN', 'GITHUB_TOKEN', 'XDG_CONFIG_HOME']
      .filter((key) => process.env[key] !== undefined)
      .map((key) => [key, process.env[key]]),
  );
  try {
    const args = ['api', endpoint];
    if (query) args.push('-f', `query=${query}`);
    for (const [name, value] of Object.entries(variables)) {
      if (value !== null && value !== undefined) args.push('-F', `${name}=${value}`);
    }
    if (paginate) args.push('--paginate', '--slurp');
    return JSON.parse(execFileSync('gh', args, {
      encoding: 'utf8', timeout: 30_000, maxBuffer: 8 * 1024 * 1024,
      env, stdio: ['ignore', 'pipe', 'pipe'],
    }));
  } catch (error) {
    if (allowNotFound && /(?:HTTP\s+404|Not Found)/i.test(String(error?.stderr ?? ''))) return null;
    throw new Error('GitHub publication evidence could not be observed through the authenticated gh CLI.');
  }
}

function observePullRequest(repository, base, publication, branch, readGh) {
  if (!Number.isSafeInteger(publication.pr_number) || publication.pr_number <= 0) {
    throw new Error('PR publication requires a positive pull request number.');
  }
  const pull = readGh(`${base}/pulls/${publication.pr_number}`);
  if (
    pull?.number !== publication.pr_number
    || pull.state !== 'open'
    || pull.draft !== false
    || pull.head?.sha !== publication.commit
    || pull.head?.ref !== branch
    || typeof pull.base?.ref !== 'string'
    || !pull.base.ref
  ) throw new Error('GitHub pull request is not an open, ready, exact-head publication.');
  if (pull.mergeable === false) throw new Error('GitHub pull request is currently unmergeable.');

  let cursor = null;
  let unresolved = 0;
  let pages = 0;
  do {
    pages += 1;
    if (pages > 10) throw new Error('GitHub pull request review-thread inventory exceeds the bounded observer limit.');
    const response = readGh('graphql', {
      query: REVIEW_THREADS_QUERY,
      variables: {
        owner: repository.owner,
        repo: repository.repo,
        number: publication.pr_number,
        cursor,
      },
    });
    const threads = response?.data?.repository?.pullRequest?.reviewThreads;
    if (!threads || !Array.isArray(threads.nodes) || typeof threads.pageInfo?.hasNextPage !== 'boolean') {
      throw new Error('GitHub pull request review threads could not be observed completely.');
    }
    for (const thread of threads.nodes) {
      if (typeof thread?.isResolved !== 'boolean') throw new Error('GitHub pull request review-thread state is invalid.');
      if (!thread.isResolved) unresolved += 1;
    }
    cursor = threads.pageInfo.hasNextPage ? threads.pageInfo.endCursor : null;
    if (threads.pageInfo.hasNextPage && (typeof cursor !== 'string' || !cursor)) {
      throw new Error('GitHub pull request review-thread pagination is incomplete.');
    }
  } while (cursor);
  if (unresolved > 0) throw new Error('GitHub pull request has an unresolved review thread.');

  const evidence = {
    number: publication.pr_number,
    state: pull.state,
    draft: pull.draft,
    head_commit: pull.head.sha,
    head_ref: pull.head.ref,
    base_ref: pull.base.ref,
    unresolved_review_threads: unresolved,
  };
  return { ...evidence, evidence_digest: digestValue(evidence) };
}

function githubProtectionSnapshot(base, branch, readGh) {
  const encoded = encodeURIComponent(branch);
  const classic = readGh(`${base}/branches/${encoded}/protection`, { allowNotFound: true });
  const rawRules = readGh(`${base}/rules/branches/${encoded}?per_page=100`, { paginate: true });
  const effectiveRules = Array.isArray(rawRules) && rawRules.every(Array.isArray)
    ? rawRules.flat()
    : rawRules;
  if (
    (classic !== null && (typeof classic !== 'object' || Array.isArray(classic)))
    || !Array.isArray(effectiveRules)
    || effectiveRules.length > 1_000
  ) {
    throw new Error('GitHub branch protection and effective rules could not be observed completely.');
  }
  const evidence = { classic, effective_rules: effectiveRules };
  return {
    status: 'captured',
    observer: 'github',
    evidence_digest: digestValue(evidence),
  };
}

function validatePreflight(preflight, publication, remoteUrlDigest) {
  if (!preflight || typeof preflight !== 'object' || Array.isArray(preflight)) {
    throw new Error('Publication requires a server-observed preparation receipt.');
  }
  const { evidence_digest: evidenceDigest, ...evidence } = preflight;
  if (!/^[a-f0-9]{64}$/i.test(evidenceDigest ?? '') || digestValue(evidence) !== evidenceDigest) {
    throw new Error('Publication preparation receipt is stale or invalid.');
  }
  if (
    preflight.mode !== publication.mode
    || preflight.remote_ref !== publication.remote_ref
    || preflight.remote_url_digest !== remoteUrlDigest
    || preflight.commit !== publication.commit
    || (publication.mode === 'pr' && preflight.pr_number !== publication.pr_number)
  ) throw new Error('Publication does not match its prepared mode, ref, PR, or remote.');
  return preflight;
}

function observeCheckRuns(base, commit, readGh) {
  const raw = readGh(`${base}/commits/${commit}/check-runs?per_page=100`, { paginate: true });
  const pages = Array.isArray(raw) ? raw : [raw];
  if (pages.length === 0 || pages.length > 10) throw new Error('GitHub check-run pagination is incomplete.');
  const runs = [];
  let total = null;
  for (const page of pages) {
    if (!page || !Array.isArray(page.check_runs)) throw new Error('GitHub check-run page is invalid.');
    if (Number.isInteger(page.total_count)) {
      if (total !== null && total !== page.total_count) throw new Error('GitHub check-run page totals disagree.');
      total = page.total_count;
    }
    runs.push(...page.check_runs);
  }
  if (runs.length > 1_000 || (total !== null && total !== runs.length)) {
    throw new Error('GitHub check-run pagination is incomplete.');
  }
  return runs;
}

function githubEvidence(remoteUrl, publication, branch, readGh, preflight) {
  const repository = githubRepository(remoteUrl);
  if (!repository) return null;
  const base = `repos/${repository.owner}/${repository.repo}`;
  const runs = observeCheckRuns(base, publication.commit, readGh);
  const canonical = runs.filter((run) => run.name === 'check');
  const accepted = new Set(['success', 'neutral', 'skipped']);
  if (
    canonical.length === 0
    || runs.some((run) => run.status !== 'completed' || !accepted.has(run.conclusion))
    || canonical.some((run) => run.conclusion !== 'success')
  ) throw new Error('GitHub checks do not prove the exact publication commit is green.');
  const ciSummary = runs.map((run) => ({
    name: run.name,
    status: run.status,
    conclusion: run.conclusion,
    app: run.app?.slug ?? null,
  })).sort((left, right) => `${left.name}\0${left.app}`.localeCompare(`${right.name}\0${right.app}`));
  let protections;
  if (publication.mode === 'direct-main') {
    const protection = githubProtectionSnapshot(base, branch, readGh);
    if (
      preflight.protections?.status !== 'captured'
      || preflight.protections.observer !== 'github'
      || preflight.protections.evidence_digest !== protection.evidence_digest
    ) throw new Error('GitHub branch protection and effective rules were not restored to the prepared state.');
    protections = {
      status: 'restored',
      observer: 'github',
      before_evidence_digest: preflight.protections.evidence_digest,
      evidence_digest: protection.evidence_digest,
    };
  } else {
    protections = {
      status: 'not-applicable',
      observer: 'github',
      evidence_digest: digestValue({ mode: publication.mode, branch }),
    };
  }
  const pullRequest = publication.mode === 'pr'
    ? observePullRequest(repository, base, publication, branch, readGh)
    : null;
  return {
    ci: {
      status: 'pass',
      commit: publication.commit,
      observer: 'github',
      evidence_digest: digestValue(ciSummary),
    },
    protections,
    pull_request: pullRequest,
  };
}

function providerEvidence(remoteUrl, publication, branch, readGh, preflight) {
  const github = githubEvidence(remoteUrl, publication, branch, readGh, preflight);
  if (github) return github;
  if (/^(?:file:\/\/|\/|\.\.?\/)/.test(remoteUrl) && publication.mode === 'branch') {
    return {
      ci: {
        status: 'pass', commit: publication.commit, observer: 'local-git',
        evidence_digest: digestValue({ branch, commit: publication.commit, provider: 'local-git' }),
      },
      protections: {
        status: 'not-applicable', observer: 'local-git',
        evidence_digest: digestValue({ branch, mode: publication.mode, provider: 'local-git' }),
      },
    };
  }
  throw new Error('The origin provider has no deterministic CI/protection observer.');
}

function targetBranch(publication) {
  const prefix = 'refs/remotes/origin/';
  if (typeof publication.remote_ref !== 'string' || !publication.remote_ref.startsWith(prefix)) {
    throw new Error('Publication must name an origin remote-tracking ref.');
  }
  const branch = publication.remote_ref.slice(prefix.length);
  if (!branch || branch.includes('..') || branch.startsWith('/') || branch.endsWith('/')) {
    throw new Error('Publication target branch is invalid.');
  }
  if (publication.mode === 'direct-main' && branch !== 'main') {
    throw new Error('Direct-main publication must target origin/main.');
  }
  if (publication.mode === 'branch' && branch === 'main') {
    throw new Error('A branch publication cannot bypass direct-main protections by targeting main.');
  }
  if (publication.mode === 'pr' && branch === 'main') {
    throw new Error('A pull request publication cannot use origin/main as its head branch.');
  }
  return branch;
}

export function observePublicationPreparation(repo, publication, candidate, {
  readGit = git,
  readGh = ghJson,
  preparedCommit,
} = {}) {
  if (!['branch', 'pr', 'direct-main'].includes(publication?.mode)) throw new Error('Publication preparation mode is invalid.');
  if (
    !preparedCommit
    || preparedCommit.commit !== publication.commit
    || !/^[a-f0-9]{40,64}$/i.test(preparedCommit.commit ?? '')
    || !/^[a-f0-9]{64}$/i.test(preparedCommit.commit_message_digest ?? '')
    || !/^[a-f0-9]{64}$/i.test(preparedCommit.commit_message_evidence_digest ?? '')
  ) throw new Error('Publication preparation requires the exact validated local commit and commit message.');
  const branch = targetBranch(publication);
  if (publication.mode === 'pr' && (!Number.isSafeInteger(publication.pr_number) || publication.pr_number <= 0)) {
    throw new Error('PR publication preparation requires a positive pull request number.');
  }
  const remoteUrl = readGit(repo, ['remote', 'get-url', 'origin']);
  const remoteUrlDigest = sha256(remoteUrl);
  if (candidate?.remote?.url_digest !== remoteUrlDigest) {
    throw new Error('Publication preparation remote differs from the approved candidate remote.');
  }
  let remoteHeadBefore = null;
  let protections;
  if (publication.mode === 'direct-main') {
    const repository = githubRepository(remoteUrl);
    if (!repository) throw new Error('Direct-main publication preparation requires a GitHub origin observer.');
    const remote = readGit(repo, ['ls-remote', '--exit-code', 'origin', `refs/heads/${branch}`]);
    const lines = remote.split(/\r?\n/).filter(Boolean);
    if (lines.length !== 1) throw new Error('Live origin returned an ambiguous pre-publication main ref.');
    const [head, ref] = lines[0].split(/\s+/);
    if (
      ref !== `refs/heads/${branch}`
      || head !== candidate?.origin_main
      || head !== candidate?.head
    ) throw new Error('Direct-main candidate head is not the current origin/main commit.');
    remoteHeadBefore = head;
    protections = githubProtectionSnapshot(`repos/${repository.owner}/${repository.repo}`, branch, readGh);
  } else {
    protections = {
      status: 'not-applicable',
      observer: githubRepository(remoteUrl) ? 'github' : 'local-git',
      evidence_digest: digestValue({ mode: publication.mode, branch }),
    };
  }
  const evidence = {
    mode: publication.mode,
    remote_ref: publication.remote_ref,
    ...(publication.mode === 'pr' ? { pr_number: publication.pr_number } : {}),
    remote_url_digest: remoteUrlDigest,
    remote_head_before: remoteHeadBefore,
    protections,
    commit: preparedCommit.commit,
    commit_message_digest: preparedCommit.commit_message_digest,
    commit_message_evidence_digest: preparedCommit.commit_message_evidence_digest,
  };
  return { ...evidence, evidence_digest: digestValue(evidence) };
}

export function observeRemotePublication(repo, publication, {
  readGit = git,
  readGh = ghJson,
  preflight = publication?.preflight,
} = {}) {
  if (!/^[a-f0-9]{40,64}$/i.test(publication?.commit ?? '')) throw new Error('Publication commit is invalid.');
  const branch = targetBranch(publication);
  const remoteUrl = readGit(repo, ['remote', 'get-url', 'origin']);
  const remote = readGit(repo, ['ls-remote', '--exit-code', 'origin', `refs/heads/${branch}`]);
  const lines = remote.split(/\r?\n/).filter(Boolean);
  if (lines.length !== 1) throw new Error('Live origin returned an ambiguous publication ref.');
  const [remoteHead, remoteRef] = lines[0].split(/\s+/);
  if (remoteRef !== `refs/heads/${branch}` || remoteHead !== publication.commit) {
    throw new Error('Live origin does not contain the exact publication commit at the target branch.');
  }
  const remoteUrlDigest = sha256(remoteUrl);
  const verifiedPreflight = validatePreflight(preflight, publication, remoteUrlDigest);
  const provider = providerEvidence(remoteUrl, publication, branch, readGh, verifiedPreflight);
  const observation = {
    remote_ref: publication.remote_ref,
    remote_head: remoteHead,
    remote_url_digest: remoteUrlDigest,
  };
  return {
    ...publication,
    remote_head: remoteHead,
    current: true,
    remote_url_digest: remoteUrlDigest,
    remote_observation_digest: digestValue(observation),
    preflight: verifiedPreflight,
    ci: provider.ci,
    protections: provider.protections,
    ...(provider.pull_request ? { pull_request: provider.pull_request } : {}),
    rollback: {
      strategy: 'revert-commit',
      target_commit: publication.commit,
      evidence_digest: digestValue({ strategy: 'revert-commit', target_commit: publication.commit }),
    },
  };
}
