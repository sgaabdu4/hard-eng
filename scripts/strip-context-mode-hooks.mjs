#!/usr/bin/env node
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const defaultTargets = [
  path.join(scriptDir, '..', 'codex', 'hooks.json'),
  path.join(os.homedir(), '.codex', 'hooks.json'),
  path.join(os.homedir(), '.codex', 'settings.json'),
  path.join(os.homedir(), '.claude', 'settings.json'),
  path.join(os.homedir(), '.claude', 'settings.local.json'),
  path.join(os.homedir(), '.copilot', 'settings.json'),
  path.join(os.homedir(), '.pi', 'settings.json'),
  path.join(os.homedir(), '.pi', 'agent', 'settings.json'),
];
const targets = process.argv.slice(2).length > 0 ? process.argv.slice(2) : defaultTargets;
const seen = new Set();
let totalRemoved = 0;

function expandTarget(target) {
  if (target === '~') return os.homedir();
  if (target.startsWith('~/')) return path.join(os.homedir(), target.slice(2));
  return path.resolve(target);
}

function isContextModeHook(hook) {
  return typeof hook?.command === 'string' && /\bcontext-mode\s+hook\b/.test(hook.command);
}

function isEmptyHookEntry(value) {
  return value && typeof value === 'object' && !Array.isArray(value) && Array.isArray(value.hooks) && value.hooks.length === 0;
}

function stripHooks(data) {
  let removed = 0;

  function visit(value) {
    if (Array.isArray(value)) {
      for (let index = value.length - 1; index >= 0; index -= 1) {
        const item = value[index];
        if (isContextModeHook(item)) {
          value.splice(index, 1);
          removed += 1;
          continue;
        }
        visit(item);
        if (isEmptyHookEntry(item)) value.splice(index, 1);
      }
      return;
    }

    if (!value || typeof value !== 'object') return;
    for (const [key, child] of Object.entries(value)) {
      visit(child);
      if (key === 'hooks' && child && typeof child === 'object' && !Array.isArray(child)) {
        for (const [event, entries] of Object.entries(child)) {
          if (Array.isArray(entries) && entries.length === 0) delete child[event];
        }
      }
    }
  }

  visit(data);
  return removed;
}

for (const target of targets) {
  const hookPath = expandTarget(target);
  if (!fs.existsSync(hookPath)) continue;
  const realPath = fs.realpathSync(hookPath);
  if (seen.has(realPath)) continue;
  seen.add(realPath);

  const data = JSON.parse(fs.readFileSync(realPath, 'utf8'));
  const removed = stripHooks(data);
  if (removed === 0) continue;

  fs.writeFileSync(realPath, `${JSON.stringify(data, null, 2)}\n`);
  totalRemoved += removed;
  console.log(`Removed ${removed} context-mode hook(s) from ${hookPath}`);
}

if (totalRemoved === 0) console.log('No context-mode hooks found.');
