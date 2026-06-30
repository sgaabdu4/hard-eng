const requiredInventoryStages = new Set(['he-implement', 'he-verify', 'he-ship']);
const inventoryStatuses = new Set(['required', 'not_applicable']);
const requiredGuardrailClasses = [
  'regex-scanners',
  'git-hooks',
  'lint-analyze-typecheck',
  'ssot-scanners',
  'fallow',
  'react-doctor',
  'repeat-mistake-prevention',
];

function isObject(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

function hasText(value) {
  return typeof value === 'string' && value.trim().length > 0;
}

function stringArray(value) {
  return Array.isArray(value) && value.every((item) => typeof item === 'string');
}

function words(value) {
  if (Array.isArray(value)) return value.join(' ');
  if (typeof value === 'string') return value;
  return '';
}

function hasAnyPattern(text, patterns) {
  return patterns.some((pattern) => pattern.test(text));
}

function entryEvidenceText(state, entry) {
  const guardrail = guardrailById(state.guardrails, entry?.guardrailId);
  return [
    entry?.reason,
    words(entry?.evidence),
    guardrail?.owner,
    guardrail?.command,
    words(guardrail?.evidence),
  ].filter(hasText).join(' ');
}

function hasFallowToolAbsenceEvidence(evidence) {
  return hasAnyPattern(evidence, [
    /\bno stack-specific(?:\s+\w+){0,8}\s+(?:fallow|dupes?|duplicates?|duplication|clone|clones)(?:\s+\w+){0,8}\s+(?:tool|detector|scanner|support|supported|available|availability|unavailable|unsupported|applicable)\b/i,
    /\bno stack-specific(?:\s+\w+){0,8}\s+(?:tool|detector|scanner|support)(?:\s+\w+){0,8}\s+(?:fallow|dupes?|duplicates?|duplication|clone|clones)\b/i,
    /\b(?:tool|detector|scanner)\b(?:\s+(?:for|supporting|covering))?\s+(?:fallow|dupes?|duplicates?|duplication|clone|clones)\b(?:\s+\w+){0,4}\s+(?:unavailable|unsupported|not supported|not applicable|missing|absent)\b/i,
    /\b(?:tool|detector|scanner)\b(?:\s+\w+){0,2}\s+(?:unavailable|unsupported|not supported|not applicable|missing|absent)\s+(?:for|on)\s+(?:fallow|dupes?|duplicates?|duplication|clone|clones)\b/i,
    /\b(?:fallow|dupes?|duplicates?|duplication|clone|clones)\b(?:\s+\w+){0,6}\s+(?:tool|detector|scanner)\b(?:\s+\w+){0,4}\s+(?:unavailable|unsupported|not supported|not applicable|missing|absent)\b/i,
    /\b(?:fallow|clone detector|duplicate detector)\b.*\b(?:unavailable|unsupported|not supported|not applicable)\b/i,
  ]);
}

function hasStaticDuplicateSearchEvidence(evidence) {
  return /\b(rg|ripgrep|static search|duplicate search|clone search)\b/i.test(evidence);
}

function hasUnavailableDuplicateCloneProof(evidence) {
  return hasAnyPattern(evidence, [
    /\b(?:skipped|skip|not run)(?:\s+\w+){0,4}\s+(?:dupes?|duplicates?|duplication|duplicate groups?|clones?|clone groups?|copy[- ]?paste|near[- ]?duplicate)\b/i,
    /\b(?:dupes?|duplicates?|duplication|duplicate groups?|clones?|clone groups?|copy[- ]?paste|near[- ]?duplicate)(?:\s+\w+){0,4}\s+(?:skipped|skip|not run|unavailable|unsupported|not supported|not applicable|unable|cannot|can't|could not|missing|not available)\b/i,
    /\b(?:no|without)(?:\s+\w+){0,3}\s+(?:dupes?|duplicates?|duplication|duplicate groups?|clones?|clone groups?|copy[- ]?paste|near[- ]?duplicate)(?:\s+\w+){0,3}\s+(?:evidence|proof|result|output)\b/i,
    /\b(?:dupes?|duplicates?|duplication|duplicate groups?|clones?|clone groups?|copy[- ]?paste|near[- ]?duplicate)(?:\s+\w+){0,3}\s+(?:evidence|proof)(?:\s+\w+){0,3}\s+(?:unavailable|missing|absent|none|not available|not found)\b/i,
    /\b(?:dupes?|duplicates?|duplication|duplicate groups?|clones?|clone groups?|copy[- ]?paste|near[- ]?duplicate)(?:\s+\w+){0,3}\s+(?:result|output)(?:\s+\w+){0,3}\s+(?:unavailable|missing|not available)\b/i,
  ]);
}

function hasNoDuplicateCloneProof(evidence) {
  if (hasUnavailableDuplicateCloneProof(evidence)) return false;
  return hasAnyPattern(evidence, [
    /\bfound no(?:\s+\w+){0,5}\s+(?:duplicates?|clones?|clone groups?|duplicate groups?)\b/i,
    /\bfound\s+(?:zero|none|0)(?:\s+\w+){0,5}\s+(?:duplicates?|clones?|clone groups?|duplicate groups?)\b/i,
    /\b(?:no|zero|without|none|absent|clean|0)(?:\s+\w+){0,5}\s+(?:duplicates?|clones?|clone groups?|duplicate groups?)\b/i,
    /\b(?:duplicates?|clones?|clone groups?|duplicate groups?)(?:\s+\w+){0,5}\s+(?:none|absent|clean|not found|zero|0)\b/i,
    /\b(?:dupes?|duplicates?|duplication|duplicate groups?|clones?|clone groups?|copy[- ]?paste|near[- ]?duplicate)(?:\s+\w+){0,3}\s+(?:result|output)\s*(?::|=)?\s*(?:none|absent|not found|zero|0|clean|clear)\b/i,
  ]);
}

function duplicateCloneEvidenceSegments(evidence) {
  return String(evidence)
    .split(/[;,\n|]+|\.(?=\s|$)/)
    .flatMap((part) => part.split(/\b(?:but|however|yet|though|although|whereas|except|while)\b|\b(?:and|then)\s+(?=(?:found|detected|identified|reported|dupes?|duplicates?|duplication|clones?|copy[- ]?paste|near[- ]?duplicate|clone groups?|duplicate groups?|[1-9]\d*\s+(?:dupes?|duplicates?|clones?|copy[- ]?paste|near[- ]?duplicate|clone groups?|duplicate groups?))\b)/i))
    .map((part) => part.trim())
    .filter(Boolean);
}

function hasFoundDuplicateCloneEvidence(evidence) {
  const positiveCountPatterns = [
    /\b[1-9]\d*\s+(?:dupes?|duplicates?|duplication|clones?|clone groups?|duplicate groups?|copy[- ]?paste|near[- ]?duplicate)\b/i,
    /\b(?:dupes?|duplicates?|duplication|clones?|clone groups?|duplicate groups?|copy[- ]?paste|near[- ]?duplicate)\s*(?::|=)?\s*[1-9]\d*\b/i,
  ];
  const foundPatterns = [
    /\bfound\s+(?!(?:no|zero|none|0)\b)(?:\w+\s+){0,5}(?:dupes?|duplicates?|duplication|clones?|clone groups?|duplicate groups?|copy[- ]?paste|near[- ]?duplicate)\b/i,
    /\b(?:detected|identified|reported)(?:\s+\w+){0,5}\s+(?:dupes?|duplicates?|duplication|clones?|clone groups?|duplicate groups?|copy[- ]?paste|near[- ]?duplicate)\b/i,
    /\b(?:dupes?|duplicates?|duplication|clones?|clone groups?|duplicate groups?|copy[- ]?paste|near[- ]?duplicate)\s+(?:were\s+)?(?:found(?!\s+(?:no|zero|none|0)\b)|detected|identified|reported)\b/i,
  ];
  return duplicateCloneEvidenceSegments(evidence)
    .some((part) => hasAnyPattern(part, positiveCountPatterns) || (!hasNoDuplicateCloneProof(part) && hasAnyPattern(part, foundPatterns)));
}

function hasFallowDuplicateCloneEvidence(evidence) {
  const negativeProofPatterns = [
    /\b(?:skipped|skip|unavailable|unsupported|not supported|not applicable|unable|cannot|can't|could not|failed to run|not run)\b/i,
    /\b(?:no|without)(?:\s+\w+){0,3}\s+(?:dupes?|duplicates?|duplication|duplicate groups?|clones?|clone groups?|copy[- ]?paste|near[- ]?duplicate)(?:\s+\w+){0,3}\s+(?:evidence|proof|result|output)\b/i,
    /\b(?:dupes?|duplicates?|duplication|duplicate groups?|clones?|clone groups?|copy[- ]?paste|near[- ]?duplicate)(?:\s+\w+){0,3}\s+(?:evidence|proof|result|output)(?:\s+\w+){0,3}\s+(?:unavailable|missing|absent|none|not available)\b/i,
  ];
  if (hasAnyPattern(evidence, negativeProofPatterns)) return false;
  const proofPatterns = [
    /\b(?:dupes?|duplicates?|duplication|duplicate groups?|clones?|clone groups?|copy[- ]?paste|near[- ]?duplicate)\b.*\b(?:checked|scanned|audited|passed|clean|reported|found|detected|identified|result|output)\b/i,
    /\b(?:checked|scanned|audited|passed|clean|reported|found|detected|identified|result|output)\b.*\b(?:dupes?|duplicates?|duplication|duplicate groups?|clones?|clone groups?|copy[- ]?paste|near[- ]?duplicate)\b/i,
  ];
  return hasAnyPattern(evidence, proofPatterns);
}

function hasDuplicateCloneTerm(evidence) {
  return /\b(?:dupes?|duplicates?|duplication|duplicate groups?|clones?|clone groups?|copy[- ]?paste|near[- ]?duplicate)\b/i.test(evidence);
}

function hasJsTsFallowContext(evidence) {
  return /\b(?:fallow|javascript|java\s+script|typescript|ts|tsx|jsx|react|next)\b/i.test(evidence);
}

function hasCleanFallowDuplicateCloneResult(evidence) {
  if (hasUnavailableDuplicateCloneProof(evidence)) return false;
  const cleanResultPatterns = [
    /\b(?:dupes?|duplicates?|duplication|duplicate groups?|clones?|clone groups?|copy[- ]?paste|near[- ]?duplicate)\b(?:\s+\w+){0,6}\s+(?:pass|passed|passing|clean|succeeded|success|ok|completed|clear)\b/i,
    /\b(?:pass|passed|passing|clean|succeeded|success|ok|completed|clear)\b(?:\s+\w+){0,6}\s+(?:dupes?|duplicates?|duplication|duplicate groups?|clones?|clone groups?|copy[- ]?paste|near[- ]?duplicate)\b/i,
  ];
  return duplicateCloneEvidenceSegments(evidence).some((part) => {
    if (hasUnavailableDuplicateCloneProof(part) || hasFoundDuplicateCloneEvidence(part)) return false;
    if (!hasDuplicateCloneTerm(part)) return false;
    if (hasStaticDuplicateSearchEvidence(part) && !hasJsTsFallowContext(part)) return false;
    return hasNoDuplicateCloneProof(part) || hasAnyPattern(part, cleanResultPatterns);
  });
}

function hasAcceptedJsTsFallowDuplicateCloneEvidence(state, entries, evidence) {
  if (!hasFallowDuplicateCloneEvidence(evidence)) return false;
  if (hasFoundDuplicateCloneEvidence(evidence)) return hasActiveDuplicateCloneDecision(state, entries);
  return hasCleanFallowDuplicateCloneResult(evidence);
}

function fallowResultEvidenceText(state, entry) {
  const guardrail = guardrailById(state.guardrails, entry?.guardrailId);
  return words(guardrail?.evidence);
}

function guardrailResult(state, entry) {
  const guardrail = guardrailById(state.guardrails, entry?.guardrailId);
  return {
    command: guardrail?.command || '',
    evidence: words(guardrail?.evidence),
  };
}

function normalizedProofText(evidence) {
  return String(evidence || '').replace(/[^a-z0-9]+/gi, ' ').replace(/\s+/g, ' ').trim();
}

function hasUnavailableTypecheckProof(evidence) {
  const proofText = normalizedProofText(evidence);
  return hasAnyPattern(proofText, [
    /\b(?:skipped|skip|not run|unavailable|unsupported|not supported|not applicable|unable|cannot|can t|could not|missing|absent|not available)\b(?:\s+\w+){0,4}\s+(?:tsc|typecheck|type\s+check|mypy)\b/i,
    /\b(?:tsc|typecheck|type\s+check|mypy)\b(?:\s+\w+){0,4}\s+(?:skipped|skip|not run|unavailable|unsupported|not supported|not applicable|unable|cannot|can t|could not|missing|absent|not available)\b/i,
    /\b(?:skipped|skip|not run|unavailable|unsupported|not supported|not applicable|unable|cannot|can t|could not|missing|absent|not available)\b(?:\s+\w+){0,4}\s+next\s+build\b/i,
    /\bnext\s+build\b(?:\s+\w+){0,4}\s+(?:skipped|skip|not run|unavailable|unsupported|not supported|not applicable|unable|cannot|can t|could not|missing|absent|not available)\b/i,
    /\b(?:no|without)(?:\s+\w+){0,3}\s+(?:tsc|typecheck|type\s+check|mypy)(?:\s+\w+){0,3}\s+(?:evidence|proof|result|output)\b/i,
    /\b(?:tsc|typecheck|type\s+check|mypy)(?:\s+\w+){0,3}\s+(?:evidence|proof|result|output)(?:\s+\w+){0,3}\s+(?:unavailable|missing|absent|none|not available|not found)\b/i,
  ]);
}

function hasFailedTypecheckProof(evidence) {
  const proofText = normalizedProofText(evidence);
  return hasAnyPattern(proofText, [
    /\b(?:failed|failure|failing|error|errors|errored|red|nonzero|non zero)\b(?:\s+\w+){0,4}\s+(?:tsc|typecheck|type\s+check|next\s+build)\b/i,
    /\b(?:tsc|typecheck|type\s+check|next\s+build)\b(?:\s+\w+){0,6}\s+(?:failed|failure|failing|error|errors|errored|red|nonzero|non zero)\b/i,
  ]);
}

function typecheckProofSegments(evidence) {
  return String(evidence || '')
    .split(/[;,\n|]+|&&|\b(?:and|then)\b/i)
    .map((part) => normalizedProofText(part))
    .filter(Boolean);
}

function hasNonJsTypecheckContext(evidence) {
  return hasAnyPattern(evidence, [
    /\b(?:mypy|pyright|pyre|ruff|python|pytest|go|golang|cargo|rust|ruby|rubocop|sorbet|phpstan|psalm|javac|gradle|maven|kotlinc|swift|scala|scalac)\b/i,
  ]);
}

function hasJsTsTypecheckContext(evidence) {
  return hasAnyPattern(evidence, [
    /\b(?:tsc|typescript|type\s+script|lint\s+typecheck|lint\s+type\s+check|vue\s+tsc|svelte\s+check)\b/i,
    /\b(?:npm|pnpm|yarn|bun)\s+(?:run\s+)?(?:typecheck|type\s+check|tsc)\b/i,
    /\bnext\s+(?:build|typecheck|type\s+check)\b/i,
    /\b(?:tsx|jsx)\b(?:\s+\w+){0,4}\s+(?:typecheck|type\s+check)\b/i,
    /\b(?:typecheck|type\s+check)\b(?:\s+\w+){0,4}\s+(?:tsx|jsx|typescript|type\s+script|tsc|next)\b/i,
  ]);
}

function hasPositiveTypecheckStatus(evidence) {
  return hasAnyPattern(evidence, [
    /\b(?:tsc|typecheck|type\s+check|lint\s+typecheck|lint\s+type\s+check|vue\s+tsc|svelte\s+check)\b(?:\s+\w+){0,4}\s+(?:pass|passed|passing|clean|succeeded|success|ok|completed)\b/i,
    /\b(?:pass|passed|passing|clean|succeeded|success|ok|completed)\b(?:\s+\w+){0,4}\s+(?:tsc|typecheck|type\s+check|lint\s+typecheck|lint\s+type\s+check|vue\s+tsc|svelte\s+check)\b/i,
    /\bnext\s+build\b(?:\s+\w+){0,4}\s+(?:pass|passed|passing|clean|succeeded|success|ok|completed)\b/i,
    /\b(?:pass|passed|passing|clean|succeeded|success|ok|completed)\b(?:\s+\w+){0,4}\s+next\s+build\b/i,
  ]);
}

function hasPositiveTypecheckProof(result) {
  const commandHasJsTsTypecheck = typecheckProofSegments(result?.command).some((part) => (
    hasJsTsTypecheckContext(part) && !hasNonJsTypecheckContext(part)
  ));
  return typecheckProofSegments(result?.evidence).some((part) => {
    if (hasUnavailableTypecheckProof(part) || hasFailedTypecheckProof(part) || hasNonJsTypecheckContext(part)) return false;
    if (!hasPositiveTypecheckStatus(part)) return false;
    return hasJsTsTypecheckContext(part) || commandHasJsTsTypecheck;
  });
}

function hasUnavailableLintAnalyzeProof(evidence) {
  const proofText = normalizedProofText(evidence);
  return hasAnyPattern(proofText, [
    /\b(?:skipped|skip|not run|unavailable|unsupported|not supported|not applicable|unable|cannot|can t|could not|missing|absent|not available|failed|failure|failing|error|errors|errored)\b(?:\s+\w+){0,4}\s+(?:eslint|biome|oxlint|lint|analyze|analyse|next\s+lint)\b/i,
    /\b(?:eslint|biome|oxlint|lint|analyze|analyse|next\s+lint)\b(?:\s+\w+){0,4}\s+(?:skipped|skip|not run|unavailable|unsupported|not supported|not applicable|unable|cannot|can t|could not|missing|absent|not available|failed|failure|failing|error|errors|errored)\b/i,
    /\b(?:no|without)(?:\s+\w+){0,3}\s+(?:eslint|biome|oxlint|lint|analyze|analyse|next\s+lint)(?:\s+\w+){0,3}\s+(?:evidence|proof|result|output)\b/i,
    /\b(?:eslint|biome|oxlint|lint|analyze|analyse|next\s+lint)(?:\s+\w+){0,3}\s+(?:evidence|proof|result|output)(?:\s+\w+){0,3}\s+(?:unavailable|missing|absent|none|not available|not found)\b/i,
  ]);
}

function hasPositiveLintAnalyzeStatus(evidence) {
  return hasAnyPattern(evidence, [
    /\b(?:eslint|biome|oxlint|typescript\s+eslint|next\s+lint)\b(?:\s+\w+){0,5}\s+(?:pass|passed|passing|clean|succeeded|success|ok|completed)\b/i,
    /\b(?:pass|passed|passing|clean|succeeded|success|ok|completed)\b(?:\s+\w+){0,5}\s+(?:eslint|biome|oxlint|typescript\s+eslint|next\s+lint)\b/i,
    /\b(?:npm|pnpm|yarn|bun)\s+(?:run\s+)?(?:lint|analyze|analyse)\b(?:\s+\w+){0,5}\s+(?:pass|passed|passing|clean|succeeded|success|ok|completed)\b/i,
    /\b(?:pass|passed|passing|clean|succeeded|success|ok|completed)\b(?:\s+\w+){0,5}\s+(?:npm|pnpm|yarn|bun)\s+(?:run\s+)?(?:lint|analyze|analyse)\b/i,
    /\b(?:react|next|typescript|java\s+script|javascript|tsx|jsx|ts|js)\b(?:\s+\w+){0,6}\s+(?:lint|analyze|analyse)\b(?:\s+\w+){0,6}\s+(?:pass|passed|passing|clean|succeeded|success|ok|completed)\b/i,
    /\b(?:lint|analyze|analyse)\b(?:\s+\w+){0,6}\s+(?:react|next|typescript|java\s+script|javascript|tsx|jsx|ts|js)\b(?:\s+\w+){0,6}\s+(?:pass|passed|passing|clean|succeeded|success|ok|completed)\b/i,
    /\b(?:pass|passed|passing|clean|succeeded|success|ok|completed)\b(?:\s+\w+){0,6}\s+(?:react|next|typescript|java\s+script|javascript|tsx|jsx|ts|js)\b(?:\s+\w+){0,6}\s+(?:lint|analyze|analyse)\b/i,
  ]);
}

function hasPositiveLintAnalyzeProof(result) {
  const evidence = words(result?.evidence);
  if (!hasText(evidence) || hasUnavailableLintAnalyzeProof(evidence)) return false;
  return hasPositiveLintAnalyzeStatus(normalizedProofText(evidence));
}

function hasLintAnalyzeTypecheckEvidence(result) {
  return hasPositiveLintAnalyzeProof(result) && hasPositiveTypecheckProof(result);
}

function hasUnavailableReactDoctorProof(evidence) {
  const proofText = normalizedProofText(evidence);
  return hasAnyPattern(proofText, [
    /\b(?:skipped|skip|not run|unavailable|unsupported|not supported|not applicable|unable|cannot|can t|could not|missing|absent|not available)\b(?:\s+\w+){0,4}\s+react\s+doctor\b/i,
    /\breact\s+doctor\b(?:\s+\w+){0,4}\s+(?:skipped|skip|not run|unavailable|unsupported|not supported|not applicable|unable|cannot|can t|could not|missing|absent|not available)\b/i,
    /\b(?:no|without)(?:\s+\w+){0,3}\s+react\s+doctor(?:\s+\w+){0,3}\s+(?:evidence|proof|result|output)\b/i,
    /\breact\s+doctor(?:\s+\w+){0,3}\s+(?:evidence|proof|result|output)(?:\s+\w+){0,3}\s+(?:unavailable|missing|absent|none|not available|not found)\b/i,
  ]);
}

function hasFailedReactDoctorProof(evidence) {
  const proofText = normalizedProofText(evidence);
  return hasAnyPattern(proofText, [
    /\b(?:failed|failure|failing|error|errors|errored|red|nonzero|non zero)\b(?:\s+\w+){0,4}\s+react\s+doctor\b/i,
    /\breact\s+doctor\b(?:\s+\w+){0,6}\s+(?:failed|failure|failing|error|errors|errored|red|nonzero|non zero)\b/i,
  ]);
}

function hasPositiveReactDoctorProof(guardrail) {
  const evidence = words(guardrail?.evidence);
  if (!hasText(evidence) || hasUnavailableReactDoctorProof(evidence) || hasFailedReactDoctorProof(evidence)) return false;
  const proofText = normalizedProofText(evidence);
  return hasAnyPattern(proofText, [
    /\breact\s+doctor\b(?:\s+\w+){0,4}\s+(?:pass|passed|passing|clean|succeeded|success|ok|completed)\b/i,
    /\b(?:pass|passed|passing|clean|succeeded|success|ok|completed)\b(?:\s+\w+){0,4}\s+react\s+doctor\b/i,
  ]);
}

function hasDuplicateCloneDecisionText(evidence) {
  return hasAnyPattern(evidence, [
    /\b(?:duplicates?|clones?|clone groups?|duplicate groups?)\b.*\b(?:owner[- ]?decision|decision|owner[- ]?ledger|ledger|resolved|accepted|recorded)\b/i,
    /\b(?:owner[- ]?decision|decision|owner[- ]?ledger|ledger|resolved|accepted|recorded)\b.*\b(?:duplicates?|clones?|clone groups?|duplicate groups?)\b/i,
  ]);
}

function hasStructuredAcceptedDuplicateCloneDecision(state) {
  return Array.isArray(state.decisions) && state.decisions.some((decision) => {
    if (!isObject(decision) || decision.status !== 'accepted') return false;
    const decisionText = [
      decision.id,
      decision.summary,
      decision.owner,
    ].filter(hasText).join(' ');
    const proofText = [
      words(decision.evidence),
      words(decision.artifacts),
      words(decision.ownerProof),
    ].filter(hasText).join(' ');
    return hasDuplicateCloneDecisionText(`${decisionText} ${proofText}`) && hasDuplicateCloneDecisionText(proofText);
  });
}

function isDuplicateCloneDecisionEntry(entry, guardrail) {
  if (entry?.id === 'fallow') return false;
  if (entry?.id === 'ssot-scanners') return true;
  return hasAnyPattern([entry?.id, guardrail?.owner, guardrail?.command].filter(hasText).join(' '), [
    /\b(?:ssot|single[- ]source|source[- ]of[- ]truth|owner[- ]?ledger|clone[- ]?decision|duplicate[- ]?decision)\b/i,
  ]);
}

function hasActiveDuplicateCloneDecision(state, entries) {
  if (hasStructuredAcceptedDuplicateCloneDecision(state)) return true;
  return entries.some((entry) => {
    if (!isObject(entry) || entry.status !== 'required') return false;
    const guardrail = guardrailById(state.guardrails, entry.guardrailId);
    if (guardrail?.status !== 'passed') return false;
    if (!isDuplicateCloneDecisionEntry(entry, guardrail)) return false;
    const evidence = [
      words(entry.evidence),
      words(guardrail.evidence),
    ].filter(hasText).join(' ');
    return hasDuplicateCloneDecisionText(evidence);
  });
}

function hasAcceptedNonJsCloneFallback(state, entries, evidence, requireToolAbsence) {
  const hasToolAbsence = hasFallowToolAbsenceEvidence(evidence);
  const hasStaticSearch = hasStaticDuplicateSearchEvidence(evidence);
  const hasCleanSearchProof = hasNoDuplicateCloneProof(evidence) && !hasFoundDuplicateCloneEvidence(evidence);
  const hasRecordedCloneDecision = hasFoundDuplicateCloneEvidence(evidence) && hasActiveDuplicateCloneDecision(state, entries);
  return (!requireToolAbsence || hasToolAbsence) && hasStaticSearch && (hasCleanSearchProof || hasRecordedCloneDecision);
}

const touchedStackAliases = new Map([
  ['js', ['javascript']],
  ['mjs', ['js', 'javascript']],
  ['cjs', ['js', 'javascript']],
  ['jsx', ['js', 'javascript', 'react', 'ui', 'component']],
  ['ts', ['typescript']],
  ['mts', ['ts', 'typescript']],
  ['cts', ['ts', 'typescript']],
  ['tsx', ['ts', 'typescript', 'react', 'ui', 'component']],
  ['react', ['ui', 'component']],
  ['next', ['ui', 'screen']],
  ['page', ['screen']],
  ['py', ['python']],
  ['kt', ['kotlin']],
  ['kts', ['kotlin']],
  ['rs', ['rust']],
  ['go', ['golang']],
  ['rb', ['ruby']],
  ['php', ['php']],
  ['java', ['java']],
  ['swift', ['swift']],
  ['scala', ['scala']],
  ['c', ['c']],
  ['cc', ['cpp']],
  ['cpp', ['cpp']],
  ['h', ['c', 'cpp']],
  ['hpp', ['cpp']],
  ['css', ['style']],
  ['scss', ['style']],
  ['sass', ['style']],
  ['less', ['style']],
  ['styling', ['style']],
  ['sql', ['schema', 'backend']],
  ['migration', ['schema', 'backend']],
  ['openapi', ['api', 'schema', 'backend']],
  ['graphql', ['api', 'schema', 'backend']],
  ['gql', ['api', 'schema', 'backend']],
]);

function stackTokenVariants(token) {
  const variants = [token];
  if (token.endsWith('ies') && token.length > 4) variants.push(`${token.slice(0, -3)}y`);
  if (token.endsWith('s') && !token.endsWith('ss') && token.length > 3) variants.push(token.slice(0, -1));
  const aliases = touchedStackAliases.get(token);
  if (aliases) variants.push(...aliases);
  return variants;
}

function normalizedTouchedStackText(touchedStacks) {
  const tokens = new Set();
  for (const stack of touchedStacks) {
    const text = stack
      .replace(/([a-z0-9])([A-Z])/g, '$1 $2')
      .toLowerCase();
    tokens.add(text);
    for (const token of text.split(/[^a-z0-9]+/).filter(Boolean)) {
      for (const variant of stackTokenVariants(token)) tokens.add(variant);
    }
  }
  return Array.from(tokens).join(' ');
}

function guardrailById(guardrails, id) {
  return Array.isArray(guardrails) ? guardrails.find((guardrail) => guardrail?.id === id) : null;
}

const guardrailClassPatterns = new Map([
  ['regex-scanners', [/\b(regex|regexp|ripgrep|rg|grep|pattern[- ]?scanner)\b/i]],
  ['git-hooks', [/\b(pre-commit|pre-push|post-merge|post-rewrite|git[- ]?hook|ensure-worktree-ready\.sh)\b/i, /\.githooks\b/i]],
  ['lint-analyze-typecheck', [/\b(eslint|lint|tsc|typecheck|type-check|analyze|mypy|ruff|biome)\b/i]],
  ['ssot-scanners', [/\b(check-ssot-guardrails\.mjs|ssot|single[- ]source|source[- ]of[- ]truth)\b/i]],
  ['fallow', [/\bfallow\b/i]],
  ['react-doctor', [/\breact-doctor\b/i]],
  ['repeat-mistake-prevention', [/\b(repeat(?:ed)?[- ]?mistake|mistake[- ]?prevention|he-learn|learning|regression|durable[- ]?guard|eval)\b/i]],
]);

function guardrailMatchesRequiredClass(guardrail, requiredClass) {
  const patterns = guardrailClassPatterns.get(requiredClass);
  if (!patterns) return false;
  const text = [guardrail?.owner, guardrail?.command]
    .filter(hasText)
    .join(' ');
  return patterns.some((pattern) => pattern.test(text));
}

function validateTouchedStackInventory(state, inventory, entries, errors, readinessRequiresInventory) {
  const touchedStacks = inventory.touchedStacks;
  if (touchedStacks !== undefined && !stringArray(touchedStacks)) {
    errors.push('guardrailInventory.touchedStacks must be string[]');
    return;
  }
  if (!Array.isArray(touchedStacks) || touchedStacks.length === 0) {
    if (readinessRequiresInventory) errors.push('guardrailInventory.touchedStacks is required for ready handoff');
    return;
  }
  if (!touchedStacks.every(hasText)) {
    errors.push('guardrailInventory.touchedStacks must contain non-empty strings');
    return;
  }

  const touchedText = normalizedTouchedStackText(touchedStacks);
  const entryById = new Map(entries.filter((entry) => isObject(entry)).map((entry) => [entry.id, entry]));
  const ssot = entryById.get('ssot-scanners');
  const fallow = entryById.get('fallow');
  const ssotSensitive = /\b(ui|component|widget|screen|list|row|card|modal|form|picker|tab|navigation|cta|empty|loading|error|calendar|date|grid|month|select|single|multi|checkbox|toggle|selectable|chip|settings|answer|alert|control|button|input|label|drag|drop|search|filter|pagination|upload|stepper|react|next|tsx|jsx|page|api|schema|repository|query|cache|backend|permission|constant|fixture|helper|design|token|theme|typography|spacing|color|style|styling|css|radius|motion|time|currency|number|formatting)\b/i.test(touchedText);
  const jsTsTouched = /\b(js|javascript|ts|typescript|tsx|jsx|react|next)\b/i.test(touchedText);
  const reactNextTouched = /\b(react|next|tsx|jsx)\b/i.test(touchedText);
  const nonJsLanguageTouched = /\b(flutter|dart|swift|kotlin|java|python|go|golang|rust|ruby|php|scala|c|cpp)\b/i.test(touchedText);
  const nonJsCodeTouched = nonJsLanguageTouched || (/\b(backend|api|schema)\b/i.test(touchedText) && !jsTsTouched);

  if (ssotSensitive && ssot?.status === 'not_applicable') {
    const evidence = `${ssot.reason || ''} ${words(ssot.evidence)}`;
    const hasOwnerEvidence = hasAnyPattern(evidence, [
      /component[- ]?pattern|interaction[- ]?pattern|shared widget|shared component|similar (screen|row|card|form|picker|calendar)|owner ledger/i,
      /api owner|schema owner|repository owner|query owner|cache owner|permission owner/i,
      /(list|row|card|modal|form|picker|tab|navigation|cta|empty|loading|error|selectable|settings|answer|alert|calendar|date-grid|month|drag|search|filter|pagination|upload|stepper|token|theme|typography|spacing|color|radius|motion).*(owner|pattern|search|searched|ledger|reuse|extend)/i,
      /(owner|pattern|search|searched|ledger|reuse|extend).*(list|row|card|modal|form|picker|tab|navigation|cta|empty|loading|error|selectable|settings|answer|alert|calendar|date-grid|month|drag|search|filter|pagination|upload|stepper|token|theme|typography|spacing|color|radius|motion)/i,
    ]);
    if (!hasOwnerEvidence) {
      errors.push('ssot-scanners cannot be not_applicable for UI/component/API/schema touched stacks without explicit owner or component-pattern search evidence');
    }
  }
  if (ssotSensitive && ssot?.status === 'required') {
    const guardrail = guardrailById(state.guardrails, ssot.guardrailId);
    if (guardrail?.status !== 'passed' || !guardrailMatchesRequiredClass(guardrail, 'ssot-scanners')) {
      errors.push('ssot-scanners requires passed SSOT scanner evidence for UI/component/API/schema touched stacks');
    }
  }

  if (jsTsTouched && fallow?.status === 'not_applicable') {
    errors.push('fallow cannot be not_applicable for JS/TS/React/Next touched stacks; record Fallow duplicate/clone evidence as a required guardrail');
  }
  if (jsTsTouched && fallow?.status === 'required') {
    const guardrail = guardrailById(state.guardrails, fallow.guardrailId);
    const evidence = fallowResultEvidenceText(state, fallow);
    if (guardrail?.status !== 'passed' || !hasAcceptedJsTsFallowDuplicateCloneEvidence(state, entries, evidence)) {
      errors.push('JS/TS/React/Next touched stacks require Fallow duplicate/clone evidence');
    }
  }
  if (reactNextTouched) {
    const reactDoctor = entryById.get('react-doctor');
    const lintTypecheck = entryById.get('lint-analyze-typecheck');
    if (reactDoctor?.status === 'not_applicable') {
      errors.push('react-doctor cannot be not_applicable for React/Next touched stacks; record React Doctor evidence as a required guardrail');
    }
    if (reactDoctor?.status === 'required') {
      const guardrail = guardrailById(state.guardrails, reactDoctor.guardrailId);
      if (guardrail?.status !== 'passed' || !guardrailMatchesRequiredClass(guardrail, 'react-doctor') || !hasPositiveReactDoctorProof(guardrail)) {
        errors.push('react-doctor requires passed React Doctor evidence for React/Next touched stacks');
      }
    }
    if (lintTypecheck?.status === 'not_applicable') {
      errors.push('lint-analyze-typecheck cannot be not_applicable for React/Next touched stacks; record lint and typecheck evidence as a required guardrail');
    }
    if (lintTypecheck?.status === 'required') {
      const guardrail = guardrailById(state.guardrails, lintTypecheck.guardrailId);
      if (guardrail?.status !== 'passed' || !hasLintAnalyzeTypecheckEvidence(guardrailResult(state, lintTypecheck))) {
        errors.push('lint-analyze-typecheck requires lint/analyze and typecheck evidence for React/Next touched stacks');
      }
    }
  }
  if (nonJsCodeTouched && fallow?.status === 'not_applicable') {
    const evidence = entryEvidenceText(state, fallow);
    if (!hasAcceptedNonJsCloneFallback(state, entries, evidence, true)) {
      errors.push('fallow not_applicable for non-JS/TS stacks requires stack-specific tool absence plus explicit no-duplicate/no-clone static-search proof or an active guardrail/SSOT clone decision');
    }
  }
  if (nonJsCodeTouched && fallow?.status === 'required') {
    const guardrail = guardrailById(state.guardrails, fallow.guardrailId);
    const evidence = words(guardrail?.evidence);
    if (guardrail?.status !== 'passed' || !hasAcceptedNonJsCloneFallback(state, entries, evidence, false)) {
      errors.push(jsTsTouched && nonJsLanguageTouched
        ? 'mixed JS/TS and non-JS stacks require Fallow JS/TS evidence plus explicit non-JS no-duplicate/no-clone static-search proof or an active guardrail/SSOT clone decision'
        : 'fallow required for non-JS/TS stacks requires explicit no-duplicate/no-clone static-search proof or an active guardrail/SSOT clone decision');
    }
  }
}

export function validateGuardrailInventory(state, errors) {
  const inventory = state.guardrailInventory;
  if (inventory !== undefined && !isObject(inventory)) {
    errors.push('guardrailInventory must be an object');
    return;
  }
  const readinessRequiresInventory = state.next?.ready === true && requiredInventoryStages.has(state.stage);
  if (readinessRequiresInventory && !isObject(inventory)) {
    errors.push(`${state.stage} ready handoff requires guardrailInventory`);
    return;
  }
  if (!isObject(inventory)) return;

  const entries = inventory.requiredGuardrails;
  if (!Array.isArray(entries)) {
    errors.push('guardrailInventory.requiredGuardrails must be an array');
    return;
  }
  validateTouchedStackInventory(state, inventory, entries, errors, readinessRequiresInventory);

  const counts = new Map();
  for (const [index, entry] of entries.entries()) {
    if (!isObject(entry)) {
      errors.push(`guardrailInventory.requiredGuardrails[${index}] must be an object`);
      continue;
    }
    if (!hasText(entry.id)) {
      errors.push(`guardrailInventory.requiredGuardrails[${index}].id is required`);
      continue;
    }
    counts.set(entry.id, (counts.get(entry.id) || 0) + 1);
    if (!requiredGuardrailClasses.includes(entry.id)) {
      errors.push(`guardrailInventory.requiredGuardrails[${index}].id is invalid`);
    }
    if (!inventoryStatuses.has(entry.status)) {
      errors.push(`guardrailInventory.requiredGuardrails[${index}].status must be required or not_applicable`);
    }
    if (!stringArray(entry.evidence) || entry.evidence.length === 0 || !entry.evidence.every(hasText)) {
      errors.push(`guardrailInventory.requiredGuardrails[${index}].evidence must be non-empty string[]`);
    }
    if (entry.status === 'not_applicable' && !hasText(entry.reason)) {
      errors.push(`guardrailInventory.requiredGuardrails[${index}].reason is required for not_applicable`);
    }
    if (entry.status === 'required') {
      if (!hasText(entry.guardrailId)) {
        errors.push(`guardrailInventory.requiredGuardrails[${index}].guardrailId is required for required`);
        continue;
      }
      const guardrail = guardrailById(state.guardrails, entry.guardrailId);
      if (!guardrail) {
        errors.push(`${entry.id} requires guardrails[] entry ${entry.guardrailId}`);
      } else if (!['passed', 'skipped'].includes(guardrail.status)) {
        errors.push(`${entry.id} requires guardrails[] entry ${entry.guardrailId} to be passed or explicitly skipped`);
      } else if (!guardrailMatchesRequiredClass(guardrail, entry.id)) {
        errors.push(`${entry.id} requires guardrails[] entry ${entry.guardrailId} to match ${entry.id}`);
      }
    }
  }

  for (const id of requiredGuardrailClasses) {
    const count = counts.get(id) || 0;
    if (readinessRequiresInventory && count !== 1) errors.push(`guardrailInventory.requiredGuardrails requires exactly one ${id}`);
    if (!readinessRequiresInventory && count > 1) errors.push(`guardrailInventory.requiredGuardrails has duplicate ${id}`);
  }
}
