#!/usr/bin/env node
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const protect = require('../hooks/claude-code-hooks/protect-secrets.js');

function assertBlocked(result, id) {
  assert.equal(result.blocked, true, `expected block ${id}`);
  assert.equal(result.pattern.id, id);
}

function assertAllowed(result, message) {
  assert.equal(result.blocked, false, message);
}

assertBlocked(protect.checkFilePath('/repo/.env.local'), 'env-file');
assertBlocked(protect.checkBashCommand('cat .env.local'), 'read-env');
assertBlocked(protect.checkBashCommand('node --env-file=.env.local scripts/run.ts'), 'env-file-loader');
assertBlocked(protect.checkBashCommand('DOTENV_CONFIG_PATH=.env.local tsx -r dotenv/config scripts/run.ts'), 'dotenv-config-path');
assertBlocked(protect.checkBashCommand('set -a && source .env.local && npm run task'), 'source-env');
assertBlocked(protect.checkBashCommand('xargs -a .env.local'), 'export-env-file');
assertAllowed(protect.checkFilePath('/repo/.env.example'), '.env.example path should remain allowed');
assertAllowed(protect.checkBashCommand('cat .env.example'), '.env.example command should remain allowed');

const tempRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'protect-secrets-env-'));
const projectDir = path.join(tempRoot, 'project');
const srcDir = path.join(projectDir, 'src');
fs.mkdirSync(srcDir, { recursive: true });
fs.writeFileSync(path.join(projectDir, '.env.local'), 'API_KEY=real-key\n');

assertBlocked(
  protect.checkBashCommand('npm run dev', 'high', { cwd: projectDir }),
  'package-script-env-autoload',
);
assertBlocked(
  protect.checkBashCommand('node -r dotenv/config app.ts', 'high', { cwd: projectDir }),
  'dotenv-require',
);
assertBlocked(
  protect.checkBashCommand('vite dev', 'high', { cwd: srcDir }),
  'framework-env-autoload',
);
assertBlocked(
  protect.checkBashCommand(`cd ${projectDir} && npm test`, 'high', { cwd: tempRoot }),
  'package-script-env-autoload',
);

const safeDir = path.join(tempRoot, 'safe');
fs.mkdirSync(safeDir, { recursive: true });
fs.writeFileSync(path.join(safeDir, '.env.example'), 'API_KEY=fake\n');
assertAllowed(
  protect.checkBashCommand('npm run dev', 'high', { cwd: safeDir }),
  'only .env.example should not block package scripts',
);

fs.rmSync(tempRoot, { recursive: true, force: true });

console.log('protect-secrets-env: pass');
