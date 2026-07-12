import { clone } from './canonical.mjs';
import { requireSupportPlane, transitionError } from './state-transition.mjs';

export function applyPlanEvent(run, event, timestamp) {
  if (event.type === 'plan.prototype-ready' && run.cursor.step === 'discover') {
    run.cursor = { step: 'prototype' };
    return;
  }
  if (event.type === 'plan.ready-for-approval' && ['discover', 'prototype'].includes(run.cursor.step)) {
    requireSupportPlane(run, 'Plan readiness');
    run.cursor = { step: 'ready-for-approval' };
    return;
  }
  if (event.type !== 'plan.accepted' || run.cursor.step !== 'ready-for-approval') {
    transitionError(run, event);
  }
  if (
    !event.plan?.path
    || !event.plan?.digest
    || event.plan.approver !== 'user'
    || !Array.isArray(event.plan.slice_ids)
    || event.plan.slice_ids.length === 0
    || !Array.isArray(event.plan.acceptance_ids)
    || event.plan.acceptance_ids.length === 0
  ) {
    throw new Error('Plan acceptance requires path, digest, planned slices, acceptance IDs, and user approver.');
  }
  run.plan = {
    path: event.plan.path,
    digest: event.plan.digest,
    sections: clone(event.plan.sections ?? {}),
    slice_ids: clone(event.plan.slice_ids),
    acceptance_ids: clone(event.plan.acceptance_ids),
    ui: clone(event.plan.ui ?? { applicable: false }),
    acceptance_revision: run.revision,
    approver_kind: 'user',
    accepted_at: timestamp,
  };
  run.intent = { ...run.intent, digest: event.plan.digest };
  run.phase = 'Build';
  run.cursor = { step: 'red', slice: 1 };
}
