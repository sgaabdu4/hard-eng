import { matchesImplementationProofGuardrail } from './he-state-proof.mjs';
import { hasUiTouchedOwnerClass } from './he-state-ssot-owner-reuse.mjs';

export const uiDecisionTools = new Set(['none', 'ui-review-receipt']);
export const uiDecisionPurposes = new Set(['none', 'ui_flow', 'visual_design']);

const uiReviewReceiptStatuses = new Set(['pending', 'shown', 'saved', 'accepted', 'blocked']);
const uiReviewSurfaceKinds = new Set(['real-route', 'react-localhost', 'storybook', 'flutter-widget-preview', 'widgetbook', 'simulator', 'local-html']);
const uiPresentationChannels = new Set(['final-response', 'user-opened-review-surface']);
const browserSurfaceKinds = new Set(['real-route', 'react-localhost', 'storybook', 'local-html']);
const frameworkNativeSurfaceKinds = new Set(['flutter-widget-preview', 'widgetbook']);
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
const stageIndexes = new Map([['he-plan', 1], ['he-implement', 2], ['he-verify', 3], ['he-ship', 4], ['he-learn', 5]]);

function isObject(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

function stringArray(value) {
  return Array.isArray(value) && value.every((item) => typeof item === 'string');
}

function hasText(value) {
  return typeof value === 'string' && value.trim().length > 0;
}

export function isLoopbackUrl(value) {
  if (!hasText(value)) return false;
  try {
    const parsed = new URL(value);
    return ['http:', 'https:'].includes(parsed.protocol) && ['localhost', '127.0.0.1', '[::1]'].includes(parsed.hostname);
  } catch {
    return false;
  }
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

function hasUserVisibleScreenshotEvidence(receipt) {
  const evidence = Array.isArray(receipt?.userVisibleEvidence)
    ? receipt.userVisibleEvidence.filter(hasText).join(' ')
    : '';
  if (hasNegatedScreenshotEvidence(evidence)) return false;
  if (hasPlannedOrFutureScreenshotEvidence(evidence)) return false;
  if (hasAfterAcceptanceScreenshotEvidence(evidence)) return false;
  return hasBeforeAcceptanceScreenshotEvidence(evidence);
}

function hasBeforeVerifyScreenshotEvidence(text) {
  return new RegExp(String.raw`\b(?:${visualArtifactPattern}[\s\S]{0,120}${capturedArtifactPattern}|${capturedArtifactPattern}[\s\S]{0,120}${visualArtifactPattern})\b[\s\S]{0,90}\b${beforePattern}\b[\s\S]{0,90}${verifyStagePattern}\b`, 'i').test(text) ||
    new RegExp(String.raw`\b${beforePattern}\b[\s\S]{0,90}${verifyStagePattern}\b[\s\S]{0,120}\b(?:${visualArtifactPattern}[\s\S]{0,90}${capturedArtifactPattern}|${capturedArtifactPattern}[\s\S]{0,90}${visualArtifactPattern})\b`, 'i').test(text);
}

function hasAfterVerifyScreenshotEvidence(text) {
  const lateVerifyOrder = String.raw`(?:after|following|once|post)\s+(?:the\s+)?${verifyStagePattern}`;
  return new RegExp(String.raw`\b${lateVerifyOrder}\b[\s\S]{0,120}\b(?:${visualArtifactPattern}[\s\S]{0,90}${capturedArtifactPattern}|${capturedArtifactPattern}[\s\S]{0,90}${visualArtifactPattern})\b`, 'i').test(text) ||
    new RegExp(String.raw`\b(?:${visualArtifactPattern}[\s\S]{0,120}${capturedArtifactPattern}|${capturedArtifactPattern}[\s\S]{0,120}${visualArtifactPattern})\b[\s\S]{0,90}\b${lateVerifyOrder}\b`, 'i').test(text);
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

export function matchesImplementationUiScreenshotsGuardrail(guardrail) {
  return hasImplementationScreenshotEvidence(guardrail);
}

function distinctTextCount(values) {
  return new Set(values.filter(hasText).map((item) => item.trim())).size;
}

const screenshotCoverageStopTokens = new Set(['option', 'choice', 'flow', 'layout', 'view', 'screen', 'variant', 'path', 'approach', 'default', 'the', 'and', 'or', 'with', 'for', 'to', 'first', 'second', 'third', 'fourth']);

function evidenceTokens(value) {
  return String(value || '').toLowerCase().match(/[a-z0-9]+/g) || [];
}

function leadingOptionKey(tokens) {
  if (/^(?:[a-z]|\d{1,2})$/.test(tokens[0] || '')) return { key: tokens[0], used: 1 };
  if (tokens[0] === 'option' && /^(?:[a-z]|\d{1,2})$/.test(tokens[1] || '')) return { key: tokens[1], used: 2 };
  return { key: '', used: 0 };
}

function optionScreenshotNeedles(option) {
  const tokens = evidenceTokens(option);
  const { key, used } = leadingOptionKey(tokens);
  const labelTokens = tokens.slice(used).filter((token) => token.length >= 3 && !screenshotCoverageStopTokens.has(token));
  const needles = new Set(key ? [key] : []);
  if (labelTokens.length) {
    needles.add(labelTokens.join('-'));
    for (const token of labelTokens) needles.add(token);
  }
  return [...needles];
}

function screenshotPathCoversOption(path, option) {
  const tokens = evidenceTokens(path);
  const tokenSet = new Set(tokens);
  const normalized = tokens.join('-');
  return optionScreenshotNeedles(option).some((needle) => (
    needle.length <= 2 ? tokenSet.has(needle) : normalized.includes(needle)
  ));
}

function uncoveredScreenshotOptions(receipt) {
  if (!stringArray(receipt?.optionsShown) || !stringArray(receipt?.screenshotPaths)) return [];
  return receipt.optionsShown.filter((option) => !receipt.screenshotPaths.some((path) => screenshotPathCoversOption(path, option)));
}

export function validateUiReviewReceipt(receipt, errors, prefix) {
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
    if (frameworkNativeSurfaceKinds.has(receipt.surfaceKind) && !isLoopbackUrl(receipt.surfaceUrl) && !hasText(receipt.deviceTarget)) {
      errors.push(`${prefix}.receipt.surfaceUrl or deviceTarget is required for ${receipt.surfaceKind} review`);
    }
    if (!Array.isArray(receipt.optionsShown) || receipt.optionsShown.length < 2) errors.push(`${prefix}.receipt.optionsShown must include at least two UI options`);
    if (!Array.isArray(receipt.rejectedOptions) || receipt.rejectedOptions.length === 0) errors.push(`${prefix}.receipt.rejectedOptions must include at least one rejected UI option`);
    if (!isObject(receipt.presentation)) {
      errors.push(`${prefix}.receipt.presentation is required for accepted`);
    } else {
      if (!uiPresentationChannels.has(receipt.presentation.channel)) {
        errors.push(`${prefix}.receipt.presentation.channel must be final-response or user-opened-review-surface`);
      }
      for (const key of ['surfaceOpened', 'visualsIncluded', 'questionIncluded', 'approvalAfterPresentation']) {
        if (receipt.presentation[key] !== true) errors.push(`${prefix}.receipt.presentation.${key} must be true`);
      }
    }
    const screenshotPathsValid = requireTextArray(receipt.screenshotPaths, errors, `${prefix}.receipt.screenshotPaths`, { minLength: 1 });
    if (screenshotPathsValid && distinctTextCount(receipt.screenshotPaths) !== receipt.screenshotPaths.length) {
      errors.push(`${prefix}.receipt.screenshotPaths must be distinct`);
    }
    if (Array.isArray(receipt.optionsShown) && screenshotPathsValid && distinctTextCount(receipt.screenshotPaths) < receipt.optionsShown.length) {
      errors.push(`${prefix}.receipt.screenshotPaths must include screenshots for every UI option shown`);
    }
    if (screenshotPathsValid && Array.isArray(receipt.optionsShown) && uncoveredScreenshotOptions(receipt).length) {
      errors.push(`${prefix}.receipt.screenshotPaths must reference every UI option shown`);
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

function hasUiTouchedStack(state) {
  if (state.planReadiness?.uiReview?.required === true) return true;
  const stacks = Array.isArray(state.guardrailInventory?.touchedStacks) ? state.guardrailInventory.touchedStacks : [];
  return stacks.some((stack) => String(stack || '')
    .split(/[,\n;]+/)
    .map((item) => item.trim())
    .filter(Boolean)
    .some((text) => {
      if (uiSurfacePathPattern.test(text) || (/\.dart\b/i.test(text) && dartUiSurfacePathPattern.test(text))) return true;
      if (backendRoutePathPattern.test(text) || backendRouteTextPattern.test(text)) return false;
      return hasUiTouchedOwnerClass(text);
    }));
}

function positiveSequence(value) {
  return Number.isInteger(value) && value > 0 ? value : 0;
}

function sequenceAfter(guardrail, id) {
  return positiveSequence(guardrail?.sequenceAfter?.[id]);
}

function passedImplementationScreenshotGuardrail(guardrail) {
  return guardrail?.id === 'implementation-ui-screenshots' &&
    guardrail?.status === 'passed' &&
    hasImplementationScreenshotEvidence(guardrail);
}

export function validateImplementationUiScreenshots(state, errors, options = {}) {
  const stageIndex = stageIndexes.get(state.stage);
  if (!stageIndex || stageIndex < stageIndexes.get('he-implement') || state.next?.ready !== true || !hasUiTouchedStack(state)) return;
  const screenshotGuardrails = Array.isArray(state.guardrails)
    ? state.guardrails.filter(passedImplementationScreenshotGuardrail)
    : [];
  const stageLabel = state.stage === 'he-implement' ? 'he-implement ready handoff' : `${state.stage} ready handoff`;
  const implementationStageScreenshotGuardrails = screenshotGuardrails.filter((guardrail) => guardrail?.stage === 'he-implement');
  if (!implementationStageScreenshotGuardrails.length) {
    errors.push(`${stageLabel} for UI-touched work requires passed he-implement guardrail implementation-ui-screenshots with actual implementation screenshot paths before /he:verify`);
    return;
  }
  const currentOwnerChangeSequence = positiveSequence((state.subStages || []).find((item) => item?.id === 'owner-change')?.sequence);
  const implementationProofSequence = Math.max(0, ...((state.guardrails || [])
    .filter((guardrail) => guardrail?.id === 'implementation-proof' && guardrail?.stage === 'he-implement' && guardrail?.status === 'passed' && matchesImplementationProofGuardrail(guardrail, options))
    .map((guardrail) => positiveSequence(guardrail.sequence))));
  const hasOrderedScreenshotProof = implementationStageScreenshotGuardrails.some((guardrail) => {
    const screenshotSequence = positiveSequence(guardrail.sequence);
    const ownerChangeSequence = state.stage === 'he-implement'
      ? currentOwnerChangeSequence
      : sequenceAfter(guardrail, 'owner-change');
    return screenshotSequence > 0 &&
      ownerChangeSequence > 0 &&
      implementationProofSequence > ownerChangeSequence &&
      screenshotSequence > implementationProofSequence;
  });
  if (!hasOrderedScreenshotProof) {
    errors.push('he-implement ready handoff requires implementation-ui-screenshots sequence after owner-change and implementation-proof');
  }
}
