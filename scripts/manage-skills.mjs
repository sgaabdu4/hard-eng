#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';

const root = path.resolve(new URL('..', import.meta.url).pathname);
const skillsRoot = path.join(root, 'skills');
const home = process.env.HOME || '';
const configPath = process.env.HARD_ENG_SKILL_CONFIG || path.join(home, '.config', 'hard-eng', 'skills.json');
const rawArgs = process.argv.slice(2);
const dryRun = ['1', 'true', 'TRUE', 'yes', 'YES', 'y', 'Y'].includes(process.env.HARD_ENG_DRY_RUN || '') ||
  rawArgs.includes('--dry-run');
const args = rawArgs.filter((arg) => arg !== '--dry-run');
const skillDirs = [
  path.join(home, '.codex', 'skills'),
  path.join(home, '.copilot', 'skills'),
  path.join(home, '.pi', 'skills'),
  path.join(home, '.pi', 'agent', 'skills'),
];
const retiredUiDecisionSkill = ['lav', 'ish'].join('');
const retiredSkills = new Set([
  retiredUiDecisionSkill,
  'skill-creator',
  'tavily-cli',
  'to-issues',
  'to-prd',
  'to-spec',
  'to-tickets',
  'tvly',
]);
const requiredCustomSkills = new Set(['workflow-help']);

function fail(message) {
  console.error(`manage-skills: ${message}`);
  process.exit(1);
}

function runPreview(command, ...args) {
  console.log(`dry-run: ${[command, ...args].join(' ')}`);
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
  const requestedNames = [...new Set(value.split(',').map((item) => item.trim()).filter(Boolean))].sort();
  if (!requestedNames.length) return { mode: 'all', names: [] };
  const names = requestedNames.filter((name) => !retiredSkills.has(name));
  if (!names.length) return { mode: 'none', names: [] };
  for (const name of requiredCustomSkills) {
    if (!names.includes(name)) names.push(name);
  }
  names.sort();
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
  if (!isManagedSkillLink(target)) return;
  if (dryRun) {
    runPreview('rm -f', target);
    return;
  }
  fs.rmSync(target, { force: true });
}

function applySelection() {
  const selected = new Set(selectedSkillNames());
  const available = availableSkills();
  for (const dir of skillDirs) {
    if (dryRun) {
      runPreview('mkdir -p', dir);
    } else {
      fs.mkdirSync(dir, { recursive: true });
    }
    for (const entry of fs.existsSync(dir) ? fs.readdirSync(dir) : []) {
      const target = path.join(dir, entry);
      if (isManagedSkillLink(target) && !selected.has(entry)) {
        if (dryRun) {
          runPreview('rm -f', target);
        } else {
          fs.rmSync(target, { force: true });
        }
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
          if (dryRun) {
            runPreview('rm -f', target);
          } else {
            fs.rmSync(target, { force: true });
          }
        } else {
          continue;
        }
      }
      if (dryRun) {
        runPreview('ln -s', source, target);
        continue;
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
  console.log(`manage-skills: ${dryRun ? 'would remove' : 'removed'} managed skill links`);
}

function writeConfig(raw) {
  const selection = normalizeSelection(raw);
  const stored = selection.mode === 'custom' ? selection.names.join(',') : selection.mode;
  if (dryRun) {
    runPreview('write', configPath, JSON.stringify({ selection: stored }));
    return;
  }
  fs.mkdirSync(path.dirname(configPath), { recursive: true });
  fs.writeFileSync(configPath, `${JSON.stringify({ selection: stored }, null, 2)}\n`);
  console.log(`manage-skills: saved selection ${stored}`);
}

const [command, value] = args;
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
  console.error('Usage: manage-skills.mjs [--dry-run] list | configure <all|none|skill-a,skill-b> | apply | remove | resolve');
  process.exit(2);
}
