import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { sha256 } from './canonical.mjs';
import { skillDescription, skillInvocationPolicy } from './skill-metadata.mjs';
import { auditPreToolHookResponses } from './hook-coexistence.mjs';
import { createCodexWiringClient } from './codex-wiring.mjs';
import { inspectSetupRecovery } from './setup-recovery.mjs';
import { inspectSetupEnvironment } from './setup-environment.mjs';
import { inspectLegacyControlPlane } from './legacy-control-plane.mjs';

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
  let text = null;
  try {
    const stat = fs.lstatSync(file);
    if (stat.isFile() && !stat.isSymbolicLink() && stat.size <= 1024 * 1024) {
      text = fs.readFileSync(file, 'utf8');
    }
  } catch (error) {
    if (error.code !== 'ENOENT') throw error;
  }
  if (text === null) {
    return {
      model: null, reasoning: null, hooks: false, contextMode: false,
      approvalPolicy: null, sandboxMode: null,
    };
  }
  const value = (name) => new RegExp(`^${name}\\s*=\\s*["']([^"']+)["']`, 'm').exec(text)?.[1] ?? null;
  return {
    model: value('model'),
    reasoning: value('model_reasoning_effort'),
    hooks: /^hooks\s*=\s*true$/m.test(text),
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

function sourceCheckoutFacts(home, env) {
  const checkout = path.join(home, '.agents');
  if (!fs.existsSync(path.join(checkout, '.git'))) {
    return {
      status: 'NOT_APPLICABLE',
      remote_count: 0,
      evidence_digest: sha256('not-a-git-checkout'),
      manual_action: null,
    };
  }
  const observed = probe('git', ['-C', checkout, 'remote'], env);
  if (!observed.ok) {
    return {
      status: 'FAIL',
      remote_count: null,
      evidence_digest: observed.output_digest,
      manual_action: 'Inspect the trusted Hard Eng source checkout before setup.',
    };
  }
  const remotes = observed.sanitized.split(/\0|\r?\n/).map((line) => line.trim()).filter(Boolean);
  return {
    status: 'PASS',
    remote_count: remotes.length,
    evidence_digest: observed.output_digest,
    manual_action: null,
  };
}

function supportTools(facts, env) {
  const cbmVersion = probe('codebase-memory-mcp', ['--version'], env);
  const cbmHelp = probe('codebase-memory-mcp', ['--help'], env);
  const cbmCli = cbmVersion.ok ? probe('codebase-memory-mcp', ['cli', 'list_projects', '{}'], env) : { ok: false, output_digest: sha256('not-run') };
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
  const codebaseMemoryReady = cbmVersion.ok && cbmCli.ok && cbmCommandsVerified;
  const contextModeReady = contextHealth && contextVersion && contextCommandsVerified;
  return {
    'codebase-memory': {
      status: codebaseMemoryReady ? 'PASS' : 'FAIL',
      transport: 'cli-only',
      cli_ready: cbmCli.ok,
      required_commands_verified: cbmCommandsVerified,
      required_commands: cbmRequiredCommands,
      version: cbmVersion.version_or_status,
      evidence_digest: sha256(`${cbmVersion.output_digest}\0${cbmHelp.output_digest}\0${cbmCli.output_digest}`),
      manual_action: codebaseMemoryReady
        ? null
        : 'See https://github.com/DeusData/codebase-memory-mcp; install codebase-memory-mcp explicitly, then run `codebase-memory-mcp cli list_projects`.',
    },
    'context-mode': {
      status: contextModeReady ? 'PASS' : 'FAIL',
      primary_configured: facts.contextMode,
      cli_fallback: contextHealth,
      required_commands_verified: contextCommandsVerified,
      required_commands: contextRequiredCommands,
      version: contextVersion,
      evidence_digest: sha256(`${contextDoctor.output_digest}\0${contextHelp.output_digest}`),
      hook_routing: contextHookRouting,
      hard_eng_coexistence: contextCoexistence,
      manual_action: contextModeReady
        ? null
        : 'See https://github.com/mksglu/context-mode; explicitly add/trust the Context Mode Codex plugin or run `context-mode doctor`.',
    },
  };
}

export function nativeSkillFacts(sourceRoot) {
  const root = path.join(sourceRoot, 'skills');
  if (!fs.existsSync(root)) throw new Error('Native skills root is missing.');
  const skills = [];
  for (const entry of fs.readdirSync(root, { withFileTypes: true }).sort((left, right) => left.name.localeCompare(right.name))) {
    if (!entry.isDirectory() && !entry.isSymbolicLink()) continue;
    const file = path.join(root, entry.name, 'SKILL.md');
    if (!fs.existsSync(file)) throw new Error(`Native skill entry has no SKILL.md: ${entry.name}.`);
    const description = skillDescription(fs.readFileSync(file, 'utf8'));
    if (!description) throw new Error(`Skill description is missing: ${entry.name}.`);
    const metadataFile = path.join(root, entry.name, 'agents', 'openai.yaml');
    const policy = skillInvocationPolicy(fs.existsSync(metadataFile) ? fs.readFileSync(metadataFile, 'utf8') : '');
    skills.push({
      name: entry.name,
      description_characters: description.length,
      estimated_tokens: Math.ceil(description.length / 4),
      invocation: policy.allow_implicit_invocation ? 'implicit' : 'explicit-only',
      policy_source: policy.source,
    });
  }
  const summarize = (selected) => {
    const characters = selected.reduce((total, skill) => total + skill.description_characters, 0);
    return {
      skill_count: selected.length,
      characters,
      estimated_tokens: Math.ceil(characters / 4),
      descriptions_over_320: selected.filter((skill) => skill.description_characters > 320).length,
    };
  };
  const implicit = skills.filter((skill) => skill.invocation === 'implicit');
  const explicitOnly = skills.filter((skill) => skill.invocation === 'explicit-only');
  return {
    per_skill: skills,
    total: summarize(skills),
    implicit: summarize(implicit),
    explicit_only: summarize(explicitOnly),
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
  if (!stat.isFile() || stat.isSymbolicLink() || stat.size > 64 * 1024) {
    return { status: 'FAIL', version: null, reason: 'unsafe-or-oversized' };
  }
  const sourceManifest = JSON.parse(fs.readFileSync(path.join(sourceRoot, 'package.json'), 'utf8'));
  const text = fs.readFileSync(launcher, 'utf8');
  const version = /^# hard-eng launcher (\S+)$/m.exec(text)?.[1] ?? null;
  const runtime = path.join(home, '.agents', 'runtime', 'he.mjs');
  return {
    status: version === sourceManifest.version && fs.existsSync(runtime) && (stat.mode & 0o111) !== 0 ? 'PASS' : 'FAIL',
    version,
    runtime_present: fs.existsSync(runtime),
    executable: (stat.mode & 0o111) !== 0,
  };
}

export function runSetupDoctor({
  home,
  sourceRoot,
  env = process.env,
  wiringClient = createCodexWiringClient({ env }),
  platform = process.platform,
  cronText = undefined,
}) {
  const environment = inspectSetupEnvironment(home, env, platform);
  const facts = configFacts(home);
  const skills = nativeSkillFacts(sourceRoot);
  const wiring = wiringClient.inspect(home);
  const recovery = inspectSetupRecovery(home);
  const safety = safetyFacts(facts);
  const tools = supportTools(facts, env);
  const launcher = launcherFacts(home, sourceRoot);
  const sourceCheckout = sourceCheckoutFacts(home, env);
  const modelOperations = modelOperationRisk(sourceRoot);
  const legacyControlPlane = inspectLegacyControlPlane(home, { cronText, env });
  const failures = environment.status === 'FAIL'
    || Object.values(tools).some((tool) => tool.status === 'FAIL')
    || ['FAIL', 'CONFLICT'].includes(wiring.status)
    || recovery.status !== 'PASS'
    || sourceCheckout.status === 'FAIL'
    || safety.status === 'FAIL'
    || modelOperations.possible
    || legacyControlPlane.status !== 'PASS'
    || launcher.status === 'FAIL';
  const concerns = launcher.status === 'NOT_INSTALLED'
    || safety.status === 'UNKNOWN_RUNTIME_OVERRIDE'
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
      budget: {
        characters: 8_000,
        basis: 'Codex initial skill list: at most 2% of model context; use the documented 8,000-character fallback when context is unknown.',
      },
      total: skills.total,
      implicit: skills.implicit,
      explicit_only: skills.explicit_only,
      per_skill: skills.per_skill,
      warning: skills.implicit.characters > 8_000,
      digest: skills.digest,
    },
    paid_or_model_operations: modelOperations,
    support_tools: tools,
    codex_mcp: wiring,
    setup_recovery: recovery,
    safety_configuration: safety,
    launcher,
    source_checkout: sourceCheckout,
    legacy_control_plane: legacyControlPlane,
    native_skill_layout: { status: 'PASS', root: '.agents/skills', skills: skills.total.skill_count },
    hook_configuration: {
      status: wiring.status === 'PASS' ? 'MANUAL_TRUST_REVIEW_REQUIRED' : 'WIRING_NOT_READY',
      trust_observable_noninteractively: false,
      manual_action: 'Restart Codex, open `/hooks`, review the exact current hook hash, and trust it before the first Hard Eng task.',
      automatic_approval_scope: 'mcp__hard_eng__state only after explicit user consent',
    },
    codex_wiring_check: 'Official `codex mcp list --json` was used; unrelated MCP entries were preserved.',
  };
}
