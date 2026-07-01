#!/usr/bin/env node
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';

const root = path.resolve(process.env.AGENTS_HYGIENE_ROOT || process.cwd());
const errors = [];
const tokenChecks = [];

const ignoredDirs = new Set(['.git', 'backups', 'node_modules', 'outputs', 'tmp', 'vendor']);
const allowedAgentsSections = [
  'Stops',
  'Core',
  'Tools',
  'Evidence',
  'Skills',
  'Impl',
];
const maxAgentsLines = 80;
const maxAgentsTokens = 1000;
const maxSkillEntrypointLines = 100;
const maxSkillDescriptionTokens = 30;

function escapeRegExp(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

const localMachinePatterns = [escapeRegExp(os.homedir())];
if (process.env.HARD_ENG_MARKDOWN_PRIVATE_PATTERN) {
  localMachinePatterns.push(process.env.HARD_ENG_MARKDOWN_PRIVATE_PATTERN);
}

const globalRules = [
  {
    name: 'local machine path',
    marker: 'allow-local-machine-paths',
    pattern: new RegExp(localMachinePatterns.join('|')),
  },
  {
    name: 'conversation state',
    marker: 'allow-conversation-state',
    pattern: /\b(this conversation|this session|as discussed|we decided|latest request|current turn)\b/i,
  },
  {
    name: 'setup internals',
    marker: 'allow-setup-internals',
    pattern: /\b(codex-update-stack|codex-watchdog|codex-context-mode-health|ctx_doctor|context-mode hook|SessionStart)\b/,
  },
];

function fail(file, message) {
  errors.push(`${file}: ${message}`);
}

function relative(file) {
  return path.relative(root, file).split(path.sep).join('/');
}

function lineCount(text) {
  return text.split(/\r?\n/).length - (text.endsWith('\n') ? 1 : 0);
}

function addTokenCheck(file, text, maxTokens, label) {
  tokenChecks.push({ file, text, maxTokens, label });
}

function flushTokenChecks() {
  if (tokenChecks.length === 0) return;
  const check = spawnSync('python3', ['-c', `
import json
import sys
import tiktoken
enc = tiktoken.get_encoding("o200k_base")
print(json.dumps([len(enc.encode(text)) for text in json.load(sys.stdin)]))
`], {
    input: JSON.stringify(tokenChecks.map((item) => item.text)),
    encoding: 'utf8',
  });
  if (check.status !== 0) {
    errors.push(`token check failed: ${check.stderr.trim()}`);
    return;
  }
  let counts;
  try {
    counts = JSON.parse(check.stdout);
  } catch (error) {
    errors.push(`token check failed: ${error.message}`);
    return;
  }
  tokenChecks.forEach((item, index) => {
    const count = counts[index];
    if (count > item.maxTokens) {
      fail(item.file, `${item.label}; got ${count}`);
    }
  });
}

function walk(dir, files = []) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    if (ignoredDirs.has(entry.name)) continue;
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      walk(fullPath, files);
      continue;
    }
    if (entry.isFile() && entry.name.endsWith('.md')) files.push(fullPath);
  }
  return files;
}

function isRepoSkillEntrypoint(file) {
  return /^skills\/[^/]+\/SKILL\.md$/.test(file);
}

function ownsRule(text, marker) {
  return text.split('\n').slice(0, 12).some((line) => {
    const trimmed = line.trim();
    return trimmed === `markdown-hygiene: ${marker}` ||
      trimmed === `<!-- markdown-hygiene: ${marker} -->`;
  });
}

function checkGlobalMarkdown(file, text) {
  for (const rule of globalRules) {
    if (rule.pattern.test(text) && !ownsRule(text, rule.marker)) {
      fail(file, `${rule.name} requires explicit markdown-hygiene: ${rule.marker}`);
    }
  }
  for (const [index, line] of text.split('\n').entries()) {
    if (/^\s*[-*+]\s+.*\.\s*$/.test(line)) {
      fail(file, `line ${index + 1} bullet must not end with a full stop`);
    }
  }
}

function checkAgents(file, text) {
  if (!text.startsWith('# Agent Rules\n\n## Stops\n')) {
    fail(file, 'must start with title then the first rule section');
  }
  const lines = lineCount(text);
  if (lines > maxAgentsLines) fail(file, `must stay at or under ${maxAgentsLines} lines; got ${lines}`);
  addTokenCheck(file, text, maxAgentsTokens, `must stay at or under ${maxAgentsTokens} tokens`);

  let inFence = false;
  for (const [index, line] of text.split('\n').entries()) {
    const lineNumber = index + 1;
    const trimmed = line.trim();
    if (trimmed.startsWith('```')) {
      inFence = !inFence;
      continue;
    }
    if (inFence || trimmed === '') continue;
    if (trimmed === '# Agent Rules') continue;
    if (trimmed.startsWith('## ')) {
      const section = trimmed.slice(3);
      if (!allowedAgentsSections.includes(section)) {
        fail(file, `line ${lineNumber} uses an unapproved section: ${section}`);
      }
      continue;
    }
    if (trimmed.startsWith('- ')) continue;
    fail(file, `line ${lineNumber} is free prose; use a bullet, heading, or fenced template`);
  }
  if (inFence) fail(file, 'has an unclosed fenced block');
}

function checkSkill(file, text) {
  const lines = lineCount(text);
  if (lines > maxSkillEntrypointLines) fail(file, `must stay at or under ${maxSkillEntrypointLines} lines; got ${lines}`);
  let inFence = false;
  let consecutiveWorkflowSteps = 0;
  for (const [index, line] of text.split('\n').entries()) {
    if (line.trim().startsWith('```')) {
      inFence = !inFence;
      consecutiveWorkflowSteps = 0;
      continue;
    }
    if (inFence) continue;
    if (/^\s*\d+\.\s+\S/.test(line)) {
      consecutiveWorkflowSteps += 1;
      if (consecutiveWorkflowSteps >= 3) {
        fail(file, `line ${index + 1} has a 3+ step workflow; move detailed workflow to references/*.md or scripts`);
        break;
      }
    } else {
      consecutiveWorkflowSteps = 0;
    }
  }
  if (inFence) fail(file, 'has an unclosed fenced block');
  const frontmatter = text.match(/^---\n([\s\S]*?)\n---/);
  if (!frontmatter) {
    fail(file, 'must have YAML frontmatter');
    return;
  }
  const description = frontmatter[1]
    .split('\n')
    .find((line) => line.startsWith('description:'))
    ?.replace(/^description:\s*/, '')
    .trim();
  if (!description) {
    fail(file, 'must have a description');
    return;
  }
  if (['>-', '>', '|'].includes(description)) {
    fail(file, 'description must stay one line to control prompt tokens');
    return;
  }
  addTokenCheck(file, description, maxSkillDescriptionTokens, `description must stay at or under ${maxSkillDescriptionTokens} tokens`);
}

for (const absolutePath of walk(root)) {
  const file = relative(absolutePath);
  const text = fs.readFileSync(absolutePath, 'utf8').replace(/\r\n/g, '\n');
  checkGlobalMarkdown(file, text);
  if (file === 'AGENTS.md') checkAgents(file, text);
  if (isRepoSkillEntrypoint(file)) checkSkill(file, text);
}

flushTokenChecks();

if (errors.length > 0) {
  console.error(`markdown-hygiene: ${errors.length} failure(s)`);
  for (const error of errors) console.error(`- ${error}`);
  process.exit(1);
}

console.log('markdown-hygiene: pass');
