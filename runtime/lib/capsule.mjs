import { findingCounts } from './findings.mjs';

function shortDigest(value) {
  return typeof value === 'string' ? value.slice(0, 12) : 'none';
}

export function renderCapsule(run) {
  const findings = findingCounts(run.findings);
  const lastProof = [...run.proof].reverse().find((proof) => proof.result === 'pass') ?? null;
  const slice = run.cursor.slice ? `\nslice: ${run.cursor.slice}` : '';
  const interruption = run.interruption ? `\ninterruption: pending — ${run.interruption.intent.slice(0, 80)}` : '';
  const clarification = run.cursor.step === 'await-user-clarification'
    ? `\nquestions: ${run.cursor.question_ids.join(', ')}`
    : '';
  return [
    'Hard Eng resume',
    `run: ${run.run_id}`,
    `phase: ${run.phase}:${run.cursor.step}${slice}${interruption}${clarification}`,
    `intent: ${run.intent.kind}:${shortDigest(run.intent.digest)}`,
    `proof: ${lastProof ? `${lastProof.name} (${shortDigest(lastProof.candidate_fingerprint)})` : 'none'}`,
    `findings: blocking ${findings.blocking}, admitted ${findings.admitted}`,
    `next: ${run.next.owner} — ${run.next.action}`,
    `revision: ${run.revision}`,
  ].join('\n');
}
