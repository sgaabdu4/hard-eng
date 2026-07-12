import test from 'node:test';
import assert from 'node:assert/strict';
import {
  parseReleaseEvalArgs,
  runReleaseEval,
} from '../../runtime/lib/release-eval.mjs';

const options = {
  repo: '/fixture',
  lowModel: 'low-fixture',
  strongModel: 'strong-fixture',
  cases: ['route', 'state-capsule'],
  maxCalls: 4,
};

test('release eval previews exact models, purpose, cases, call count, and cap without a model call', () => {
  let calls = 0;
  const report = runReleaseEval({ ...options, confirmed: false }, {
    runner() {
      calls += 1;
      throw new Error('preview must not call a model');
    },
  });
  assert.equal(report.status, 'APPROVAL_REQUIRED');
  assert.equal(report.purpose, 'release-only route, state-tool, and capsule compatibility');
  assert.deepEqual(report.models, [
    { role: 'low', model: 'low-fixture' },
    { role: 'strong', model: 'strong-fixture' },
  ]);
  assert.deepEqual(report.cases, ['route', 'state-capsule']);
  assert.equal(report.predicted_calls, 4);
  assert.equal(report.max_calls, 4);
  assert.equal(report.confirmation_flag, '--confirm-model-evals');
  assert.equal(calls, 0);
});

test('confirmed release eval runs sequentially once per model/case with no retry', () => {
  const calls = [];
  const report = runReleaseEval({ ...options, confirmed: true }, {
    runner(call) {
      calls.push(`${call.role}:${call.case_id}`);
      return { status: 'PASS', output: call.expected_output };
    },
  });
  assert.equal(report.status, 'PASS');
  assert.deepEqual(calls, [
    'low:route', 'low:state-capsule', 'strong:route', 'strong:state-capsule',
  ]);
  assert.equal(report.actual_calls, 4);
  assert.equal(report.results.length, 4);
  assert.equal(report.results.every((result) => /^[a-f0-9]{64}$/.test(result.output_digest)), true);
  assert.equal(JSON.stringify(report).includes('expected_output'), false);
});

test('release eval stops on first failure and never retries or exceeds the approved cap', () => {
  let calls = 0;
  const failed = runReleaseEval({ ...options, confirmed: true }, {
    runner() {
      calls += 1;
      return { status: 'FAIL', output: 'systemic failure' };
    },
  });
  assert.equal(failed.status, 'FAIL');
  assert.equal(failed.actual_calls, 1);
  assert.equal(calls, 1);

  assert.throws(
    () => runReleaseEval({ ...options, confirmed: true, maxCalls: 3 }, { runner() {} }),
    /predicted.*approved cap/i,
  );
  assert.throws(
    () => runReleaseEval({ ...options, confirmed: true, maxCalls: 5 }, { runner() {} }),
    /between 1 and 4/i,
  );
});

test('release eval CLI requires explicit model choices, max calls, and confirmation syntax', () => {
  assert.deepEqual(parseReleaseEvalArgs([
    '--repo', '/fixture',
    '--low-model', 'low-fixture',
    '--strong-model', 'strong-fixture',
    '--case', 'route',
    '--max-calls', '2',
    '--confirm-model-evals',
    '--json',
  ]), {
    repo: '/fixture', lowModel: 'low-fixture', strongModel: 'strong-fixture',
    cases: ['route'], maxCalls: 2, confirmed: true, json: true,
  });
  assert.throws(() => parseReleaseEvalArgs(['--max-calls', '4']), /low-model.*strong-model/i);
  assert.throws(() => parseReleaseEvalArgs([
    '--low-model', 'same', '--strong-model', 'same', '--max-calls', '4',
  ]), /distinct/i);
});
