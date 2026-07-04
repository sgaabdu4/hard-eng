#!/usr/bin/env node
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';

const repo = path.resolve(new URL('..', import.meta.url).pathname);
const mini = 'gpt-5.4-mini';

function walk(dir, out = []) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) walk(fullPath, out);
    if (entry.isFile()) out.push(fullPath);
  }
  return out;
}

const evalFiles = walk(path.join(repo, 'tests'))
  .filter((file) => file.includes(`${path.sep}evals${path.sep}`));
const descriptionRoutingPath = path.join('tests', 'skills', 'description-routing', 'evals', 'evals.json');

for (const file of evalFiles.filter((item) => item.endsWith('.json'))) {
  const parsed = JSON.parse(fs.readFileSync(file, 'utf8'));
  if (Object.hasOwn(parsed, 'model')) {
    assert.equal(parsed.model, mini, `${path.relative(repo, file)} model must be ${mini}`);
  }
  const relativePath = path.relative(repo, file);
  if (relativePath === path.join('tests', 'agents-md-routing', 'evals', 'evals.json') && Array.isArray(parsed.cases)) {
    const caseIds = new Set(parsed.cases.map((item) => item.id));
    const caseById = new Map(parsed.cases.map((item) => [item.id, item]));
    for (const requiredCase of [
      'workflow_help_front_door',
      'he_stage_order_receipts_full_path',
      'he_failure_loops_all_stages',
      'he_plan_no_guesswork_alignment',
      'ui_review_decision_receipt',
      'verify_loop_before_no_mistakes',
      'no_mistakes_handoff',
      'upstream_skill_behavior_change_local_wrapper',
      'he_implement_ssot_owner_reuse_gate',
      'flutter_ui_ssot_reuse_and_owner',
      'react_ui_ssot_reuse_and_duplicate_owner',
      'verify_blocks_unresolved_ssot_before_e2e',
      'backend_e2e_approval_boundary',
      'repeat_miss_learning_skill_eval',
      'user_caught_process_misses_recorded',
      'broad_ui_product_feature_requires_approval',
    ]) {
      assert.ok(caseIds.has(requiredCase), `${path.relative(repo, file)} missing required eval case ${requiredCase}`);
    }
    for (const requiredExpectation of [
      'requiresCommittedWorkBeforeNoMistakes',
      'usesWorktreeReadyGuard',
      'requiresProjectHooksBeforeDryRun',
    ]) {
      assert.ok(
        caseById.get('no_mistakes_handoff')?.expectTrue?.includes(requiredExpectation),
        `${path.relative(repo, file)} no_mistakes_handoff missing ${requiredExpectation}`,
      );
    }
    assert.ok(
      caseById.get('verify_loop_before_no_mistakes')?.expectTrue?.includes('waitsForCleanLoopBeforeNoMistakes'),
      `${path.relative(repo, file)} verify_loop_before_no_mistakes missing waitsForCleanLoopBeforeNoMistakes`,
    );
    assert.ok(
      caseById.get('he_stage_order_receipts_full_path')?.expectTrue?.includes('usesHandoverPrompt'),
      `${path.relative(repo, file)} he_stage_order_receipts_full_path missing usesHandoverPrompt`,
    );
    assert.ok(
      caseById.get('upstream_skill_behavior_change_local_wrapper')?.expectTrue?.includes('keepsUpstreamSkillsReadOnly'),
      `${path.relative(repo, file)} upstream skill eval missing read-only expectation`,
    );
  }
  if (relativePath === path.join('tests', 'skills', 'e2e', 'evals', 'evals.json') && Array.isArray(parsed.cases)) {
    const caseIds = new Set(parsed.cases.map((item) => item.id));
    for (const requiredCase of [
      'profile_lock_not_e2e_blocker',
      'repeated_blocker_stops_and_asks',
      'prod_backend_permission_requires_approval',
      'generated_user_cleanup_recorded',
      'unresolved_ui_ssot_blocks_e2e',
    ]) {
      assert.ok(caseIds.has(requiredCase), `${path.relative(repo, file)} missing required eval case ${requiredCase}`);
    }
  }
  if (relativePath === descriptionRoutingPath && Array.isArray(parsed.cases)) {
    const routedSkills = new Set(parsed.cases.flatMap((item) => item.expectedSkills || []));
    const activeSkills = fs.readdirSync(path.join(repo, 'skills'), { withFileTypes: true })
      .filter((entry) => entry.isDirectory() || entry.isSymbolicLink())
      .filter((entry) => fs.existsSync(path.join(repo, 'skills', entry.name, 'SKILL.md')))
      .map((entry) => entry.name)
      .sort();
    for (const skill of activeSkills) {
      assert.ok(routedSkills.has(skill), `${descriptionRoutingPath} missing broad routing eval for ${skill}`);
    }
  }
}

for (const file of [
  path.join(repo, 'scripts', 'run-skill-mini-evals.mjs'),
  ...evalFiles.filter((item) => /run.*evals\.(mjs|py)$/.test(path.basename(item))),
]) {
  const text = fs.readFileSync(file, 'utf8');
  const configPath = path.join(path.dirname(file), 'evals.json');
  const usesPinnedConfig = text.includes('config.model') &&
    fs.existsSync(configPath) &&
    JSON.parse(fs.readFileSync(configPath, 'utf8')).model === mini;
  assert.ok(text.includes(mini) || usesPinnedConfig, `${path.relative(repo, file)} must default evals to ${mini}`);
  assert.ok(!/gpt-5\.5/.test(text), `${path.relative(repo, file)} must not run evals on gpt-5.5`);
}

const descriptionRunnerText = fs.readFileSync(
  path.join(repo, 'tests', 'skills', 'description-routing', 'evals', 'run-evals.mjs'),
  'utf8',
);
assert.ok(
  descriptionRunnerText.includes('hasActual') && descriptionRunnerText.includes('missing: !hasActual'),
  `${descriptionRoutingPath} runner must fail missing case ids, including expectedSkills [] cases`,
);

const grillStageRunnerText = fs.readFileSync(
  path.join(repo, 'tests', 'skills', 'grill-me', 'evals', 'run-stage-routing-evals.mjs'),
  'utf8',
);
assert.ok(/["']-["']/.test(grillStageRunnerText), 'Grill Me stage routing eval must pass the prompt through stdin');
assert.ok(grillStageRunnerText.includes('input: prompt'), 'Grill Me stage routing eval must write the prompt to stdin');

console.log('eval-model-defaults-test: pass');
