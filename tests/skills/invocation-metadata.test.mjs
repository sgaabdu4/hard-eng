#!/usr/bin/env node
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';

const repo = path.resolve(new URL('../..', import.meta.url).pathname);
const skillsRoot = path.join(repo, 'skills');

const manualOnlySkills = new Set([
  'implement',
]);
const modelOnlySkills = new Set(['terse']);

function read(file) {
  return fs.readFileSync(file, 'utf8');
}

function frontmatter(markdown) {
  const match = markdown.match(/^---\n([\s\S]*?)\n---/);
  assert.ok(match, 'SKILL.md must have frontmatter');
  return match[1];
}

function hasFrontmatterValue(frontmatterText, key, value) {
  return new RegExp(`^${key}:\\s*${value}\\s*$`, 'm').test(frontmatterText);
}

function hasCodexImplicitPolicy(skillDir) {
  const openaiPath = path.join(skillDir, 'agents', 'openai.yaml');
  if (!fs.existsSync(openaiPath)) return false;
  return /^\s*allow_implicit_invocation:\s*false\s*$/m.test(read(openaiPath));
}

const repoOwnedSkills = fs.readdirSync(skillsRoot, { withFileTypes: true })
  .filter((entry) => entry.isDirectory())
  .filter((entry) => fs.existsSync(path.join(skillsRoot, entry.name, 'SKILL.md')))
  .map((entry) => entry.name)
  .sort();

for (const skill of manualOnlySkills) {
  assert.ok(repoOwnedSkills.includes(skill), `${skill} must exist`);
}

for (const skill of repoOwnedSkills) {
  const skillDir = path.join(skillsRoot, skill);
  const metadata = frontmatter(read(path.join(skillDir, 'SKILL.md')));
  const claudeManual = hasFrontmatterValue(metadata, 'disable-model-invocation', 'true');
  const codexManual = hasCodexImplicitPolicy(skillDir);
  const userVisible = hasFrontmatterValue(metadata, 'user-invocable', 'true');
  const modelOnly = hasFrontmatterValue(metadata, 'user-invocable', 'false');

  if (manualOnlySkills.has(skill)) {
    assert.ok(claudeManual, `${skill} must disable model invocation for Claude-style runtimes`);
    assert.ok(codexManual, `${skill} must disable implicit invocation for Codex`);
    assert.ok(userVisible, `${skill} must stay explicitly user-invocable`);
    assert.equal(modelOnly, false, `${skill} cannot be model-only`);
    continue;
  }

  assert.equal(claudeManual, false, `${skill} has disable-model-invocation but is not in manualOnlySkills`);
  assert.equal(codexManual, false, `${skill} has Codex implicit-disable policy but is not in manualOnlySkills`);

  if (modelOnlySkills.has(skill)) {
    assert.ok(modelOnly, `${skill} must be hidden from user slash menus`);
  } else {
    assert.equal(modelOnly, false, `${skill} should remain user-invocable or omit the field`);
  }
}

console.log('skill-invocation-metadata-test: pass');
