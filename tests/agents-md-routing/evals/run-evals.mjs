#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import { spawn } from 'node:child_process';

const repoRoot = path.resolve(new URL('../../..', import.meta.url).pathname);
const evalDir = path.join(repoRoot, 'tests/agents-md-routing/evals');
const config = JSON.parse(fs.readFileSync(path.join(evalDir, 'evals.json'), 'utf8'));
const caseTimeoutMs = Number(process.env.AGENTS_ROUTING_EVAL_TIMEOUT_MS || 90000);
const concurrency = Number(process.env.AGENTS_ROUTING_EVAL_CONCURRENCY || 4);
const requestedCases = process.env.AGENTS_ROUTING_EVAL_CASES
  ? new Set(process.env.AGENTS_ROUTING_EVAL_CASES.split(',').map((item) => item.trim()).filter(Boolean))
  : null;
const cases = requestedCases
  ? config.cases.filter((testCase) => requestedCases.has(testCase.id))
  : config.cases;
const runId = new Date().toISOString().replace(/[:.]/g, '-');
const outBase = process.env.AGENTS_ROUTING_EVAL_OUT_DIR
  ? path.resolve(process.env.AGENTS_ROUTING_EVAL_OUT_DIR)
  : path.join('/tmp', 'agents-md-routing-evals');
const outDir = path.join(outBase, runId);
fs.mkdirSync(outDir, { recursive: true });

const policyFiles = [
  'AGENTS.md',
  'README.md',
  'skills/he-plan/SKILL.md',
  'skills/he-implement/SKILL.md',
  'skills/he-verify/SKILL.md',
  'skills/he-ship/SKILL.md',
  'skills/he-learn/SKILL.md',
  'skills/workflow-help/SKILL.md',
  'skills/workflow-help/references/route-map.md',
];

const policyDigestPattern = /workflow-help|he-plan|he-implement|he-verify|he-ship|he-learn|he-state|state file|stateful|resume source|steps\[\]|findings\[\]|guardrails\[\]|next\.ready|\/he:|stage|receipt|handover|worktree|transcript|context rot|Stage:|Decision:|Owner\/proof|Artifacts:|Blocker:|Next:|ready for|grill-me|Grill Me|session_state|one-question|aligned|no-guesswork|unlimited_until_aligned|open questions|open unknowns|Lavish|lavish-axi|poll receipt|saved choices|saved components|selected option|rejected options|localhost|to-prd|to-issues|readiness|ensure-worktree-ready|check-project-quality-gates|quality gate|push-blocking|project hooks|push dry-run|PASS|CONCERNS|FAIL|correct course|scope expands|deterministic|repeat work|learning-capture|learning finding|he-learn|test-quality|test-first|red-first|failing test|failed as expected|mutation|make it fail|TDD|lint|scanner|gate|script\/test\/hook\/eval|codebase-memory|context-mode|support tools|not stages|AGENTS\.md|repo-specific|global|canonical|read-only|vendor\/skill-upstreams|upstream skill|local wrapper|local caller|root owner|wrappers|duplicat|budget|tokens|o200k|600|component\/state|visual review|visual direction|UI choices|design-system|design SSOT|atomic-ui|theme|hardcoded|react-doctor|React Doctor|fallow|dupes|duplication|vercel-react-best-practices|flutter_skill_lints|dart analyze|Flutter|sentry|security-review|performance-rescue|e2e|real UI|screenshots|events|regression command|thermo|maintainability|no-mistakes|committed|GitHub Actions|gh.*CI|GH CI|parallel|batch fixes|rerun|fewest|least|BMAD|menu codes|Treehouse|700|blast radius|surrounding issues|Report:|Why:|What:|Risk:|Proof:/i;

const policyText = policyFiles
  .map((rel) => {
    const fullPath = path.join(repoRoot, rel);
    const lines = fs.readFileSync(fullPath, 'utf8')
      .split('\n')
      .filter((line) => policyDigestPattern.test(line));
    return `# ${rel}\n${lines.join('\n')}`;
  })
  .join('\n\n');

const allKeys = Array.from(new Set(config.cases.flatMap((testCase) => [
  ...testCase.expectTrue,
  ...testCase.expectFalse,
])));

function schemaFor(keys) {
  return {
  type: 'object',
  additionalProperties: false,
  required: keys,
  properties: Object.fromEntries(keys.map((key) => [key, {
    type: 'object',
    additionalProperties: false,
    required: ['value', 'reason'],
    properties: {
      value: { type: 'boolean' },
      reason: { type: 'string' },
    },
  }])),
  };
}

const keyDefinitions = [
  'usesHePlan: routes stage 1 planning/readiness to he-plan or /he:plan',
  'usesHeImplement: routes stage 2 owner-changing implementation to he-implement or /he:implement',
  'usesTestQualityInImplement: requires he-implement to load or use test-quality before code changes when behavior tests or TDD are involved',
  'requiresTddInImplement: requires test-first/red-first proof before owner-change, or mutation/make-it-fail proof when red-first is impossible',
  'recordsTestQualityProofEvidence: requires test-first-proof evidence to explicitly record test-quality scenario, skill, or review use',
  'startsImplementationWithoutTdd: incorrectly starts owner-change or implementation before test-quality scenarios and red-first or mutation proof',
  'usesHeVerify: enters, resumes, or routes the immediate next active stage to he-verify or /he:verify; true when the answer says to run, resume, or complete verify before ship; mentioning verify only as background is false',
  'usesHeShip: enters, resumes, or routes the immediate next active stage to he-ship or /he:ship; if ship is only a blocked/requested target and the answer says not to start ship yet, count false',
  'usesHeLearn: routes stage 5 durable learning to he-learn or /he:learn when repeated misses, review gaps, or ship findings exist',
  'keepsHeStageOrder: preserves the order he-plan -> he-implement -> he-verify -> he-ship -> he-learn when needed',
  'skipsHeStageOrder: incorrectly skips or reorders HE stages',
  'usesStageReceipt: uses, reads, or requires the compact stage receipt with Stage, State, Decision, Owner/proof, Artifacts, Blocker, and Next',
  'usesHandoverPrompt: requires each stage receipt to include a copy-paste fresh-session handover prompt with worktree path, he-state.json path, exact next /he:* command or loop-complete target, blockers, artifacts, and instruction to read state first',
  'usesHeStateFile: requires reading, writing, validating, or trusting he-state.json as the state source for feature handoff, readiness, resume, findings, guardrails, or blockers',
  'recordsFindingsInHeState: records failures, review findings, planning concerns, or blockers in he-state.json findings[] with owner repair stage',
  'recordsLearningFindingsInHeState: records repeated misses, process gaps, review gaps, or missing future guardrails as he-state.json findings[] with ownerStage he-learn and repairType learning',
  'routesOpenLearningToHeLearn: routes ship to /he:learn instead of loop-complete when open learning findings exist',
  'skipsLearningCapture: incorrectly leaves repeated misses, process gaps, or future guards out of he-state.json so he-learn has no input',
  'recordsGuardrailsInHeState: records missing or added deterministic scripts/tests/lints/scanners/hooks/evals in he-state.json guardrails[] with command, status, evidence, and push-blocking status',
  'usesProjectQualityGate: runs or requires check-project-quality-gates.mjs --require-push-gate for React/Next, JS/TS, or Flutter push-blocking gates',
  'requiresPushBlockingGuardrails: requires project hooks or push-blocking guardrails to be active and passed before ship, no-mistakes, or push dry-run trust',
  'startsFreshStageThread: prefers each HE stage to start in a fresh thread using the prior he-state.json path',
  'updatesHeStepsStatefully: requires internal steps to update steps[] before and after work, with receipts for done or blocked steps',
  'validatesHeStateBeforeReady: runs he-state.mjs validate before any ready-yes next-stage handoff',
  'blocksReadyYesWithoutValidState: blocks a ready-yes handoff or direct stage jump when state is missing, invalid, unvalidated, has pending/in_progress/blocked work, or lacks the required prior-stage receipt',
  'treatsChatAsSourceOfTruth: incorrectly treats chat transcript or memory as the authoritative state instead of he-state.json',
  'avoidsTranscriptDump: avoids relying on long transcript dumps for stage handoff or resume',
  'dumpsTranscriptForHandoff: incorrectly asks to carry or paste the whole transcript instead of a compact receipt',
  'blocksHeImplementWithoutPass: blocks he-implement unless he-plan readiness is PASS',
  'runsHeImplementWithoutPass: incorrectly starts he-implement from CONCERNS, FAIL, unknown owner, or weak readiness',
  'blocksHeShipBeforeVerifyClean: blocks he-ship until he-verify/local proof is clean and work is committed',
  'runsHeShipBeforeVerifyClean: incorrectly starts he-ship before verification is clean or committed',
  'usesHeLearnOnlyWhenNeeded: treats he-learn as conditional for repeated misses, review gaps, or ship findings rather than mandatory every time',
  'runsHeLearnAlways: incorrectly runs he-learn after every ship even when no durable learning is needed',
  'usesStageFailureLoop: routes failed stages back to the owning repair stage before retrying handoff',
  'skipsStageFailureLoop: incorrectly treats a stage failure as final or jumps to the next stage without repair',
  'usesWorkflowHelp: route unclear workflow or next-step questions to workflow-help',
  'keepsSupportToolsAsTools: treats codebase-memory, context-mode, and terse as support tools, not workflow stages',
  'treatsSupportToolsAsStages: incorrectly presents support tools as standalone workflow stages',
  'usesCodebaseMemoryAsSupport: uses codebase-memory for owners, callers, routes, structure, or blast radius',
  'usesContextModeAsSupport: uses context-mode for logs, diffs, tests, commands, APIs, or data processing',
  'usesExistingAcceptedSlices: recognizes that accepted vertical slices or task waves in plan.md are enough to move toward readiness and implementation',
  'avoidsRedundantToIssues: does not require to-issues when an accepted plan already contains agent-ready slices',
  'requiresToIssuesForExistingSlices: incorrectly treats to-issues as mandatory after grill-me even though plan.md already has accepted slices',
  'usesToIssuesForMissingSlices: routes to-issues when the post-grill-me plan lacks vertical slices, task waves, or agent-ready issue breakdown',
  'usesToIssuesForRequestedIssueCards: routes to-issues when the user explicitly asks to turn accepted slices into separate issue or tracker cards',
  'usesToPrdAndToIssuesForBigWork: routes broad unsliced work through to-prd and then to-issues before build',
  'usesComponentArtifactsForVisualUiDecisions: uses project-local component/state artifacts for UI flow or visual choices that cannot be judged from text',
  'keepsVisualArtifactsInsideGrillMe: treats visual decision artifacts as support inside grill-me, not as their own Plan/Implement/Verify stage',
  'treatsVisualArtifactAsRequiredStage: incorrectly requires a visual artifact for every feature or makes it a standalone workflow stage',
  'usesAtomicUi: includes atomic-ui for UI components, reusable controls, design-system, token, styling work, or project-local UI component/state decision artifacts',
  'checksDesignSsot: requires locating or creating PRODUCT.md, DESIGN.md, tokens, or the UI design SSOT before UI flow artifacts, visual decisions, or reusable UI styling edits',
  'skipsDesignSsot: incorrectly allows UI styling or reusable component work without checking or creating the project-local design SSOT',
  'usesReactDoctor: includes react-doctor for React or Next.js implementation/review',
  'usesFallow: includes fallow for JS/TS code health, cleanup, risk, or architecture checks',
  'usesFallowCloneGroups: requires fallow dupes, Fallow audit/dupes, clone groups, or duplication checks as part of React/JS/TS code health or push guardrails',
  'usesReactDoctorWithoutFallow: incorrectly runs React Doctor alone for React app code health when fallow is also required',
  'skipsFallowCloneGroups: incorrectly omits fallow duplication or clone-group checks when duplication or copy-paste is part of the React/JS/TS request',
  'usesVercelReactBestPractices: includes Vercel React best-practices for React/Next performance guidance',
  'usesOnlyGenericReactRoute: says only generic React skills or only react-doctor when the policy requires the full React route',
  'usesSentryWorkflow: routes all Sentry or observability work through sentry-workflow',
  'exposesSentrySetupSubskills: exposes sentry-sdk-setup or sentry-feature-setup as the user-facing route',
  'exposesSentryCliAsUserRoute: exposes sentry-cli as the user-facing route',
  'usesE2E: routes real UI flow proof to e2e',
  'requiresRealUiProof: requires a real browser/app/device flow, not just unit tests or curl',
  'requiresArtifactsOrRegressionCommand: requires screenshots/events/video/artifacts or a runnable regression command for UI proof',
  'allowsUnitTestsAsE2E: incorrectly allows unit tests alone to count as E2E proof',
  'usesThermoNuclearReview: routes strict maintainability PR/diff review to thermo-nuclear-code-quality-review',
  'treatsThermoAsPolishOnly: incorrectly treats thermo review as optional cosmetic polish',
  'usesSecurityReviewWhenTouched: routes security, auth, secrets, or data-exposure risk to security-review when requested or touched',
  'usesPerformanceRescueWhenTouched: routes latency, bundle, query, or efficiency risk to performance-rescue when requested or touched',
  'keepsRiskReviewsConditional: treats security-review and performance-rescue as conditional reviews for requested or touched risks, not default stages',
  'runsRiskReviewsBeforeThermo: places conditional security/performance reviews before thermo-nuclear-code-quality-review in the verify loop',
  'treatsRiskReviewsAsDefaultStages: incorrectly requires security-review or performance-rescue for every feature regardless of touched risk',
  'usesVerifyLoop: requires a local verify loop between implementation and proof until blockers are gone',
  'usesDeterministicOwner: runs an existing deterministic owner such as a script, test, hook, or eval before fresh reasoning for known repeat work',
  'createsDeterministicOwnerForRecurringWork: adds lint, scanner, and a script/test/hook/eval gate when a recurring deterministic violation has no owner',
  'skipsDeterministicOwner: incorrectly uses fresh LLM-only reasoning while an existing deterministic owner should run',
  'createsPassThroughWrapper: incorrectly adds a wrapper with no validation, transform, owner boundary, or integration',
  'keepsUpstreamSkillsReadOnly: treats vendored submodule skill text under vendor/skill-upstreams or symlinked upstream skills as canonical read-only inputs',
  'changesLocalSkillCalling: changes local wrappers, route-map, integration scripts, hooks, or evals when Hard Eng needs different behavior from an upstream skill',
  'editsUpstreamSkillText: incorrectly edits vendored upstream skill text or symlinked upstream skill files to change behavior',
  'keepsProjectAgentsRepoSpecific: keeps project AGENTS.md limited to repo-specific additions instead of restating global workflow, hygiene, or token-budget policy',
  'reusesGlobalAgentsHygieneOwner: recognizes that global .agents owns general AGENTS.md hygiene, compactness, and token-budget enforcement unless a project-only gap is proven',
  'allowsProjectSpecificAgentsFacts: allows project AGENTS.md to keep concrete repo-specific facts such as project keys, setup commands, out-of-scope paths, local CLI wrappers, or backend invariants',
  'requiresProjectAgentsTokenCap: requires project AGENTS.md to stay at or under the global repo-specific cap of 600 o200k tokens',
  'duplicatesGlobalPolicyInProjectAgents: incorrectly copies global workflow, skill routing, AGENTS hygiene, token-budget, or generic policy into project AGENTS.md',
  'wouldAddProjectLocalAgentsGate: incorrectly chooses to add a project-local AGENTS budget/check script, package hook, or token gate when global .agents already owns the rule and no project-only gap was proven',
  'acceptsOverBudgetProjectAgents: incorrectly allows a project AGENTS.md to exceed the global 600 o200k token cap',
  'runsThermoBeforeE2E: runs thermo-nuclear-code-quality-review before expensive E2E in the local verify loop',
  'runsE2ELastWhenNeeded: runs E2E last when a user-visible flow changed',
  'loopsBackAfterVerificationFailure: sends tests, review, or E2E failures back to implementation and reruns affected proof',
  'waitsForCleanLoopBeforeNoMistakes: requires clean tests/review/required E2E plus committed work before no-mistakes',
  'runsNoMistakesBeforeCleanLoop: incorrectly runs no-mistakes before the local verify loop is clean',
  'usesReadinessGate: requires readiness before implementation',
  'readinessConcernsOrFail: marks weak readiness, missing context/design SSOT, unclear scope, missing owner, or missing proof as CONCERNS or FAIL instead of PASS/start coding',
  'usesGrillMeWhenAmbiguous: routes ambiguous feature scope to grill-me',
  'usesGrillMeUntilAligned: says Grill Me asks one question at a time as many times as needed until aligned with no guesswork',
  'requiresNoGuessworkAlignment: requires user-confirmed alignment, no open questions, and no open unknowns before Plan can hand off to implementation',
  'allowsParkedPlanReady: incorrectly allows parked questions, artifacts, UI decisions, or unknowns to produce a ready handoff to implementation',
  'usesGrillMeUiStagesWhenUnclear: sends unclear UI flow or visual direction through Grill Me UI flow or visual design stages instead of guessing in implementation',
  'usesLavishForUiDecision: uses Lavish only to compare UI options and collect UI decisions when UI flow or visual design needs user choice',
  'requiresLavishPollReceipt: requires no-timeout npx -y lavish-axi poll evidence or poll receipt before accepting a Lavish UI decision',
  'requiresSavedUiChoicesComponents: requires saving selected choice, rejected options, and chosen components for UI decisions',
  'usesLavishForNonUi: incorrectly uses Lavish for generic plans, reports, non-UI diagrams, or stage management',
  'startsImplementationWithUnknowns: true only when the answer explicitly permits coding or implementation to start despite missing outcome, owner, blast radius, proof path, or risk routing; false when it blocks implementation',
  'usesTreehouseWorkspace: for feature planning/coding or next implementation after an accepted plan, names Treehouse worktree or isolated branch before implementation proceeds',
  'skipsWorkspaceIsolation: incorrectly starts feature implementation without Treehouse/worktree/branch isolation',
  'usesWorktreeReadyGuard: runs or requires scripts/ensure-worktree-ready.sh after worktree creation or before final gate validation',
  'skipsWorktreeReadyGuard: incorrectly trusts a worktree, no-mistakes checkout, or push dry-run without the worktree readiness guard',
  'requiresProjectHooksBeforeDryRun: states project hooks/worktree hook readiness must be active before no-mistakes, push, final gate, or trusting any push dry-run evidence',
  'treatsDryRunAsSufficientAlone: incorrectly treats git push --dry-run or explicit refspec dry-run as sufficient without proving project hooks',
  'correctsCourseOnScopeExpansion: stops and reroutes when scope expands midstream',
  'routesBackToPlanning: uses grill-me, to-prd, to-issues, or codebase-design for expanded or unclear scope',
  'silentlyExpandsScope: continues implementation after scope expansion without rerouting',
  'usesNoMistakes: routes committed validation, push, PR, or CI to no-mistakes',
  'usesCostAwareGhCi: GH Actions/gh CI reads failing logs first, parallelizes independent logs/jobs, batches fixes, reruns fewest checks',
  'wastesGithubActions: pushes speculative commits, repeats reruns, or serializes independent CI work wastefully',
  'endsAtNoMistakes: feature-to-PR flow ends at no-mistakes after implementation/review proof',
  'requiresCommittedWorkBeforeNoMistakes: states no-mistakes validates committed implementation work',
  'usesNoMistakesBeforeImplementation: incorrectly starts no-mistakes before implementation proof',
  'mapsBmadToLocalSkills: maps BMAD-style requests to local skills and workflow names',
  'usesBmadMenuCodes: follows BMAD persona/menu codes as local workflow commands',
  'requires700LineSplit: requires touched or connected files over 700 lines to be split below 700 lines',
  'skips700LineSplit: incorrectly leaves a touched or connected file over 700 lines unchanged',
  'requiresBlastRadius: requires semantic changes to include blast radius analysis',
  'fixesSurroundingIssues: requires surrounding issues found in blast radius to be fixed',
  'skipsBlastRadius: incorrectly allows semantic edits without blast radius analysis',
  'usesCompactReportTemplate: reports using Why, What, Risk, and Proof fields',
  'usesLongReportTemplate: incorrectly reports using the old long Problem/Fixes/Blast radius/Testing template',
].join('\n');

function keysFor(testCase) {
  return Array.from(new Set([
    ...testCase.expectTrue,
    ...testCase.expectFalse,
  ]));
}

function definitionsFor(keys) {
  const wanted = new Set(keys);
  return keyDefinitions
    .split('\n')
    .filter((line) => wanted.has(line.split(':')[0]))
    .join('\n');
}

if (requestedCases && cases.length !== requestedCases.size) {
  const found = new Set(cases.map((testCase) => testCase.id));
  const missing = Array.from(requestedCases).filter((id) => !found.has(id));
  throw new Error(`Unknown eval case(s): ${missing.join(', ')}`);
}

function promptFor(testCase, retryNote = '') {
  const keys = keysFor(testCase);
  return `You are evaluating local .agents workflow routing policy.
Do not use tools. Use only the policy text below.
Return JSON only, with every key below as a boolean and a short "reason" string.
Return one JSON object with every key exactly once.
For each key, use this exact shape: "<key>": {"value": true_or_false, "reason": "short reason"}.
Set each key for this user request, not merely because the policy mentions the concept.
For anti-pattern keys such as incorrectly, skips, runs-before, duplicates, exposes, or allows, set true only when the agent response should commit that anti-pattern. Set false when the response should detect, reject, block, or repair that anti-pattern.
Classify what the policy requires the agent to do for the request.
Stage keys mean the immediate next active route, or a required stage in the full path when the user asks for the whole workflow/order. If a stage is only named as a blocked target, set that stage key false.
State keys are true when the answer must read, write, validate, or update he-state.json for readiness, findings, guardrails, or handoff.
${retryNote}
Keys: ${keys.join(', ')}
Definitions:
${definitionsFor(keys)}
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
    if (char === '"') inString = true;
    else if (char === '{') depth += 1;
    else if (char === '}') {
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

function runCodex(prompt, outputPath, outputSchemaPath) {
  return new Promise((resolve) => {
    const child = spawn('codex', [
      'exec',
      '-m',
      config.model,
      '--sandbox',
      'read-only',
      '--skip-git-repo-check',
      '--ignore-user-config',
      '--color',
      'never',
      '--output-schema',
      outputSchemaPath,
      '-o',
      outputPath,
      '-',
    ], {
      cwd: process.env.TMPDIR || '/tmp',
      stdio: ['pipe', 'pipe', 'pipe'],
    });
    let stdout = '';
    let stderr = '';
    let timedOut = false;
    const timer = setTimeout(() => {
      timedOut = true;
      child.kill('SIGTERM');
    }, caseTimeoutMs);
    child.stdout.on('data', (chunk) => { stdout += chunk.toString(); });
    child.stderr.on('data', (chunk) => { stderr += chunk.toString(); });
    child.on('error', (error) => {
      clearTimeout(timer);
      resolve({ status: null, error, stdout, stderr });
    });
    child.on('close', (status) => {
      clearTimeout(timer);
      resolve({
        status,
        error: timedOut ? new Error(`codex timed out after ${caseTimeoutMs}ms`) : null,
        stdout,
        stderr,
      });
    });
    child.stdin.end(prompt);
  });
}

async function runCase(testCase) {
  const caseDir = path.join(outDir, testCase.id);
  fs.mkdirSync(caseDir, { recursive: true });
  const expectedKeys = keysFor(testCase);
  const caseSchemaPath = path.join(caseDir, 'routing-output-schema.json');
  fs.writeFileSync(caseSchemaPath, `${JSON.stringify(schemaFor(expectedKeys), null, 2)}\n`);
  let errors = [];
  let parsed = {};
  let attempts = [];

  for (let attempt = 1; attempt <= 2; attempt += 1) {
    const retryNote = attempt === 1
      ? ''
      : 'Retry note: your previous answer omitted required keys. Return every key in the requested object shape.';
    const prompt = promptFor(testCase, retryNote);
    const outputPath = path.join(caseDir, attempt === 1 ? 'output.json' : `output-attempt-${attempt}.json`);
    fs.writeFileSync(path.join(caseDir, attempt === 1 ? 'prompt.txt' : `prompt-attempt-${attempt}.txt`), prompt);

    const result = await runCodex(prompt, outputPath, caseSchemaPath);

    fs.writeFileSync(path.join(caseDir, attempt === 1 ? 'stdout.txt' : `stdout-attempt-${attempt}.txt`), result.stdout || '');
    fs.writeFileSync(path.join(caseDir, attempt === 1 ? 'stderr.txt' : `stderr-attempt-${attempt}.txt`), result.stderr || '');

    errors = [];
    parsed = {};
    if (result.error) errors.push(result.error.message);
    if (result.status !== 0) errors.push(`codex exit status ${result.status}`);
    try {
      parsed = fs.existsSync(outputPath)
        ? JSON.parse(fs.readFileSync(outputPath, 'utf8'))
        : extractJson(result.stdout || '');
    } catch (error) {
      errors.push(error.message);
    }

    const missingKeys = expectedKeys.filter((key) => boolValue(parsed, key) === undefined);
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

const queue = [...cases];
const results = [];

async function worker() {
  while (queue.length) {
    const testCase = queue.shift();
    const result = await runCase(testCase);
    results.push(result);
    console.log(`${result.passed ? 'PASS' : 'FAIL'} ${result.id}${result.errors.length ? `: ${result.errors.join('; ')}` : ''}`);
  }
}

await Promise.all(Array.from({ length: Math.min(concurrency, cases.length) }, worker));
results.sort((left, right) => cases.findIndex((item) => item.id === left.id) - cases.findIndex((item) => item.id === right.id));
const summary = {
  runId,
  model: config.model,
  passed: results.filter((result) => result.passed).length,
  total: results.length,
  results,
};

fs.writeFileSync(path.join(outDir, 'summary.json'), `${JSON.stringify(summary, null, 2)}\n`);
console.log(`results: ${outDir}`);
console.log(`passed: ${summary.passed}/${summary.total}`);
for (const result of results) {
  console.log(`${result.passed ? 'PASS' : 'FAIL'} ${result.id}${result.errors.length ? `: ${result.errors.join('; ')}` : ''}`);
}
process.exit(summary.passed === summary.total ? 0 : 1);
