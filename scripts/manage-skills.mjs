#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';

const root = path.resolve(new URL('..', import.meta.url).pathname);
const skillsRoot = path.join(root, 'skills');
const home = process.env.HOME || '';
const configPath = process.env.HARD_ENG_SKILL_CONFIG || path.join(home, '.config', 'hard-eng', 'skills.json');
const skillDirs = [
  path.join(home, '.codex', 'skills'),
  path.join(home, '.copilot', 'skills'),
  path.join(home, '.pi', 'skills'),
  path.join(home, '.pi', 'agent', 'skills'),
];

function fail(message) {
  console.error(`manage-skills: ${message}`);
  process.exit(1);
}

function hasText(value) {
  return typeof value === 'string' && value.trim().length > 0;
}

function availableSkills() {
  return fs.readdirSync(skillsRoot, { withFileTypes: true })
    .filter((entry) => entry.isDirectory() || entry.isSymbolicLink())
    .map((entry) => entry.name)
    .filter((name) => fs.existsSync(path.join(skillsRoot, name, 'SKILL.md')))
    .sort();
}

function readConfigSelection() {
  if (!fs.existsSync(configPath)) return '';
  try {
    const parsed = JSON.parse(fs.readFileSync(configPath, 'utf8'));
    if (typeof parsed.selection === 'string') return parsed.selection;
    if (Array.isArray(parsed.skills)) return parsed.skills.join(',');
  } catch (error) {
    fail(`cannot read ${configPath}: ${error.message}`);
  }
  return '';
}

function normalizeSelection(raw) {
  const value = hasText(raw) ? raw.trim() : 'all';
  if (['all', '*'].includes(value)) return { mode: 'all', names: [] };
  if (['none', 'off', 'skip'].includes(value)) return { mode: 'none', names: [] };
  const names = [...new Set(value.split(',').map((item) => item.trim()).filter(Boolean))].sort();
  if (!names.length) return { mode: 'all', names: [] };
  const available = new Set(availableSkills());
  const unknown = names.filter((name) => !available.has(name));
  if (unknown.length) fail(`unknown skill(s): ${unknown.join(', ')}. Available: ${availableSkills().join(', ')}`);
  return { mode: 'custom', names };
}

function selectedSkillNames() {
  const raw = hasText(process.env.HARD_ENG_SKILLS) ? process.env.HARD_ENG_SKILLS : readConfigSelection();
  const selection = normalizeSelection(raw);
  if (selection.mode === 'all') return availableSkills();
  if (selection.mode === 'none') return [];
  return selection.names;
}

function isManagedSkillLink(target) {
  const stat = fs.lstatSync(target, { throwIfNoEntry: false });
  if (!stat?.isSymbolicLink()) return false;
  const link = fs.readlinkSync(target);
  return link === skillsRoot || link.startsWith(`${skillsRoot}${path.sep}`);
}

function removeIfManaged(target) {
  if (isManagedSkillLink(target)) fs.rmSync(target, { force: true });
}

function applySelection() {
  const selected = new Set(selectedSkillNames());
  const available = availableSkills();
  for (const dir of skillDirs) {
    fs.mkdirSync(dir, { recursive: true });
    for (const entry of fs.readdirSync(dir)) {
      const target = path.join(dir, entry);
      if (isManagedSkillLink(target) && !selected.has(entry)) {
        fs.rmSync(target, { force: true });
      }
    }
    for (const name of available) {
      const target = path.join(dir, name);
      const source = path.join(skillsRoot, name);
      if (!selected.has(name)) {
        removeIfManaged(target);
        continue;
      }
      if (fs.existsSync(target) || fs.lstatSync(target, { throwIfNoEntry: false })?.isSymbolicLink()) {
        if (isManagedSkillLink(target) && fs.readlinkSync(target) !== source) {
          fs.rmSync(target, { force: true });
        } else {
          continue;
        }
      }
      fs.symlinkSync(source, target, 'dir');
    }
  }
  console.log(`manage-skills: installed ${selected.size ? [...selected].join(', ') : 'none'}`);
}

function removeManaged() {
  for (const dir of skillDirs) {
    if (!fs.existsSync(dir)) continue;
    for (const entry of fs.readdirSync(dir)) {
      removeIfManaged(path.join(dir, entry));
    }
  }
  console.log('manage-skills: removed managed skill links');
}

function writeConfig(raw) {
  const selection = normalizeSelection(raw);
  const stored = selection.mode === 'custom' ? selection.names.join(',') : selection.mode;
  fs.mkdirSync(path.dirname(configPath), { recursive: true });
  fs.writeFileSync(configPath, `${JSON.stringify({ selection: stored }, null, 2)}\n`);
  console.log(`manage-skills: saved selection ${stored}`);
}

const [command, value] = process.argv.slice(2);
if (command === 'list') {
  console.log(availableSkills().join('\n'));
} else if (command === 'configure') {
  writeConfig(value || process.env.HARD_ENG_SKILLS || 'all');
} else if (command === 'apply') {
  applySelection();
} else if (command === 'remove') {
  removeManaged();
} else if (command === 'resolve') {
  console.log(selectedSkillNames().join('\n'));
} else {
  console.error('Usage: manage-skills.mjs list | configure <all|none|skill-a,skill-b> | apply | remove | resolve');
  process.exit(2);
}
