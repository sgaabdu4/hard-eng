const planRisks = new Set(['auth', 'billing', 'schema', 'migration', 'data-loss', 'destructive', 'privacy', 'permissions']);
const reviewCadences = new Set(['every-vertical-slice', 'meaningful-milestones', 'final-candidate']);

function materialPlanTrigger(input) {
  return Boolean(
    input.new_feature
    || input.user_visible_workflow
    || input.ambiguous
    || input.scope_expanded
    || (input.risks ?? []).some((risk) => planRisks.has(risk)),
  );
}

export function validateDirectContract(contract) {
  if (!contract || typeof contract !== 'object') throw new Error('Direct contract is required.');
  if (!contract.objective) throw new Error('Direct contract objective is required.');
  if (!Array.isArray(contract.acceptance) || contract.acceptance.length === 0) throw new Error('Direct contract acceptance is required.');
  if (!Array.isArray(contract.scope) || contract.scope.length === 0) throw new Error('Direct contract scope is required.');
  if (!Array.isArray(contract.non_goals)) throw new Error('Direct contract non-goals are required.');
  if (!contract.justification) throw new Error('Direct contract Plan-bypass justification is required.');
  if (!reviewCadences.has(contract.review_cadence)) throw new Error('Direct contract review cadence is invalid.');
  if (Array.isArray(contract.risks) && contract.risks.some((risk) => planRisks.has(risk))) {
    throw new Error('Direct contract contains a material Plan risk.');
  }
  return true;
}

export function routeRequest(input = {}) {
  const action = input.explicit_action ?? 'auto';
  if (action === 'plan') return { route: 'Plan', reason: 'explicit' };
  if (action === 'status') return { route: 'Status', reason: 'explicit' };
  if (action === 'doctor') return { route: 'Doctor', reason: 'explicit' };
  if (action === 'resume') return { route: 'Resume', reason: 'explicit' };

  if (action === 'learn') {
    if (!input.admitted_finding) throw new Error('Learn requires an admitted finding.');
    return { route: 'Learn', reason: 'admitted-finding' };
  }
  if (action === 'ship') {
    if (!input.candidate_adoptable) throw new Error('Ship requires a bounded adoptable candidate.');
    return { route: 'Ship', reason: 'candidate' };
  }
  if (action === 'build') {
    if (materialPlanTrigger(input)) throw new Error('Material risk requires Plan before Build.');
    if (input.accepted_plan_matches) return { route: 'Build', reason: 'accepted-plan' };
    if (input.direct_contract) {
      validateDirectContract(input.direct_contract);
      return { route: 'Build', reason: 'direct-contract' };
    }
    throw new Error('Build requires a matching accepted plan or bounded Direct contract.');
  }
  if (action !== 'auto') throw new Error(`Unknown Hard Eng action: ${action}.`);

  if (materialPlanTrigger(input)) return { route: 'Plan', reason: 'new-ambiguous-or-risky' };
  if (input.accepted_plan_matches) return { route: 'Build', reason: 'accepted-plan' };
  if (input.read_only || input.mechanical || (input.small_fix && input.clear_acceptance)) {
    return { route: 'Direct', reason: 'bounded' };
  }
  return { route: 'Plan', reason: 'unresolved-default' };
}
