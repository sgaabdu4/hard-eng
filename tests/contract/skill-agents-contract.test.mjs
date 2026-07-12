import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import assert from 'node:assert/strict';

const root = path.resolve('.');

test('global AGENTS rule is tiny and contains only core route plus required support tools', () => {
  const text = fs.readFileSync(path.join(root, 'AGENTS.md'), 'utf8');
  const words = text.replace(/[`#$]/g, '').trim().split(/\s+/).length;
  assert.ok(words <= 120, `AGENTS.md exceeds 120 words: ${words}`);
  assert.match(text, /\$hard-eng/);
  assert.match(text, /codebase-memory-mcp cli list_projects/);
  assert.match(text, /codebase-memory-mcp cli index_repository/);
  for (const operation of ['get_architecture', 'search_graph', 'trace_path', 'detect_changes']) {
    assert.match(text, new RegExp(operation));
  }
  assert.match(text, /context-mode index <path>/);
  assert.match(text, /context-mode search "<query>"/);
  assert.match(text, /context-mode doctor/);
  assert.match(text, /Never launch model evals or subagents automatically/);
  assert.doesNotMatch(text, /he-plan|he-implement|he-verify|he-ship|he-learn|workflow-help|grill-me|no-mistakes|treehouse|impeccable/i);
});

test('core plugin advertises one concise Hard Eng skill with progressive disclosure', () => {
  const skillsRoot = path.join(root, 'plugins', 'hard-eng', 'skills');
  const skillDirs = fs.readdirSync(skillsRoot, { withFileTypes: true }).filter((entry) => entry.isDirectory());
  assert.deepEqual(skillDirs.map((entry) => entry.name), ['hard-eng']);
  const skillRoot = path.join(skillsRoot, 'hard-eng');
  const text = fs.readFileSync(path.join(skillRoot, 'SKILL.md'), 'utf8');
  assert.ok(text.split(/\r?\n/).length <= 80);
  const description = /^description:\s*(.+)$/m.exec(text)?.[1] ?? '';
  assert.ok(description.length > 0 && description.length <= 320);
  assert.doesNotMatch(text, /^\s*3\.\s/m, 'SKILL.md must not contain a 3+ step workflow');
  for (const reference of ['route.md', 'plan.md', 'ui-decision-lab.md', 'build.md', 'ship.md', 'learn.md', 'recovery.md']) {
    assert.ok(fs.existsSync(path.join(skillRoot, 'references', reference)), `missing ${reference}`);
  }
  const metadata = fs.readFileSync(path.join(skillRoot, 'agents', 'openai.yaml'), 'utf8');
  assert.match(metadata, /display_name: "Hard Eng"/);
  assert.match(metadata, /default_prompt:/);

  const manifest = JSON.parse(fs.readFileSync(path.join(root, 'plugins', 'hard-eng', '.codex-plugin', 'plugin.json'), 'utf8'));
  assert.equal(manifest.interface.displayName, 'Hard Eng');
  assert.equal(manifest.interface.category, 'Developer Tools');
  assert.deepEqual(manifest.interface.capabilities, ['Interactive', 'Write']);
  assert.equal(manifest.interface.logo, './assets/hard-eng.svg');
  const icon = fs.readFileSync(path.join(root, 'plugins', 'hard-eng', 'assets', 'hard-eng.svg'), 'utf8');
  assert.match(icon, /role="img"/);
  assert.match(icon, /<title id="title">Hard Eng<\/title>/);
});

test('Hard Eng makes support tools deterministic without storing their output', () => {
  const referenceRoot = path.join(root, 'plugins', 'hard-eng', 'skills', 'hard-eng', 'references');
  const build = fs.readFileSync(path.join(referenceRoot, 'build.md'), 'utf8');
  const ship = fs.readFileSync(path.join(referenceRoot, 'ship.md'), 'utf8');

  assert.match(build, /Codebase Memory is mandatory/);
  assert.match(build, /cannot be `not-applicable`/);
  assert.match(build, /state server resolves the\s+exact repository project/);
  assert.match(build, /actual\s+bounded `get_architecture`, `search_graph`, `trace_path`, or `detect_changes`/);
  assert.match(build, /reason_code: no-large-output/);
  assert.match(build, /strips parameters and raw output from state/);
  assert.match(ship, /exact `detect_changes` operation/);
  assert.match(ship, /it is never\s+`not-applicable`/);
  assert.match(ship, /exact `not-applicable` disposition documented/);
});
