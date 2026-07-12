const actions = {
  'Plan:discover': 'Resolve evidence and remaining material questions',
  'Plan:prototype': 'Complete and review the required flow prototype',
  'Plan:ready-for-approval': 'Obtain explicit user approval for plan.md',
  'Plan:await-user-clarification': 'Answer the recorded clarification questions before any mutation',
  'Build:red': 'Prove the focused slice test fails for the expected reason',
  'Build:implement': 'Implement the smallest change for the current slice',
  'Build:verify': 'Run focused proof for the current candidate',
  'Build:review': 'Review the verified slice against intent and risk',
  'Build:slice-proven': 'Start the next slice or declare all slices proven',
  'Build:await-user-review': 'Wait for the required visual milestone decision',
  'Build:learn': 'Prove the admitted durable guard and return boundary',
  'Build:await-user-clarification': 'Answer the recorded clarification questions before any mutation',
  'Ship:preflight': 'Run deterministic Ship preflight and candidate proof',
  'Ship:await-candidate-approval': 'Wait for explicit final candidate approval',
  'Ship:publish': 'Publish the exact approved candidate safely',
  'Ship:await-publication-approval': 'Wait for explicit approval of currentness, CI, protections, and rollback evidence',
  'Ship:learn': 'Prove the admitted durable guard and return boundary',
  'Ship:await-user-clarification': 'Answer the recorded clarification questions before any mutation',
  'Complete:complete': 'No action',
};

export function nextFor(phase, cursor) {
  const action = actions[`${phase}:${cursor?.step}`];
  if (!action) throw new Error('Lifecycle cursor has no next-action contract.');
  const owner = cursor.step.includes('await') || cursor.step === 'ready-for-approval' ? 'user' : 'model';
  return { owner, action };
}
