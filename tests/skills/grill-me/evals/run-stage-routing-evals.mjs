#!/usr/bin/env node
import fs from "node:fs";
import path from "node:path";
import { spawnSync } from "node:child_process";

const evalRoot = path.resolve(path.dirname(new URL(import.meta.url).pathname));
const repoRoot = path.resolve(evalRoot, "../../../..");
const config = JSON.parse(fs.readFileSync(path.join(evalRoot, "stage-routing-evals.json"), "utf8"));
const model = process.env.GRILL_ME_STAGE_EVAL_MODEL || config.model || "gpt-5.4-mini";
const timeoutMs = Number(process.env.GRILL_ME_STAGE_EVAL_TIMEOUT_MS || 180000);
const outRoot = process.env.GRILL_ME_STAGE_EVAL_ROOT || path.join("/tmp", "grill-me-stage-routing-evals");
const outDir = path.join(outRoot, new Date().toISOString().replace(/[:.]/g, "-"));
fs.mkdirSync(outDir, { recursive: true });

const stageSources = {
  intake: [
    "skills/grill-me/SKILL.md",
    "skills/grill-me/references/start-routing.md",
    "skills/grill-me/modules/modes.md",
    "skills/grill-me/modules/orchestration.md"
  ],
  product: ["skills/grill-me/modules/product.md"],
  "ui-flow": ["skills/grill-me/modules/ui-flow.md"],
  "visual-design": ["skills/grill-me/modules/visual-design.md"],
  "prototype-tech": ["skills/grill-me/modules/prototype-tech.md"],
  prototype: ["skills/grill-me/modules/prototype.md"],
  "backend-tech": ["skills/grill-me/modules/backend-tech.md"],
  "vertical-slices": ["skills/grill-me/modules/vertical-slices.md"],
  "final-plan": ["skills/grill-me/modules/final-plan.md"],
  "session-state": ["skills/grill-me/modules/session-state.md"],
  "domain-docs": ["skills/grill-me/modules/domain-docs.md"],
  questions: ["skills/grill-me/modules/questions.md"]
};

for (const stage of config.stages) {
  if (!stageSources[stage]) throw new Error(`Missing stage source for ${stage}`);
}
for (const testCase of config.cases) {
  for (const stage of testCase.expectedStages) {
    if (!config.stages.includes(stage)) throw new Error(`${testCase.id} expects unknown stage ${stage}`);
  }
}

function excerpt(rel) {
  return fs.readFileSync(path.join(repoRoot, rel), "utf8")
    .split("\n")
    .filter((line) => /^#|^Use |^Load |^- |^Owns:|^Out of scope:|^Clarity gate:|^## (Scope|Goal|Rules|Q pattern|Stage Map|Inputs|Delivery)/.test(line))
    .slice(0, 40)
    .join("\n");
}

const stageText = config.stages.map((stage) => {
  const body = stageSources[stage].map((rel) => `# ${rel}\n${excerpt(rel)}`).join("\n");
  return `## ${stage}\n${body}`;
}).join("\n\n");

const prompt = `You are evaluating Grill Me stage routing.
Do not use tools. Use only the stage descriptions below.
For each user request, return the Grill Me stage or support module that should own the next action.
Return JSON matching the schema and preserve every case id.

Stages:
${stageText}

Cases:
${config.cases.map((testCase) => `- ${testCase.id}: ${testCase.prompt}`).join("\n")}
`;

const schemaPath = path.join(evalRoot, "stage-routing-output-schema.json");
const outputPath = path.join(outDir, "output.json");
fs.writeFileSync(path.join(outDir, "prompt.txt"), prompt);

const run = spawnSync("codex", [
  "exec",
  "-m", model,
  "--sandbox", "read-only",
  "--skip-git-repo-check",
  "--ignore-user-config",
  "--color", "never",
  "--output-schema", schemaPath,
  "-o", outputPath,
  prompt
], {
  cwd: repoRoot,
  encoding: "utf8",
  timeout: timeoutMs,
  maxBuffer: 1024 * 1024 * 4,
});

fs.writeFileSync(path.join(outDir, "stdout.txt"), run.stdout || "");
fs.writeFileSync(path.join(outDir, "stderr.txt"), run.stderr || "");
if (run.error) throw run.error;
if (run.status !== 0) {
  console.error(`codex exit status ${run.status}`);
  console.error(run.stderr);
  process.exit(run.status || 1);
}

const parsed = JSON.parse(fs.readFileSync(outputPath, "utf8"));
const actualById = new Map(parsed.cases.map((item) => [item.id, item]));
const results = config.cases.map((testCase) => {
  const actual = actualById.get(testCase.id);
  const actualStages = [...new Set(actual?.stages || [])].sort();
  const expectedStages = [...testCase.expectedStages].sort();
  const pass = expectedStages.every((stage) => actualStages.includes(stage)) &&
    actualStages.every((stage) => expectedStages.includes(stage));
  return {
    id: testCase.id,
    pass,
    expectedStages,
    actualStages,
    reason: actual?.reason || "missing case"
  };
});

const failed = results.filter((result) => !result.pass);
const summary = {
  model,
  outputDir: outDir,
  total: results.length,
  passed: results.length - failed.length,
  failed: failed.length,
  results
};
fs.writeFileSync(path.join(outDir, "summary.json"), `${JSON.stringify(summary, null, 2)}\n`);
console.log(`results: ${outDir}`);
console.log(`passed: ${summary.passed}/${summary.total}`);
for (const result of results) {
  console.log(`${result.pass ? "PASS" : "FAIL"} ${result.id}: expected ${result.expectedStages.join(",")} got ${result.actualStages.join(",") || "(none)"}`);
}
process.exit(failed.length ? 1 : 0);
