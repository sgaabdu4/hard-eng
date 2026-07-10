import fs from 'node:fs';
import path from 'node:path';
import { createHash } from 'node:crypto';

const coverageStatuses = new Set(['pending', 'complete', 'not_required']);
const sourceKinds = new Set(['brief', 'spec', 'requirements', 'other']);
const itemStatuses = new Set(['covered', 'overridden', 'not_applicable', 'open', 'contradictory', 'non_normative']);
const completeItemStatuses = new Set(['covered', 'overridden', 'not_applicable', 'non_normative']);

function isObject(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

function hasText(value) {
  return typeof value === 'string' && value.trim().length > 0;
}

function textArray(value) {
  return Array.isArray(value) && value.every(hasText);
}

function concreteRef(value) {
  return hasText(value) && /(?:[/\\]|\.[a-z0-9]+)(?:#|:L\d+)/i.test(value);
}

function referenceArray(value) {
  return textArray(value) && value.length > 0 && value.every(concreteRef);
}

function splitLines(text) {
  return text.split(/\r\n|\n|\r/);
}

function sourcePath(entry, options) {
  if (!hasText(entry?.path)) return '';
  return path.isAbsolute(entry.path) ? entry.path : path.resolve(options.root || process.cwd(), entry.path);
}

function isPlanPassHandoff(state) {
  if (state?.stage !== 'he-plan') return false;
  const lastStep = Array.isArray(state.steps) ? state.steps[state.steps.length - 1] : null;
  const receipt = isObject(lastStep?.receipt) ? lastStep.receipt : null;
  if (receipt?.decision !== 'PASS') return false;
  return /ready for \/he:implement:\s*yes\b/i.test(`${receipt.next || ''} ${receipt.handoverPrompt || ''}`);
}

function readinessRequired(state) {
  return state?.next?.ready === true || isPlanPassHandoff(state);
}

function addIssue(issues, message) {
  issues.push(`planReadiness.sourceCoverage ${message}`);
}

export function validateSourceCoverage(state, errors, options = {}) {
  const coverage = state?.planReadiness?.sourceCoverage;
  const strict = readinessRequired(state);
  if (!isObject(coverage)) {
    if (strict) errors.push('planReadiness.sourceCoverage is required before next.ready or a Plan PASS handoff');
    return;
  }

  const structural = [];
  const issues = [];
  if (typeof coverage.required !== 'boolean') structural.push('planReadiness.sourceCoverage.required must be boolean');
  if (!coverageStatuses.has(coverage.status)) structural.push('planReadiness.sourceCoverage.status is invalid');
  if (!Array.isArray(coverage.sources)) structural.push('planReadiness.sourceCoverage.sources must be an array');
  if (!Array.isArray(coverage.items)) structural.push('planReadiness.sourceCoverage.items must be an array');
  if (structural.length) {
    errors.push(...structural);
    return;
  }

  if (coverage.required === false) {
    if (coverage.status !== 'not_required') structural.push('planReadiness.sourceCoverage.status must be not_required when required is false');
    if (coverage.sources.length !== 0) structural.push('planReadiness.sourceCoverage.sources must be empty when required is false');
    if (coverage.items.length !== 0) structural.push('planReadiness.sourceCoverage.items must be empty when required is false');
    if (!hasText(coverage.reason)) structural.push('planReadiness.sourceCoverage.reason is required when no source exists');
    if (!referenceArray(coverage.evidenceRefs)) structural.push('planReadiness.sourceCoverage.evidenceRefs must contain concrete references when no source exists');
    errors.push(...structural);
    return;
  }

  if (coverage.required !== true) {
    errors.push(...structural);
    return;
  }
  if (coverage.status === 'not_required') structural.push('planReadiness.sourceCoverage.status cannot be not_required when required is true');
  if (coverage.sources.length === 0) structural.push('planReadiness.sourceCoverage.sources must include at least one source');

  const sourcesById = new Map();
  const sourceFacts = new Map();
  for (const [index, source] of coverage.sources.entries()) {
    const prefix = `planReadiness.sourceCoverage.sources[${index}]`;
    if (!isObject(source)) {
      structural.push(`${prefix} must be an object`);
      continue;
    }
    if (!hasText(source.id)) structural.push(`${prefix}.id is required`);
    else if (sourcesById.has(source.id)) structural.push(`${prefix}.id must be unique`);
    else sourcesById.set(source.id, source);
    if (!sourceKinds.has(source.kind)) structural.push(`${prefix}.kind is invalid`);
    if (!hasText(source.path)) structural.push(`${prefix}.path is required`);
    if (!hasText(source.revision)) structural.push(`${prefix}.revision is required`);
    if (!/^[a-f0-9]{64}$/i.test(source.sha256 || '')) structural.push(`${prefix}.sha256 must be a SHA-256 digest`);
    if (!Number.isInteger(source.lineCount) || source.lineCount < 1) structural.push(`${prefix}.lineCount must be a positive integer`);
    if (!Number.isInteger(source.nonblankLineCount) || source.nonblankLineCount < 0) structural.push(`${prefix}.nonblankLineCount must be a non-negative integer`);
    const resolvedPath = sourcePath(source, options);
    if (!resolvedPath) continue;
    let content;
    try {
      content = fs.readFileSync(resolvedPath);
    } catch (error) {
      addIssue(issues, `cannot read source ${source.id || index}: ${error.message}`);
      continue;
    }
    const text = content.toString('utf8');
    const lines = splitLines(text);
    const nonblankLines = lines
      .map((line, lineIndex) => ({ line, number: lineIndex + 1 }))
      .filter(({ line }) => line.trim().length > 0)
      .map(({ number }) => number);
    const actualDigest = createHash('sha256').update(content).digest('hex');
    if (source.sha256 !== actualDigest) addIssue(issues, `sha256 mismatch for source ${source.id}; source changed after audit`);
    if (source.lineCount !== lines.length) addIssue(issues, `lineCount mismatch for source ${source.id}: expected ${lines.length}`);
    if (source.nonblankLineCount !== nonblankLines.length) addIssue(issues, `nonblankLineCount mismatch for source ${source.id}: expected ${nonblankLines.length}`);
    sourceFacts.set(source.id, { path: source.path, lines, nonblankLines });
  }

  const itemIds = new Set();
  const coverageBySource = new Map();
  for (const [index, item] of coverage.items.entries()) {
    const prefix = `planReadiness.sourceCoverage.items[${index}]`;
    if (!isObject(item)) {
      structural.push(`${prefix} must be an object`);
      continue;
    }
    if (!hasText(item.id)) structural.push(`${prefix}.id is required`);
    else if (itemIds.has(item.id)) structural.push(`${prefix}.id must be unique`);
    else itemIds.add(item.id);
    if (!hasText(item.sourceId) || !sourcesById.has(item.sourceId)) structural.push(`${prefix}.sourceId must reference a declared source`);
    if (!itemStatuses.has(item.status)) structural.push(`${prefix}.status is invalid`);
    if (!Number.isInteger(item.startLine) || item.startLine < 1) structural.push(`${prefix}.startLine must be a positive integer`);
    if (!Number.isInteger(item.endLine) || item.endLine < item.startLine) structural.push(`${prefix}.endLine must be greater than or equal to startLine`);
    if (!referenceArray(item.planRefs)) addIssue(issues, `items[${index}].planRefs must contain concrete plan references`);
    if (!referenceArray(item.evidenceRefs)) addIssue(issues, `items[${index}].evidenceRefs must contain concrete evidence references`);
    const facts = sourceFacts.get(item.sourceId);
    if (!facts || !Number.isInteger(item.startLine) || !Number.isInteger(item.endLine)) continue;
    if (item.endLine > facts.lines.length) {
      addIssue(issues, `items[${index}] span exceeds source ${item.sourceId} lineCount`);
      continue;
    }
    const expectedRef = `${sourcesById.get(item.sourceId).path}#L${item.startLine}-L${item.endLine}`;
    if (item.sourceRef !== expectedRef) structural.push(`${prefix}.sourceRef must equal ${expectedRef}`);
    const lineCounts = coverageBySource.get(item.sourceId) || new Map();
    for (let line = item.startLine; line <= item.endLine; line += 1) {
      if (facts.lines[line - 1].trim().length === 0) continue;
      lineCounts.set(line, (lineCounts.get(line) || 0) + 1);
    }
    coverageBySource.set(item.sourceId, lineCounts);
    if (!completeItemStatuses.has(item.status)) addIssue(issues, `item ${item.id || index} has blocking status ${item.status}`);
  }

  for (const [sourceId, facts] of sourceFacts.entries()) {
    const lineCounts = coverageBySource.get(sourceId) || new Map();
    const uncovered = facts.nonblankLines.filter((line) => !lineCounts.has(line));
    const overlapped = facts.nonblankLines.filter((line) => (lineCounts.get(line) || 0) > 1);
    if (uncovered.length) addIssue(issues, `has uncovered nonblank lines for source ${sourceId}: ${uncovered.join(',')}`);
    if (overlapped.length) addIssue(issues, `has overlapping spans for source ${sourceId}: ${overlapped.join(',')}`);
  }

  errors.push(...structural);
  if (coverage.status === 'complete' && issues.length) errors.push(...issues);
  if (strict) {
    if (coverage.status !== 'complete') errors.push('planReadiness.sourceCoverage must be complete before next.ready or a Plan PASS handoff');
    if (issues.length && coverage.status !== 'complete') errors.push(...issues);
  }
}
