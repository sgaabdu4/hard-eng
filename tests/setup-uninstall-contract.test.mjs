#!/usr/bin/env node
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';

const repo = path.resolve(new URL('..', import.meta.url).pathname);

function read(relativePath) {
  return fs.readFileSync(path.join(repo, relativePath), 'utf8');
}

function assertIncludes(text, needle, message = `missing ${needle}`) {
  assert.ok(text.includes(needle), message);
}

function assertNotIncludes(text, needle, message = `unexpected ${needle}`) {
  assert.ok(!text.includes(needle), message);
}

const readme = read('README.md');
const setup = read('scripts/setup.sh');
const install = read('scripts/install.sh');
const uninstall = read('scripts/uninstall.sh');
const cron = read('scripts/install-cron.sh');
const manageSkills = read('scripts/manage-skills.mjs');
const setupSmoke = read('tests/setup-isolated-install.test.mjs');

for (const mode of ['--full', '--skills-only', '--prereqs-only', '--uninstall']) {
  assertIncludes(setup, mode, `setup.sh must support ${mode}`);
  assertIncludes(readme, mode, `README must document ${mode}`);
}

for (const command of [
  'bash setup.sh --full',
  'bash setup.sh --skills-only',
  './scripts/uninstall.sh --yes',
  'bash setup.sh --uninstall --yes',
]) {
  assertIncludes(readme, command, `README must show ${command}`);
}

assertIncludes(readme, '<a id="tested-scope"></a>', 'README tested badge must have an anchor');
assertIncludes(readme, 'only been tested on Codex running on macOS');
assertIncludes(readme, 'docs/images/hard-eng-hero.png');
assertIncludes(readme, 'docs/images/project-workflow-gates.png');

const oldPublicNames = [
  String.fromCharCode(65, 98, 105, 100) + ' Agents',
  String.fromCharCode(97, 98, 105, 100) + '-agents',
  String.fromCharCode(65, 66, 73, 68) + '_AGENTS',
  '/a' + 'a:',
  'a' + 'a-state',
];
for (const oldPublicName of oldPublicNames) {
  assertNotIncludes(readme, oldPublicName, `README must not mention ${oldPublicName}`);
  assertNotIncludes(setup, oldPublicName, `setup.sh must not expose ${oldPublicName}`);
}

assertIncludes(setup, '"$ROOT/scripts/uninstall.sh" "${@:2}"', 'setup.sh --uninstall must delegate to the uninstall owner');
assertIncludes(setup, 'Hard Eng skills to link: all, none, or comma-separated names [all]:', 'setup must ask for skill selection');
assertIncludes(setup, 'persist_skill_selection', 'setup must persist selected skills before install');
assertIncludes(setupSmoke, "setup.sh'), '--skills-only'", 'setup smoke must execute skills-only setup');
assertIncludes(setupSmoke, "HARD_ENG_SKILLS: 'he-plan,no-mistakes'", 'setup smoke must prove selected skill linking');
const mainFlow = setup.slice(setup.lastIndexOf('install_prerequisites'));
assert.ok(mainFlow.indexOf('clone_or_update_repo') < mainFlow.indexOf('choose_setup_options'), 'setup must clone/update before prompting for skills so fresh installs can list available skills');
assertIncludes(install, 'node "$ROOT/scripts/manage-skills.mjs" apply', 'install must delegate skill links to the stateful skill manager');
assertIncludes(uninstall, 'node "$ROOT/scripts/manage-skills.mjs" remove', 'uninstall must remove selected managed skill links through the owner');
assertIncludes(uninstall, 'HARD_ENG_SKILL_CONFIG', 'uninstall must remove the persisted skill-selection config');
assertIncludes(uninstall, 'remove_codex_config_entries', 'uninstall must remove managed Codex config entries');
assertIncludes(uninstall, 'remove_context_mode_permissions', 'uninstall must remove managed context-mode permission entries');
assertIncludes(manageSkills, '.config\', \'hard-eng\', \'skills.json', 'skill manager must store user selection outside the repo');
assertIncludes(manageSkills, 'HARD_ENG_SKILLS', 'skill manager must support one-run skill selection override');
assertIncludes(manageSkills, 'isManagedSkillLink', 'skill manager must preserve user-owned skill folders');
assertIncludes(uninstall, 'HARD_ENG_UNINSTALL_YES', 'uninstall must support non-interactive confirmation');
assertIncludes(uninstall, '--dry-run', 'uninstall must support dry-run proof');
assertIncludes(uninstall, 'Shared prerequisites such as Homebrew, Git, Node, Dart, Flutter, Treehouse, and');
assertNotIncludes(uninstall, 'brew uninstall');
assertNotIncludes(uninstall, 'npm uninstall -g');
assertNotIncludes(uninstall, 'rm -rf "$HOME/flutter"');

const managedBins = [...install.matchAll(/install_managed_executable "\$ROOT\/codex\/bin\/([^"]+)"/g)].map((match) => match[1]);
assert.deepEqual(
  managedBins.sort(),
  ['codex-cleanup', 'codex-context-mode-health', 'codex-health', 'codex-update-stack', 'codex-watchdog'].sort(),
  'install.sh managed Codex bins changed; update uninstall contract',
);
for (const name of managedBins) {
  assertIncludes(uninstall, name, `uninstall must remove managed Codex bin ${name}`);
}

const installedHooks = [...install.matchAll(/install_hook (post-merge|post-rewrite|pre-commit|pre-push)/g)].map((match) => match[1]);
assert.deepEqual(installedHooks.sort(), ['post-merge', 'post-rewrite', 'pre-commit', 'pre-push'].sort());
for (const hook of installedHooks) {
  assertIncludes(uninstall, hook, `uninstall must remove managed hook ${hook}`);
}

assertIncludes(install, 'dev.hard-eng.codex-watchdog');
assertIncludes(uninstall, 'dev.hard-eng.codex-watchdog');
assertIncludes(cron, '# BEGIN hard-eng auto-sync');
assertIncludes(uninstall, '# BEGIN hard-eng auto-sync');
assertIncludes(setup, '# BEGIN hard-eng bootstrap path');
assertIncludes(uninstall, '# BEGIN hard-eng bootstrap path');
assertIncludes(manageSkills, '!selected.has(entry)', 'skill manager must clean stale or deselected managed skill symlinks');

const relativeTargets = new Set();
for (const match of readme.matchAll(/!?\[[^\]]*\]\(([^)\s]+)(?:\s+"[^"]*")?\)/g)) {
  relativeTargets.add(match[1]);
}
for (const match of readme.matchAll(/<(?:img|a)\b[^>]*(?:src|href)="([^"]+)"/g)) {
  relativeTargets.add(match[1]);
}

for (const rawTarget of relativeTargets) {
  if (/^(https?:|mailto:|#)/.test(rawTarget)) continue;
  const target = rawTarget.split('#')[0];
  if (!target) continue;
  assert.ok(fs.existsSync(path.join(repo, target)), `README target does not exist: ${rawTarget}`);
}

console.log('setup-uninstall-contract: pass');
