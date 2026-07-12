import { applyEvent } from '../../runtime/lib/state-machine.mjs';

export function supportEvents() {
  return [
    {
      type: 'support.recorded',
      receipt: {
        tool: 'codebase-memory', operation: 'detect_changes', status: 'pass', evidence_digest: 'a'.repeat(64), runtime_observed: true,
      },
    },
    {
      type: 'support.recorded',
      receipt: {
        tool: 'context-mode', operation: 'not-applicable', status: 'not-applicable', reason_code: 'no-large-output', runtime_observed: true,
      },
    },
  ];
}

export function recordSupport(run) {
  return supportEvents().reduce((current, event) => applyEvent(current, event), run);
}
