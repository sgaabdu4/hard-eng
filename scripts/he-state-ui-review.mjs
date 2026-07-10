import fs from 'node:fs';
import { createHash } from 'node:crypto';
import { matchesImplementationProofGuardrail } from './he-state-proof.mjs';
import { resolveProjectFile } from './he-state-project-files.mjs';
import { hasUiTouchedOwnerClass } from './he-state-ssot-owner-reuse.mjs';

export const uiDecisionTools = new Set(['none', 'ui-review-receipt']);
export const uiDecisionPurposes = new Set(['none', 'ui_flow', 'visual_design']);

const uiReviewReceiptStatuses = new Set(['pending', 'shown', 'saved', 'accepted', 'blocked']);
const uiReviewSurfaceKinds = new Set(['real-route', 'react-localhost', 'storybook', 'flutter-widget-preview', 'widgetbook', 'simulator', 'local-html']);
const uiPresentationChannels = new Set(['user-opened-review-surface']);
const uiPresentationTools = new Set(['browser', 'chrome', 'computer-use']);
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

function implementationScreenshotPaths(evidence) {
  return [...new Set([...String(evidence || '').matchAll(/(?:^|[\s:(])([A-Za-z0-9_.\/-]+\.(?:png|jpe?g|webp))\b/gi)].map((match) => match[1]))];
}

function hasImplementationScreenshotEvidence(guardrail, options = {}) {
  const evidence = Array.isArray(guardrail?.evidence) ? guardrail.evidence.filter(hasText).join(' ') : '';
  if (hasNegatedScreenshotEvidence(evidence)) return false;
  if (hasPlannedOrFutureScreenshotEvidence(evidence)) return false;
  if (hasAfterVerifyScreenshotEvidence(evidence)) return false;
  const paths = implementationScreenshotPaths(evidence);
  return (
    new RegExp(String.raw`\b${capturedArtifactPattern}\b[\s\S]{0,90}\b(?:screenshot|screenshots|image|images)\b`, 'i').test(evidence) ||
    new RegExp(String.raw`\b(?:screenshot|screenshots|image|images)\b[\s\S]{0,90}\b${capturedArtifactPattern}\b`, 'i').test(evidence)
  ) &&
    hasBeforeVerifyScreenshotEvidence(evidence) &&
    /\b(?:actual|implemented|implementation|real\s+(?:app|route|screen|ui)|localhost|simulator|storybook|widgetbook)\b/i.test(evidence) &&
    paths.length > 0 && paths.every((value) => isVerifiedImage(resolveProjectFile(value, options)));
}

export function matchesImplementationUiScreenshotsGuardrail(guardrail, options = {}) {
  return hasImplementationScreenshotEvidence(guardrail, options);
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

function validateProjectArtifact(value, errors, pointer, options) {
  const resolved = resolveProjectFile(value, options);
  if (!resolved.ok) errors.push(`${pointer} ${resolved.error}`);
  return resolved;
}

function crc32(bytes) {
  let crc = 0xffffffff;
  for (const byte of bytes) {
    crc ^= byte;
    for (let bit = 0; bit < 8; bit += 1) crc = (crc >>> 1) ^ (crc & 1 ? 0xedb88320 : 0);
  }
  return (crc ^ 0xffffffff) >>> 0;
}

function validPng(bytes) {
  if (bytes.length < 20 || !bytes.subarray(0, 8).equals(Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]))) return false;
  let offset = 8;
  let sawHeader = false;
  let sawImageData = false;
  while (offset + 12 <= bytes.length) {
    const length = bytes.readUInt32BE(offset);
    const end = offset + 12 + length;
    if (end > bytes.length) return false;
    const type = bytes.subarray(offset + 4, offset + 8).toString('ascii');
    const expectedCrc = bytes.readUInt32BE(offset + 8 + length);
    if (crc32(bytes.subarray(offset + 4, offset + 8 + length)) !== expectedCrc) return false;
    if (!sawHeader) {
      if (type !== 'IHDR' || length !== 13 || bytes.readUInt32BE(offset + 8) < 1 || bytes.readUInt32BE(offset + 12) < 1) return false;
      sawHeader = true;
    }
    if (type === 'IDAT') sawImageData = true;
    if (type === 'IEND') return sawHeader && sawImageData && length === 0 && end === bytes.length;
    offset = end;
  }
  return false;
}

function validJpeg(bytes) {
  if (bytes.length < 4 || bytes[0] !== 0xff || bytes[1] !== 0xd8 || bytes.at(-2) !== 0xff || bytes.at(-1) !== 0xd9) return false;
  let offset = 2;
  while (offset + 4 <= bytes.length - 2) {
    if (bytes[offset] !== 0xff) return false;
    while (bytes[offset] === 0xff) offset += 1;
    const marker = bytes[offset++];
    if ([0x01, 0xd8, 0xd9].includes(marker) || marker >= 0xd0 && marker <= 0xd7) continue;
    if (offset + 2 > bytes.length) return false;
    const length = bytes.readUInt16BE(offset);
    if (length < 2 || offset + length > bytes.length) return false;
    if ([0xc0, 0xc1, 0xc2, 0xc3, 0xc5, 0xc6, 0xc7, 0xc9, 0xca, 0xcb, 0xcd, 0xce, 0xcf].includes(marker)) {
      return length >= 7 && bytes.readUInt16BE(offset + 3) > 0 && bytes.readUInt16BE(offset + 5) > 0;
    }
    offset += length;
  }
  return false;
}

function validWebp(bytes) {
  if (bytes.length < 30 || bytes.subarray(0, 4).toString('ascii') !== 'RIFF' || bytes.subarray(8, 12).toString('ascii') !== 'WEBP') return false;
  if (bytes.readUInt32LE(4) + 8 !== bytes.length) return false;
  const type = bytes.subarray(12, 16).toString('ascii');
  const length = bytes.readUInt32LE(16);
  if (20 + length > bytes.length) return false;
  if (type === 'VP8X') return length >= 10;
  if (type === 'VP8L') return length >= 5 && bytes[20] === 0x2f;
  return type === 'VP8 ' && length >= 10 && bytes.subarray(23, 26).equals(Buffer.from([0x9d, 0x01, 0x2a]));
}

function isVerifiedImage(file) {
  if (!file?.ok) return false;
  const bytes = fs.readFileSync(file.absolute);
  return validPng(bytes) || validJpeg(bytes) || validWebp(bytes);
}

function fileContainsValues(file, values) {
  if (!file?.ok) return false;
  const text = fs.readFileSync(file.absolute, 'utf8');
  return values.filter(hasText).every((value) => text.includes(value));
}

function fileDigest(file) {
  return file?.ok ? createHash('sha256').update(fs.readFileSync(file.absolute)).digest('hex') : '';
}

function parseJsonFile(file) {
  if (!file?.ok) return null;
  try {
    return JSON.parse(fs.readFileSync(file.absolute, 'utf8'));
  } catch {
    return null;
  }
}

function validEventTime(value) {
  return hasText(value) && Number.isFinite(Date.parse(value));
}

function validatePresentationEvent(receipt, projectArtifacts, screenshotFiles, errors, prefix, options) {
  const presentation = receipt.presentation;
  if (!isObject(presentation)) return;
  const eventFile = validateProjectArtifact(presentation.eventPath, errors, `${prefix}.receipt.presentation.eventPath`, options);
  const event = parseJsonFile(eventFile);
  if (!event) {
    if (eventFile.ok) errors.push(`${prefix}.receipt.presentation.eventPath must contain valid JSON tool-event evidence`);
    return;
  }
  if (event.schema !== 'ui-presentation/v1') errors.push(`${prefix}.receipt.presentation event schema must be ui-presentation/v1`);
  for (const [key, expected] of [
    ['eventId', presentation.eventId],
    ['tool', presentation.tool],
    ['channel', presentation.channel],
    ['surfacePath', receipt.artifactPath],
    ['surfaceUrl', receipt.surfaceUrl || ''],
    ['questionText', receipt.questionText],
    ['presentedAt', presentation.presentedAt],
  ]) {
    if (event[key] !== expected) errors.push(`${prefix}.receipt.presentation event ${key} must bind the accepted receipt`);
  }
  if (event.surfaceSha256 !== fileDigest(projectArtifacts.get('artifactPath'))) {
    errors.push(`${prefix}.receipt.presentation event surfaceSha256 must bind artifactPath`);
  }
  if (!isObject(event.screenshotSha256)) {
    errors.push(`${prefix}.receipt.presentation event screenshotSha256 must bind screenshotPaths`);
  } else {
    for (const [screenshotPath, screenshot] of screenshotFiles) {
      if (event.screenshotSha256[screenshotPath] !== fileDigest(screenshot)) {
        errors.push(`${prefix}.receipt.presentation event screenshotSha256 must bind ${screenshotPath}`);
      }
    }
  }
  if (!isObject(event.approval) || event.approval.decision !== receipt.userDecision || event.approval.selectedOption !== receipt.selectedOption || event.approval.approvedAt !== presentation.approvedAt) {
    errors.push(`${prefix}.receipt.presentation event approval must bind userDecision, selectedOption, and approvedAt`);
  }
  if (!validEventTime(presentation.presentedAt) || !validEventTime(presentation.approvedAt) || Date.parse(presentation.approvedAt) <= Date.parse(presentation.presentedAt)) {
    errors.push(`${prefix}.receipt.presentation approvedAt must be after presentedAt`);
  }
}

export function validateUiReviewReceipt(receipt, errors, prefix, options = {}) {
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
        errors.push(`${prefix}.receipt.presentation.channel must be user-opened-review-surface`);
      }
      if (!uiPresentationTools.has(receipt.presentation.tool)) errors.push(`${prefix}.receipt.presentation.tool must identify browser, chrome, or computer-use`);
      for (const key of ['eventId', 'eventPath', 'presentedAt', 'approvedAt']) {
        if (!hasText(receipt.presentation[key])) errors.push(`${prefix}.receipt.presentation.${key} is required`);
      }
      if (hasText(receipt.presentation.eventId) && !/^[A-Za-z0-9][A-Za-z0-9._:-]{11,}$/.test(receipt.presentation.eventId)) {
        errors.push(`${prefix}.receipt.presentation.eventId must be a stable tool event identifier`);
      }
      if (receipt.presentation.eventPath === receipt.receiptPath || receipt.presentation.eventPath === receipt.artifactPath) {
        errors.push(`${prefix}.receipt.presentation.eventPath must be a distinct tool-event receipt`);
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
    const projectArtifacts = new Map();
    for (const key of ['artifactPath', 'receiptPath', 'savedChoicesPath', 'savedComponentsPath']) {
      if (hasText(receipt[key])) projectArtifacts.set(key, validateProjectArtifact(receipt[key], errors, `${prefix}.receipt.${key}`, options));
    }
    const receiptValues = [
      receipt.userDecision,
      receipt.selectedOption,
      ...(stringArray(receipt.optionsShown) ? receipt.optionsShown : []),
      ...(stringArray(receipt.rejectedOptions) ? receipt.rejectedOptions : []),
      ...(stringArray(receipt.screenshotPaths) ? receipt.screenshotPaths : []),
    ];
    if (projectArtifacts.get('receiptPath')?.ok && !fileContainsValues(projectArtifacts.get('receiptPath'), receiptValues)) {
      errors.push(`${prefix}.receipt.receiptPath must bind the decision, options, and screenshotPaths`);
    }
    if (projectArtifacts.get('savedChoicesPath')?.ok && !fileContainsValues(projectArtifacts.get('savedChoicesPath'), [receipt.selectedOption, ...(stringArray(receipt.rejectedOptions) ? receipt.rejectedOptions : [])])) {
      errors.push(`${prefix}.receipt.savedChoicesPath must bind selectedOption and rejectedOptions`);
    }
    if (projectArtifacts.get('savedComponentsPath')?.ok && !fileContainsValues(projectArtifacts.get('savedComponentsPath'), stringArray(receipt.selectedComponents) ? receipt.selectedComponents : [])) {
      errors.push(`${prefix}.receipt.savedComponentsPath must bind selectedComponents`);
    }
    const screenshotFiles = new Map();
    if (screenshotPathsValid) {
      for (const screenshotPath of receipt.screenshotPaths) {
        const screenshot = validateProjectArtifact(screenshotPath, errors, `${prefix}.receipt.screenshotPaths entry ${screenshotPath}`, options);
        screenshotFiles.set(screenshotPath, screenshot);
        if (screenshot.ok && !isVerifiedImage(screenshot)) {
          errors.push(`${prefix}.receipt.screenshotPaths entry ${screenshotPath} must be a valid PNG, JPEG, or WebP image`);
        }
      }
    }
    if (isObject(receipt.presentation) && hasText(receipt.presentation.eventPath)) {
      validatePresentationEvent(receipt, projectArtifacts, screenshotFiles, errors, prefix, options);
    }
    requireTextArray(receipt.userVisibleEvidence, errors, `${prefix}.receipt.userVisibleEvidence`, { minLength: 1 });
    if (!hasUserVisibleScreenshotEvidence(receipt)) {
      errors.push(`${prefix}.receipt.userVisibleEvidence must prove screenshots or visual artifacts were shown to the user before acceptance`);
    }
    const visibleEvidence = stringArray(receipt.userVisibleEvidence) ? receipt.userVisibleEvidence.join(' ') : '';
    if (screenshotPathsValid && receipt.screenshotPaths.some((screenshotPath) => !visibleEvidence.includes(screenshotPath))) {
      errors.push(`${prefix}.receipt.userVisibleEvidence must reference every screenshotPaths entry`);
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

function passedImplementationScreenshotGuardrail(guardrail, options) {
  return guardrail?.id === 'implementation-ui-screenshots' &&
    guardrail?.status === 'passed' &&
    hasImplementationScreenshotEvidence(guardrail, options);
}

export function validateImplementationUiScreenshots(state, errors, options = {}) {
  const stageIndex = stageIndexes.get(state.stage);
  if (!stageIndex || stageIndex < stageIndexes.get('he-implement') || state.next?.ready !== true || !hasUiTouchedStack(state)) return;
  const screenshotGuardrails = Array.isArray(state.guardrails)
    ? state.guardrails.filter((guardrail) => passedImplementationScreenshotGuardrail(guardrail, options))
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
