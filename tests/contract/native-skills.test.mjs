import fs from 'node:fs';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import test from 'node:test';
import assert from 'node:assert/strict';
import {
  skillDescription,
  skillInvocationPolicy,
} from '../../runtime/lib/skill-metadata.mjs';

const root = path.resolve('.');

test('the canonical native skill root is complete and plugin-free', () => {
  assert.equal(fs.existsSync(path.join(root, 'plugins')), false);
  const skillsRoot = path.join(root, 'skills');
  const entries = fs.readdirSync(skillsRoot, { withFileTypes: true })
    .filter((entry) => entry.isDirectory() || entry.isSymbolicLink())
    .sort((left, right) => left.name.localeCompare(right.name));
  assert.deepEqual(entries.map((entry) => entry.name), [
    'appwrite-backend',
    'atomic-ui',
    'building-flutter-apps',
    'code-review',
    'codebase-design',
    'codebase-memory',
    'create-pdf',
    'diagnosing-bugs',
    'domain-modeling',
    'e2e',
    'fallow',
    'find-skills',
    'handoff',
    'hard-eng',
    'improve-codebase-architecture',
    'performance-rescue',
    'product-demo-video',
    'prototype',
    'react-doctor',
    'repeated-failure-learning',
    'research',
    'resolving-merge-conflicts',
    'security-review',
    'sentry-workflow',
    'setup-engineering-skills',
    'setup-pre-commit',
    'tdd',
    'teach',
    'terse',
    'test-quality',
    'thermo-nuclear-code-quality-review',
    'triage',
    'vercel-react-best-practices',
    'website-launch-readiness',
    'writing-great-skills',
  ]);

  let characters = 0;
  for (const entry of entries) {
    const file = path.join(skillsRoot, entry.name, 'SKILL.md');
    assert.equal(fs.existsSync(file), true, `missing SKILL.md: ${entry.name}`);
    const value = skillDescription(fs.readFileSync(file, 'utf8'));
    assert.ok(value.length > 0, `missing description: ${entry.name}`);
    characters += value.length;
  }
  assert.ok(characters > 0);
});

test('the seven upstream owners remain exact pinned gitlinks with notices', () => {
  const expected = new Map([
    ['vendor/skill-upstreams/building-flutter-apps', '6e79dd24d03d586861678a697b04cf0fb74aa30e'],
    ['vendor/skill-upstreams/appwrite-backend', 'bab31570b067f9c5454799fd9f2c1b5e4fcba279'],
    ['vendor/skill-upstreams/fallow-skills', 'b3fb694566f0d9a570b9efa6c5138dbc1b75c847'],
    ['vendor/skill-upstreams/react-doctor', 'dfccac44e4468dd971e2a4fe8e44a49ba91f498a'],
    ['vendor/skill-upstreams/vercel-agent-skills', 'f8a72b9603728bb92a217a879b7e62e43ad76c81'],
    ['vendor/skill-upstreams/sentry-for-ai', 'a9562ccfefbaa09ab5800740efbd6959b764863d'],
    ['vendor/skill-upstreams/sentry-cli', '3c7d0851cc71cf25503b6300329ae40ede75e20e'],
  ]);
  const stage = execFileSync('git', ['-C', root, 'ls-files', '--stage'], { encoding: 'utf8' });
  const notices = fs.readFileSync(path.join(root, 'THIRD_PARTY_NOTICES.md'), 'utf8');
  for (const [relative, commit] of expected) {
    assert.match(stage, new RegExp(`^160000 ${commit} 0\\t${relative}$`, 'm'));
    assert.match(notices, new RegExp(commit));
  }
});

test('Hard Eng has one concise native front door and CLI-only Codebase Memory guidance', () => {
  const skillRoot = path.join(root, 'skills', 'hard-eng');
  const skill = fs.readFileSync(path.join(skillRoot, 'SKILL.md'), 'utf8');
  assert.ok(skill.split(/\r?\n/).length <= 80);
  assert.match(skill, /one local state tool/i);
  assert.doesNotMatch(skill, /^\s*3\.\s/m);
  assert.match(fs.readFileSync(path.join(skillRoot, 'agents', 'openai.yaml'), 'utf8'), /display_name: "Hard Eng"/);

  const codebaseMemory = fs.readFileSync(path.join(root, 'skills', 'codebase-memory', 'SKILL.md'), 'utf8');
  assert.match(codebaseMemory, /codebase-memory-mcp cli <tool>/);
  assert.match(codebaseMemory, /Never use its MCP transport/);
  assert.doesNotMatch(codebaseMemory, /mcp__codebase_memory/);
});

test('approved natural-language skills declare implicit invocation without broadening adjacent triggers', () => {
  const implicitSkills = [
    'handoff',
    'improve-codebase-architecture',
    'product-demo-video',
    'setup-engineering-skills',
    'setup-pre-commit',
    'teach',
    'triage',
    'website-launch-readiness',
  ];
  for (const name of implicitSkills) {
    const metadata = fs.readFileSync(path.join(root, 'skills', name, 'agents', 'openai.yaml'), 'utf8');
    assert.deepEqual(skillInvocationPolicy(metadata), {
      allow_implicit_invocation: true,
      source: 'declared',
    }, `${name} must bind the approved invocation policy`);
  }

  const demo = fs.readFileSync(path.join(root, 'skills', 'product-demo-video', 'SKILL.md'), 'utf8');
  assert.match(skillDescription(demo), /user explicitly requests a product demo video/i);
  assert.match(skillDescription(demo), /ordinary E2E screenshots and verification recordings do not trigger it/i);
  const launch = fs.readFileSync(path.join(root, 'skills', 'website-launch-readiness', 'SKILL.md'), 'utf8');
  assert.match(skillDescription(launch), /user explicitly asks for website launch readiness/i);
});

test('Codex invocation metadata defaults to implicit and rejects malformed policy values', () => {
  assert.deepEqual(skillInvocationPolicy('interface:\n  display_name: "Fixture"\n'), {
    allow_implicit_invocation: true,
    source: 'codex-default',
  });
  assert.deepEqual(skillInvocationPolicy('policy:\n  allow_implicit_invocation: false\n'), {
    allow_implicit_invocation: false,
    source: 'declared',
  });
  assert.throws(
    () => skillInvocationPolicy('policy:\n  allow_implicit_invocation: sometimes\n'),
    /boolean/i,
  );
});

test('native skills never launch subagents without explicit user delegation', () => {
  const forbidden = [
    /when subagents are available/i,
    /when a subagent tool exists/i,
    /spawn \d+\+ sub-agents/i,
    /use subagents through the available multi-agent tool when/i,
    /with parallel subagents/i,
  ];
  const visit = (directory) => {
    for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
      const target = path.join(directory, entry.name);
      if (entry.isSymbolicLink()) continue;
      if (entry.isDirectory()) visit(target);
      else if (entry.isFile() && entry.name.endsWith('.md')) {
        const text = fs.readFileSync(target, 'utf8');
        for (const pattern of forbidden) {
          assert.doesNotMatch(text, pattern, `${path.relative(root, target)} enables automatic subagents`);
        }
      }
    }
  };
  visit(path.join(root, 'skills'));
});
