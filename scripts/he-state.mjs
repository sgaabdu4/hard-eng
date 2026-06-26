#!/usr/bin/env node
import fs from 'node:fs';

const stages = new Map([
  ['he-plan', { index: 1, nextTargets: ['/he:implement'] }],
  ['he-implement', { index: 2, nextTargets: ['/he:verify'] }],
  ['he-verify', { index: 3, nextTargets: ['/he:ship'] }],
  ['he-ship', { index: 4, nextTargets: ['/he:learn', 'loop-complete'] }],
  ['he-learn', { index: 5, nextTargets: ['loop-complete'] }],
]);
const statuses = new Set(['pending', 'in_progress', 'done', 'blocked', 'skipped']);
const stateStatuses = new Set(['in_progress', 'blocked', 'ready', 'complete']);
const findingStatuses = new Set(['open', 'owned', 'fixed', 'blocked', 'accepted']);
const guardrailKinds = new Set(['script', 'test', 'lint', 'scanner', 'hook', 'eval', 'ci', 'manual']);
const guardrailStatuses = new Set(['planned', 'active', 'passed', 'failed', 'blocked', 'skipped']);
const contextStatuses = new Set(['current', 'updated', 'created']);
const planReadinessStatuses = new Set(['not_required', 'pending', 'accepted', 'parked', 'blocked']);
const artifactStatuses = new Set(['not_required', 'missing', 'draft', 'accepted', 'parked', 'blocked']);
const questionStatuses = new Set(['none', 'draft', 'asked', 'answered', 'parked']);
const grillStageMaps = new Set(['run', 'brief', 'skip', 'n/a']);
const agentKinds = new Set(['subagent', 'eval']);
const agentStatuses = new Set(['planned', 'running', 'done', 'failed', 'blocked', 'skipped']);
const repairTypes = new Map([
  ['scope', 'he-plan'],
  ['code', 'he-implement'],
  ['proof', 'he-verify'],
  ['gate', 'he-ship'],
  ['evidence', 'he-ship'],
  ['learning', 'he-learn'],
  ['process', 'he-learn'],
]);
const uiDecisionTools = new Set(['none', 'lavish']);
const uiDecisionPurposes = new Set(['none', 'ui_flow', 'visual_design']);
const lavishDecisionStatuses = new Set(['pending', 'polled', 'saved', 'accepted', 'blocked']);
const alignmentStatuses = new Set(['pending', 'aligned', 'blocked']);
const requiredSubStages = new Map([
  ['he-plan', ['context', 'grill-me', 'owner-proof', 'artifact-choice', 'risk-route', 'state-validation']],
  ['he-implement', ['owner-read', 'owner-change', 'guardrails', 'state-update']],
  ['he-verify', ['tests', 'guardrails', 'reviews', 'fix-loop', 'state-update']],
  ['he-ship', ['status', 'hooks', 'quality-gates', 'no-mistakes', 'pr-evidence', 'ci-or-skip', 'state-update']],
  ['he-learn', ['learning-findings', 'durable-owner', 'proof', 'state-update']],
]);
const requiredDoneSubStages = new Map([
  ['he-plan', ['context', 'owner-proof', 'artifact-choice', 'risk-route', 'state-validation']],
  ['he-implement', ['owner-read', 'owner-change', 'guardrails']],
  ['he-verify', ['tests', 'guardrails']],
  ['he-ship', ['status', 'hooks', 'quality-gates', 'no-mistakes', 'pr-evidence', 'ci-or-skip', 'state-update']],
  ['he-learn', ['durable-owner', 'proof']],
]);
const requiredEntryStages = new Map([
  ['he-implement', 'he-plan'],
  ['he-verify', 'he-implement'],
  ['he-ship', 'he-verify'],
  ['he-learn', 'he-ship'],
]);
const requiredGuardrails = new Map([
  ['he-plan', ['context-gate', 'state-validation']],
  ['he-implement', ['deterministic-owner-scan']],
  ['he-verify', ['quality-gate']],
  ['he-ship', ['git-status', 'worktree-ready', 'quality-gate', 'no-mistakes', 'pr-evidence', 'ci-or-skip']],
]);
const oldStagePrefix = `${String.fromCharCode(97, 97)}:`;
const oldCommandPattern = new RegExp(`(^|[^A-Za-z0-9_])/?${oldStagePrefix}[a-z][a-z-]*`, 'i');
const oldCommandLabel = `old /${oldStagePrefix.slice(0, -1)} command`;

function template() {
  return {
    schema: 'he-state/v1',
    feature: 'feature-slug',
    updatedAt: new Date().toISOString(),
    stage: 'he-plan',
    stageIndex: 1,
    status: 'in_progress',
    currentStep: 'define-owner-proof',
    next: { target: '/he:implement', ready: false, reason: 'planning not complete' },
    steps: [
      { id: '1', title: 'Define owner and proof', status: 'in_progress' },
      { id: '2', title: 'Choose planning artifact', status: 'pending' },
    ],
    subStages: requiredSubStages.get('he-plan').map((id) => ({ id, title: id, status: 'pending', evidence: [], reason: '' })),
    findings: [],
    guardrails: [
      {
        id: 'context-gate',
        stage: 'he-plan',
        kind: 'script',
        owner: 'scripts/check-project-context-gates.mjs',
        command: 'node "$HOME/.agents/scripts/check-project-context-gates.mjs" --require-all .',
        status: 'planned',
        evidence: [],
        blocksPush: false,
      },
      {
        id: 'state-validation',
        stage: 'he-plan',
        kind: 'script',
        owner: 'scripts/he-state.mjs',
        command: 'node "$HOME/.agents/scripts/he-state.mjs" validate he-state.json',
        status: 'planned',
        evidence: [],
        blocksPush: false,
      },
    ],
    context: {
      product: { path: 'PRODUCT.md', status: 'current' },
      design: { path: 'DESIGN.md', status: 'current' },
      tokenOwner: { path: 'docs/design/tokens.css', status: 'current' },
    },
    planReadiness: {
      grillMe: { required: false, status: 'not_required', statePath: '', questionPolicy: { mode: 'unlimited_until_aligned', evidence: [] }, alignment: { status: 'pending', userConfirmed: false, noGuesswork: false, openQuestions: [], openUnknowns: [], evidence: [] }, stages: [], lastQuestion: { status: 'none', format: 'grill-me/v1', text: '' } },
      uiReview: { required: false, status: 'not_required', liveTool: '', decisionTool: 'none', decisionPurpose: 'none', localhostUrl: '', designSystemEvidence: [], sharedComponentEvidence: [], reviewSurfacePath: '', shownToUser: false, userResponse: '', tweaks: [], evidence: [], lavish: null },
      artifact: { status: 'not_required', paths: [] },
    },
    agentWork: [],
    decisions: [],
    blockers: [],
  };
}

function isObject(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

function stringArray(value) {
  return Array.isArray(value) && value.every((item) => typeof item === 'string');
}

function expectedTargets(stage) {
  return stage.nextTargets.join(' or ');
}

function hasText(value) {
  return typeof value === 'string' && value.trim().length > 0;
}

function hasGrillQuestionShape(text) {
  if (!hasText(text)) return false;
  const required = [/^Q\d+:/m, /Meaning:/, /Why it matters:/, /Suggested default:/, /Options:/, /^A\)/m, /^B\)/m, /^C\)/m, /Reply:/];
  return required.every((pattern) => pattern.test(text));
}

function isLoopbackUrl(value) {
  if (!hasText(value)) return false;
  try {
    const parsed = new URL(value);
    return ['http:', 'https:'].includes(parsed.protocol) && ['localhost', '127.0.0.1', '[::1]'].includes(parsed.hostname);
  } catch {
    return false;
  }
}

function isLavishCommand(command, type) {
  if (!hasText(command)) return false;
  const normalized = command.replace(/\s+/g, ' ').trim();
  const prefix = /(?:^|\s)(?:npx -y )?lavish-axi\s+/;
  if (type === 'poll') return prefix.test(normalized) && /\bpoll\s+\S+/.test(normalized) && !/--timeout|timeout-ms/i.test(normalized);
  if (type === 'launch') return prefix.test(normalized) && !/\bpoll\b/.test(normalized) && !/\bend\b/.test(normalized);
  return false;
}

function validateLavishDecision(lavish, errors, prefix) {
  if (!isObject(lavish)) {
    errors.push(`${prefix}.lavish is required when decisionTool is lavish`);
    return;
  }
  if (!lavishDecisionStatuses.has(lavish.decisionStatus)) errors.push(`${prefix}.lavish.decisionStatus is invalid`);
  if (!isLavishCommand(lavish.launchCommand, 'launch')) errors.push(`${prefix}.lavish.launchCommand must open a Lavish UI artifact`);
  if (!isLavishCommand(lavish.pollCommand, 'poll')) errors.push(`${prefix}.lavish.pollCommand must be a no-timeout lavish-axi poll command`);
  for (const key of ['optionsPath', 'pollReceiptPath']) {
    if (!hasText(lavish[key])) errors.push(`${prefix}.lavish.${key} is required`);
  }
  for (const key of ['optionsShown', 'rejectedOptions', 'selectedComponents', 'evidence']) {
    if (lavish[key] !== undefined && !stringArray(lavish[key])) errors.push(`${prefix}.lavish.${key} must be string[]`);
  }
  if (['saved', 'accepted'].includes(lavish.decisionStatus) && !hasText(lavish.savedChoicesPath)) errors.push(`${prefix}.lavish.savedChoicesPath is required for saved or accepted`);
  if (['saved', 'accepted'].includes(lavish.decisionStatus) && !hasText(lavish.savedComponentsPath)) errors.push(`${prefix}.lavish.savedComponentsPath is required for saved or accepted`);
  if (lavish.decisionStatus === 'accepted') {
    for (const key of ['userDecision', 'selectedOption', 'savedChoicesPath', 'savedComponentsPath']) {
      if (!hasText(lavish[key])) errors.push(`${prefix}.lavish.${key} is required for accepted`);
    }
    if (!Array.isArray(lavish.optionsShown) || lavish.optionsShown.length < 2) errors.push(`${prefix}.lavish.optionsShown must include at least two UI options`);
    if (!Array.isArray(lavish.selectedComponents) || lavish.selectedComponents.length === 0) errors.push(`${prefix}.lavish.selectedComponents is required`);
    if (!Array.isArray(lavish.evidence) || lavish.evidence.length === 0) errors.push(`${prefix}.lavish.evidence is required`);
  }
}

function validateAlignment(alignment, errors, prefix, openKeys) {
  if (!isObject(alignment)) {
    errors.push(`${prefix} is required`);
    return;
  }
  if (!alignmentStatuses.has(alignment.status)) errors.push(`${prefix}.status is invalid`);
  if (typeof alignment.userConfirmed !== 'boolean') errors.push(`${prefix}.userConfirmed must be boolean`);
  if (typeof alignment.noGuesswork !== 'boolean') errors.push(`${prefix}.noGuesswork must be boolean`);
  if (!stringArray(alignment.evidence)) errors.push(`${prefix}.evidence must be string[]`);
  for (const key of openKeys) {
    if (!stringArray(alignment[key])) errors.push(`${prefix}.${key} must be string[]`);
  }
}

function requireAligned(alignment, errors, prefix, openKeys) {
  if (!isObject(alignment)) {
    errors.push(`${prefix} is required before ready handoff`);
    return;
  }
  if (alignment.status !== 'aligned') errors.push(`${prefix}.status must be aligned before ready handoff`);
  if (alignment.userConfirmed !== true) errors.push(`${prefix}.userConfirmed must be true before ready handoff`);
  if (alignment.noGuesswork !== true) errors.push(`${prefix}.noGuesswork must be true before ready handoff`);
  if (!stringArray(alignment.evidence) || alignment.evidence.length === 0) errors.push(`${prefix}.evidence is required before ready handoff`);
  for (const key of openKeys) {
    if (!Array.isArray(alignment[key]) || alignment[key].length !== 0) errors.push(`${prefix}.${key} must be empty before ready handoff`);
  }
}

function commandMatchesGuardrail(guardrail, required) {
  const command = `${guardrail?.id || ''} ${guardrail?.command || ''} ${(guardrail?.evidence || []).join(' ')}`;
  if (['git-status', 'worktree-ready', 'no-mistakes', 'pr-evidence', 'ci-or-skip', 'deterministic-owner-scan'].includes(required) && guardrail?.id !== required) {
    return false;
  }
  if (required === 'context-gate') return /check-project-context-gates\.mjs/.test(command) && /--require-all/.test(command);
  if (required === 'state-validation') return /he-state\.mjs/.test(command) && /validate/.test(command);
  if (required === 'quality-gate') return /check-project-quality-gates\.mjs/.test(command) && /--require-push-gate/.test(command);
  if (required === 'git-status') return /git status --short/.test(command);
  if (required === 'worktree-ready') return /ensure-worktree-ready\.sh/.test(command) && /--require-pre-push/.test(command);
  if (required === 'no-mistakes') return /no-mistakes/.test(command) && /axi run\b/.test(command) && /--intent\b/.test(command) && /passed|PASS|clean|no findings/i.test(command);
  if (required === 'pr-evidence') return /repair-pr-evidence\.mjs/.test(command) && /PR screenshots|2x E2E video|No PR screenshots|No 2x E2E video|evidence/i.test(command);
  if (required === 'ci-or-skip') return /\b(gh|no-mistakes|ci|actions)\b/i.test(command) && /passed|green|skipped|not required|no CI/i.test(command);
  if (required === 'deterministic-owner-scan') return /find-deterministic-owner\.mjs/.test(command) && /--json\b/.test(command);
  return false;
}

function hasPassedGuardrail(guardrails, required) {
  return Array.isArray(guardrails) && guardrails.some((guardrail) => guardrail?.status === 'passed' && commandMatchesGuardrail(guardrail, required));
}

function collectOldCommands(value, pointer = '$', hits = []) {
  if (typeof value === 'string') {
    if (oldCommandPattern.test(value)) hits.push(pointer);
    return hits;
  }
  if (Array.isArray(value)) {
    value.forEach((item, index) => collectOldCommands(item, `${pointer}[${index}]`, hits));
    return hits;
  }
  if (isObject(value)) {
    for (const [key, item] of Object.entries(value)) {
      collectOldCommands(item, `${pointer}.${key}`, hits);
    }
  }
  return hits;
}

function validate(state) {
  const errors = [];
  if (!isObject(state)) return ['state must be a JSON object'];
  for (const pointer of collectOldCommands(state)) {
    errors.push(`${oldCommandLabel} must not appear in state at ${pointer}; use /he:*`);
  }
  if (state.schema !== 'he-state/v1') errors.push('schema must be he-state/v1');
  if (typeof state.feature !== 'string' || !state.feature.trim()) errors.push('feature is required');
  if (typeof state.updatedAt !== 'string' || !state.updatedAt.trim()) errors.push('updatedAt is required');
  const stage = stages.get(state.stage);
  if (!stage) errors.push('stage must be one of he-plan, he-implement, he-verify, he-ship, he-learn');
  if (stage && state.stageIndex !== stage.index) errors.push(`stageIndex must be ${stage.index} for ${state.stage}`);
  if (!stateStatuses.has(state.status)) errors.push('status must be in_progress, blocked, ready, or complete');
  if (typeof state.currentStep !== 'string' || !state.currentStep.trim()) errors.push('currentStep is required');
  if (!isObject(state.next)) {
    errors.push('next is required');
  } else {
    if (typeof state.next.target !== 'string' || !state.next.target.trim()) errors.push('next.target is required');
    if (stage && !stage.nextTargets.includes(state.next.target)) errors.push(`next.target must be ${expectedTargets(stage)} for ${state.stage}`);
    if (typeof state.next.ready !== 'boolean') errors.push('next.ready must be boolean');
  }
  if (!Array.isArray(state.findings)) {
    errors.push('findings must be an array');
  } else {
    for (const [index, finding] of state.findings.entries()) {
      if (!isObject(finding)) {
        errors.push(`findings[${index}] must be an object`);
        continue;
      }
      for (const key of ['id', 'stage', 'summary', 'ownerStage', 'status']) {
        if (typeof finding[key] !== 'string' || !finding[key].trim()) errors.push(`findings[${index}].${key} is required`);
      }
      if (!hasText(finding.repairType)) errors.push(`findings[${index}].repairType is required`);
      if (finding.repairType && !repairTypes.has(finding.repairType)) errors.push(`findings[${index}].repairType is invalid`);
      if (finding.status && !findingStatuses.has(finding.status)) errors.push(`findings[${index}].status is invalid`);
      if (finding.stage && !stages.has(finding.stage)) errors.push(`findings[${index}].stage is invalid`);
      if (finding.ownerStage && !stages.has(finding.ownerStage)) errors.push(`findings[${index}].ownerStage is invalid`);
      if (finding.repairType && repairTypes.has(finding.repairType) && finding.ownerStage !== repairTypes.get(finding.repairType)) {
        errors.push(`findings[${index}].ownerStage must be ${repairTypes.get(finding.repairType)} for ${finding.repairType}`);
      }
      if (finding.owner !== undefined && typeof finding.owner !== 'string') errors.push(`findings[${index}].owner must be a string`);
      if (!stringArray(finding.ownerProof)) errors.push(`findings[${index}].ownerProof must be string[]`);
      if (!stringArray(finding.artifacts)) errors.push(`findings[${index}].artifacts must be string[]`);
      if (finding.guardrailId !== undefined && typeof finding.guardrailId !== 'string') errors.push(`findings[${index}].guardrailId must be a string`);
      if (finding.blocking !== undefined && typeof finding.blocking !== 'boolean') errors.push(`findings[${index}].blocking must be boolean`);
    }
  }
  if (!Array.isArray(state.guardrails)) {
    errors.push('guardrails must be an array');
  } else {
    for (const [index, guardrail] of state.guardrails.entries()) {
      if (!isObject(guardrail)) {
        errors.push(`guardrails[${index}] must be an object`);
        continue;
      }
      for (const key of ['id', 'stage', 'kind', 'owner', 'command', 'status']) {
        if (typeof guardrail[key] !== 'string' || !guardrail[key].trim()) errors.push(`guardrails[${index}].${key} is required`);
      }
      if (guardrail.kind && !guardrailKinds.has(guardrail.kind)) errors.push(`guardrails[${index}].kind is invalid`);
      if (guardrail.status && !guardrailStatuses.has(guardrail.status)) errors.push(`guardrails[${index}].status is invalid`);
      if (guardrail.stage && !stages.has(guardrail.stage)) errors.push(`guardrails[${index}].stage is invalid`);
      if (!stringArray(guardrail.evidence)) errors.push(`guardrails[${index}].evidence must be string[]`);
      if (guardrail.blocksPush !== undefined && typeof guardrail.blocksPush !== 'boolean') errors.push(`guardrails[${index}].blocksPush must be boolean`);
      if (['passed', 'failed', 'blocked', 'skipped'].includes(guardrail.status) && guardrail.evidence?.length === 0) {
        errors.push(`guardrails[${index}].evidence is required for ${guardrail.status}`);
      }
      if (guardrail.status === 'skipped' && !hasText(guardrail.reason)) errors.push(`guardrails[${index}].reason is required for skipped`);
    }
  }
  if (state.entryGate !== undefined) {
    if (!isObject(state.entryGate)) {
      errors.push('entryGate must be an object');
    } else {
      if (!hasText(state.entryGate.fromStage)) errors.push('entryGate.fromStage is required');
      if (!hasText(state.entryGate.decision)) errors.push('entryGate.decision is required');
      if (!hasText(state.entryGate.statePath)) errors.push('entryGate.statePath is required');
      if (!stringArray(state.entryGate.evidence) || state.entryGate.evidence.length === 0) errors.push('entryGate.evidence must be non-empty string[]');
    }
  }
  const requiredEntryStage = requiredEntryStages.get(state.stage);
  if (requiredEntryStage) {
    if (!isObject(state.entryGate)) {
      errors.push(`${state.stage} requires entryGate from ${requiredEntryStage}`);
    } else {
      if (state.entryGate.fromStage !== requiredEntryStage) errors.push(`${state.stage} entryGate.fromStage must be ${requiredEntryStage}`);
      if (state.entryGate.decision !== 'PASS') errors.push(`${state.stage} entryGate.decision must be PASS`);
    }
  }
  if (state.agentWork !== undefined) {
    if (!Array.isArray(state.agentWork)) {
      errors.push('agentWork must be an array');
    } else {
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
        if (['done', 'failed', 'blocked', 'skipped'].includes(work.status) && work.evidence?.length === 0) {
          errors.push(`agentWork[${index}].evidence is required for ${work.status}`);
        }
        if (work.status === 'skipped' && !hasText(work.reason)) errors.push(`agentWork[${index}].reason is required for skipped`);
      }
    }
  }
  if (state.context !== undefined) {
    if (!isObject(state.context)) {
      errors.push('context must be an object');
    } else {
      for (const key of ['product', 'design', 'tokenOwner']) {
        const entry = state.context[key];
        if (!isObject(entry)) {
          errors.push(`context.${key} is required`);
          continue;
        }
        if (typeof entry.path !== 'string' || !entry.path.trim()) errors.push(`context.${key}.path is required`);
        if (!contextStatuses.has(entry.status)) errors.push(`context.${key}.status must be current, updated, or created`);
      }
    }
  }
  if (state.subStages !== undefined) {
    if (!Array.isArray(state.subStages)) {
      errors.push('subStages must be an array');
    } else {
      for (const [index, subStage] of state.subStages.entries()) {
        if (!isObject(subStage)) {
          errors.push(`subStages[${index}] must be an object`);
          continue;
        }
        if (!hasText(subStage.id)) errors.push(`subStages[${index}].id is required`);
        if (!hasText(subStage.title)) errors.push(`subStages[${index}].title is required`);
        if (!statuses.has(subStage.status)) errors.push(`subStages[${index}].status is invalid`);
        if (!stringArray(subStage.evidence)) errors.push(`subStages[${index}].evidence must be string[]`);
        if (subStage.status === 'done' && subStage.evidence?.length === 0) errors.push(`subStages[${index}].evidence is required for done`);
        if (subStage.status === 'skipped' && !hasText(subStage.reason)) errors.push(`subStages[${index}].reason is required for skipped`);
        if (subStage.status === 'skipped' && subStage.evidence?.length === 0) errors.push(`subStages[${index}].evidence is required for skipped`);
        if (subStage.status === 'blocked' && !hasText(subStage.reason)) errors.push(`subStages[${index}].reason is required for blocked`);
        if (subStage.status === 'blocked' && subStage.evidence?.length === 0) errors.push(`subStages[${index}].evidence is required for blocked`);
      }
      const expected = requiredSubStages.get(state.stage);
      if (expected) {
        const allowed = new Set(expected);
        const counts = new Map();
        for (const subStage of state.subStages) {
          if (!hasText(subStage?.id)) continue;
          counts.set(subStage.id, (counts.get(subStage.id) || 0) + 1);
          if (!allowed.has(subStage.id)) errors.push(`${state.stage} subStages includes unknown ${subStage.id}`);
        }
        for (const id of expected) {
          if ((counts.get(id) || 0) !== 1) errors.push(`${state.stage} requires exactly one subStage ${id}`);
        }
      }
    }
  }
  if (state.planReadiness !== undefined) {
    if (!isObject(state.planReadiness)) {
      errors.push('planReadiness must be an object');
    } else {
      const grillMe = state.planReadiness.grillMe;
      if (!isObject(grillMe)) {
        errors.push('planReadiness.grillMe is required');
      } else {
        if (typeof grillMe.required !== 'boolean') errors.push('planReadiness.grillMe.required must be boolean');
        if (!planReadinessStatuses.has(grillMe.status)) errors.push('planReadiness.grillMe.status is invalid');
        if (grillMe.required === true && !hasText(grillMe.statePath)) errors.push('planReadiness.grillMe.statePath is required when Grill Me is required');
        if (grillMe.required === true) {
          if (!isObject(grillMe.questionPolicy)) {
            errors.push('planReadiness.grillMe.questionPolicy is required when Grill Me is required');
          } else {
            if (grillMe.questionPolicy.mode !== 'unlimited_until_aligned') errors.push('planReadiness.grillMe.questionPolicy.mode must be unlimited_until_aligned');
            if (!stringArray(grillMe.questionPolicy.evidence)) errors.push('planReadiness.grillMe.questionPolicy.evidence must be string[]');
          }
          validateAlignment(grillMe.alignment, errors, 'planReadiness.grillMe.alignment', ['openQuestions', 'openUnknowns']);
        }
        if (!Array.isArray(grillMe.stages)) {
          errors.push('planReadiness.grillMe.stages must be an array');
        } else {
          for (const [index, item] of grillMe.stages.entries()) {
            if (!isObject(item)) {
              errors.push(`planReadiness.grillMe.stages[${index}] must be an object`);
              continue;
            }
            if (!hasText(item.id)) errors.push(`planReadiness.grillMe.stages[${index}].id is required`);
            if (!grillStageMaps.has(item.map)) errors.push(`planReadiness.grillMe.stages[${index}].map is invalid`);
            if (!statuses.has(item.status)) errors.push(`planReadiness.grillMe.stages[${index}].status is invalid`);
            if (!stringArray(item.evidence)) errors.push(`planReadiness.grillMe.stages[${index}].evidence must be string[]`);
            if (item.status === 'done' && item.evidence?.length === 0) errors.push(`planReadiness.grillMe.stages[${index}].evidence is required for done`);
            if (['skipped', 'blocked'].includes(item.status) && !hasText(item.reason)) errors.push(`planReadiness.grillMe.stages[${index}].reason is required for ${item.status}`);
            if (['skipped', 'blocked'].includes(item.status) && item.evidence?.length === 0) errors.push(`planReadiness.grillMe.stages[${index}].evidence is required for ${item.status}`);
            if (['skip', 'n/a'].includes(item.map) && item.status !== 'skipped') errors.push(`planReadiness.grillMe.stages[${index}] must be skipped when map is ${item.map}`);
          }
        }
        const lastQuestion = grillMe.lastQuestion;
        if (!isObject(lastQuestion)) {
          errors.push('planReadiness.grillMe.lastQuestion is required');
        } else {
          if (!questionStatuses.has(lastQuestion.status)) errors.push('planReadiness.grillMe.lastQuestion.status is invalid');
          if (lastQuestion.format !== 'grill-me/v1') errors.push('planReadiness.grillMe.lastQuestion.format must be grill-me/v1');
          if (lastQuestion.status !== 'none' && !hasGrillQuestionShape(lastQuestion.text)) {
            errors.push('planReadiness.grillMe.lastQuestion.text must use the full Grill Me question format');
          }
          if (lastQuestion.visibleText !== undefined) {
            if (!hasGrillQuestionShape(lastQuestion.visibleText)) errors.push('planReadiness.grillMe.lastQuestion.visibleText must use the full Grill Me question format');
            if (lastQuestion.visibleText !== lastQuestion.text) errors.push('planReadiness.grillMe.lastQuestion.visibleText must match text exactly');
          }
        }
      }
      const artifact = state.planReadiness.artifact;
      if (!isObject(artifact)) {
        errors.push('planReadiness.artifact is required');
      } else {
        if (!artifactStatuses.has(artifact.status)) errors.push('planReadiness.artifact.status is invalid');
        if (!stringArray(artifact.paths)) errors.push('planReadiness.artifact.paths must be string[]');
        if (artifact.status === 'accepted' && artifact.paths.length === 0) errors.push('planReadiness.artifact.paths is required for accepted');
      }
      const uiReview = state.planReadiness.uiReview;
      if (uiReview !== undefined) {
        if (!isObject(uiReview)) {
          errors.push('planReadiness.uiReview must be an object');
        } else {
          if (typeof uiReview.required !== 'boolean') errors.push('planReadiness.uiReview.required must be boolean');
          if (!planReadinessStatuses.has(uiReview.status)) errors.push('planReadiness.uiReview.status is invalid');
          if (uiReview.required === true && uiReview.liveTool !== 'impeccable-live') errors.push('planReadiness.uiReview.liveTool must be impeccable-live when UI review is required');
          if (uiReview.required === true) validateAlignment(uiReview.alignment, errors, 'planReadiness.uiReview.alignment', ['openDecisions', 'openUnknowns']);
          if (uiReview.decisionTool !== undefined && !uiDecisionTools.has(uiReview.decisionTool)) errors.push('planReadiness.uiReview.decisionTool is invalid');
          if (uiReview.decisionPurpose !== undefined && !uiDecisionPurposes.has(uiReview.decisionPurpose)) errors.push('planReadiness.uiReview.decisionPurpose is invalid');
          if (uiReview.decisionTool === 'lavish' && !['ui_flow', 'visual_design'].includes(uiReview.decisionPurpose)) {
            errors.push('planReadiness.uiReview.decisionPurpose must be ui_flow or visual_design when using Lavish');
          }
          if (!stringArray(uiReview.designSystemEvidence)) errors.push('planReadiness.uiReview.designSystemEvidence must be string[]');
          if (uiReview.sharedComponentEvidence !== undefined && !stringArray(uiReview.sharedComponentEvidence)) errors.push('planReadiness.uiReview.sharedComponentEvidence must be string[]');
          if (!stringArray(uiReview.evidence)) errors.push('planReadiness.uiReview.evidence must be string[]');
          if (!stringArray(uiReview.tweaks)) errors.push('planReadiness.uiReview.tweaks must be string[]');
          if (uiReview.decisionTool === 'lavish') validateLavishDecision(uiReview.lavish, errors, 'planReadiness.uiReview');
          if (uiReview.required === true && uiReview.status === 'accepted') {
            if (uiReview.shownToUser !== true) errors.push('planReadiness.uiReview.shownToUser must be true before UI plan ready');
            if (!isLoopbackUrl(uiReview.localhostUrl)) errors.push('planReadiness.uiReview.localhostUrl must be a localhost URL before UI plan ready');
            if (!hasText(uiReview.reviewSurfacePath)) errors.push('planReadiness.uiReview.reviewSurfacePath is required before UI plan ready');
            if (!hasText(uiReview.userResponse)) errors.push('planReadiness.uiReview.userResponse is required before UI plan ready');
            if (uiReview.designSystemEvidence.length === 0) errors.push('planReadiness.uiReview.designSystemEvidence is required before UI plan ready');
            if ((uiReview.sharedComponentEvidence || []).length === 0) errors.push('planReadiness.uiReview.sharedComponentEvidence is required before UI plan ready');
            if (uiReview.evidence.length === 0) errors.push('planReadiness.uiReview.evidence is required before UI plan ready');
            if (uiReview.tweaks.length === 0) errors.push('planReadiness.uiReview.tweaks must record applied tweaks or none requested');
            if (uiReview.decisionTool !== 'lavish') errors.push('planReadiness.uiReview.decisionTool must be lavish before UI plan ready');
            if (uiReview.lavish?.decisionStatus !== 'accepted') errors.push('planReadiness.uiReview.lavish.decisionStatus must be accepted before UI plan ready');
            requireAligned(uiReview.alignment, errors, 'planReadiness.uiReview.alignment', ['openDecisions', 'openUnknowns']);
          }
          if (['parked', 'blocked'].includes(uiReview.status) && !hasText(uiReview.reason)) errors.push(`planReadiness.uiReview.reason is required for ${uiReview.status}`);
        }
      }
    }
  }
  if (!Array.isArray(state.steps) || state.steps.length === 0) {
    errors.push('steps must be a non-empty array');
  } else {
    const inProgress = state.steps.filter((step) => step?.status === 'in_progress');
    if (inProgress.length > 1) errors.push('only one step can be in_progress');
    for (const [index, step] of state.steps.entries()) {
      if (!isObject(step)) {
        errors.push(`steps[${index}] must be an object`);
        continue;
      }
      if (typeof step.id !== 'string' || !step.id.trim()) errors.push(`steps[${index}].id is required`);
      if (typeof step.title !== 'string' || !step.title.trim()) errors.push(`steps[${index}].title is required`);
      if (!statuses.has(step.status)) errors.push(`steps[${index}].status is invalid`);
      if (['done', 'blocked'].includes(step.status)) {
        const receipt = step.receipt;
        if (!isObject(receipt)) {
          errors.push(`steps[${index}].receipt is required for ${step.status}`);
          continue;
        }
        for (const key of ['stage', 'state', 'decision', 'blocker', 'next']) {
          if (typeof receipt[key] !== 'string') errors.push(`steps[${index}].receipt.${key} must be a string`);
        }
        if (!stringArray(receipt.ownerProof)) errors.push(`steps[${index}].receipt.ownerProof must be string[]`);
        if (!stringArray(receipt.artifacts)) errors.push(`steps[${index}].receipt.artifacts must be string[]`);
      }
      if (step.status === 'skipped') {
        if (!hasText(step.reason)) errors.push(`steps[${index}].reason is required for skipped`);
        if (!stringArray(step.evidence) || step.evidence.length === 0) errors.push(`steps[${index}].evidence is required for skipped`);
      }
    }
    if (['ready', 'complete'].includes(state.status) && state.next?.ready !== true) {
      errors.push('state.status ready or complete requires next.ready true');
    }
    if (state.status === 'blocked') {
      if (state.next?.ready !== false) errors.push('state.status blocked requires next.ready false');
      const blocking = state.findings?.some((finding) => finding?.blocking === true && ['open', 'owned', 'blocked'].includes(finding.status));
      if (!blocking && !(Array.isArray(state.blockers) && state.blockers.length)) {
        errors.push('state.status blocked requires a blocking finding or blocker entry');
      }
    }
    if (state.next?.ready === true) {
      const unfinished = state.steps.filter((step) => ['pending', 'in_progress', 'blocked'].includes(step.status));
      if (unfinished.length) errors.push('next.ready cannot be true while steps are pending, in_progress, or blocked');
      if (!['ready', 'complete'].includes(state.status)) errors.push('state.status must be ready or complete when next.ready is true');
      const blockingFindings = state.findings?.filter((finding) => finding?.blocking === true && ['open', 'owned', 'blocked'].includes(finding.status));
      if (blockingFindings?.length) errors.push('next.ready cannot be true while blocking findings are unresolved');
      const unresolvedLearning = state.findings?.filter((finding) => finding?.ownerStage === 'he-learn' && ['open', 'owned', 'blocked'].includes(finding.status));
      if (state.stage === 'he-ship' && state.next?.target === 'loop-complete' && unresolvedLearning?.length) {
        errors.push('he-ship cannot skip he-learn while learning findings are unresolved');
      }
      if (state.stage === 'he-ship' && state.next?.target === '/he:learn' && !unresolvedLearning?.length) {
        errors.push('he-ship should target loop-complete when there are no unresolved learning findings');
      }
      if (state.stage === 'he-plan') {
        const context = state.context;
        for (const key of ['product', 'design', 'tokenOwner']) {
          if (!context?.[key] || !contextStatuses.has(context[key].status)) {
            errors.push(`he-plan ready handoff requires context.${key} to be current, updated, or created`);
          }
        }
        const readiness = state.planReadiness;
        if (!isObject(readiness)) {
          errors.push('he-plan ready handoff requires planReadiness');
        } else {
          const grillMe = readiness.grillMe;
          const uiMapped = Array.isArray(grillMe?.stages)
            ? grillMe.stages.some((item) => ['ui-flow', 'visual-design'].includes(item?.id) && ['run', 'brief'].includes(item?.map))
            : false;
          if (!isObject(grillMe)) {
            errors.push('he-plan ready handoff requires planReadiness.grillMe');
          } else if (grillMe.required === true) {
            if (grillMe.status !== 'accepted') {
              errors.push('he-plan ready handoff requires required Grill Me to be accepted');
            }
            if (grillMe.questionPolicy?.mode !== 'unlimited_until_aligned') {
              errors.push('he-plan ready handoff requires unlimited Grill Me questions until aligned');
            }
            requireAligned(grillMe.alignment, errors, 'planReadiness.grillMe.alignment', ['openQuestions', 'openUnknowns']);
            const unresolvedStages = Array.isArray(grillMe.stages)
              ? grillMe.stages.filter((item) => ['run', 'brief'].includes(item?.map) && ['pending', 'in_progress', 'blocked'].includes(item?.status))
              : [];
            if (unresolvedStages.length) errors.push('he-plan ready handoff cannot have unresolved Grill Me stages');
            if (['draft', 'asked'].includes(grillMe.lastQuestion?.status)) {
              errors.push('he-plan ready handoff cannot have an open Grill Me question');
            }
            if (grillMe.lastQuestion?.status === 'parked') {
              errors.push('he-plan ready handoff cannot have a parked Grill Me question');
            }
            if (grillMe.lastQuestion?.status !== 'none' && !hasText(grillMe.lastQuestion?.visibleText)) {
              errors.push('he-plan ready handoff requires the visible Grill Me question text');
            }
            if (uiMapped) {
              const uiReview = readiness.uiReview;
              if (!isObject(uiReview)) {
                errors.push('he-plan ready handoff requires planReadiness.uiReview when UI flow or visual design ran');
              } else if (uiReview.required !== true || uiReview.status !== 'accepted') {
                errors.push('he-plan ready handoff requires UI review to be accepted when UI flow or visual design ran');
              }
            }
          }
          if (readiness.uiReview?.decisionTool === 'lavish' && !uiMapped) {
            errors.push('he-plan ready handoff cannot use Lavish unless Grill Me UI flow or visual design ran');
          }
          const artifact = readiness.artifact;
          if (isObject(artifact) && !['not_required', 'accepted'].includes(artifact.status)) {
            errors.push('he-plan ready handoff requires the plan artifact to be accepted or not_required');
          }
        }
      }
      const expectedSubStages = requiredSubStages.get(state.stage) || [];
      const mustBeDone = new Set(requiredDoneSubStages.get(state.stage) || []);
      if (!Array.isArray(state.subStages)) {
        errors.push(`${state.stage} ready handoff requires subStages`);
      } else {
        for (const id of expectedSubStages) {
          const subStage = state.subStages.find((item) => item?.id === id);
          if (!subStage) {
            errors.push(`${state.stage} ready handoff requires subStage ${id}`);
            continue;
          }
          if (!['done', 'skipped'].includes(subStage.status)) {
            errors.push(`${state.stage} ready handoff requires subStage ${id} to be done or skipped`);
          }
          if (mustBeDone.has(id) && subStage.status !== 'done') {
            errors.push(`${state.stage} ready handoff requires subStage ${id} to be done, not skipped`);
          }
        }
      }
      const entryStage = requiredEntryStages.get(state.stage);
      if (entryStage) {
        if (!isObject(state.entryGate)) {
          errors.push(`${state.stage} ready handoff requires entryGate from ${entryStage}`);
        } else {
          if (state.entryGate.fromStage !== entryStage) errors.push(`${state.stage} entryGate.fromStage must be ${entryStage}`);
          if (state.entryGate.decision !== 'PASS') errors.push(`${state.stage} entryGate.decision must be PASS`);
        }
      }
      for (const required of requiredGuardrails.get(state.stage) || []) {
        if (!hasPassedGuardrail(state.guardrails, required)) errors.push(`${state.stage} ready handoff requires passed guardrail ${required}`);
      }
      if (state.stage === 'he-implement' && !state.guardrails?.some((guardrail) => guardrail?.stage === 'he-implement' && guardrail.status === 'passed')) {
        errors.push('he-implement ready handoff requires a passed implementation guardrail');
      }
      if (state.stage === 'he-learn') {
        const closedLearning = state.findings?.filter((finding) => finding?.ownerStage === 'he-learn' && ['fixed', 'accepted'].includes(finding.status));
        if (!closedLearning?.length) errors.push('he-learn ready handoff requires a fixed or accepted learning finding');
      }
      const unfinishedAgentWork = state.agentWork?.filter((work) => ['planned', 'running', 'failed', 'blocked'].includes(work?.status));
      if (unfinishedAgentWork?.length) errors.push('next.ready cannot be true while agentWork is planned, running, failed, or blocked');
      const unresolvedGuardrails = state.guardrails?.filter((guardrail) => ['planned', 'active', 'failed', 'blocked'].includes(guardrail?.status));
      if (unresolvedGuardrails?.length) errors.push('next.ready cannot be true while guardrails are planned, active, failed, or blocked');
      const brokenGuardrails = state.guardrails?.filter((guardrail) => guardrail?.blocksPush === true && ['failed', 'blocked', 'planned'].includes(guardrail.status));
      if (brokenGuardrails?.length) errors.push('next.ready cannot be true while push-blocking guardrails are unresolved');
      if (['he-verify', 'he-ship'].includes(state.stage)) {
        const unprovedGuardrails = state.guardrails?.filter((guardrail) => guardrail?.blocksPush === true && !['passed', 'skipped'].includes(guardrail.status));
        if (unprovedGuardrails?.length) errors.push(`${state.stage} ready handoff requires push-blocking guardrails to be passed or explicitly skipped`);
      }
    }
  }
  return errors;
}

function usage() {
  console.error('Usage: he-state.mjs validate <state.json> | template');
}

const [command, file] = process.argv.slice(2);
if (command === 'template') {
  console.log(`${JSON.stringify(template(), null, 2)}\n`);
} else if (command === 'validate' && file) {
  let parsed;
  try {
    parsed = JSON.parse(fs.readFileSync(file, 'utf8'));
  } catch (error) {
    console.error(`he-state: cannot read ${file}: ${error.message}`);
    process.exit(1);
  }
  const errors = validate(parsed);
  if (errors.length) {
    console.error(`he-state: ${errors.length} error(s)`);
    for (const error of errors) console.error(`- ${error}`);
    process.exit(1);
  }
  console.log('he-state: pass');
} else {
  usage();
  process.exit(2);
}
