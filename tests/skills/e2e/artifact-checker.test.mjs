import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import test from 'node:test';

const repoRoot = path.resolve(new URL('../../..', import.meta.url).pathname);
const checker = path.join(repoRoot, 'skills/e2e/scripts/check-e2e-run-artifacts.mjs');

function makeRunDir(name) {
  return fs.mkdtempSync(path.join(os.tmpdir(), `e2e-artifacts-${name}-`));
}

function writeFile(root, rel, text = '') {
  const fullPath = path.join(root, rel);
  fs.mkdirSync(path.dirname(fullPath), { recursive: true });
  fs.writeFileSync(fullPath, text);
}

function runChecker(runDir, extraArgs = []) {
  return spawnSync('node', [checker, '--run-dir', runDir, ...extraArgs], {
    encoding: 'utf8',
  });
}

function writeCompleteRun(runDir, overrides = {}) {
  writeFile(runDir, 'screenshots/login/01_pass.png', 'png');
  writeFile(runDir, 'videos/login_desktop.mp4', 'desktop video');
  writeFile(runDir, 'videos/login_mobile.mp4', 'mobile video');
  writeFile(runDir, 'recaps/login_desktop_2x_cursor.mp4', 'desktop recap');
  writeFile(runDir, 'recaps/login_mobile_2x_cursor.mp4', 'mobile recap');
  writeFile(runDir, 'issues.md', overrides.issues ?? 'No unresolved issues.\n');
  writeFile(runDir, 'report.md', overrides.report ?? [
    'Driver used: Codex Browser. No fallback.',
    'Issues: none unresolved.',
    'Regression commands: npm test -> pass.',
    '2x cursor recap desktop: recaps/login_desktop_2x_cursor.mp4.',
    '2x cursor recap mobile: recaps/login_mobile_2x_cursor.mp4.',
  ].join('\n'));
  if (overrides.events !== null) {
    writeFile(runDir, 'events.jsonl', overrides.events ?? `${JSON.stringify({
      runId: 'run-1',
      flow: 'login',
      step: 'submit credentials',
      eventId: 'evt-1',
      ts: '2026-06-22T00:00:00Z',
      driver: 'browser',
      profile: 'desktop',
      action: 'click',
      target: 'button[name=Sign in]',
      assertion: 'dashboard is visible',
      status: 'pass',
      screenshotPath: 'screenshots/login/01_pass.png',
    })}\n`);
  }
}

test('artifact checker accepts a complete captured run', () => {
  const runDir = makeRunDir('pass');
  writeCompleteRun(runDir);

  const result = runChecker(runDir);
  assert.equal(result.status, 0, result.stdout + result.stderr);
});

test('artifact checker rejects a run with missing action evidence', () => {
  const runDir = makeRunDir('fail');
  writeFile(runDir, 'report.md', [
    'Driver used: Codex Browser. No fallback.',
    'Issues: none unresolved.',
    'Regression commands: npm test -> pass.',
    '2x cursor recap desktop: recaps/login_desktop_2x_cursor.mp4.',
    '2x cursor recap mobile: recaps/login_mobile_2x_cursor.mp4.',
  ].join('\n'));
  writeFile(runDir, 'issues.md', 'No unresolved issues.\n');
  writeFile(runDir, 'videos/login_desktop.mp4', 'desktop video');
  writeFile(runDir, 'videos/login_mobile.mp4', 'mobile video');
  writeFile(runDir, 'recaps/login_desktop_2x_cursor.mp4', 'desktop recap');
  writeFile(runDir, 'recaps/login_mobile_2x_cursor.mp4', 'mobile recap');
  writeFile(runDir, 'events.jsonl', `${JSON.stringify({
    runId: 'run-1',
    flow: 'login',
    step: 'submit credentials',
    eventId: 'evt-1',
    ts: '2026-06-22T00:00:00Z',
    driver: 'browser',
    action: 'click',
    status: 'pass',
  })}\n`);

  const result = runChecker(runDir);
  assert.notEqual(result.status, 0);
  assert.match(result.stdout, /missing target or x\/y coordinates/);
  assert.match(result.stdout, /missing existing screenshot\/video\/log\/trace evidence/);
});

const failureCases = [
  {
    name: 'missing events file',
    omitEvents: true,
    expected: /events\.jsonl is missing/,
  },
  {
    name: 'invalid event JSON',
    events: '{nope}\n',
    expected: /not valid JSON/,
  },
  {
    name: 'zero UI actions',
    events: `${JSON.stringify({
      runId: 'run-1',
      flow: 'login',
      step: 'assert home',
      eventId: 'evt-1',
      ts: '2026-06-22T00:00:00Z',
      driver: 'browser',
      action: 'assert',
      status: 'pass',
      assertion: 'home is visible',
      screenshotPath: 'screenshots/login/01_pass.png',
    })}\n`,
    expected: /no UI action events were recorded/,
  },
  {
    name: 'missing required event fields',
    events: `${JSON.stringify({
      action: 'click',
      target: 'button',
      assertion: 'done',
      screenshotPath: 'screenshots/login/01_pass.png',
    })}\n`,
    expected: /missing runId/,
  },
  {
    name: 'missing settled assertion',
    events: `${JSON.stringify({
      runId: 'run-1',
      flow: 'login',
      step: 'submit credentials',
      eventId: 'evt-1',
      ts: '2026-06-22T00:00:00Z',
      driver: 'browser',
      action: 'click',
      target: 'button[name=Sign in]',
      status: 'pass',
      screenshotPath: 'screenshots/login/01_pass.png',
    })}\n`,
    expected: /missing settled assertion/,
  },
  {
    name: 'failed event without screenshot',
    events: `${JSON.stringify({
      runId: 'run-1',
      flow: 'login',
      step: 'submit credentials',
      eventId: 'evt-1',
      ts: '2026-06-22T00:00:00Z',
      driver: 'browser',
      action: 'click',
      target: 'button[name=Sign in]',
      assertion: 'dashboard is visible',
      status: 'fail',
      logPath: 'logs/login.log',
    })}\n`,
    extraFiles: [['logs/login.log', 'error']],
    expected: /failed without screenshot evidence/,
  },
  {
    name: 'report omits regression',
    report: [
      'Driver used: Codex Browser. No fallback.',
      'Issues: none unresolved.',
      '2x cursor recap desktop: recaps/login_desktop_2x_cursor.mp4.',
      '2x cursor recap mobile: recaps/login_mobile_2x_cursor.mp4.',
    ].join('\n'),
    expected: /omits regression/,
  },
  {
    name: 'unresolved issue checkbox',
    issues: '- [ ] resolved\n',
    expected: /unresolved issue checkboxes/,
  },
];

for (const item of failureCases) {
  test(`artifact checker rejects ${item.name}`, () => {
    const runDir = makeRunDir('failure-case');
    writeCompleteRun(runDir, {
      events: item.omitEvents ? null : item.events,
      report: item.report,
      issues: item.issues,
    });
    if (item.omitEvents) {
      writeFile(runDir, 'events.jsonl.disabled', 'not used');
    }
    for (const [rel, text] of item.extraFiles ?? []) {
      writeFile(runDir, rel, text);
    }

    const result = runChecker(runDir);
    assert.notEqual(result.status, 0);
    assert.match(result.stdout, item.expected);
  });
}

test('artifact checker rejects missing required videos even with fallback text', () => {
  const runDir = makeRunDir('video-fallback');
  writeFile(runDir, 'screenshots/login/01_pass.png', 'png');
  writeFile(runDir, 'issues.md', 'No unresolved issues.\n');
  writeFile(runDir, 'report.md', [
    'Driver used: local script fallback.',
    'Issues: none unresolved.',
    'Regression commands: npm test -> pass.',
    'Video unavailable: driver unsupported.',
    '2x recap unavailable: encoder unsupported.',
  ].join('\n'));
  writeFile(runDir, 'events.jsonl', `${JSON.stringify({
    runId: 'run-1',
    flow: 'login',
    step: 'submit credentials',
    eventId: 'evt-1',
    ts: '2026-06-22T00:00:00Z',
    driver: 'local-script',
    action: 'click',
    target: 'button[name=Sign in]',
    assertion: 'dashboard is visible',
    status: 'pass',
    screenshotPath: 'screenshots/login/01_pass.png',
  })}\n`);

  const result = runChecker(runDir);
  assert.notEqual(result.status, 0);
  assert.match(result.stdout, /desktop video is expected/);
  assert.match(result.stdout, /mobile 2x recap is expected/);
});

test('artifact checker accepts optional video fallback for incomplete visual proof reports', () => {
  const runDir = makeRunDir('video-optional-fallback');
  writeFile(runDir, 'screenshots/login/01_pass.png', 'png');
  writeFile(runDir, 'issues.md', 'No unresolved issues.\n');
  writeFile(runDir, 'report.md', [
    'Driver used: local script fallback.',
    'Issues: none unresolved.',
    'Regression commands: npm test -> pass.',
    'Video unavailable: driver unsupported.',
    '2x recap unavailable: encoder unsupported.',
  ].join('\n'));
  writeFile(runDir, 'events.jsonl', `${JSON.stringify({
    runId: 'run-1',
    flow: 'login',
    step: 'submit credentials',
    eventId: 'evt-1',
    ts: '2026-06-22T00:00:00Z',
    driver: 'local-script',
    action: 'click',
    target: 'button[name=Sign in]',
    assertion: 'dashboard is visible',
    status: 'pass',
    screenshotPath: 'screenshots/login/01_pass.png',
  })}\n`);

  const result = runChecker(runDir, ['--video', 'optional']);
  assert.equal(result.status, 0, result.stdout + result.stderr);
});

test('artifact checker rejects missing mobile video from an otherwise captured run', () => {
  const runDir = makeRunDir('missing-mobile');
  writeCompleteRun(runDir);
  fs.unlinkSync(path.join(runDir, 'videos/login_mobile.mp4'));
  fs.unlinkSync(path.join(runDir, 'recaps/login_mobile_2x_cursor.mp4'));

  const result = runChecker(runDir);
  assert.notEqual(result.status, 0);
  assert.match(result.stdout, /mobile video is expected/);
  assert.match(result.stdout, /mobile 2x recap is expected/);
});
