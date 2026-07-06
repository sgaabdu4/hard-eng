import { spawnSync } from 'node:child_process';

function isObject(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

function latestPassedGuardrail(state, id) {
  return Array.isArray(state.guardrails)
    ? state.guardrails
      .filter((item) => item?.id === id && item?.status === 'passed')
      .sort((left, right) => (Number(right.sequence) || 0) - (Number(left.sequence) || 0))[0]
    : null;
}

function allStrings(value) {
  if (typeof value === 'string') return [value];
  if (Array.isArray(value)) return value.flatMap(allStrings);
  if (isObject(value)) return Object.values(value).flatMap(allStrings);
  return [];
}

function liveGuardrailText(guardrail) {
  return allStrings([guardrail?.command, guardrail?.evidence]).join(' ');
}

function extractValidatedHead(text) {
  const match = String(text || '').match(/\bvalidated head\b\s*[:=]?\s*`?([0-9a-f]{7,40})`?/i);
  return match?.[1] || '';
}

function git(repo, args) {
  return spawnSync('git', ['-C', repo, ...args], {
    encoding: 'utf8',
    maxBuffer: 1024 * 1024,
  });
}

function resolveGitRoot(repo, errors) {
  const result = git(repo, ['rev-parse', '--show-toplevel']);
  if (result.status !== 0) {
    errors.push(`live currentness cannot resolve git root from ${repo}`);
    return null;
  }
  return result.stdout.trim();
}

function resolveGitRevision(repo, revision) {
  const result = git(repo, ['rev-parse', '--verify', `${revision}^{commit}`]);
  if (result.status !== 0) return '';
  return result.stdout.trim();
}

function classifyShortStatusLine(line) {
  const trimmed = String(line || '').trimEnd();
  if (!trimmed) return null;
  const pathText = trimmed.length > 3 ? trimmed.slice(3).trim() : trimmed;
  const filePath = pathText.replace(/^"|"$/g, '').split(/\s+->\s+/).pop();
  const code = trimmed.slice(0, 2);
  const kind = filePath.startsWith('vendor/')
    ? 'vendor/submodule'
    : code.includes('?')
      ? 'untracked'
      : 'feature-or-unclassified';
  return { code, path: filePath, kind };
}

export function validateLiveCurrentness(state, errors, options = {}) {
  if (state.stage !== 'he-ship' || state.next?.ready !== true || state.next?.target !== 'loop-complete') return;
  const repoInput = options.liveRepo || options.root || process.cwd();
  const repoRoot = resolveGitRoot(repoInput, errors);
  if (!repoRoot) return;

  const headResult = git(repoRoot, ['rev-parse', 'HEAD']);
  if (headResult.status !== 0) {
    errors.push('he-ship live currentness cannot read git rev-parse HEAD');
    return;
  }
  const actualHead = headResult.stdout.trim();
  const currentness = latestPassedGuardrail(state, 'ship-currentness');
  const recordedHead = extractValidatedHead(liveGuardrailText(currentness));
  if (!recordedHead) {
    errors.push('he-ship live currentness requires ship-currentness evidence with validated head');
  } else if (resolveGitRevision(repoRoot, recordedHead) !== actualHead) {
    errors.push(`he-ship live currentness head mismatch: state records ${recordedHead}, git HEAD is ${actualHead}`);
  }

  const statusResult = git(repoRoot, ['status', '--short']);
  if (statusResult.status !== 0) {
    errors.push('he-ship live currentness cannot read git status --short');
    return;
  }
  const dirty = statusResult.stdout
    .split('\n')
    .map(classifyShortStatusLine)
    .filter(Boolean);
  if (dirty.length) {
    const groups = new Map();
    for (const item of dirty) {
      const values = groups.get(item.kind) || [];
      values.push(`${item.code.trim() || '??'} ${item.path}`);
      groups.set(item.kind, values);
    }
    const summary = Array.from(groups.entries())
      .map(([kind, values]) => `${kind}: ${values.slice(0, 8).join(', ')}${values.length > 8 ? ', ...' : ''}`)
      .join('; ');
    errors.push(`he-ship live currentness requires clean git status --short; mixed dirty state classified as ${summary}`);
  }
}
