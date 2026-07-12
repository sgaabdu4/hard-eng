import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import test from 'node:test';
import assert from 'node:assert/strict';
import { sha256 } from '../../runtime/lib/canonical.mjs';
import { runSetup as baseRunSetup } from '../../scripts/setup.mjs';
import { makeWiringClient } from '../fixtures/wiring-client-fixture.mjs';

const sourceRoot = path.resolve('.');
const wiringClient = makeWiringClient();

function runSetup(argv, options = {}) {
  return baseRunSetup(argv, { cronText: '', ...options, wiringClient });
}

function snapshot(root) {
  const values = [];
  function walk(directory, prefix = '') {
    if (!fs.existsSync(directory)) return;
    for (const entry of fs.readdirSync(directory, { withFileTypes: true }).sort((a, b) => a.name.localeCompare(b.name))) {
      const relative = path.join(prefix, entry.name);
      const target = path.join(directory, entry.name);
      if (entry.isDirectory()) walk(target, relative);
      else values.push([relative, entry.isSymbolicLink() ? `link:${fs.readlinkSync(target)}` : sha256(fs.readFileSync(target))]);
    }
  }
  walk(root);
  return values;
}

function fakeTools(root, { contextHooks = true, cbmCommands = true, contextCommands = true } = {}) {
  const bin = path.join(root, 'bin');
  fs.mkdirSync(bin, { recursive: true });
  const cbm = `#!/bin/sh
if [ -n "$HARD_ENG_TEST_SECRET" ]; then exit 19; fi
if [ "$1" = "--version" ]; then echo "codebase-memory-mcp 0.9.0"; exit 0; fi
if [ "$1" = "--help" ]; then echo "Tools: index_repository search_graph get_architecture ${cbmCommands ? 'trace_path detect_changes' : 'detect_changes'} list_projects"; exit 0; fi
if [ "$1" = "cli" ] && [ "$2" = "list_projects" ]; then echo '{"projects":[]}'; exit 0; fi
exit 2
`;
  const hookOutput = contextHooks ? `
  echo "PreToolUse hook: PASS"
  echo "PostToolUse hook: PASS"
  echo "SessionStart hook: PASS"
  echo "PreCompact hook: PASS"
  echo "UserPromptSubmit hook: PASS"
  echo "Stop hook: PASS"` : '';
  const context = `#!/bin/sh
if [ -n "$HARD_ENG_TEST_SECRET" ]; then exit 19; fi
if [ "$1" = "doctor" ]; then
  echo "Storage session: PASS"
  echo "Storage content: PASS"
  echo "Storage stats: PASS"
  echo "Server test: PASS"
  echo "npm (MCP): PASS - local v1.0.168"
${hookOutput}
  exit 0
fi
if [ "$1" = "--help" ]; then printf "context-mode doctor\\n${contextCommands ? 'context-mode index\ncontext-mode search\n' : ''}"; exit 0; fi
exit 2
`;
  fs.writeFileSync(path.join(bin, 'codebase-memory-mcp'), cbm, { mode: 0o755 });
  fs.writeFileSync(path.join(bin, 'context-mode'), context, { mode: 0o755 });
  return bin;
}

function readyHome(prefix) {
  const targetHome = fs.mkdtempSync(path.join(os.tmpdir(), prefix));
  fs.mkdirSync(path.join(targetHome, '.agents', 'runtime'), { recursive: true });
  fs.mkdirSync(path.join(targetHome, '.local', 'bin'), { recursive: true });
  fs.writeFileSync(path.join(targetHome, '.agents', 'runtime', 'he.mjs'), 'export {};\n');
  fs.writeFileSync(path.join(targetHome, '.local', 'bin', 'he'), [
    '#!/bin/sh', '# hard-eng launcher 1.0.0', 'exit 0', '',
  ].join('\n'), { mode: 0o755 });
  return targetHome;
}

test('doctor is read-only and reports model, context, support tools, launcher, and paid-operation risk', () => {
  const targetHome = readyHome('hard-eng-doctor-');
  fs.mkdirSync(path.join(targetHome, '.codex', 'agents'), { recursive: true });
  fs.writeFileSync(path.join(targetHome, '.codex', 'agents', 'custom.toml'), 'model = "fixture"\n');
  fs.writeFileSync(path.join(targetHome, '.codex', 'config.toml'), [
    'model = "gpt-fixture"',
    'model_reasoning_effort = "high"',
    'approval_policy = "on-request"',
    'sandbox_mode = "workspace-write"',
    'hooks = true',
    '[mcp_servers.context-mode]',
  ].join('\n'));
  const bin = fakeTools(targetHome);
  const before = snapshot(targetHome);
  const report = runSetup(['doctor', '--home', targetHome], {
    sourceRoot,
    env: {
      ...process.env, HOME: targetHome, PATH: `${bin}:${process.env.PATH}`,
      HARD_ENG_TEST_SECRET: 'must-not-reach-support-tool',
    },
  });
  assert.equal(report.status, 'PASS');
  assert.deepEqual(report.model, { name: 'gpt-fixture', reasoning_effort: 'high' });
  assert.equal(report.custom_agent_profiles, 1);
  assert.equal(report.advertised_context.total.skill_count, 35);
  assert.equal(report.advertised_context.implicit.skill_count, 35);
  assert.equal(report.advertised_context.explicit_only.skill_count, 0);
  assert.equal(report.advertised_context.implicit.descriptions_over_320, 2);
  assert.equal(
    report.advertised_context.implicit.estimated_tokens,
    Math.ceil(report.advertised_context.implicit.characters / 4),
  );
  assert.equal(report.advertised_context.budget.characters, 8_000);
  assert.match(report.advertised_context.budget.basis, /Codex.*2%.*8,000/i);
  assert.equal(
    report.advertised_context.warning,
    report.advertised_context.implicit.characters > report.advertised_context.budget.characters,
  );
  assert.equal(report.advertised_context.per_skill.length, 35);
  assert.equal(report.advertised_context.per_skill.every((skill) => skill.invocation === 'implicit'), true);
  assert.equal(report.paid_or_model_operations.possible, false);
  assert.equal(report.support_tools['codebase-memory'].status, 'PASS');
  assert.equal(report.support_tools['codebase-memory'].manual_action, null);
  assert.equal(report.support_tools['codebase-memory'].required_commands_verified, true);
  assert.equal(report.support_tools['context-mode'].status, 'PASS');
  assert.equal(report.support_tools['context-mode'].manual_action, null);
  assert.equal(report.support_tools['context-mode'].required_commands_verified, true);
  assert.equal(report.support_tools['context-mode'].hook_routing.status, 'PASS');
  assert.equal(report.support_tools['context-mode'].hard_eng_coexistence.status, 'PASS');
  assert.equal(report.support_tools['context-mode'].hard_eng_coexistence.updated_input_owner, 'hard-eng');
  assert.equal(report.launcher.status, 'PASS');
  assert.equal(report.legacy_control_plane.status, 'PASS');
  assert.equal(report.legacy_control_plane.external_no_mistakes.preserved, true);
  assert.deepEqual(report.source_checkout, {
    status: 'NOT_APPLICABLE', remote_count: 0,
    evidence_digest: sha256('not-a-git-checkout'), manual_action: null,
  });
  assert.deepEqual(snapshot(targetHome), before);
});

test('doctor fails when installed support CLIs lack the required command contract', () => {
  const targetHome = readyHome('hard-eng-doctor-command-contract-');
  fs.mkdirSync(path.join(targetHome, '.codex'), { recursive: true });
  fs.writeFileSync(path.join(targetHome, '.codex', 'config.toml'), [
    'approval_policy = "on-request"',
    'sandbox_mode = "workspace-write"',
  ].join('\n'));
  const bin = fakeTools(targetHome, { contextHooks: false, cbmCommands: false });
  const report = runSetup(['doctor', '--home', targetHome], {
    sourceRoot,
    env: { ...process.env, HOME: targetHome, PATH: `${bin}:${process.env.PATH}` },
  });
  assert.equal(report.status, 'FAIL');
  assert.equal(report.support_tools['codebase-memory'].required_commands_verified, false);
  assert.equal(report.support_tools['context-mode'].required_commands_verified, true);
});

test('Context Mode remains required while its global plugin hooks stay optional', () => {
  const targetHome = readyHome('hard-eng-doctor-context-cli-');
  fs.mkdirSync(path.join(targetHome, '.codex'), { recursive: true });
  fs.writeFileSync(path.join(targetHome, '.codex', 'config.toml'), [
    'hooks = true',
    'approval_policy = "on-request"',
    'sandbox_mode = "workspace-write"',
    '[mcp_servers.context-mode]',
  ].join('\n'));
  const bin = fakeTools(targetHome, { contextHooks: false });
  const report = runSetup(['doctor', '--home', targetHome], {
    sourceRoot,
    env: { ...process.env, HOME: targetHome, PATH: `${bin}:${process.env.PATH}` },
  });

  assert.equal(report.status, 'PASS');
  assert.equal(report.support_tools['context-mode'].status, 'PASS');
  assert.equal(report.support_tools['context-mode'].hook_routing.status, 'NOT_ENABLED');
  assert.equal(report.support_tools['context-mode'].hook_routing.required_for_hard_eng, false);
  assert.equal(report.support_tools['context-mode'].hard_eng_coexistence.status, 'NOT_APPLICABLE');
});

test('missing support tools fail readiness and return official manual actions without installing', () => {
  const targetHome = fs.mkdtempSync(path.join(os.tmpdir(), 'hard-eng-doctor-missing-'));
  const before = snapshot(targetHome);
  const report = runSetup(['doctor', '--home', targetHome], {
    sourceRoot,
    env: { HOME: targetHome, PATH: '/nonexistent' },
  });
  assert.equal(report.status, 'FAIL');
  assert.match(report.support_tools['codebase-memory'].manual_action, /codebase-memory-mcp/i);
  assert.match(report.support_tools['context-mode'].manual_action, /context-mode/i);
  assert.deepEqual(snapshot(targetHome), before);
});

test('doctor rejects a Codebase Memory MCP registration while preserving CLI-only support', () => {
  const targetHome = readyHome('hard-eng-doctor-codebase-memory-mcp-');
  fs.mkdirSync(path.join(targetHome, '.codex'), { recursive: true });
  fs.writeFileSync(path.join(targetHome, '.codex', 'config.toml'), [
    'approval_policy = "on-request"',
    'sandbox_mode = "workspace-write"',
  ].join('\n'));
  const bin = fakeTools(targetHome, { contextHooks: false });
  const base = makeWiringClient();
  const mcpRegistered = {
    ...base,
    inspect(home) {
      return {
        ...base.inspect(home),
        codebase_memory_mcp_entries: 1,
        codebase_memory_mcp_evidence_digest: 'a'.repeat(64),
      };
    },
  };
  const report = baseRunSetup(['doctor', '--home', targetHome], {
    sourceRoot, cronText: '', wiringClient: mcpRegistered,
    env: { ...process.env, HOME: targetHome, PATH: `${bin}:${process.env.PATH}` },
  });
  assert.equal(report.status, 'FAIL');
  assert.equal(report.support_tools['codebase-memory'].cli_ready, true);
  assert.equal(report.support_tools['codebase-memory'].mcp_entry_count, 1);
  assert.equal(report.support_tools['codebase-memory'].mcp_transport_absent, false);
  assert.match(report.support_tools['codebase-memory'].manual_action, /codex mcp remove/i);
});

test('doctor fails an explicitly unsafe static Codex approval or sandbox configuration', () => {
  const targetHome = readyHome('hard-eng-doctor-unsafe-');
  fs.mkdirSync(path.join(targetHome, '.codex'), { recursive: true });
  fs.writeFileSync(path.join(targetHome, '.codex', 'config.toml'), [
    'approval_policy = "never"',
    'sandbox_mode = "danger-full-access"',
  ].join('\n'));
  const bin = fakeTools(targetHome, { contextHooks: false });
  const report = runSetup(['doctor', '--home', targetHome], {
    sourceRoot,
    env: { ...process.env, HOME: targetHome, PATH: `${bin}:${process.env.PATH}` },
  });
  assert.equal(report.status, 'FAIL');
  assert.equal(report.safety_configuration.status, 'FAIL');
  assert.match(report.safety_configuration.enforcement_boundary, /native approvals and sandbox/i);
});

test('doctor reports only bounded current checkout facts without exposing remote URLs', () => {
  const targetHome = readyHome('hard-eng-doctor-source-checkout-');
  fs.mkdirSync(path.join(targetHome, '.codex'), { recursive: true });
  fs.writeFileSync(path.join(targetHome, '.codex', 'config.toml'), [
    'approval_policy = "on-request"',
    'sandbox_mode = "workspace-write"',
    '[mcp_servers.context-mode]',
  ].join('\n'));
  const checkout = path.join(targetHome, '.agents');
  execFileSync('git', ['-C', checkout, 'init', '-q']);
  execFileSync('git', ['-C', checkout, 'remote', 'add', 'origin', 'https://example.invalid/private.git']);
  const bin = fakeTools(targetHome, { contextHooks: false });
  const env = { ...process.env, HOME: targetHome, PATH: `${bin}:${process.env.PATH}` };
  const before = snapshot(targetHome);
  const report = runSetup(['doctor', '--home', targetHome], { sourceRoot, env });
  assert.equal(report.status, 'PASS');
  assert.equal(report.source_checkout.status, 'PASS');
  assert.equal(report.source_checkout.remote_count, 1);
  assert.match(report.source_checkout.evidence_digest, /^[a-f0-9]{64}$/);
  assert.equal(JSON.stringify(report).includes('example.invalid'), false);
  assert.deepEqual(snapshot(targetHome), before);
});

test('doctor never follows a symlinked Codex config into unrelated data', () => {
  const targetHome = readyHome('hard-eng-doctor-symlink-config-');
  fs.mkdirSync(path.join(targetHome, '.codex'), { recursive: true });
  const outside = path.join(targetHome, 'unrelated-private-config');
  fs.writeFileSync(outside, [
    'model = "PRIVATE_MODEL_VALUE"',
    'approval_policy = "on-request"',
    'sandbox_mode = "workspace-write"',
  ].join('\n'));
  fs.symlinkSync(outside, path.join(targetHome, '.codex', 'config.toml'));
  const bin = fakeTools(targetHome, { contextHooks: false });
  const report = runSetup(['doctor', '--home', targetHome], {
    sourceRoot,
    env: { ...process.env, HOME: targetHome, PATH: `${bin}:${process.env.PATH}` },
  });

  assert.equal(report.status, 'CONCERNS');
  assert.deepEqual(report.model, { name: null, reasoning_effort: null });
  assert.equal(JSON.stringify(report).includes('PRIVATE_MODEL_VALUE'), false);
});
