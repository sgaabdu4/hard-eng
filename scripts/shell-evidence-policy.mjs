const allowedAssignments = new Map([
  ['NODE_ENV', new Set(['test'])],
]);

export function shellEnvironmentAssignment(word) {
  const match = String(word || '').match(/^([A-Za-z_][A-Za-z0-9_]*)(\+?=)(.*)$/);
  return match ? { name: match[1], operator: match[2], value: match[3] } : null;
}

export function isAllowedShellEvidenceAssignment(word) {
  const assignment = shellEnvironmentAssignment(word);
  return assignment?.operator === '=' && allowedAssignments.get(assignment.name)?.has(assignment.value) === true;
}
