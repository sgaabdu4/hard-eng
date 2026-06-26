#!/usr/bin/env node
import fs from "node:fs";
import path from "node:path";
import { spawn } from "node:child_process";

const repoRoot = path.resolve(path.dirname(new URL(import.meta.url).pathname), "..");
const skillNames = process.argv.slice(2);
const model = process.env.SKILL_EVAL_MODEL || "gpt-5.4-mini";
const runRoot = process.env.SKILL_EVAL_ROOT || "/tmp/skill-mini-evals";
const concurrency = Number(process.env.SKILL_EVAL_CONCURRENCY || "2");
const runId = process.env.SKILL_EVAL_RUN_ID || `${Date.now()}-${process.pid}`;

const schema = {
  type: "object",
  additionalProperties: false,
  required: ["skill", "eval_id", "reply", "expectations", "overall_pass", "notes"],
  properties: {
    skill: { type: "string" },
    eval_id: { type: "string" },
    reply: { type: "string" },
    expectations: {
      type: "array",
      items: {
        type: "object",
        additionalProperties: false,
        required: ["text", "passed", "evidence"],
        properties: {
          text: { type: "string" },
          passed: { type: "boolean" },
          evidence: { type: "string" }
        }
      }
    },
    overall_pass: { type: "boolean" },
    notes: { type: "string" }
  }
};

function readJson(file) {
  return JSON.parse(fs.readFileSync(file, "utf8"));
}

function discoverSkills() {
  const skillsDir = path.join(repoRoot, "skills");
  return fs.readdirSync(skillsDir, { withFileTypes: true })
    .filter((dirent) => dirent.isDirectory())
    .map((dirent) => dirent.name)
    .filter((name) => fs.existsSync(path.join(skillsDir, name, "evals", "evals.json")))
    .sort();
}

function copyDir(src, dest) {
  if (fs.existsSync(dest)) {
    throw new Error(`Destination already exists: ${dest}`);
  }
  fs.mkdirSync(path.dirname(dest), { recursive: true });
  fs.cpSync(src, dest, { recursive: true });
}

function writeFixtureFiles(item, targetDir) {
  for (const file of item.files || []) {
    const fullPath = path.resolve(targetDir, file.path);
    if (!fullPath.startsWith(`${targetDir}${path.sep}`)) {
      throw new Error(`Fixture escapes target dir: ${file.path}`);
    }
    fs.mkdirSync(path.dirname(fullPath), { recursive: true });
    fs.writeFileSync(fullPath, file.content);
  }
}

function promptFor(skill, item) {
  return `You are running an automated eval for the local Codex skill at ./skill-under-test.

Rules:
- Read ./skill-under-test/SKILL.md and any referenced files needed for the task.
- Use the skill exactly as written.
- Treat the target project as the current directory, excluding ./skill-under-test.
- Do not edit ./skill-under-test.
- Produce the user-visible response for the eval prompt.
- Then grade your response against each expectation using concrete evidence.
- If the prompt lacks needed repo evidence, state what is unknown instead of inventing details.
- Return only JSON matching the provided output schema.

Skill: ${skill}
Eval id: ${item.id}
Model: ${model}

User prompt:
${item.prompt}

Expected output:
${item.expected_output}

Expectations:
${item.expectations.map((expectation, index) => `${index + 1}. ${expectation}`).join("\n")}
`;
}

function runEval(task, schemaPath, resultDir) {
  return new Promise((resolve) => {
    const evalDir = path.join(runRoot, "runs", runId, `${task.skill}-${task.item.id}`);
    const targetDir = path.join(evalDir, "target");
    const resultPath = path.join(resultDir, `${task.skill}-${task.item.id}.json`);
    const logPath = path.join(resultDir, `${task.skill}-${task.item.id}.log`);
    fs.mkdirSync(targetDir, { recursive: true });
    copyDir(task.skillPath, path.join(targetDir, "skill-under-test"));
    fs.writeFileSync(path.join(targetDir, "README.md"), "Synthetic eval target repo. App code exists only if this eval provides fixtures.\n");
    writeFixtureFiles(task.item, targetDir);

    const args = [
      "exec",
      "-m", model,
      "--sandbox", "workspace-write",
      "--skip-git-repo-check",
      "--ephemeral",
      "-C", targetDir,
      "--output-schema", schemaPath,
      "-o", resultPath,
      promptFor(task.skill, task.item)
    ];

    const child = spawn("codex", args, { cwd: targetDir, stdio: ["ignore", "pipe", "pipe"] });
    let log = "";
    child.stdout.on("data", (chunk) => { log += chunk.toString(); });
    child.stderr.on("data", (chunk) => { log += chunk.toString(); });
    child.on("close", (code) => {
      fs.writeFileSync(logPath, log);
      let parsed;
      try {
        parsed = readJson(resultPath);
      } catch (error) {
        parsed = {
          skill: task.skill,
          eval_id: task.item.id,
          reply: "",
          expectations: [],
          overall_pass: false,
          notes: `result parse failed: ${error.message}`
        };
      }
      resolve({ skill: task.skill, id: task.item.id, code, parsed, resultPath, logPath });
    });
  });
}

const selectedSkills = skillNames.length ? skillNames : discoverSkills();
const tasks = [];
for (const skill of selectedSkills) {
  const skillPath = path.join(repoRoot, "skills", skill);
  const evalPath = path.join(skillPath, "evals", "evals.json");
  if (!fs.existsSync(evalPath)) {
    throw new Error(`Missing evals.json for ${skill}`);
  }
  const evals = readJson(evalPath).evals || [];
  for (const item of evals) {
    tasks.push({ skill, skillPath, item });
  }
}

if (!tasks.length) {
  throw new Error("No eval tasks selected.");
}

const resultDir = path.join(runRoot, "results", runId);
fs.mkdirSync(resultDir, { recursive: true });
const schemaPath = path.join(resultDir, "eval-output-schema.json");
fs.writeFileSync(schemaPath, JSON.stringify(schema, null, 2));

const queue = [...tasks];
const results = [];

async function worker() {
  while (queue.length) {
    const task = queue.shift();
    console.log(`START ${task.skill}/${task.item.id}`);
    const result = await runEval(task, schemaPath, resultDir);
    results.push(result);
    console.log(`DONE ${task.skill}/${task.item.id} code=${result.code} pass=${Boolean(result.parsed.overall_pass)}`);
  }
}

await Promise.all(Array.from({ length: Math.min(concurrency, tasks.length) }, worker));

results.sort((a, b) => `${a.skill}/${a.id}`.localeCompare(`${b.skill}/${b.id}`));
const summary = {
  model,
  runId,
  total: results.length,
  passed: results.filter((result) => result.parsed.overall_pass === true).length,
  failed: results.filter((result) => result.parsed.overall_pass !== true).length,
  resultDir,
  results: results.map((result) => ({
    skill: result.skill,
    id: result.id,
    code: result.code,
    overall_pass: Boolean(result.parsed.overall_pass),
    resultPath: result.resultPath,
    logPath: result.logPath,
    notes: result.parsed.notes || ""
  }))
};
fs.writeFileSync(path.join(resultDir, "summary.json"), JSON.stringify(summary, null, 2));
console.log(JSON.stringify(summary, null, 2));
if (summary.failed) process.exit(2);
