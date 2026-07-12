export function skillDescription(text) {
  const lines = String(text ?? '').split(/\r?\n/);
  if (lines[0]?.trim() !== '---') return '';
  const end = lines.findIndex((line, index) => index > 0 && line.trim() === '---');
  if (end < 0) return '';
  const index = lines.slice(1, end).findIndex((line) => line.startsWith('description:')) + 1;
  if (index < 1) return '';
  const scalar = lines[index].slice('description:'.length).trim();
  if (!['>', '>-', '|', '|-'].includes(scalar)) {
    if (scalar.startsWith('"') && scalar.endsWith('"')) {
      try { return JSON.parse(scalar); } catch { return ''; }
    }
    return scalar.replace(/^'|'$/g, '').trim();
  }
  const body = [];
  for (const line of lines.slice(index + 1, end)) {
    if (line && !/^\s+/.test(line)) break;
    body.push(line.trim());
  }
  return body.join(scalar.startsWith('>') ? ' ' : '\n').trim();
}

export function skillInvocationPolicy(text) {
  const lines = String(text ?? '').split(/\r?\n/);
  const policyIndex = lines.findIndex((line) => /^policy:\s*(?:\{\s*\})?\s*(?:#.*)?$/.test(line));
  if (policyIndex < 0 || /^policy:\s*\{\s*\}/.test(lines[policyIndex])) {
    return { allow_implicit_invocation: true, source: 'codex-default' };
  }

  const values = [];
  for (const line of lines.slice(policyIndex + 1)) {
    if (/^[A-Za-z_][A-Za-z0-9_-]*:\s*/.test(line)) break;
    if (!/^\s+allow_implicit_invocation\s*:/.test(line)) continue;
    const match = /^\s+allow_implicit_invocation\s*:\s*(true|false)\s*(?:#.*)?$/.exec(line);
    if (!match) throw new Error('Skill allow_implicit_invocation policy must be a boolean.');
    values.push(match[1] === 'true');
  }
  if (values.length > 1) throw new Error('Skill allow_implicit_invocation policy is duplicated.');
  return values.length === 1
    ? { allow_implicit_invocation: values[0], source: 'declared' }
    : { allow_implicit_invocation: true, source: 'codex-default' };
}
