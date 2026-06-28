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
