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

const touchedStackAliases = new Map([
  ['js', ['javascript']],
  ['mjs', ['js', 'javascript']],
  ['cjs', ['js', 'javascript']],
  ['jsx', ['js', 'javascript', 'react']],
  ['ts', ['typescript']],
  ['mts', ['ts', 'typescript']],
  ['cts', ['ts', 'typescript']],
  ['tsx', ['ts', 'typescript', 'react']],
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
    const text = stack.toLowerCase();
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

function validateTouchedStackInventory(inventory, entries, errors, readinessRequiresInventory) {
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
  const ssotSensitive = /\b(ui|component|widget|screen|form|picker|calendar|date-grid|select|settings-row|api|schema|repository|query|cache|backend)\b/i.test(touchedText);
  const jsTsTouched = /\b(js|javascript|ts|typescript|tsx|jsx|react|next)\b/i.test(touchedText);
  const nonJsCodeTouched = /\b(flutter|dart|swift|kotlin|java|python|go|rust|backend|api|schema)\b/i.test(touchedText) && !jsTsTouched;

  if (ssotSensitive && ssot?.status === 'not_applicable') {
    const evidence = `${ssot.reason || ''} ${words(ssot.evidence)}`;
    const hasOwnerEvidence = hasAnyPattern(evidence, [
      /component[- ]?pattern|interaction[- ]?pattern|shared widget|shared component|similar (screen|row|card|form|picker|calendar)|owner ledger/i,
      /api owner|schema owner|repository owner|query owner|cache owner|permission owner/i,
    ]);
    if (!hasOwnerEvidence) {
      errors.push('ssot-scanners cannot be not_applicable for UI/component/API/schema touched stacks without explicit owner or component-pattern search evidence');
    }
  }

  if (jsTsTouched && fallow?.status === 'not_applicable') {
    errors.push('fallow cannot be not_applicable for JS/TS/React/Next touched stacks; record Fallow duplicate/clone evidence as a required guardrail');
  }
  if (nonJsCodeTouched && fallow?.status === 'not_applicable') {
    const evidence = `${fallow.reason || ''} ${words(fallow.evidence)}`;
    if (!/no .*duplicate|no .*clone|tool unavailable|no stack-specific/i.test(evidence) || !/\b(rg|static search|duplicate search|clone search)\b/i.test(evidence)) {
      errors.push('fallow not_applicable for non-JS/TS stacks requires stack-specific tool absence reason plus static-search duplicate/clone evidence');
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
  validateTouchedStackInventory(inventory, entries, errors, readinessRequiresInventory);

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
