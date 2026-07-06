#!/usr/bin/env node
import fs from "node:fs";
import path from "node:path";
import { spawn } from "node:child_process";

const evalRoot = path.resolve(path.dirname(new URL(import.meta.url).pathname));
const repoRoot = path.resolve(evalRoot, "../../../..");
const config = JSON.parse(fs.readFileSync(path.join(evalRoot, "evals.json"), "utf8"));
const schemaPath = path.join(evalRoot, "eval-output-schema.json");
const model = process.env.HE_PLAN_EVAL_MODEL || config.model || "gpt-5.4-mini";
const codexBin = process.env.HE_PLAN_EVAL_CODEX_BIN || "codex";
const runRoot = process.env.HE_PLAN_EVAL_ROOT || "/tmp/he-plan-eval-run";
const timeoutMs = Number(process.env.HE_PLAN_EVAL_TIMEOUT_MS || "900000");
const runId = process.env.HE_PLAN_EVAL_RUN_ID || `${Date.now()}-${process.pid}`;
const ids = process.argv.slice(2).length ? new Set(process.argv.slice(2).map(Number)) : null;
const selected = ids ? config.evals.filter((item) => ids.has(item.id)) : config.evals;

if (!selected.length) {
  console.error("No matching eval ids.");
  process.exit(1);
}

function copyDir(src, dest) {
  if (fs.existsSync(dest)) throw new Error(`Destination already exists: ${dest}`);
  fs.mkdirSync(path.dirname(dest), { recursive: true });
  fs.cpSync(src, dest, { recursive: true });
}

function writeFixtureFiles(item, targetDir) {
  for (const file of item.files || []) {
    const fullPath = path.resolve(targetDir, file.path);
    if (!fullPath.startsWith(`${targetDir}${path.sep}`)) {
      throw new Error(`Eval ${item.id} fixture escapes target dir: ${file.path}`);
    }
    fs.mkdirSync(path.dirname(fullPath), { recursive: true });
    fs.writeFileSync(fullPath, file.content);
  }
}

function copySkillBundle(targetDir) {
  const skillsDir = path.join(targetDir, "skills");
  for (const name of ["he-plan", "workflow-help", "treehouse", "grill-me"]) {
    copyDir(path.join(repoRoot, "skills", name), path.join(skillsDir, name));
  }
}

function promptFor(item) {
  return `You are running an automated eval for the local Codex Hard Eng skill at ./skills/he-plan.

Rules:
- Read ./skills/he-plan/SKILL.md and referenced files needed for this task.
- Use the skill exactly as written.
- Treat the target project as the current directory, excluding ./skills.
- Do not edit ./skills.
- Do not implement code. Produce only the user-visible response for the eval prompt.
- Then grade that response against each expectation using concrete evidence from your response.
- Return only JSON matching the provided output schema.

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

function runEval(item, resultDir) {
  return new Promise((resolve) => {
    const evalDir = path.join(runRoot, "runs", runId, `eval-${String(item.id).padStart(2, "0")}`);
    const targetDir = path.join(evalDir, "target");
    const resultPath = path.join(resultDir, `eval-${String(item.id).padStart(2, "0")}.json`);
    const logPath = path.join(resultDir, `eval-${String(item.id).padStart(2, "0")}.log`);
    fs.mkdirSync(targetDir, { recursive: true });
    copySkillBundle(targetDir);
    writeFixtureFiles(item, targetDir);

    const args = [
      "exec",
      "-m", model,
      "--sandbox", "workspace-write",
      "--skip-git-repo-check",
      "--ephemeral",
      "-C", targetDir,
      "--output-schema", schemaPath,
      "-o", resultPath,
      promptFor(item)
    ];

    const child = spawn(codexBin, args, { cwd: targetDir, stdio: ["ignore", "pipe", "pipe"] });
    let log = "";
    let timedOut = false;
    const timer = timeoutMs > 0
      ? setTimeout(() => {
        timedOut = true;
        child.kill("SIGTERM");
      }, timeoutMs)
      : null;
    child.stdout.on("data", (chunk) => { log += chunk.toString(); });
    child.stderr.on("data", (chunk) => { log += chunk.toString(); });
    child.on("close", (code) => {
      if (timer) clearTimeout(timer);
      fs.writeFileSync(logPath, log);
      let parsed;
      try {
        parsed = JSON.parse(fs.readFileSync(resultPath, "utf8"));
      } catch (error) {
        parsed = { eval_id: item.id, model, used_skill: false, visible_response: "", files_created: [], expectations: [], overall_pass: false, notes: `parse/error: ${error.message}` };
      }
      if (timedOut) parsed = { ...parsed, overall_pass: false, notes: `timed out after ${timeoutMs}ms; ${parsed.notes || ""}` };
      const passed = code === 0 && parsed.overall_pass === true;
      if (code !== 0 && parsed.overall_pass === true) {
        parsed = { ...parsed, notes: `child exited ${code}; ${parsed.notes || ""}` };
      }
      resolve({ id: item.id, code, passed, parsed, resultPath, logPath });
    });
  });
}

const resultDir = path.join(runRoot, "results", runId);
fs.mkdirSync(resultDir, { recursive: true });
const results = [];
for (const item of selected) {
  console.log(`START eval-${item.id}`);
  const result = await runEval(item, resultDir);
  results.push(result);
  console.log(`DONE eval-${item.id} code=${result.code} pass=${result.passed}`);
}

const summary = {
  model,
  runId,
  total: results.length,
  passed: results.filter((result) => result.passed).length,
  failed: results.filter((result) => !result.passed).length,
  resultDir,
  results: results.map((result) => ({
    id: result.id,
    code: result.code,
    overall_pass: result.passed,
    resultPath: result.resultPath,
    logPath: result.logPath,
    notes: result.parsed.notes || ""
  }))
};

fs.writeFileSync(path.join(resultDir, "summary.json"), JSON.stringify(summary, null, 2));
console.log(JSON.stringify(summary, null, 2));
if (summary.failed) process.exit(2);
