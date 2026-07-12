import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import assert from 'node:assert/strict';

const root = path.resolve('.');
const pluginsRoot = path.join(root, 'plugins');
const expected = {
  'hard-eng': ['hard-eng'],
  'hard-eng-flutter': ['flutter-workflow'],
  'hard-eng-appwrite': ['appwrite-backend'],
  'hard-eng-web': ['web-quality'],
  'hard-eng-sentry': ['sentry-workflow'],
  'hard-eng-delivery': ['product-demo-video', 'website-launch-readiness'],
  'hard-eng-authoring': ['skill-authoring', 'teach'],
};

function frontmatterDescription(text) {
  return /^description:\s*(.+)$/m.exec(text)?.[1]?.trim() ?? '';
}

test('personal marketplace enables only the core plugin by default', () => {
  const marketplace = JSON.parse(fs.readFileSync(path.join(pluginsRoot, 'marketplace.json'), 'utf8'));
  assert.equal(marketplace.name, 'personal');
  assert.equal(marketplace.interface.displayName, 'Personal');
  assert.deepEqual(marketplace.plugins.map((plugin) => plugin.name), Object.keys(expected));
  for (const entry of marketplace.plugins) {
    assert.deepEqual(entry.source, { source: 'local', path: `./.agents/plugins/${entry.name}` });
    assert.equal(entry.policy.authentication, 'ON_INSTALL');
    assert.equal(entry.policy.installation, entry.name === 'hard-eng' ? 'INSTALLED_BY_DEFAULT' : 'AVAILABLE');
    assert.equal(entry.category, 'Developer Tools');
  }
});

test('optional plugins are compact OpenAI-only front doors with no hooks or MCP owner', () => {
  let advertisedCharacters = 0;
  for (const [pluginName, skills] of Object.entries(expected)) {
    const pluginRoot = path.join(pluginsRoot, pluginName);
    const manifest = JSON.parse(fs.readFileSync(path.join(pluginRoot, '.codex-plugin', 'plugin.json'), 'utf8'));
    assert.equal(manifest.name, pluginName);
    assert.equal(manifest.version, '1.0.0');
    assert.equal(manifest.skills, './skills/');
    if (pluginName !== 'hard-eng') {
      assert.equal(manifest.mcpServers, undefined);
      assert.equal(manifest.hooks, undefined);
    }
    const actualSkills = fs.readdirSync(path.join(pluginRoot, 'skills'), { withFileTypes: true })
      .filter((entry) => entry.isDirectory()).map((entry) => entry.name).sort();
    assert.deepEqual(actualSkills, [...skills].sort());
    for (const skillName of skills) {
      const skill = fs.readFileSync(path.join(pluginRoot, 'skills', skillName, 'SKILL.md'), 'utf8');
      const description = frontmatterDescription(skill);
      advertisedCharacters += description.length;
      assert.ok(description.length > 0 && description.length <= 320, `${pluginName}/${skillName} description budget`);
      assert.ok(skill.split(/\r?\n/).length <= 80, `${pluginName}/${skillName} line budget`);
      assert.doesNotMatch(skill, /^\s*3\.\s/m, `${pluginName}/${skillName} has a 3+ step workflow`);
      assert.doesNotMatch(skill, /\b(?:Claude|Pi|OpenCode|no-mistakes|Treehouse|Impeccable)\b/i);
      assert.ok(fs.existsSync(path.join(pluginRoot, 'skills', skillName, 'agents', 'openai.yaml')));
    }
  }
  assert.ok(advertisedCharacters <= 2_500, `optional advertised context is too large: ${advertisedCharacters}`);
});

test('third-party behavior sources are pinned and noticed without vendored runtime dependencies', () => {
  const notices = fs.readFileSync(path.join(root, 'THIRD_PARTY_NOTICES.md'), 'utf8');
  for (const [url, commit] of [
    ['github.com/sgaabdu4/building-flutter-apps', '6e79dd24d03d586861678a697b04cf0fb74aa30e'],
    ['github.com/sgaabdu4/appwrite-backend', 'bab31570b067f9c5454799fd9f2c1b5e4fcba279'],
    ['github.com/fallow-rs/fallow-skills', 'b3fb694566f0d9a570b9efa6c5138dbc1b75c847'],
    ['github.com/millionco/react-doctor', 'dfccac44e4468dd971e2a4fe8e44a49ba91f498a'],
    ['github.com/vercel-labs/agent-skills', 'f8a72b9603728bb92a217a879b7e62e43ad76c81'],
    ['github.com/getsentry/sentry-for-ai', 'a9562ccfefbaa09ab5800740efbd6959b764863d'],
  ]) {
    assert.match(notices, new RegExp(url.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')));
    assert.match(notices, new RegExp(commit));
  }
  assert.doesNotMatch(notices, /copied source code/i);
});
