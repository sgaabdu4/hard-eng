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

function openLearningFindings(state) {
  return Array.isArray(state.findings)
    ? state.findings.filter((finding) => finding?.ownerStage === 'he-learn' && finding?.repairType === 'learning' && ['open', 'owned', 'blocked', 'fixed', 'accepted'].includes(finding.status))
    : [];
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

  const required = state.e2ePolicy?.requiredApprovalBoundaries;
  if (required !== undefined && !stringArray(required)) {
    errors.push('e2ePolicy.requiredApprovalBoundaries must be string[]');
    return;
  }
  if (!Array.isArray(required) || required.length === 0) return;
  if (state.next?.ready !== true) return;
  if (!Array.isArray(boundaries)) {
    errors.push('approvalBoundaries are required when e2ePolicy.requiredApprovalBoundaries is non-empty');
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
    if (!hasText(miss.issueClass)) errors.push(`repeatMisses[${index}].issueClass is required`);
    if (!stringArray(miss.evidence) || miss.evidence.length === 0) errors.push(`repeatMisses[${index}].evidence must be non-empty string[]`);
  }
  const grouped = new Map();
  for (const miss of repeatMisses) {
    if (!hasText(miss?.issueClass)) continue;
    grouped.set(miss.issueClass, (grouped.get(miss.issueClass) || 0) + 1);
  }
  const repeatedClasses = Array.from(grouped.entries()).filter(([, count]) => count >= 2).map(([issueClass]) => issueClass);
  if (!repeatedClasses.length) return;
  const findingText = openLearningFindings(state).map((finding) => [
    finding.summary,
    finding.owner,
    textOf(finding.ownerProof),
    textOf(finding.artifacts),
  ].filter(Boolean).join(' ')).join(' ');
  for (const issueClass of repeatedClasses) {
    if (!findingText.toLowerCase().includes(issueClass.toLowerCase())) {
      errors.push(`repeatMisses ${issueClass} requires a he-learn learning finding`);
    }
  }
}

export function validateComplianceState(state, errors) {
  validateApprovalBoundaries(state, errors);
  validateRepeatMisses(state, errors);
}
