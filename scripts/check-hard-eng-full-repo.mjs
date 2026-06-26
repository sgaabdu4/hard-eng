#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';

const args = process.argv.slice(2);
let root = process.cwd();
let json = false;
let listOnly = false;
let includeE2e = false;
let includeEvals = false;
let includeSessionEvals = false;

for (let index = 0; index < args.length; index += 1) {
  const arg = args[index];
  if (arg === '--json') json = true;
  else if (arg === '--list') listOnly = true;
  else if (arg === '--include-e2e') includeE2e = true;
  else if (arg === '--include-evals') includeEvals = true;
  else if (arg === '--include-session-evals') includeSessionEvals = true;
  else if (arg === '--help' || arg === '-h') {
    console.log(`Usage: check-hard-eng-full-repo.mjs [--list] [--json] [--include-e2e] [--include-evals] [--include-session-evals] [repo]

Runs the deterministic Hard Eng repository gate.
Default scope excludes real E2E dogfood, model evals, and long session evals.
Use --include-evals for skill or routing contract changes, release readiness, or a regression; do not run model evals after every session.`);
    process.exit(0);
  } else {
    root = path.resolve(arg);
  }
}

root = path.resolve(root);

function cmd(id, command, argsList = [], options = {}) {
  return {
    id,
    command,
    args: argsList,
    cwd: root,
    timeoutMs: options.timeoutMs ?? 120000,
    optional: options.optional ?? false,
    category: options.category ?? 'local',
    env: options.env ?? {},
  };
}

function nodeFile(file, options = {}) {
  const extraArgs = options.args ?? [];
  const cleanOptions = { ...options };
  delete cleanOptions.args;
  return cmd(file, process.execPath, [file, ...extraArgs], cleanOptions);
}

const commands = [
  cmd('git-diff-check', 'git', ['diff', '--check']),
  nodeFile('tests/agents-md-contract.test.mjs'),
  nodeFile('tests/codebase-memory-mcp-probe.test.mjs', { category: 'runtime', timeoutMs: 45000 }),
  nodeFile('tests/codex-config-sync.test.mjs'),
  nodeFile('tests/codex-hooks-contract.test.mjs'),
  nodeFile('tests/context-mode-health.test.mjs', { category: 'runtime', timeoutMs: 45000 }),
  nodeFile('tests/deterministic-owner.test.mjs'),
  nodeFile('tests/eval-model-defaults.test.mjs'),
  nodeFile('tests/generated-assets.test.mjs'),
  nodeFile('tests/git-hooks-contract.test.mjs'),
  nodeFile('tests/hard-eng-full-repo-gate.test.mjs'),
  nodeFile('tests/he-state.test.mjs'),
  nodeFile('tests/he-state-ship-proof.test.mjs'),
  nodeFile('tests/he-state-stage-contract.test.mjs'),
  nodeFile('tests/he-state-ui-decision.test.mjs'),
  nodeFile('tests/manage-skills.test.mjs'),
  nodeFile('tests/markdown-hygiene.test.mjs'),
  nodeFile('tests/pre-commit-hygiene-behavior.test.mjs'),
  nodeFile('tests/project-context-gates.test.mjs'),
  nodeFile('tests/project-naming.test.mjs'),
  nodeFile('tests/project-quality-gates.test.mjs'),
  nodeFile('tests/protect-secrets-env.test.mjs'),
  nodeFile('tests/security-pretooluse-env.test.mjs'),
  nodeFile('tests/setup-isolated-install.test.mjs'),
  nodeFile('tests/setup-uninstall-contract.test.mjs'),
  nodeFile('tests/ssot-guardrails.test.mjs'),
  nodeFile('tests/uninstall-config-cleanup.test.mjs'),
  nodeFile('tests/vendor-skill-integrity.test.mjs'),
  nodeFile('tests/versioning-contract.test.mjs'),
  nodeFile('tests/worktree-ready.test.mjs'),
  nodeFile('tests/skills/e2e/artifact-checker.test.mjs'),
  nodeFile('tests/skills/e2e/playwright-tooling.test.mjs'),
  nodeFile('tests/skills/e2e/project-pack.test.mjs'),
  nodeFile('tests/skills/e2e/recap.test.mjs'),
  nodeFile('tests/skills/grill-me/evals/validate-evals.mjs'),
  nodeFile('tests/integrations/no-mistakes/gate-hook.test.mjs'),
  nodeFile('tests/integrations/no-mistakes/migration-coverage.test.mjs'),
  nodeFile('tests/integrations/no-mistakes/pr-evidence.test.mjs'),
  nodeFile('tests/skills/no-runtime-evals.test.mjs'),
  nodeFile('tests/skills/treehouse/validate-skill.mjs'),
  nodeFile('scripts/check-generated-assets.mjs', { args: ['.'] }),
  nodeFile('scripts/check-project-context-gates.mjs', { args: ['--require-all', '.'] }),
  nodeFile('scripts/check-project-naming.mjs', { args: ['.'] }),
  nodeFile('scripts/check-project-quality-gates.mjs', { args: ['--require-push-gate', '.'] }),
  nodeFile('scripts/check-ssot-guardrails.mjs', { args: ['.'] }),
  nodeFile('scripts/check-vendor-skill-integrity.mjs', { args: ['.'] }),
].map((item) => item.args ? cmd(item.id, item.command, item.args, item) : item);

const evalCommands = [
  nodeFile('tests/agents-md-routing/evals/run-evals.mjs', {
    category: 'eval',
    timeoutMs: 3600000,
    env: { AGENTS_ROUTING_EVAL_TIMEOUT_MS: '240000', AGENTS_ROUTING_EVAL_CONCURRENCY: '2' },
  }),
  nodeFile('tests/skills/description-routing/evals/run-evals.mjs', { category: 'eval', timeoutMs: 600000 }),
  nodeFile('tests/skills/e2e/evals/run-evals.mjs', {
    category: 'eval',
    timeoutMs: 3600000,
    env: { E2E_EVAL_TIMEOUT_MS: '180000' },
  }),
  nodeFile('tests/skills/grill-me/evals/run-stage-routing-evals.mjs', { category: 'eval', timeoutMs: 600000 }),
  nodeFile('tests/skills/grill-me/evals/run-trigger-evals.mjs', { category: 'eval', timeoutMs: 600000 }),
  cmd('tests/skills/terse/evals/run-mini-evals.py', 'python3', ['tests/skills/terse/evals/run-mini-evals.py'], {
    category: 'eval',
    timeoutMs: 600000,
  }),
  nodeFile('tests/skills/treehouse/evals/run-trigger-evals.mjs', { category: 'eval', timeoutMs: 600000 }),
];

const sessionEvalCommands = [
  nodeFile('tests/skills/grill-me/evals/run-mini-evals.mjs', {
    category: 'session-eval',
    timeoutMs: 28800000,
    env: { GRILL_ME_EVAL_TIMEOUT_MS: '3600000' },
  }),
];

if (includeE2e) {
  commands.push(nodeFile('tests/skills/e2e/dogfood-playwright-smoke.test.mjs', {
    category: 'e2e',
    timeoutMs: 180000,
  }));
}

if (includeEvals) commands.push(...evalCommands);
if (includeSessionEvals) commands.push(...sessionEvalCommands);

const skipped = [
  !includeE2e && 'tests/skills/e2e/dogfood-playwright-smoke.test.mjs',
  ...(!includeEvals ? evalCommands.map((entry) => entry.id) : []),
  ...(!includeSessionEvals ? sessionEvalCommands.map((entry) => entry.id) : []),
].filter(Boolean);

function display(entry) {
  return [entry.command, ...entry.args].join(' ');
}

function listPayload() {
  return {
    root,
    commands: commands.map((entry) => ({
      id: entry.id,
      command: display(entry),
      category: entry.category,
      timeoutMs: entry.timeoutMs,
    })),
    skipped,
  };
}

if (listOnly) {
  const payload = listPayload();
  if (json) console.log(`${JSON.stringify(payload, null, 2)}\n`);
  else {
    for (const entry of payload.commands) console.log(`${entry.id}: ${entry.command}`);
    for (const entry of payload.skipped) console.log(`skipped: ${entry}`);
  }
  process.exit(0);
}

const logDir = path.join(root, '.codebase', 'hard-eng-full-repo');
fs.mkdirSync(logDir, { recursive: true });
const logPath = path.join(logDir, `${new Date().toISOString().replace(/[:.]/g, '-')}.log`);
const failures = [];
const results = [];

for (const entry of commands) {
  const started = Date.now();
  const result = spawnSync(entry.command, entry.args, {
    cwd: entry.cwd,
    env: { ...process.env, ...entry.env },
    encoding: 'utf8',
    timeout: entry.timeoutMs,
    maxBuffer: 1024 * 1024 * 64,
  });
  const durationMs = Date.now() - started;
  const passed = result.status === 0 && !result.error;
  const output = `${result.stdout || ''}${result.stderr || ''}`;
  fs.appendFileSync(logPath, [
    `\n## ${entry.id}`,
    `$ ${display(entry)}`,
    `status: ${result.status ?? 'error'} durationMs: ${durationMs}`,
    result.signal ? `signal: ${result.signal}` : '',
    result.error ? `error: ${result.error.message}` : '',
    output,
  ].filter(Boolean).join('\n'));
  results.push({ id: entry.id, command: display(entry), passed, durationMs });
  if (!passed) failures.push({ ...results.at(-1), logPath });
  console.log(`${passed ? 'pass' : 'fail'} ${entry.id} (${Math.round(durationMs / 1000)}s)`);
}

const payload = {
  status: failures.length ? 'fail' : 'pass',
  root,
  logPath,
  skipped,
  results,
  failures,
};

if (json) console.log(`${JSON.stringify(payload, null, 2)}\n`);
else {
  for (const entry of skipped) console.log(`skipped: ${entry}`);
  console.log(`hard-eng-full-repo: ${payload.status}`);
  console.log(`log: ${logPath}`);
}

process.exit(failures.length ? 1 : 0);
