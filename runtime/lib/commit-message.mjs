import { digestValue, sha256 } from './canonical.mjs';

const metadataLine = /^\s*(?:generated(?:-|\s+)(?:by|with)|ai-generated|model|prompt|token(?:s|\s+usage)?|codex(?:-task)?|task-id|session-id|run-id)\s*:/im;
const generatedClaim = /^\s*(?:generated with|created by)\s+(?:codex|chatgpt|ai)\b/im;
const decoration = /^\s*(?:-{3,}|_{3,}|={3,}|\*{3,}|–{3,}|—{3,})\s*$/m;

export function validateCommitMessage(value) {
  if (typeof value !== 'string' || value.length === 0 || value.length > 16 * 1024 || value.includes('\0')) {
    throw new Error('Commit message must be non-empty, text-only, and at most 16 KiB.');
  }
  const message = value.replace(/\r\n?/g, '\n').trimEnd();
  const subject = message.split('\n', 1)[0].trim();
  if (!subject) throw new Error('Commit message requires a non-empty subject.');
  if (/^\s*co-authored-by\s*:/im.test(message)) {
    throw new Error('Commit message cannot contain a co-author line.');
  }
  if (message.includes('—')) throw new Error('Commit message cannot contain an em dash.');
  if (/^[-–—]/.test(subject)) throw new Error('Commit message subject cannot use a dash prefix.');
  if (decoration.test(message)) throw new Error('Commit message cannot contain decorative divider lines.');
  if (metadataLine.test(message) || generatedClaim.test(message)) {
    throw new Error('Commit message cannot contain unrelated tool, model, task, or usage metadata.');
  }
  const evidence = {
    policy: 'hard-eng/commit-message/v1',
    message_digest: sha256(message),
    subject_digest: sha256(subject),
  };
  return {
    message_digest: evidence.message_digest,
    subject_digest: evidence.subject_digest,
    evidence_digest: digestValue(evidence),
  };
}
