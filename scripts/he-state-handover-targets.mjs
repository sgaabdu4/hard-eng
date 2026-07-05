function hasText(value) {
  return typeof value === 'string' && value.trim().length > 0;
}

function normalizeText(value) {
  return String(value || '')
    .replace(/([a-z0-9])([A-Z])/g, '$1 $2')
    .replace(/[^a-z0-9]+/gi, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .toLowerCase();
}

function unique(values) {
  return [...new Set(values)];
}

function normalizeTarget(value) {
  return /^loop[- ]complete$/i.test(value) ? 'loop-complete' : value.toLowerCase();
}

function targetText(value) {
  return normalizeTarget(value).replace('/', '').replace(':', ' ');
}

function clauseAround(text, index) {
  const before = text.slice(0, index);
  const after = text.slice(index);
  const start = Math.max(before.lastIndexOf('.'), before.lastIndexOf(';'), before.lastIndexOf('\n')) + 1;
  const endOffsets = ['.', ';', '\n']
    .map((delimiter) => after.indexOf(delimiter))
    .filter((offset) => offset >= 0);
  const end = endOffsets.length ? index + Math.min(...endOffsets) : text.length;
  return text.slice(start, end);
}

function hasNegatedTargetReference(clause, target) {
  const normalized = normalizeText(clause);
  const normalizedTarget = targetText(target).replace(/\s+/g, '\\s+');
  return new RegExp(`\\b(?:do\\s+not|don\\s+t|dont|not|never|avoid|without|no)\\b.{0,50}\\b${normalizedTarget}\\b`).test(normalized) ||
    new RegExp(`\\b${normalizedTarget}\\b.{0,50}\\b(?:later|yet)\\b`).test(normalized);
}

export function targetCommandsFromText(value) {
  const text = String(value || '');
  if (!hasText(text)) return [];
  const targets = [];
  const pattern = /\/he:[a-z-]+|loop[- ]complete/gi;
  for (let match = pattern.exec(text); match !== null; match = pattern.exec(text)) {
    const target = normalizeTarget(match[0]);
    if (!hasNegatedTargetReference(clauseAround(text, match.index), target)) targets.push(target);
  }
  return unique(targets);
}

const handoverLabelSource = String.raw`Artifact ready|Owner\/proof|Owner proof|Handover prompt|Command(?:\s+(?:to\s+run|target))?|Blockers?|Artifacts?|Readiness|Ready|Stage|State|Decision|Next|Worktree`;

function handoverLabelEntries(value) {
  const text = String(value || '');
  if (!hasText(text)) return [];
  const boundaries = [];
  const pattern = new RegExp(`(?:^|[.;\\n]\\s*|\\s+)(?:(?<label>${handoverLabelSource})\\s*:|(?<read>Read\\s+\\S+\\.json\\s+first\\b))`, 'gi');
  for (let match = pattern.exec(text); match !== null; match = pattern.exec(text)) {
    boundaries.push({
      index: match.index,
      end: pattern.lastIndex,
      label: match.groups?.label?.trim() || '',
      boundaryOnly: !match.groups?.label,
    });
  }
  return boundaries
    .map((boundary, index) => {
      if (boundary.boundaryOnly) return null;
      const next = boundaries[index + 1];
      return {
        label: boundary.label,
        value: text.slice(boundary.end, next ? next.index : text.length).trim(),
      };
    })
    .filter((entry) => entry && hasText(entry.value));
}

export function handoverLabeledStrings(value, labelPattern) {
  const label = new RegExp(`^(?:${labelPattern})$`, 'i');
  return handoverLabelEntries(value)
    .filter((entry) => label.test(entry.label))
    .map((entry) => entry.value);
}

export function handoverBlockerStrings(value) {
  return handoverLabeledStrings(value, 'Blockers?');
}

export function handoverCommandStrings(value) {
  return handoverLabeledStrings(value, String.raw`Command(?:\s+(?:to\s+run|target))?`);
}

export function handoverNextStrings(value) {
  return handoverLabeledStrings(value, 'Next');
}

export function handoverReadinessStrings(value) {
  return handoverLabeledStrings(value, '(?:Readiness|Ready)');
}

function handoverCommandInvocationTargets(value) {
  const text = String(value || '');
  if (!hasText(text)) return [];
  const targets = [];
  const pattern = /(?:^|[.;\n]\s*)(?:please\s+)?(?:run|execute|invoke|start|use|continue with|handoff to|hand off to)\s+(\/he:[a-z-]+|loop[- ]complete)\b/gi;
  for (let match = pattern.exec(text); match !== null; match = pattern.exec(text)) {
    const target = normalizeTarget(match[1]);
    if (!hasNegatedTargetReference(clauseAround(text, match.index), target)) targets.push(target);
  }
  return targets;
}

export function handoverTargetCommands(value) {
  return unique([
    ...handoverCommandStrings(value).flatMap(targetCommandsFromText),
    ...handoverNextStrings(value).flatMap(targetCommandsFromText),
    ...handoverCommandInvocationTargets(value),
  ]);
}

export function receiptTargetCommands(receipt) {
  return unique([
    ...targetCommandsFromText(receipt?.next),
    ...handoverTargetCommands(receipt?.handoverPrompt),
  ]);
}
