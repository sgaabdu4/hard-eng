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

for (const skill of ['implement', 'improve-codebase-architecture', 'resolving-merge-conflicts']) {
  const skillDir = path.join(skillsRoot, skill);
  const skillText = fs.readFileSync(path.join(skillDir, 'SKILL.md'), 'utf8');
  const workflowPath = path.join(skillDir, 'references', 'workflow.md');
  assert.ok(fs.existsSync(workflowPath), `${skill}/SKILL.md must disclose its workflow through references/workflow.md`);
  assert.match(skillText, /Load `references\/workflow\.md`/, `${skill}/SKILL.md must point to references/workflow.md`);
  const body = skillText.replace(/^---\n[\s\S]*?\n---\n/, '');
  const workflowSteps = body.match(/^(?:-\s+)?(?:Use|Run|Once|Prepare|Read|Trace|Preserve|Continue|Explore|Write|Ask)\b/gm) || [];
  assert.ok(workflowSteps.length < 3, `${skill}/SKILL.md must keep three-or-more-step workflows in references/workflow.md`);
}

console.log('skill-entrypoint-hygiene: pass');
