#!/usr/bin/env node
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';

const home = process.env.HOME;
const repo = path.join(home, '.agents');
const featureName = 'default_mode_request_user_input';
const installText = fs.readFileSync(path.join(repo, 'scripts', 'install.sh'), 'utf8');
const codexConfigPath = path.join(home, '.codex', 'config.toml');
const codexConfigText = fs.readFileSync(codexConfigPath, 'utf8');

function section(text, name) {
  const lines = text.split(/\r?\n/);
  const header = new RegExp(`^\\s*\\[${name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\]\\s*(?:#.*)?$`);
  let start = -1;
  for (let index = 0; index < lines.length; index += 1) {
    if (header.test(lines[index])) {
      start = index + 1;
      break;
    }
  }
  if (start === -1) return '';
  const end = lines.findIndex((line, offset) => offset >= start && /^\s*\[/.test(line));
  return lines.slice(start, end === -1 ? undefined : end).join('\n');
}

const featureAssignment = new RegExp(`^\\s*${featureName}\\s*=\\s*true\\s*(?:#.*)?$`, 'm');
const featuresSection = section(codexConfigText, 'features');

assert.ok(
  installText.includes(`("${featureName}", "true")`),
  `scripts/install.sh must manage features.${featureName}`,
);
assert.match(
  featuresSection,
  featureAssignment,
  `${codexConfigPath} must have [features].${featureName} = true; run scripts/install.sh`,
);

console.log('codex-config-sync: pass');
