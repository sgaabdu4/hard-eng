#!/usr/bin/env node
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

function fail(message) {
  console.error(`no-mistakes-agent-paths: ${message}`);
  process.exit(1);
}

function option(name, fallback = '') {
  const index = process.argv.indexOf(name);
  return index === -1 ? fallback : process.argv[index + 1] || '';
}

function executable(file) {
  try {
    fs.accessSync(file, fs.constants.X_OK);
    return true;
  } catch {
    return false;
  }
}

function yamlScalar(value) {
  const trimmed = value.trim();
  if (trimmed.startsWith('"') && trimmed.endsWith('"')) {
    try {
      return JSON.parse(trimmed);
    } catch {
      return '';
    }
  }
  if (trimmed.startsWith("'") && trimmed.endsWith("'")) return trimmed.slice(1, -1).replaceAll("''", "'");
  return trimmed.replace(/\s+#.*$/, '').trim();
}

const config = path.resolve(option('--config', path.join(process.env.NO_MISTAKES_HOME || path.join(os.homedir(), '.no-mistakes'), 'config.yaml')));
const agent = option('--agent', 'codex');
const binary = path.resolve(option('--binary'));

if (!option('--binary')) fail('--binary is required');
if (!/^[a-z0-9_-]+$/i.test(agent)) fail(`invalid agent name: ${agent}`);
if (!executable(binary)) fail(`replacement is not executable: ${binary}`);
if (!fs.existsSync(config)) {
  console.log(`no-mistakes-agent-paths: skipped missing ${config}`);
  process.exit(0);
}

const original = fs.readFileSync(config, 'utf8');
const lines = original.split('\n');
const section = lines.findIndex((line) => /^agent_path_override:\s*(?:#.*)?$/.test(line));
if (section === -1) {
  console.log('no-mistakes-agent-paths: no override section');
  process.exit(0);
}

let entry = -1;
for (let index = section + 1; index < lines.length; index += 1) {
  if (/^\S/.test(lines[index]) && lines[index].trim()) break;
  if (new RegExp(`^  ${agent}:\\s*`).test(lines[index])) {
    entry = index;
    break;
  }
}
if (entry === -1) {
  console.log(`no-mistakes-agent-paths: no ${agent} override`);
  process.exit(0);
}

const current = yamlScalar(lines[entry].replace(new RegExp(`^  ${agent}:\\s*`), ''));
if (current && executable(current)) {
  console.log(`no-mistakes-agent-paths: preserved executable ${agent} override`);
  process.exit(0);
}

lines[entry] = `  ${agent}: ${JSON.stringify(binary)}`;
const updated = lines.join('\n');
const temp = `${config}.tmp-${process.pid}`;
fs.writeFileSync(temp, updated, { mode: fs.statSync(config).mode });
fs.renameSync(temp, config);
console.log(`no-mistakes-agent-paths: refreshed ${agent} override`);
