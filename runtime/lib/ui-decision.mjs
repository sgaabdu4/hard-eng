import fs from 'node:fs';
import path from 'node:path';
import { sha256 } from './canonical.mjs';
import { resolveContainedPath } from './safe-path.mjs';

const requiredStates = ['happy', 'loading', 'empty', 'validation', 'permission', 'error'];
const cadences = new Set(['every-vertical-slice', 'meaningful-milestones', 'final-candidate']);
const explorationPaths = new Set(['existing-system', 'imagegen', 'constrained']);
const privateOrNetworkContent = /(?:\/Users\/|\/home\/|-----BEGIN [A-Z ]*PRIVATE KEY-----|\bsk-[A-Za-z0-9_-]{20,}|https?:\/\/)/;

function field(section, label) {
  const escaped = label.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  return new RegExp(`^\\*\\*${escaped}:\\*\\*\\s*(.+)$`, 'mi').exec(section)?.[1]?.trim() ?? null;
}

function notApplicableWithReason(value) {
  return /^not applicable\s*(?:—|-|:)\s*\S.+/i.test(value ?? '');
}

function safeRunArtifactPath(relative, prefix) {
  return typeof relative === 'string'
    && relative.startsWith(prefix)
    && !relative.includes('\\')
    && !path.isAbsolute(relative)
    && path.posix.normalize(relative) === relative
    && !relative.split('/').includes('..');
}

function verifyArtifact(repo, relative, digest, maxBytes, label) {
  const { target, stat } = resolveContainedPath(repo, relative, { label });
  if (!stat.isFile() || stat.isSymbolicLink() || stat.size > maxBytes) throw new Error(`${label} artifact is invalid or oversized.`);
  if (sha256(fs.readFileSync(target)) !== digest.toLowerCase()) throw new Error(`${label} artifact digest does not match.`);
  return target;
}

function assertRasterImage(target, label) {
  const bytes = fs.readFileSync(target);
  const png = bytes.length >= 8 && bytes.subarray(0, 8).equals(Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]));
  const jpeg = bytes.length >= 3 && bytes[0] === 0xff && bytes[1] === 0xd8 && bytes[2] === 0xff;
  if (!png && !jpeg) throw new Error(`${label} must be a PNG or JPEG image.`);
}

function validateBaseline(repo, runId, value) {
  if (notApplicableWithReason(value)) return { applicable: false, reason: value };
  const match = /^(.+?)\s+@\s+([a-f0-9]{64})$/i.exec(value ?? '');
  const prefix = `.hard-eng/baselines/${runId}/`;
  if (!match || !safeRunArtifactPath(match[1].trim(), prefix) || !match[1].trim().endsWith('.json')) {
    throw new Error('UI baseline must reference a run-owned metadata JSON digest or give a not-applicable reason.');
  }
  const relative = match[1].trim();
  if (!repo) return { applicable: true, path: relative, digest: match[2].toLowerCase() };
  const metadataTarget = verifyArtifact(repo, relative, match[2], 256 * 1024, 'UI baseline metadata');
  const metadata = JSON.parse(fs.readFileSync(metadataTarget, 'utf8'));
  for (const fieldName of ['commit_or_tree', 'route', 'role', 'seed_state', 'viewport_or_device', 'environment', 'screenshots']) {
    if (metadata[fieldName] === undefined || metadata[fieldName] === null || metadata[fieldName] === '') {
      throw new Error(`UI baseline metadata is missing ${fieldName}.`);
    }
  }
  if (!/^[a-f0-9]{40,64}$/i.test(metadata.commit_or_tree) || !Array.isArray(metadata.screenshots) || metadata.screenshots.length === 0) {
    throw new Error('UI baseline metadata has invalid commit/tree or screenshots.');
  }
  if (privateOrNetworkContent.test(JSON.stringify(metadata))) throw new Error('UI baseline metadata contains private, secret-like, or network content.');
  for (const screenshot of metadata.screenshots) {
    if (!safeRunArtifactPath(screenshot.path, prefix) || !/^[a-f0-9]{64}$/i.test(screenshot.digest ?? '')) {
      throw new Error('UI baseline screenshot receipt is invalid.');
    }
    const screenshotTarget = verifyArtifact(repo, screenshot.path, screenshot.digest, 10 * 1024 * 1024, 'UI baseline screenshot');
    assertRasterImage(screenshotTarget, 'UI baseline screenshot');
  }
  return { applicable: true, path: relative, digest: match[2].toLowerCase(), metadata_digest: sha256(JSON.stringify(metadata)) };
}

function validatePrototype(repo, runId, value) {
  const match = /^(.+?)\s+@\s+([a-f0-9]{64})$/i.exec(value ?? '');
  if (!match) throw new Error('UI prototype must be a relative path plus SHA-256 digest.');
  const relative = match[1].trim();
  const expectedPrefix = `.hard-eng/prototypes/${runId}/`;
  if (!safeRunArtifactPath(relative, expectedPrefix)) {
    throw new Error('UI prototype must be run-owned under .hard-eng/prototypes/<run-id>/.');
  }
  if (!repo) return { path: relative, digest: match[2].toLowerCase() };
  const { target, stat } = resolveContainedPath(repo, relative, { label: 'UI prototype' });
  if (!stat.isFile() || stat.isSymbolicLink() || stat.size > 2 * 1024 * 1024) {
    throw new Error('UI prototype must be a regular file no larger than 2 MiB.');
  }
  const content = fs.readFileSync(target);
  if (sha256(content) !== match[2].toLowerCase()) throw new Error('UI prototype digest does not match the artifact.');
  const text = content.toString('utf8');
  if (!/<html[\s>]/i.test(text) || !/<(?:button|input|select|textarea|a)[\s>]/i.test(text)) {
    throw new Error('UI prototype must be coded and interactive.');
  }
  if (!/data-hard-eng-prototype=["']interactive["']/i.test(text) || !/data-mock=["']realistic-sanitized["']/i.test(text)) {
    throw new Error('UI prototype must declare interactive flow and realistic sanitized mock data.');
  }
  if (privateOrNetworkContent.test(text)) throw new Error('UI prototype contains private, secret-like, or network content.');
  for (const state of requiredStates) {
    if (!new RegExp(`\\b${state}\\b`, 'i').test(text)) throw new Error(`UI prototype is missing the ${state} state.`);
  }
  return { path: relative, digest: match[2].toLowerCase(), size: stat.size };
}

function validateDirectionBoards(repo, runId, value) {
  const prefix = `.hard-eng/directions/${runId}/`;
  const boards = String(value ?? '').split(';').map((entry) => entry.trim()).filter(Boolean).map((entry) => {
    const match = /^(.+?)\s+@\s+([a-f0-9]{64})$/i.exec(entry);
    if (!match || !safeRunArtifactPath(match[1].trim(), prefix)) throw new Error('Imagegen direction-board receipt is invalid.');
    return { path: match[1].trim(), digest: match[2].toLowerCase() };
  });
  if (boards.length < 2 || boards.length > 3) throw new Error('Imagegen exploration requires two or three direction boards.');
  if (
    new Set(boards.map((board) => board.path)).size !== boards.length
    || new Set(boards.map((board) => board.digest)).size !== boards.length
  ) throw new Error('Imagegen direction boards must be distinct artifacts.');
  if (repo) {
    for (const board of boards) {
      const boardTarget = verifyArtifact(repo, board.path, board.digest, 10 * 1024 * 1024, 'Imagegen direction board');
      assertRasterImage(boardTarget, 'Imagegen direction board');
    }
  }
  return boards;
}

export function validateUiDecision(section, { repo = null, runId } = {}) {
  const applicability = field(section, 'UI applicability');
  if (!applicability) throw new Error('UI applicability is missing.');
  if (/^not applicable/i.test(applicability)) {
    if (!notApplicableWithReason(applicability)) throw new Error('UI not-applicable decision requires a reason.');
    return { applicable: false, reason: applicability };
  }
  if (applicability.toLowerCase() !== 'applicable') throw new Error('UI applicability must be applicable or not applicable with a reason.');

  const baseline = field(section, 'Baseline');
  if (!baseline || (/^not applicable/i.test(baseline) && !notApplicableWithReason(baseline))) {
    throw new Error('UI baseline or a justified greenfield baseline is required.');
  }
  const baselineReceipt = validateBaseline(repo, runId, baseline);
  const designOwner = field(section, 'Design owner');
  if (!designOwner || privateOrNetworkContent.test(designOwner)) throw new Error('UI design owner is missing or unsafe.');
  const exploration = field(section, 'Exploration path');
  if (!explorationPaths.has(exploration)) throw new Error('UI exploration path is invalid.');
  const prototype = validatePrototype(repo, runId, field(section, 'Prototype'));
  const direction = field(section, 'Approved direction');
  if (!direction || !/user-approved/i.test(direction)) throw new Error('UI direction requires explicit user approval.');
  const states = (field(section, 'Mock states') ?? '').split(',').map((value) => value.trim().toLowerCase());
  for (const state of requiredStates) if (!states.includes(state)) throw new Error(`UI mock-state receipt is missing ${state}.`);
  const cadence = field(section, 'Review cadence');
  if (!cadences.has(cadence)) throw new Error('UI review cadence is invalid.');
  const codedOptions = field(section, 'Coded options');
  if (!codedOptions) throw new Error('UI coded-option disposition is required.');
  let directionBoards = [];
  if (exploration === 'imagegen') {
    if (!/^approved\s*:\s*[23]\s+calls?$/i.test(field(section, 'Imagegen budget') ?? '')) {
      throw new Error('Imagegen exploration requires an approved two- or three-call budget.');
    }
    const brief = field(section, 'Visual brief');
    if (!brief || brief.length > 1_000 || privateOrNetworkContent.test(brief)) throw new Error('Imagegen exploration requires a bounded sanitized visual brief.');
    directionBoards = validateDirectionBoards(repo, runId, field(section, 'Direction boards'));
    if (!field(section, 'Rejected directions')) throw new Error('Imagegen rejected-direction decisions are required.');
  }
  return { applicable: true, baseline: baselineReceipt, design_owner: designOwner, exploration, prototype, direction, direction_boards: directionBoards, states, cadence, coded_options: codedOptions };
}
