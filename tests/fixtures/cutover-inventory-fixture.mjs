import fs from 'node:fs';
import path from 'node:path';
import { sha256 } from '../../runtime/lib/canonical.mjs';
import { inspectSetupTarget } from '../../runtime/lib/setup-transaction.mjs';

export function seedApprovedLegacyLinks(home, approvedInventory) {
  const skillsRoot = path.join(home, '.codex', 'skills');
  fs.mkdirSync(skillsRoot, { recursive: true });
  for (const name of Object.keys(approvedInventory.legacy_skill_links)) {
    fs.symlinkSync(
      path.join(home, '.agents', 'skills', name),
      path.join(skillsRoot, name),
    );
  }
  for (const relative of Object.keys(approvedInventory.legacy_backup_links)) {
    const target = relative.includes('/AGENTS.md.backup.')
      ? path.join(home, '.agents', 'AGENTS.md')
      : path.join(home, '.agents', 'codex', 'hooks.json');
    fs.symlinkSync(target, path.join(home, relative));
  }
}

export function fixtureRetirementInventory(home, approvedInventory) {
  const customAgents = Object.fromEntries(
    Object.keys(approvedInventory.custom_agents).map((name) => [name, {
      ...approvedInventory.custom_agents[name],
      hash: sha256(fs.readFileSync(path.join(home, '.codex', 'agents', name))),
    }]),
  );
  const legacySkillLinks = Object.fromEntries(
    Object.keys(approvedInventory.legacy_skill_links).map((name) => [
      name,
      inspectSetupTarget(path.join(home, '.codex', 'skills', name)).hash,
    ]),
  );
  const legacyBackupLinks = Object.fromEntries(
    Object.keys(approvedInventory.legacy_backup_links).map((relative) => [
      relative,
      inspectSetupTarget(path.join(home, relative)).hash,
    ]),
  );
  return {
    schema: 'hard-eng/approved-cutover-inventory/v1',
    legacy_skill_links: legacySkillLinks,
    legacy_backup_links: legacyBackupLinks,
    duplicate_teach: {
      path: '.codex/skills/teach',
      hash: inspectSetupTarget(path.join(home, '.codex', 'skills', 'teach')).hash,
      files: [...approvedInventory.duplicate_teach.files],
    },
    custom_agents: customAgents,
  };
}
