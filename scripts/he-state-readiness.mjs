function isObject(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

function hasText(value) {
  return typeof value === 'string' && value.trim().length > 0;
}

function textFrom(values) {
  return values.flat(Infinity).filter(hasText).join(' ');
}

function uiStageMapped(grillMe) {
  return Array.isArray(grillMe?.stages) &&
    grillMe.stages.some((item) => ['ui-flow', 'visual-design'].includes(item?.id) && ['run', 'brief'].includes(item?.map));
}

function alignedForReady(alignment, openKeys) {
  return isObject(alignment) &&
    alignment.status === 'aligned' &&
    alignment.userConfirmed === true &&
    alignment.noGuesswork === true &&
    Array.isArray(alignment.evidence) &&
    alignment.evidence.some(hasText) &&
    openKeys.every((key) => Array.isArray(alignment[key]) && alignment[key].length === 0);
}

function hasApprovedSkipEvidence(grillMe) {
  const stageText = Array.isArray(grillMe?.stages)
    ? grillMe.stages.flatMap((stage) => [stage.reason, stage.evidence])
    : [];
  const text = textFrom([grillMe?.reason, grillMe?.evidence, grillMe?.skipEvidence, stageText]);
  return /\buser(?:[- ]visible)?\b.{0,80}\b(approved|confirmed|requested|accepted|explicit)\b.{0,80}\b(skip|not required|no grill me)\b/i.test(text) ||
    /\b(skip|not required|no grill me)\b.{0,80}\b(approved|confirmed|requested|accepted)\b.{0,80}\buser\b/i.test(text);
}

function grillMeSkipNeedsApproval(state, readiness) {
  const contextChanged = Object.values(state.context || {}).some((entry) => ['updated', 'created'].includes(entry?.status));
  const acceptedArtifact = readiness.artifact?.status === 'accepted';
  const uiReviewRequired = readiness.uiReview?.required === true;
  const mappedWork = Array.isArray(readiness.grillMe?.stages) &&
    readiness.grillMe.stages.some((stage) => ['product', 'ui-flow', 'visual-design'].includes(stage?.id));
  return contextChanged || acceptedArtifact || uiReviewRequired || mappedWork;
}

function validateRequiredUiReview(readiness, errors) {
  const uiReview = readiness.uiReview;
  if (!isObject(uiReview) || uiReview.required !== true) return;
  if (uiReview.status !== 'accepted') errors.push('next.ready cannot be true while required UI review is not accepted');
  if (uiReview.shownToUser !== true) errors.push('next.ready true requires required UI review to be shown to the user');
  if (!hasText(uiReview.reviewSurfacePath)) errors.push('next.ready true requires required UI review surface evidence');
  if (!hasText(uiReview.userResponse)) errors.push('next.ready true requires required UI review user approval evidence');
  if (!Array.isArray(uiReview.designSystemEvidence) || uiReview.designSystemEvidence.length === 0) errors.push('next.ready true requires required UI review design system evidence');
  if (!Array.isArray(uiReview.sharedComponentEvidence) || uiReview.sharedComponentEvidence.length === 0) errors.push('next.ready true requires required UI review shared component evidence');
  if (!Array.isArray(uiReview.evidence) || uiReview.evidence.length === 0) errors.push('next.ready true requires required UI review evidence');
  if (!alignedForReady(uiReview.alignment, ['openDecisions', 'openUnknowns'])) {
    errors.push('next.ready true requires required UI review to be aligned with no open decisions or unknowns');
  }
}

function hasLearningFinding(state) {
  return Array.isArray(state.findings) && state.findings.some((finding) => (
    finding?.ownerStage === 'he-learn' &&
    ['learning', 'process'].includes(finding?.repairType) &&
    ['open', 'owned', 'blocked'].includes(finding?.status)
  ));
}

function hasRepeatMisses(state) {
  return Array.isArray(state.repeatMisses) && state.repeatMisses.length > 0;
}

function hasUserCaughtProcessMiss(state) {
  const findingText = Array.isArray(state.findings)
    ? state.findings.flatMap((finding) => [finding.summary, finding.ownerProof, finding.artifacts])
    : [];
  const text = textFrom([findingText, state.decisions, state.blockers]);
  return /\b(user[- ]caught|user caught|caught by user|workflow miss|process miss|missed workflow|same miss again)\b/i.test(text);
}

export function validatePlanReadinessForReadyState(state, errors) {
  if (state.next?.ready !== true) return;
  if (hasUserCaughtProcessMiss(state) && !hasRepeatMisses(state) && !hasLearningFinding(state)) {
    errors.push('next.ready true requires user-caught workflow/process misses in repeatMisses[] or he-learn learning findings');
  }
  if (!isObject(state.planReadiness)) return;
  const readiness = state.planReadiness;
  const grillMe = readiness.grillMe;
  const uiMapped = uiStageMapped(grillMe);
  if (uiMapped) {
    if (!isObject(readiness.uiReview)) {
      errors.push('he-plan ready handoff requires planReadiness.uiReview when UI flow or visual design ran');
    } else if (readiness.uiReview.required !== true || readiness.uiReview.status !== 'accepted') {
      errors.push('he-plan ready handoff requires UI review to be accepted when UI flow or visual design ran');
    }
  }
  validateRequiredUiReview(readiness, errors);
  if (isObject(grillMe) && grillMe.required === false && grillMeSkipNeedsApproval(state, readiness) && !hasApprovedSkipEvidence(grillMe)) {
    errors.push('next.ready true requires explicit user-approved Grill Me skip evidence for feature, product, design, UI, or ambiguous work');
  }
}
