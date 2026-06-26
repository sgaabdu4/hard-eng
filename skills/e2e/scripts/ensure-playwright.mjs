#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';

const args = process.argv.slice(2);
const install = args.includes('--install');
const withBrowser = args.includes('--with-browser');
const browserIndex = args.indexOf('--browser');
const installDirIndex = args.indexOf('--install-dir');
const browser = browserIndex === -1 ? 'chromium' : args[browserIndex + 1];
const home = process.env.HOME || process.cwd();
const installDir = path.resolve(
  installDirIndex === -1
    ? path.join(home, '.cache', 'hard-eng', 'e2e-playwright')
    : args[installDirIndex + 1],
);

function candidateRoots() {
  const roots = [];
  if (process.env.PLAYWRIGHT_NODE_MODULE_DIR) roots.push(process.env.PLAYWRIGHT_NODE_MODULE_DIR);
  if (process.env.E2E_PLAYWRIGHT_HOME) roots.push(path.join(process.env.E2E_PLAYWRIGHT_HOME, 'node_modules'));

  let current = process.cwd();
  while (true) {
    roots.push(path.join(current, 'node_modules'));
    const next = path.dirname(current);
    if (next === current) break;
    current = next;
  }

  roots.push(path.join(installDir, 'node_modules'));
  return Array.from(new Set(roots));
}

function findPlaywright() {
  for (const nodeModuleDir of candidateRoots()) {
    const packagePath = path.join(nodeModuleDir, 'playwright', 'package.json');
    if (!fs.existsSync(packagePath)) continue;
    const pkg = JSON.parse(fs.readFileSync(packagePath, 'utf8'));
    return {
      status: 'ready',
      version: pkg.version,
      packagePath,
      nodeModuleDir,
    };
  }
  return null;
}

function print(result) {
  console.log(JSON.stringify(result, null, 2));
}

const ready = findPlaywright();
if (ready) {
  print(ready);
  process.exit(0);
}

if (!install) {
  print({
    status: 'missing',
    installDir,
    command: `node <skill-dir>/scripts/ensure-playwright.mjs --install --with-browser ${browser}`,
  });
  process.exit(1);
}

fs.mkdirSync(installDir, { recursive: true });

const npm = process.platform === 'win32' ? 'npm.cmd' : 'npm';
const installResult = spawnSync(npm, ['install', '--prefix', installDir, 'playwright@latest'], {
  encoding: 'utf8',
});
if (installResult.status !== 0) {
  print({
    status: 'install-failed',
    installDir,
    stderr: installResult.stderr.trim(),
  });
  process.exit(installResult.status || 1);
}

if (withBrowser) {
  const bin = path.join(installDir, 'node_modules', '.bin', process.platform === 'win32' ? 'playwright.cmd' : 'playwright');
  const browserResult = spawnSync(bin, ['install', browser], { encoding: 'utf8' });
  if (browserResult.status !== 0) {
    print({
      status: 'browser-install-failed',
      installDir,
      browser,
      stderr: browserResult.stderr.trim(),
    });
    process.exit(browserResult.status || 1);
  }
}

const installed = findPlaywright();
if (!installed) {
  print({ status: 'missing-after-install', installDir });
  process.exit(1);
}

print({
  ...installed,
  installed: true,
  browserInstalled: withBrowser ? browser : false,
});
