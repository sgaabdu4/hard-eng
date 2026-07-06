#!/usr/bin/env node
// HARD_ENG_LARGE_OWNER: he-state validator contract with focused behavior coverage.
import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { validateComplianceState } from './he-state-compliance.mjs';
import { validateGuardrailInventory } from './he-state-guardrail-inventory.mjs';
import { handoverLabeledStrings, handoverTargetCommands, targetCommandsFromText } from './he-state-handover-targets.mjs';
import { validateNoGrillMeLedger } from './he-state-grill-me-ledger.mjs';
import { validateImplementOrder, validateShipOrder } from './he-state-order.mjs';
import { validatePlanReadinessForPlanExit, validatePlanReadinessForReadyState } from './he-state-readiness-parser.mjs';
import { matchesImplementationProofGuardrail, matchesTestFirstProofGuardrail } from './he-state-proof.mjs';
import { hasUiTouchedOwnerClass, validateSsotOwnerReuse } from './he-state-ssot-owner-reuse.mjs';
import { agentWorkBlocksReady, validateAgentWork } from './he-state-agent-work.mjs';

const stages = new Map([['he-plan', { index: 1, nextTargets: ['/he:implement'] }], ['he-implement', { index: 2, nextTargets: ['/he:verify'] }], ['he-verify', { index: 3, nextTargets: ['/he:ship'] }], ['he-ship', { index: 4, nextTargets: ['/he:learn', 'loop-complete'] }], ['he-learn', { index: 5, nextTargets: ['loop-complete'] }]]);
const statuses = new Set(['pending', 'in_progress', 'done', 'blocked', 'skipped']);
const stateStatuses = new Set(['in_progress', 'blocked', 'ready', 'complete']);
const receiptDecisions = new Set(['PASS', 'CONCERNS', 'FAIL']);
const findingStatuses = new Set(['open', 'owned', 'fixed', 'blocked', 'accepted']);
const guardrailKinds = new Set(['script', 'test', 'lint', 'scanner', 'hook', 'eval', 'ci', 'manual']);
const guardrailStatuses = new Set(['planned', 'active', 'passed', 'failed', 'blocked', 'skipped']);
const contextStatuses = new Set(['current', 'updated', 'created']);
const planReadinessStatuses = new Set(['not_required', 'pending', 'accepted', 'parked', 'blocked']);
const artifactStatuses = new Set(['not_required', 'missing', 'draft', 'accepted', 'parked', 'blocked']);
const questionStatuses = new Set(['none', 'draft', 'asked', 'answered', 'parked']);
const grillStageMaps = new Set(['run', 'brief', 'skip', 'n/a']);
const repairTypes = new Map([
  ['scope', 'he-plan'],
  ['code', 'he-implement'],
  ['proof', 'he-verify'],
  ['gate', 'he-ship'],
  ['evidence', 'he-ship'],
  ['learning', 'he-learn'],
  ['process', 'he-learn'],
]);
const uiDecisionTools = new Set(['none', 'ui-review-receipt']);
const uiDecisionPurposes = new Set(['none', 'ui_flow', 'visual_design']);
const uiReviewReceiptStatuses = new Set(['pending', 'shown', 'saved', 'accepted', 'blocked']);
const uiReviewSurfaceKinds = new Set(['real-route', 'react-localhost', 'storybook', 'flutter-widget-preview', 'widgetbook', 'simulator', 'local-html']);
const browserSurfaceKinds = new Set(['real-route', 'react-localhost', 'storybook', 'flutter-widget-preview', 'local-html']);
const alignmentStatuses = new Set(['pending', 'aligned', 'blocked']);
const visualArtifactPattern = String.raw`(?:screenshot|screenshots|image|images|preview|artifact|artifacts|surface)`;
const shownArtifactPattern = String.raw`(?:shown|showed|sent|displayed|presented|inline|attached|reviewed|shared|opened|viewed)`;
const capturedArtifactPattern = String.raw`(?:captured|recorded|saved|exported|attached)`;
const beforePattern = String.raw`(?:before|prior\s+to|ahead\s+of)`;
const acceptancePattern = String.raw`(?:(?:user\s+)?(?:approved|accepted)|approval|acceptance|decision|selection)`;
const verifyStagePattern = String.raw`(?:/he:verify|he-verify|verify\s+handoff|verification)`;
const uiSurfacePathPattern = /\.(?:css|scss|sass|less|tsx|jsx|html?|svelte|vue|astro)\b/i;
const dartUiSurfacePathPattern = /(?:^|[/._-])(?:screen|screens|page|pages|view|views|widget|widgets|component|components|route|routes|ui|app)(?:[/._-]|$)/i;
const backendRoutePathPattern = /(?:^|[\\/])(?:api|apis|server|servers|backend|backends|functions?|controllers?|handlers?|middleware|workers?)(?:[\\/]|$)|(?:^|[\\/])(?:\+server|route)\.(?:ts|js|mjs|cjs)\b|(?:^|[\\/])\+(?:page|layout)\.server\.(?:ts|js|mjs|cjs)\b/i;
const backendRouteTextPattern = /\b(?:api|apis|server|servers|backend|backends|functions?|controllers?|handlers?|middleware|workers?)\s+(?:route|routes|endpoint|endpoints|handler|handlers|controller|controllers|module|modules)\b|\b(?:route|routes|endpoint|endpoints)\s+(?:api|apis|server|servers|backend|backends|functions?|controllers?|handlers?|middleware|workers?)\b/i;
const requiredSubStages = new Map([
  ['he-plan', ['context', 'grill-me', 'owner-proof', 'artifact-choice', 'risk-route', 'learning-capture', 'state-validation']],
  ['he-implement', ['owner-read', 'ssot-owner-reuse', 'test-first', 'owner-change', 'guardrails', 'learning-capture', 'state-update']],
  ['he-verify', ['tests', 'guardrails', 'reviews', 'fix-loop', 'learning-capture', 'state-update']],
  ['he-ship', ['status', 'hooks', 'quality-gates', 'no-mistakes', 'pr-evidence', 'pr-review-threads', 'ci-or-skip', 'learning-capture', 'state-update']],
  ['he-learn', ['learning-findings', 'durable-owner', 'proof', 'state-update']],
]);
const requiredDoneSubStages = new Map([
  ['he-plan', ['context', 'owner-proof', 'artifact-choice', 'risk-route', 'state-validation']],
  ['he-implement', ['owner-read', 'ssot-owner-reuse', 'test-first', 'owner-change', 'guardrails']],
  ['he-verify', ['tests', 'guardrails']],
  ['he-ship', ['status', 'hooks', 'quality-gates', 'no-mistakes', 'pr-evidence', 'pr-review-threads', 'ci-or-skip', 'state-update']],
  ['he-learn', ['durable-owner', 'proof']],
]);
const requiredEntryStages = new Map([['he-implement', 'he-plan'], ['he-verify', 'he-implement'], ['he-ship', 'he-verify'], ['he-learn', 'he-ship']]);
const requiredGuardrails = new Map([['he-plan', ['context-gate', 'state-validation']], ['he-implement', ['deterministic-owner-scan', 'test-first-proof', 'implementation-proof']], ['he-verify', ['quality-gate']], ['he-ship', ['git-status', 'worktree-ready', 'quality-gate', 'no-mistakes', 'pr-evidence', 'pr-review-threads', 'ci-or-skip']]]);
const oldStagePrefix = `${String.fromCharCode(97, 97)}:`, oldCommandPattern = new RegExp(`(^|[^A-Za-z0-9_])/?${oldStagePrefix}[a-z][a-z-]*`, 'i'), oldCommandLabel = `old /${oldStagePrefix.slice(0, -1)} command`;
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
      uiReview: { required: false, status: 'not_required', liveTool: '', decisionTool: 'none', decisionPurpose: 'none', localhostUrl: '', designSystemEvidence: [], sharedComponentEvidence: [], reviewSurfacePath: '', shownToUser: false, userResponse: '', tweaks: [], evidence: [], receipt: null },
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

function expectedTargets(stage) { return stage.nextTargets.join(' or '); }

function hasText(value) { return typeof value === 'string' && value.trim().length > 0; }

function hasGrillQuestionShape(text) {
  if (!hasText(text)) return false;
  const required = [/^Q\d+:/m, /Meaning:/, /Why it matters:/, /Suggested default:/, /Options:/, /^A\)/m, /^B\)/m, /^C\)/m, /Reply:/];
  return required.every((pattern) => pattern.test(text));
}

function validateHandoverPrompt(receipt, errors, pointer) {
  const text = receipt.handoverPrompt;
  if (!hasText(text)) { errors.push(`${pointer}.handoverPrompt must be a non-empty string`); return; }
  const handoverTargets = handoverTargetCommands(text);
  const checks = [['fresh session/thread', /(fresh|new).*(session|thread)/i], ['worktree', /worktree/i], ['he-state.json', /he-state\.json/i], ['read-state instruction', /read .*he-state\.json|read .*state/i]];
  for (const [label, pattern] of checks) if (!pattern.test(text)) errors.push(`${pointer}.handoverPrompt must include ${label}`);
  for (const [label, pattern] of [['Stage label', 'Stage'], ['State label', 'State'], ['Next label', 'Next']]) {
    if (handoverLabeledStrings(text, pattern).length === 0) errors.push(`${pointer}.handoverPrompt must include ${label}`);
  }
  if (handoverTargets.length === 0) errors.push(`${pointer}.handoverPrompt must include next command`);
  for (const nextTarget of targetCommandsFromText(receipt.next)) {
    if (!handoverTargets.includes(nextTarget)) errors.push(`${pointer}.handoverPrompt must include receipt next target`);
  }
}

function isLoopbackUrl(value) {
  if (!hasText(value)) return false;
  try { const parsed = new URL(value); return ['http:', 'https:'].includes(parsed.protocol) && ['localhost', '127.0.0.1', '[::1]'].includes(parsed.hostname); } catch { return false; }
}

function requireTextArray(value, errors, pointer, { minLength = 0 } = {}) {
  if (!stringArray(value) || value.some((item) => !hasText(item))) {
    errors.push(`${pointer} must be non-empty string[]`);
    return false;
  }
  if (value.length < minLength) {
    errors.push(`${pointer} must include at least ${minLength} item${minLength === 1 ? '' : 's'}`);
    return false;
  }
  return true;
}

function hasUserVisibleScreenshotEvidence(receipt) {
  const evidence = Array.isArray(receipt?.userVisibleEvidence)
    ? receipt.userVisibleEvidence.filter(hasText).join(' ')
    : '';
  if (hasNegatedScreenshotEvidence(evidence)) return false;
  if (hasPlannedOrFutureScreenshotEvidence(evidence)) return false;
  if (hasAfterAcceptanceScreenshotEvidence(evidence)) return false;
  return hasBeforeAcceptanceScreenshotEvidence(evidence);
}

function hasNegatedScreenshotEvidence(text) {
  return /\b(?:no|not|never|without|missing|absent|failed|failure|unable|cannot|can't|did not|didn't|was not|wasn't|were not|weren't)\b[\s\S]{0,90}\b(?:screenshot|screenshots|image|images|preview|artifact|artifacts|surface|shown|showed|displayed|presented|captured|saved|recorded)\b/i.test(text) ||
    /\b(?:screenshot|screenshots|image|images|preview|artifact|artifacts|surface|shown|showed|displayed|presented|captured|saved|recorded)\b[\s\S]{0,90}\b(?:no|not|never|without|missing|absent|failed|failure|unable|cannot|can't|did not|didn't|was not|wasn't|were not|weren't)\b/i.test(text);
}

function hasPlannedOrFutureScreenshotEvidence(text) {
  const planned = String.raw`(?:will|would|should|could|can|may|might|going\s+to|plan(?:s|ned|ning)?\s+to|intend(?:s|ed|ing)?\s+to|to\s+be|todo|pending|not\s+yet|later)`;
  const action = String.raw`(?:show|shown|display|displayed|present|presented|capture|captured|save|saved|record|recorded|attach|attached|share|shared|open|opened|view|viewed)`;
  return new RegExp(String.raw`\b${planned}\b[\s\S]{0,80}\b(?:${visualArtifactPattern}|${action})\b`, 'i').test(text) ||
    new RegExp(String.raw`\b(?:${visualArtifactPattern}|${action})\b[\s\S]{0,80}\b${planned}\b`, 'i').test(text);
}

function hasBeforeAcceptanceScreenshotEvidence(text) {
  return new RegExp(String.raw`\b${visualArtifactPattern}\b[\s\S]{0,120}\b${shownArtifactPattern}\b[\s\S]{0,90}\b${beforePattern}\b[\s\S]{0,90}\b${acceptancePattern}\b`, 'i').test(text) ||
    new RegExp(String.raw`\b${shownArtifactPattern}\b[\s\S]{0,120}\b${visualArtifactPattern}\b[\s\S]{0,90}\b${beforePattern}\b[\s\S]{0,90}\b${acceptancePattern}\b`, 'i').test(text) ||
    new RegExp(String.raw`\b${beforePattern}\b[\s\S]{0,90}\b${acceptancePattern}\b[\s\S]{0,120}\b(?:${visualArtifactPattern}[\s\S]{0,90}${shownArtifactPattern}|${shownArtifactPattern}[\s\S]{0,90}${visualArtifactPattern})\b`, 'i').test(text) ||
    new RegExp(String.raw`\b(?:${visualArtifactPattern}[\s\S]{0,120}${shownArtifactPattern}|${shownArtifactPattern}[\s\S]{0,120}${visualArtifactPattern})\b[\s\S]{0,90}\b(?:then|after\s+that|afterward|afterwards)\b[\s\S]{0,90}\b${acceptancePattern}\b`, 'i').test(text);
}

function hasAfterAcceptanceScreenshotEvidence(text) {
  const lateOrderPattern = String.raw`(?:after(?!\s+that\b)|following|once)`;
  return new RegExp(String.raw`\b${lateOrderPattern}\b[\s\S]{0,90}\b${acceptancePattern}\b[\s\S]{0,120}\b(?:${visualArtifactPattern}[\s\S]{0,90}${shownArtifactPattern}|${shownArtifactPattern}[\s\S]{0,90}${visualArtifactPattern})\b`, 'i').test(text) ||
    new RegExp(String.raw`\b(?:${visualArtifactPattern}[\s\S]{0,120}${shownArtifactPattern}|${shownArtifactPattern}[\s\S]{0,120}${visualArtifactPattern})\b[\s\S]{0,90}\b${lateOrderPattern}\b[\s\S]{0,90}\b${acceptancePattern}\b`, 'i').test(text);
}

function hasBeforeVerifyScreenshotEvidence(text) {
  return new RegExp(String.raw`\b(?:${visualArtifactPattern}[\s\S]{0,120}${capturedArtifactPattern}|${capturedArtifactPattern}[\s\S]{0,120}${visualArtifactPattern})\b[\s\S]{0,90}\b${beforePattern}\b[\s\S]{0,90}${verifyStagePattern}\b`, 'i').test(text) ||
    new RegExp(String.raw`\b${beforePattern}\b[\s\S]{0,90}${verifyStagePattern}\b[\s\S]{0,120}\b(?:${visualArtifactPattern}[\s\S]{0,90}${capturedArtifactPattern}|${capturedArtifactPattern}[\s\S]{0,90}${visualArtifactPattern})\b`, 'i').test(text);
}

function hasAfterVerifyScreenshotEvidence(text) {
  return new RegExp(String.raw`\b(?:after|following|once|post)\b[\s\S]{0,90}${verifyStagePattern}\b[\s\S]{0,120}\b(?:${visualArtifactPattern}[\s\S]{0,90}${capturedArtifactPattern}|${capturedArtifactPattern}[\s\S]{0,90}${visualArtifactPattern})\b`, 'i').test(text) ||
    new RegExp(String.raw`\b(?:${visualArtifactPattern}[\s\S]{0,120}${capturedArtifactPattern}|${capturedArtifactPattern}[\s\S]{0,120}${visualArtifactPattern})\b[\s\S]{0,90}\b(?:after|following|once|post)\b[\s\S]{0,90}${verifyStagePattern}\b`, 'i').test(text);
}

function hasImplementationScreenshotEvidence(guardrail) {
  const evidence = Array.isArray(guardrail?.evidence) ? guardrail.evidence.filter(hasText).join(' ') : '';
  if (hasNegatedScreenshotEvidence(evidence)) return false;
  if (hasPlannedOrFutureScreenshotEvidence(evidence)) return false;
  if (hasAfterVerifyScreenshotEvidence(evidence)) return false;
  return (
    new RegExp(String.raw`\b${capturedArtifactPattern}\b[\s\S]{0,90}\b(?:screenshot|screenshots|image|images)\b`, 'i').test(evidence) ||
    new RegExp(String.raw`\b(?:screenshot|screenshots|image|images)\b[\s\S]{0,90}\b${capturedArtifactPattern}\b`, 'i').test(evidence)
  ) &&
    hasBeforeVerifyScreenshotEvidence(evidence) &&
    /\b(?:actual|implemented|implementation|real\s+(?:app|route|screen|ui)|localhost|simulator|storybook|widgetbook)\b/i.test(evidence) &&
    /\.(?:png|jpe?g|webp)\b/i.test(evidence);
}

function distinctTextCount(values) {
  return new Set(values.filter(hasText).map((item) => item.trim())).size;
}

function validateUiReviewReceipt(receipt, errors, prefix) {
  if (!isObject(receipt)) {
    errors.push(`${prefix}.receipt is required when decisionTool is ui-review-receipt`);
    return;
  }
  if (!uiReviewReceiptStatuses.has(receipt.status)) errors.push(`${prefix}.receipt.status is invalid`);
  if (!uiReviewSurfaceKinds.has(receipt.surfaceKind)) errors.push(`${prefix}.receipt.surfaceKind is invalid`);
  for (const key of ['artifactPath', 'receiptPath']) {
    if (!hasText(receipt[key])) errors.push(`${prefix}.receipt.${key} is required`);
  }
  for (const key of ['optionsShown', 'rejectedOptions', 'selectedComponents', 'evidence']) {
    if (receipt[key] !== undefined && !stringArray(receipt[key])) errors.push(`${prefix}.receipt.${key} must be string[]`);
  }
  if (['saved', 'accepted'].includes(receipt.status) && !hasText(receipt.savedChoicesPath)) errors.push(`${prefix}.receipt.savedChoicesPath is required for saved or accepted`);
  if (['saved', 'accepted'].includes(receipt.status) && !hasText(receipt.savedComponentsPath)) errors.push(`${prefix}.receipt.savedComponentsPath is required for saved or accepted`);
  if (receipt.status === 'accepted') {
    for (const key of ['questionText', 'userDecision', 'selectedOption', 'savedChoicesPath', 'savedComponentsPath']) {
      if (!hasText(receipt[key])) errors.push(`${prefix}.receipt.${key} is required for accepted`);
    }
    if (browserSurfaceKinds.has(receipt.surfaceKind) && !isLoopbackUrl(receipt.surfaceUrl)) {
      errors.push(`${prefix}.receipt.surfaceUrl must be a localhost URL for ${receipt.surfaceKind}`);
    }
    if (receipt.surfaceKind === 'simulator' && !hasText(receipt.deviceTarget)) {
      errors.push(`${prefix}.receipt.deviceTarget is required for simulator review`);
    }
    if (receipt.surfaceKind === 'widgetbook' && !isLoopbackUrl(receipt.surfaceUrl) && !hasText(receipt.deviceTarget)) {
      errors.push(`${prefix}.receipt.surfaceUrl or deviceTarget is required for widgetbook review`);
    }
    if (!Array.isArray(receipt.optionsShown) || receipt.optionsShown.length < 2) errors.push(`${prefix}.receipt.optionsShown must include at least two UI options`);
    if (!Array.isArray(receipt.rejectedOptions) || receipt.rejectedOptions.length === 0) errors.push(`${prefix}.receipt.rejectedOptions must include at least one rejected UI option`);
    const screenshotPathsValid = requireTextArray(receipt.screenshotPaths, errors, `${prefix}.receipt.screenshotPaths`, { minLength: 1 });
    if (screenshotPathsValid && distinctTextCount(receipt.screenshotPaths) !== receipt.screenshotPaths.length) {
      errors.push(`${prefix}.receipt.screenshotPaths must be distinct`);
    }
    if (Array.isArray(receipt.optionsShown) && screenshotPathsValid && distinctTextCount(receipt.screenshotPaths) < receipt.optionsShown.length) {
      errors.push(`${prefix}.receipt.screenshotPaths must include screenshots for every UI option shown`);
    }
    requireTextArray(receipt.userVisibleEvidence, errors, `${prefix}.receipt.userVisibleEvidence`, { minLength: 1 });
    if (!hasUserVisibleScreenshotEvidence(receipt)) {
      errors.push(`${prefix}.receipt.userVisibleEvidence must prove screenshots or visual artifacts were shown to the user before acceptance`);
    }
    if (stringArray(receipt.optionsShown)) {
      const shownOptions = new Set(receipt.optionsShown);
      if (hasText(receipt.selectedOption) && !shownOptions.has(receipt.selectedOption)) {
        errors.push(`${prefix}.receipt.selectedOption must be one of optionsShown`);
      }
      if (stringArray(receipt.rejectedOptions)) {
        if (receipt.rejectedOptions.some((option) => !shownOptions.has(option))) {
          errors.push(`${prefix}.receipt.rejectedOptions must only include optionsShown entries`);
        }
        if (hasText(receipt.selectedOption) && receipt.rejectedOptions.includes(receipt.selectedOption)) {
          errors.push(`${prefix}.receipt.selectedOption must not be in rejectedOptions`);
        }
      }
    }
    if (!Array.isArray(receipt.selectedComponents) || receipt.selectedComponents.length === 0) errors.push(`${prefix}.receipt.selectedComponents is required`);
    if (!Array.isArray(receipt.evidence) || receipt.evidence.length === 0) errors.push(`${prefix}.receipt.evidence is required`);
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

function commandMatchesGuardrail(guardrail, required, options = {}) {
  const command = `${guardrail?.id || ''} ${guardrail?.command || ''} ${(guardrail?.evidence || []).join(' ')}`;
  if (['git-status', 'worktree-ready', 'no-mistakes', 'pr-evidence', 'pr-review-threads', 'ci-or-skip', 'deterministic-owner-scan', 'test-first-proof', 'implementation-proof', 'implementation-ui-screenshots'].includes(required) && guardrail?.id !== required) {
    return false;
  }
  if (required === 'context-gate') return /check-project-context-gates\.mjs/.test(command) && /--require-all/.test(command);
  if (required === 'state-validation') return /he-state\.mjs/.test(command) && /validate/.test(command);
  if (required === 'quality-gate') return /check-project-quality-gates\.mjs/.test(command) && /--require-push-gate/.test(command);
  if (required === 'git-status') return /git status --short/.test(command);
  if (required === 'worktree-ready') return /ensure-worktree-ready\.sh/.test(command) && /--require-pre-push/.test(command);
  if (required === 'no-mistakes') return /no-mistakes/.test(command) && /axi run\b/.test(command) && /--intent\b/.test(command) && /passed|PASS|clean|no findings/i.test(command);
  if (required === 'pr-evidence') return /repair-pr-evidence\.mjs/.test(command) && /Current head:\s*`?[0-9a-f]{7,40}`?/i.test(command) && /No open no-mistakes findings|outcome:\s*(?:checks-passed|passed)/i.test(command) && /PR screenshots|2x E2E video|No PR screenshots|No 2x E2E video|evidence/i.test(command);
  if (required === 'pr-review-threads') return /repair-pr-evidence\.mjs/.test(command) && /--check-review-threads/.test(command) && /No open GitHub review threads|all GitHub review threads resolved|0 open GitHub review threads|reviewThreads.+checked/i.test(command);
  if (required === 'ci-or-skip') return /\b(gh|no-mistakes|ci|actions)\b/i.test(command) && /passed|green|skipped|not required|no CI/i.test(command);
  if (required === 'deterministic-owner-scan') return /find-deterministic-owner\.mjs/.test(command) && /--json\b/.test(command);
  if (required === 'test-first-proof') return matchesTestFirstProofGuardrail(guardrail, options);
  if (required === 'implementation-proof') return matchesImplementationProofGuardrail(guardrail, options);
  if (required === 'implementation-ui-screenshots') {
    return hasImplementationScreenshotEvidence(guardrail);
  }
  return false;
}

function hasPassedGuardrail(guardrails, required, options = {}) {
  return Array.isArray(guardrails) && guardrails.some((guardrail) => guardrail?.status === 'passed' && commandMatchesGuardrail(guardrail, required, options));
}

function openLearningFindings(state) { return Array.isArray(state.findings) ? state.findings.filter((finding) => finding?.ownerStage === 'he-learn' && ['open', 'owned', 'blocked'].includes(finding.status)) : []; }

function hasUiTouchedStack(state) {
  if (state.planReadiness?.uiReview?.required === true) return true;
  const stacks = Array.isArray(state.guardrailInventory?.touchedStacks) ? state.guardrailInventory.touchedStacks : [];
  return stacks.some((stack) => {
    const text = String(stack || '');
    if (backendRoutePathPattern.test(text) || backendRouteTextPattern.test(text)) return false;
    return hasUiTouchedOwnerClass(text) ||
      uiSurfacePathPattern.test(text) ||
      (/\.dart\b/i.test(text) && dartUiSurfacePathPattern.test(text));
  });
}

function validateImplementationUiScreenshots(state, errors, options = {}) {
  const stage = stages.get(state.stage);
  if (!stage || stage.index < stages.get('he-implement').index || state.next?.ready !== true || !hasUiTouchedStack(state)) return;
  const screenshotGuardrails = Array.isArray(state.guardrails)
    ? state.guardrails.filter((guardrail) => guardrail?.status === 'passed' && commandMatchesGuardrail(guardrail, 'implementation-ui-screenshots', options))
    : [];
  const stageLabel = state.stage === 'he-implement' ? 'he-implement ready handoff' : `${state.stage} ready handoff`;
  if (!screenshotGuardrails.length) {
    errors.push(`${stageLabel} for UI-touched work requires passed guardrail implementation-ui-screenshots with actual implementation screenshot paths before /he:verify`);
    return;
  }
  if (state.stage !== 'he-implement') return;
  const screenshotSequence = Math.max(...screenshotGuardrails.map((guardrail) => Number(guardrail.sequence) || 0));
  const ownerChangeSequence = Number((state.subStages || []).find((item) => item?.id === 'owner-change')?.sequence) || 0;
  const implementationProofSequence = Math.max(0, ...((state.guardrails || [])
    .filter((guardrail) => guardrail?.status === 'passed' && commandMatchesGuardrail(guardrail, 'implementation-proof', options))
    .map((guardrail) => Number(guardrail.sequence) || 0)));
  if (screenshotSequence <= 0 || screenshotSequence <= ownerChangeSequence || screenshotSequence <= implementationProofSequence) {
    errors.push('he-implement ready handoff requires implementation-ui-screenshots sequence after owner-change and implementation-proof');
  }
}

function collectOldCommands(value, pointer = '$', hits = []) {
  if (typeof value === 'string') {
    if (oldCommandPattern.test(value)) hits.push(pointer);
  } else if (Array.isArray(value)) {
    value.forEach((item, index) => collectOldCommands(item, `${pointer}[${index}]`, hits));
  } else if (isObject(value)) {
    for (const [key, item] of Object.entries(value)) {
      collectOldCommands(item, `${pointer}.${key}`, hits);
    }
  }
  return hits;
}

function validate(state, options = {}) {
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
  validateGuardrailInventory(state, errors);
  validateComplianceState(state, errors);
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
  validateAgentWork(state, errors);
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
        validateNoGrillMeLedger(grillMe, errors);
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
          if (uiReview.decisionTool === 'ui-review-receipt' && !['ui_flow', 'visual_design'].includes(uiReview.decisionPurpose)) {
            errors.push('planReadiness.uiReview.decisionPurpose must be ui_flow or visual_design when using ui-review-receipt');
          }
          if (!stringArray(uiReview.designSystemEvidence)) errors.push('planReadiness.uiReview.designSystemEvidence must be string[]');
          if (uiReview.sharedComponentEvidence !== undefined && !stringArray(uiReview.sharedComponentEvidence)) errors.push('planReadiness.uiReview.sharedComponentEvidence must be string[]');
          if (!stringArray(uiReview.evidence)) errors.push('planReadiness.uiReview.evidence must be string[]');
          if (!stringArray(uiReview.tweaks)) errors.push('planReadiness.uiReview.tweaks must be string[]');
          if (uiReview.decisionTool === 'ui-review-receipt') validateUiReviewReceipt(uiReview.receipt, errors, 'planReadiness.uiReview');
          if (uiReview.required === true && uiReview.status === 'accepted') {
            if (uiReview.shownToUser !== true) errors.push('planReadiness.uiReview.shownToUser must be true before UI plan ready');
            if (hasText(uiReview.localhostUrl) && !isLoopbackUrl(uiReview.localhostUrl)) errors.push('planReadiness.uiReview.localhostUrl must be a localhost URL when present');
            if (!hasText(uiReview.reviewSurfacePath)) errors.push('planReadiness.uiReview.reviewSurfacePath is required before UI plan ready');
            if (!hasText(uiReview.userResponse)) errors.push('planReadiness.uiReview.userResponse is required before UI plan ready');
            if (uiReview.designSystemEvidence.length === 0) errors.push('planReadiness.uiReview.designSystemEvidence is required before UI plan ready');
            if ((uiReview.sharedComponentEvidence || []).length === 0) errors.push('planReadiness.uiReview.sharedComponentEvidence is required before UI plan ready');
            if (uiReview.evidence.length === 0) errors.push('planReadiness.uiReview.evidence is required before UI plan ready');
            if (uiReview.tweaks.length === 0) errors.push('planReadiness.uiReview.tweaks must record applied tweaks or none requested');
            if (uiReview.decisionTool !== 'ui-review-receipt') errors.push('planReadiness.uiReview.decisionTool must be ui-review-receipt before UI plan ready');
            if (uiReview.receipt?.status !== 'accepted') errors.push('planReadiness.uiReview.receipt.status must be accepted before UI plan ready');
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
        if (typeof receipt.decision === 'string' && !receiptDecisions.has(receipt.decision)) {
          errors.push(`steps[${index}].receipt.decision must be PASS, CONCERNS, or FAIL`);
        }
        validateHandoverPrompt(receipt, errors, `steps[${index}].receipt`);
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
      const doneReceipts = state.steps.filter((step) => step?.status === 'done' && isObject(step.receipt)).map((step) => step.receipt), finalReceipt = doneReceipts[doneReceipts.length - 1];
      if (!isObject(finalReceipt) || finalReceipt.decision !== 'PASS') errors.push('next.ready true requires final stage receipt decision PASS');
      const blockingFindings = state.findings?.filter((finding) => finding?.blocking === true && ['open', 'owned', 'blocked'].includes(finding.status));
      if (blockingFindings?.length) errors.push('next.ready cannot be true while blocking findings are unresolved');
      const unresolvedLearning = openLearningFindings(state);
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
          }
          if (readiness.uiReview?.decisionTool === 'ui-review-receipt' && !uiMapped) {
            errors.push('he-plan ready handoff cannot use UI review receipt unless Grill Me UI flow or visual design ran');
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
        if (!hasPassedGuardrail(state.guardrails, required, options)) errors.push(`${state.stage} ready handoff requires passed guardrail ${required}`);
      }
      validateSsotOwnerReuse(state, errors);
      validatePlanReadinessForReadyState(state, errors);
      validateImplementOrder(state, errors, options);
      validateImplementationUiScreenshots(state, errors, options);
      validateShipOrder(state, errors);
      if (state.stage === 'he-ship') {
        const learning = openLearningFindings(state);
        if (state.next.target === 'loop-complete' && learning.length) errors.push('he-ship loop-complete requires open learning findings to route to /he:learn');
        if (state.next.target === '/he:learn' && !learning.length) errors.push('he-ship handoff to /he:learn requires an open learning finding');
      }
      if (state.stage === 'he-learn') {
        const closedLearning = state.findings?.filter((finding) => finding?.ownerStage === 'he-learn' && ['fixed', 'accepted'].includes(finding.status));
        if (!closedLearning?.length) errors.push('he-learn ready handoff requires a fixed or accepted learning finding');
        const openLearning = openLearningFindings(state);
        if (openLearning.length) errors.push('he-learn loop-complete requires open learning findings to be fixed or accepted');
      }
      if (agentWorkBlocksReady(state)) errors.push('next.ready cannot be true while agentWork is planned, running, stalled, failed, or blocked');
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
  validatePlanReadinessForPlanExit(state, errors);
  return errors;
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

function validateLiveCurrentness(state, errors, options = {}) {
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

function usage() {
  console.error('Usage: he-state.mjs validate [--live-currentness] [--repo <repo>] <state.json> | template');
}

const argv = process.argv.slice(2);
const command = argv[0];
if (command === 'template') {
  console.log(`${JSON.stringify(template(), null, 2)}\n`);
} else if (command === 'validate') {
  let liveCurrentness = false;
  let liveRepo = '';
  let file = '';
  for (let index = 1; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === '--live-currentness') liveCurrentness = true;
    else if (arg === '--repo') {
      liveRepo = argv[index + 1] || '';
      index += 1;
    } else if (!file) {
      file = arg;
    } else {
      usage();
      process.exit(2);
    }
  }
  if (!file) {
    usage();
    process.exit(2);
  }
  let parsed;
  try {
    parsed = JSON.parse(fs.readFileSync(file, 'utf8'));
  } catch (error) {
    console.error(`he-state: cannot read ${file}: ${error.message}`);
    process.exit(1);
  }
  const options = { root: path.dirname(path.resolve(file)), liveRepo: liveRepo ? path.resolve(liveRepo) : '' };
  const errors = validate(parsed, options);
  if (liveCurrentness) validateLiveCurrentness(parsed, errors, options);
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
