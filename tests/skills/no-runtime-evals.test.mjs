import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';

const repoRoot = path.resolve(new URL('../..', import.meta.url).pathname);
const skillsRoot = path.join(repoRoot, 'skills');
const forbiddenMarkdown = /Skill Eval|gpt-5\.4-mini|run-mini|run-trigger|trigger-eval|verification\/eval|vertical slices\/evals|\bevals\b/i;
const allowedModelPolicyLines = new Set([
  'skills/workflow-help/references/route-map.md:8',
  'skills/workflow-help/references/route-map.md:59',
]);

function isAllowedRuntimePolicy(rel, lineNumber, line) {
  if (!allowedModelPolicyLines.has(`${rel}:${lineNumber}`)) return false;
  return /subagents?.*gpt-5\.5/i.test(line) && /evals?.*gpt-5\.4-mini/i.test(line);
}

function walk(dir, visitor) {
  for (const name of fs.readdirSync(dir)) {
    const fullPath = path.join(dir, name);
    const stat = fs.lstatSync(fullPath);
    if (stat.isDirectory()) {
      visitor(fullPath, stat);
      walk(fullPath, visitor);
    } else {
      visitor(fullPath, stat);
    }
  }
}

test('runtime skills do not contain eval harness directories', () => {
  const evalDirs = [];
  walk(skillsRoot, (fullPath, stat) => {
    if (stat.isDirectory() && path.basename(fullPath) === 'evals') {
      evalDirs.push(path.relative(repoRoot, fullPath));
    }
  });
  assert.deepEqual(evalDirs, []);
});

test('runtime skill markdown does not contain skill-eval harness guidance', () => {
  const hits = [];
  walk(skillsRoot, (fullPath, stat) => {
    if (!stat.isFile() || !fullPath.endsWith('.md')) return;
    const rel = path.relative(repoRoot, fullPath);
    const lines = fs.readFileSync(fullPath, 'utf8').split('\n');
    lines.forEach((line, index) => {
      const lineNumber = index + 1;
      if (forbiddenMarkdown.test(line) && !isAllowedRuntimePolicy(rel, lineNumber, line)) {
        hits.push(`${rel}:${lineNumber}: ${line}`);
      }
    });
  });
  assert.deepEqual(hits, []);
});
