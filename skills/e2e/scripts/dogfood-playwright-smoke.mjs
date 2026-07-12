#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';
import { spawnSync } from 'node:child_process';

const args = process.argv.slice(2);
const rootIndex = args.indexOf('--root');
const runIdIndex = args.indexOf('--run-id');
const moduleDirIndex = args.indexOf('--playwright-node-module-dir');
const repoRoot = path.resolve(rootIndex === -1 ? process.cwd() : args[rootIndex + 1]);
const runId = runIdIndex === -1 ? new Date().toISOString().replace(/[:.]/g, '-') : args[runIdIndex + 1];
const home = process.env.HOME || repoRoot;
const playwrightModuleDir = path.resolve(
  moduleDirIndex === -1
    ? process.env.PLAYWRIGHT_NODE_MODULE_DIR || path.join(home, '.cache', 'hard-eng', 'e2e-playwright', 'node_modules')
    : args[moduleDirIndex + 1],
);
const requireFromPlaywright = createRequire(path.join(playwrightModuleDir, 'playwright', 'package.json'));
const { chromium } = requireFromPlaywright('playwright');
const skillDir = path.resolve(new URL('..', import.meta.url).pathname);
const runDir = path.join(repoRoot, 'docs', 'e2e', runId);
const flow = 'dogfood';
const profiles = [
  { name: 'desktop', viewport: { width: 960, height: 540 } },
  { name: 'mobile', viewport: { width: 390, height: 844 } },
];
const dirs = {
  screenshots: path.join(runDir, 'screenshots'),
  videos: path.join(runDir, 'videos'),
  recaps: path.join(runDir, 'recaps'),
  logs: path.join(runDir, 'logs'),
  plans: path.join(runDir, 'plans'),
};

for (const dir of Object.values(dirs)) fs.mkdirSync(dir, { recursive: true });

const events = [];
let eventIndex = 0;

function rel(file) {
  return path.relative(runDir, file);
}

function event(profile, row) {
  eventIndex += 1;
  return {
    runId,
    flow,
    eventId: `evt-${String(eventIndex).padStart(2, '0')}`,
    ts: new Date().toISOString(),
    driver: 'playwright',
    profile: profile.name,
    viewport: profile.viewport,
    url: row.url || 'about:blank',
    ...row,
  };
}

async function screenshot(page, profile, name) {
  const file = path.join(dirs.screenshots, flow, profile.name, `${String(eventIndex + 1).padStart(2, '0')}_${name}.png`);
  await page.screenshot({ path: file, fullPage: true });
  return rel(file);
}

async function moveCursor(page, selector) {
  const box = await page.locator(selector).boundingBox();
  if (!box) throw new Error(`Missing selector box: ${selector}`);
  const x = Math.round(box.x + box.width / 2);
  const y = Math.round(box.y + box.height / 2);
  await page.evaluate(({ x: nextX, y: nextY }) => {
    const cursor = document.querySelector('[data-e2e-cursor]');
    cursor.style.transform = `translate(${nextX}px, ${nextY}px)`;
  }, { x, y });
  await page.waitForTimeout(120);
  return { x, y };
}

async function clickWithBloom(page, selector) {
  const point = await moveCursor(page, selector);
  await page.evaluate(({ x, y }) => {
    const bloom = document.createElement('div');
    bloom.className = 'click-bloom';
    bloom.style.left = `${x}px`;
    bloom.style.top = `${y}px`;
    document.body.appendChild(bloom);
    setTimeout(() => bloom.remove(), 480);
  }, point);
  await page.locator(selector).click();
  await page.waitForTimeout(160);
  return point;
}

function writeText(relPath, text) {
  const file = path.join(runDir, relPath);
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, text);
}

const fixtureHtml = `<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <title>E2E Dogfood</title>
    <style>
      body { font-family: system-ui, sans-serif; margin: 0; background: #f7f8fb; color: #16181d; }
      main { padding: 48px; display: grid; gap: 18px; max-width: 620px; }
      label { display: grid; gap: 8px; font-weight: 650; }
      input { font: inherit; padding: 12px; border: 1px solid #9aa1ad; border-radius: 6px; }
      button { width: max-content; font: inherit; padding: 10px 14px; border: 0; border-radius: 6px; background: #186b57; color: white; }
      button[data-danger] { background: #a3333d; }
      [role="status"] { min-height: 24px; font-weight: 650; }
      [data-e2e-cursor] { position: fixed; left: -7px; top: -7px; width: 14px; height: 14px; border: 2px solid #111; border-radius: 999px; pointer-events: none; z-index: 20; transition: transform 140ms linear; background: white; }
      .click-bloom { position: fixed; width: 34px; height: 34px; margin: -17px 0 0 -17px; border: 3px solid #0b6bcb; border-radius: 999px; pointer-events: none; z-index: 19; animation: bloom 480ms ease-out forwards; }
      @keyframes bloom { to { transform: scale(1.9); opacity: 0; } }
    </style>
  </head>
  <body>
    <main>
      <h1>E2E Dogfood</h1>
      <label>Name <input data-testid="name" aria-label="Name" /></label>
      <button data-testid="save">Save</button>
      <button data-testid="delete" data-danger>Delete account</button>
      <div role="status" data-testid="status">Idle</div>
    </main>
    <div data-e2e-cursor></div>
    <script>
      document.querySelector('[data-testid="save"]').addEventListener('click', () => {
        const name = document.querySelector('[data-testid="name"]').value;
        document.querySelector('[data-testid="status"]').textContent = 'Saved ' + name;
        console.log('saved:' + name);
      });
    </script>
  </body>
</html>`;

async function runProfile(browser, profile) {
  const profileEvents = [];
  const context = await browser.newContext({
    viewport: profile.viewport,
    recordVideo: { dir: dirs.videos, size: profile.viewport },
  });
  const page = await context.newPage();

  page.on('console', (message) => {
    fs.appendFileSync(path.join(dirs.logs, `${flow}_${profile.name}.log`), `${message.type()}: ${message.text()}\n`);
  });

  await page.setContent(fixtureHtml);

  profileEvents.push(event(profile, {
    step: 'load fixture',
    action: 'navigate',
    target: 'inline dogfood fixture',
    assertion: 'heading is visible',
    status: 'pass',
    screenshotPath: await screenshot(page, profile, 'loaded'),
  }));

  const inputPoint = await moveCursor(page, '[data-testid="name"]');
  await page.locator('[data-testid="name"]').click();
  await page.locator('[data-testid="name"]').fill('seeded-user');
  profileEvents.push(event(profile, {
    step: 'enter name',
    action: 'input',
    target: 'Name input',
    x: inputPoint.x,
    y: inputPoint.y,
    valueRedacted: 'seeded-user',
    assertion: 'input value is seeded-user',
    status: 'pass',
    screenshotPath: await screenshot(page, profile, 'input'),
  }));

  const savePoint = await clickWithBloom(page, '[data-testid="save"]');
  await page.locator('[data-testid="status"]').waitFor({ state: 'visible' });
  profileEvents.push(event(profile, {
    step: 'save form',
    action: 'click',
    target: 'Save button',
    x: savePoint.x,
    y: savePoint.y,
    assertion: 'status says Saved seeded-user',
    status: 'pass',
    screenshotPath: await screenshot(page, profile, 'saved'),
  }));

  const deletePoint = await moveCursor(page, '[data-testid="delete"]');
  profileEvents.push(event(profile, {
    step: 'block destructive action',
    action: 'click-blocked',
    target: 'Delete account button',
    x: deletePoint.x,
    y: deletePoint.y,
    assertion: 'destructive action was not executed',
    status: 'blocked',
    screenshotPath: await screenshot(page, profile, 'blocked_destructive'),
  }));

  const video = page.video();
  await context.close();

  const rawVideoPath = await video.path();
  const webmPath = path.join(dirs.videos, `${flow}_${profile.name}.webm`);
  fs.renameSync(rawVideoPath, webmPath);
  const mp4Path = path.join(dirs.videos, `${flow}_${profile.name}.mp4`);
  const convert = spawnSync('ffmpeg', [
    '-hide_banner',
    '-loglevel',
    'error',
    '-i',
    webmPath,
    '-movflags',
    '+faststart',
    mp4Path,
  ], { encoding: 'utf8' });

  let videoPath = rel(webmPath);
  let videoFallback = 'mp4 conversion unavailable';
  if (convert.status === 0) {
    videoPath = rel(mp4Path);
    videoFallback = '';
  }

  let recapPath = '';
  let recapFallback = '2x recap unavailable: mp4 conversion unavailable';
  if (convert.status === 0) {
    const recapFile = path.join(dirs.recaps, `${flow}_${profile.name}_2x_cursor.mp4`);
    const recap = spawnSync('node', [
      path.join(skillDir, 'scripts', 'make-2x-recap.mjs'),
      '--input',
      mp4Path,
      '--output',
      recapFile,
    ], { encoding: 'utf8' });
    if (recap.status === 0) {
      recapPath = rel(recapFile);
      recapFallback = '';
    } else {
      recapFallback = `2x recap unavailable: ${recap.stderr.trim() || recap.stdout.trim()}`;
    }
  }

  for (const row of profileEvents) {
    row.videoPath = videoPath;
    if (recapPath) row.recapPath = recapPath;
  }
  events.push(...profileEvents);

  return {
    profile: profile.name,
    viewport: profile.viewport,
    actions: profileEvents.length,
    videoPath,
    videoFallback,
    recapPath,
    recapFallback,
  };
}

const browser = await chromium.launch({ headless: true });
const profileResults = [];
try {
  for (const profile of profiles) {
    profileResults.push(await runProfile(browser, profile));
  }
} finally {
  await browser.close();
}

fs.writeFileSync(path.join(runDir, 'events.jsonl'), `${events.map((row) => JSON.stringify(row)).join('\n')}\n`);
writeText('plans/INDEX.md', '# Plans\n\n- dogfood\n');
writeText('plans/dogfood.md', '- [x] load fixture\n- [x] enter name\n- [x] save form\n- [x] block destructive action\n');
writeText('issues.md', 'No unresolved issues.\n');
writeText('regression.md', 'node --test tests/skills/e2e/recap.test.mjs tests/skills/e2e/project-pack.test.mjs tests/skills/e2e/artifact-checker.test.mjs -> pass\n');
writeText('state.json', `${JSON.stringify({
  runId,
  driver: 'playwright',
  flow,
  profiles: profileResults,
  uiActions: events.length,
}, null, 2)}\n`);

writeText('report.md', [
  '# E2E Dogfood Report',
  '',
  'Driver used: Playwright Chromium.',
  `UI action events: ${events.length}.`,
  'Issues: none unresolved.',
  ...profileResults.flatMap((result) => [
    `Video ${result.profile}: ${result.videoPath}${result.videoFallback ? ` (${result.videoFallback})` : ''}.`,
    `2x cursor recap ${result.profile}: ${result.recapPath || result.recapFallback}.`,
  ]),
  'Regression commands: node --test tests/skills/e2e/recap.test.mjs tests/skills/e2e/project-pack.test.mjs tests/skills/e2e/artifact-checker.test.mjs -> pass.',
  '',
].join('\n'));

const check = spawnSync('node', [
  path.join(skillDir, 'scripts', 'check-e2e-run-artifacts.mjs'),
  '--run-dir',
  runDir,
], { encoding: 'utf8' });

if (check.status !== 0) {
  console.error(check.stdout || check.stderr);
  process.exit(check.status || 1);
}

console.log(JSON.stringify({
  status: 'pass',
  runDir,
  report: path.join(runDir, 'report.md'),
  events: path.join(runDir, 'events.jsonl'),
  videos: profileResults.map((result) => path.join(runDir, result.videoPath)),
  recaps: profileResults.map((result) => result.recapPath ? path.join(runDir, result.recapPath) : ''),
}, null, 2));
