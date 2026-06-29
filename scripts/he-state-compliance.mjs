const approvalStatuses = new Set(['approved', 'blocked', 'not_required']);
const approvalCategories = new Set([
  'prod-backend-write',
  'native-permission',
  'real-credentials',
  'generated-credentials',
  'prod-cleanup',
]);

function isObject(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

function hasText(value) {
  return typeof value === 'string' && value.trim().length > 0;
}

function stringArray(value) {
  return Array.isArray(value) && value.every((item) => typeof item === 'string');
}

function textOf(value) {
  if (Array.isArray(value)) return value.filter((item) => typeof item === 'string').join(' ');
  if (typeof value === 'string') return value;
  return '';
}

function collectText(value) {
  if (typeof value === 'string') return value;
  if (Array.isArray(value)) return value.map(collectText).filter(Boolean).join(' ');
  if (isObject(value)) return Object.values(value).map(collectText).filter(Boolean).join(' ');
  return '';
}

function collectStrings(value) {
  if (typeof value === 'string') return [value];
  if (Array.isArray(value)) return value.flatMap(collectStrings);
  if (isObject(value)) return Object.values(value).flatMap(collectStrings);
  return [];
}

function normalizeEvidenceText(text) {
  return text
    .replace(/([a-z0-9])([A-Z])/g, '$1 $2')
    .replace(/[^a-z0-9]+/gi, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .toLowerCase();
}

function matchesAny(text, patterns) {
  return patterns.some((pattern) => pattern.test(text));
}

const approvalBoundaryEvidencePatterns = new Map([
  ['prod-backend-write', [
    /\b(?:changed|change|changing|wrote|write|writing|mutated|mutation|mutate|deleted|delete|deleting)\b.*\b(?:prod|production)\b/,
    /\b(?:prod|production)\b.*\b(?:changed|change|changing|wrote|write|writing|mutated|mutation|mutate|deleted|delete|deleting)\b/,
    /\b(?:changed|change|changing|wrote|write|writing|mutated|mutation|mutate|deleted|delete|deleting)\b.*\b(?:backend|appwrite|database|db|permission|permissions|schema|index)\b.*\b(?:prod|production)\b/,
    /\b(?:changed|change|changing|wrote|write|writing|mutated|mutation|mutate|deleted|delete|deleting)\b.*\b(?:prod|production)\b.*\b(?:backend|appwrite|database|db|permission|permissions|schema|index)\b/,
    /\b(?:prod|production)\b.*\b(?:backend|appwrite|database|db|permission|permissions|schema|index)\b.*\b(?:changed|change|changing|wrote|write|writing|mutated|mutation|mutate|deleted|delete|deleting|gap|fix|fixed)\b/,
    /\b(?:backend|appwrite|database|db)\b.*\b(?:permission|permissions|schema|index)\b.*\b(?:prod|production|changed|change|changing|wrote|write|writing|mutated|mutation|mutate|deleted|delete|deleting|gap|fix|fixed)\b/,
    /\b(?:backend|appwrite|database|db)\b.*\b(?:schema|index|permission|permissions)\b.*\b(?:must|need|needs|required|requires)\b.*\b(?:change|write|mutation|fix)\b/,
  ]],
  ['native-permission', [
    /\bnative\b.*\b(?:permission|prompt|dialog)\b/,
    /\bpermission\b.*\bprompt\b/,
    /\b(?:native|permission|prompt|dialog)\b.*\b(?:clicked|click|accepted|accept|allowed|allow|granted|grant)\b/,
    /\b(?:clicked|click|accepted|accept|allowed|allow|granted|grant)\b.*\b(?:native|permission|prompt|dialog)\b/,
  ]],
  ['real-credentials', [
    /\breal\b.*\b(?:credential|credentials|account|user)\b/,
    /\b(?:used|use|using|logged|login)\b.*\b(?:saved auth|personal account|real credential|real credentials|real account|real user)\b/,
  ]],
  ['generated-credentials', [
    /\bgenerated\b.*\b(?:credential|credentials|user|test user|account|password)\b/,
    /\b(?:created|create|generated|used|use|using)\b.*\bgenerated\b.*\b(?:user|credential|credentials|password|account)\b/,
  ]],
  ['prod-cleanup', [
    /\b(?:prod|production)\b.*\bcleanup\b/,
    /\bcleanup\b.*\b(?:prod|production)\b/,
  ]],
]);

const nonRiskApprovalEvidencePatterns = [
  /\b(?:no|not|never|without)(?:\s+\w+){0,3}\s+(?:real\s+credentials?|real\s+accounts?|real\s+users?|generated\s+credentials?|generated\s+users?|generated\s+accounts?|native\s+permission|permission\s+prompt)\b/,
  /\b(?:no|not|never|without)(?:\s+\w+){0,3}\s+(?:prod|production)\s+(?:cleanup|write|writes|mutation|delete|backend|appwrite|database|db)\b/,
  /\b(?:no|not|never|without)(?:\s+\w+){0,4}\s+(?:prod|production|backend|appwrite|database|db|native|real|generated|credential|credentials|cleanup)(?:\s+\w+){0,6}\s+(?:write|writes|wrote|mutation|mutate|mutated|change|changed|delete|deleted|created|create|used|use|clicked|click|allow|cleanup)\b/,
  /\b(?:no|not|never|without)(?:\s+\w+){0,4}\s+(?:write|writes|wrote|mutation|mutate|mutated|change|changed|delete|deleted|created|create|used|use|clicked|click|allow|cleanup)(?:\s+\w+){0,6}\s+(?:prod|production|backend|appwrite|database|db|native|real|generated|credential|credentials|cleanup)\b/,
];

const preventionOnlyApprovalEvidencePatterns = [
  /\b(?:prevent|prevents|prevented|prevention|blocked|blocking|guarded|guardrail|check|scanner|validation|verify|verified)(?:\s+\w+){0,8}\s+(?:no|without|blocked|denied|read only|readonly|clean)\b/,
  /\b(?:read only|readonly)(?:\s+\w+){0,6}\s+(?:check|probe|review|inspection|verification|prevention|passed|clean)\b/,
  /\b(?:check|probe|review|inspection|verification|prevention)(?:\s+\w+){0,6}\s+(?:read only|readonly)\b/,
];

const performedApprovalRiskActionPatterns = [
  /\b(?:changed|changing|wrote|writing|mutated|mutating|deleted|deleting|created|creating|used|using|clicked|accepted|allowed|granted|logged)\b/,
  /\blogged\s+in\b/,
];

function firstPatternIndex(text, patterns) {
  return patterns.reduce((earliest, pattern) => {
    const match = text.match(pattern);
    if (!match || match.index === undefined) return earliest;
    return earliest === -1 ? match.index : Math.min(earliest, match.index);
  }, -1);
}

function hasPerformedApprovalRiskAction(text) {
  return matchesAny(text, performedApprovalRiskActionPatterns);
}

function isNonRiskApprovalEvidence(text) {
  if (/\b(?:no|without)(?:\s+\w+){0,2}\s+approval\b/.test(text)) return false;
  const negationIndex = firstPatternIndex(text, [/\b(?:no|not|never|without|read only|readonly)\b/]);
  const actionIndex = firstPatternIndex(text, performedApprovalRiskActionPatterns);
  if (matchesAny(text, nonRiskApprovalEvidencePatterns)) {
    return actionIndex === -1 || (negationIndex !== -1 && negationIndex <= actionIndex);
  }
  if (matchesAny(text, preventionOnlyApprovalEvidencePatterns)) {
    return !hasPerformedApprovalRiskAction(text);
  }
  return false;
}

function approvalBoundaryCategoriesForText(text) {
  const categories = new Set();
  const segments = String(text).split(/[;,\n|]+|\.(?=\s|$)/).map(normalizeEvidenceText).filter(Boolean);
  for (const normalized of segments) {
    if (isNonRiskApprovalEvidence(normalized)) continue;
    for (const [category, patterns] of approvalBoundaryEvidencePatterns.entries()) {
      if (matchesAny(normalized, patterns)) categories.add(category);
    }
  }
  return Array.from(categories);
}

function inferredApprovalBoundaryCategories(state) {
  const categories = new Set();
  const texts = collectStrings(state.e2ePolicy);
  if (Array.isArray(state.guardrails)) {
    for (const guardrail of state.guardrails) {
      if (!isObject(guardrail) || guardrail.kind === 'eval') continue;
      texts.push(...collectStrings(guardrail.evidence), ...collectStrings(guardrail.reason));
    }
  }
  for (const text of texts) {
    for (const category of approvalBoundaryCategoriesForText(text)) categories.add(category);
  }
  return categories;
}

function normalizeIssueClass(issueClass) {
  return issueClass.trim().toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/-+/g, '-').replace(/^-|-$/g, '');
}

function escapedRegExp(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function openLearningFindings(state) {
  return Array.isArray(state.findings)
    ? state.findings.filter((finding) => finding?.ownerStage === 'he-learn' && finding?.repairType === 'learning' && ['open', 'owned', 'blocked', 'fixed', 'accepted'].includes(finding.status))
    : [];
}

function learningFindingMatchesIssueClass(finding, issueClass) {
  const structuredIssueClass = hasText(finding?.issueClass) ? normalizeIssueClass(finding.issueClass) : '';
  if (structuredIssueClass && structuredIssueClass === issueClass) return true;
  const findingText = normalizeIssueClass([
    finding.summary,
    finding.owner,
    textOf(finding.ownerProof),
    textOf(finding.artifacts),
  ].filter(Boolean).join(' '));
  return new RegExp(`(?:^|-)${escapedRegExp(issueClass)}(?:-|$)`).test(findingText);
}

function validateApprovalBoundaries(state, errors) {
  const boundaries = state.approvalBoundaries;
  if (boundaries !== undefined && !Array.isArray(boundaries)) {
    errors.push('approvalBoundaries must be an array');
    return;
  }
  if (Array.isArray(boundaries)) {
    for (const [index, boundary] of boundaries.entries()) {
      if (!isObject(boundary)) {
        errors.push(`approvalBoundaries[${index}] must be an object`);
        continue;
      }
      for (const key of ['id', 'category', 'status', 'reason']) {
        if (!hasText(boundary[key])) errors.push(`approvalBoundaries[${index}].${key} is required`);
      }
      if (boundary.category && !approvalCategories.has(boundary.category)) errors.push(`approvalBoundaries[${index}].category is invalid`);
      if (boundary.status && !approvalStatuses.has(boundary.status)) errors.push(`approvalBoundaries[${index}].status must be approved, blocked, or not_required`);
      if (!stringArray(boundary.evidence) || boundary.evidence.length === 0) errors.push(`approvalBoundaries[${index}].evidence must be non-empty string[]`);
      if (['real-credentials', 'generated-credentials'].includes(boundary.category)) {
        if (!hasText(boundary.redactedCredentialRef)) errors.push(`approvalBoundaries[${index}].redactedCredentialRef is required for ${boundary.category}`);
        if (!hasText(boundary.dataScope)) errors.push(`approvalBoundaries[${index}].dataScope is required for ${boundary.category}`);
      }
      if (boundary.category === 'generated-credentials') {
        if (!stringArray(boundary.cleanupProof) || boundary.cleanupProof.length === 0) errors.push(`approvalBoundaries[${index}].cleanupProof must be non-empty string[] for generated credentials`);
      }
    }
  }

  const configuredRequired = state.e2ePolicy?.requiredApprovalBoundaries;
  if (configuredRequired !== undefined && !stringArray(configuredRequired)) {
    errors.push('e2ePolicy.requiredApprovalBoundaries must be string[]');
    return;
  }
  const inferredRequired = inferredApprovalBoundaryCategories(state);
  const required = [
    ...(Array.isArray(configuredRequired) ? configuredRequired : []),
    ...inferredRequired,
  ].filter((category, index, categories) => categories.indexOf(category) === index);
  if (required.length === 0) return;
  if (state.next?.ready !== true) return;
  if (!Array.isArray(boundaries)) {
    errors.push(`approvalBoundaries are required when ${Array.isArray(configuredRequired) && configuredRequired.length > 0 ? 'e2ePolicy.requiredApprovalBoundaries is non-empty' : 'guardrail evidence records risky actions'}`);
    return;
  }
  for (const category of required) {
    if (!approvalCategories.has(category)) {
      errors.push(`e2ePolicy.requiredApprovalBoundaries includes invalid ${category}`);
      continue;
    }
    const boundary = boundaries.find((item) => item?.category === category);
    if (!boundary) {
      errors.push(`approvalBoundaries requires ${category}`);
      continue;
    }
    if (boundary.status !== 'approved') {
      errors.push(`approvalBoundaries ${category} must be approved before ready handoff`);
    }
  }
}

function validateRepeatMisses(state, errors) {
  const repeatMisses = state.repeatMisses;
  if (repeatMisses !== undefined && !Array.isArray(repeatMisses)) {
    errors.push('repeatMisses must be an array');
    return;
  }
  if (!Array.isArray(repeatMisses) || repeatMisses.length === 0) return;
  for (const [index, miss] of repeatMisses.entries()) {
    if (!isObject(miss)) {
      errors.push(`repeatMisses[${index}] must be an object`);
      continue;
    }
    if (!hasText(miss.issueClass)) {
      errors.push(`repeatMisses[${index}].issueClass is required`);
    } else if (!normalizeIssueClass(miss.issueClass)) {
      errors.push(`repeatMisses[${index}].issueClass must include an alphanumeric slug`);
    }
    if (!stringArray(miss.evidence) || miss.evidence.length === 0) errors.push(`repeatMisses[${index}].evidence must be non-empty string[]`);
  }
  const grouped = new Map();
  for (const miss of repeatMisses) {
    if (!hasText(miss?.issueClass)) continue;
    const issueClass = normalizeIssueClass(miss.issueClass);
    if (!issueClass) continue;
    grouped.set(issueClass, (grouped.get(issueClass) || 0) + 1);
  }
  const repeatedClasses = Array.from(grouped.entries()).filter(([, count]) => count >= 2).map(([issueClass]) => issueClass);
  if (!repeatedClasses.length) return;
  const learningFindings = openLearningFindings(state);
  for (const issueClass of repeatedClasses) {
    if (!learningFindings.some((finding) => learningFindingMatchesIssueClass(finding, issueClass))) {
      errors.push(`repeatMisses ${issueClass} requires a he-learn learning finding`);
    }
  }
}

export function validateComplianceState(state, errors) {
  validateApprovalBoundaries(state, errors);
  validateRepeatMisses(state, errors);
}
