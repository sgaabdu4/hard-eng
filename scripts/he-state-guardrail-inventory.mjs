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
    /\btool unavailable\b/i,
    /\bno stack-specific\b/i,
    /\b(?:fallow|clone detector|duplicate detector)\b.*\b(?:unavailable|unsupported|not supported|not applicable)\b/i,
  ]);
}

function hasStaticDuplicateSearchEvidence(evidence) {
  return /\b(rg|ripgrep|static search|duplicate search|clone search)\b/i.test(evidence);
}

function hasNoDuplicateCloneProof(evidence) {
  return hasAnyPattern(evidence, [
    /\bfound no(?:\s+\w+){0,5}\s+(?:duplicates?|clones?|clone groups?|duplicate groups?)\b/i,
    /\bfound\s+(?:zero|none|0)(?:\s+\w+){0,5}\s+(?:duplicates?|clones?|clone groups?|duplicate groups?)\b/i,
    /\b(?:no|zero|without|none|absent|clean|0)(?:\s+\w+){0,5}\s+(?:duplicates?|clones?|clone groups?|duplicate groups?)\b/i,
    /\b(?:duplicates?|clones?|clone groups?|duplicate groups?)(?:\s+\w+){0,5}\s+(?:none|absent|clean|not found|zero|0)\b/i,
  ]);
}

function hasFoundDuplicateCloneEvidence(evidence) {
  const foundPatterns = [
    /\bfound\s+(?!(?:no|zero|none|0)\b)(?:\w+\s+){0,5}(?:duplicates?|clones?|clone groups?|duplicate groups?)\b/i,
    /\b(?:detected|identified|reported)(?:\s+\w+){0,5}\s+(?:duplicates?|clones?|clone groups?|duplicate groups?)\b/i,
    /\b(?:duplicates?|clones?|clone groups?|duplicate groups?)\s+(?:were\s+)?(?:found(?!\s+(?:no|zero|none|0)\b)|detected|identified|reported)\b/i,
  ];
  return String(evidence)
    .split(/[;,\n|]+/)
    .map((part) => part.trim())
    .filter(Boolean)
    .some((part) => !hasNoDuplicateCloneProof(part) && hasAnyPattern(part, foundPatterns));
}

function hasActiveDuplicateCloneDecision(state, entries) {
  return entries.some((entry) => {
    if (!isObject(entry) || entry.status !== 'required') return false;
    const evidence = entryEvidenceText(state, entry);
    return hasAnyPattern(evidence, [
      /\b(?:duplicates?|clones?|clone groups?|duplicate groups?)\b.*\b(?:owner|decision|ledger|resolved|recorded|guardrail|ssot)\b/i,
      /\b(?:owner|decision|ledger|resolved|recorded|guardrail|ssot)\b.*\b(?:duplicates?|clones?|clone groups?|duplicate groups?)\b/i,
    ]);
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
  ['jsx', ['js', 'javascript', 'react']],
  ['ts', ['typescript']],
  ['mts', ['ts', 'typescript']],
  ['cts', ['ts', 'typescript']],
  ['tsx', ['ts', 'typescript', 'react']],
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
  const ssotSensitive = /\b(ui|component|widget|screen|list|row|card|modal|form|picker|tab|navigation|cta|empty|loading|error|calendar|date|grid|month|select|single|multi|checkbox|toggle|selectable|chip|settings|answer|alert|control|drag|drop|search|filter|pagination|upload|stepper|api|schema|repository|query|cache|backend|permission|constant|fixture|helper|design|token|theme|typography|spacing|color|radius|motion|time|currency|number|formatting)\b/i.test(touchedText);
  const jsTsTouched = /\b(js|javascript|ts|typescript|tsx|jsx|react|next)\b/i.test(touchedText);
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

  if (jsTsTouched && fallow?.status === 'not_applicable') {
    errors.push('fallow cannot be not_applicable for JS/TS/React/Next touched stacks; record Fallow duplicate/clone evidence as a required guardrail');
  }
  if (nonJsCodeTouched && fallow?.status === 'not_applicable') {
    const evidence = entryEvidenceText(state, fallow);
    if (!hasAcceptedNonJsCloneFallback(state, entries, evidence, true)) {
      errors.push('fallow not_applicable for non-JS/TS stacks requires stack-specific tool absence plus explicit no-duplicate/no-clone static-search proof or an active guardrail/SSOT clone decision');
    }
  }
  if (jsTsTouched && nonJsLanguageTouched && fallow?.status === 'required') {
    const evidence = entryEvidenceText(state, fallow);
    if (!hasAcceptedNonJsCloneFallback(state, entries, evidence, false)) {
      errors.push('mixed JS/TS and non-JS stacks require Fallow JS/TS evidence plus explicit non-JS no-duplicate/no-clone static-search proof or an active guardrail/SSOT clone decision');
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
    if (!stringArray(entry.evidence) || entry.evidence.length === 0) {
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
