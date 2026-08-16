#!/usr/bin/env node

import fs from "node:fs";
import { fromMarkdown } from "mdast-util-from-markdown";
import { parseFragment } from "parse5";
import { isAlias, isMap, isScalar, isSeq, parseDocument } from "yaml";

/** @param {string} message */
function fail(message) {
  throw new Error(message);
}

/** @param {string} path */
function readRegular(path) {
  const descriptor = fs.openSync(path, fs.constants.O_RDONLY | (fs.constants.O_NOFOLLOW ?? 0));
  try {
    const metadata = fs.fstatSync(descriptor);
    if (!metadata.isFile()) fail("source is not a regular no-follow file");
    return fs.readFileSync(descriptor, "utf8");
  } finally {
    fs.closeSync(descriptor);
  }
}

/**
 * @param {any} node
 * @param {string[]} path
 * @param {Record<string, string>} styles
 */
function inspectYaml(node, path, styles) {
  if (node == null) return;
  rejectYamlDecorators(node);
  if (isScalar(node)) {
    styles[path.join(".")] = node.type ?? "PLAIN";
    return;
  }
  inspectYamlCollection(node, path, styles);
}

function rejectYamlDecorators(node) {
  if (isAlias(node) || node.anchor || node.tag) {
    fail("YAML aliases, anchors, and explicit tags are not allowed");
  }
}

function inspectYamlCollection(node, path, styles) {
  if (isMap(node)) {
    inspectYamlMap(node, path, styles);
    return;
  }
  if (isSeq(node)) {
    inspectYamlSequence(node, path, styles);
    return;
  }
  fail("unsupported YAML node");
}

function inspectYamlMap(node, path, styles) {
  for (const pair of node.items) {
    const keyNode = /** @type {any} */ (pair.key);
    if (!isScalar(pair.key) || typeof keyNode.value !== "string") {
      fail("YAML mapping keys must be strings");
    }
    inspectYaml(pair.value, [...path, keyNode.value], styles);
  }
}

function inspectYamlSequence(node, path, styles) {
  for (const [index, item] of node.items.entries()) {
    inspectYaml(item, [...path, String(index)], styles);
  }
}

function yamlDocument(source) {
  const document = parseDocument(source, {
    merge: false,
    schema: "core",
    strict: true,
    uniqueKeys: true,
  });
  if (document.errors.length) fail(document.errors[0].message);
  return document;
}

function yamlMapping(data) {
  if (data == null || Array.isArray(data) || typeof data !== "object") {
    fail("YAML document must be a mapping");
  }
  return data;
}

/** @param {string} source */
function parseYaml(source) {
  const document = yamlDocument(source);
  /** @type {Record<string, string>} */
  const styles = {};
  inspectYaml(document.contents, [], styles);
  return { data: yamlMapping(document.toJS({ maxAliasCount: 0 })), styles };
}

/** @param {string} source */
function frontmatter(source) {
  const lines = source.replaceAll("\r\n", "\n").split("\n");
  if (lines[0] !== "---") fail("SKILL.md missing opening frontmatter delimiter");
  const closing = lines.indexOf("---", 1);
  if (closing < 0) fail("SKILL.md missing closing frontmatter delimiter");
  const result = parseYaml(lines.slice(1, closing).join("\n"));
  const body = lines
    .slice(closing + 1)
    .join("\n")
    .trim();
  if (!body) fail("SKILL.md body is empty");
  return { ...result, body };
}

/** @param {string} value */
function htmlTargets(value) {
  const targets = [];
  /** @type {any[]} */
  const pending = [parseFragment(value)];
  while (pending.length) {
    const node = pending.pop();
    targets.push(...htmlAttributeTargets(node));
    pending.push(...htmlChildren(node));
  }
  return targets;
}

function htmlAttributeTargets(node) {
  const targets = [];
  const linkAttributes = new Set(["href", "src"]);
  for (const attribute of Array.isArray(node.attrs) ? node.attrs : []) {
    if (linkAttributes.has(attribute.name)) targets.push(attribute.value);
  }
  return targets;
}

function htmlChildren(node) {
  return Array.isArray(node.childNodes) ? node.childNodes : [];
}

function collectDirectMarkdownTarget(node, direct) {
  const directTypes = new Set(["link", "image"]);
  if (directTypes.has(node.type)) direct.push(node.url);
}

function collectMarkdownDefinition(node, definitions) {
  if (node.type === "definition") definitions.set(node.identifier.toLowerCase(), node.url);
}

function collectMarkdownReference(node, references) {
  const referenceTypes = new Set(["linkReference", "imageReference"]);
  if (referenceTypes.has(node.type)) references.push(node.identifier.toLowerCase());
}

function collectHtmlTargets(node, direct) {
  if (node.type === "html") direct.push(...htmlTargets(node.value));
}

function resolveMarkdownReferences(direct, definitions, references) {
  for (const identifier of references) {
    const target = definitions.get(identifier);
    if (target !== undefined) direct.push(target);
  }
}

/** @param {string} source */
function markdownTargets(source) {
  const tree = fromMarkdown(source);
  const direct = [];
  const definitions = new Map();
  const references = [];
  /** @type {any[]} */
  const pending = [tree];
  while (pending.length) {
    const node = pending.pop();
    collectDirectMarkdownTarget(node, direct);
    collectMarkdownDefinition(node, definitions);
    collectMarkdownReference(node, references);
    collectHtmlTargets(node, direct);
    if (Array.isArray(node.children)) pending.push(...node.children);
  }
  resolveMarkdownReferences(direct, definitions, references);
  return [...new Set(direct)];
}

function parserArguments() {
  const [mode, path] = process.argv.slice(2);
  if (!path || !["frontmatter", "yaml", "markdown"].includes(mode)) {
    fail("usage: skill-package-parser.mjs <frontmatter|yaml|markdown> <path>");
  }
  return { mode, path };
}

function parseMode(mode, source) {
  const parsers = {
    frontmatter,
    markdown: markdownTargets,
    yaml: parseYaml,
  };
  return parsers[mode](source);
}

function main() {
  const { mode, path } = parserArguments();
  const source = readRegular(path);
  process.stdout.write(`${JSON.stringify(parseMode(mode, source))}\n`);
}

try {
  main();
} catch (error) {
  const message = error instanceof Error ? error.message : "parser failed";
  process.stderr.write(`skill-package-parser: ${message}\n`);
  process.exitCode = 1;
}
