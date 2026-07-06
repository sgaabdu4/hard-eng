#!/usr/bin/env node
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';

const repo = path.resolve(new URL('..', import.meta.url).pathname);
const script = path.join(repo, 'tests/skills/he-plan/evals/run-mini-evals.mjs');
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'he-plan-eval-runner-'));
const fakeCodex = path.join(tmp, 'fake-codex.mjs');

fs.writeFileSync(fakeCodex, `#!/usr/bin/env node
import fs from 'node:fs';
const outputIndex = process.argv.indexOf('-o') + 1;
fs.writeFileSync(process.argv[outputIndex], JSON.stringify({
  eval_id: 1,
  model: 'fake-model',
  used_skill: true,
  visible_response: 'response',
  files_created: [],
  expectations: [],
  overall_pass: true,
  notes: 'model output claims pass'
}));
process.exit(9);
`);
fs.chmodSync(fakeCodex, 0o755);

const result = spawnSync('node', [script, '1'], {
  cwd: repo,
  encoding: 'utf8',
  env: {
    ...process.env,
    HE_PLAN_EVAL_CODEX_BIN: fakeCodex,
    HE_PLAN_EVAL_MODEL: 'fake-model',
    HE_PLAN_EVAL_ROOT: tmp,
    HE_PLAN_EVAL_RUN_ID: 'child-exit-failure',
    HE_PLAN_EVAL_TIMEOUT_MS: '10000',
  },
});

assert.equal(result.status, 2, result.stderr || result.stdout);
assert.match(result.stdout, /DONE eval-1 code=9 pass=false/);
const summary = JSON.parse(fs.readFileSync(path.join(tmp, 'results', 'child-exit-failure', 'summary.json'), 'utf8'));
assert.equal(summary.passed, 0);
assert.equal(summary.failed, 1);
assert.equal(summary.results[0].code, 9);
assert.equal(summary.results[0].overall_pass, false);

console.log('he-plan-eval-runner-test: pass');
