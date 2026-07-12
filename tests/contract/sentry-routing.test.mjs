import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import assert from 'node:assert/strict';

const root = path.resolve('.');
const routerFile = path.join(root, 'skills', 'sentry-workflow', 'references', 'upstream-routing.md');

function skillFiles(directory) {
  const output = [];
  for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
    const target = path.join(directory, entry.name);
    if (entry.isDirectory()) output.push(...skillFiles(target));
    else if (entry.isFile() && entry.name === 'SKILL.md') output.push(target);
  }
  return output.sort();
}

test('the single native Sentry router covers every pinned upstream entrypoint and CLI exactly once', () => {
  const text = fs.readFileSync(routerFile, 'utf8');
  const routes = [...text.matchAll(/`(\.\.\/\.\.\/\.\.\/vendor\/skill-upstreams\/sentry-[^`]+\/SKILL\.md)`/g)]
    .map((match) => path.resolve(path.dirname(routerFile), match[1]));
  const expected = [
    ...skillFiles(path.join(root, 'vendor', 'skill-upstreams', 'sentry-for-ai', 'skills')),
    path.join(root, 'vendor', 'skill-upstreams', 'sentry-cli', 'plugins', 'sentry-cli', 'skills', 'sentry-cli', 'SKILL.md'),
  ].sort();

  assert.equal(routes.length, expected.length);
  assert.equal(new Set(routes).size, routes.length, 'a pinned Sentry entrypoint is routed more than once');
  assert.deepEqual([...routes].sort(), expected);
  assert.match(text, /When more than one row still matches,\s+ask\s+one targeted question/i);
  assert.equal(fs.existsSync(path.join(root, 'skills', 'sentry-cli')), false);
  assert.equal(fs.existsSync(path.join(root, 'skills', 'sentry-feature-setup')), false);
});
