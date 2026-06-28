#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';

const home = process.env.HOME;
const repo = path.join(home, '.agents');
const canonical = path.join(repo, 'AGENTS.md');
const text = fs.readFileSync(canonical, 'utf8');
const maxAgentsTokens = 1000;

function assertIncludes(haystack, needle, message = `missing ${needle}`) {
  assert.ok(haystack.includes(needle), message);
}

function assertNotIncludes(haystack, needle, message = `unexpected ${needle}`) {
  assert.ok(!haystack.includes(needle), message);
}

assert.ok(text.startsWith('# Agent Rules\n\n## Stops\n'), 'AGENTS.md must start with rules, not prose preamble');
assertIncludes(text, 'Touched/connected files >700 lines must end <700');
assertIncludes(text, '`SKILL.md`: no 3+ step workflows');
assertIncludes(text, 'Prod -> `PRODUCT.md`; design/UI/token -> `DESIGN.md` + token owner before handoff');
assertIncludes(text, '`codebase-memory`, `context-mode`, `terse` are support tools, not stages');
assertIncludes(text, 'violation -> lint/scanner/gate; repeat -> run/add script/test/hook/eval');
assertIncludes(text, 'GH CI -> parallel logs/jobs, batch fixes, least reruns');
assertIncludes(text, "codebase-memory-mcp cli <tool> '<json>'");
assertIncludes(text, 'Logs/output/docs/data -> sandbox/index; no dumps');
assertIncludes(text, 'Semantic edits: blast radius + surrounding issues');
assertNotIncludes(text, 'This file is the gatekeeper');
assertNotIncludes(text, 'Skills and scripts own detailed workflows');
assertNotIncludes(text, 'codex-update-stack');
assertNotIncludes(text, 'codex-watchdog');
assertNotIncludes(text, 'Codex hooks stay limited');
assertNotIncludes(text, 'SessionStart');
assertNotIncludes(text, 'context-mode hook ...');
assertNotIncludes(text, 'ctx_doctor');
assertNotIncludes(text, 'codex-context-mode-health');
assertNotIncludes(text, 'vendor/skill-upstreams');
assertNotIncludes(text, '## Writing');
assertNotIncludes(text, 'brevity');
assertNotIncludes(text, 'exact-symbol');
assertNotIncludes(text, 'Load `terse`;');
assertNotIncludes(text, '## Final Change Report');
assertIncludes(text, 'Report:');
assertIncludes(text, 'Why: root cause/evidence');
assertIncludes(text, 'What: files/behavior');
assertIncludes(text, 'Risk: Direct callers; Cross-package; Schema/index; Cache/storage keys; Tests/fixtures; Routes/endpoints; Docs/config/agent assets');
assertIncludes(text, 'Proof: tests/gaps');
assertIncludes(text, 'Project AGENTS.md overrides global; repo facts only, <=600 o200k');
assertIncludes(text, 'User-facing replies -> `terse`');
assertIncludes(text, 'React/Next/perf/dupes -> `react-doctor` + `fallow` dupes + `vercel-react-best-practices`');
assertIncludes(text, 'Sentry/observability/issues/setup -> `sentry-workflow` only');
assertIncludes(text, 'Features -> `he-plan`/`he-implement`/`he-verify`; ship:`he-ship`; learn:`he-learn`');
assertIncludes(text, 'Post-`grill-me`: clear skip; brief `to-prd`; missing -> `to-issues`; sliced -> build; big -> both');

const tokenCheck = spawnSync('python3', ['-c', `
import sys
import tiktoken

enc = tiktoken.get_encoding("o200k_base")
print(len(enc.encode(sys.stdin.read())))
`], { input: text, encoding: 'utf8' });
assert.equal(tokenCheck.status, 0, `tiktoken token check failed: ${tokenCheck.stderr.trim()}`);
const agentsTokens = Number.parseInt(tokenCheck.stdout.trim(), 10);
assert.ok(
  Number.isInteger(agentsTokens) && agentsTokens < maxAgentsTokens,
  `AGENTS.md token budget exceeded: ${agentsTokens} >= ${maxAgentsTokens}`,
);

const expectedSymlinks = [
  path.join(home, '.claude', 'AGENTS.md'),
  path.join(home, '.codex', 'AGENTS.md'),
  path.join(home, '.copilot', 'AGENTS.md'),
  path.join(home, '.pi', 'AGENTS.md'),
  path.join(home, '.pi', 'agent', 'AGENTS.md'),
];
const canonicalReal = fs.realpathSync(canonical);
for (const installed of expectedSymlinks) {
  const stat = fs.lstatSync(installed);
  assert.ok(stat.isSymbolicLink(), `${installed} must be a symlink`);
  assert.equal(fs.realpathSync(installed), canonicalReal, `${installed} must point to ${canonical}`);
}

const claudeFile = path.join(home, '.claude', 'CLAUDE.md');
if (fs.existsSync(claudeFile)) {
  const claudeText = fs.readFileSync(claudeFile, 'utf8');
  assertIncludes(claudeText, '@AGENTS.md', `${claudeFile} must include @AGENTS.md`);
}

const installText = fs.readFileSync(path.join(repo, 'scripts', 'install.sh'), 'utf8');
const mcpInstallText = fs.readFileSync(path.join(repo, 'scripts', 'install-mcp-tools.sh'), 'utf8');
const setupText = fs.readFileSync(path.join(repo, 'scripts', 'setup.sh'), 'utf8');
const setupRuntimeText = fs.readFileSync(path.join(repo, 'scripts', 'setup-runtime.sh'), 'utf8');
const setupCombinedText = `${setupText}\n${setupRuntimeText}`;
const gitmodulesText = fs.readFileSync(path.join(repo, '.gitmodules'), 'utf8');
const updateSubmodulesText = fs.readFileSync(path.join(repo, 'scripts', 'update-submodules.sh'), 'utf8');
const readmeText = fs.readFileSync(path.join(repo, 'README.md'), 'utf8');
const ciText = fs.readFileSync(path.join(repo, '.github', 'workflows', 'ci.yml'), 'utf8');
const noMistakesRequiredText = fs.readFileSync(path.join(repo, '.github', 'workflows', 'no-mistakes-required.yml'), 'utf8');
const designDocText = fs.readFileSync(path.join(repo, 'DESIGN.md'), 'utf8');
const routeMapText = fs.readFileSync(path.join(repo, 'skills', 'workflow-help', 'references', 'route-map.md'), 'utf8');
const projectWorkflowGatesHtml = fs.readFileSync(path.join(repo, 'docs', 'project-workflow-gates.html'), 'utf8');
const hePlanText = fs.readFileSync(path.join(repo, 'skills', 'he-plan', 'SKILL.md'), 'utf8');
const lavishSkillText = fs.readFileSync(path.join(repo, 'skills', 'lavish', 'SKILL.md'), 'utf8');
const grillFinalPlanText = fs.readFileSync(path.join(repo, 'skills', 'grill-me', 'modules', 'final-plan.md'), 'utf8');
const grillUiFlowText = fs.readFileSync(path.join(repo, 'skills', 'grill-me', 'modules', 'ui-flow.md'), 'utf8');
const grillVisualDesignText = fs.readFileSync(path.join(repo, 'skills', 'grill-me', 'modules', 'visual-design.md'), 'utf8');
const watchdogText = fs.readFileSync(path.join(repo, 'codex', 'bin', 'codex-watchdog'), 'utf8');
const healthText = fs.readFileSync(path.join(repo, 'codex', 'bin', 'codex-health'), 'utf8');
const updateStackPath = path.join(repo, 'codex', 'bin', 'codex-update-stack');
const updateStackText = fs.readFileSync(updateStackPath, 'utf8');
const contextHealthPath = path.join(repo, 'codex', 'bin', 'codex-context-mode-health');
const contextHealthText = fs.readFileSync(contextHealthPath, 'utf8');
const cleanupPath = path.join(repo, 'codex', 'bin', 'codex-cleanup');
const cleanupText = fs.readFileSync(cleanupPath, 'utf8');
const cbmProbePath = path.join(repo, 'scripts', 'probe-codebase-memory-mcp.mjs');
const cbmProbeText = fs.readFileSync(cbmProbePath, 'utf8');
const contextProbePath = path.join(repo, 'scripts', 'probe-context-mode-mcp.mjs');
const contextProbeText = fs.readFileSync(contextProbePath, 'utf8');
const routingEvalText = fs.readFileSync(path.join(repo, 'tests', 'agents-md-routing', 'evals', 'run-evals.mjs'), 'utf8');
const markdownHygienePath = path.join(repo, 'scripts', 'check-markdown-hygiene.mjs');
const markdownHygieneText = fs.readFileSync(markdownHygienePath, 'utf8');
const generatedAssetsPath = path.join(repo, 'scripts', 'check-generated-assets.mjs');
const generatedAssetsText = fs.readFileSync(generatedAssetsPath, 'utf8');
const generatedAssetsConfigText = fs.readFileSync(path.join(repo, 'generated-assets.json'), 'utf8');
const licenseText = fs.readFileSync(path.join(repo, 'LICENSE'), 'utf8');
const ssotGuardrailsPath = path.join(repo, 'scripts', 'check-ssot-guardrails.mjs');
const ssotGuardrailsText = fs.readFileSync(ssotGuardrailsPath, 'utf8');
const vendorSkillIntegrityText = fs.readFileSync(path.join(repo, 'scripts', 'check-vendor-skill-integrity.mjs'), 'utf8');
const contextGatePath = path.join(repo, 'scripts', 'check-project-context-gates.mjs');
const contextGateText = fs.readFileSync(contextGatePath, 'utf8');
const deterministicOwnerPath = path.join(repo, 'scripts', 'find-deterministic-owner.mjs');
const deterministicOwnerText = fs.readFileSync(deterministicOwnerPath, 'utf8');
const worktreeReadyPath = path.join(repo, 'scripts', 'ensure-worktree-ready.sh');
const worktreeReadyText = fs.readFileSync(worktreeReadyPath, 'utf8');
const autoSyncText = fs.readFileSync(path.join(repo, 'scripts', 'auto-sync.sh'), 'utf8');
const cronText = fs.readFileSync(path.join(repo, 'scripts', 'install-cron.sh'), 'utf8');
const treehouseSkillText = fs.readFileSync(path.join(repo, 'skills', 'treehouse', 'SKILL.md'), 'utf8');
const noMistakesSkillPath = path.join(repo, 'skills', 'no-mistakes');
const noMistakesSkillText = fs.readFileSync(path.join(noMistakesSkillPath, 'SKILL.md'), 'utf8');
const noMistakesAxiText = fs.readFileSync(path.join(repo, 'integrations', 'no-mistakes', 'references', 'axi-workflow.md'), 'utf8');
const noMistakesPrEvidenceText = fs.readFileSync(path.join(repo, 'integrations', 'no-mistakes', 'references', 'pr-evidence.md'), 'utf8');

for (const executable of [cleanupPath, updateStackPath, contextHealthPath, cbmProbePath, contextProbePath, markdownHygienePath, generatedAssetsPath, ssotGuardrailsPath, contextGatePath, deterministicOwnerPath, worktreeReadyPath]) {
  assert.ok(fs.existsSync(executable), `${executable} must exist`);
  assert.ok(fs.statSync(executable).mode & 0o111, `${executable} must be executable`);
}

assertIncludes(setupText, '--prereqs-only', 'setup.sh must expose a prerequisite-only mode');
assertIncludes(setupText, '--safe', 'setup.sh must expose safe setup mode');
assertIncludes(setupText, '--full', 'setup.sh must expose full setup mode');
assertIncludes(setupText, '--skills-only', 'setup.sh must expose skills-only setup mode');
assertIncludes(setupText, '--uninstall', 'setup.sh must expose uninstall delegation mode');
assertIncludes(setupText, '--dry-run', 'setup.sh must expose dry-run mode');
assertIncludes(setupText, 'apply_safe_mode', 'setup.sh must own public-safe setup defaults');
assertIncludes(setupText, 'choose_interactive_default_options', 'setup.sh default mode must own the consent wizard');
assertIncludes(setupText, 'Hard Eng setup will ask before installing workstation-level tools.');
assertIncludes(setupText, 'Install or repair prerequisite tools?');
assertIncludes(setupText, 'Install or update global npm tools?');
assertIncludes(setupText, 'Write active Codex MCP config?');
assertIncludes(setupText, 'Write trusted Codex settings?');
assertIncludes(setupText, 'Install the Codex watchdog and managed bins?');
assertIncludes(setupText, 'elif is_interactive; then');
assertIncludes(setupText, 'HARD_ENG_DRY_RUN', 'setup.sh must support dry-run proof');
assertIncludes(setupText, 'HARD_ENG_SKIP_MCP_CONFIG=1', 'safe and skills-only setup must skip active MCP config');
assertIncludes(setupText, 'HARD_ENG_TRUSTED_WORKSTATION', 'setup dry-run must disclose trusted Codex setting behavior');
assertIncludes(setupText, 'HARD_ENG_ALLOW_HOMEBREW_BOOTSTRAP');
assertNotIncludes(setupText, 'HARD_ENG_SKIP_HOMEBREW_INSTALL');
assertIncludes(readmeText, '<a id="tested-scope"></a>');
assertIncludes(readmeText, 'Hard Eng makes AI coding agents plan, prove, ship, and learn for serious feature and shipping work instead of guessing, editing random files, and saying "done".');
assertIncludes(readmeText, 'It is an opt-in local discipline layer for Codex on macOS today.');
assertIncludes(readmeText, 'Every serious coding task goes through five gates:');
assertIncludes(readmeText, '## 30-Second Version');
assertIncludes(readmeText, '`Ship this feature` -> agent may guess, edit random places, and say done without durable proof.');
assertIncludes(readmeText, '`Ship this feature` -> agent plans, records state, finds the owner, changes the owner, verifies, ships with evidence, and learns from repeated failures.');
assertIncludes(readmeText, 'If you just say "fix this bug", Hard Eng does not automatically run the full `/he:*` workflow.');
assertIncludes(readmeText, 'Start `/he:plan` when you want the full token-intensive workflow for real features, risky changes, or shipping discipline.');
assertIncludes(readmeText, 'User: /he:plan ship login redirect fix');
assertIncludes(readmeText, 'For tiny text edits or throwaway experiments, use the relevant agent directly and run the normal repo checks.');
assertIncludes(readmeText, 'only been tested on Codex running on macOS');
assertIncludes(readmeText, 'MIT License');
assertIncludes(readmeText, 'provided as-is, without warranty');
assertIncludes(readmeText, 'not liable');
assertIncludes(readmeText, 'docs/images/hard-eng-hero.png');
assertIncludes(readmeText, 'docs/images/project-workflow-gates.png');
assertIncludes(readmeText, 'https://www.tiktok.com/@ambition.culture/video/7269802601581989121');
assertIncludes(readmeText, '`context.product`, `context.design`, `context.tokenOwner`');
assertIncludes(readmeText, '`subStages[]`');
assertIncludes(readmeText, '`entryGate`');
assertIncludes(readmeText, '`planReadiness`');
assertIncludes(readmeText, '`agentWork[]`');
assertIncludes(readmeText, 'check-project-context-gates.mjs --require-all');
assertIncludes(readmeText, 'Missing PRODUCT.md routes to `/impeccable init`');
assertIncludes(readmeText, 'missing DESIGN.md routes to `/impeccable document`');
assertIncludes(readmeText, 'Product behavior changes update `PRODUCT.md`; design, UI, component, or token changes update `DESIGN.md`');
assertIncludes(readmeText, 'Required stage gates cannot be skipped');
assertIncludes(readmeText, 'Plan context/owner-proof/artifact-choice/risk-route/state validation');
assertIncludes(readmeText, 'PR review threads');
assertIncludes(readmeText, 'Implement requires a passed `find-deterministic-owner.mjs --json` guardrail');
assertIncludes(readmeText, '`repair-pr-evidence.mjs --check-review-threads`');
assertIncludes(readmeText, 'Subagents recorded in state must use `gpt-5.5`; evals must use `gpt-5.4-mini`');
assertIncludes(readmeText, 'model evals are not a per-session tax');
assertIncludes(readmeText, 'Use `--include-evals` only for skill/routing contract changes, release readiness, or a real regression');
assertIncludes(readmeText, 'Use `--include-session-evals` only when Grill Me conversation behavior changed or needs release proof');
assertIncludes(readmeText, 'Deterministic guardrails include regex scanners, Git hooks, lint/analyze/typecheck commands, SSOT scanners, Fallow, React Doctor, and repeat-mistake prevention');
assertIncludes(readmeText, '`guardrailInventory.requiredGuardrails[]`');
assertIncludes(readmeText, 'missing, failed, unresolved, or skipped-without-reason/evidence guardrails block ready handoff');
assertIncludes(readmeText, 'Impeccable Live');
assertIncludes(readmeText, 'real app route with current tokens/components first');
assertIncludes(readmeText, 'current-design-system mock only when the real surface cannot exist yet');
assertIncludes(readmeText, 'Lavish');
assertIncludes(readmeText, 'npx -y lavish-axi poll');
assertIncludes(readmeText, '`planReadiness.uiReview.lavish`');
assertIncludes(readmeText, 'SSOT guardrails are also deterministic');
assertIncludes(readmeText, 'duplicated commands, scanner owners, colors, and policy concepts');
assertNotIncludes(readmeText, 'Vendored upstream skills are canonical and read-only');
assertNotIncludes(readmeText, 'change the local wrapper, route-map, integration script, hook, or eval');
for (const inspirationLink of [
  'https://github.com/EveryInc/compound-engineering-plugin',
  'https://github.com/bmad-code-org/BMAD-METHOD',
  'https://github.com/mattpocock/skills',
  'https://github.com/google-labs-code/design.md',
  'https://github.com/kunchenguid/treehouse',
  'https://github.com/kunchenguid/lavish-axi',
  'https://github.com/kunchenguid/no-mistakes',
  'https://github.com/pbakaus/impeccable',
  'https://github.com/millionco/react-doctor',
  'https://github.com/fallow-rs/fallow-skills',
  'https://github.com/vercel-labs/agent-skills',
  'https://github.com/anthropics/skills',
  'https://github.com/tavily-ai/skills',
  'https://github.com/getsentry/sentry-for-ai',
  'https://github.com/getsentry/cli',
]) assertIncludes(readmeText, inspirationLink);
assertIncludes(readmeText, 'Grill Me-style human alignment and senior-engineer taste');
assertIncludes(readmeText, 'Hard Eng makes it stateful with stage receipts, context gates, and loop enforcement.');
assertIncludes(readmeText, 'curl -fsSLO https://raw.githubusercontent.com/sgaabdu4/hard-eng/main/scripts/setup.sh');
assertIncludes(readmeText, 'bash setup.sh --safe');
assertIncludes(readmeText, 'Running `bash setup.sh` with no mode starts an interactive wizard');
assertIncludes(readmeText, 'In non-interactive shells and CI, no-mode setup uses `--safe` behavior');
assertIncludes(readmeText, 'bash setup.sh --safe --dry-run');
assertIncludes(readmeText, 'bash setup.sh --full');
assertIncludes(readmeText, 'bash setup.sh --skills-only');
assertIncludes(readmeText, './scripts/install.sh --dry-run');
assertIncludes(readmeText, './scripts/uninstall.sh --yes');
assertIncludes(readmeText, './scripts/uninstall.sh --yes --dry-run');
assertIncludes(readmeText, 'bash setup.sh --uninstall --yes');
assertIncludes(readmeText, '## Install Security');
assertIncludes(readmeText, 'approval_policy = "never"');
assertIncludes(readmeText, 'sandbox_mode = "danger-full-access"');
assertIncludes(readmeText, 'not written by default');
assertIncludes(readmeText, 'HARD_ENG_TRUSTED_WORKSTATION=1');
assertIncludes(readmeText, 'HARD_ENG_SKIP_MCP_CONFIG=1');
assertIncludes(readmeText, 'Setup switches are shell environment variables');
assertIncludes(readmeText, 'HARD_ENG_TRUSTED_WORKSTATION=1 bash setup.sh --full');
assertIncludes(readmeText, 'export HARD_ENG_SKIP_NPM_INSTALL=1');
assertIncludes(readmeText, 'unset HARD_ENG_SKIP_NPM_INSTALL HARD_ENG_SKIP_MCP_CONFIG');
assertIncludes(readmeText, 'Global npm tools: `context-mode`, `codebase-memory-mcp`, `@openai/codex`');
assertIncludes(readmeText, 'Managed Codex bins under `~/.codex/bin`');
assertIncludes(readmeText, 'Runs `codex-watchdog` every 60 seconds');
assertIncludes(readmeText, 'process killing remains opt-in via watchdog env vars');
assertIncludes(readmeText, 'If any installer mode, managed path, automatic tool, or trust setting changes, update this README in the same change.');
assertIncludes(readmeText, '## Repository Guardrails');
assertIncludes(readmeText, 'Installing Hard Eng does not grant push access to this upstream repository.');
assertIncludes(readmeText, 'changes merge through pull requests only');
assertIncludes(readmeText, 'direct pushes to `main` are blocked by branch protection');
assertIncludes(readmeText, 'repository write and merge permission is limited to `sgaabdu4`');
assertNotIncludes(readmeText, 'approving reviews are not required');
assertNotIncludes(readmeText, 'the last push needs approval');
assertNotIncludes(readmeText, 'force-pushes and branch deletion');
assertIncludes(readmeText, '| `hard-eng` | GitHub Actions runs `node scripts/check-hard-eng-full-repo.mjs` against the PR. |');
assertIncludes(readmeText, '| `no-mistakes-required` | The PR contains passed no-mistakes evidence from `sgaabdu4` for the current head before review or merge.');
assertIncludes(readmeText, 'current head SHA plus `No open no-mistakes findings` or `outcome: checks-passed`');
assertIncludes(readmeText, 'If branch-protection rules, required check names, or no-mistakes PR evidence behavior change, update this README and the workflow contract tests in the same change.');
assertIncludes(noMistakesRequiredText, 'name: no-mistakes-required');
assertIncludes(noMistakesRequiredText, 'pull_request:');
assertIncludes(noMistakesRequiredText, 'issue_comment:');
assertIncludes(noMistakesRequiredText, 'pull_request_review:');
assertIncludes(noMistakesRequiredText, 'REQUIRED_AUTHOR: sgaabdu4');
assertIncludes(noMistakesRequiredText, 'pr.head.sha');
assertIncludes(noMistakesRequiredText, '<!-- nm-pr-evidence:start -->');
assertIncludes(noMistakesRequiredText, 'passedEvidencePattern');
assertIncludes(noMistakesRequiredText, 'No open no-mistakes findings');
assertNotIncludes(noMistakesRequiredText, '|checks-passed/i');
assertNotIncludes(noMistakesRequiredText, 'No-mistakes Evidence|no-mistakes axi');
assertIncludes(noMistakesRequiredText, 'createCommitStatus');
assertIncludes(readmeText, 'Codex skill triggers, not shell commands');
for (const requiredContextFile of ['PRODUCT.md', 'DESIGN.md', 'docs/design/tokens.css']) {
  assert.ok(fs.existsSync(path.join(repo, requiredContextFile)), `${requiredContextFile} must exist`);
}
assertIncludes(designDocText, 'https://github.com/google-labs-code/design.md');
assertIncludes(designDocText, 'https://github.com/pbakaus/impeccable');
assertNotIncludes(readmeText, 'less setup.sh && bash setup.sh');
assertNotIncludes(readmeText, 'curl -fsSL https://raw.githubusercontent.com/sgaabdu4/hard-eng/main/scripts/setup.sh | bash');
assertNotIncludes(readmeText, String.fromCharCode(65, 98, 105, 100) + ' Agents');
assertNotIncludes(readmeText, String.fromCharCode(65, 66, 73, 68) + '_AGENTS');
assertNotIncludes(readmeText, '/a' + 'a:');
assertNotIncludes(readmeText, 'a' + 'a-state');
assertIncludes(readmeText, 'scripts/ensure-worktree-ready.sh');
assertIncludes(readmeText, 'when slices are missing or should be published as work items');
assertIncludes(readmeText, 'React app or Next.js implementation/review');
assertIncludes(readmeText, 'include `fallow dupes` / clone-group checks for duplication');
assertIncludes(routeMapText, 'Create a Treehouse worktree before planning/coding, then run');
assertIncludes(routeMapText, 'Repeat work runs its deterministic owner first');
assertIncludes(routeMapText, 'Run `find-deterministic-owner.mjs --json` and record `deterministic-owner-scan`');
assertIncludes(routeMapText, 'Every violation gets lint/scanner/gate');
assertIncludes(routeMapText, 'known repeat work skips an owner or violation lacks lint/scanner/gate');
assertIncludes(routeMapText, 'ensure-worktree-ready.sh');
assertIncludes(routeMapText, 'Dry-run push only counts after project hooks are active and quality gates pass.');
assertIncludes(routeMapText, 'For GitHub Actions/`gh` CI, parallelize independent logs/jobs, batch fixes locally, rerun fewest checks.');
assertIncludes(routeMapText, 'Use `grill-me` when outcome, scope, proof, risk, UI flow, or visual direction is unclear.');
assertIncludes(routeMapText, 'Let Grill Me own `session_state.md`, its stage map, and one-question loop');
assertIncludes(routeMapText, 'it asks as many one-by-one Qs as needed until aligned with no guesswork.');
assertIncludes(routeMapText, 'run Grill Me UI flow/visual stages, use Impeccable Live on the real app route with current tokens/components first');
assertIncludes(routeMapText, 'use a current-design-system mock only when the real surface cannot exist yet');
assertIncludes(routeMapText, 'Lavish only for UI option comparison and decisions');
assertIncludes(routeMapText, 'npx -y lavish-axi poll');
assertIncludes(routeMapText, '`to-issues` only for missing agent-ready slices');
assertIncludes(routeMapText, 'when the accepted `plan.md` already has vertical slices or task waves');
assertIncludes(routeMapText, '`grill-me` with `atomic-ui` + `impeccable`');
assertIncludes(routeMapText, 'Create the Treehouse worktree before feature planning/coding.');
assertIncludes(routeMapText, 'Run `node "$HOME/.agents/scripts/check-project-context-gates.mjs" --require-all <path>`');
assertIncludes(routeMapText, 'product changes update `PRODUCT.md`, design/UI/token changes update `DESIGN.md`, and token/design-system owner paths must exist');
assertIncludes(routeMapText, 'Reroute to `he-ship`/`no-mistakes` only after committed implementation work is ready for the gate.');
assertIncludes(routeMapText, 'Run `security-review` or `performance-rescue` when requested or when those risks were touched, then `thermo-nuclear-code-quality-review`, then `e2e` last');
assertIncludes(routeMapText, 'Loop back to Implement until tests, reviews, and required E2E are clean.');
assertIncludes(routeMapText, 'Add or wire deterministic guardrails in `guardrails[]`');
assertIncludes(routeMapText, 'React/Next changes need React Doctor + Fallow audit/dupes + lint/typecheck gate');
assertIncludes(routeMapText, 'Flutter changes need package-root `dart analyze` with `flutter_skill_lints` plus tests');
assertIncludes(routeMapText, 'Load `test-quality`, list behavior scenarios, add or identify the smallest failing test first');
assertIncludes(routeMapText, 'record the red state as `test-first-proof`');
assertIncludes(routeMapText, 'every repeated miss, review gap, process gap, or missing future guard becomes a learning finding');
assertIncludes(routeMapText, '`loop-complete` is invalid while open learning findings exist');
assertIncludes(routeMapText, 'Run every guardrail command in `guardrails[]`; missing or failing guard routes to `he-implement`.');
assertIncludes(routeMapText, 'node "$HOME/.agents/scripts/check-project-quality-gates.mjs" --require-push-gate .');
assertIncludes(routeMapText, 'Order is fixed: 1 `he-plan` -> 2 `he-implement` -> 3 `he-verify` -> 4 `he-ship` -> 5 `he-learn` when needed.');
assertIncludes(routeMapText, 'Each stage runs until its exit is true or blocked');
assertIncludes(routeMapText, 'Prefer a fresh thread for each stage.');
assertIncludes(routeMapText, 'Start the new thread with the handover prompt from the prior receipt');
assertIncludes(routeMapText, 'worktree path, `he-state.json` path, stage, state, next target, blockers, artifacts');
assertIncludes(routeMapText, 'The visible command is one `he-*` command per stage.');
assertIncludes(routeMapText, 'uses parallel subagents only for independent work that can merge back through the active stage.');
assertIncludes(routeMapText, 'State is required: each feature keeps an `he-state.json` in the plan/worktree.');
assertIncludes(routeMapText, 'every required stage checklist updates `subStages[]`');
assertIncludes(routeMapText, 'every later stage records `entryGate` from the prior `PASS`');
assertIncludes(routeMapText, 'Plan also records `context.product`, `context.design`, `context.tokenOwner`, and `planReadiness`');
assertIncludes(routeMapText, 'Subagent work uses `gpt-5.5`; eval work uses `gpt-5.4-mini`');
assertIncludes(routeMapText, 'every finding from Plan onward updates `findings[]` with owner repair stage');
assertIncludes(routeMapText, 'every deterministic guard updates `guardrails[]` with owner, command, status, evidence, and whether it blocks push');
assertIncludes(routeMapText, 'Return to `he-plan` only when a finding changes scope, owner, proof path, risk route, artifact choice, or Grill Me stage map.');
assertIncludes(routeMapText, 'Before any `Next: ... yes`, run `node "$HOME/.agents/scripts/he-state.mjs" validate <he-state.json>`.');
assertIncludes(routeMapText, 'To avoid context rot, every stage exits with a receipt, not a transcript');
assertIncludes(routeMapText, '`Stage:` current stage; `State:` path to `he-state.json`; `Decision:` pass/blocker; `Owner/proof:` paths or commands; `Artifacts:` links/paths; `Blocker:` none or exact ask; `Next:` ready/not-ready; `Handover prompt:`');
assertIncludes(routeMapText, 'Vendored upstream skills are canonical and read-only.');
assertIncludes(routeMapText, 'Update state before and after each internal step, not only at stage end');
assertIncludes(routeMapText, 'Record every required stage checklist item in `subStages[]`');
assertIncludes(routeMapText, 'Record `entryGate` for stages 2-5');
assertIncludes(routeMapText, 'Record Grill Me/UI readiness in `planReadiness`');
assertIncludes(routeMapText, 'Record `agentWork[]`; subagents must use `gpt-5.5`, evals must use `gpt-5.4-mini`');
assertIncludes(routeMapText, 'Eval cadence is realistic: deterministic state/hooks/scanners run by default');
assertIncludes(routeMapText, '`gpt-5.4-mini` model evals run only for skill/routing contract changes, release readiness, or a regression');
assertIncludes(routeMapText, 'Record product/design context in `context`: `PRODUCT.md`, `DESIGN.md`, and token/design-system owner path');
assertIncludes(routeMapText, 'Product behavior changes update `PRODUCT.md`; design/UI/token changes update `DESIGN.md` and the token owner');
assertIncludes(routeMapText, 'New stage threads read `he-state.json` first; they do not need the previous chat transcript');
assertIncludes(routeMapText, '`next.ready: true` is invalid while any step is pending, in progress, or blocked');
assertIncludes(routeMapText, '`next.ready: true` is invalid while blocking findings or push-blocking guardrails are unresolved');
assertIncludes(routeMapText, '`next.ready: true` is invalid without the stage-required guardrails');
assertIncludes(routeMapText, 'Auto-fix loop: diagnose failures, route code changes back through `he-implement`, update state, rerun affected proof only, repeat until clean or blocked.');
assertIncludes(routeMapText, 'Every failed stage records a finding in `he-state.json`, loops to the owning repair stage');
assertIncludes(routeMapText, 'unresolved actionable threads route back to the right stage before loop-complete');
assertIncludes(routeMapText, 'known Copilot or human review threads are unresolved or unread');
assertIncludes(routeMapText, '| `he-ship` | Use the no-mistakes response loop; code changes return through `he-implement`, proof gaps through `he-verify`, gate/evidence fixes stay in `he-ship`. |');
assertIncludes(routeMapText, '`/he:plan` is human shorthand for `he-plan`');
assertIncludes(routeMapText, '`/he:ship` | `he-ship` | Stage 4. Ends by saying if `/he:learn` is needed or if the loop is complete.');
assertIncludes(routeMapText, 'Skip this stage when learning is empty; if it runs, loop-complete requires a fixed or accepted learning finding');
assertIncludes(routeMapText, 'React app/Next.js');
assertIncludes(routeMapText, 'include `fallow dupes` / clone-group checks for duplication or copy-paste');
for (const needle of [
  'Plan, Implement, Verify, Ship, Learn',
  'Run one <code>/he:*</code> command per stage.',
  'Start each stage in a fresh thread with the handover prompt from the prior receipt',
  'supporting skills, state updates, validation, receipts, and parallel subagents',
  '<strong>Invokes automatically</strong>',
  'Treehouse and worktree readiness for isolation',
  '<code>check-project-context-gates.mjs --require-all</code>',
  '<strong>Context docs</strong>',
  'Product changes update <code>PRODUCT.md</code>.',
  'Design, UI, component, or token changes update <code>DESIGN.md</code>',
  '<code>grill-me</code> for unclear outcome, scope, proof, risk, UI flow, or visual direction',
  '<strong>Grill Me behavior</strong>',
  'It asks unlimited one-by-one questions until user and AI are aligned with no guesswork.',
  '<code>subStages[]</code>',
  '<code>entryGate</code>',
  '<code>planReadiness</code>',
  'Uses parallel subagents on <code>gpt-5.5</code>',
  'evals use <code>gpt-5.4-mini</code>',
  '<strong>UI decision gate</strong>',
  'Impeccable Live',
  'Lavish is only for comparing UI options and decisions',
  '<code>npx -y lavish-axi poll</code>',
  'Non-skippable sub-stages include state validation, owner read/change, tests, quality gates, no-mistakes, PR review threads, durable-owner, and proof.',
  'SSOT scanner guardrails keep duplicated commands, scanner owners, colors, and policy concepts tied to source files.',
  '<code>to-prd</code> or <code>to-issues</code> only when the plan needs that artifact',
  '<code>find-deterministic-owner.mjs --json</code>',
  '<code>codebase-design</code> when ownership is unclear',
  'touched-area skills such as React, Flutter, Appwrite, UI, Sentry, security, or performance',
  '<strong>Guardrails</strong>',
  'React/Next gets React Doctor, Fallow audit/dupes, lint, and typecheck.',
  'Flutter gets package-root <code>dart analyze</code> with <code>flutter_skill_lints</code>',
  '<code>test-quality</code> for assertions and gaps',
  'thermo review before expensive UI proof',
  '<code>check-project-quality-gates.mjs --require-push-gate</code>',
  '<code>repeated-failure-learning</code> captures the pattern',
  '<code>skill-creator</code> updates stage skills when they are the owner',
  '<h2>Automatic Work</h2>',
  'Loads the required specialist skills for the touched area.',
  'Records <code>PRODUCT.md</code>, <code>DESIGN.md</code>, and token/design-system owner paths before implementation readiness.',
  'Records findings with an owner repair stage and guardrails with command, status, evidence, and push-blocking status.',
  'Uses parallel subagents on <code>gpt-5.5</code> when tasks are independent; evals use <code>gpt-5.4-mini</code>.',
  'Validates state before any ready-yes handoff.',
  'compact receipt: stage, state path, decision, owner/proof, artifacts, blocker, next, handover prompt',
  '<strong>Auto-fix loop</strong>',
  'Diagnose failures, route code changes back through <code>/he:implement</code>',
  'rerun only affected proof',
  'Verify failures loop back through <code>/he:implement</code>; proof reruns after each fix.',
  '<h2>Failure Loops</h2>',
  '<code>/he:plan</code> stays in planning until missing owner, scope, proof, risk, or Grill Me alignment is resolved.',
  '<code>/he:implement</code> loops in implementation unless owner or scope changed',
  '<code>/he:ship</code> uses the no-mistakes loop',
  '<code>/he:learn</code> stays in learning until the durable guard owner exists and passes.',
  '<code>/he:implement</code> starts only after <code>/he:plan</code> is <code>PASS</code>.',
  'Parallel subagents are used only for independent work and merge back through the active <code>he-*</code> stage.',
  'Decide owner, proof, risk, and readiness.',
  '/he:plan',
  'Next: ready for /he:implement: yes/no',
  'Next: ready for /he:verify: yes/no',
  'Next: ready for /he:ship: yes/no',
  'Next: ready for /he:learn: yes',
  'OR Next: loop complete: yes',
  'Next: loop complete: yes/no',
  'Change the canonical owner',
  '/he:implement',
  'Runs the proof loop',
  '/he:verify',
  'Runs status/secrets checks',
  '/he:ship',
  'Learn and tighten',
  '/he:learn',
  'Visual quick reference derived from <code>skills/workflow-help/references/route-map.md</code>',
]) assertIncludes(projectWorkflowGatesHtml, needle);
assertIncludes(hePlanText, 'check-project-context-gates.mjs --require-all');
assertIncludes(hePlanText, '`/impeccable init` creates PRODUCT.md');
assertIncludes(hePlanText, '`/impeccable document` creates or refreshes DESIGN.md');
assertIncludes(hePlanText, 'he-state.json.context');
assertIncludes(hePlanText, 'Product changes update `PRODUCT.md`; design/UI/token changes update `DESIGN.md` and the token owner');
assertIncludes(hePlanText, 'Grill Me owns the active question/state');
assertIncludes(hePlanText, 'Impeccable Live reviews the real app route with the current design system first');
assertIncludes(hePlanText, 'current-design-system mock only when the real surface cannot exist yet');
assertIncludes(hePlanText, 'Lavish is decision capture only');
assertIncludes(hePlanText, 'separate browser surfaces and receipts');
assertIncludes(hePlanText, 'Impeccable Live URL for review, Lavish URL/poll for capture');
assertIncludes(hePlanText, 'direct Live buttons are not Lavish receipts unless `window.lavish` capture actually ran');
assertIncludes(grillFinalPlanText, 'Sliced plan -> readiness');
assertIncludes(grillFinalPlanText, '`to-issues` only for missing');
assertIncludes(grillFinalPlanText, '## Product/Design Context');
assertIncludes(grillFinalPlanText, 'Plan cannot hand off to implementation without PRODUCT.md, DESIGN.md, and token/design-system owner evidence');
assertIncludes(grillFinalPlanText, 'Product behavior changes update `PRODUCT.md`; design/UI/token changes update `DESIGN.md` and the token owner');
assertIncludes(gitmodulesText, '[submodule "vendor/skill-upstreams/lavish-axi"]');
assertIncludes(gitmodulesText, 'url = https://github.com/kunchenguid/lavish-axi');
assert.ok(fs.existsSync(path.join(repo, 'vendor', 'skill-upstreams', 'lavish-axi', 'skills', 'lavish', 'SKILL.md')), 'Lavish upstream skill must be vendored');
assert.ok(fs.existsSync(path.join(repo, 'skills', 'lavish', 'SKILL.md')), 'Lavish local skill wrapper must exist');
assert.ok(!fs.lstatSync(path.join(repo, 'skills', 'lavish')).isSymbolicLink(), 'Lavish wrapper must narrow upstream behavior instead of exposing the broad upstream skill directly');
for (const entry of fs.readdirSync(path.join(repo, 'skills'))) {
  const skillPath = path.join(repo, 'skills', entry);
  const stat = fs.lstatSync(skillPath);
  if (!stat.isSymbolicLink()) continue;
  const link = fs.readlinkSync(skillPath);
  assert.ok(link.startsWith('../vendor/skill-upstreams/'), `${entry} skill symlink must point inside vendor/skill-upstreams`);
  const submodulePath = link.replace(/^\.\.\//, '').split('/').slice(0, 3).join('/');
  assertIncludes(gitmodulesText, `path = ${submodulePath}`, `${entry} upstream skill must have a .gitmodules path`);
  assert.ok(fs.existsSync(path.join(skillPath, 'SKILL.md')), `${entry} upstream skill link must expose SKILL.md`);
}
assertIncludes(lavishSkillText, 'current Grill Me');
assertIncludes(lavishSkillText, '--agent-reply');
assertIncludes(lavishSkillText, 'Do not ask the next Grill Me question only in chat while a Lavish session is');
assertIncludes(lavishSkillText, 'native form controls');
assertIncludes(lavishSkillText, 'window.lavish.queuePrompt()');
assertIncludes(lavishSkillText, 'sendQueuedPrompts()');
assertIncludes(lavishSkillText, 'Direct Impeccable Live pages must not claim `Sent to Lavish`');
assertIncludes(lavishSkillText, 'manual browser-read receipt');
assertIncludes(lavishSkillText, 'Do not rely on browser `localStorage`/`sessionStorage`');
assertIncludes(grillUiFlowText, 'project-local route/component/state');
assertIncludes(grillUiFlowText, 'artifact first');
assertIncludes(grillUiFlowText, 'the Lavish artifact is the visible question surface');
assertIncludes(grillUiFlowText, 'never ask the next question only in chat');
assertIncludes(grillUiFlowText, 'Grill Me owns the active question and state files');
assertIncludes(grillUiFlowText, 'Impeccable Live reviews the real app route first');
assertIncludes(grillUiFlowText, 'separate browser surfaces and receipts');
assertIncludes(grillUiFlowText, 'Direct Impeccable Live pages must not claim `Sent to Lavish`');
assertIncludes(grillUiFlowText, 'manual browser-read');
assertIncludes(grillUiFlowText, 'wireflows/maps/state boards, not visual direction');
assertIncludes(grillUiFlowText, '`atomic-ui` and `impeccable`');
assertIncludes(grillUiFlowText, '`/impeccable init` for PRODUCT.md');
assertIncludes(grillUiFlowText, '`/impeccable document` for DESIGN.md');
assertIncludes(grillVisualDesignText, 'Project-local direction boards');
assertIncludes(grillVisualDesignText, 'context.mjs');
assertIncludes(grillVisualDesignText, 'missing `PRODUCT.md`/`NO_PRODUCT_MD`');
assertIncludes(grillVisualDesignText, '`/impeccable init`');
assertIncludes(grillVisualDesignText, '`/impeccable document`');
assertIncludes(grillVisualDesignText, 'update the artifact to the exact current');
assertIncludes(grillVisualDesignText, 'Do not continue polling a stale artifact');
assertIncludes(grillVisualDesignText, 'Impeccable Live reviews the real app route first');
assertIncludes(grillVisualDesignText, 'Lavish is decision capture only');
assertIncludes(grillVisualDesignText, 'separate browser surfaces and receipts');
assertIncludes(grillVisualDesignText, 'Direct Impeccable Live pages must not claim `Sent to Lavish`');
assertIncludes(grillVisualDesignText, 'subject-project');
assertIncludes(grillVisualDesignText, 'tokens/components/CSS vars');
assertIncludes(grillVisualDesignText, 'project-local token/component owner');
assertIncludes(setupText, 'source "$ROOT/scripts/setup-runtime.sh"', 'setup.sh must delegate post-clone workstation helpers to setup-runtime.sh');
assertIncludes(setupCombinedText, 'install_or_update_treehouse');
assertIncludes(setupCombinedText, 'ensure_worktree_ready_repo');
assertIncludes(setupCombinedText, 'HARD_ENG_SKIP_WORKTREE_READY');
assertIncludes(setupCombinedText, 'HARD_ENG_WORKTREE_READY_INSTALL');
assertIncludes(setupCombinedText, 'HARD_ENG_SETUP_TREEHOUSE');
assertIncludes(setupCombinedText, 'HARD_ENG_SKIP_TREEHOUSE');
{
  const mainFlow = setupText.slice(setupText.lastIndexOf('install_prerequisites'));
  assert.ok(mainFlow.indexOf('clone_or_update_repo') < mainFlow.indexOf('source "$ROOT/scripts/setup-runtime.sh"'), 'setup must clone/update before sourcing runtime helpers');
  assert.ok(mainFlow.indexOf('source "$ROOT/scripts/setup-runtime.sh"') < mainFlow.indexOf('choose_setup_options'), 'setup must load runtime helpers before prompting for repo-owned skills');
}
assertIncludes(setupCombinedText, 'https://kunchenguid.github.io/treehouse/install.sh');
assertIncludes(readmeText, '[`Treehouse`](https://github.com/kunchenguid/treehouse)');
assertIncludes(setupText, 'install_python_prerequisites');
assertIncludes(setupText, 'python3 -m pip install --user tiktoken');
assertIncludes(setupText, 'HARD_ENG_SKIP_NPM_INSTALL=1 HARD_ENG_SKIP_SUBMODULE_INIT=1 "$ROOT/scripts/install.sh"');
assertIncludes(installText, '"$ROOT/scripts/setup.sh" --prereqs-only');
assertIncludes(installText, '--dry-run', 'install.sh must expose dry-run mode');
assertIncludes(installText, 'print_install_dry_run', 'install.sh must print planned writes without mutating');
assertIncludes(installText, 'HARD_ENG_SKIP_MCP_CONFIG', 'install.sh must support setup --skills-only without MCP/global npm requirements');
assertIncludes(installText, 'HARD_ENG_TRUSTED_WORKSTATION', 'install.sh must keep trusted Codex settings opt-in');
assertIncludes(installText, 'approval_policy = "never"', 'install.sh must explicitly handle approval_policy trust setting');
assertIncludes(installText, 'sandbox_mode = "danger-full-access"', 'install.sh must explicitly handle sandbox_mode trust setting');
assertIncludes(installText, 'drop_top_level(trusted_settings)', 'install.sh must remove legacy managed trust settings when not trusted');
assertIncludes(installText, 'drop_sections(managed_mcp_sections)', 'install.sh must remove legacy managed MCP sections when MCP config is skipped');
assertIncludes(installText, 'remove_managed_executable "$ROOT/codex/bin/codex-update-stack"', 'install.sh must remove managed stack repair when not trusted');
assertIncludes(installText, 'HARD_ENG_REMOVE_MANAGED_CRON', 'install.sh must remove managed cron blocks only with cleanup consent');
assertIncludes(setupText, 'HARD_ENG_REMOVE_MANAGED_CRON=1', 'safe and skills-only setup must remove managed cron blocks');
assertIncludes(installText, 'codex-context-mode-health', 'install.sh must install the no-hooks context-mode health check');
assertIncludes(installText, 'ensure_claude_stub', 'install.sh must keep Claude reduced to AGENTS.md plus CLAUDE.md');
assertNotIncludes(installText, '"$HOME/.claude/skills"', 'install.sh must not repopulate Claude skills');
assertIncludes(installText, 'CODEX_CBM_COMMAND', 'install.sh must pass a resolved CBM command into Codex config');
assertIncludes(installText, '$HOME/.codex/bin/codebase-memory-mcp', 'install.sh must point Codex at the stable CBM binary copy');
assertIncludes(installText, 'resolve_codebase_memory_mcp_command', 'install.sh must resolve CBM through the stable command owner');
assertIncludes(installText, 'default_mode_request_user_input', 'install.sh must sync Codex request-user-input feature into ~/.codex/config.toml');
assertIncludes(installText, 'node "$repo/scripts/check-generated-assets.mjs" "$repo"', 'install.sh hooks must block stale generated README images');
assertIncludes(installText, 'node "$repo/scripts/check-ssot-guardrails.mjs" "$repo"', 'install.sh hooks must enforce SSOT scanner guardrails');
assertIncludes(installText, 'node "$repo/scripts/check-vendor-skill-integrity.mjs" "$repo"', 'install.sh hooks must block direct vendored upstream skill edits');
assertIncludes(vendorSkillIntegrityText, 'dirty vendored skill upstream');
assertIncludes(vendorSkillIntegrityText, 'repo-owned vendored skill file changed');
assertIncludes(installText, 'node "$repo/scripts/check-project-context-gates.mjs" --require-all "$repo"', 'install.sh hooks must enforce PRODUCT/DESIGN context before push');
assertIncludes(installText, 'mcp_servers.context-mode', 'install.sh must keep context-mode MCP registered');
assertIncludes(installText, 'CONTEXT_MODE_DIR', 'install.sh must pin context-mode storage outside ~/.claude');
assertIncludes(mcpInstallText, 'HARD_ENG_CONTEXT_MODE_VERSION');
assertIncludes(mcpInstallText, '"context-mode@$context_mode_version"');
assertIncludes(mcpInstallText, '"codebase-memory-mcp@$cbm_version"');
assertIncludes(mcpInstallText, '"@openai/codex@$codex_version"');
assertIncludes(setupCombinedText, 'HARD_ENG_NO_MISTAKES_VERSION');
assertIncludes(mcpInstallText, 'ln -s "$npm_bin" "$candidate"', 'CBM setup must link to npm binary');
assert.ok(!mcpInstallText.includes('.backup.'), 'CBM setup must not keep backup binaries');
assertIncludes(ciText, 'node scripts/check-hard-eng-full-repo.mjs', 'GitHub Actions must run the full repo gate');
assertIncludes(ciText, 'submodules: recursive', 'GitHub Actions must check out vendored skill submodules');
assertIncludes(ciText, '>> "$GITHUB_PATH"', 'GitHub Actions must persist npm global bin for later gate steps');

assertIncludes(watchdogText, 'codex-cleanup', 'codex-watchdog must run codex-cleanup');
assertIncludes(watchdogText, 'codex-stack-signature.json', 'codex-watchdog must track Codex stack drift');
assertIncludes(cleanupText, 'SkyComputerUseClient', 'codex-cleanup must trim duplicate computer-use MCP children');
assertIncludes(cleanupText, '/node_repl', 'codex-cleanup must trim duplicate node_repl children');
assertIncludes(cleanupText, 'CODEX_CLEANUP_MCP_CHILD_LIMIT', 'codex-cleanup must cap duplicate MCP children per helper kind');
assertIncludes(cleanupText, 'CODEX_CLEANUP_REPAIR_GLOBAL_STATE', 'codex-cleanup must keep Codex global-state repair opt-in');
assertIncludes(cleanupText, 'CODEX_CLEANUP_DELETE_STALE_THREAD_ROWS', 'codex-cleanup must keep stale thread row deletion opt-in');
assertIncludes(cleanupText, 'stale_codex_cli_groups', 'codex-cleanup must report stale Codex CLI group cleanup');
assertIncludes(cleanupText, 'CODEX_CLEANUP_STALE_CLI_CWDS', 'codex-cleanup must keep stale CLI cleanup scoped by cwd');
assertIncludes(cleanupText, 'CODEX_CLEANUP_STALE_CLI_MAX_AGE_SECONDS', 'codex-cleanup must keep stale CLI cleanup age-gated');
assertIncludes(cleanupText, 'os.killpg', 'codex-cleanup must terminate stale Codex CLI process groups');
assertIncludes(installText, '<integer>60</integer>', 'installed watchdog must run cleanup every minute');
assertIncludes(installText, '<key>CODEX_CLEANUP_STALE_CLI_CWDS</key>', 'installed watchdog must scope stale CLI cleanup to this repo');
assertIncludes(installText, '<string>$ROOT</string>', 'installed watchdog must pass the repo root to stale CLI cleanup');
assertIncludes(installText, '<key>CODEX_CLEANUP_STALE_CLI_MAX_AGE_SECONDS</key>', 'installed watchdog must set the stale CLI age threshold');
assertIncludes(installText, '<string>21600</string>', 'installed watchdog must clean stale repo CLI groups after six hours');
assertIncludes(updateStackText, '"$ROOT/scripts/install.sh"', 'codex-update-stack must run setup after package updates');
assertIncludes(updateStackText, 'trusted-workstation-only', 'codex-update-stack must require trusted workstation consent');
assertIncludes(updateStackText, 'HARD_ENG_TRUSTED_WORKSTATION', 'codex-update-stack must share installer trust consent');
assertIncludes(updateStackText, 'load_installer_consent', 'codex-update-stack must load persisted installer consent before repair');
assertIncludes(updateStackText, 'HARD_ENG_SKIP_MCP_CONFIG', 'codex-update-stack must preserve skipped MCP consent during repair');
assertIncludes(updateStackText, 'probe-codebase-memory-mcp.mjs');
assertIncludes(updateStackText, '$HOME/.codex/bin/codebase-memory-mcp', 'codex-update-stack must probe the stable CBM command');
assertIncludes(updateStackText, 'CBM_MCP_PROBE_TIMEOUT_MS="${CBM_MCP_PROBE_TIMEOUT_MS:-30000}"');
assertIncludes(updateStackText, 'codex-context-mode-health');
assertIncludes(cbmProbeText, '.codex/bin/codebase-memory-mcp', 'CBM probe must prefer the stable Codex-owned command');
assertIncludes(cbmProbeText, "CBM_MCP_PROBE_TIMEOUT_MS ?? '30000'", 'CBM probe must allow slow cold starts');
assertNotIncludes(updateStackText, '["context-mode", "doctor"]', 'codex-update-stack must not call raw context-mode doctor');
assertNotIncludes(updateStackText, 'context-mode doctor missing required PASS checks');
assertIncludes(healthText, 'context-mode no-hooks:');
assertIncludes(healthText, 'codex-context-mode-health');
assertIncludes(healthText, 'manual_repair_env');
assertIncludes(healthText, 'HARD_ENG_SKIP_MCP_CONFIG');
assertIncludes(healthText, 'details=(checks.get("mcp.config") or {}).get("details") or {}');
assertIncludes(contextHealthText, 'context-mode no-hooks config ok: MCP registered; storage pinned to ~/.codex/context-mode; Codex context-mode hooks absent');
assertIncludes(contextHealthText, 'CONTEXT_MODE_DIR');
assertIncludes(contextHealthText, 'probe-context-mode-mcp.mjs');
assertIncludes(contextProbeText, 'ctx_execute');
assertIncludes(contextProbeText, 'ctx_search');
assertIncludes(contextProbeText, 'ctx_stats');
assertIncludes(routingEvalText, 'AGENTS_ROUTING_EVAL_OUT_DIR');
assertIncludes(routingEvalText, "path.join('/tmp', 'agents-md-routing-evals')");
assertIncludes(markdownHygieneText, 'free prose; use a bullet, heading, or fenced template');
assertIncludes(markdownHygieneText, 'bullet must not end with a full stop');
assertIncludes(markdownHygieneText, 'must stay at or under ${maxAgentsLines} lines');
assertIncludes(markdownHygieneText, 'must stay at or under ${maxAgentsTokens} tokens');
assertIncludes(markdownHygieneText, 'requires explicit markdown-hygiene:');
assertIncludes(markdownHygieneText, 'allow-local-machine-paths');
assertIncludes(markdownHygieneText, 'allow-conversation-state');
assertIncludes(markdownHygieneText, 'allow-setup-internals');
assertIncludes(generatedAssetsConfigText, 'docs/project-workflow-gates.html');
assertIncludes(generatedAssetsConfigText, 'docs/images/project-workflow-gates.png');
assertNotIncludes(generatedAssetsConfigText, 'docs/media/stay-hard.mp4');
assertIncludes(generatedAssetsText, 'docs/media');
assertIncludes(generatedAssetsText, 'is older than');
assertIncludes(generatedAssetsText, 'referenced by README.md');
assertIncludes(generatedAssetsText, 'missing for');
assertIncludes(licenseText, 'MIT License');
assertIncludes(licenseText, 'THE SOFTWARE IS PROVIDED "AS IS"');
assertIncludes(licenseText, 'AUTHORS OR COPYRIGHT HOLDERS BE LIABLE');
assertIncludes(ssotGuardrailsText, 'scannerRegistry');
assertIncludes(ssotGuardrailsText, 'patternRules');
assertIncludes(ssotGuardrailsText, 'not registered in ssot-guardrails.json');
assertIncludes(contextGateText, '--require-product-update');
assertIncludes(contextGateText, '--require-design-update');
assertIncludes(contextGateText, 'run /impeccable init');
assertIncludes(contextGateText, 'run /impeccable document');
assertIncludes(contextGateText, 'Token owner');
assertIncludes(deterministicOwnerText, 'package scripts, scripts, tests, hooks');
assertIncludes(deterministicOwnerText, 'Run matching owners before fresh LLM reasoning.');
assertIncludes(deterministicOwnerText, 'package.json');
assertIncludes(worktreeReadyText, 'detect_hook_owner');
assertIncludes(worktreeReadyText, '.husky/_');
assertIncludes(worktreeReadyText, '.githooks');
assertIncludes(worktreeReadyText, '.git-hooks');
assertIncludes(worktreeReadyText, '/.no-mistakes/repos/');
assertIncludes(worktreeReadyText, 'hook_path_is_private_or_gate');
assertIncludes(worktreeReadyText, 'npm --prefix "$repo" run prepare --if-present');
assertIncludes(treehouseSkillText, 'ensure-worktree-ready.sh');
assertIncludes(gitmodulesText, '[submodule "vendor/skill-upstreams/no-mistakes"]');
assertIncludes(gitmodulesText, 'url = https://github.com/kunchenguid/no-mistakes');
assert.ok(fs.existsSync(path.join(repo, 'vendor', 'skill-upstreams', 'no-mistakes', 'skills', 'no-mistakes', 'SKILL.md')), 'no-mistakes upstream skill must be vendored');
assert.ok(fs.lstatSync(noMistakesSkillPath).isSymbolicLink(), 'skills/no-mistakes must point at the pinned upstream skill');
assert.equal(fs.readlinkSync(noMistakesSkillPath), '../vendor/skill-upstreams/no-mistakes/skills/no-mistakes');
assertIncludes(noMistakesSkillText, 'Validate your code changes through the no-mistakes pipeline');
assertIncludes(noMistakesSkillText, '## Two ways to invoke');
assertIncludes(fs.readFileSync(path.join(repo, 'skills', 'he-ship', 'SKILL.md'), 'utf8'), 'Ship-specific worktree and PR-evidence guardrails');
assertIncludes(noMistakesAxiText, 'ensure-worktree-ready.sh');
assertIncludes(noMistakesAxiText, 'explicit refspec');
assertIncludes(noMistakesAxiText, 'For GitHub Actions or `gh` CI failures, inspect all failing checks/logs before');
assertIncludes(noMistakesAxiText, 'batch fixes');
assertIncludes(noMistakesAxiText, 'rerun only the needed workflows/checks');
assertIncludes(noMistakesPrEvidenceText, 'scripts/repair-pr-evidence.mjs');
assertIncludes(noMistakesPrEvidenceText, 'run `--check-review-threads` before final loop-complete');
assertIncludes(noMistakesPrEvidenceText.replace(/\s+/g, ' '), 'do not call the repo done after known review comments exist');

assertIncludes(autoSyncText, 'refresh_local_install', 'auto-sync must refresh installed scripts after pulls');
assertIncludes(autoSyncText, 'HARD_ENG_SKIP_NPM_INSTALL=1', 'auto-sync refresh must not run package updates');
assertIncludes(autoSyncText, 'HARD_ENG_SKIP_PREREQ_INSTALL=1', 'auto-sync refresh must not run prerequisite installers from cron');
assertIncludes(autoSyncText, 'install_env=(env HARD_ENG_SKIP_NPM_INSTALL=1', 'auto-sync refresh must preserve installer consent flags');
assertIncludes(autoSyncText, 'HARD_ENG_SKIP_MCP_CONFIG', 'auto-sync refresh must preserve MCP skip consent');
assertIncludes(autoSyncText, 'HARD_ENG_TRUSTED_WORKSTATION', 'auto-sync refresh must preserve trusted workstation consent');
assertIncludes(autoSyncText, 'update_treehouse', 'auto-sync must update Treehouse when installed');
assertIncludes(updateSubmodulesText, 'vendor/skill-upstreams/lavish-axi:skills/lavish', 'submodule updater must keep Lavish sparse checkout on the vendored skill');
assertIncludes(updateSubmodulesText, 'vendor/skill-upstreams/no-mistakes:skills/no-mistakes', 'submodule updater must keep no-mistakes sparse checkout on the vendored skill');
assertIncludes(updateSubmodulesText, 'vendor/skill-upstreams/appwrite-backend:references', 'submodule updater must sparse-checkout Appwrite skill references without upstream eval payloads');
assertIncludes(updateSubmodulesText, 'vendor/skill-upstreams/building-flutter-apps:references templates hooks .codex-plugin .claude-plugin', 'submodule updater must sparse-checkout Flutter skill assets without upstream eval payloads');
assertIncludes(autoSyncText, 'HARD_ENG_SKIP_TREEHOUSE_UPDATE', 'auto-sync must allow skipping Treehouse update');
assertIncludes(autoSyncText, 'HARD_ENG_TREEHOUSE_BIN', 'auto-sync must allow overriding Treehouse binary');
assertIncludes(autoSyncText, '"$binary" update', 'auto-sync must call treehouse update through the resolved binary');
assertIncludes(autoSyncText, 'git diff --name-only -- .gitmodules vendor/skill-upstreams', 'auto-sync private-path scans must stay scoped to submodule update outputs');
assertIncludes(cronText, 'codex-update-stack', 'cron installer must schedule codex stack updates');
assertIncludes(cronText, 'HARD_ENG_CODEX_STACK_CRON_SCHEDULE', 'codex stack cron schedule must be configurable');
assertIncludes(cronText, 'HARD_ENG_SKIP_CODEX_STACK_CRON', 'codex stack cron must be skippable');
assertIncludes(cronText, 'consent_env_prefix', 'codex stack cron must carry trusted-workstation and skip consent');
assertIncludes(cronText, 'HARD_ENG_SKIP_MCP_CONFIG', 'codex stack cron must preserve MCP skip consent');

console.log('agents-md-contract: pass');
