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
  if (isAlias(node) || node.anchor || node.tag) {
    fail("YAML aliases, anchors, and explicit tags are not allowed");
  }
  if (isScalar(node)) {
    styles[path.join(".")] = node.type ?? "PLAIN";
    return;
  }
  if (isMap(node)) {
    for (const pair of node.items) {
      const keyNode = /** @type {any} */ (pair.key);
      if (!isScalar(pair.key) || typeof keyNode.value !== "string") {
        fail("YAML mapping keys must be strings");
      }
      inspectYaml(pair.value, [...path, keyNode.value], styles);
    }
    return;
  }
  if (isSeq(node)) {
    for (const [index, item] of node.items.entries()) {
      inspectYaml(item, [...path, String(index)], styles);
    }
    return;
  }
  fail("unsupported YAML node");
}

/** @param {string} source */
function parseYaml(source) {
  const document = parseDocument(source, {
    merge: false,
    schema: "core",
    strict: true,
    uniqueKeys: true,
  });
  if (document.errors.length) fail(document.errors[0].message);
  /** @type {Record<string, string>} */
  const styles = {};
  inspectYaml(document.contents, [], styles);
  const data = document.toJS({ maxAliasCount: 0 });
  if (data == null || Array.isArray(data) || typeof data !== "object") {
    fail("YAML document must be a mapping");
  }
  return { data, styles };
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
    if (Array.isArray(node.attrs)) {
      for (const attribute of node.attrs) {
        if (attribute.name === "href" || attribute.name === "src") {
          targets.push(attribute.value);
        }
      }
    }
    if (Array.isArray(node.childNodes)) pending.push(...node.childNodes);
  }
  return targets;
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
    if (node.type === "link" || node.type === "image") direct.push(node.url);
    if (node.type === "definition") definitions.set(node.identifier.toLowerCase(), node.url);
    if (node.type === "linkReference" || node.type === "imageReference") {
      references.push(node.identifier.toLowerCase());
    }
    if (node.type === "html") direct.push(...htmlTargets(node.value));
    if (Array.isArray(node.children)) pending.push(...node.children);
  }
  for (const identifier of references) {
    const target = definitions.get(identifier);
    if (target !== undefined) direct.push(target);
  }
  return [...new Set(direct)];
}

function main() {
  const [mode, path] = process.argv.slice(2);
  if (!path || !["frontmatter", "yaml", "markdown"].includes(mode)) {
    fail("usage: skill-package-parser.mjs <frontmatter|yaml|markdown> <path>");
  }
  const source = readRegular(path);
  const result =
    mode === "frontmatter"
      ? frontmatter(source)
      : mode === "yaml"
        ? parseYaml(source)
        : markdownTargets(source);
  process.stdout.write(`${JSON.stringify(result)}\n`);
}

try {
  main();
} catch (error) {
  const message = error instanceof Error ? error.message : "parser failed";
  process.stderr.write(`skill-package-parser: ${message}\n`);
  process.exitCode = 1;
}
