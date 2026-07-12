import fs from 'node:fs';
import path from 'node:path';
import { digestValue, sha256 } from './canonical.mjs';
import { resolveContainedPath } from './safe-path.mjs';

const artifactKinds = new Set(['screenshot', 'video']);
const scenarioFields = ['role', 'data_fixture', 'route', 'viewport_or_device', 'environment'];

function assertDigest(value, label) {
  if (!/^[a-f0-9]{64}$/i.test(value ?? '')) throw new Error(`${label} must be a SHA-256 digest.`);
}

function boundedText(value, label, limit = 240) {
  if (typeof value !== 'string' || !value.trim() || value.length > limit) throw new Error(`${label} is required and must be bounded.`);
}

function validateArtifacts(artifacts, { runId, label, repo = null }) {
  if (!Array.isArray(artifacts) || artifacts.length === 0 || artifacts.length > 12) {
    throw new Error(`${label} artifacts must contain one to twelve entries.`);
  }
  const prefix = `.hard-eng/evidence/${runId}/`;
  return artifacts.map((artifact) => {
    if (!artifact || !artifactKinds.has(artifact.kind)) throw new Error(`${label} artifact kind is invalid.`);
    if (
      typeof artifact.path !== 'string'
      || !artifact.path.startsWith(prefix)
      || path.posix.normalize(artifact.path) !== artifact.path
      || artifact.path.split('/').includes('..')
    ) throw new Error(`${label} artifact path must be run-owned under ${prefix}.`);
    assertDigest(artifact.digest, `${label} artifact digest`);
    if (repo) {
      const { target, stat } = resolveContainedPath(repo, artifact.path, { label: `${label} artifact` });
      const maxBytes = artifact.kind === 'video' ? 50 * 1024 * 1024 : 10 * 1024 * 1024;
      if (!stat.isFile() || stat.isSymbolicLink() || stat.size > maxBytes) throw new Error(`${label} artifact is invalid or oversized.`);
      const bytes = fs.readFileSync(target);
      if (sha256(bytes) !== artifact.digest.toLowerCase()) throw new Error(`${label} artifact digest does not match.`);
      if (artifact.kind === 'screenshot') {
        const png = bytes.length >= 8 && bytes.subarray(0, 8).equals(Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]));
        const jpeg = bytes.length >= 3 && bytes[0] === 0xff && bytes[1] === 0xd8 && bytes[2] === 0xff;
        if (!png && !jpeg) throw new Error(`${label} screenshot must be PNG or JPEG.`);
      } else {
        const mp4 = bytes.length >= 8 && bytes.subarray(4, 8).toString('ascii') === 'ftyp';
        const webm = bytes.length >= 4 && bytes.subarray(0, 4).equals(Buffer.from([0x1a, 0x45, 0xdf, 0xa3]));
        if (!mp4 && !webm) throw new Error(`${label} video must be MP4 or WebM.`);
      }
    }
    return { kind: artifact.kind, path: artifact.path, digest: artifact.digest };
  });
}

export function validateVisualEvidence(pack, {
  runId,
  final = pack?.kind === 'final',
  videoExpected = false,
  candidateFingerprint = null,
  repo = null,
} = {}) {
  if (!pack || typeof pack !== 'object' || Array.isArray(pack)) throw new Error('Visual evidence pack is required.');
  if (!/^[a-zA-Z0-9][a-zA-Z0-9._-]{2,80}$/.test(runId ?? '')) throw new Error('Visual evidence run ID is invalid.');
  if (!['milestone', 'final'].includes(pack.kind)) throw new Error('Visual evidence kind is invalid.');
  if (final && pack.kind !== 'final') throw new Error('Final candidate requires final visual evidence.');
  if (pack.applicability !== 'applicable') throw new Error('Visual evidence pack applicability must be applicable.');
  assertDigest(pack.candidate_fingerprint, 'Visual evidence candidate fingerprint');
  if (candidateFingerprint && pack.candidate_fingerprint !== candidateFingerprint) {
    throw new Error('Visual evidence candidate fingerprint is stale.');
  }
  assertDigest(pack.approved_direction_digest, 'Approved direction digest');
  if (!pack.scenario || typeof pack.scenario !== 'object') throw new Error('Comparable visual scenario is required.');
  scenarioFields.forEach((field) => boundedText(pack.scenario[field], `Visual scenario ${field}`));

  if (!pack.baseline || !['captured', 'not-applicable'].includes(pack.baseline.status)) {
    throw new Error('Visual baseline status is required.');
  }
  let baselineArtifacts = [];
  if (pack.baseline.status === 'captured') {
    baselineArtifacts = validateArtifacts(pack.baseline.artifacts, { runId, label: 'Baseline', repo });
    if (!baselineArtifacts.some((artifact) => artifact.kind === 'screenshot')) {
      throw new Error('Baseline requires at least one screenshot.');
    }
  } else {
    boundedText(pack.baseline.reason, 'Baseline not-applicable reason');
  }

  const implementationArtifacts = validateArtifacts(pack.implementation?.artifacts, { runId, label: 'Implementation', repo });
  if (!implementationArtifacts.some((artifact) => artifact.kind === 'screenshot')) {
    throw new Error('Implementation evidence requires at least one screenshot.');
  }
  const videoPresent = implementationArtifacts.some((artifact) => artifact.kind === 'video');
  const videoRequired = Boolean(pack.requires_video || videoExpected);
  if (final && videoRequired && !videoPresent) boundedText(pack.video_unavailable_reason, 'Unavailable video reason');
  if (!Array.isArray(pack.known_gaps) || pack.known_gaps.length > 16) throw new Error('Visual evidence known gaps must be a bounded list.');
  pack.known_gaps.forEach((gap) => boundedText(gap, 'Visual evidence known gap'));
  if (Buffer.byteLength(JSON.stringify(pack)) >= 32 * 1024) throw new Error('Visual evidence pack exceeds 32 KiB.');

  return {
    kind: pack.kind,
    applicability: 'applicable',
    candidate_fingerprint: pack.candidate_fingerprint,
    evidence_digest: digestValue(pack),
    scenario_digest: digestValue(pack.scenario),
    approved_direction_digest: pack.approved_direction_digest,
    baseline_status: pack.baseline.status,
    baseline_digest: digestValue(pack.baseline),
    implementation_digest: digestValue(pack.implementation),
    video_required: videoRequired,
    video_present: videoPresent,
    video_unavailable: final && videoRequired && !videoPresent,
    known_gaps_digest: digestValue(pack.known_gaps),
    artifact_count: baselineArtifacts.length + implementationArtifacts.length,
  };
}
