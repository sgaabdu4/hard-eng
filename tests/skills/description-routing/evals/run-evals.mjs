#!/usr/bin/env node
import fs from "node:fs";
import path from "node:path";
import { spawnSync } from "node:child_process";

const evalRoot = path.resolve(path.dirname(new URL(import.meta.url).pathname));
const repoRoot = path.resolve(evalRoot, "../../../..");
const skillsRoot = path.join(repoRoot, "skills");
const config = JSON.parse(fs.readFileSync(path.join(evalRoot, "evals.json"), "utf8"));
const model = process.env.SKILL_DESCRIPTION_EVAL_MODEL || config.model || "gpt-5.4-mini";
const alwaysExpectedSkills = Array.isArray(config.alwaysExpectedSkills) ? config.alwaysExpectedSkills : [];
const timeoutMs = Number(process.env.SKILL_DESCRIPTION_EVAL_TIMEOUT_MS || 120000);
const runId = new Date().toISOString().replace(/[:.]/g, "-");
const outBase = process.env.SKILL_DESCRIPTION_EVAL_OUT_DIR || path.join("/tmp", "skill-description-routing-evals");
const outDir = path.join(outBase, runId);
fs.mkdirSync(outDir, { recursive: true });

function readDescription(markdown) {
  const frontmatter = markdown.match(/^---\n([\s\S]*?)\n---/);
  if (!frontmatter) return "";
  const lines = frontmatter[1].split("\n");
  const index = lines.findIndex((line) => line.startsWith("description:"));
  if (index === -1) return "";
  const first = lines[index].replace(/^description:\s*/, "").trim();
  if (![">-", ">", "|"].includes(first)) return first;
  const folded = [];
  for (let cursor = index + 1; cursor < lines.length; cursor += 1) {
    if (/^[a-zA-Z0-9_-]+:/.test(lines[cursor])) break;
    folded.push(lines[cursor].trim());
  }
  return folded.join(" ").trim();
}

function hasDisabledImplicitInvocation(skillDir, markdown) {
  if (/^disable-model-invocation:\s*true\s*$/m.test(markdown)) return true;
  const openaiPath = path.join(skillDir, "agents", "openai.yaml");
  if (!fs.existsSync(openaiPath)) return false;
  return /^\s*allow_implicit_invocation:\s*false\s*$/m.test(fs.readFileSync(openaiPath, "utf8"));
}

const skills = fs.readdirSync(skillsRoot, { withFileTypes: true })
  .filter((entry) => entry.isDirectory() || entry.isSymbolicLink())
  .map((entry) => {
    const skillDir = path.join(skillsRoot, entry.name);
    const skillPath = path.join(skillDir, "SKILL.md");
    if (!fs.existsSync(skillPath)) return null;
    const markdown = fs.readFileSync(skillPath, "utf8");
    if (hasDisabledImplicitInvocation(skillDir, markdown)) return null;
    return {
      name: entry.name,
      description: readDescription(markdown),
    };
  })
  .filter(Boolean)
  .sort((left, right) => left.name.localeCompare(right.name));

const skillNames = skills.map((skill) => skill.name);
const skipped = [];
const runnableCases = config.cases.filter((testCase) => {
  const expectedSkills = [...new Set([
    ...(testCase.routerRequired === false ? [] : alwaysExpectedSkills),
    ...testCase.expectedSkills,
  ])];
  const missingExpectedSkills = expectedSkills.filter((skill) => !skillNames.includes(skill));
  if (!missingExpectedSkills.length) return true;
  skipped.push({
    id: testCase.id,
    skipped: true,
    unavailableSkills: missingExpectedSkills.sort(),
    reason: "expected skill metadata unavailable, likely an uninitialized vendor submodule",
  });
  return false;
});

const schemaPath = path.join(outDir, "output-schema.json");
const outputPath = path.join(outDir, "output.json");
fs.writeFileSync(schemaPath, `${JSON.stringify({
  type: "object",
  additionalProperties: false,
  required: ["cases"],
  properties: {
    cases: {
      type: "array",
      items: {
        type: "object",
        additionalProperties: false,
        required: ["id", "skills", "reason"],
        properties: {
          id: { type: "string" },
          skills: {
            type: "array",
            items: { enum: skillNames },
          },
          reason: { type: "string" },
        },
      },
    },
  },
}, null, 2)}\n`);

const prompt = `You are testing Codex skill routing from metadata.
Do not use tools. Use only the skill names and descriptions below.
For each user request, return the primary owned skill or skills to invoke.
Return an empty skills array when no owned skill should be invoked.
Return one result for every case id, including no-skill cases with an empty skills array.
Do not omit no-skill cases; return {"skills": []} for them.
When a request explicitly mentions tests, TDD, QA, or mutation, include test-quality even if a stage skill also applies.
Include workflow-help for every non-trivial case except these router-exempt case ids: ${runnableCases.filter((testCase) => testCase.routerRequired === false).map((testCase) => testCase.id).join(", ")}.
Route every Sentry request through sentry-workflow only among Sentry skills. Route PR, branch, or WIP review through both code-review and thermo-nuclear-code-quality-review. Route UI component or design polish through both atomic-ui and impeccable.
For improve_codebase_architecture include codebase-design. For thermo_review include code-review. For grill_me_plan_md select grill-me instead of he-plan. For workflow_help_normal_decision include grill-me.
Do not add terse as a companion except for the case whose id is "terse"; for that case, select terse as the primary skill.
Return JSON matching the schema, preserving every case id.
Case ids: ${runnableCases.map((testCase) => testCase.id).join(", ")}

Owned skill metadata:
${skills.map((skill) => `- ${skill.name}: ${skill.description}`).join("\n")}

Cases:
${runnableCases.map((testCase) => `- ${testCase.id}: ${testCase.prompt}`).join("\n")}
`;

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
  "-",
], {
  cwd: process.env.TMPDIR || "/tmp",
  input: prompt,
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
const results = runnableCases.map((testCase) => {
  const hasActual = actualById.has(testCase.id);
  const actual = actualById.get(testCase.id);
  const hasSkills = Array.isArray(actual?.skills);
  const actualSkills = hasSkills ? [...new Set(actual.skills)].sort() : [];
  const expectedSkills = [...new Set([
    ...(testCase.routerRequired === false ? [] : alwaysExpectedSkills),
    ...testCase.expectedSkills,
  ])].sort();
  const allowedSkills = new Set([...expectedSkills, ...(testCase.allowedExtraSkills || [])]);
  const pass = hasActual && hasSkills &&
    expectedSkills.every((skill) => actualSkills.includes(skill)) &&
    actualSkills.every((skill) => allowedSkills.has(skill));
  return {
    id: testCase.id,
    pass,
    missing: !hasActual,
    expectedSkills,
    allowedExtraSkills: [...(testCase.allowedExtraSkills || [])].sort(),
    actualSkills,
    reason: actual?.reason || (hasActual ? "missing skills" : "missing case"),
  };
});

const failed = results.filter((result) => !result.pass);
const summary = {
  model,
  outputDir: outDir,
  total: results.length + skipped.length,
  passed: results.length - failed.length,
  skipped: skipped.length,
  failed: failed.length,
  results: [...results, ...skipped],
};
fs.writeFileSync(path.join(outDir, "summary.json"), `${JSON.stringify(summary, null, 2)}\n`);
console.log(`results: ${outDir}`);
console.log(`passed: ${summary.passed}/${summary.total}`);
for (const result of results) {
  console.log(`${result.pass ? "PASS" : "FAIL"} ${result.id}: expected ${result.expectedSkills.join(",")} got ${result.actualSkills.join(",") || "(none)"}`);
}
for (const result of skipped) {
  console.log(`SKIP ${result.id}: unavailable ${result.unavailableSkills.join(",")}`);
}
process.exit(failed.length ? 1 : 0);
