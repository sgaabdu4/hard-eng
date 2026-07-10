#!/usr/bin/env node
import fs from "node:fs";
import path from "node:path";

const evalRoot = path.resolve(path.dirname(new URL(import.meta.url).pathname));
const repoRoot = path.resolve(evalRoot, "../../../..");
const skillRoot = path.join(repoRoot, "skills/grill-me");
const taskEvalFiles = ["evals.json", "session-regression-evals.json"];
const triggersPath = path.join(evalRoot, "trigger-evals.json");
const stageRoutingPath = path.join(evalRoot, "stage-routing-evals.json");
const stageRoutingRunnerPath = path.join(evalRoot, "run-stage-routing-evals.mjs");
const evalGroups = taskEvalFiles.map((file) => ({
  file,
  data: JSON.parse(fs.readFileSync(path.join(evalRoot, file), "utf8"))
}));
const taskEvals = evalGroups.flatMap(({ file, data }) =>
  (data.evals || []).map((item) => ({ ...item, __file: file }))
);
const triggers = JSON.parse(fs.readFileSync(triggersPath, "utf8"));
const stageRouting = JSON.parse(fs.readFileSync(stageRoutingPath, "utf8"));
const stageRoutingRunner = fs.readFileSync(stageRoutingRunnerPath, "utf8");

const errors = [];
const ids = new Set();
const prompts = new Set();

function requireText(value, label) {
  if (typeof value !== "string" || !value.trim()) errors.push(`${label} missing text`);
}

for (const group of evalGroups) {
  if (group.data.skill_name !== "grill-me") errors.push(`${group.file} skill_name must be grill-me`);
  if (!Array.isArray(group.data.evals)) errors.push(`${group.file} evals must be array`);
}
if (taskEvals.length < 30) {
  errors.push("expected at least 30 task evals");
}

for (const item of taskEvals) {
  if (!Number.isInteger(item.id)) errors.push(`eval id ${item.id} is not integer`);
  if (ids.has(item.id)) errors.push(`duplicate eval id ${item.id}`);
  ids.add(item.id);
  requireText(item.prompt, `eval ${item.id} prompt`);
  requireText(item.expected_output, `eval ${item.id} expected_output`);
  if (prompts.has(item.prompt)) errors.push(`duplicate prompt at eval ${item.id}`);
  prompts.add(item.prompt);
  if (!Array.isArray(item.files)) errors.push(`eval ${item.id} files must be array`);
  if (!Array.isArray(item.expectations) || item.expectations.length < 4) {
    errors.push(`eval ${item.id} in ${item.__file} needs at least 4 expectations`);
  }
}

const suiteText = JSON.stringify(taskEvals).toLowerCase();
const requiredCoverage = [
  ["greenfield", 2],
  ["brownfield", 4],
  ["simple-feature", 1],
  ["understand", 4],
  ["codebase", 3],
  ["compaction", 2],
  ["session_state.md", 8],
  ["visual", 6],
  ["prototype", 8],
  ["backend", 7],
  ["verification", 8],
  ["human review", 2],
  ["rollback", 2],
  ["telemetry", 2],
  ["ui-review-receipt", 4],
  ["storybook", 3],
  ["widgetbook", 2],
  ["simulator", 2],
  ["selected option", 2],
  ["rejected option", 2]
];

for (const [term, min] of requiredCoverage) {
  const count = suiteText.split(term).length - 1;
  if (count < min) errors.push(`coverage term "${term}" count ${count} < ${min}`);
}

if (!Array.isArray(triggers) || triggers.length < 20) {
  errors.push("expected at least 20 trigger evals");
}
const should = triggers.filter((item) => item.should_trigger === true).length;
const shouldNot = triggers.filter((item) => item.should_trigger === false).length;
if (should < 8) errors.push("expected at least 8 should-trigger queries");
if (shouldNot < 8) errors.push("expected at least 8 should-not-trigger queries");
for (const [index, item] of triggers.entries()) {
  requireText(item.query, `trigger ${index} query`);
  if (typeof item.should_trigger !== "boolean") {
    errors.push(`trigger ${index} should_trigger must be boolean`);
  }
}

const requiredStages = [
  "intake",
  "product",
  "ui-flow",
  "visual-design",
  "prototype-tech",
  "prototype",
  "backend-tech",
  "vertical-slices",
  "final-plan",
  "session-state",
  "domain-docs",
  "questions"
];
if (stageRouting.model !== "gpt-5.6-luna") {
  errors.push("stage-routing-evals.json model must be gpt-5.6-luna");
}
for (const stage of requiredStages) {
  if (!stageRouting.stages?.includes(stage)) {
    errors.push(`stage-routing-evals.json missing stage ${stage}`);
  }
  const hasCase = (stageRouting.cases || []).some((item) =>
    Array.isArray(item.expectedStages) && item.expectedStages.includes(stage)
  );
  if (!hasCase) errors.push(`stage-routing-evals.json missing case for ${stage}`);
}
if ((stageRouting.cases || []).length < requiredStages.length) {
  errors.push("stage-routing-evals.json needs at least one case per stage");
}
if (!stageRoutingRunner.includes("skills/grill-me/references/start-routing.md")) {
  errors.push("run-stage-routing-evals.mjs must include start-routing.md in stage source context");
}

const loaded = [
  path.join(skillRoot, "SKILL.md"),
  ...fs.readdirSync(path.join(skillRoot, "modules"))
    .filter((name) => name.endsWith(".md"))
    .sort()
    .map((name) => path.join(skillRoot, "modules", name))
];

let loadedChars = 0;
for (const file of loaded) {
  const text = fs.readFileSync(file, "utf8");
  loadedChars += text.length;
  if (/[^\x00-\x7F]/.test(text)) errors.push(`non-ascii in ${path.relative(skillRoot, file)}`);
}
if (loadedChars > 64000) {
  errors.push(`loaded skill chars ${loadedChars} exceeds 64000 budget`);
}

const questionsText = fs.readFileSync(path.join(skillRoot, "modules/questions.md"), "utf8");
const normalizedQuestionsText = questionsText.replace(/\s+/g, " ");
for (const required of [
  "request_user_input",
  "Default to the markdown",
  "Do not use `request_user_input` for `grill-me` interview prompts",
  "rich context belongs in the markdown block",
  "only for simple, low-risk choices",
  "2-3 exclusive options",
  "autoResolutionMs",
  "the tool `question` string is only the short question",
  "Descriptions are optional and non-critical",
  "built-in UI may hide them"
]) {
  if (!normalizedQuestionsText.includes(required)) {
    errors.push(`questions.md missing request_user_input contract: ${required}`);
  }
}

for (const required of [
  "Question-premise preflight",
  "Run immediately before every visible question",
  "Proven",
  "Unresolved",
  "Unsupported",
  "exact user answer or accepted UI review receipt",
  "state says no question, emit no question"
]) {
  if (!normalizedQuestionsText.includes(required)) {
    errors.push(`questions.md missing question-premise contract: ${required}`);
  }
}

const uiFlowText = fs.readFileSync(path.join(skillRoot, "modules/ui-flow.md"), "utf8").replace(/\s+/g, " ");
for (const required of [
  "fallback renders a proven candidate",
  "missing feature does not prove a new parent surface",
  "open the verified review surface",
  "screenshot for every layout option"
]) {
  if (!uiFlowText.includes(required)) errors.push(`ui-flow.md missing parent-surface contract: ${required}`);
}

if (errors.length) {
  console.error("FAIL");
  for (const error of errors) console.error(`- ${error}`);
  process.exit(1);
}

console.log("PASS");
console.log(`task_evals=${taskEvals.length} files=${taskEvalFiles.length}`);
console.log(`trigger_evals=${triggers.length} should=${should} should_not=${shouldNot}`);
console.log(`loaded_chars=${loadedChars}`);
