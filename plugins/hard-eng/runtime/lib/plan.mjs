import fs from 'node:fs';
import path from 'node:path';
import { sha256 } from './canonical.mjs';
import { validateUiDecision } from './ui-decision.mjs';

export const PLAN_HEADINGS = [
  'Outcome and success measures',
  'Scope and non-goals',
  'Evidence and constraints',
  'Decisions and rejected alternatives',
  'Actors and end-to-end journeys',
  'UI/design contract and approved prototype reference, when applicable',
  'Data/API/security/migration/observability contract',
  'Vertical implementation slices with owners and dependencies',
  'Acceptance and proof matrix',
  'Adversarial findings and dispositions',
  'Rollout, rollback, and open blockers',
];

const headerPattern = /^<!-- hard-eng:plan\/v1 run=([a-zA-Z0-9][a-zA-Z0-9._-]{2,80}) accepted-digest=(pending|[a-f0-9]{64}) -->$/;
const readinessStatuses = new Set(['resolved', 'evidence-backed inference', 'not applicable', 'open']);
const dispositions = new Set(['resolve', 'accept', 'out-of-scope']);
const readinessLabels = [
  'user/problem/value/success',
  'actors/permissions/trust/accessibility',
  'scope/non-goals/compatibility/rollout',
  'journeys/states/recovery',
  'information-architecture/visual/responsive/copy/interaction',
  'data/validation/privacy/retention/cache/migration',
  'API/events/timeouts/idempotency/concurrency/offline',
  'ownership/reuse/dependencies/deletion',
  'observability/support/performance/security/abuse',
  'tests/E2E/proof/release/rollback/completion',
];
const adversarialLabels = [
  'problem/scope', 'trust/people', 'journey failure', 'state/data',
  'architecture/operations', 'interface', 'delivery', 'false proof',
];

function normalize(text) {
  return String(text).replace(/\r\n?/g, '\n').trimEnd() + '\n';
}

export function inspectPlanOwnership(text) {
  const match = headerPattern.exec(normalize(text).split('\n')[0]);
  return match
    ? { status: 'hard-eng', run_id: match[1], accepted_digest: match[2] }
    : { status: 'foreign' };
}

export function computePlanDigest(text) {
  const normalized = normalize(text).replace(/accepted-digest=(?:pending|[a-f0-9]{64})/, 'accepted-digest=pending');
  return sha256(normalized);
}

function tableCells(line) {
  const trimmed = line.trim();
  if (!trimmed.startsWith('|') || !trimmed.endsWith('|')) return null;
  return trimmed.slice(1, -1).split('|').map((cell) => cell.trim());
}

function parseSections(text) {
  const lines = normalize(text).split('\n');
  const numbered = [];
  lines.forEach((line, index) => {
    const match = /^##\s+(\d+)\.\s+(.+)$/.exec(line);
    if (match) numbered.push({ number: Number(match[1]), heading: match[2], index });
  });
  if (numbered.length !== PLAN_HEADINGS.length) throw new Error('plan.md must contain exactly the 11 canonical sections.');
  const sections = {};
  for (let offset = 0; offset < PLAN_HEADINGS.length; offset += 1) {
    const found = numbered[offset];
    if (found.number !== offset + 1 || found.heading !== PLAN_HEADINGS[offset]) {
      throw new Error(`plan.md section ${offset + 1} must be “${PLAN_HEADINGS[offset]}”.`);
    }
    const end = numbered[offset + 1]?.index ?? lines.length - 1;
    const body = lines.slice(found.index, end).join('\n').trimEnd();
    sections[offset + 1] = { heading: found.heading, line: found.index + 1, digest: sha256(body), text: body };
  }
  return sections;
}

function parseReadiness(section) {
  const rows = new Map();
  for (const line of section.split('\n')) {
    const cells = tableCells(line);
    const match = /^(D(?:10|[1-9]))\b/.exec(cells?.[0] ?? '');
    if (!match) continue;
    if (rows.has(match[1])) throw new Error(`Duplicate readiness domain ${match[1]}.`);
    const expectedLabel = `${match[1]} ${readinessLabels[Number(match[1].slice(1)) - 1]}`;
    if (cells[0] !== expectedLabel) throw new Error(`Readiness domain ${match[1]} label must be “${expectedLabel}”.`);
    const status = cells[1]?.toLowerCase();
    if (!readinessStatuses.has(status)) throw new Error(`Readiness domain ${match[1]} has invalid status.`);
    if (!cells[2] || /^(?:tbd|none)$/i.test(cells[2])) throw new Error(`Readiness domain ${match[1]} lacks evidence.`);
    rows.set(match[1], { status, evidence: cells[2] });
  }
  const missing = Array.from({ length: 10 }, (_, index) => `D${index + 1}`).filter((id) => !rows.has(id));
  if (missing.length) throw new Error(`Readiness ledger is missing ${missing.join(', ')}.`);
  const open = [...rows].filter(([, value]) => value.status === 'open').map(([id]) => id);
  if (open.length) throw new Error(`Plan has open readiness domains: ${open.join(', ')}.`);
  return { rows, open };
}

function parseAcceptance(section) {
  const rows = new Map();
  for (const line of section.split('\n')) {
    const cells = tableCells(line);
    if (!/^P\d+$/.test(cells?.[0] ?? '')) continue;
    if (cells.length < 4 || cells.slice(1, 4).some((cell) => !cell || /^tbd$/i.test(cell))) {
      throw new Error(`Acceptance proof ${cells[0]} is incomplete.`);
    }
    if (rows.has(cells[0])) throw new Error(`Duplicate acceptance proof ${cells[0]}.`);
    rows.set(cells[0], { id: cells[0], acceptance: cells[1], owner: cells[2], proof: cells[3], line });
  }
  if (!rows.size) throw new Error('Acceptance and proof matrix is empty.');
  return rows;
}

function parseSlices(section, acceptance) {
  const rows = new Map();
  for (const line of section.split('\n')) {
    const cells = tableCells(line);
    if (!/^S\d+$/.test(cells?.[0] ?? '')) continue;
    if (cells.length < 5 || cells.slice(1, 5).some((cell) => !cell)) throw new Error(`Slice ${cells[0]} is incomplete.`);
    const proofIds = cells[4].match(/P\d+/g) ?? [];
    if (!proofIds.length || proofIds.some((id) => !acceptance.has(id))) throw new Error(`Slice ${cells[0]} has an invalid proof mapping.`);
    if (rows.has(cells[0])) throw new Error(`Duplicate slice ${cells[0]}.`);
    rows.set(cells[0], { id: cells[0], outcome: cells[1], owner: cells[2], depends_on: cells[3], proof_ids: proofIds, line });
  }
  if (!rows.size) throw new Error('Vertical slice matrix is empty.');
  const ids = [...rows.keys()];
  for (let index = 0; index < ids.length; index += 1) {
    const expected = `S${index + 1}`;
    if (ids[index] !== expected) throw new Error(`Slice IDs must be contiguous and ordered; expected ${expected}.`);
  }
  for (const [id, row] of rows) {
    if (row.depends_on.toLowerCase() === 'none') continue;
    const dependencies = row.depends_on.match(/S\d+/g) ?? [];
    if (!dependencies.length) throw new Error(`Slice ${id} dependency declaration is invalid.`);
    const number = Number(id.slice(1));
    for (const dependency of dependencies) {
      if (!rows.has(dependency) || Number(dependency.slice(1)) >= number) {
        throw new Error(`Slice ${id} dependency ${dependency} must name an earlier slice.`);
      }
    }
  }
  return rows;
}

function parseAdversarial(section) {
  const rows = new Map();
  for (const line of section.split('\n')) {
    const cells = tableCells(line);
    const match = /^(A[1-8])\b/.exec(cells?.[0] ?? '');
    if (!match) continue;
    const expectedLabel = `${match[1]} ${adversarialLabels[Number(match[1].slice(1)) - 1]}`;
    if (cells[0] !== expectedLabel) throw new Error(`Adversarial category ${match[1]} label must be “${expectedLabel}”.`);
    if (cells.length < 6 || cells.slice(1, 6).some((cell) => !cell || /^none$/i.test(cell))) {
      throw new Error(`Adversarial category ${match[1]} lacks a concrete challenge/outcome.`);
    }
    const disposition = cells[3].toLowerCase();
    if (!dispositions.has(disposition)) throw new Error(`Adversarial category ${match[1]} has invalid disposition.`);
    if (disposition === 'accept' && !/user-approved/i.test(cells[5])) {
      throw new Error(`Adversarial category ${match[1]} acceptance requires user-approved rationale.`);
    }
    if (rows.has(match[1])) throw new Error(`Duplicate adversarial category ${match[1]}.`);
    rows.set(match[1], { disposition, line });
  }
  const missing = Array.from({ length: 8 }, (_, index) => `A${index + 1}`).filter((id) => !rows.has(id));
  if (missing.length) throw new Error(`Adversarial coverage is missing ${missing.join(', ')}.`);
  return rows;
}

function planDetails(text, options) {
  const normalized = normalize(text);
  const lines = normalized.split('\n');
  if (!/^# Plan:\s+\S/.test(lines[1] ?? '') || lines.filter((line) => /^#\s+/.test(line)).length !== 1) {
    throw new Error('plan.md must have exactly one “# Plan: <title>” heading immediately after its owner header.');
  }
  const ownership = inspectPlanOwnership(normalized);
  if (ownership.status !== 'hard-eng') throw new Error('plan.md is owned by the user or another system; explicit adoption is required.');
  if (ownership.run_id !== options.runId) throw new Error('plan.md Hard Eng run ID does not match the bound run.');
  const sections = parseSections(normalized);
  const readiness = parseReadiness(sections[3].text);
  const acceptance = parseAcceptance(sections[9].text);
  const slices = parseSlices(sections[8].text, acceptance);
  const adversarial = parseAdversarial(sections[10].text);
  const blockers = /^\*\*Open blockers:\*\*\s*(.+)$/mi.exec(sections[11].text)?.[1]?.trim();
  if (!blockers || blockers.toLowerCase() !== 'none') throw new Error('Plan has open blockers or lacks the blocker declaration.');
  const ui = validateUiDecision(sections[6].text, { repo: options.repo, runId: options.runId });
  const digest = computePlanDigest(normalized);
  if (ownership.accepted_digest !== 'pending' && ownership.accepted_digest !== digest) {
    throw new Error('Accepted plan digest does not match plan.md; Plan reconciliation is required.');
  }
  if (options.requireAccepted && ownership.accepted_digest === 'pending') throw new Error('Plan has not recorded its accepted digest.');
  return { normalized, ownership, sections, readiness, acceptance, slices, adversarial, blockers, ui, digest };
}

export function validatePlanText(text, { runId, requireAccepted = false, repo = null } = {}) {
  const details = planDetails(text, { runId, requireAccepted, repo });
  const estimatedTokens = Math.ceil(details.normalized.length / 4);
  return {
    status: 'PASS',
    run_id: runId,
    digest: details.digest,
    accepted_digest: details.ownership.accepted_digest,
    sections: Object.fromEntries(Object.entries(details.sections).map(([id, section]) => [id, {
      heading: section.heading, line: section.line, digest: section.digest,
    }])),
    open_domains: details.readiness.open,
    acceptance_ids: [...details.acceptance.keys()],
    slice_ids: [...details.slices.keys()],
    adversarial_categories: [...details.adversarial.keys()],
    ui: details.ui,
    estimated_tokens: estimatedTokens,
    warning: estimatedTokens > 12_000 ? 'plan.md exceeds the 12,000-token warning threshold' : null,
  };
}

export function validatePlanFile(repo, { runId, requireAccepted = false } = {}) {
  const file = path.join(repo, 'plan.md');
  const stat = fs.lstatSync(file);
  if (!stat.isFile() || stat.isSymbolicLink()) throw new Error('Repository-root plan.md must be a regular owned file.');
  if (stat.size > 2 * 1024 * 1024) throw new Error('plan.md exceeds the 2 MiB safety limit.');
  return validatePlanText(fs.readFileSync(file, 'utf8'), { runId, requireAccepted, repo });
}

export function renderPlanExcerpt(text, { runId, sliceId }) {
  const details = planDetails(text, { runId, requireAccepted: false, repo: null });
  const slice = details.slices.get(sliceId);
  if (!slice) throw new Error(`Plan slice not found: ${sliceId}.`);
  const proofRows = slice.proof_ids.map((id) => details.acceptance.get(id).line);
  const digestLines = [1, 2, 3, 4, 7, 8, 9].map((id) => `§${id} ${details.sections[id].digest.slice(0, 12)}`).join(', ');
  const excerpt = [
    `# Hard Eng plan excerpt — ${details.ownership.run_id}`,
    `plan-digest: ${details.digest}`,
    `section-digests: ${digestLines}`,
    '',
    details.sections[1].text,
    '',
    details.sections[2].text,
    '',
    details.sections[3].text,
    '',
    details.sections[4].text,
    '',
    details.sections[7].text,
    '',
    '## Current vertical slice',
    slice.line,
    '',
    '## Acceptance and proof',
    ...proofRows,
  ].join('\n');
  if (excerpt.length >= 4_800) throw new Error('Current Plan excerpt exceeds the 1,200-token target budget.');
  return excerpt;
}
