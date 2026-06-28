#!/usr/bin/env node
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';

const repo = path.join(process.env.HOME, '.agents');
const installScript = fs.readFileSync(path.join(repo, 'scripts', 'install.sh'), 'utf8');
const setupScript = fs.readFileSync(path.join(repo, 'scripts', 'setup.sh'), 'utf8');
const setupRuntimeScript = fs.readFileSync(path.join(repo, 'scripts', 'setup-runtime.sh'), 'utf8');
const setupCombinedScript = `${setupScript}\n${setupRuntimeScript}`;
const uninstallScript = fs.readFileSync(path.join(repo, 'scripts', 'uninstall.sh'), 'utf8');
const readme = fs.readFileSync(path.join(repo, 'README.md'), 'utf8');
const worktreeReadyScript = fs.readFileSync(path.join(repo, 'scripts', 'ensure-worktree-ready.sh'), 'utf8');
const autoSyncScript = fs.readFileSync(path.join(repo, 'scripts', 'auto-sync.sh'), 'utf8');
const cronScript = fs.readFileSync(path.join(repo, 'scripts', 'install-cron.sh'), 'utf8');
const submoduleScript = fs.readFileSync(path.join(repo, 'scripts', 'update-submodules.sh'), 'utf8');
const manageSkillsScript = fs.readFileSync(path.join(repo, 'scripts', 'manage-skills.mjs'), 'utf8');
const codexWatchdog = fs.readFileSync(path.join(repo, 'codex', 'bin', 'codex-watchdog'), 'utf8');
const codexHealth = fs.readFileSync(path.join(repo, 'codex', 'bin', 'codex-health'), 'utf8');
const securityHook = fs.readFileSync(path.join(repo, 'hooks', 'security-pretooluse.js'), 'utf8');
const dangerousHook = fs.readFileSync(path.join(repo, 'hooks', 'claude-code-hooks', 'block-dangerous-commands.js'), 'utf8');

assert.ok(installScript.includes('install_hook post-merge'), 'installer must create post-merge hook');
assert.ok(installScript.includes('install_hook post-rewrite'), 'installer must create post-rewrite hook for pull --rebase');
assert.ok(installScript.includes('install_hook pre-commit'), 'installer must create pre-commit hook');
assert.ok(installScript.includes('install_hook pre-push'), 'installer must create pre-push hook');
assert.ok(
  installScript.includes('hooks_dir="$ROOT/$hooks_dir"'),
  'installer must make relative git hook paths repo-absolute for LaunchAgent cwd safety'
);
assert.ok(installScript.includes('scripts/update-submodules.sh'), 'installer and hooks must update submodules');
assert.ok(installScript.includes('config --local pull.rebase false'), 'installer must disable pull rebases for this repo');
assert.ok(installScript.includes('config --local pull.ff only'), 'installer must force fast-forward-only pulls for this repo');
assert.ok(installScript.includes('HARD_ENG_SKIP_SUBMODULE_INIT'), 'installer must support skipping submodule init');
assert.ok(installScript.includes('HARD_ENG_SKIP_SUBMODULE_UPDATE'), 'pull hooks must support skipping submodule updates');
assert.ok(installScript.includes('HARD_ENG_CHECK_SUBMODULES_BEFORE_PUSH'), 'pre-push submodule status must be opt-in');
assert.ok(installScript.includes('default_mode_request_user_input'), 'installer must sync request-user-input feature into Codex config');
assert.ok(installScript.includes('--dry-run'), 'installer must support dry-run proof');
assert.ok(installScript.includes('print_install_dry_run'), 'installer must print planned writes without mutating');
assert.ok(installScript.includes('HARD_ENG_SKIP_MCP_CONFIG'), 'installer must allow skills-only/safe installs without active MCP config');
assert.ok(installScript.includes('HARD_ENG_TRUSTED_WORKSTATION'), 'installer must keep trusted Codex settings opt-in');
assert.ok(installScript.includes('approval_policy = "never"'), 'installer must explicitly gate approval_policy trust setting');
assert.ok(installScript.includes('sandbox_mode = "danger-full-access"'), 'installer must explicitly gate sandbox_mode trust setting');
assert.ok(
  installScript.includes('HARD_ENG_SKIP_CRON=1 \\') &&
    installScript.includes('__HARD_ENG_INSTALL_REFRESH_ENV__') &&
    installScript.includes('  "$repo/scripts/install.sh"'),
  'pre-push hook must refresh through the installer consent envelope'
);
assert.ok(installScript.includes('install_refresh_consent_assignments'), 'pre-push refresh must persist installer consent flags');
assert.ok(
  installScript.includes('node "$repo/tests/codex-config-sync.test.mjs"'),
  'pre-push hook must test live Codex config sync before pushing'
);
assert.ok(
  installScript.includes('node "$repo/tests/setup-uninstall-contract.test.mjs"'),
  'pre-push hook must test setup/uninstall parity before pushing'
);
assert.ok(
  installScript.includes('node "$repo/tests/uninstall-config-cleanup.test.mjs"'),
  'pre-push hook must prove uninstall removes managed Codex config entries'
);
assert.ok(
  installScript.includes('node "$repo/scripts/check-generated-assets.mjs" "$repo"'),
  'pre-commit/pre-push hooks must block stale generated README images'
);
assert.ok(
  installScript.includes('node "$repo/scripts/check-ssot-guardrails.mjs" "$repo"'),
  'pre-commit/pre-push hooks must enforce SSOT scanner registry and drift checks'
);
assert.ok(
  installScript.includes('node "$repo/scripts/check-vendor-skill-integrity.mjs" "$repo"'),
  'pre-commit/pre-push hooks must block direct vendored upstream skill edits'
);
assert.ok(
  installScript.includes('node "$repo/scripts/check-project-naming.mjs" "$repo"'),
  'pre-commit/pre-push hooks must block old project naming'
);
assert.ok(
  installScript.includes('node "$repo/scripts/check-project-context-gates.mjs" --require-all "$repo"'),
  'pre-push hook must run product/design context gates before pushing'
);
assert.ok(
  installScript.includes('node "$repo/scripts/check-project-quality-gates.mjs" --require-push-gate "$repo"'),
  'pre-push hook must run deterministic project quality gate checks before pushing'
);
assert.ok(installScript.includes('install_codex_watchdog'), 'installer must install the Codex watchdog');
assert.ok(installScript.includes('dev.hard-eng.codex-watchdog'), 'installer must install the Codex watchdog LaunchAgent');
assert.ok(installScript.includes('HARD_ENG_SKIP_WATCHDOG'), 'installer must allow skipping the Codex watchdog');
assert.ok(installScript.includes('launchctl bootstrap'), 'installer must load the Codex watchdog when missing');
assert.ok(installScript.includes('replace_with_link_file "$ROOT/AGENTS.md" "$HOME/.codex/AGENTS.md"'), 'installer must link Codex AGENTS.md to the canonical file');
assert.ok(installScript.includes('replace_with_link_file "$ROOT/AGENTS.md" "$HOME/.claude/AGENTS.md"'), 'installer must link Claude AGENTS.md to the canonical file');
assert.ok(installScript.includes('replace_with_link_file "$ROOT/AGENTS.md" "$HOME/.copilot/AGENTS.md"'), 'installer must link Copilot AGENTS.md to the canonical file');
assert.ok(installScript.includes('replace_with_link_file "$ROOT/AGENTS.md" "$HOME/.pi/AGENTS.md"'), 'installer must link Pi AGENTS.md to the canonical file');
assert.ok(!installScript.includes('install_managed_block'), 'installer must not install copied AGENTS.md managed blocks');
assert.ok(installScript.includes('node "$ROOT/scripts/manage-skills.mjs" apply'), 'installer must delegate skill links to manage-skills');
assert.ok(manageSkillsScript.includes('isManagedSkillLink'), 'skill manager must only remove managed skill symlinks');
assert.ok(manageSkillsScript.includes('HARD_ENG_SKILLS'), 'skill manager must support explicit selected skills');
assert.ok(manageSkillsScript.includes("'.config', 'hard-eng', 'skills.json'"), 'skill manager must persist selected skills outside the repo');
assert.ok(installScript.includes('scripts/check-markdown-hygiene.mjs'), 'pre-commit hook must run Markdown hygiene');
assert.ok(installScript.includes('Blocked commit: staged forbidden files must not be edited.'), 'pre-commit hook must block forbidden edited files');
assert.ok(installScript.includes('Blocked commit: staged files over 700 lines must be split below 700.'), 'pre-commit hook must block staged files over 700 lines');
assert.ok(installScript.includes('line_cap_exception'), 'pre-commit hook must keep a narrow line-cap exception owner');
assert.ok(installScript.includes('HARD_ENG_SCANNER_OWNER'), 'pre-commit hook must require the scanner-owner marker for line-cap exceptions');
assert.ok(installScript.includes('scripts/*proof*.mjs'), 'pre-commit hook must narrow scanner-owner line-cap exceptions by path');
assert.ok(installScript.includes('scripts/*regex*.mjs'), 'pre-commit hook must allow marked regex owner line-cap exceptions');
assert.ok(installScript.includes('Blocked commit: staged content contains secret-like values.'), 'pre-commit hook must block secret-like staged values');
assert.ok(installScript.includes('generated_marker="AUTO""-GENERATED"'), 'pre-commit hook must define generated marker under set -u');
assert.ok(installScript.includes('[[ "$mode" == "160000" ]]'), 'pre-commit hook must skip staged submodule gitlinks');
assert.ok(installScript.includes('is_binary_staged'), 'pre-commit hook must identify staged binary files');
assert.ok(installScript.includes('git diff --cached --numstat -- "$1"'), 'pre-commit hook must use git binary detection');
assert.ok(installScript.includes('LC_ALL=C strings -a -n 8'), 'pre-commit hook must scan staged binary strings for secrets');
assert.ok(!installScript.includes('if is_binary_staged "$file"; then\n    continue'), 'pre-commit hook must not skip binary blobs entirely');
assert.ok(installScript.includes('grep -F "$HOME"'), 'pre-commit private-path scan must use runtime HOME');
assert.ok(installScript.includes('HARD_ENG_PRIVATE_CONTENT_PATTERN'), 'pre-commit private-path scan must allow a private local pattern without storing it');
assert.ok(installScript.includes('HARD_ENG_PRIVATE_CONTENT_PATTERN_FILE'), 'pre-commit private path scan must support a local ignored pattern file');
assert.ok(installScript.includes('grep -E -i "$private_pattern"'), 'pre-commit private pattern scan must include binary string output');
assert.ok(installScript.includes("':!scripts/check-markdown-hygiene.mjs'"), 'pre-commit private-path scan must not flag the checker pattern');
assert.ok(installScript.includes("':!tests/markdown-hygiene.test.mjs'"), 'pre-commit private-path scan must not flag the hygiene test fixture');
assert.ok(installScript.includes('Preserving existing file'), 'installer must preserve existing non-managed config files');
assert.ok(!installScript.includes('rm "$target"'), 'installer must not remove existing linked targets');
assert.ok(installScript.includes('mv "$target" "$(backup_path "$target")"'), 'installer must back up existing Codex hooks config instead of deleting it');
assert.ok(setupScript.includes('git clone --recurse-submodules'), 'new-user setup must clone with submodules');
assert.ok(setupScript.includes('scripts/install.sh'), 'new-user setup must run the main installer');
assert.ok(setupScript.includes('--safe'), 'setup must expose safe mode');
assert.ok(setupScript.includes('--full'), 'setup must expose full mode');
assert.ok(setupScript.includes('--skills-only'), 'setup must expose skills-only mode');
assert.ok(setupScript.includes('--uninstall'), 'setup must expose uninstall mode');
assert.ok(setupScript.includes('--dry-run'), 'setup must expose dry-run mode');
assert.ok(setupScript.includes('apply_safe_mode'), 'setup must own safe mode defaults');
assert.ok(setupScript.includes('choose_interactive_default_options'), 'setup default mode must own the interactive consent wizard');
assert.ok(setupScript.includes('Install or repair prerequisite tools?'), 'setup wizard must ask before prerequisite repair');
assert.ok(setupScript.includes('Install or update global npm tools?'), 'setup wizard must ask before global npm installs');
assert.ok(setupScript.includes('Write active Codex MCP config?'), 'setup wizard must ask before active MCP config');
assert.ok(setupScript.includes('Write trusted Codex settings?'), 'setup wizard must ask before dangerous Codex trust settings');
assert.ok(setupScript.includes('Install the Codex watchdog and managed bins?'), 'setup wizard must ask before watchdog install');
assert.ok(setupScript.includes('elif is_interactive; then'), 'setup default mode must distinguish interactive from non-interactive');
assert.ok(setupScript.includes('HARD_ENG_DRY_RUN'), 'setup must support dry-run proof');
assert.ok(setupScript.includes('HARD_ENG_SKIP_MCP_CONFIG=1'), 'safe/skills-only setup must skip active MCP config');
assert.ok(!setupScript.includes('HARD_ENG_ENABLE_CRON="${HARD_ENG_ENABLE_CRON:-1}"'), 'full setup must not enable cron by default');
assert.ok(setupScript.includes('"$ROOT/scripts/uninstall.sh" $uninstall_args'), 'setup uninstall mode must delegate to scripts/uninstall.sh');
assert.ok(readme.includes('## Install Security'), 'README must document install security');
assert.ok(readme.includes('Running `bash setup.sh` with no mode starts an interactive wizard'), 'README must document no-mode wizard');
assert.ok(readme.includes('In non-interactive shells and CI, no-mode setup uses `--safe` behavior'), 'README must document non-interactive safe default');
assert.ok(readme.includes('If any installer mode, managed path, automatic tool, or trust setting changes, update this README in the same change.'), 'README must require install-surface doc updates');
assert.ok(setupScript.includes('source "$ROOT/scripts/setup-runtime.sh"'), 'setup must source post-clone runtime helpers');
assert.ok(setupCombinedScript.includes('no-mistakes'), 'new-user setup must install or initialize no-mistakes');
assert.ok(setupCombinedScript.includes('install_or_update_treehouse'), 'setup must install or update Treehouse');
assert.ok(setupCombinedScript.includes('HARD_ENG_SETUP_TREEHOUSE'), 'setup must allow non-interactive Treehouse choice');
assert.ok(setupCombinedScript.includes('HARD_ENG_SKIP_TREEHOUSE'), 'setup must allow skipping Treehouse install');
assert.ok(setupCombinedScript.includes('https://kunchenguid.github.io/treehouse/install.sh'), 'setup must use Treehouse upstream installer');
assert.ok(setupScript.includes('ask_yes_no'), 'setup must ask questions when interactive');
assert.ok(setupCombinedScript.includes('Hard Eng skills to link: all, none, or comma-separated names [all]:'), 'setup must ask for selected skills when interactive');
assert.ok(setupCombinedScript.includes('persist_skill_selection'), 'setup must persist selected skills before install');
assert.ok(setupCombinedScript.includes('HARD_ENG_SETUP_NO_MISTAKES'), 'setup must allow non-interactive no-mistakes choice');
assert.ok(setupCombinedScript.includes('HARD_ENG_ENABLE_CRON'), 'setup must allow cron choice');
assert.ok(setupCombinedScript.includes('HARD_ENG_NO_MISTAKES_REPOS'), 'new-user setup must support extra no-mistakes repo init');
assert.ok(setupCombinedScript.includes('ensure_worktree_ready_repo'), 'setup must run the shared worktree readiness guard');
assert.ok(setupCombinedScript.includes('HARD_ENG_SKIP_WORKTREE_READY'), 'setup must allow skipping worktree readiness only by explicit env');
assert.ok(setupCombinedScript.includes('HARD_ENG_WORKTREE_READY_INSTALL'), 'setup must make dependency install for readiness explicit');
assert.ok(setupCombinedScript.includes('if [[ "${#args[@]}" -gt 0 ]]'), 'setup must avoid empty array expansion under macOS Bash 3 set -u');
assert.ok(setupCombinedScript.includes('"$script" "$repo"'), 'setup must call worktree readiness with no empty array when no flags are set');
assert.ok(setupCombinedScript.includes('run_no_mistakes_with_isolated_agent_home'), 'setup must isolate no-mistakes skill writes from repo-owned skill symlinks');
assert.ok(setupCombinedScript.includes('CODEX_HOME="$isolated_home/.codex"'), 'isolated no-mistakes init must not write through real Codex skill symlinks');
assert.ok(setupCombinedScript.includes('NM_HOME="${NM_HOME:-$NO_MISTAKES_HOME}"'), 'isolated no-mistakes init must keep the real no-mistakes state home');
assert.ok(worktreeReadyScript.includes('core.hooksPath'), 'worktree readiness must inspect active Git hook path');
assert.ok(worktreeReadyScript.includes('/.no-mistakes/repos/'), 'worktree readiness must reject no-mistakes gate hook paths');
assert.ok(worktreeReadyScript.includes('.githooks'), 'worktree readiness must support generic tracked hook dirs');
assert.ok(worktreeReadyScript.includes('.husky/_'), 'worktree readiness must support Husky hook shims');
assert.ok(uninstallScript.includes('HARD_ENG_UNINSTALL_YES'), 'uninstall must support non-interactive confirmation');
assert.ok(uninstallScript.includes('--dry-run'), 'uninstall must support dry-run proof');
assert.ok(uninstallScript.includes('HARD_ENG_DRY_RUN="$DRY_RUN" node "$ROOT/scripts/manage-skills.mjs" remove'), 'uninstall dry-run must not mutate managed skill links');
assert.ok(uninstallScript.includes('dev.hard-eng.codex-watchdog'), 'uninstall must remove the Hard Eng watchdog LaunchAgent');
assert.ok(uninstallScript.includes('# BEGIN hard-eng auto-sync'), 'uninstall must remove managed cron blocks');
assert.ok(uninstallScript.includes('# BEGIN hard-eng bootstrap path'), 'uninstall must remove the managed shell PATH block');
assert.ok(uninstallScript.includes('.cache/hard-eng'), 'uninstall must remove the Hard Eng cache');
assert.ok(!uninstallScript.includes('brew uninstall'), 'uninstall must not remove shared Homebrew packages');
assert.ok(!uninstallScript.includes('npm uninstall -g'), 'uninstall must not remove shared global npm packages');
assert.ok(!uninstallScript.includes('rm -rf "$HOME/flutter"'), 'uninstall must not remove shared Flutter SDKs');
assert.ok(uninstallScript.includes('node "$ROOT/scripts/manage-skills.mjs" remove'), 'uninstall must remove managed skill links through manage-skills');
assert.ok(uninstallScript.includes('HARD_ENG_SKILL_CONFIG'), 'uninstall must remove persisted Hard Eng skill selection');
assert.ok(installScript.includes('"${1:-}" != "rebase"'), 'post-rewrite hook must only react to rebase rewrites');
assert.ok(
  installScript.includes('Blocked push: reachable git history contains private path or secret-like references.'),
  'pre-push hook must block private path or secret-like history matches'
);
assert.ok(installScript.includes("':!scripts/install.sh'"), 'pre-push history scan must ignore installer policy literals');
assert.ok(installScript.includes("':!tests/markdown-hygiene.test.mjs'"), 'pre-push history scan must ignore hygiene leak fixture');
assert.ok(installScript.includes('grep -n -I -F "$needle"'), 'pre-push fixed history scan must ignore binary blobs');
assert.ok(installScript.includes('grep -n -I -i -E "$pattern"'), 'pre-push regex history scan must ignore binary blobs');
assert.ok(installScript.includes("awk -F: '{ print $1 \":\" $2 \":\" $3 }'"), 'pre-push hook must avoid printing matched secret content');
assert.ok(installScript.includes('scan_history_fixed'), 'pre-push history scan must avoid giant revision argv');
assert.ok(autoSyncScript.includes('git rev-parse --git-path hard-eng-auto-sync.lock'), 'auto-sync lock must be repo-local');
assert.ok(autoSyncScript.includes('git pull --ff-only origin main'), 'auto-sync must pull main with ff-only');
assert.ok(autoSyncScript.includes('scripts/update-submodules.sh" --remote'), 'auto-sync must bump submodules to tracked upstreams');
assert.ok(autoSyncScript.includes('HARD_ENG_SKIP_SUBMODULE_BUMP'), 'auto-sync must allow disabling upstream submodule bumps');
assert.ok(autoSyncScript.includes('HARD_ENG_SKIP_NO_MISTAKES_UPDATE'), 'auto-sync must allow disabling no-mistakes updates');
assert.ok(autoSyncScript.includes('HARD_ENG_NO_MISTAKES_BIN'), 'auto-sync must allow overriding the no-mistakes binary path');
assert.ok(autoSyncScript.includes('update_treehouse'), 'auto-sync must update Treehouse');
assert.ok(autoSyncScript.includes('HARD_ENG_SKIP_TREEHOUSE_UPDATE'), 'auto-sync must allow disabling Treehouse updates');
assert.ok(autoSyncScript.includes('HARD_ENG_TREEHOUSE_BIN'), 'auto-sync must allow overriding the Treehouse binary path');
assert.ok(autoSyncScript.includes('NO_MISTAKES_NO_UPDATE_CHECK=1'), 'auto-sync must avoid nested no-mistakes update checks');
assert.ok(autoSyncScript.includes('update --yes'), 'auto-sync must update no-mistakes non-interactively');
assert.ok(autoSyncScript.includes('HARD_ENG_SKIP_PREREQ_INSTALL=1'), 'auto-sync local refresh must not run prerequisite installers from cron');
assert.ok(autoSyncScript.includes('install_env=(env HARD_ENG_SKIP_NPM_INSTALL=1'), 'auto-sync refresh must preserve installer consent flags');
assert.ok(autoSyncScript.includes('HARD_ENG_SKIP_MCP_CONFIG'), 'auto-sync refresh must preserve MCP skip consent');
assert.ok(autoSyncScript.includes('HARD_ENG_TRUSTED_WORKSTATION'), 'auto-sync refresh must preserve trusted workstation consent');
assert.ok(autoSyncScript.includes('HARD_ENG_AUTO_PUSH'), 'auto-sync must require explicit auto-push consent');
assert.ok(autoSyncScript.includes('Auto-sync staged submodule updates'), 'auto-sync must stop with staged submodule updates when auto-push is not enabled');
assert.ok(autoSyncScript.includes('git diff --name-only -- .gitmodules vendor/skill-upstreams'), 'auto-sync private-path scan must be scoped to submodule update outputs');
assert.ok(!autoSyncScript.includes('mapfile'), 'auto-sync must stay compatible with macOS Bash 3');
assert.ok(autoSyncScript.includes('git commit -m "Auto-update skill submodules"'), 'auto-sync must still support explicit auto-push commits');
assert.ok(autoSyncScript.includes('git push --recurse-submodules=check origin main'), 'auto-sync must push only after explicit auto-push consent');
assert.ok(
  autoSyncScript.includes('private path or secret-like reference found after submodule update'),
  'auto-sync must block secret-like submodule updates before committing'
);
assert.ok(cronScript.includes('# BEGIN hard-eng auto-sync'), 'cron installer must manage a marked crontab block');
assert.ok(cronScript.includes('scripts/auto-sync.sh'), 'cron installer must run auto-sync');
assert.ok(cronScript.includes('consent_env_prefix'), 'cron installer must carry installer consent into scheduled jobs');
assert.ok(cronScript.includes('HARD_ENG_SKIP_MCP_CONFIG'), 'cron installer must preserve MCP skip consent');
assert.ok(cronScript.includes('HARD_ENG_SKIP_WATCHDOG'), 'cron installer must preserve watchdog skip consent');
assert.ok(cronScript.includes('Hard Eng auto-sync cron already installed'), 'cron installer must no-op when current cron matches');
assert.ok(cronScript.includes('HARD_ENG_CRON_INSTALL_TIMEOUT_SECONDS'), 'cron installer must bound crontab writes');
assert.ok(cronScript.includes('crontab "$TMP_CRON"'), 'cron installer must install a temp crontab file');
assert.ok(submoduleScript.includes('git submodule update --init --recursive'), 'submodule script must initialize pinned submodules');
assert.ok(submoduleScript.includes('git submodule update --init --remote --recursive'), 'submodule script must support explicit upstream bumps');
assert.ok(submoduleScript.includes('Refusing submodule update'), 'remote submodule update must refuse dirty tracked state');
assert.ok(submoduleScript.includes('read -r -a sources <<< "$source"'), 'submodule script must split multi-path sparse checkout entries');
assert.ok(submoduleScript.includes('sparse-checkout set "${sources[@]}"'), 'submodule script must sparse-checkout only configured skill source paths');
assert.ok(
  submoduleScript.includes('vendor/skill-upstreams/sentry-cli:plugins/sentry-cli/skills/sentry-cli'),
  'submodule script must update the official Sentry CLI skill path'
);
assert.ok(
  submoduleScript.includes('vendor/skill-upstreams/sentry-for-ai:skills'),
  'submodule script must update the official Sentry for AI skill tree'
);
assert.ok(codexWatchdog.includes('CODEX_WATCHDOG_KILL_ORPHANS'), 'watchdog must reap orphaned MCP processes');
assert.ok(codexWatchdog.includes('CODEX_WATCHDOG_KILL_CODEX_APP_ON_STORM'), 'watchdog must handle severe Codex.app storms');
assert.ok(codexWatchdog.includes('CODEX_WATCHDOG_KILL_ORPHANS:-0'), 'watchdog must not kill orphan MCP processes by default');
assert.ok(codexWatchdog.includes('CODEX_WATCHDOG_KILL_CODEX_APP_ON_STORM:-0'), 'watchdog must not kill Codex.app by default');
assert.ok(installScript.includes('<key>CODEX_WATCHDOG_KILL_ORPHANS</key>\n    <string>0</string>'), 'installed watchdog must keep orphan killing opt-in');
assert.ok(installScript.includes('<key>CODEX_WATCHDOG_KILL_CODEX_APP_ON_STORM</key>\n    <string>0</string>'), 'installed watchdog must keep Codex.app killing opt-in');
assert.ok(installScript.includes('<integer>60</integer>'), 'installed watchdog must run every minute');
assert.ok(installScript.includes('<key>CODEX_CLEANUP_STALE_CLI_CWDS</key>'), 'installed watchdog must configure stale CLI cwd scope');
assert.ok(installScript.includes('<key>CODEX_CLEANUP_STALE_CLI_MAX_AGE_SECONDS</key>'), 'installed watchdog must configure stale CLI age gating');
assert.ok(codexWatchdog.includes('policy_cpu'), 'watchdog must use syspolicyd/trustd as storm evidence');
assert.ok(codexWatchdog.includes("tr '\\n' ' '"), 'watchdog must pass Codex root pids to awk without embedded newlines');
assert.ok(codexHealth.includes('mcp counts:'), 'codex-health must report MCP counts');
assert.ok(codexHealth.includes('mcp.config'), 'codex-health must read MCP count from doctor check details');
assert.ok(securityHook.includes('sanitizeLogData(data)'), 'security hook logs must be sanitized before writing');
assert.ok(dangerousHook.includes('sanitizeLogData(data)'), 'dangerous command hook logs must be sanitized before writing');

const prePushHook = path.join(repo, '.git', 'hooks', 'pre-push');
if (fs.existsSync(prePushHook)) {
  const stat = fs.statSync(prePushHook);
  const text = fs.readFileSync(prePushHook, 'utf8');
  assert.ok((stat.mode & 0o111) !== 0, 'installed pre-push hook must be executable');
  assert.ok(text.includes('node "$repo/tests/codex-config-sync.test.mjs"'), 'installed pre-push hook must test live Codex config sync');
  assert.ok(text.includes('node "$repo/tests/setup-uninstall-contract.test.mjs"'), 'installed pre-push hook must test setup/uninstall parity');
  assert.ok(text.includes('node "$repo/tests/uninstall-config-cleanup.test.mjs"'), 'installed pre-push hook must test uninstall config cleanup');
  assert.ok(text.includes('node "$repo/scripts/check-generated-assets.mjs" "$repo"'), 'installed pre-push hook must block stale generated README images');
  assert.ok(text.includes('node "$repo/scripts/check-ssot-guardrails.mjs" "$repo"'), 'installed pre-push hook must enforce SSOT scanner guardrails');
  assert.ok(text.includes('node "$repo/scripts/check-vendor-skill-integrity.mjs" "$repo"'), 'installed pre-push hook must block direct vendored upstream skill edits');
  assert.ok(text.includes('node "$repo/scripts/check-project-naming.mjs" "$repo"'), 'installed pre-push hook must block old project naming');
  assert.ok(text.includes('node "$repo/scripts/check-project-context-gates.mjs" --require-all "$repo"'), 'installed pre-push hook must run product/design context gates');
  assert.ok(text.includes('node "$repo/scripts/check-project-quality-gates.mjs" --require-push-gate "$repo"'), 'installed pre-push hook must run deterministic project quality gate checks');
  assert.ok(text.includes('HARD_ENG_CHECK_SUBMODULES_BEFORE_PUSH'), 'installed pre-push hook must keep submodule status opt-in');
  assert.ok(text.includes('Blocked push: reachable git history contains private path or secret-like references.'));
  assert.ok(text.includes("':!scripts/install.sh'"), 'installed pre-push hook must ignore installer policy literals');
  assert.ok(text.includes("':!tests/markdown-hygiene.test.mjs'"), 'installed pre-push hook must ignore hygiene leak fixture');
}

const preCommitHook = path.join(repo, '.git', 'hooks', 'pre-commit');
if (fs.existsSync(preCommitHook)) {
  const stat = fs.statSync(preCommitHook);
  const text = fs.readFileSync(preCommitHook, 'utf8');
  assert.ok((stat.mode & 0o111) !== 0, 'installed pre-commit hook must be executable');
  assert.ok(text.includes('scripts/check-markdown-hygiene.mjs'), 'installed pre-commit hook must run Markdown hygiene');
  assert.ok(text.includes('scripts/check-project-naming.mjs'), 'installed pre-commit hook must block old project naming');
  assert.ok(text.includes('scripts/check-generated-assets.mjs'), 'installed pre-commit hook must block stale generated README images');
  assert.ok(text.includes('scripts/check-ssot-guardrails.mjs'), 'installed pre-commit hook must enforce SSOT scanner guardrails');
  assert.ok(text.includes('scripts/check-vendor-skill-integrity.mjs'), 'installed pre-commit hook must block direct vendored upstream skill edits');
  assert.ok(text.includes('Blocked commit: staged forbidden files must not be edited.'), 'installed pre-commit hook must block forbidden files');
  assert.ok(text.includes('Blocked commit: staged files over 700 lines must be split below 700.'), 'installed pre-commit hook must block staged files over 700 lines');
  assert.ok(text.includes('HARD_ENG_SCANNER_OWNER'), 'installed pre-commit hook must require the scanner-owner marker for line-cap exceptions');
  assert.ok(text.includes('scripts/*proof*.mjs'), 'installed pre-commit hook must narrow scanner-owner line-cap exceptions by path');
  assert.ok(text.includes('scripts/*regex*.mjs'), 'installed pre-commit hook must allow marked regex owner line-cap exceptions');
  assert.ok(text.includes('Blocked commit: staged content contains secret-like values.'), 'installed pre-commit hook must block secret-like values');
  assert.ok(text.includes('generated_marker="AUTO""-GENERATED"'), 'installed pre-commit hook must define generated marker under set -u');
  assert.ok(text.includes('[[ "$mode" == "160000" ]]'), 'installed pre-commit hook must skip staged submodule gitlinks');
  assert.ok(text.includes("':!scripts/check-markdown-hygiene.mjs'"), 'installed pre-commit hook must ignore checker pattern file');
  assert.ok(text.includes("':!tests/markdown-hygiene.test.mjs'"), 'installed pre-commit hook must ignore test fixture pattern file');
  assert.ok(text.includes('grep -F "$HOME"'), 'installed pre-commit hook must use runtime HOME');
  assert.ok(text.includes('HARD_ENG_PRIVATE_CONTENT_PATTERN'), 'installed pre-commit hook must keep private pattern env support');
  assert.ok(text.includes('Blocked commit: staged content contains private project/local path references.'));
}

const postRewriteHook = path.join(repo, '.git', 'hooks', 'post-rewrite');
if (fs.existsSync(postRewriteHook)) {
  const stat = fs.statSync(postRewriteHook);
  const text = fs.readFileSync(postRewriteHook, 'utf8');
  assert.ok((stat.mode & 0o111) !== 0, 'installed post-rewrite hook must be executable');
  assert.ok(text.includes('"${1:-}" != "rebase"'), 'installed post-rewrite hook must only handle rebases');
  assert.ok(text.includes('scripts/update-submodules.sh'), 'installed post-rewrite hook must update pinned submodules');
  assert.ok(text.includes('HARD_ENG_SKIP_SUBMODULE_UPDATE'), 'installed post-rewrite hook must support skipping submodule updates');
}

for (const relativePath of ['scripts/auto-sync.sh', 'scripts/check-generated-assets.mjs', 'scripts/check-project-context-gates.mjs', 'scripts/check-project-naming.mjs', 'scripts/check-ssot-guardrails.mjs', 'scripts/check-vendor-skill-integrity.mjs', 'scripts/ensure-worktree-ready.sh', 'scripts/install-cron.sh', 'scripts/update-submodules.sh', 'scripts/setup.sh', 'codex/bin/codex-watchdog', 'codex/bin/codex-health']) {
  const stat = fs.statSync(path.join(repo, relativePath));
  assert.ok((stat.mode & 0o111) !== 0, `${relativePath} must be executable`);
}

console.log('git-hooks-contract: pass');
