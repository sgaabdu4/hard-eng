const agentKinds = new Set(['subagent', 'eval']);
const agentStatuses = new Set(['planned', 'running', 'stalled', 'done', 'failed', 'blocked', 'skipped']);
const evidenceRequiredStatuses = new Set(['done', 'stalled', 'failed', 'blocked', 'skipped']);
const progressRequiredStatuses = new Set(['running', 'stalled', 'failed', 'blocked']);
const recoveryRequiredStatuses = new Set(['running', 'stalled', 'failed', 'blocked']);
const reasonRequiredStatuses = new Set(['stalled', 'blocked', 'skipped']);
const unfinishedStatuses = new Set(['planned', 'running', 'stalled', 'failed', 'blocked']);

function isObject(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

function hasText(value) {
  return typeof value === 'string' && value.trim().length > 0;
}

function stringArray(value) {
  return Array.isArray(value) && value.every((item) => typeof item === 'string');
}

export function agentWorkBlocksReady(state) {
  return Array.isArray(state.agentWork) && state.agentWork.some((work) => unfinishedStatuses.has(work?.status));
}

export function validateAgentWork(state, errors) {
  if (state.agentWork === undefined) return;
  if (!Array.isArray(state.agentWork)) {
    errors.push('agentWork must be an array');
    return;
  }

  for (const [index, work] of state.agentWork.entries()) {
    if (!isObject(work)) {
      errors.push(`agentWork[${index}] must be an object`);
      continue;
    }
    for (const key of ['id', 'kind', 'model', 'purpose', 'status']) {
      if (!hasText(work[key])) errors.push(`agentWork[${index}].${key} is required`);
    }
    if (work.kind && !agentKinds.has(work.kind)) errors.push(`agentWork[${index}].kind is invalid`);
    if (work.status && !agentStatuses.has(work.status)) errors.push(`agentWork[${index}].status is invalid`);
    if (work.kind === 'subagent' && work.model !== 'gpt-5.5') errors.push(`agentWork[${index}].model must be gpt-5.5 for subagent work`);
    if (work.kind === 'eval' && work.model !== 'gpt-5.4-mini') errors.push(`agentWork[${index}].model must be gpt-5.4-mini for eval work`);
    if (!stringArray(work.evidence)) errors.push(`agentWork[${index}].evidence must be string[]`);
    if (work.progress !== undefined && !stringArray(work.progress)) errors.push(`agentWork[${index}].progress must be string[]`);
    if (evidenceRequiredStatuses.has(work.status) && work.evidence?.length === 0) {
      errors.push(`agentWork[${index}].evidence is required for ${work.status}`);
    }
    if (progressRequiredStatuses.has(work.status) && (!Array.isArray(work.progress) || work.progress.length === 0)) {
      errors.push(`agentWork[${index}].progress is required for ${work.status}`);
    }
    if (progressRequiredStatuses.has(work.status) && !hasText(work.lastProgressAt)) {
      errors.push(`agentWork[${index}].lastProgressAt is required for ${work.status}`);
    }
    if (recoveryRequiredStatuses.has(work.status) && !hasText(work.recoveryPrompt)) {
      errors.push(`agentWork[${index}].recoveryPrompt is required for ${work.status}`);
    }
    if (reasonRequiredStatuses.has(work.status) && !hasText(work.reason)) {
      errors.push(`agentWork[${index}].reason is required for ${work.status}`);
    }
  }
}
