import test from 'node:test';
import assert from 'node:assert/strict';
import { routeRequest, validateDirectContract } from '../../runtime/lib/route.mjs';

test('route matrix sends new, ambiguous, expanded, and material-risk work to Plan', () => {
  for (const input of [
    { new_feature: true },
    { ambiguous: true },
    { scope_expanded: true },
    { risks: ['auth'] },
    { risks: ['schema'] },
    { user_visible_workflow: true },
  ]) assert.equal(routeRequest(input).route, 'Plan');
});

test('small clear fixes, read-only work, and mechanical edits stay Direct', () => {
  assert.equal(routeRequest({ small_fix: true, clear_acceptance: true }).route, 'Direct');
  assert.equal(routeRequest({ read_only: true }).route, 'Direct');
  assert.equal(routeRequest({ mechanical: true }).route, 'Direct');
});

test('explicit actions are bounded by state and safety', () => {
  assert.equal(routeRequest({ explicit_action: 'plan' }).route, 'Plan');
  assert.equal(routeRequest({ explicit_action: 'build', accepted_plan_matches: true }).route, 'Build');
  assert.equal(routeRequest({ explicit_action: 'ship', candidate_adoptable: true }).route, 'Ship');
  assert.equal(routeRequest({ explicit_action: 'learn', admitted_finding: true }).route, 'Learn');
  assert.equal(routeRequest({ explicit_action: 'status' }).route, 'Status');
  assert.throws(() => routeRequest({ explicit_action: 'learn' }), /admitted finding/i);
  assert.throws(() => routeRequest({ explicit_action: 'build', risks: ['data-loss'] }), /Plan/i);
});

test('Direct Build contract requires acceptance, scope, non-goals, justification, and review cadence', () => {
  assert.equal(validateDirectContract({
    objective: 'Fix exact parser regression',
    acceptance: ['focused regression passes'],
    scope: ['parser owner'],
    non_goals: ['new behavior'],
    justification: 'Clear reproduction and behavior',
    review_cadence: 'final-candidate',
  }), true);
  assert.throws(() => validateDirectContract({ objective: 'vague' }), /acceptance/i);
});

test('stateful Direct Build rejects Plan-only fields instead of silently dropping them', async () => {
  const { createInitialRun } = await import('../../runtime/lib/state-machine.mjs');
  const base = {
    repoId: 'a'.repeat(64), checkoutId: 'b'.repeat(64), taskHash: 'c'.repeat(64),
    objective: 'Do not bypass routing', now: '2026-07-12T00:00:00.000Z', runId: 'route-direct-guard',
  };
  const direct = {
    kind: 'direct', digest: 'd'.repeat(64), acceptance: ['bounded'], scope: ['fixture'],
    non_goals: [], justification: 'Small exact fix', review_cadence: 'final-candidate', risks: [],
  };
  assert.throws(() => createInitialRun({ ...base, intent: { ...direct, new_feature: true } }), /Plan-only|unknown/i);
  assert.throws(() => createInitialRun({ ...base, intent: { ...direct, risks: ['auth'] } }), /Plan risk/i);
});
