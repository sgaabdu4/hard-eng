import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import assert from 'node:assert/strict';
import { sha256 } from '../../plugins/hard-eng/runtime/lib/canonical.mjs';
import { runSetup as baseRunSetup } from '../../scripts/setup.mjs';
import { makePluginClient } from '../fixtures/plugin-client-fixture.mjs';

const sourceRoot = path.resolve('.');
const NOW = Date.parse('2026-07-12T00:00:00.000Z');
const pluginClient = makePluginClient();

function runSetup(argv, options = {}) {
  return baseRunSetup(argv, { cronText: '', ...options, pluginClient });
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
  const codex = `#!/bin/sh
if [ -n "$HARD_ENG_TEST_SECRET" ]; then exit 19; fi
if [ "$1" = "features" ] && [ "$2" = "list" ]; then
  echo "hooks stable true"
  echo "plugin_hooks removed false"
  exit 0
fi
if [ "$1" = "plugin" ] && [ "$2" = "list" ]; then
  printf '{"installed":[{"pluginId":"hard-eng@personal","name":"hard-eng","version":"1.0.0","installed":true,"enabled":true,"source":{"source":"local","path":"%s/.agents/plugins/hard-eng"}}],"available":[' "$HOME"
  first=1
  for name in hard-eng-flutter hard-eng-appwrite hard-eng-web hard-eng-sentry hard-eng-delivery hard-eng-authoring; do
    if [ "$first" = 0 ]; then printf ','; fi
    printf '{"pluginId":"%s@personal","name":"%s","version":"1.0.0","installed":false,"enabled":false,"source":{"source":"local","path":"%s/.agents/plugins/%s"}}' "$name" "$name" "$HOME" "$name"
    first=0
  done
  printf ']}\n'
  exit 0
fi
exit 2
`;
  fs.writeFileSync(path.join(bin, 'codebase-memory-mcp'), cbm, { mode: 0o755 });
  fs.writeFileSync(path.join(bin, 'context-mode'), context, { mode: 0o755 });
  fs.writeFileSync(path.join(bin, 'codex'), codex, { mode: 0o755 });
  return bin;
}

test('doctor is read-only and reports model, context, support tools, launcher, and paid-operation risk', () => {
  const targetHome = fs.mkdtempSync(path.join(os.tmpdir(), 'hard-eng-doctor-'));
  const install = runSetup(['install', '--home', targetHome, '--dry-run'], { sourceRoot, now: NOW });
  runSetup(['install', '--home', targetHome, '--confirm', install.plan_digest], { sourceRoot, now: NOW });
  fs.mkdirSync(path.join(targetHome, '.codex', 'agents'), { recursive: true });
  fs.writeFileSync(path.join(targetHome, '.codex', 'agents', 'custom.toml'), 'model = "fixture"\n');
  fs.writeFileSync(path.join(targetHome, '.codex', 'config.toml'), [
    'model = "gpt-fixture"',
    'model_reasoning_effort = "high"',
    'approval_policy = "on-request"',
    'sandbox_mode = "workspace-write"',
    'hooks = true',
    '[mcp_servers.codebase-memory]',
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
  assert.ok(report.advertised_context.characters <= 2_500);
  assert.equal(report.paid_or_model_operations.possible, false);
  assert.equal(report.support_tools['codebase-memory'].status, 'PASS');
  assert.equal(report.support_tools['codebase-memory'].required_commands_verified, true);
  assert.equal(report.support_tools['context-mode'].status, 'PASS');
  assert.equal(report.support_tools['context-mode'].required_commands_verified, true);
  assert.equal(report.support_tools['context-mode'].hook_routing.status, 'PASS');
  assert.equal(report.support_tools['context-mode'].hard_eng_coexistence.status, 'PASS');
  assert.equal(report.support_tools['context-mode'].hard_eng_coexistence.updated_input_owner, 'hard-eng');
  assert.equal(report.launcher.status, 'PASS');
  assert.deepEqual(snapshot(targetHome), before);
});

test('doctor fails when installed support CLIs lack the required command contract', () => {
  const targetHome = fs.mkdtempSync(path.join(os.tmpdir(), 'hard-eng-doctor-command-contract-'));
  const install = runSetup(['install', '--home', targetHome, '--dry-run'], { sourceRoot, now: NOW });
  runSetup(['install', '--home', targetHome, '--confirm', install.plan_digest], { sourceRoot, now: NOW });
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
  const targetHome = fs.mkdtempSync(path.join(os.tmpdir(), 'hard-eng-doctor-context-cli-'));
  const install = runSetup(['install', '--home', targetHome, '--dry-run'], { sourceRoot, now: NOW });
  runSetup(['install', '--home', targetHome, '--confirm', install.plan_digest], { sourceRoot, now: NOW });
  fs.mkdirSync(path.join(targetHome, '.codex'), { recursive: true });
  fs.writeFileSync(path.join(targetHome, '.codex', 'config.toml'), [
    'hooks = true',
    'approval_policy = "on-request"',
    'sandbox_mode = "workspace-write"',
    '[mcp_servers.codebase-memory]',
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

test('doctor fails an explicitly unsafe static Codex approval or sandbox configuration', () => {
  const targetHome = fs.mkdtempSync(path.join(os.tmpdir(), 'hard-eng-doctor-unsafe-'));
  const install = runSetup(['install', '--home', targetHome, '--dry-run'], { sourceRoot, now: NOW });
  runSetup(['install', '--home', targetHome, '--confirm', install.plan_digest], { sourceRoot, now: NOW });
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

test('doctor reports bounded legacy blockers without reading or changing external tool state', () => {
  const targetHome = fs.mkdtempSync(path.join(os.tmpdir(), 'hard-eng-doctor-legacy-'));
  const install = runSetup(['install', '--home', targetHome, '--dry-run'], { sourceRoot, now: NOW });
  runSetup(['install', '--home', targetHome, '--confirm', install.plan_digest], { sourceRoot, now: NOW });
  fs.mkdirSync(path.join(targetHome, '.local', 'bin'), { recursive: true });
  fs.mkdirSync(path.join(targetHome, '.no-mistakes'), { recursive: true });
  fs.mkdirSync(path.join(targetHome, '.treehouse'), { recursive: true });
  fs.writeFileSync(path.join(targetHome, '.local', 'bin', 'no-mistakes'), 'wrapper\n', { mode: 0o755 });
  fs.writeFileSync(path.join(targetHome, '.local', 'bin', 'treehouse'), 'binary\n', { mode: 0o755 });
  fs.writeFileSync(path.join(targetHome, '.no-mistakes', 'state.sqlite'), 'opaque\n');
  fs.writeFileSync(path.join(targetHome, '.treehouse', 'treehouse-state.json'), '{}\n');
  const bin = fakeTools(targetHome);
  const before = snapshot(targetHome);
  const report = runSetup(['doctor', '--home', targetHome], {
    sourceRoot,
    env: { ...process.env, HOME: targetHome, PATH: `${bin}:${process.env.PATH}` },
  });
  assert.equal(report.status, 'CONCERNS');
  assert.deepEqual(
    report.legacy_surfaces.blockers.map((blocker) => blocker.code).sort(),
    ['NO_MISTAKES_EXTERNAL_DEPENDENCIES', 'TREEHOUSE_RETIREMENT_REQUIRES_SEPARATE_APPROVAL'],
  );
  assert.equal(report.legacy_surfaces.detected, 4);
  assert.match(report.legacy_surfaces.evidence_digest, /^[a-f0-9]{64}$/);
  assert.equal(report.legacy_surfaces.exact_plan_command, 'node scripts/setup.mjs migrate --dry-run');
  assert.deepEqual(snapshot(targetHome), before);
});
