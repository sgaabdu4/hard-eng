import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { digestValue, sha256 } from './canonical.mjs';

const PURPOSE = 'release-only route, state-tool, and capsule compatibility';
const cases = new Map([
  ['route', {
    expected: [
      'ROUTE_NEW=Plan',
      'ROUTE_ACCEPTED=Build',
      'LIFECYCLE=Plan>Build-Verify-loop>Ship>Learn-conditional',
    ].join('\n'),
    prompt: [
      'This is an explicitly approved, read-only Hard Eng release evaluation.',
      'Invoke $hard-eng. Do not edit files, start a run, or call network tools.',
      'Check the route contract for a new ambiguous feature and bounded accepted work.',
      'Return exactly these three lines and nothing else:',
      'ROUTE_NEW=Plan',
      'ROUTE_ACCEPTED=Build',
      'LIFECYCLE=Plan>Build-Verify-loop>Ship>Learn-conditional',
    ].join('\n'),
  }],
  ['state-capsule', {
    expected: [
      'TOOL=state',
      'STATUS=unbound-or-resumable',
      'RESUME=checkpoint-and-capsule',
    ].join('\n'),
    prompt: [
      'This is an explicitly approved, read-only Hard Eng release evaluation.',
      'Invoke $hard-eng and inspect only its state-tool and resume contract.',
      'Do not edit files, start a run, or call network tools.',
      'Return exactly these three lines and nothing else:',
      'TOOL=state',
      'STATUS=unbound-or-resumable',
      'RESUME=checkpoint-and-capsule',
    ].join('\n'),
  }],
]);

function modelName(value, label) {
  if (typeof value !== 'string' || !value.trim() || value.length > 200 || /[\r\n\0]/.test(value)) {
    throw new Error(`${label} must be one explicit bounded Codex-compatible model name.`);
  }
  return value.trim();
}

function selectedCases(values) {
  const chosen = values?.length ? values : [...cases.keys()];
  if (chosen.length < 1 || chosen.length > 2 || new Set(chosen).size !== chosen.length) {
    throw new Error('Release eval requires one or two distinct cases.');
  }
  for (const value of chosen) if (!cases.has(value)) throw new Error(`Unknown release eval case: ${value}.`);
  return chosen;
}

function releaseEvalPlan(options) {
  const lowModel = modelName(options.lowModel, '--low-model');
  const strongModel = modelName(options.strongModel, '--strong-model');
  if (lowModel === strongModel) throw new Error('Release eval low and strong models must be distinct.');
  if (!Number.isInteger(options.maxCalls) || options.maxCalls < 1 || options.maxCalls > 4) {
    throw new Error('--max-calls must be between 1 and 4.');
  }
  const caseIds = selectedCases(options.cases);
  const models = [{ role: 'low', model: lowModel }, { role: 'strong', model: strongModel }];
  const predictedCalls = models.length * caseIds.length;
  if (predictedCalls > options.maxCalls) {
    throw new Error(`Release eval predicted ${predictedCalls} calls, above the approved cap of ${options.maxCalls}.`);
  }
  const facts = {
    purpose: PURPOSE,
    models,
    cases: caseIds,
    predicted_calls: predictedCalls,
    max_calls: options.maxCalls,
    concurrency: 1,
    automatic_retries: 0,
  };
  return { ...facts, evidence_digest: digestValue(facts) };
}

function childEnvironment(env) {
  return Object.fromEntries(
    [
      'PATH', 'HOME', 'TMPDIR', 'TMP', 'TEMP', 'SHELL', 'LANG', 'LC_ALL',
      'LC_CTYPE', 'TERM', 'SSH_AUTH_SOCK', 'CODEX_HOME',
    ]
      .filter((key) => env[key] !== undefined)
      .map((key) => [key, env[key]]),
  );
}

function runCodexCall(call, { env = process.env } = {}) {
  const temporary = fs.mkdtempSync(path.join(os.tmpdir(), 'hard-eng-release-eval-'));
  const outputFile = path.join(temporary, 'last-message.txt');
  try {
    const result = spawnSync('codex', [
      'exec', '--ephemeral', '--sandbox', 'read-only', '--model', call.model,
      '--color', 'never', '--output-last-message', outputFile, '-C', call.repo,
      call.prompt,
    ], {
      env: childEnvironment(env),
      encoding: 'utf8',
      timeout: 300_000,
      maxBuffer: 512 * 1024,
      shell: false,
    });
    const safeOutput = fs.existsSync(outputFile) && fs.lstatSync(outputFile).isFile()
      && !fs.lstatSync(outputFile).isSymbolicLink() && fs.statSync(outputFile).size <= 64 * 1024;
    return {
      status: result.status === 0 && !result.error && safeOutput ? 'PASS' : 'FAIL',
      output: safeOutput ? fs.readFileSync(outputFile, 'utf8') : '',
    };
  } finally {
    fs.rmSync(temporary, { recursive: true, force: true });
  }
}

export function runReleaseEval(options, {
  runner = runCodexCall,
  env = process.env,
} = {}) {
  const plan = releaseEvalPlan(options);
  if (options.confirmed !== true) {
    return {
      status: 'APPROVAL_REQUIRED',
      ...plan,
      confirmation_flag: '--confirm-model-evals',
      actual_calls: 0,
      results: [],
    };
  }

  const results = [];
  outer: for (const model of plan.models) {
    for (const caseId of plan.cases) {
      if (results.length >= plan.max_calls) throw new Error('Release eval call cap would be exceeded.');
      const contract = cases.get(caseId);
      let observed;
      try {
        observed = runner({
          ...model,
          case_id: caseId,
          repo: path.resolve(options.repo),
          prompt: contract.prompt,
          expected_output: contract.expected,
        }, { env });
      } catch (error) {
        observed = { status: 'FAIL', output: '', error_digest: sha256(String(error?.message ?? error)) };
      }
      const output = String(observed?.output ?? '').replace(/\r\n?/g, '\n').trim();
      const passed = observed?.status === 'PASS' && output === contract.expected;
      results.push({
        role: model.role,
        model: model.model,
        case_id: caseId,
        status: passed ? 'PASS' : 'FAIL',
        reason_code: passed ? null : observed?.status === 'PASS' ? 'contract-mismatch' : 'runner-failure',
        output_digest: sha256(output),
      });
      if (!passed) break outer;
    }
  }
  return {
    status: results.length === plan.predicted_calls && results.every((result) => result.status === 'PASS')
      ? 'PASS'
      : 'FAIL',
    ...plan,
    actual_calls: results.length,
    results,
  };
}

export function parseReleaseEvalArgs(argv) {
  const options = {
    repo: process.cwd(), lowModel: null, strongModel: null, cases: [],
    maxCalls: null, confirmed: false, json: false,
  };
  for (let index = 0; index < argv.length; index += 1) {
    const value = argv[index];
    if (value === '--repo') options.repo = path.resolve(argv[++index]);
    else if (value === '--low-model') options.lowModel = argv[++index];
    else if (value === '--strong-model') options.strongModel = argv[++index];
    else if (value === '--case') options.cases.push(argv[++index]);
    else if (value === '--max-calls') options.maxCalls = Number.parseInt(argv[++index], 10);
    else if (value === '--confirm-model-evals') options.confirmed = true;
    else if (value === '--json') options.json = true;
    else throw new Error(`Unknown release eval option: ${value}.`);
  }
  if (!options.lowModel || !options.strongModel) {
    throw new Error('Release eval requires explicit --low-model and --strong-model choices.');
  }
  releaseEvalPlan(options);
  return options;
}
