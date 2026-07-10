#!/usr/bin/env node
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';

const repo = path.resolve(new URL('..', import.meta.url).pathname);
const evalModel = 'gpt-5.6-luna';
const defaultModelModule = path.join(repo, 'scripts', 'eval-model.mjs');

function walk(dir, out = []) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) walk(fullPath, out);
    if (entry.isFile()) out.push(fullPath);
  }
  return out;
}

const evalFiles = walk(path.join(repo, 'tests'))
  .filter((file) => file.includes(`${path.sep}evals${path.sep}`))
  .filter((file) => !file.includes(`${path.sep}results${path.sep}`));
const descriptionRoutingPath = path.join('tests', 'skills', 'description-routing', 'evals', 'evals.json');

function readText(file) {
  return fs.readFileSync(file, 'utf8');
}

function hasDisabledImplicitInvocation(skillDir, markdown) {
  if (/^disable-model-invocation:\s*true\s*$/m.test(markdown)) return true;
  const openaiPath = path.join(skillDir, 'agents', 'openai.yaml');
  if (!fs.existsSync(openaiPath)) return false;
  return /^\s*allow_implicit_invocation:\s*false\s*$/m.test(readText(openaiPath));
}

for (const file of evalFiles.filter((item) => item.endsWith('.json'))) {
  const parsed = JSON.parse(fs.readFileSync(file, 'utf8'));
  if (Object.hasOwn(parsed, 'model')) {
    assert.equal(parsed.model, evalModel, `${path.relative(repo, file)} model must be ${evalModel}`);
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
      'he_plan_ui_screenshots_before_implement',
      'he_implement_ui_screenshots_before_verify',
      'he_ship_live_currentness_dirty_scope',
      'hard_eng_artifact_write_safety_gates',
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
    for (const [caseId, requiredExpectation] of [
      ['he_plan_ui_screenshots_before_implement', 'requiresPlanUiScreenshots'],
      ['he_implement_ui_screenshots_before_verify', 'requiresImplementationUiScreenshots'],
      ['he_ship_live_currentness_dirty_scope', 'usesLiveShipCurrentness'],
      ['he_ship_live_currentness_dirty_scope', 'classifiesDirtyScope'],
      ['hard_eng_artifact_write_safety_gates', 'usesArtifactHygieneScanner'],
      ['hard_eng_artifact_write_safety_gates', 'usesWriteSafetyScanner'],
    ]) {
      assert.ok(
        caseById.get(caseId)?.expectTrue?.includes(requiredExpectation),
        `${path.relative(repo, file)} ${caseId} missing ${requiredExpectation}`,
      );
    }
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
    const coveredSkills = new Set(parsed.cases.flatMap((item) => [
      ...(item.expectedSkills || []),
      ...(item.suppressedSkills || []),
    ]));
    const activeSkills = fs.readdirSync(path.join(repo, 'skills'), { withFileTypes: true })
      .filter((entry) => entry.isDirectory() || entry.isSymbolicLink())
      .filter((entry) => fs.existsSync(path.join(repo, 'skills', entry.name, 'SKILL.md')))
      .filter((entry) => {
        const skillDir = path.join(repo, 'skills', entry.name);
        return !hasDisabledImplicitInvocation(skillDir, readText(path.join(skillDir, 'SKILL.md')));
      })
      .map((entry) => entry.name)
      .sort();
    for (const skill of activeSkills) {
      assert.ok(coveredSkills.has(skill), `${descriptionRoutingPath} missing broad routing eval for ${skill}`);
    }
  }
}

const runnerFiles = [
  path.join(repo, 'scripts', 'run-skill-mini-evals.mjs'),
  ...evalFiles.filter((item) => /run.*evals\.(mjs|py)$/.test(path.basename(item))),
];

assert.equal(readText(defaultModelModule).trim(), `export const DEFAULT_EVAL_MODEL = '${evalModel}';`);

for (const file of runnerFiles) {
  const text = fs.readFileSync(file, 'utf8');
  const relative = path.relative(repo, file);
  const modelLiterals = [...text.matchAll(/gpt-\d+(?:\.\d+)+(?:-[a-z0-9-]+)?/gi)].map((match) => match[0]);
  if (file.endsWith('.py')) {
    const defaultMatch = text.match(/add_argument\(\s*["']--model["'][\s\S]*?default=os\.environ\.get\([^,]+,\s*["']([^"']+)["']\)/);
    assert.equal(defaultMatch?.[1], evalModel, `${relative} must parse an effective default of ${evalModel}`);
    assert.deepEqual([...new Set(modelLiterals)], [evalModel], `${relative} must not contain unsupported model literals`);
    continue;
  }
  assert.match(text, /import \{ DEFAULT_EVAL_MODEL \} from ["'][^"']*eval-model\.mjs["'];/, `${relative} must import the centralized eval default`);
  const assignment = text.match(/const model\s*=\s*([^;]+);/)?.[1] || '';
  assert.match(assignment, /DEFAULT_EVAL_MODEL/, `${relative} must use the centralized eval default in the effective model assignment`);
  assert.match(text, /["']-m["']\s*,\s*model\b/, `${relative} must pass the effective model to Codex`);
  assert.deepEqual(modelLiterals, [], `${relative} must not contain runner-local model literals`);
}

const descriptionRunnerText = fs.readFileSync(
  path.join(repo, 'tests', 'skills', 'description-routing', 'evals', 'run-evals.mjs'),
  'utf8',
);
assert.ok(
  descriptionRunnerText.includes('hasActual') && descriptionRunnerText.includes('missing: !hasActual'),
  `${descriptionRoutingPath} runner must fail missing case ids, including expectedSkills [] cases`,
);
assert.ok(descriptionRunnerText.includes('testCase.evalId'), `${descriptionRoutingPath} runner must use opaque case ids in the model prompt`);
assert.ok(!descriptionRunnerText.includes('`- ${testCase.id}: ${testCase.prompt}`'), `${descriptionRoutingPath} runner must keep semantic case ids out of the model prompt`);
assert.ok(descriptionRunnerText.includes('every skill whose description independently requires invocation'), `${descriptionRoutingPath} runner must grade metadata without a primary-skill bias`);
assert.ok(descriptionRunnerText.includes('omit response-style-only skills unless the request itself is about response wording'), `${descriptionRoutingPath} runner must keep support-style skills outside task routing`);
for (const leakedExpectation of [
  'When a request explicitly mentions tests',
  'Include workflow-help for every non-trivial case',
  'Route every Sentry request',
  'Route PR, branch, or WIP review',
  'Route every UI component',
  'Route every React or Next.js',
  'For improve_codebase_architecture',
]) {
  assert.ok(!descriptionRunnerText.includes(leakedExpectation), `${descriptionRoutingPath} runner must not leak expected routing: ${leakedExpectation}`);
}

const grillStageRunnerText = fs.readFileSync(
  path.join(repo, 'tests', 'skills', 'grill-me', 'evals', 'run-stage-routing-evals.mjs'),
  'utf8',
);
assert.ok(/["']-["']/.test(grillStageRunnerText), 'Grill Me stage routing eval must pass the prompt through stdin');
assert.ok(grillStageRunnerText.includes('input: prompt'), 'Grill Me stage routing eval must write the prompt to stdin');

console.log('eval-model-defaults-test: pass');
