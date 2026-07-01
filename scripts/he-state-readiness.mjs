function isObject(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

function hasText(value) {
  return typeof value === 'string' && value.trim().length > 0;
}

function textFrom(values) {
  return values.flat(Infinity).filter(hasText).join(' ');
}

function stringsFrom(value) {
  if (typeof value === 'string') return [value];
  if (Array.isArray(value)) return value.flatMap(stringsFrom);
  if (isObject(value)) return Object.values(value).flatMap(stringsFrom);
  return [];
}

function normalizeText(value) {
  return String(value || '')
    .replace(/([a-z0-9])([A-Z])/g, '$1 $2')
    .replace(/[^a-z0-9]+/gi, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .toLowerCase();
}

function normalizeIssueClass(value) {
  return normalizeText(value).replace(/\s+/g, '-').replace(/^-|-$/g, '');
}

function evidenceClauses(text) {
  const value = String(text || '');
  return value
    .split(/(?:[.;\n]+|,?\s+\b(?:but|however|yet|although|though)\b\s+)/i)
    .map((segment) => segment.trim())
    .filter(Boolean);
}

function stemToken(token) {
  if (/^skipp?(?:ed|ing|s)?$/.test(token)) return 'skip';
  if (/^miss(?:ed|es|ing)?$/.test(token)) return 'miss';
  if (/^approv(?:al|ed|es|ing)?$/.test(token)) return 'approval';
  if (/^complet(?:e|ed|es|ing)?$/.test(token)) return 'complete';
  return token;
}

const genericMissTokens = new Set([
  'a',
  'again',
  'an',
  'and',
  'are',
  'as',
  'at',
  'after',
  'be',
  'been',
  'before',
  'by',
  'captured',
  'complete',
  'caught',
  'durable',
  'feedback',
  'for',
  'from',
  'gap',
  'guard',
  'had',
  'has',
  'he',
  'in',
  'is',
  'learn',
  'miss',
  'needs',
  'of',
  'on',
  'or',
  'process',
  'record',
  'recorded',
  'repeated',
  'review',
  'required',
  'requires',
  'same',
  'that',
  'the',
  'to',
  'until',
  'user',
  'was',
  'were',
  'when',
  'where',
  'with',
  'workflow',
]);

function meaningfulTokens(value) {
  return new Set(normalizeText(value)
    .split(' ')
    .map(stemToken)
    .filter((token) => token.length > 1 && !genericMissTokens.has(token)));
}

function textMatchesMiss(missText, recordText) {
  const missTokens = meaningfulTokens(missText);
  const recordTokens = meaningfulTokens(recordText);
  if (!missTokens.size || !recordTokens.size) return false;
  const shared = [...missTokens].filter((token) => recordTokens.has(token)).length;
  const smallerSize = Math.min(missTokens.size, recordTokens.size);
  if (smallerSize === 1) return missTokens.size === recordTokens.size && shared === 1;
  if (smallerSize === 2) return shared === 2;
  return shared / smallerSize >= 0.75;
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

function hasNegatedApprovedSkipEvidence(text) {
  const normalized = normalizeText(text);
  return [
    /\b(?:no|without|missing|absent)\s+(?:explicit\s+)?(?:user\s+)?(?:approved|approval|confirmation|confirmed|request|requested|accepted)\s+(?:to\s+)?(?:grill\s+me\s+)?(?:skip|skipping|not\s+required|evidence)\b/,
    /\buser\s+(?:has\s+|had\s+|does\s+|did\s+|is\s+|was\s+)?(?:not|never)\s+(?:approved|confirmed|requested|accepted)\s+(?:the\s+)?(?:grill\s+me\s+)?(?:skip|skipping|not\s+required|no\s+grill\s+me)\b/,
    /\buser\b.{0,60}\b(?:not|never)\s+(?:asked|consulted|shown|prompted)\b/,
    /\buser\b.{0,60}\b(?:declined|rejected|refused|denied)\b(?:.{0,60}\b(?:skip|skipping|not\s+required|no\s+grill\s+me|grill\s+me)\b)?/,
    /\b(?:skip|skipping|grill\s+me|not\s+required|no\s+grill\s+me)\b.{0,80}\b(?:not|never)\b.{0,40}\b(?:approved|confirmed|requested|accepted|approval|confirmation)\b.{0,80}\buser\b/,
    /\buser\b.{0,80}\b(?:approved|confirmed|requested|accepted|approval|confirmation)\b.{0,40}\b(?:not|never)\s+to\s+(?:skip|skip\s+grill\s+me|make\s+grill\s+me\s+not\s+required)\b/,
    /\b(?:skip|skipping|grill\s+me)\s+(?:approval|evidence)\s+(?:is\s+|was\s+)?(?:missing|absent|not\s+present|not\s+recorded)\b/,
    /\b(?:agent|assistant|system|codex|tool)\s+(?:explicitly\s+)?(?:approved|confirmed|requested|accepted|approval|confirmation)\b.{0,80}\b(?:skip|skipping|not\s+required|no\s+grill\s+me|grill\s+me\s+skip)\b/,
    /\b(?:skip|skipping|not\s+required|no\s+grill\s+me|grill\s+me\s+skip)\b.{0,80}\b(?:approved|confirmed|requested|accepted|approval|confirmation)\s+(?:by|from)\s+(?:agent|assistant|system|codex|tool)\b/,
  ].some((pattern) => pattern.test(normalized));
}

function hasUserApprovedSkipClause(clause) {
  if (hasNegatedApprovedSkipEvidence(clause)) return false;
  const normalized = normalizeText(clause);
  return [
    /\buser(?:\s+visible)?\b.{0,80}\b(?:approved|approval|confirmed|confirmation|requested|accepted|agreed|consented)\b.{0,80}\b(?:skip|skipping|not\s+required|no\s+grill\s+me|grill\s+me\s+not\s+required|grill\s+me\s+skip)\b/,
    /\b(?:skip|skipping|not\s+required|no\s+grill\s+me|grill\s+me\s+not\s+required|grill\s+me\s+skip)\b.{0,80}\b(?:approved|approval|confirmed|confirmation|requested|accepted|agreed|consented)\b.{0,80}\buser\b/,
  ].some((pattern) => pattern.test(normalized));
}

function hasApprovedSkipEvidence(grillMe) {
  const stageText = Array.isArray(grillMe?.stages)
    ? grillMe.stages.flatMap((stage) => [stage.reason, stage.evidence])
    : [];
  const text = textFrom([grillMe?.reason, grillMe?.evidence, grillMe?.skipEvidence, stageText]);
  if (hasNegatedApprovedSkipEvidence(text)) return false;
  const clauses = evidenceClauses(text);
  return (clauses.length ? clauses : [text]).some(hasUserApprovedSkipClause);
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

function validateReadyArtifact(readiness, errors) {
  const artifact = readiness.artifact;
  if (isObject(artifact) && !['not_required', 'accepted'].includes(artifact.status)) {
    errors.push('he-plan ready handoff requires the plan artifact to be accepted or not_required');
  }
}

function validateLavishUiMapping(readiness, uiMapped, errors) {
  if (readiness.uiReview?.decisionTool === 'lavish' && !uiMapped) {
    errors.push('he-plan ready handoff cannot use Lavish unless Grill Me UI flow or visual design ran');
  }
}

function validateRequiredGrillMe(grillMe, errors) {
  if (!isObject(grillMe)) {
    errors.push('next.ready true requires planReadiness.grillMe');
    return;
  }
  if (grillMe.required !== true) return;
  if (grillMe.status !== 'accepted') errors.push('next.ready true requires required Grill Me to be accepted');
  if (grillMe.questionPolicy?.mode !== 'unlimited_until_aligned') errors.push('next.ready true requires unlimited Grill Me questions until aligned');
  if (!alignedForReady(grillMe.alignment, ['openQuestions', 'openUnknowns'])) {
    errors.push('next.ready true requires required Grill Me to be aligned with no open questions or unknowns');
  }
  const unresolvedStages = Array.isArray(grillMe.stages)
    ? grillMe.stages.filter((item) => ['run', 'brief'].includes(item?.map) && ['pending', 'in_progress', 'blocked'].includes(item?.status))
    : [];
  if (unresolvedStages.length) errors.push('next.ready true cannot have unresolved Grill Me stages');
  if (['draft', 'asked'].includes(grillMe.lastQuestion?.status)) errors.push('next.ready true cannot have an open Grill Me question');
  if (grillMe.lastQuestion?.status === 'parked') errors.push('next.ready true cannot have a parked Grill Me question');
  if (grillMe.lastQuestion?.status !== 'none' && !hasText(grillMe.lastQuestion?.visibleText)) {
    errors.push('next.ready true requires the visible Grill Me question text');
  }
}

function learningFindingStatuses(state) {
  return state.stage === 'he-learn' && state.next?.target === 'loop-complete'
    ? ['open', 'owned', 'blocked', 'fixed', 'accepted']
    : ['open', 'owned', 'blocked'];
}

function learningFindings(state) {
  const statuses = learningFindingStatuses(state);
  return Array.isArray(state.findings)
    ? state.findings.filter((finding) => (
      finding?.ownerStage === 'he-learn' &&
      ['learning', 'process'].includes(finding?.repairType) &&
      statuses.includes(finding?.status)
    ))
    : [];
}

const userCaughtProcessMissPattern = /\b(user[- ]caught|user caught|caught by user|workflow miss|process miss|missed workflow|same miss again)\b/i;
const userCaughtProcessMissAbsencePatterns = [
  /\b(?:no|without|missing|absent)\s+(?:evidence\s+of\s+)?(?:user\s+caught\s+|caught\s+by\s+user\s+)?(?:(?:workflow|process)\s+)*(?:miss|misses|missed\s+workflow)\b/i,
  /\b(?:(?:workflow|process)\s+)*(?:miss|misses|missed\s+workflow)\s+(?:is\s+|are\s+|was\s+|were\s+)?not\s+(?:found|present|detected|recorded|observed)\b/i,
  /\b(?:(?:workflow|process)\s+)*(?:miss|misses|missed\s+workflow)\s+(?:is\s+|are\s+|was\s+|were\s+)?(?:missing|absent)\b/i,
  /\bnot\s+(?:a\s+|an\s+|the\s+)?(?:user\s+caught\s+|caught\s+by\s+user\s+)?(?:(?:workflow|process)\s+)*(?:miss|misses|missed\s+workflow)\b/i,
];

function hasUserCaughtProcessMissEvidence(text) {
  const value = String(text || '');
  if (!userCaughtProcessMissPattern.test(value)) return false;
  const segments = evidenceClauses(value);
  return (segments.length ? segments : [value]).some((segment) => (
    userCaughtProcessMissPattern.test(segment) &&
    !userCaughtProcessMissAbsencePatterns.some((pattern) => pattern.test(normalizeText(segment)))
  ));
}

function userCaughtProcessMisses(state) {
  const misses = [];
  if (Array.isArray(state.findings)) {
    for (const finding of state.findings) {
      const processEvidence = textFrom([finding?.summary, finding?.ownerProof, finding?.artifacts]);
      if (hasUserCaughtProcessMissEvidence(processEvidence)) {
        misses.push({
          issueClass: hasText(finding?.issueClass) ? normalizeIssueClass(finding.issueClass) : '',
          evidence: textFrom([finding?.issueClass, processEvidence]),
        });
      }
    }
  }
  for (const evidence of [...stringsFrom(state.decisions), ...stringsFrom(state.blockers)]) {
    if (hasUserCaughtProcessMissEvidence(evidence)) misses.push({ issueClass: '', evidence });
  }
  return misses;
}

function repeatMisses(state) {
  return Array.isArray(state.repeatMisses) ? state.repeatMisses.filter(isObject) : [];
}

function learningFindingText(finding) {
  return textFrom([finding?.issueClass, finding?.summary, finding?.owner, finding?.ownerProof, finding?.artifacts]);
}

function repeatMissText(miss) {
  return textFrom([miss?.issueClass, miss?.evidence]);
}

function recordMatchesMiss(miss, issueClass, text) {
  if (miss.issueClass && issueClass === miss.issueClass) return true;
  return textMatchesMiss(miss.evidence, text);
}

function hasMatchingRepeatMiss(state, miss) {
  return repeatMisses(state).some((record) => recordMatchesMiss(
    miss,
    hasText(record?.issueClass) ? normalizeIssueClass(record.issueClass) : '',
    repeatMissText(record),
  ));
}

function hasMatchingLearningFinding(state, miss) {
  return learningFindings(state).some((finding) => recordMatchesMiss(
    miss,
    hasText(finding?.issueClass) ? normalizeIssueClass(finding.issueClass) : '',
    learningFindingText(finding),
  ));
}

function hasRecordedUserCaughtProcessMiss(state, miss) {
  return hasMatchingRepeatMiss(state, miss) || hasMatchingLearningFinding(state, miss);
}

function hasUnrecordedUserCaughtProcessMiss(state) {
  const misses = userCaughtProcessMisses(state);
  return misses.length > 0 && misses.some((miss) => !hasRecordedUserCaughtProcessMiss(state, miss));
}

export function validatePlanReadinessForReadyState(state, errors) {
  if (state.next?.ready !== true) return;
  if (hasUnrecordedUserCaughtProcessMiss(state)) {
    errors.push('next.ready true requires user-caught workflow/process misses in repeatMisses[] or he-learn learning findings');
  }
  if (!isObject(state.planReadiness)) {
    errors.push('next.ready true requires planReadiness');
    return;
  }
  const readiness = state.planReadiness;
  const grillMe = readiness.grillMe;
  const uiMapped = uiStageMapped(grillMe);
  validateReadyArtifact(readiness, errors);
  validateLavishUiMapping(readiness, uiMapped, errors);
  if (uiMapped) {
    if (!isObject(readiness.uiReview)) {
      errors.push('he-plan ready handoff requires planReadiness.uiReview when UI flow or visual design ran');
    } else if (readiness.uiReview.required !== true || readiness.uiReview.status !== 'accepted') {
      errors.push('he-plan ready handoff requires UI review to be accepted when UI flow or visual design ran');
    }
  }
  validateRequiredGrillMe(grillMe, errors);
  validateRequiredUiReview(readiness, errors);
  if (isObject(grillMe) && grillMe.required === false && grillMeSkipNeedsApproval(state, readiness) && !hasApprovedSkipEvidence(grillMe)) {
    errors.push('next.ready true requires explicit user-approved Grill Me skip evidence for feature, product, design, UI, or ambiguous work');
  }
}
