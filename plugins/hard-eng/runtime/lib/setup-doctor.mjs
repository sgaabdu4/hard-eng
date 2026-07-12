import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { sha256 } from './canonical.mjs';
import { auditPreToolHookResponses } from './hook-coexistence.mjs';
import { inspectLegacySurfaces, readCronTextForHome } from './setup-migration.mjs';
import { createCodexPluginClient } from './codex-plugin.mjs';
import { inspectSetupRecovery } from './setup-recovery.mjs';
import { inspectSetupEnvironment } from './setup-environment.mjs';

const reviewedContextModeHooks = new Map([
  ['1.0.168', sha256(JSON.stringify({
    package: 'df355b43768995bfbf36b24e228b749f34cc84dacf0b3faeb5807dd516d5145c',
    pretooluse: '3d31580ad41412399ffd4824b2b6d80072e413e13ad027ef381caf0f52cdd2ed',
    routing: '7447ee2e444743d6581c53aa1cfec9ffe0d904bc5a478d6fe2ac3e09ef0b3462',
    formatter: 'dfe1c57fea9bcab2d04f93ad499e2020285f1b1a8fe580f52bfb466ac1abd722',
    codex_caps: 'cb6fa33e3a591460dfce7bc8776fed87952e7ae9c4a283548670aafb33063490',
  }))],
]);

function contextModeCoexistence(version) {
  const reviewDigest = reviewedContextModeHooks.get(version);
  if (!reviewDigest) {
    return {
      status: 'REVIEW_REQUIRED',
      tested_versions: [...reviewedContextModeHooks.keys()],
      manual_action: 'Do not upgrade Context Mode silently. Review the new Codex PreToolUse routing and prove it neither denies nor rewrites `mcp__hard_eng__state`, then add a deterministic compatibility receipt.',
    };
  }
  const audit = auditPreToolHookResponses([
    {
      owner: 'hard-eng',
      output: { hookSpecificOutput: { permissionDecision: 'allow', updatedInput: { action: 'status', _he: {} } } },
    },
    {
      owner: 'context-mode',
      output: { hookSpecificOutput: { additionalContext: 'Reviewed passive external-MCP guidance only.' } },
    },
  ]);
  return { ...audit, tested_version: version, source_review_digest: reviewDigest };
}

function configFacts(home) {
  const file = path.join(home, '.codex', 'config.toml');
  if (!fs.existsSync(file) || fs.statSync(file).size > 1024 * 1024) {
    return {
      model: null, reasoning: null, hooks: false, codebaseMemory: false, contextMode: false,
      approvalPolicy: null, sandboxMode: null,
    };
  }
  const text = fs.readFileSync(file, 'utf8');
  const value = (name) => new RegExp(`^${name}\\s*=\\s*["']([^"']+)["']`, 'm').exec(text)?.[1] ?? null;
  return {
    model: value('model'),
    reasoning: value('model_reasoning_effort'),
    hooks: /^hooks\s*=\s*true$/m.test(text),
    codebaseMemory: /\[mcp_servers\.[^\]]*codebase[-_]memory[^\]]*\]/i.test(text),
    contextMode: /\[mcp_servers\.[^\]]*context[-_]mode[^\]]*\]/i.test(text),
    approvalPolicy: value('approval_policy'),
    sandboxMode: value('sandbox_mode'),
  };
}

function safetyFacts(facts) {
  const unsafe = facts.approvalPolicy === 'never' || facts.sandboxMode === 'danger-full-access';
  const unknown = !facts.approvalPolicy || !facts.sandboxMode;
  return {
    status: unsafe ? 'FAIL' : unknown ? 'UNKNOWN_RUNTIME_OVERRIDE' : 'PASS',
    approval_policy: facts.approvalPolicy,
    sandbox_mode: facts.sandboxMode,
    runtime_overrides_observable: false,
    enforcement_boundary: 'Codex native approvals and sandbox; PreToolUse hooks are not a complete security boundary.',
    manual_action: unknown
      ? 'Confirm the active task approval policy and sandbox before destructive, secret-bearing, or external actions.'
      : null,
  };
}

function probe(command, args, env) {
  const childEnv = Object.fromEntries(
    [
      'PATH', 'HOME', 'TMPDIR', 'TMP', 'TEMP', 'SHELL', 'LANG', 'LC_ALL', 'TERM',
      'XDG_CONFIG_HOME', 'XDG_CACHE_HOME', 'CODEX_HOME', 'CONTEXT_MODE_DIR', 'CBM_CACHE_DIR',
    ]
      .filter((key) => env[key] !== undefined)
      .map((key) => [key, env[key]]),
  );
  const result = spawnSync(command, args, {
    env: { ...childEnv, NO_COLOR: '1' },
    encoding: 'utf8',
    timeout: 15_000,
    maxBuffer: 256 * 1024,
    shell: false,
  });
  const output = `${result.stdout ?? ''}\0${result.stderr ?? ''}`;
  const sanitized = output.replace(/\x1b\[[0-?]*[ -/]*[@-~]/g, '');
  const line = sanitized.split(/\0|\r?\n/).find((value) => value.trim())?.trim().slice(0, 120) ?? null;
  return {
    ok: result.status === 0 && !result.error,
    version_or_status: line,
    output_digest: sha256(output),
    sanitized,
  };
}

function supportTools(facts, env) {
  const cbmVersion = probe('codebase-memory-mcp', ['--version'], env);
  const cbmHelp = probe('codebase-memory-mcp', ['--help'], env);
  const cbmCli = cbmVersion.ok ? probe('codebase-memory-mcp', ['cli', 'list_projects'], env) : { ok: false, output_digest: sha256('not-run') };
  const cbmRequiredCommands = ['index_repository', 'list_projects', 'get_architecture', 'search_graph', 'trace_path', 'detect_changes'];
  const cbmCommandsVerified = cbmHelp.ok && cbmRequiredCommands.every((command) => new RegExp(`\\b${command}\\b`).test(cbmHelp.sanitized));
  const contextDoctor = probe('context-mode', ['doctor'], env);
  const contextHelp = probe('context-mode', ['--help'], env);
  const contextRequiredCommands = ['index', 'search', 'doctor'];
  const contextCommandsVerified = contextHelp.ok
    && contextRequiredCommands.every((command) => new RegExp(`context-mode\\s+${command}\\b`).test(contextHelp.sanitized));
  const contextHealth = contextDoctor.ok
    && ['Storage session: PASS', 'Storage content: PASS', 'Storage stats: PASS', 'Server test: PASS']
      .every((marker) => contextDoctor.sanitized.includes(marker));
  const contextVersion = /\blocal v([0-9]+(?:\.[0-9]+){1,3}(?:[-+][0-9A-Za-z.-]+)?)/.exec(contextDoctor.sanitized)?.[1] ?? null;
  const contextHookEvents = ['PreToolUse', 'PostToolUse', 'SessionStart', 'PreCompact', 'UserPromptSubmit', 'Stop'];
  const contextHookPasses = contextHookEvents.filter((event) => new RegExp(`${event} hook: PASS`).test(contextDoctor.sanitized));
  const contextHooksEnabled = contextHookPasses.length > 0;
  const allContextHooksPass = contextHookPasses.length === contextHookEvents.length;
  const contextHookRouting = {
    status: allContextHooksPass ? 'PASS' : contextHooksEnabled ? 'PARTIAL_REVIEW_REQUIRED' : 'NOT_ENABLED',
    passing: contextHookPasses.length,
    available: contextHookEvents.length,
    required_for_hard_eng: false,
    behavior_scope: 'When enabled, Context Mode plugin hooks are global Codex behavior, not Hard Eng lifecycle state.',
    manual_action: contextHooksEnabled
      ? 'A partial Context Mode hook suite is unsafe. Review/trust every enabled hook or disable that external plugin hook suite, restart Codex, then run `context-mode doctor`.'
      : 'Optional: install and trust the official mksglu/context-mode Codex plugin only if global automatic routing is wanted.',
  };
  const contextCoexistence = contextHooksEnabled
    ? contextModeCoexistence(contextVersion)
    : { status: 'NOT_APPLICABLE', reason: 'context-mode-plugin-hooks-not-active' };
  return {
    'codebase-memory': {
      status: cbmVersion.ok && cbmCli.ok && cbmCommandsVerified ? 'PASS' : 'FAIL',
      primary_configured: facts.codebaseMemory,
      cli_fallback: cbmCli.ok,
      required_commands_verified: cbmCommandsVerified,
      required_commands: cbmRequiredCommands,
      version: cbmVersion.version_or_status,
      evidence_digest: sha256(`${cbmVersion.output_digest}\0${cbmHelp.output_digest}\0${cbmCli.output_digest}`),
      manual_action: 'See https://github.com/DeusData/codebase-memory-mcp; install codebase-memory-mcp explicitly, then run `codebase-memory-mcp cli list_projects`.',
    },
    'context-mode': {
      status: contextHealth && contextVersion && contextCommandsVerified ? 'PASS' : 'FAIL',
      primary_configured: facts.contextMode,
      cli_fallback: contextHealth,
      required_commands_verified: contextCommandsVerified,
      required_commands: contextRequiredCommands,
      version: contextVersion,
      evidence_digest: sha256(`${contextDoctor.output_digest}\0${contextHelp.output_digest}`),
      hook_routing: contextHookRouting,
      hard_eng_coexistence: contextCoexistence,
      manual_action: 'See https://github.com/mksglu/context-mode; explicitly add/trust the Context Mode Codex plugin or run `context-mode doctor`.',
    },
  };
}

function skillDescription(file) {
  const text = fs.readFileSync(file, 'utf8');
  return /^description:\s*(.+)$/m.exec(text)?.[1]?.trim() ?? '';
}

function pluginFacts(sourceRoot) {
  const marketplace = JSON.parse(fs.readFileSync(path.join(sourceRoot, 'plugins', 'marketplace.json'), 'utf8'));
  const names = marketplace.plugins.map((entry) => entry.name);
  if (new Set(names).size !== names.length) throw new Error('Marketplace has duplicate plugin names.');
  if (marketplace.plugins.filter((entry) => entry.policy?.installation === 'INSTALLED_BY_DEFAULT').map((entry) => entry.name).join(',') !== 'hard-eng') {
    throw new Error('Exactly the core hard-eng plugin must be installed by default.');
  }
  const skills = [];
  for (const entry of marketplace.plugins) {
    // Marketplace paths are resolved from the installed home. Source checkout
    // validation must use the canonical distribution owner instead.
    const pluginRoot = path.join(sourceRoot, 'plugins', entry.name);
    const manifest = JSON.parse(fs.readFileSync(path.join(pluginRoot, '.codex-plugin', 'plugin.json'), 'utf8'));
    if (manifest.name !== entry.name || manifest.skills !== './skills/') throw new Error(`Plugin layout is invalid: ${entry.name}.`);
    for (const directory of fs.readdirSync(path.join(pluginRoot, 'skills'), { withFileTypes: true })) {
      if (!directory.isDirectory()) continue;
      const file = path.join(pluginRoot, 'skills', directory.name, 'SKILL.md');
      const description = skillDescription(file);
      if (!description || description.length > 320) throw new Error(`Skill description is invalid: ${entry.name}/${directory.name}.`);
      skills.push({ plugin: entry.name, name: directory.name, description_length: description.length });
    }
  }
  return {
    plugins: names.length,
    skills,
    characters: skills.reduce((total, skill) => total + skill.description_length, 0),
    digest: sha256(JSON.stringify(skills)),
  };
}

function customAgentCount(home) {
  const directory = path.join(home, '.codex', 'agents');
  if (!fs.existsSync(directory)) return 0;
  return fs.readdirSync(directory, { withFileTypes: true })
    .filter((entry) => entry.isFile() && entry.name.endsWith('.toml')).length;
}

function modelOperationRisk(sourceRoot) {
  const pkg = JSON.parse(fs.readFileSync(path.join(sourceRoot, 'package.json'), 'utf8'));
  const commands = Object.values(pkg.scripts ?? {}).join('\n');
  const matches = commands.match(/(?:\bcodex\s+exec\b|\bclaude\b|\bimagegen\b|\bno-mistakes\b|\btreehouse\b)/gi) ?? [];
  return { possible: matches.length > 0, command_digest: sha256(commands), matched_command_count: matches.length };
}

function launcherFacts(home, sourceRoot) {
  const launcher = path.join(home, '.local', 'bin', 'he');
  if (!fs.existsSync(launcher)) return { status: 'NOT_INSTALLED', version: null };
  const stat = fs.lstatSync(launcher);
  if (!stat.isFile() || stat.isSymbolicLink()) return { status: 'FAIL', version: null, reason: 'not-a-regular-file' };
  const sourceManifest = JSON.parse(fs.readFileSync(path.join(sourceRoot, 'plugins', 'hard-eng', '.codex-plugin', 'plugin.json'), 'utf8'));
  const text = fs.readFileSync(launcher, 'utf8');
  const version = /^# hard-eng launcher (\S+)$/m.exec(text)?.[1] ?? null;
  const runtime = path.join(home, '.agents', 'plugins', 'hard-eng', 'runtime', 'he.mjs');
  return {
    status: version === sourceManifest.version && fs.existsSync(runtime) && (stat.mode & 0o111) !== 0 ? 'PASS' : 'FAIL',
    version,
    runtime_present: fs.existsSync(runtime),
    executable: (stat.mode & 0o111) !== 0,
  };
}

function legacyFacts(home, env, cronText) {
  const observedCron = cronText === undefined ? readCronTextForHome(home, env) : cronText;
  const { legacy, blockers } = inspectLegacySurfaces(home, { cronText: observedCron });
  const legacyOnly = legacy.filter((entry) => entry.classification !== 'canonical-agents-link');
  const classifications = {};
  for (const entry of legacyOnly) classifications[entry.classification] = (classifications[entry.classification] ?? 0) + 1;
  return {
    detected: legacyOnly.length,
    classifications: Object.fromEntries(Object.entries(classifications).sort(([left], [right]) => left.localeCompare(right))),
    blockers,
    evidence_digest: sha256(JSON.stringify({ legacy, blockers })),
    exact_plan_command: 'node scripts/setup.mjs migrate --dry-run',
  };
}

export function runSetupDoctor({
  home,
  sourceRoot,
  env = process.env,
  pluginClient = createCodexPluginClient({ env }),
  cronText,
  platform = process.platform,
}) {
  const environment = inspectSetupEnvironment(home, env, platform);
  const facts = configFacts(home);
  const plugins = pluginFacts(sourceRoot);
  const activePlugin = pluginClient.inspect(home);
  const recovery = inspectSetupRecovery(home);
  const safety = safetyFacts(facts);
  const tools = supportTools(facts, env);
  const launcher = launcherFacts(home, sourceRoot);
  const modelOperations = modelOperationRisk(sourceRoot);
  const legacy = legacyFacts(home, env, cronText);
  const failures = environment.status === 'FAIL'
    || Object.values(tools).some((tool) => tool.status === 'FAIL')
    || activePlugin.status !== 'PASS'
    || recovery.status !== 'PASS'
    || safety.status === 'FAIL'
    || plugins.characters > 2_500
    || modelOperations.possible
    || launcher.status === 'FAIL';
  const concerns = launcher.status === 'NOT_INSTALLED'
    || safety.status === 'UNKNOWN_RUNTIME_OVERRIDE'
    || legacy.blockers.length > 0
    || tools['context-mode'].hook_routing.status === 'PARTIAL_REVIEW_REQUIRED'
    || (tools['context-mode'].hook_routing.status === 'PASS'
      && tools['context-mode'].hard_eng_coexistence.status !== 'PASS');
  return {
    status: failures ? 'FAIL' : concerns ? 'CONCERNS' : 'PASS',
    mode: 'doctor',
    environment,
    model: { name: facts.model, reasoning_effort: facts.reasoning },
    custom_agent_profiles: customAgentCount(home),
    advertised_context: {
      characters: plugins.characters,
      warning: plugins.characters > 2_500,
      skills: plugins.skills.length,
      digest: plugins.digest,
    },
    paid_or_model_operations: modelOperations,
    support_tools: tools,
    codex_plugin: activePlugin,
    setup_recovery: recovery,
    safety_configuration: safety,
    launcher,
    legacy_surfaces: legacy,
    plugin_layout: { status: 'PASS', plugins: plugins.plugins, default_owner: 'hard-eng' },
    hook_configuration: {
      status: activePlugin.status === 'PASS' ? 'MANUAL_TRUST_REVIEW_REQUIRED' : 'PLUGIN_NOT_READY',
      trust_observable_noninteractively: false,
      manual_action: 'Restart Codex, open `/hooks`, review the exact current plugin-hook hash, and trust it before the first Hard Eng task.',
      automatic_approval_scope: 'mcp__hard_eng__state only after explicit user consent',
    },
    external_plugin_owner_check: 'Official `codex plugin list --available --json` was used; no internal plugin cache was scanned directly.',
  };
}
