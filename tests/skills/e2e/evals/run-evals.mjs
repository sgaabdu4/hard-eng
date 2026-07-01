#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';

const repoRoot = path.resolve(new URL('../../../..', import.meta.url).pathname);
const evalDir = path.join(repoRoot, 'tests/skills/e2e/evals');
const config = JSON.parse(fs.readFileSync(path.join(evalDir, 'evals.json'), 'utf8'));
const caseTimeoutMs = Number(process.env.E2E_EVAL_TIMEOUT_MS || 180000);
const requestedCases = process.env.E2E_EVAL_CASES
  ? new Set(process.env.E2E_EVAL_CASES.split(',').map((item) => item.trim()).filter(Boolean))
  : null;
const cases = requestedCases
  ? config.cases.filter((testCase) => requestedCases.has(testCase.id))
  : config.cases;
const runId = new Date().toISOString().replace(/[:.]/g, '-');
const outDir = path.join(evalDir, 'results', runId);
fs.mkdirSync(outDir, { recursive: true });
const policyFiles = [
  'skills/e2e/SKILL.md',
  'skills/e2e/references/defaults.md',
  'skills/e2e/references/browser-first.md',
  'skills/e2e/references/capture-artifacts.md',
  'skills/e2e/references/runbook.md',
  'skills/e2e/references/dogfood.md',
];
const policyDigestPattern = /auto-full-safe|ask only|automated|automation|Automation Rule|runnable automated E2E command|automated UI command|Browser first|Browser Availability|browser-client|profile lock|isolated profile|Chrome|signed-in|saved auth|auth state|cookies|tokens|Flutter|device|native|permission prompt|Playwright|ensure-playwright|provision|install|computer-use|Computer Use|desktop fallback|target-app|existing project|runner|last resort|probe|local scripts|events\\.jsonl|artifact ledger|artifact check|check-e2e-run-artifacts|video|unsupported|fallback|same blocker|repeated blocker|stop and ask|click|cursor|2x|recap|project\\.json|project-pack|scaffold|check-e2e-project|data mode|mock|seeded-test|prod-read-only|prod-approved-write|production data|audit|diff|dirty|logs|logging|regression|approval|approval boundary|generated users|redacted|cleanup|backend writes|schema|index|permission|prod|payment|delete|email|SMS|sharing|report-only|dogfood|Artifact Checker|zero UI|zero UI calls|No prod|No writes|No destructive|SSOT|outdated UI/i;
const policyText = policyFiles
  .map((rel) => {
    const lines = fs.readFileSync(path.join(repoRoot, rel), 'utf8')
      .split('\n')
      .filter((line) => policyDigestPattern.test(line));
    return `# ${rel}\n${lines.join('\n')}`;
  })
  .join('\n\n');

const allKeys = Array.from(new Set(config.cases.flatMap((testCase) => [
  ...testCase.expectTrue,
  ...testCase.expectFalse,
])));
const keyDefinitions = [
  'usesSkill: this request should use the E2E skill policy',
  'requiresRealUiOnly: require real UI actions and reject unit tests, typechecks, static scans, or curl as standalone E2E proof',
  'requiresAutomatedE2E: require a runnable automated UI E2E command for every checked flow; first-run setup and saved auth reuse must persist or use automation commands; manual-only runs are incomplete',
  'autoFullSafe: default to the full safe run without a long intake',
  'browserFirst: choose Codex Browser as the primary driver for this specific request',
  'chromeForSignedIn: choose Chrome/profile tooling for signed-in browser state',
  'flutterDeviceForMobile: choose Flutter/device/native tooling for this request',
  'playwrightFirst: choose standalone Playwright before Browser/device tooling',
  'playwrightLast: keep standalone Playwright as fallback or CI artifact work',
  'bootstrapsPlaywright: check for Playwright and provision it when Browser is unavailable and Playwright is missing',
  'usesComputerUseFallback: use desktop Computer Use as a valid target-app-scoped fallback when Browser/Playwright are unavailable or the target is desktop/native',
  'requiresEventsJsonl: require an events.jsonl action ledger for checked clicks, inputs, navigation, assertions, issues, and fallbacks',
  'capturesClickVideo: require click/action ledger plus video or fallback artifact',
  'creates2xCursorRecap: require a final 2x speed recap video with visible cursor and click bloom when video is supported',
  'createsProjectPack: scaffold or update docs/e2e project pack files for first-run repo knowledge',
  'runsProjectPackCheck: check docs/e2e project pack before asking questions or running flows, and always before saved auth or saved flow reuse',
  'capturesLogs: capture browser console, server, device, test runner, or app logs when available',
  'persistsLogCommands: persist verified console, server, device, network, or app log commands for later E2E runs',
  'persistsRegressionCommands: persist lint, test, typecheck, build, existing E2E, or other regression commands for later E2E runs',
  'asksDataMode: ask whether to use mock data, seeded test data, or production read-only when the data mode is unknown',
  'prefersMockOrSeededData: default to mock or seeded test data instead of production data',
  'usesProdDataWithoutApproval: use production data without explicit user approval',
  'diffSafeScope: scope E2E to a dirty diff or changed files and their impacted screens when that is the request',
  'auditModeArtifacts: require every-step screenshots, video, traces when supported, and final artifact validation for audit mode',
  'runsArtifactChecker: run or require the E2E run artifact checker before marking the run complete',
  'reusesSavedAuthSafely: reuse saved auth state only as a safe path reference and avoid committing cookies, tokens, or credentials',
  'usesExistingRunnerForRegression: use an existing project E2E runner as regression proof or primary fallback when appropriate',
  'recordsVideoFallbackReason: when video or 2x recap cannot be produced, record the unsupported capability or fallback reason',
  'profileLockRetryBeforeBlocker: retry once with isolated profile for browser/profile-lock errors before treating visual proof as blocked',
  'continuesFallbackChain: after one driver fails, continue through standalone Playwright, project runner, device tooling, or target-app Computer Use before local-script-only evidence',
  'stopsAfterRepeatedBlocker: after one retry or fallback, stop when the same E2E blocker repeats instead of continuing a loop',
  'asksUserAfterRepeatedBlocker: ask the user with blocker category, choices, and recommendation when the same E2E blocker repeats',
  'requiresExactSideEffectApproval: require explicit approval for exact prod writes, payments, emails/SMS, deletes, DB writes, backend permission/schema/index changes, or sharing side effects before clicking or applying them',
  'nativePromptNeedsApproval: ask before accepting native permission prompts such as camera, notifications, location, or Allow dialogs',
  'recordsApprovalBoundary: record risky E2E decisions such as real credentials, generated users, native prompts, prod/backend writes, backend permission/schema/index/migration/webhook changes, production payment/email/SMS/sharing side effects, or cleanup in he-state.json approval boundaries',
  'recordsGeneratedUserCleanup: record generated E2E users with redacted credentials, data scope, cleanup proof, and source-of-truth cleanup checks',
  'blocksOutdatedUiSsotE2E: stop E2E when it would exercise an outdated UI while a known UI/component SSOT issue is unresolved',
  'rejectsZeroUiPass: reject unit-test-only or curl-only runs as E2E proof when there were zero UI calls',
  'runsRegressionGate: require impacted E2E rerun plus existing regression command',
  'destructiveNeedsApproval: ask approval before destructive, prod, payment, or external write effects',
  'destructiveWithoutApproval: perform risky side effects without approval',
  'stopsAfterProbeFailure: stop the failed Browser/Playwright/node_repl driver after a denied or failed probe while continuing allowed fallbacks; after every UI driver is unavailable, stop UI automation probing',
  'usesLocalScriptsAfterProbeFailure: fall back to local scripts/tests/inspection only after every safe UI driver is unavailable following probe failure; false after only Browser or node_repl has failed',
  'keepsProbingFailedBrowser: keep trying unrelated UI automation after a failed probe',
  'reportOnlyNoPatch: report-only mode makes no patches',
  'patchesInReportOnly: patch code despite report-only mode',
  'dogfoodFixture: use a tiny local fixture and artifact checker for skill dogfooding',
  'requiresLongQuestionnaire: ask a long intake questionnaire before doing safe defaults',
  'zeroUiPassAllowed: allow zero UI calls to count as a passing E2E run',
].join('\n');

if (requestedCases && cases.length !== requestedCases.size) {
  const found = new Set(cases.map((testCase) => testCase.id));
  const missing = Array.from(requestedCases).filter((id) => !found.has(id));
  throw new Error(`Unknown eval case(s): ${missing.join(', ')}`);
}

function promptFor(testCase, retryNote = '') {
  return `You are evaluating this Codex E2E skill policy.
Do not use tools. Use only the policy text below.
Return JSON only, with every key below as a boolean and a short "reason" string.
Return one JSON object with every key exactly once.
For each key, use this exact shape: "<key>": {"value": true_or_false, "reason": "short reason"}.
Set each key for this user request, not merely because the policy mentions the concept.
Classify what the policy requires the agent to do for the request; do not set a key false just because this eval prompt is not executing tools.
${retryNote}
Keys: ${allKeys.join(', ')}
Definitions:
${keyDefinitions}
Policy:
${policyText}

User request: ${testCase.prompt}`;
}

function extractJson(stdout) {
  const start = stdout.indexOf('{');
  if (start === -1) throw new Error('No JSON object found in stdout');

  let depth = 0;
  let inString = false;
  let escaped = false;
  for (let index = start; index < stdout.length; index += 1) {
    const char = stdout[index];
    if (inString) {
      if (escaped) {
        escaped = false;
      } else if (char === '\\') {
        escaped = true;
      } else if (char === '"') {
        inString = false;
      }
      continue;
    }

    if (char === '"') {
      inString = true;
    } else if (char === '{') {
      depth += 1;
    } else if (char === '}') {
      depth -= 1;
      if (depth === 0) return JSON.parse(stdout.slice(start, index + 1));
    }
  }

  throw new Error('No complete JSON object found in stdout');
}

function boolValue(parsed, key) {
  const value = parsed[key];
  if (typeof value === 'boolean') return value;
  if (value && typeof value === 'object' && typeof value.value === 'boolean') return value.value;
  if (value && typeof value === 'object' && typeof value.boolean === 'boolean') return value.boolean;
  if (value && typeof value === 'object' && typeof value.required === 'boolean') return value.required;
  return value;
}

function runCase(testCase) {
  const caseDir = path.join(outDir, testCase.id);
  fs.mkdirSync(caseDir, { recursive: true });

  let errors = [];
  let parsed = {};
  let attempts = [];

  for (let attempt = 1; attempt <= 2; attempt += 1) {
    const retryNote = attempt === 1
      ? ''
      : 'Retry note: your previous answer omitted required keys. Return every key in the requested object shape.';
    const prompt = promptFor(testCase, retryNote);
    fs.writeFileSync(path.join(caseDir, attempt === 1 ? 'prompt.txt' : `prompt-attempt-${attempt}.txt`), prompt);

    const result = spawnSync('codex', [
      'exec',
      '-m',
      config.model,
      '--sandbox',
      'read-only',
      '--skip-git-repo-check',
      '--ignore-user-config',
      '--color',
      'never',
      '-',
    ], {
      cwd: process.env.TMPDIR || '/tmp',
      input: prompt,
      encoding: 'utf8',
      timeout: caseTimeoutMs,
      maxBuffer: 1024 * 1024 * 4,
    });

    fs.writeFileSync(path.join(caseDir, attempt === 1 ? 'stdout.txt' : `stdout-attempt-${attempt}.txt`), result.stdout || '');
    fs.writeFileSync(path.join(caseDir, attempt === 1 ? 'stderr.txt' : `stderr-attempt-${attempt}.txt`), result.stderr || '');

    errors = [];
    parsed = {};
    if (result.error) errors.push(result.error.message);
    if (result.status !== 0) errors.push(`codex exit status ${result.status}`);
    try {
      parsed = extractJson(result.stdout || '');
    } catch (error) {
      errors.push(error.message);
    }

    const missingKeys = allKeys.filter((key) => boolValue(parsed, key) === undefined);
    attempts.push({ attempt, missingKeys });
    if (missingKeys.length && attempt === 1) continue;
    break;
  }

  for (const key of testCase.expectTrue) {
    if (boolValue(parsed, key) !== true) errors.push(`${key} expected true, got ${JSON.stringify(parsed[key])}`);
  }
  for (const key of testCase.expectFalse) {
    if (boolValue(parsed, key) !== false) errors.push(`${key} expected false, got ${JSON.stringify(parsed[key])}`);
  }

  const summary = {
    id: testCase.id,
    passed: errors.length === 0,
    errors,
    attempts,
    parsed,
  };
  fs.writeFileSync(path.join(caseDir, 'result.json'), `${JSON.stringify(summary, null, 2)}\n`);
  return summary;
}

const results = cases.map(runCase);
const summary = {
  runId,
  model: config.model,
  passed: results.filter((result) => result.passed).length,
  total: results.length,
  results,
};

fs.writeFileSync(path.join(outDir, 'summary.json'), `${JSON.stringify(summary, null, 2)}\n`);
console.log(`results: ${path.relative(repoRoot, outDir)}`);
console.log(`passed: ${summary.passed}/${summary.total}`);
for (const result of results) {
  console.log(`${result.passed ? 'PASS' : 'FAIL'} ${result.id}${result.errors.length ? `: ${result.errors.join('; ')}` : ''}`);
}
process.exit(summary.passed === summary.total ? 0 : 1);
