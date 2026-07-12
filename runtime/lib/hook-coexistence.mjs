export function auditPreToolHookResponses(responses) {
  if (!Array.isArray(responses) || responses.length === 0) throw new Error('PreToolUse coexistence evidence is missing.');
  const updatedOwners = [];
  for (const entry of responses) {
    const output = entry.output?.hookSpecificOutput ?? {};
    if (output.permissionDecision === 'deny' || entry.output?.decision === 'block') {
      throw new Error(`${entry.owner} blocks the Hard Eng state tool.`);
    }
    if (output.updatedInput !== undefined) updatedOwners.push(entry.owner);
  }
  if (updatedOwners.length !== 1 || updatedOwners[0] !== 'hard-eng') {
    throw new Error(`Hard Eng must be the sole updatedInput owner; found ${updatedOwners.join(', ') || 'none'}.`);
  }
  return { status: 'PASS', updated_input_owner: 'hard-eng', observers: responses.map((entry) => entry.owner).filter((owner) => owner !== 'hard-eng') };
}
