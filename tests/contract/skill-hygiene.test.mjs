import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import assert from 'node:assert/strict';
import { skillInvocationPolicy } from '../../runtime/lib/skill-metadata.mjs';

const root = path.resolve('.');

function nativeSkillFiles() {
  return fs.readdirSync(path.join(root, 'skills'), { withFileTypes: true })
    .filter((entry) => entry.isDirectory() || entry.isSymbolicLink())
    .map((entry) => path.join(root, 'skills', entry.name, 'SKILL.md'))
    .sort();
}

function assertConciseWorkflow(text, label) {
  const sections = [];
  let current = { heading: '', numbered: 0 };
  for (const line of text.split(/\r?\n/)) {
    if (/^##\s+/.test(line)) {
      sections.push(current);
      current = { heading: line, numbered: 0 };
    } else if (/^\s*\d+\.\s+/.test(line)) current.numbered += 1;
  }
  sections.push(current);
  const workflowHeading = /\b(?:workflow|instructions?|steps?|process|procedure|method|flow|setup)\b/i;
  const violation = sections.find((section) => workflowHeading.test(section.heading) && section.numbered >= 3);
  const phaseHeadings = [...text.matchAll(/^#{2,4}\s+(?:Step|Phase)\s+\d+\b/gim)].length;
  assert.equal(violation, undefined, `${label} contains a 3+ step workflow in ${violation?.heading}`);
  assert.ok(phaseHeadings < 3, `${label} contains a 3+ heading workflow`);
}

test('skill workflow hygiene fails on long entrypoint workflows and passes every native front door', () => {
  assert.throws(() => assertConciseWorkflow([
    '# Fixture', '## Workflow', '1. First', '2. Second', '3. Third',
  ].join('\n'), 'fixture'), /3\+ step workflow/i);
  for (const file of nativeSkillFiles()) {
    assertConciseWorkflow(fs.readFileSync(file, 'utf8'), path.relative(root, file));
  }
});

test('every native skill reference and local resource path is reachable', () => {
  for (const file of nativeSkillFiles()) {
    const text = fs.readFileSync(file, 'utf8');
    const resources = new Set();
    for (const match of text.matchAll(/\[[^\]]*\]\(([^)]+)\)/g)) {
      const value = match[1].split('#')[0];
      if (value && !/^[a-z]+:/i.test(value) && !value.startsWith('#')) resources.add(value);
    }
    for (const match of text.matchAll(/`((?:references|scripts|assets)\/[^`\s]+)`/g)) {
      resources.add(match[1].replace(/[.,;:]$/, '').split('#')[0]);
    }
    for (const relative of resources) {
      if (/[\*?<>]/.test(relative)) continue;
      assert.equal(
        fs.existsSync(path.resolve(path.dirname(file), relative)),
        true,
        `${path.relative(root, file)} references missing ${relative}`,
      );
    }
  }
});

test('Codex skill metadata is tab-free and every declared invocation policy is boolean', () => {
  for (const file of nativeSkillFiles()) {
    const metadata = path.join(path.dirname(file), 'agents', 'openai.yaml');
    if (!fs.existsSync(metadata)) continue;
    const text = fs.readFileSync(metadata, 'utf8');
    assert.doesNotMatch(text, /\t/, `${path.relative(root, metadata)} contains a tab`);
    const policy = skillInvocationPolicy(text);
    assert.equal(typeof policy.allow_implicit_invocation, 'boolean');
    assert.ok(['declared', 'codex-default'].includes(policy.source));
  }
});
