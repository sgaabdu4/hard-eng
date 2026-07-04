const marker = 'Updates from [git push no-mistakes](https://github.com/kunchenguid/no-mistakes)';

function compactText(value, maxLength = 140) {
  const text = String(value || '').replace(/\s+/g, ' ').trim();
  if (text.length <= maxLength) return text;
  return `${text.slice(0, maxLength - 1)}...`;
}

function plainSummary(summary) {
  return String(summary || '')
    .replace(/<[^>]+>/g, '')
    .replace(/\s+/g, ' ')
    .trim();
}

function summaryIsResolved(summary) {
  const text = plainSummary(summary).toLowerCase();
  return (text.includes('✅') && text.includes('passed'))
    || (text.includes('✅') && text.includes('auto-fixed'));
}

function normalizeSha(value) {
  const sha = String(value || '').trim();
  return /^[0-9a-f]{40}$/i.test(sha) ? sha.toLowerCase() : '';
}

function escapeRegExp(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function hasCurrentHeadProof(body, expectedHeadSha) {
  const sha = normalizeSha(expectedHeadSha);
  if (!sha) return false;
  const escaped = escapeRegExp(sha);
  return [
    new RegExp(`\\bCurrent head:\\s*\`?${escaped}\`?\\b`, 'i'),
    new RegExp(`\\b(?:current|pr) head(?: sha)?:\\s*\`?${escaped}\`?\\b`, 'i'),
    new RegExp(`\\bheadRefOid\\b[^\\n]{0,80}\\b${escaped}\\b`, 'i'),
  ].some((pattern) => pattern.test(body));
}

export function parseNoMistakesPipelineStatus(body, expectedHeadSha = '') {
  const fullBody = String(body || '');
  const pipelineStart = fullBody.indexOf(marker);
  if (pipelineStart === -1) return [];

  const pipelineBody = fullBody.slice(pipelineStart);
  const summaries = [...pipelineBody.matchAll(/<summary>([\s\S]*?)<\/summary>/gi)]
    .map((match) => match[1]);
  if (summaries.length === 0) return [];

  const unresolved = summaries.find((summary) => !summaryIsResolved(summary));
  if (unresolved) {
    return [{
      status: 'Open',
      issue: 'no-mistakes PR pipeline still reports incomplete checks',
      evidence: compactText(plainSummary(unresolved)),
    }];
  }

  if (!summaries.some((summary) => /push/i.test(plainSummary(summary)))) {
    return [{
      status: 'Open',
      issue: 'no-mistakes PR pipeline has not recorded push completion',
      evidence: `${summaries.length} resolved step(s) found`,
    }];
  }

  const expectedSha = normalizeSha(expectedHeadSha);
  if (!expectedSha) {
    return [{
      status: 'Unknown',
      issue: 'no-mistakes PR pipeline current head unavailable',
      evidence: 'expected current head was not provided',
    }];
  }

  if (!hasCurrentHeadProof(fullBody, expectedSha)) {
    return [{
      status: 'Open',
      issue: 'no-mistakes PR pipeline does not prove current head',
      evidence: `expected current head \`${expectedSha.slice(0, 7)}\`; no matching current-head marker found`,
    }];
  }

  return [{
    status: 'Resolved',
    issue: 'No open no-mistakes findings',
    evidence: `PR Pipeline -> ${summaries.length} step(s) passed or auto-fixed`,
  }];
}
