import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import test from 'node:test';

const repoRoot = path.resolve(new URL('../../..', import.meta.url).pathname);
const ensurePlaywright = path.join(repoRoot, 'skills/e2e/scripts/ensure-playwright.mjs');
const dogfood = path.join(repoRoot, 'skills/e2e/scripts/dogfood-playwright-smoke.mjs');
const playwrightReady = spawnSync('node', [ensurePlaywright], { encoding: 'utf8' }).status === 0;

test('dogfood Playwright smoke creates checked screenshots, video, recap, and events', { skip: !playwrightReady && 'Playwright unavailable' }, () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'e2e-dogfood-smoke-'));
  const runId = 'test-run';
  const result = spawnSync('node', [dogfood, '--root', root, '--run-id', runId], {
    encoding: 'utf8',
  });
  assert.equal(result.status, 0, result.stdout + result.stderr);

  const parsed = JSON.parse(result.stdout);
  assert.equal(parsed.status, 'pass');
  for (const file of [parsed.report, parsed.events, ...parsed.videos, ...parsed.recaps]) {
    assert.equal(fs.existsSync(file), true, `${file} missing`);
    assert.ok(fs.statSync(file).size > 0, `${file} empty`);
  }
  assert.equal(parsed.videos.length, 2);
  assert.equal(parsed.recaps.length, 2);
  assert.deepEqual(
    parsed.videos.map((file) => path.basename(file)).sort(),
    ['dogfood_desktop.mp4', 'dogfood_mobile.mp4'],
  );

  const runDir = path.join(root, 'docs/e2e', runId);
  const screenshotRoot = path.join(runDir, 'screenshots/dogfood');
  const screenshots = ['desktop', 'mobile'].flatMap((profile) => (
    fs.readdirSync(path.join(screenshotRoot, profile)).filter((name) => name.endsWith('.png'))
  ));
  assert.equal(screenshots.length, 8);
  assert.doesNotMatch(fs.readFileSync(parsed.report, 'utf8'), /\/Users\/|[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/);
  assert.doesNotMatch(fs.readFileSync(parsed.events, 'utf8'), /\/Users\/|[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/);
});
