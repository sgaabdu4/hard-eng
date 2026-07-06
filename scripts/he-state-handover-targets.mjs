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
  return normalizeText(normalizeTarget(value));
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

function clausePrefix(text, index) {
  const before = text.slice(0, index);
  const start = Math.max(before.lastIndexOf('.'), before.lastIndexOf(';'), before.lastIndexOf('\n')) + 1;
  return text.slice(start, index);
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

const blockerLabelSource = String.raw`Blockers?|Blocked(?:\s+(?:by|on))?|Blocking(?:\s+on)?`;
const readinessTargetSource = String.raw`(?:\/he:[a-z-]+|implementation|implement)`;
const readinessLabelSource = String.raw`(?:Implementation|Implement)\s+ready(?:\s+for\s+${readinessTargetSource})?|Readiness(?:\s+for\s+${readinessTargetSource})?|Ready(?:\s+for\s+${readinessTargetSource})?`;
const readStateInstructionSource = String.raw`Read\b[^.;\n]{0,120}\b(?:he-state\.json|state(?:\.json)?)\b(?:[^.;\n]{0,40}\bfirst\b)?`;
const handoverLabelSource = String.raw`Artifacts? ready|Artifacts? readiness|Owner\/proof|Owner proof|Handover prompt|Command(?:\s+(?:to\s+run|target))?|${blockerLabelSource}|Artifacts?|${readinessLabelSource}|Stage|State|Decision|Next|Worktree`;

function isGenericReadinessLabel(label) {
  return /^(?:ready|readiness)$/i.test(label);
}

function shouldSkipSoftReadinessSuffix(text, labelStart, label, boundary) {
  if (!isGenericReadinessLabel(label) || boundary.length === 0 || /[.;\n]/.test(boundary)) return false;
  const token = text.slice(0, labelStart).match(/(\S+)\s*$/)?.[1] || '';
  if (!/^[A-Za-z]+$/.test(token)) return false;
  return !['pass', 'concerns', 'fail', 'yes', 'no', 'true', 'false'].includes(normalizeText(token));
}

function handoverLabelEntries(value) {
  const text = String(value || '');
  if (!hasText(text)) return [];
  const boundaries = [];
  const pattern = new RegExp(`(?<boundary>^|[.;\\n]\\s*|(?<![:\\s])\\s+)(?:(?<label>${handoverLabelSource})\\s*:|(?<read>${readStateInstructionSource}))`, 'gi');
  for (let match = pattern.exec(text); match !== null; match = pattern.exec(text)) {
    const boundary = match.groups?.boundary || '';
    const label = match.groups?.label?.trim() || '';
    const labelStart = match.index + boundary.length;
    if (label && shouldSkipSoftReadinessSuffix(text, labelStart, label, boundary)) continue;
    boundaries.push({
      index: match.index,
      end: pattern.lastIndex,
      label,
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
  return handoverLabeledStrings(value, blockerLabelSource);
}

export function handoverCommandStrings(value) {
  return handoverLabeledStrings(value, String.raw`Command(?:\s+(?:to\s+run|target))?`);
}

export function handoverNextStrings(value) {
  return handoverLabeledStrings(value, 'Next');
}

export function handoverReadinessStrings(value) {
  return handoverLabeledStrings(value, readinessLabelSource);
}

const commandLeadInSource = String.raw`(?:then|next|also|afterwards?|after that|and then)`;
const commandVerbSource = String.raw`(?:run|execute|invoke|start|use|continue\s+with|handoff\s+to|hand\s+off\s+to)`;

function hasPositiveCommandPrefix(value) {
  const normalized = normalizeText(value);
  return new RegExp(`(?:^|\\b)(?:${commandLeadInSource}\\s+)?(?:please\\s+)?${commandVerbSource}\\s*$`).test(normalized);
}

function handoverCommandInvocationTargets(value) {
  const text = String(value || '');
  if (!hasText(text)) return [];
  const targets = [];
  const pattern = /\/he:[a-z-]+|loop[- ]complete/gi;
  for (let match = pattern.exec(text); match !== null; match = pattern.exec(text)) {
    const target = normalizeTarget(match[0]);
    const clause = clauseAround(text, match.index);
    if (hasPositiveCommandPrefix(clausePrefix(text, match.index)) && !hasNegatedTargetReference(clause, target)) targets.push(target);
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
