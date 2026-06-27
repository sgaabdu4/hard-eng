#!/usr/bin/env node
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';

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
const setupRuntime = read('scripts/setup-runtime.sh');
const setupCombined = `${setup}\n${setupRuntime}`;
const install = read('scripts/install.sh');
const uninstall = read('scripts/uninstall.sh');
const cron = read('scripts/install-cron.sh');
const manageSkills = read('scripts/manage-skills.mjs');
const setupSmoke = read('tests/setup-isolated-install.test.mjs');
const ci = read('.github/workflows/ci.yml');
const noMistakesRequired = read('.github/workflows/no-mistakes-required.yml');
const stateExamplePath = path.join(repo, 'docs/examples/he-state-plan-ready.example.json');

for (const mode of ['--safe', '--full', '--skills-only', '--prereqs-only', '--uninstall', '--dry-run']) {
  assertIncludes(setup, mode, `setup.sh must support ${mode}`);
  assertIncludes(readme, mode, `README must document ${mode}`);
}

for (const command of [
  'bash setup.sh --safe',
  'bash setup.sh --safe --dry-run',
  'bash setup.sh --full',
  'bash setup.sh --skills-only',
  './scripts/install.sh --dry-run',
  './scripts/uninstall.sh --yes',
  './scripts/uninstall.sh --yes --dry-run',
  'bash setup.sh --uninstall --yes',
]) {
  assertIncludes(readme, command, `README must show ${command}`);
}

assertIncludes(readme, '<a id="tested-scope"></a>', 'README tested badge must have an anchor');
assertIncludes(readme, 'Hard Eng makes AI coding agents plan, prove, ship, and learn for serious feature and shipping work instead of guessing, editing random files, and saying "done".', 'README must explain the value before install details');
assertIncludes(readme, 'It is an opt-in local discipline layer for Codex on macOS today.', 'README must say the full Hard Eng flow is opt-in');
assertIncludes(readme, '## 30-Second Version', 'README must include a fast first-read explanation');
assertIncludes(readme, 'If you just say "fix this bug", Hard Eng does not automatically run the full `/he:*` workflow.', 'README must distinguish normal fixes from the full Hard Eng flow');
assertIncludes(readme, 'User: /he:plan ship login redirect fix', 'README must include a tiny /he:* example');
assertIncludes(readme, 'For tiny text edits or throwaway experiments, use the relevant agent directly and run the normal repo checks.', 'README must say when the workflow is too heavy');
assertIncludes(readme, '## When To Use It', 'README must explain when to use the full flow');
assertIncludes(readme, '## Demo And Examples', 'README must link demo and state examples');
assertIncludes(readme, 'docs/media/hard-eng-terminal-flow.gif', 'README must link the illustrative terminal-flow GIF');
assertIncludes(readme, 'It is not a real `codex` CLI recording.', 'README must not present the illustrative GIF as live CLI proof');
assertIncludes(readme, 'docs/examples/he-state-plan-ready.example.json', 'README must link the checked he-state example');
const stateExample = spawnSync('node', [path.join(repo, 'scripts/he-state.mjs'), 'validate', stateExamplePath], { cwd: repo, encoding: 'utf8' });
assert.equal(stateExample.status, 0, `checked he-state example must validate:\n${stateExample.stderr}`);
assertIncludes(readme, 'only been tested on Codex running on macOS');
assertIncludes(readme, 'docs/images/hard-eng-hero.png');
assertIncludes(readme, 'docs/images/project-workflow-gates.png');
assertIncludes(readme, '## Install Security', 'README must explain installer security posture');
assertIncludes(readme, '| Surface | What it does | When it is installed or skipped |', 'README must explain each install surface and skip behavior');
assertIncludes(readme, 'approval_policy = "never"', 'README must document Codex approval trust setting');
assertIncludes(readme, 'sandbox_mode = "danger-full-access"', 'README must document Codex sandbox trust setting');
assertIncludes(readme, 'not written by default', 'README must say trusted Codex settings are opt-in');
assertIncludes(readme, 'HARD_ENG_TRUSTED_WORKSTATION=1', 'README must document trusted-workstation opt-in');
assertIncludes(readme, 'HARD_ENG_SKIP_MCP_CONFIG=1', 'README must document MCP config skip switch');
assertIncludes(readme, 'Running `bash setup.sh` with no mode starts an interactive wizard', 'README must document no-mode setup wizard');
assertIncludes(readme, 'In non-interactive shells and CI, no-mode setup uses `--safe` behavior', 'README must document non-interactive safe default');
assertIncludes(readme, 'Setup switches are shell environment variables', 'README must explain how to set setup variables');
assertIncludes(readme, 'HARD_ENG_TRUSTED_WORKSTATION=1 bash setup.sh --full', 'README must show one-run setup variable syntax');
assertIncludes(readme, 'export HARD_ENG_SKIP_NPM_INSTALL=1', 'README must show exported setup variable syntax');
assertIncludes(readme, 'unset HARD_ENG_SKIP_NPM_INSTALL HARD_ENG_SKIP_MCP_CONFIG', 'README must show how to return to defaults');
for (const installedSurface of [
  '~/.zshenv',
  'Homebrew packages',
  'tiktoken',
  'Flutter SDK',
  'context-mode',
  'codebase-memory-mcp',
  '@openai/codex',
  '~/.codex/config.toml',
  '~/.codex/hooks.json',
  '~/.claude',
  '~/.copilot',
  '~/.pi',
  'post-merge',
  'post-rewrite',
  'pre-commit',
  'pre-push',
  'LaunchAgent',
  'HARD_ENG_ENABLE_CRON=1',
  'Treehouse',
  'no-mistakes',
]) {
  assertIncludes(readme, installedSurface, `README must document installed/touched surface: ${installedSurface}`);
}
assertIncludes(
  readme,
  'If any installer mode, managed path, automatic tool, or trust setting changes, update this README in the same change.',
  'README must document the install-surface documentation guardrail',
);
assertIncludes(readme, '## Repository Guardrails', 'README must document upstream repository guardrails');
assertIncludes(readme, 'Installing Hard Eng does not grant push access to this upstream repository.', 'README must separate install from repo push access');
assertIncludes(readme, 'changes merge through pull requests only', 'README must document PR-only main');
assertIncludes(readme, 'direct pushes to `main` are blocked by branch protection', 'README must document blocked direct main writes');
assertIncludes(readme, 'repository write and merge permission is limited to `sgaabdu4`', 'README must document owner-only repo write permission');
assertIncludes(readme, '`hard-eng`', 'README must document the required full-repo CI check');
assertIncludes(readme, '`no-mistakes-required`', 'README must document the no-mistakes PR evidence check');
assertIncludes(readme, 'The PR contains passed no-mistakes evidence from `sgaabdu4` for the current head before review or merge.', 'README must document owner-authored no-mistakes evidence');
assertIncludes(readme, 'current head SHA plus `No open no-mistakes findings` or `outcome: checks-passed`', 'README must document passed-marker evidence');
assertIncludes(readme, 'If branch-protection rules, required check names, or no-mistakes PR evidence behavior change, update this README and the workflow contract tests in the same change.');
assertIncludes(readme, 'Codex skill triggers, not shell commands', 'README must clarify /he:* command surface');
assertIncludes(readme, 'Deterministic guardrails include regex scanners, Git hooks, lint/analyze/typecheck commands, SSOT scanners, Fallow, React Doctor, and repeat-mistake prevention', 'README must document deterministic guardrail classes');
assertIncludes(readme, 'Every touched-stack guardrail must be recorded in `guardrailInventory.requiredGuardrails[]` and, when required, in `guardrails[]`', 'README must require guardrail state evidence');
assertIncludes(readme, '`guardrailInventory.requiredGuardrails[]`', 'README must document touched-stack guardrail inventory');
assertIncludes(readme, 'Runs `codex-watchdog` every 60 seconds', 'README must explain the watchdog behavior');
assertIncludes(readme, 'process killing remains opt-in via watchdog env vars', 'README must explain watchdog safety defaults');
assertIncludes(readme, 'Links shared rules and skills', 'README must explain Codex linked config purpose');
assertIncludes(readme, 'Refreshes submodules after pulls', 'README must explain managed Git hook purpose');

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

assertIncludes(setup, '"$ROOT/scripts/uninstall.sh" $uninstall_args', 'setup.sh --uninstall must delegate to the uninstall owner');
assertIncludes(setup, 'apply_safe_mode', 'setup.sh must own safe install mode');
assertIncludes(setup, 'choose_interactive_default_options', 'setup.sh default mode must own the consent wizard');
assertIncludes(setup, 'Hard Eng setup will ask before installing workstation-level tools.', 'setup wizard must explain it asks before workstation-level installs');
assertIncludes(setup, 'Install or repair prerequisite tools?', 'setup wizard must ask before prerequisite repair');
assertIncludes(setup, 'Install or update global npm tools?', 'setup wizard must ask before global npm installs');
assertIncludes(setup, 'Write active Codex MCP config?', 'setup wizard must ask before active MCP config');
assertIncludes(setup, 'Write trusted Codex settings?', 'setup wizard must ask before dangerous Codex trust settings');
assertIncludes(setup, 'Install the Codex watchdog and managed bins?', 'setup wizard must ask before watchdog/LaunchAgent install');
assertIncludes(setup, 'elif is_interactive; then', 'setup default mode must distinguish interactive from non-interactive');
assertIncludes(setup, 'HARD_ENG_SKIP_MCP_CONFIG=1', 'safe/skills-only setup must skip active MCP config');
assertIncludes(setup, 'HARD_ENG_DRY_RUN', 'setup.sh must support dry-run');
assertIncludes(setup, 'print_setup_dry_run', 'setup.sh must print planned writes without mutating');
assertIncludes(setup, 'HARD_ENG_TRUSTED_WORKSTATION', 'setup dry-run must disclose trusted Codex setting behavior');
const skillsOnlyMode = setup.slice(setup.indexOf('apply_skills_only_mode()'), setup.indexOf('apply_safe_mode()'));
assertIncludes(skillsOnlyMode, 'export HARD_ENG_ENABLE_CRON=0', 'safe/skills-only setup must force cron disabled before later prompts');
assertNotIncludes(skillsOnlyMode, 'unset HARD_ENG_ENABLE_CRON', 'safe/skills-only setup must not reopen the cron prompt');
assertIncludes(setup, 'source "$ROOT/scripts/setup-runtime.sh"', 'setup.sh must source post-clone runtime helpers');
assertIncludes(setupCombined, 'Hard Eng skills to link: all, none, or comma-separated names [all]:', 'setup must ask for skill selection');
assertIncludes(setupCombined, 'persist_skill_selection', 'setup must persist selected skills before install');
assertIncludes(setupSmoke, "setup.sh'), '--skills-only'", 'setup smoke must execute skills-only setup');
assertIncludes(setupSmoke, "HARD_ENG_SKILLS: 'he-plan,no-mistakes'", 'setup smoke must prove selected skill linking');
const mainFlow = setup.slice(setup.lastIndexOf('install_prerequisites'));
assert.ok(mainFlow.indexOf('clone_or_update_repo') < mainFlow.indexOf('source "$ROOT/scripts/setup-runtime.sh"'), 'setup must clone/update before loading repo-owned runtime helpers');
assert.ok(mainFlow.indexOf('source "$ROOT/scripts/setup-runtime.sh"') < mainFlow.indexOf('choose_setup_options'), 'setup must load runtime helpers before prompting for skills');
assertIncludes(install, 'node "$ROOT/scripts/manage-skills.mjs" apply', 'install must delegate skill links to the stateful skill manager');
assertIncludes(uninstall, 'node "$ROOT/scripts/manage-skills.mjs" remove', 'uninstall must remove selected managed skill links through the owner');
assertIncludes(uninstall, 'HARD_ENG_DRY_RUN="$DRY_RUN" node "$ROOT/scripts/manage-skills.mjs" remove', 'uninstall dry-run must not mutate managed skill links');
assertIncludes(uninstall, 'HARD_ENG_SKILL_CONFIG', 'uninstall must remove the persisted skill-selection config');
assertIncludes(uninstall, 'remove_codex_config_entries', 'uninstall must remove managed Codex config entries');
assertIncludes(uninstall, 'remove_context_mode_permissions', 'uninstall must remove managed context-mode permission entries');
assertIncludes(manageSkills, '.config\', \'hard-eng\', \'skills.json', 'skill manager must store user selection outside the repo');
assertIncludes(manageSkills, 'HARD_ENG_SKILLS', 'skill manager must support one-run skill selection override');
assertIncludes(manageSkills, 'process.env.HARD_ENG_DRY_RUN', 'skill manager must support dry-run for uninstall previews');
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
assertIncludes(install, '--dry-run', 'install.sh must support dry-run proof');
assertIncludes(install, 'print_install_dry_run', 'install.sh must print planned writes without mutating');
assertIncludes(install, 'HARD_ENG_SKIP_MCP_CONFIG', 'install.sh must allow safe/skills-only installs without active MCP config');
assertIncludes(install, 'HARD_ENG_TRUSTED_WORKSTATION', 'install.sh must keep dangerous Codex settings opt-in');
assertIncludes(install, 'approval_policy = "never"', 'install.sh must explicitly guard approval_policy trust setting');
assertIncludes(install, 'sandbox_mode = "danger-full-access"', 'install.sh must explicitly guard sandbox_mode trust setting');
assertIncludes(install, 'drop_top_level(trusted_settings)', 'non-trusted install must remove legacy managed trust settings');
assertIncludes(install, 'drop_sections(managed_mcp_sections)', 'MCP-skip install must remove legacy managed MCP sections');
assertIncludes(install, 'remove_managed_executable "$ROOT/codex/bin/codex-update-stack"', 'non-trusted install must remove managed stack repair');
assertIncludes(install, 'HARD_ENG_REMOVE_MANAGED_CRON', 'managed cron cleanup must require explicit cleanup consent');
assertIncludes(setup, 'HARD_ENG_REMOVE_MANAGED_CRON=1', 'safe/skills-only setup must remove old managed cron blocks');
assertIncludes(uninstall, 'dev.hard-eng.codex-watchdog');
assertIncludes(cron, '# BEGIN hard-eng auto-sync');
assertIncludes(cron, 'consent_env_prefix', 'Codex stack cron must carry trusted workstation consent and skip flags');
assertIncludes(cron, 'HARD_ENG_SKIP_MCP_CONFIG', 'Codex stack cron must carry MCP skip consent');
assertIncludes(uninstall, '# BEGIN hard-eng auto-sync');
assertIncludes(setup, '# BEGIN hard-eng bootstrap path');
assertIncludes(uninstall, '# BEGIN hard-eng bootstrap path');
assertIncludes(manageSkills, '!selected.has(entry)', 'skill manager must clean stale or deselected managed skill symlinks');
assertIncludes(ci, 'node scripts/check-hard-eng-full-repo.mjs', 'GitHub Actions must run the full repo gate');
assertIncludes(ci, 'submodules: recursive', 'GitHub Actions must check out vendored skill submodules');
assertIncludes(ci, '>> "$GITHUB_PATH"', 'GitHub Actions must persist npm global bin for later steps');
assertIncludes(noMistakesRequired, 'name: no-mistakes-required', 'GitHub Actions must expose the required no-mistakes PR check');
assertIncludes(noMistakesRequired, 'pull_request:', 'no-mistakes required check must run on PRs');
assertIncludes(noMistakesRequired, 'issue_comment:', 'no-mistakes required check must rerun for PR comments');
assertIncludes(noMistakesRequired, 'pull_request_review:', 'no-mistakes required check must rerun for PR reviews');
assertIncludes(noMistakesRequired, 'REQUIRED_AUTHOR: sgaabdu4', 'no-mistakes PR evidence must be owner-authored');
assertIncludes(noMistakesRequired, 'pr.head.sha', 'no-mistakes PR evidence must be current-head scoped');
assertIncludes(noMistakesRequired, 'createCommitStatus', 'comment-triggered no-mistakes evidence must update the PR head status');
assertIncludes(noMistakesRequired, '<!-- nm-pr-evidence:start -->', 'no-mistakes required check must accept managed PR evidence');
assertIncludes(noMistakesRequired, 'passedEvidencePattern', 'no-mistakes required check must require an explicit passed marker');
assertIncludes(noMistakesRequired, 'No open no-mistakes findings', 'no-mistakes required check must accept no-open-findings evidence');
assertIncludes(noMistakesRequired, 'outcome:\\s*(?:checks-passed|passed)', 'no-mistakes required check must accept passed outcomes');
assertNotIncludes(noMistakesRequired, '|checks-passed/i', 'no-mistakes required check must not accept bare checks-passed text');
assertNotIncludes(noMistakesRequired, 'No-mistakes Evidence|no-mistakes axi', 'no-mistakes required check must not accept headings or command mentions alone');
assertIncludes(noMistakesRequired, 'Missing passed no-mistakes evidence from ${requiredAuthor}', 'no-mistakes required check must fail closed');

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
