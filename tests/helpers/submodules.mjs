import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';

export function isUninitializedSubmodule(repo, relativePath) {
  const result = spawnSync('git', ['submodule', 'status', '--', relativePath], {
    cwd: repo,
    encoding: 'utf8',
  });
  assert.equal(result.status, 0, `could not inspect submodule ${relativePath}: ${result.stderr.trim()}`);
  return result.stdout.trimStart().startsWith('-');
}

export function assertVendoredSkillCheckout(repo, relativePath, message) {
  const absolutePath = path.join(repo, relativePath);
  if (fs.existsSync(absolutePath)) return true;
  const submodulePath = relativePath.split(path.sep).slice(0, 3).join(path.sep);
  assert.ok(
    isUninitializedSubmodule(repo, submodulePath),
    `${message}; ${submodulePath} is neither initialized nor exposing ${relativePath}`,
  );
  return false;
}
