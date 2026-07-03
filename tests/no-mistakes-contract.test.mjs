#!/usr/bin/env node
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { assertVendoredSkillCheckout } from './helpers/submodules.mjs';

const repo = process.cwd();

function read(relativePath) {
  return fs.readFileSync(path.join(repo, relativePath), 'utf8');
}

function assertIncludes(text, needle, message = `missing ${needle}`) {
  assert.ok(text.includes(needle), message);
}

const readmeText = read('README.md');
const productText = read('PRODUCT.md');
const setupRuntimeText = read('scripts/setup-runtime.sh');
const installText = read('scripts/install.sh');
const uninstallText = read('scripts/uninstall.sh');
const wrapperText = read('scripts/no-mistakes-wrapper.sh');
const wrapperInstallText = read('scripts/no-mistakes-wrapper-install.sh');
const gitmodulesText = read('.gitmodules');
const updateSubmodulesText = read('scripts/update-submodules.sh');
const noMistakesSkillPath = path.join(repo, 'skills', 'no-mistakes');
const noMistakesSkillText = fs.existsSync(path.join(noMistakesSkillPath, 'SKILL.md')) ? fs.readFileSync(path.join(noMistakesSkillPath, 'SKILL.md'), 'utf8') : '';
const noMistakesAxiText = read('integrations/no-mistakes/references/axi-workflow.md');
const noMistakesPrEvidenceText = read('integrations/no-mistakes/references/pr-evidence.md');

assertIncludes(productText, 'no-mistakes ownership: pinned upstream `/no-mistakes` skill');
assertIncludes(productText, 'an `init`-isolating command wrapper refreshed by');
assertIncludes(readmeText, 'Hard Eng installs the upstream binary/state under `~/.no-mistakes` or `NO_MISTAKES_HOME`');
assertIncludes(readmeText, 'normal `scripts/install.sh` refreshes or preserves the wrapper for an existing upstream binary on `PATH`, direct symlink, or managed custom-home wrapper');
assertIncludes(readmeText, '`NM_HOME`/`NO_MISTAKES_HOME` override state while `HARD_ENG_NO_MISTAKES_REAL_BIN` overrides the executable');
assertIncludes(readmeText, 'uninstall restores the normal upstream symlink from the managed wrapper defaults');
assertIncludes(readmeText, 'Hard Eng-specific changes belong in local wrappers, integrations, route maps, hooks, or evals.');

assertIncludes(setupRuntimeText, 'install_no_mistakes_wrapper "$link_path" "$install_dir/no-mistakes"');
assertIncludes(setupRuntimeText, 'is_managed_no_mistakes_wrapper "$binary"');
assertIncludes(setupRuntimeText, 'resolve_no_mistakes_command_binary "$binary"');
assertIncludes(setupRuntimeText, 'install_no_mistakes_wrapper "$link_path" "$real_binary"');
assertIncludes(setupRuntimeText, 'NM_HOME="${NM_HOME:-$NO_MISTAKES_HOME}"');
assertIncludes(installText, 'source "$ROOT/scripts/no-mistakes-wrapper-install.sh"');
assertIncludes(installText, 'refresh_no_mistakes_wrapper');
assertIncludes(wrapperInstallText, 'read_no_mistakes_wrapper_assignment');
assertIncludes(wrapperInstallText, 'infer_no_mistakes_home_from_binary "$resolved"');
assertIncludes(wrapperInstallText, 'is_known_no_mistakes_home "$nm_home" || return 1');
assertIncludes(wrapperInstallText, 'command -v no-mistakes 2>/dev/null');
assertIncludes(wrapperInstallText, 'HARD_ENG_NO_MISTAKES_DEFAULT_REAL_BIN');
assertIncludes(wrapperText, 'HARD_ENG_NO_MISTAKES_DEFAULT_REAL_BIN+x');
assertIncludes(uninstallText, 'restore_no_mistakes_link');
assertIncludes(uninstallText, 'read_no_mistakes_wrapper_assignment');

assertIncludes(gitmodulesText, '[submodule "vendor/skill-upstreams/no-mistakes"]');
assertIncludes(gitmodulesText, 'url = https://github.com/kunchenguid/no-mistakes');
const hasNoMistakesCheckout = assertVendoredSkillCheckout(repo, path.join('vendor', 'skill-upstreams', 'no-mistakes', 'skills', 'no-mistakes', 'SKILL.md'), 'no-mistakes upstream skill must be vendored');
assert.ok(fs.lstatSync(noMistakesSkillPath).isSymbolicLink(), 'skills/no-mistakes must point at the pinned upstream skill');
assert.equal(fs.readlinkSync(noMistakesSkillPath), '../vendor/skill-upstreams/no-mistakes/skills/no-mistakes');
if (hasNoMistakesCheckout) assertIncludes(noMistakesSkillText, 'Validate your code changes through the no-mistakes pipeline');
if (hasNoMistakesCheckout) assertIncludes(noMistakesSkillText, '## Two ways to invoke');
assertIncludes(noMistakesAxiText, 'ensure-worktree-ready.sh');
assertIncludes(noMistakesAxiText, 'explicit refspec');
assertIncludes(noMistakesAxiText, 'For GitHub Actions or `gh` CI failures, inspect all failing checks/logs before');
assertIncludes(noMistakesAxiText, 'batch fixes');
assertIncludes(noMistakesAxiText, 'rerun only the needed workflows/checks');
assertIncludes(noMistakesPrEvidenceText, 'scripts/repair-pr-evidence.mjs');
assertIncludes(noMistakesPrEvidenceText, 'maintainer-owned PR comment or review');
assertIncludes(noMistakesPrEvidenceText, 'run `--check-review-threads` before final loop-complete');
assertIncludes(noMistakesPrEvidenceText.replace(/\s+/g, ' '), 'do not call the repo done after known review comments exist');
assertIncludes(updateSubmodulesText, 'vendor/skill-upstreams/no-mistakes:skills/no-mistakes', 'submodule updater must keep no-mistakes sparse checkout on the vendored skill');

console.log('no-mistakes contract: pass');
