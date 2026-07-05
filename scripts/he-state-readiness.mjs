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

function claimClauses(text) {
  const value = String(text || '');
  return value
    .split(/(?:[.;,\n]+|\s+\b(?:and|but|however|yet|although|though|while|whereas)\b\s+|\b(?:next|blocker|reason|finding|decision|evidence)\s*:\s*)/i)
    .map((segment) => segment.trim())
    .filter(Boolean);
}

function missEvidenceClauses(text) {
  return evidenceClauses(text)
    .flatMap((segment) => segment.split(/\s*,\s*/))
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
    grillMe.stages.some((item) => ['ui-flow', 'visual-design'].includes(item?.id) && ['run', 'brief'].includes(item?.map) && item?.status === 'done');
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
  const raw = String(text || '');
  if ([
    /\buser(?:\s+visible)?\b[\s\S]{0,80}\b(?:approved|confirmed|requested|accepted|agreed|consented)\b[\s\S]{0,80}\b(?:(?:skip|skipping|skipped)(?:\s+grill\s+me)?|not\s+required|no\s+grill\s+me|grill\s+me\s+not\s+required|grill\s+me\s+skip)\b\s*(?:[:=?]|\bis\b|\bwas\b)\s*(?:false|no)\b/i,
    /\b(?:(?:skip|skipping|skipped)(?:\s+grill\s+me)?|not\s+required|no\s+grill\s+me|grill\s+me\s+not\s+required|grill\s+me\s+skip)\b[\s\S]{0,80}\b(?:approved|confirmed|requested|accepted|agreed|consented)\b[\s\S]{0,30}\b(?:by|from)\s+(?:the\s+)?user\b\s*(?:[:=?]|\bis\b|\bwas\b)\s*(?:false|no)\b/i,
  ].some((pattern) => pattern.test(raw))) return true;
  const normalized = normalizeText(text);
  const nearbyNegation = '(?:not(?!\\s+(?:only|just|merely|simply)\\b)|never|cannot|hasn\\s+t|hadn\\s+t|doesn\\s+t|didn\\s+t|isn\\s+t|wasn\\s+t|weren\\s+t|can\\s+t|couldn\\s+t|won\\s+t|wouldn\\s+t|shouldn\\s+t|mustn\\s+t)';
  const approvalVerb = '(?:approved|approve|confirmed|confirm|requested|request|accepted|accept|agreed|agree|consented|consent)';
  const skipTarget = '(?:skip|skipping|not\\s+required|no\\s+grill\\s+me|grill\\s+me)';
  return [
    /\buser\s+(?:approval|confirmation|request|consent|acceptance)\s+(?:is\s+|was\s+)?not\s+(?:required|needed|necessary)\b/,
    /\buser\s+(?:approval|confirmation|request|consent|acceptance)\b.{0,50}\b(?:skip|skipping|grill\s+me)\b.{0,50}\b(?:is|was|are|were)?\s*not\s+(?:required|needed|necessary)\b/,
    /\buser\s+(?:approval|confirmation|request|consent|acceptance)\b.{0,50}\b(?:skip|skipping|grill\s+me)\b.{0,50}\b(?:skipped|bypassed|omitted)\b/,
    /\b(?:no|without|missing|absent)\s+(?:explicit\s+)?(?:user\s+)?(?:approved|approval|confirmation|confirmed|request|requested|accepted|agreement|agreed|consent|consented)\s+(?:to\s+)?(?:grill\s+me\s+)?(?:skip|skipping|not\s+required|evidence)\b/,
    /\buser\s+(?:has\s+|had\s+|does\s+|did\s+|is\s+|was\s+)?(?:not|never)\s+(?:approved|confirmed|requested|accepted|agreed|consented|agree|consent)\s+(?:to\s+)?(?:the\s+)?(?:grill\s+me\s+)?(?:skip|skipping|not\s+required|no\s+grill\s+me)\b/,
    new RegExp(`\\buser\\b.{0,40}\\b(?:(?:has|had|does|did|is|was|were|can|could|will|would|should|must)\\s+)?${nearbyNegation}\\b.{0,40}\\b${approvalVerb}\\b.{0,80}\\b${skipTarget}\\b`),
    new RegExp(`\\b(?:not(?!\\s+(?:only|just|merely|simply)\\b)|never)\\s+(?:the\\s+)?user\\b.{0,80}\\b${approvalVerb}\\b.{0,80}\\b${skipTarget}\\b`),
    /\buser\b.{0,60}\b(?:not|never)\s+(?:asked|consulted|shown|prompted)\b/,
    /\buser\b.{0,60}\b(?:declined|rejected|refused|denied)\b(?:.{0,60}\b(?:skip|skipping|not\s+required|no\s+grill\s+me|grill\s+me)\b)?/,
    /\b(?:skip|skipping|grill\s+me|not\s+required|no\s+grill\s+me)\b.{0,80}\b(?:not|never)\b.{0,40}\b(?:approved|confirmed|requested|accepted|agreed|consented|approval|confirmation|agreement|consent)\b.{0,80}\buser\b/,
    /\buser\b.{0,80}\b(?:approved|confirmed|requested|accepted|agreed|consented|approval|confirmation|agreement|consent)\b.{0,40}\b(?:not|never)\s+to\s+(?:skip|skip\s+grill\s+me|make\s+grill\s+me\s+not\s+required)\b/,
    /\b(?:skip|skipping|grill\s+me)\s+(?:approval|evidence)\s+(?:is\s+|was\s+)?(?:missing|absent|not\s+present|not\s+recorded)\b/,
    /\b(?:agent|assistant|system|codex|tool)\s+(?:explicitly\s+)?(?:approved|confirmed|requested|accepted|agreed|consented|approval|confirmation|agreement|consent)\b.{0,80}\b(?:skip|skipping|not\s+required|no\s+grill\s+me|grill\s+me\s+skip)\b/,
    /\b(?:skip|skipping|not\s+required|no\s+grill\s+me|grill\s+me\s+skip)\b.{0,80}\b(?:approved|confirmed|requested|accepted|agreed|consented|approval|confirmation|agreement|consent)\s+(?:by|from)\s+(?:agent|assistant|system|codex|tool)\b/,
  ].some((pattern) => pattern.test(normalized));
}

function hasUserApprovedSkipClause(clause) {
  if (hasNegatedApprovedSkipEvidence(clause)) return false;
  const normalized = normalizeText(clause);
  return [
    /\buser(?:\s+visible)?\b.{0,80}\b(?:approved|confirmed|requested|accepted|agreed|consented)\b\s+(?:(?:to\s+)?skip(?:\s+grill\s+me)?|skipping(?:\s+grill\s+me)?|(?:the\s+)?(?:grill\s+me\s+)?skip|(?:making|make|made)\s+grill\s+me\s+not\s+required|that\s+grill\s+me\s+(?:be\s+|was\s+)?skipped)\b/,
    /\b(?:(?:the\s+)?(?:grill\s+me\s+)?skip|skipping(?:\s+grill\s+me)?|to\s+skip(?:\s+grill\s+me)?)\b.{0,80}\b(?:approved|confirmed|requested|accepted|agreed|consented)\b.{0,30}\b(?:by|from)\s+(?:the\s+)?user\b/,
  ].some((pattern) => pattern.test(normalized));
}

function grillMeSkipEvidenceStrings(grillMe) {
  const stageText = Array.isArray(grillMe?.stages)
    ? grillMe.stages.flatMap((stage) => [stage?.reason, stage?.evidence])
    : [];
  return stringsFrom([grillMe?.reason, grillMe?.evidence, grillMe?.skipEvidence, stageText])
    .filter(hasText);
}

function hasApprovedSkipEvidence(grillMe) {
  const evidenceItems = grillMeSkipEvidenceStrings(grillMe);
  if (evidenceItems.some(hasNegatedApprovedSkipEvidence)) return false;
  return evidenceItems.some((text) => {
    const clauses = evidenceClauses(text);
    return (clauses.length ? clauses : [text]).some(hasUserApprovedSkipClause);
  });
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
    errors.push('next.ready true requires the plan artifact to be accepted or not_required');
  }
}

function validateUiReviewReceiptMapping(readiness, uiMapped, errors) {
  if (readiness.uiReview?.decisionTool === 'ui-review-receipt' && !uiMapped) {
    errors.push('next.ready true with UI review receipt requires Grill Me UI flow or visual design evidence');
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

function stageReceipts(state) {
  return Array.isArray(state.steps)
    ? state.steps
      .map((step) => step?.receipt)
      .filter(isObject)
    : [];
}

function isPlanExitAttempt(state) {
  if (state.stage !== 'he-plan') return false;
  if (['ready', 'complete', 'blocked'].includes(state.status)) return true;
  return stageReceipts(state).some((receipt) => (
    ['PASS', 'CONCERNS', 'FAIL'].includes(receipt?.decision)
  ));
}

function referencesImplementTarget(text) {
  return /\b(?:he implement|implementation|implement)\b/.test(normalizeText(text));
}

function hasReadyYesClause(text) {
  const normalized = normalizeText(text);
  if (/\b(?:not|no)\b.{0,20}\bready\b/.test(normalized)) return false;
  return /\bready\b.{0,40}\b(?:yes|true)\b/.test(normalized) ||
    /\b(?:yes|true)\b.{0,40}\bready\b/.test(normalized);
}

function claimsReadyYes(value) {
  const clauses = claimClauses(value);
  return (clauses.length ? clauses : [String(value || '')]).some(hasReadyYesClause);
}

function claimsImplementReadyYes(value) {
  const clauses = claimClauses(value);
  const claimTexts = clauses.length ? clauses : [String(value || '')];
  return claimTexts.some((clause) => referencesImplementTarget(clause) && hasReadyYesClause(clause)) ||
    (referencesImplementTarget(value) && claimTexts.some(hasReadyYesClause));
}

function receiptClaimsImplementReadyYes(receipt) {
  return claimsImplementReadyYes(textFrom([receipt?.next, receipt?.handoverPrompt])) ||
    claimsReadyYes(receipt?.next);
}

function hasNonPassReadyYesReceipt(state) {
  return stageReceipts(state).some((receipt) => (
    ['CONCERNS', 'FAIL'].includes(receipt?.decision) &&
    receiptClaimsImplementReadyYes(receipt)
  ));
}

function hasUnresolvedGrillMeInterview(state, grillMe) {
  if (!isObject(grillMe) || grillMe.required !== true) return false;
  const alignment = grillMe.alignment;
  const openQuestions = Array.isArray(alignment?.openQuestions) ? alignment.openQuestions : [];
  const openUnknowns = Array.isArray(alignment?.openUnknowns) ? alignment.openUnknowns : [];
  if (hasTerminalBlockedGrillMe(state, grillMe, openQuestions, openUnknowns)) return false;
  const unresolvedAlignment = isObject(alignment) &&
    (alignment.status !== 'aligned' || alignment.userConfirmed !== true || alignment.noGuesswork !== true || openQuestions.length > 0 || openUnknowns.length > 0);
  const unresolvedStages = Array.isArray(grillMe.stages) &&
    grillMe.stages.some((item) => ['run', 'brief'].includes(item?.map) && ['pending', 'in_progress', 'blocked'].includes(item?.status));
  return hasUnresolvedExitBlocker(state) ||
    grillMe.status !== 'accepted' ||
    unresolvedAlignment ||
    unresolvedStages ||
    ['draft', 'asked', 'parked'].includes(grillMe.lastQuestion?.status) ||
    (grillMe.lastQuestion?.status === 'answered' && alignment?.status !== 'aligned');
}

function normalizedClaimClauses(value) {
  const clauses = claimClauses(value);
  return (clauses.length ? clauses : [String(value || '')])
    .map(normalizeText)
    .filter(hasText);
}

function hasUserAnswerableBlockerClause(text) {
  return /\b(?:need|needs|require|requires|required|await|awaiting|wait|waiting|blocked on|ask|asking)\b.{0,80}\b(?:user|human|customer|client|stakeholder)\b.{0,80}\b(?:answer|clarification|decision|choice|input|response|reply|approval|confirmation|confirm|choose|decide|pick|select)\b/.test(text) ||
    /\b(?:answer|clarification|decision|choice|input|response|reply|approval|confirmation)\b.{0,80}\b(?:from|by)\b.{0,20}\b(?:user|human|customer|client|stakeholder)\b/.test(text) ||
    /\b(?:user|human|customer|client|stakeholder)\b.{0,80}\b(?:must|needs?|requires?|required|has to|have to|should)\b.{0,80}\b(?:answer|clarify|decide|choose|pick|select|confirm|approve|provide|reply|respond)\b/.test(text) ||
    /\b(?:user|human|customer|client|stakeholder)\b.{0,80}\b(?:answer|clarification|decision|choice|input|response|reply|approval|confirmation)\b.{0,80}\b(?:required|needed|pending|open|missing)\b/.test(text) ||
    /\b(?:need|needs|require|requires|required|await|awaiting|wait|waiting|blocked on|ask|asking)\b.{0,80}\b(?:you|your)\b.{0,80}\b(?:answer|clarification|decision|choice|input|response|reply|approval|confirmation|confirm|choose|decide|pick|select)\b/.test(text) ||
    /\b(?:can|could|will|would|should|do|did)\s+you\b.{0,80}\b(?:answer|clarify|confirm|choose|decide|pick|select|approve|provide|reply|respond|tell)\b/.test(text) ||
    /\b(?:your)\b.{0,40}\b(?:answer|clarification|decision|choice|input|response|reply|approval|confirmation)\b/.test(text);
}

function hasExplicitNonUserInterviewBlockerClause(text) {
  return /\b(?:platform owner|security owner|backend owner|frontend owner|design owner|repo owner|service owner|data owner|infra owner|devops|sre|legal|compliance|vendor|third party|external system|external provider|ci system|build system|test runner|schema owner|migration owner|credential owner|secret owner|environment owner|production owner|staging owner|tenant admin|acl owner|api provider|non user|nonuser)\b/.test(text) ||
    /\b(?:ci|build|test(?: runner| suite)?|schema|migration|credential|credentials|secret|secrets|environment|production|staging|tenant|acl matrix|access matrix|api contract)\b.{0,80}\b(?:fail|failed|failure|error|unavailable|missing|expired|invalid|denied|blocked|outage|timeout|not provisioned|not available|cannot run|cannot access|cannot load|cannot connect|is down)\b/.test(text) ||
    /\b(?:fail|failed|failure|error|unavailable|missing|expired|invalid|denied|blocked|outage|timeout|not provisioned|not available|cannot run|cannot access|cannot load|cannot connect|down)\b.{0,80}\b(?:ci|build|test(?: runner| suite)?|schema|migration|credential|credentials|secret|secrets|environment|production|staging|tenant|acl matrix|access matrix|api contract)\b/.test(text);
}

function hasAmbiguousInterviewBlockerClause(text) {
  return /\b(?:need|needs|require|requires|required|await|awaiting|wait|waiting|blocked|blocking|open|pending)\b.{0,80}\b(?:answer|clarification|clarify|decision|choice|input|response|reply|approval|confirmation)\b/.test(text) ||
    /\b(?:answer|clarification|clarify|decision|choice|input|response|reply|approval|confirmation)\b.{0,80}\b(?:need|needs|required|awaiting|pending|open|unclear|unknown|missing)\b/.test(text) ||
    /\b(?:unclear|unknown|unresolved|open)\b.{0,80}\b(?:visibility|scope|question|decision|choice|answer|clarification)\b/.test(text) ||
    /\b(?:visibility|scope|question|decision|choice|answer|clarification|input|response|reply|approval|confirmation)\b.{0,80}\b(?:unanswered|undecided|tbd|to be determined)\b/.test(text) ||
    /\b(?:unanswered|undecided|tbd|to be determined)\b.{0,80}\b(?:visibility|scope|question|decision|choice|answer|clarification|input|response|reply|approval|confirmation)\b/.test(text) ||
    /^(?:who|what|which|whether|how|when|where)\b.{0,120}\b(?:can|should|will|does|is|are|visibility|scope|audience|access|permission|see|read|write|owner)\b/.test(text) ||
    /\b(?:must|should|need to|needs to|has to|have to)\b.{0,80}\b(?:decide|choose|pick|select|clarify|confirm)\b/.test(text);
}

function hasResolvedNoInterviewBlockerClause(text) {
  return /\b(?:no|none|zero|0|without)\b.{0,30}\b(?:blocker|blockers|blocking|blocked)\b/.test(text) ||
    /\b(?:blocker|blockers|blocking)\b\s*(?::|=)?\s*(?:none|no|zero|0|n a|not applicable)\b/.test(text) ||
    /\bnot\b.{0,20}\bblocked\b/.test(text);
}

function isNonUserInterviewBlockerClause(text) {
  return !hasUserAnswerableBlockerClause(text) &&
    hasExplicitNonUserInterviewBlockerClause(text);
}

function hasRelevantInterviewBlockerClause(text) {
  if (hasResolvedNoInterviewBlockerClause(text)) return false;
  return hasUserAnswerableBlockerClause(text) ||
    hasExplicitNonUserInterviewBlockerClause(text) ||
    hasAmbiguousInterviewBlockerClause(text) ||
    /\b(?:block|blocked|blocker|blocking)\b/.test(text);
}

function hasNonUserInterviewBlockerText(value) {
  const relevantClauses = normalizedClaimClauses(value).filter(hasRelevantInterviewBlockerClause);
  return relevantClauses.length > 0 && relevantClauses.every(isNonUserInterviewBlockerClause);
}

function hasRelevantInterviewBlockerText(value) {
  return normalizedClaimClauses(value).some(hasRelevantInterviewBlockerClause);
}

function hasUnresolvedInterviewBlockerText(value) {
  return normalizedClaimClauses(value).some((clause) => (
    !isNonUserInterviewBlockerClause(clause) &&
    hasRelevantInterviewBlockerClause(clause)
  ));
}

function hasUserAnswerableOpenItems(items) {
  return items.some((item) => !hasNonUserInterviewBlockerText(stringsFrom(item).join(' ')));
}

function handoverBlockerStrings(value) {
  const text = String(value || '');
  if (!hasText(text)) return [];
  const blockers = [];
  const pattern = /\bBlockers?\s*:\s*([\s\S]*?)(?=\b(?:Stage|State|Decision|Owner\/proof|Owner proof|Artifacts?|Next|Handover prompt|Command|Worktree|Read)\s*:|$)/gi;
  for (let match = pattern.exec(text); match !== null; match = pattern.exec(text)) {
    if (hasText(match[1])) blockers.push(match[1].trim());
  }
  return blockers;
}

function exitBlockerStrings(state) {
  const receipts = stageReceipts(state).map((receipt) => [
    receipt.blocker,
    receipt.next,
    handoverBlockerStrings(receipt.handoverPrompt),
  ]);
  const findings = Array.isArray(state.findings)
    ? state.findings.map((finding) => [
      finding?.summary,
      finding?.reason,
      finding?.blocker,
    ])
    : [];
  return stringsFrom([
    state.blockers,
    state.decisions,
    state.next?.reason,
    receipts,
    findings,
  ]).filter(hasText);
}

function hasUnresolvedExitBlocker(state) {
  return exitBlockerStrings(state).some(hasUnresolvedInterviewBlockerText);
}

function hasUnprovenTerminalExitBlocker(state) {
  return exitBlockerStrings(state)
    .filter(hasRelevantInterviewBlockerText)
    .some((item) => !hasNonUserInterviewBlockerText(item));
}

function hasUnprovenRelevantBlockerItem(value) {
  return stringsFrom(value)
    .filter(hasText)
    .filter(hasRelevantInterviewBlockerText)
    .some((item) => !hasNonUserInterviewBlockerText(item));
}

function hasProvenTerminalBlockerItems(value) {
  const items = stringsFrom(value).filter(hasText);
  return items.some(hasNonUserInterviewBlockerText) &&
    !hasUnprovenRelevantBlockerItem(items);
}

function hasOpenSkippedGrillMeWork(grillMe) {
  if (!isObject(grillMe)) return false;
  const alignment = grillMe.alignment;
  const openQuestions = Array.isArray(alignment?.openQuestions) ? alignment.openQuestions : [];
  const openUnknowns = Array.isArray(alignment?.openUnknowns) ? alignment.openUnknowns : [];
  const blockedTopLevelWork = grillMe.status === 'blocked' &&
    !hasProvenTerminalBlockerItems([grillMe.reason, grillMe.evidence]);
  const unresolvedStages = Array.isArray(grillMe.stages) &&
    grillMe.stages.some((item) => (
      ['run', 'brief'].includes(item?.map) &&
      (
        ['pending', 'in_progress'].includes(item?.status) ||
        (item?.status === 'blocked' && !hasProvenTerminalBlockerItems([item?.reason, item?.evidence]))
      )
    ));
  return ['pending', 'parked'].includes(grillMe.status) ||
    blockedTopLevelWork ||
    openQuestions.length > 0 ||
    hasUserAnswerableOpenItems(openUnknowns) ||
    unresolvedStages ||
    ['draft', 'asked', 'parked'].includes(grillMe.lastQuestion?.status);
}

function hasTerminalBlockedGrillMe(state, grillMe, openQuestions, openUnknowns) {
  if (grillMe.status !== 'blocked' || grillMe.alignment?.status !== 'blocked' || openQuestions.length > 0 || hasUserAnswerableOpenItems(openUnknowns)) return false;
  if (hasUnresolvedExitBlocker(state) || hasUnprovenTerminalExitBlocker(state)) return false;
  if (['draft', 'asked', 'parked'].includes(grillMe.lastQuestion?.status)) return false;
  const mappedStages = Array.isArray(grillMe.stages)
    ? grillMe.stages.filter((item) => ['run', 'brief'].includes(item?.map))
    : [];
  if (mappedStages.some((item) => ['pending', 'in_progress'].includes(item?.status))) return false;
  const blockedStages = mappedStages.filter((item) => item?.status === 'blocked');
  const stageBlockEvidence = blockedStages.length > 0 &&
    blockedStages.every((item) => hasText(item?.reason) && stringsFrom(item?.evidence).some(hasText));
  const grillMeBlockEvidence = hasText(grillMe.reason) && stringsFrom(grillMe.evidence).some(hasText);
  if (hasUnprovenRelevantBlockerItem([grillMe.reason, grillMe.evidence])) return false;
  const stageBlockersProven = stageBlockEvidence &&
    blockedStages.every((item) => hasProvenTerminalBlockerItems([item.reason, item.evidence]));
  const grillMeBlockerProven = grillMeBlockEvidence &&
    hasProvenTerminalBlockerItems([grillMe.reason, grillMe.evidence]);
  if (blockedStages.length > 0) return stageBlockersProven;
  return grillMeBlockerProven;
}

function hasVisibleAskedQuestion(grillMe) {
  return grillMe?.lastQuestion?.status === 'asked' && hasText(grillMe.lastQuestion.visibleText);
}

export function validatePlanReadinessForPlanExit(state, errors) {
  if (!isPlanExitAttempt(state)) return;
  if (hasNonPassReadyYesReceipt(state)) {
    errors.push('he-plan CONCERNS or FAIL receipt cannot claim ready for /he:implement: yes');
  }
  if (!isObject(state.planReadiness)) {
    errors.push('he-plan exit requires planReadiness');
    return;
  }
  const readiness = state.planReadiness;
  const grillMe = readiness.grillMe;
  if (!isObject(grillMe)) {
    errors.push('he-plan exit requires planReadiness.grillMe');
    return;
  }
  const hasApprovedSkip = hasApprovedSkipEvidence(grillMe);
  const skippedGrillMeHasUserWork = grillMe.required === false &&
    (hasUnresolvedExitBlocker(state) || hasOpenSkippedGrillMeWork(grillMe));
  if (grillMe.required === false && grillMeSkipNeedsApproval(state, readiness) && !hasApprovedSkip) {
    errors.push('he-plan exit requires explicit user-approved Grill Me skip evidence for feature, product, design, UI, or ambiguous work');
  }
  if (skippedGrillMeHasUserWork && !hasApprovedSkip && !hasVisibleAskedQuestion(grillMe)) {
    errors.push('he-plan not-ready exit with unresolved Grill Me work must ask the next visible Grill Me question instead of parking concerns');
  }
  if (hasUnresolvedGrillMeInterview(state, grillMe) && !hasVisibleAskedQuestion(grillMe)) {
    errors.push('he-plan not-ready exit with unresolved Grill Me work must ask the next visible Grill Me question instead of parking concerns');
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

const userCaughtProcessMissPattern = /\b(user[- ]caught|user caught|caught by user|workflow miss|process miss|missed workflow|same miss again|repeat(?:ed)? miss(?:es)?)\b/i;
const absenceAdverbs = '(?:(?:actually|currently|yet|ever|clearly|explicitly|formally|properly|really|previously|still)\\s+){0,3}';
const repeatedMissTarget = '(?:same\\s+miss\\s+again|repeated\\s+miss(?:es)?|repeat(?:ed)?\\s+miss(?:es)?)';
const userCaughtProcessMissAbsencePatterns = [
  /\b(?:no|without|missing|absent)\s+(?:evidence\s+of\s+)?(?:user\s+caught\s+|caught\s+by\s+user\s+)?(?:(?:workflow|process)\s+)*(?:miss|misses|missed\s+workflow)\b/i,
  new RegExp(`\\b(?:no|without|missing|absent)\\s+(?:evidence\\s+of\\s+)?${repeatedMissTarget}\\b`, 'i'),
  new RegExp(`\\b(?:(?:workflow|process)\\s+)*(?:miss|misses|missed\\s+workflow)\\s+(?:is\\s+|are\\s+|was\\s+|were\\s+)?not(?!\\s+(?:only|just|merely|simply)\\b)\\s+${absenceAdverbs}(?:found|present|detected|recorded|observed)\\b`, 'i'),
  new RegExp(`\\b(?:(?:workflow|process)\\s+)*(?:miss|misses|missed\\s+workflow)\\s+(?:isn|aren|wasn|weren)\\s+t\\s+${absenceAdverbs}(?:found|present|detected|recorded|observed)\\b`, 'i'),
  new RegExp(`\\b${repeatedMissTarget}\\s+(?:is\\s+|are\\s+|was\\s+|were\\s+)?not(?!\\s+(?:only|just|merely|simply)\\b)\\s+${absenceAdverbs}(?:found|present|detected|recorded|observed|repeated)\\b`, 'i'),
  new RegExp(`\\b${repeatedMissTarget}\\s+(?:isn|aren|wasn|weren)\\s+t\\s+${absenceAdverbs}(?:found|present|detected|recorded|observed|repeated)\\b`, 'i'),
  /\b(?:(?:workflow|process)\s+)*(?:miss|misses|missed\s+workflow)\s+(?:is\s+|are\s+|was\s+|were\s+)?(?:missing|absent)\b/i,
  /\bnot\s+(?:a\s+|an\s+|the\s+)?(?:user\s+caught\s+|caught\s+by\s+user\s+)?(?:(?:workflow|process)\s+)*(?:miss|misses|missed\s+workflow)\b/i,
  new RegExp(`\\bnot\\s+(?:a\\s+|an\\s+|the\\s+)?${repeatedMissTarget}\\b`, 'i'),
];

function stripUserCaughtProcessMissAbsenceText(text) {
  let remaining = normalizeText(text);
  for (let pass = 0; pass < 8; pass += 1) {
    const before = remaining;
    for (const pattern of userCaughtProcessMissAbsencePatterns) {
      remaining = remaining.replace(pattern, ' ');
    }
    remaining = normalizeText(remaining);
    if (remaining === before) return remaining;
  }
  return remaining;
}

function isUserCaughtProcessMissAbsenceOnly(text) {
  const normalized = normalizeText(text);
  if (!userCaughtProcessMissAbsencePatterns.some((pattern) => pattern.test(normalized))) return false;
  return !userCaughtProcessMissPattern.test(stripUserCaughtProcessMissAbsenceText(normalized));
}

function hasUserCaughtProcessMissEvidence(text) {
  const value = String(text || '');
  if (!userCaughtProcessMissPattern.test(value)) return false;
  const segments = missEvidenceClauses(value);
  return (segments.length ? segments : [value]).some((segment) => (
    userCaughtProcessMissPattern.test(segment) &&
    !isUserCaughtProcessMissAbsenceOnly(segment)
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
  return textFrom([miss?.evidence]);
}

function recordMatchesMiss(miss, issueClass, text) {
  const evidenceMatches = textMatchesMiss(miss.evidence, text);
  if (!miss.issueClass) return evidenceMatches;
  return issueClass === miss.issueClass && evidenceMatches;
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
  validateUiReviewReceiptMapping(readiness, uiMapped, errors);
  if (uiMapped) {
    if (!isObject(readiness.uiReview)) {
      errors.push('next.ready true requires planReadiness.uiReview when UI flow or visual design ran');
    } else if (readiness.uiReview.required !== true || readiness.uiReview.status !== 'accepted') {
      errors.push('next.ready true requires UI review to be accepted when UI flow or visual design ran');
    }
  }
  validateRequiredGrillMe(grillMe, errors);
  validateRequiredUiReview(readiness, errors);
  if (isObject(grillMe) && grillMe.required === false && grillMeSkipNeedsApproval(state, readiness) && !hasApprovedSkipEvidence(grillMe)) {
    errors.push('next.ready true requires explicit user-approved Grill Me skip evidence for feature, product, design, UI, or ambiguous work');
  }
}
