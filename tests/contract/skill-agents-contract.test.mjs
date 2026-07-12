import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import assert from 'node:assert/strict';

const root = path.resolve('.');

test('global AGENTS rule preserves current-state documentation and core routing', () => {
  const text = fs.readFileSync(path.join(root, 'AGENTS.md'), 'utf8');
  assert.match(text, /\$hard-eng/);
  assert.match(text, /codebase-memory-mcp cli <tool>/);
  assert.match(text, /Context Mode/);
  assert.match(text, /current accepted system/);
  assert.match(text, /Omit before-state/);
  assert.match(text, /dedicated migration or rollback evidence/);
  assert.match(text, /Documentation tests assert the current required behavior/);
  assert.match(text, /Never automatically launch model evals, subagents/);
  for (const principle of ['KISS', 'YAGNI', 'DRY', 'SSOT']) assert.match(text, new RegExp(principle));
  assert.match(text, /fewest complete concepts, not the smallest patch/);
  assert.match(text, /Fix the root owner and every connected path/);
  assert.match(text, /No patchwork/);
  assert.match(text, /complete the migration in the owned scope/);
  assert.match(text, /no alias, compatibility mode, dual read\/write, dormant copy, parallel owner, or legacy runtime/);
  assert.match(text, /If confused or materially uncertain/);
  assert.match(text, /Never guess or mutate first/);
  assert.match(text, /Create commits, push refs, open or merge PRs, or publish only after/);
});

test('the Hard Eng skill uses progressive disclosure from one native entry point', () => {
  const skillRoot = path.join(root, 'skills', 'hard-eng');
  const text = fs.readFileSync(path.join(skillRoot, 'SKILL.md'), 'utf8');
  assert.ok(text.split(/\r?\n/).length <= 80);
  assert.match(text, /Use one local state tool/);
  assert.doesNotMatch(text, /^\s*3\.\s/m, 'SKILL.md must not contain a 3+ step workflow');
  for (const reference of [
    'route.md', 'plan.md', 'ui-decision-lab.md', 'build.md', 'ship.md', 'learn.md', 'recovery.md',
  ]) {
    assert.equal(fs.existsSync(path.join(skillRoot, 'references', reference)), true, `missing ${reference}`);
  }
  const metadata = fs.readFileSync(path.join(skillRoot, 'agents', 'openai.yaml'), 'utf8');
  assert.match(metadata, /display_name: "Hard Eng"/);
  assert.match(metadata, /default_prompt:/);
});

test('Hard Eng records support receipts without storing raw support output', () => {
  const referenceRoot = path.join(root, 'skills', 'hard-eng', 'references');
  const build = fs.readFileSync(path.join(referenceRoot, 'build.md'), 'utf8');
  const ship = fs.readFileSync(path.join(referenceRoot, 'ship.md'), 'utf8');
  assert.match(build, /Codebase Memory is mandatory/);
  assert.match(build, /codebase-memory-mcp cli get_architecture\|search_graph\|trace_path\|detect_changes/);
  assert.match(build, /never opens or uses the\s+Codebase Memory MCP transport/);
  assert.match(build, /never\s+store raw output/);
  assert.match(build, /reason_code: no-large-output/);
  assert.match(ship, /exact `detect_changes` operation/);
  assert.match(ship, /it is never\s+`not-applicable`/);
});

test('Hard Eng preserves the complete Plan, Build loop, Ship, and conditional Learn contract', () => {
  const referenceRoot = path.join(root, 'skills', 'hard-eng', 'references');
  const route = fs.readFileSync(path.join(referenceRoot, 'route.md'), 'utf8');
  const plan = fs.readFileSync(path.join(referenceRoot, 'plan.md'), 'utf8');
  const build = fs.readFileSync(path.join(referenceRoot, 'build.md'), 'utf8');
  const ship = fs.readFileSync(path.join(referenceRoot, 'ship.md'), 'utf8');
  const learn = fs.readFileSync(path.join(referenceRoot, 'learn.md'), 'utf8');

  assert.match(route, /stop before mutation/);
  assert.match(route, /ask the\s+smallest targeted question/);
  assert.match(route, /clarification\.required/);
  assert.match(route, /await-user-clarification/);
  assert.match(plan, /PRODUCT\.md/);
  assert.match(plan, /DESIGN\.md/);
  assert.match(plan, /every normative clause/);
  assert.match(plan, /classify its premise and each proposed option/);
  assert.match(plan, /A user\s+decision requires an exact user answer/);
  assert.match(plan, /clarification\.required/);
  assert.match(plan, /recommended default and reason/);
  assert.match(plan, /Canonicalize domain terms/);
  assert.match(plan, /offline\/retry/);
  assert.match(plan, /never connect the Plan artifact to production data/);
  for (const domain of Array.from({ length: 10 }, (_, index) => `D${index + 1}`)) {
    assert.match(plan, new RegExp(`\\| ${domain} `));
  }
  for (const category of Array.from({ length: 8 }, (_, index) => `A${index + 1}`)) {
    assert.match(plan, new RegExp(`\\| ${category} `));
  }

  assert.match(build, /one Implement ⇄ Verify loop/);
  assert.match(build, /There is no\s+separate Verify stage/);
  assert.match(build, /canonical behavior, domain, data, API, UI primitive/);
  assert.match(build, /smallest failing behavior test before implementation/);
  assert.match(build, /Mock\s+only external boundaries/);
  assert.match(build, /return directly to `implement` for the same slice/);
  assert.match(build, /run real UI E2E last/);
  assert.match(build, /ask the targeted user\s+question/);

  assert.match(ship, /clean candidate, exact current HEAD/);
  assert.match(ship, /resolved actionable review\s+threads/);
  assert.match(ship, /Ship does not auto-fix source/);
  assert.match(learn, /conditional Build\/Ship interrupt/);
  assert.match(learn, /fail-before\/pass-after proof/);
  assert.match(learn, /explicit user-approved call budget/);
});
