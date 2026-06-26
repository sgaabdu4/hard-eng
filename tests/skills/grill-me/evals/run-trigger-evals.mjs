#!/usr/bin/env node
import fs from "node:fs";
import path from "node:path";
import { spawn } from "node:child_process";

const evalRoot = path.resolve(path.dirname(new URL(import.meta.url).pathname));
const repoRoot = path.resolve(evalRoot, "../../../..");
const skillRoot = path.join(repoRoot, "skills/grill-me");
const evals = JSON.parse(fs.readFileSync(path.join(evalRoot, "trigger-evals.json"), "utf8"));
const skillMd = fs.readFileSync(path.join(skillRoot, "SKILL.md"), "utf8");
const schemaPath = path.join(evalRoot, "trigger-output-schema.json");
const runRoot = process.env.GRILL_ME_EVAL_ROOT || "/tmp/grill-me-eval-run";
const model = process.env.GRILL_ME_EVAL_MODEL || "gpt-5.4-mini";
const resultPath = path.join(runRoot, "results", "trigger-evals.json");
const logPath = path.join(runRoot, "results", "trigger-evals.log");

fs.mkdirSync(path.dirname(resultPath), { recursive: true });

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

const description = readDescription(skillMd);
if (!description) {
  console.error("Could not read SKILL.md description.");
  process.exit(1);
}

const prompt = `You are evaluating whether a Codex skill should trigger.

Skill name: grill-me
Skill description: ${description}

Decision rule:
- predicted_trigger=true when the user is asking for an interview/planning/understanding session that matches the skill description, or when the request asks for a plan, UI flow, mockup, prototype, or final implementation plan where clarifying before building is the intended first step.
- predicted_trigger=false when the user asks for direct execution, a different specialized task, or explicitly says not to interview/ask planning questions.
- Return one result per input, preserving the zero-based index.

Inputs:
${evals.map((item, index) => `${index}. ${item.query}`).join("\n")}
`;

const child = spawn("codex", [
  "exec",
  "-m", model,
  "--sandbox", "workspace-write",
  "--skip-git-repo-check",
  "--ephemeral",
  "-C", repoRoot,
  "--output-schema", schemaPath,
  "-o", resultPath,
  prompt
], { cwd: repoRoot, stdio: ["ignore", "pipe", "pipe"] });

let log = "";
child.stdout.on("data", (chunk) => { log += chunk.toString(); });
child.stderr.on("data", (chunk) => { log += chunk.toString(); });

child.on("close", (code) => {
  fs.writeFileSync(logPath, log);
  let parsed;
  try {
    parsed = JSON.parse(fs.readFileSync(resultPath, "utf8"));
  } catch (error) {
    console.error(`Could not parse trigger output: ${error.message}`);
    process.exit(1);
  }

  const byIndex = new Map(parsed.results.map((item) => [item.index, item]));
  const results = evals.map((item, index) => {
    const actual = byIndex.get(index);
    return {
      index,
      expected: item.should_trigger,
      actual: Boolean(actual?.predicted_trigger),
      pass: Boolean(actual) && Boolean(actual.predicted_trigger) === item.should_trigger,
      reason: actual?.reason || "missing result"
    };
  });
  const failed = results.filter((item) => !item.pass);
  const summary = {
    model,
    total: results.length,
    passed: results.length - failed.length,
    failed: failed.length,
    code,
    failed_results: failed
  };
  fs.writeFileSync(path.join(runRoot, "results", "trigger-summary.json"), `${JSON.stringify(summary, null, 2)}\n`);
  console.log(JSON.stringify(summary, null, 2));
  process.exit(code || (failed.length ? 2 : 0));
});
