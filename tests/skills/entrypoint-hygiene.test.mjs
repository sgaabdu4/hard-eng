#!/usr/bin/env node
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';

const repo = path.resolve(new URL('../..', import.meta.url).pathname);
const skillsRoot = path.join(repo, 'skills');
const maxSkillLines = 45;

const repoOwnedSkills = fs.readdirSync(skillsRoot, { withFileTypes: true })
  .filter((entry) => entry.isDirectory())
  .filter((entry) => fs.existsSync(path.join(skillsRoot, entry.name, 'SKILL.md')))
  .map((entry) => entry.name)
  .sort();

assert.ok(repoOwnedSkills.length > 0, 'repo-owned skills must be discoverable');

for (const skill of repoOwnedSkills) {
  const skillDir = path.join(skillsRoot, skill);
  const skillPath = path.join(skillDir, 'SKILL.md');
  const text = fs.readFileSync(skillPath, 'utf8');
  const lines = text.trimEnd().split('\n');
  assert.ok(
    lines.length <= maxSkillLines,
    `${skill}/SKILL.md has ${lines.length} lines; move workflow/reference detail into references/*.md`,
  );
  if (/workflow|runbook|during the session|file structure/i.test(text)) {
    const hasReference = fs.existsSync(path.join(skillDir, 'references'));
    assert.ok(hasReference, `${skill}/SKILL.md names workflow-like detail but has no references/ directory`);
  }
}

console.log('skill-entrypoint-hygiene: pass');
