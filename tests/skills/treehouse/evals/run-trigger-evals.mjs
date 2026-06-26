#!/usr/bin/env node
import fs from "node:fs";
import path from "node:path";
import { spawn } from "node:child_process";

const evalRoot = path.resolve(path.dirname(new URL(import.meta.url).pathname));
const repoRoot = path.resolve(evalRoot, "../../../..");
const skillRoot = path.join(repoRoot, "skills/treehouse");
const evals = JSON.parse(fs.readFileSync(path.join(evalRoot, "trigger-evals.json"), "utf8"));
const skillMd = fs.readFileSync(path.join(skillRoot, "SKILL.md"), "utf8");
const schemaPath = path.join(evalRoot, "trigger-output-schema.json");
const runRoot = process.env.TREEHOUSE_EVAL_ROOT || "/tmp/treehouse-skill-eval-run";
const model = process.env.TREEHOUSE_EVAL_MODEL || "gpt-5.4-mini";
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
if (!description) throw new Error("Could not read SKILL.md description");

const prompt = `You are evaluating whether a Codex skill should trigger.

Skill name: treehouse
Skill description: ${description}

Decision rule:
- predicted_trigger=true for Treehouse CLI/worktree-pool intent, including "tree house" with a space.
- predicted_trigger=false for unrelated work, plain grill-me requests, filesystem trees, or literal backyard treehouse design.
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
  const parsed = JSON.parse(fs.readFileSync(resultPath, "utf8"));
  const byIndex = new Map(parsed.results.map((item) => [item.index, item]));
  const results = evals.map((item, index) => {
    const actual = byIndex.get(index);
    const predicted = Boolean(actual?.predicted_trigger);
    return {
      index,
      expected: item.should_trigger,
      actual: predicted,
      pass: Boolean(actual) && predicted === item.should_trigger,
      reason: actual?.reason || "missing result"
    };
  });
  const failed = results.filter((item) => !item.pass);
  const summary = { model, total: results.length, passed: results.length - failed.length, failed: failed.length, code, failed_results: failed };
  fs.writeFileSync(path.join(runRoot, "results", "trigger-summary.json"), `${JSON.stringify(summary, null, 2)}\n`);
  console.log(JSON.stringify(summary, null, 2));
  process.exit(code || (failed.length ? 2 : 0));
});
