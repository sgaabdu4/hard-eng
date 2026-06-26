#!/usr/bin/env node
import fs from "node:fs";
import path from "node:path";

const repoRoot = path.resolve(new URL("../../..", import.meta.url).pathname);
const skillPath = path.join(repoRoot, "skills/treehouse/SKILL.md");
const evalsPath = path.join(repoRoot, "tests/skills/treehouse/evals/trigger-evals.json");
const text = fs.readFileSync(skillPath, "utf8");
const evals = JSON.parse(fs.readFileSync(evalsPath, "utf8"));
const errors = [];

function has(needle) {
  if (!text.includes(needle)) errors.push(`missing ${needle}`);
}

if (!text.startsWith("---\nname: treehouse\n")) errors.push("bad frontmatter name");
has("tree house");
has("treehouse <name>");
has("treehouse status");
has("treehouse get --lease");
has("ensure-worktree-ready.sh");
has("treehouse return <path>");
has("return --force");
has("destroy");
has("prune --yes");
has("grill-me");
has("scripts/setup.sh");

if (/[^\x00-\x7F]/.test(text)) errors.push("non-ascii in skill");
if (text.split("\n").length > 80) errors.push("skill too long");
if (!Array.isArray(evals) || evals.length !== 8) errors.push("expected 8 trigger evals");
if (evals.filter((item) => item.should_trigger === true).length < 4) errors.push("not enough positive evals");
if (evals.filter((item) => item.should_trigger === false).length < 4) errors.push("not enough negative evals");

if (errors.length) {
  console.error(errors.join("\n"));
  process.exit(1);
}

console.log("treehouse-skill: pass");
