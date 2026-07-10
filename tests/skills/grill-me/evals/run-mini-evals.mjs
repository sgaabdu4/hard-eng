#!/usr/bin/env node
import fs from "node:fs";
import path from "node:path";
import { spawn } from "node:child_process";
import { DEFAULT_EVAL_MODEL } from "../../../../scripts/eval-model.mjs";

const skillRoot = path.resolve(path.dirname(new URL(import.meta.url).pathname), "..");
const evalFiles = ["evals.json", "session-regression-evals.json"];
const evals = evalFiles.flatMap((file) => {
  const fullPath = path.join(skillRoot, "evals", file);
  if (!fs.existsSync(fullPath)) return [];
  return JSON.parse(fs.readFileSync(fullPath, "utf8")).evals;
});
const schemaPath = path.join(skillRoot, "evals", "eval-output-schema.json");
const runRoot = process.env.GRILL_ME_EVAL_ROOT || "/tmp/grill-me-eval-run";
const model = process.env.GRILL_ME_EVAL_MODEL || DEFAULT_EVAL_MODEL;
const concurrency = Number(process.env.GRILL_ME_EVAL_CONCURRENCY || "3");
const timeoutMs = Number(process.env.GRILL_ME_EVAL_TIMEOUT_MS || "3600000");
const runId = process.env.GRILL_ME_EVAL_RUN_ID || `${Date.now()}-${process.pid}`;
const idsArg = process.argv.slice(2);
const ids = idsArg.length ? new Set(idsArg.map(Number)) : null;
const selected = ids ? evals.filter((item) => ids.has(item.id)) : evals;

if (!selected.length) {
  console.error("No matching eval ids.");
  process.exit(1);
}

const skillCopy = path.join(runRoot, "skill-under-test");
if (!fs.existsSync(skillCopy)) {
  fs.mkdirSync(path.dirname(skillCopy), { recursive: true });
  fs.cpSync(path.join(skillRoot, "..", "..", "..", "skills", "grill-me"), skillCopy, { recursive: true });
}

const resultDir = path.join(runRoot, "results", runId);
fs.mkdirSync(resultDir, { recursive: true });

function copyDir(src, dest) {
  if (fs.existsSync(dest)) {
    throw new Error(`Destination already exists: ${dest}`);
  }
  fs.mkdirSync(path.dirname(dest), { recursive: true });
  fs.cpSync(src, dest, { recursive: true });
}

function writeFixtureFiles(item, targetDir) {
  for (const file of item.files || []) {
    if (!file.path || typeof file.content !== "string") {
      throw new Error(`Eval ${item.id} has an invalid file fixture.`);
    }
    const fullPath = path.resolve(targetDir, file.path);
    if (!fullPath.startsWith(`${targetDir}${path.sep}`)) {
      throw new Error(`Eval ${item.id} file fixture escapes target dir: ${file.path}`);
    }
    fs.mkdirSync(path.dirname(fullPath), { recursive: true });
    fs.writeFileSync(fullPath, file.content);
  }
}

function promptFor(item) {
  return `You are running an automated eval for the local Codex skill at ./skill-under-test.

Rules:
- Read ./skill-under-test/SKILL.md and any relevant modules before answering.
- Use the skill exactly as written.
- Treat the target project as the current directory, excluding ./skill-under-test.
- Do not edit ./skill-under-test.
- You may create docs/planning/... in the current directory if the skill requires it.
- Produce the user-visible grill-me response for the eval prompt.
- Then grade the result against each expectation using concrete evidence from your output/files.
- If code/docs would normally be inspected but no app fixture exists, say evidence is unknown rather than inventing it.
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

function runEval(item) {
  return new Promise((resolve) => {
    const evalDir = path.join(runRoot, "runs", runId, `eval-${String(item.id).padStart(2, "0")}`);
    const targetDir = path.join(evalDir, "target");
    const resultPath = path.join(resultDir, `eval-${String(item.id).padStart(2, "0")}.json`);
    const logPath = path.join(resultDir, `eval-${String(item.id).padStart(2, "0")}.log`);
    if (fs.existsSync(evalDir)) {
      throw new Error(`Eval directory already exists: ${evalDir}`);
    }
    fs.mkdirSync(targetDir, { recursive: true });
    copyDir(skillCopy, path.join(targetDir, "skill-under-test"));
    fs.writeFileSync(path.join(targetDir, "README.md"), "Synthetic eval target repo. App code exists only if this eval prompt provides it.\n");
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

    const child = spawn("codex", args, { cwd: targetDir, stdio: ["ignore", "pipe", "pipe"] });
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
      let parsed = null;
      try {
        parsed = JSON.parse(fs.readFileSync(resultPath, "utf8"));
      } catch (error) {
        parsed = { eval_id: item.id, overall_pass: false, notes: `parse/error: ${error.message}` };
      }
      if (timedOut) {
        parsed = {
          ...parsed,
          overall_pass: false,
          notes: `timed out after ${timeoutMs}ms${parsed?.notes ? `; ${parsed.notes}` : ""}`
        };
      }
      resolve({ id: item.id, code, parsed, resultPath, logPath });
    });
  });
}

const queue = [...selected];
const results = [];

async function worker() {
  while (queue.length) {
    const item = queue.shift();
    console.log(`START eval-${item.id}`);
    const result = await runEval(item);
    results.push(result);
    console.log(`DONE eval-${item.id} code=${result.code} pass=${Boolean(result.parsed?.overall_pass)}`);
  }
}

await Promise.all(Array.from({ length: Math.min(concurrency, selected.length) }, worker));

results.sort((a, b) => a.id - b.id);
const passed = results.filter((result) => result.parsed?.overall_pass === true).length;
const summary = {
  model,
  runId,
  total: results.length,
  passed,
  failed: results.length - passed,
  results: results.map((result) => ({
    id: result.id,
    code: result.code,
    overall_pass: Boolean(result.parsed?.overall_pass),
    resultPath: result.resultPath,
    logPath: result.logPath,
    notes: result.parsed?.notes || ""
  }))
};
fs.writeFileSync(path.join(resultDir, "summary.json"), JSON.stringify(summary, null, 2));
console.log(JSON.stringify(summary, null, 2));
if (summary.failed) process.exit(2);
