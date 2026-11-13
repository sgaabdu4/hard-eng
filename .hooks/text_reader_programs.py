"""The reader programs that run beside the parser of each screen language, as text."""

JS_READER = r'''import { readFileSync } from "node:fs";
import { parseSync } from "oxc-parser";

const request = JSON.parse(readFileSync(0, "utf8"));
const INLINE = new Set(request.inline);
const TEXT_PROPS = new Set(request.text_props);
const SKIP = new Set(request.skip);
const STORED = new Set(request.stored);
const TAP_NAMES = new Set(request.tap_names);
const TAP_ATTRS = new Set(request.tap_attrs);
const USER = request.user;
const SLOT = { x: 1 };
const NO_CLAMP = 1000;
const LETTER = /[\p{L}\p{N}]/u;
const CLAMP_STYLES = new Set(["WebkitLineClamp", "lineClamp"]);
const WRAPPERS = new Set(["ParenthesizedExpression", "TSAsExpression", "TSSatisfiesExpression", "TSNonNullExpression", "ChainExpression", "TSTypeAssertion"]);

let starts = [0];
let blocks = [];

function lineOf(offset) {
  let lo = 0;
  let hi = starts.length - 1;
  while (lo < hi) {
    const mid = (lo + hi + 1) >> 1;
    if (starts[mid] <= offset) lo = mid;
    else hi = mid - 1;
  }
  return lo + 1;
}

function span(from, to) {
  const out = [];
  for (let line = lineOf(from); line <= lineOf(Math.max(from, to - 1)); line++) out.push(line);
  return out;
}

function unwrap(node) {
  while (node && WRAPPERS.has(node.type)) node = node.expression;
  return node;
}

function elementName(node) {
  const name = node.openingElement ? node.openingElement.name : null;
  if (!name) return "";
  if (name.type === "JSXIdentifier") return name.name;
  if (name.type === "JSXMemberExpression") return name.property.name;
  return "";
}

function attrName(attr) {
  if (attr.type !== "JSXAttribute") return "";
  return attr.name.type === "JSXIdentifier" ? attr.name.name : "";
}

function keyName(property) {
  if (property.computed) return "";
  const key = property.key;
  if (key.type === "Identifier") return key.name;
  if (key.type === "Literal" && typeof key.value === "string") return key.value;
  return "";
}

function stringOf(node) {
  node = unwrap(node);
  if (!node) return null;
  if (node.type === "Literal" && typeof node.value === "string") return [node.value];
  if (node.type === "TemplateLiteral") {
    const parts = [];
    node.quasis.forEach((quasi, index) => {
      parts.push(quasi.value.cooked ?? quasi.value.raw);
      if (index < node.expressions.length) parts.push(SLOT);
    });
    return parts;
  }
  if (node.type === "ConditionalExpression") {
    const a = stringOf(node.consequent);
    const b = stringOf(node.alternate);
    if (a || b) return [{ alt: [a ?? [SLOT], b ?? [SLOT]] }];
  }
  if (node.type === "LogicalExpression") {
    const right = stringOf(node.right);
    if (!right) return null;
    return node.operator === "&&" ? right : [{ alt: [[SLOT], right] }];
  }
  if (node.type === "BinaryExpression" && node.operator === "+") {
    const left = stringOf(node.left);
    const right = stringOf(node.right);
    if (left || right) return [...(left ?? [SLOT]), ...(right ?? [SLOT])];
  }
  return null;
}

function storedField(node) {
  node = unwrap(node);
  if (!node) return "";
  if (node.type === "MemberExpression") {
    if (!node.computed && node.property.type === "Identifier" && STORED.has(node.property.name)) return node.property.name;
    return "";
  }
  if (node.type === "CallExpression") return node.callee.type === "MemberExpression" ? storedField(node.callee.object) : "";
  if (node.type === "LogicalExpression") return storedField(node.left) || storedField(node.right);
  if (node.type === "ConditionalExpression") return storedField(node.consequent) || storedField(node.alternate);
  return "";
}

function holdsJsx(node) {
  let found = false;
  walkAll(node, (child) => {
    if (child.type === "JSXElement" || child.type === "JSXFragment") found = true;
    return !found;
  });
  return found;
}

function children(node) {
  const out = [];
  for (const key in node) {
    if (key === "parent") continue;
    const value = node[key];
    if (Array.isArray(value)) {
      for (const item of value) if (item && typeof item.type === "string") out.push(item);
    } else if (value && typeof value.type === "string") out.push(value);
  }
  return out;
}

function walkAll(node, visit) {
  if (!node || typeof node.type !== "string") return;
  if (visit(node) === false) return;
  for (const child of children(node)) walkAll(child, visit);
}

function cleanText(raw) {
  const lines = raw.split(/\r\n|\n|\r/);
  let out = "";
  lines.forEach((line, index) => {
    let text = line.replace(/\t/g, " ");
    if (index !== 0) text = text.replace(/^ +/, "");
    if (index !== lines.length - 1) text = text.replace(/ +$/, "");
    if (text) out += (out && index !== 0 ? " " : "") + text;
  });
  return out;
}

function hasText(parts) {
  return parts.some((part) => {
    if (typeof part === "string") return LETTER.test(part);
    if (part.alt) return part.alt.some(hasText);
    return Boolean(part.field);
  });
}

function stringLiterals(node, out) {
  walkAll(node, (child) => {
    if (child.type === "Literal" && typeof child.value === "string") out.push(child.value);
    if (child.type === "TemplateElement") out.push(child.value.cooked ?? child.value.raw);
    return true;
  });
  return out;
}

function classClamp(tokens) {
  let best = null;
  for (const token of tokens) {
    const name = token.slice(token.lastIndexOf(":") + 1);
    let value = null;
    let found = /^line-clamp-(\d+)$/.exec(name) || /^line-clamp-\[(\d+)\]$/.exec(name);
    if (found) value = Number(found[1]);
    else if (name === "truncate") value = 1;
    else if (name === "line-clamp-none") value = NO_CLAMP;
    if (value !== null && (best === null || value > best)) best = value;
  }
  return best;
}

function styleClamp(expression) {
  let best = null;
  walkAll(expression, (child) => {
    if (child.type === "Property" && CLAMP_STYLES.has(keyName(child))) {
      const value = unwrap(child.value);
      if (value && value.type === "Literal") {
        const number = typeof value.value === "number" ? value.value : Number(value.value);
        if (Number.isFinite(number) && (best === null || number > best)) best = number;
      }
    }
    return true;
  });
  return best;
}

function traits(node, name) {
  let clamp = null;
  let tap = TAP_NAMES.has(name);
  for (const attr of node.openingElement.attributes) {
    const key = attrName(attr);
    if (TAP_ATTRS.has(key)) tap = true;
    const container = attr.value && attr.value.type === "JSXExpressionContainer" ? attr.value.expression : attr.value;
    let found = null;
    if (key === "className" || key === "class") {
      found = classClamp(stringLiterals(container, []).flatMap((text) => text.split(/\s+/)));
    } else if (key === "style") found = styleClamp(container);
    else if (key === "numberOfLines") {
      const value = unwrap(container);
      if (value && value.type === "Literal" && typeof value.value === "number") found = value.value;
    }
    if (found !== null && (clamp === null || found > clamp)) clamp = found;
  }
  return { clamp, tap };
}

function context(stack) {
  let clamp = null;
  let tap = false;
  let user = false;
  for (let index = stack.length - 1; index >= 0; index--) {
    if (clamp === null && stack[index].clamp !== null) clamp = stack[index].clamp;
    tap = tap || stack[index].tap;
    user = user || stack[index].user;
  }
  return { clamp, tap, user };
}

function emit(kind, name, parts, rawLines, stack) {
  const lines = [...new Set(rawLines)];
  if (!hasText(parts) || lines.length === 0) return;
  if (request.touched && !lines.some((line) => request.touched.has(line))) return;
  const { clamp, tap, user } = context(stack);
  blocks.push({ line: Math.min(...lines), lines, kind, name, parts, clamp, tap, user });
}

function visitAttributes(node, stack) {
  for (const attr of node.openingElement.attributes) {
    if (attr.type !== "JSXAttribute") {
      walkInto(attr, stack);
      continue;
    }
    const key = attrName(attr);
    const container = attr.value && attr.value.type === "JSXExpressionContainer" ? attr.value.expression : attr.value;
    if (TEXT_PROPS.has(key)) {
      let parts = stringOf(container);
      if (!parts && container && storedField(container)) parts = [{ x: 1, field: storedField(container) }];
      if (parts) emit("prop", key, parts, span(attr.start, attr.end), stack);
    }
    if (key === "dangerouslySetInnerHTML" && container) {
      walkAll(container, (child) => {
        if (child.type === "Property" && keyName(child) === "__html" && storedField(child.value)) {
          emit("prop", key, [{ x: 1, field: storedField(child.value) }], span(attr.start, attr.end), stack);
        }
        return true;
      });
    }
    if (container) walkInto(container, stack);
  }
}

function walkInto(node, stack) {
  walkAll(node, (child) => visit(child, stack));
}

function expressionParts(expression, stack, from, to) {
  const parts = stringOf(expression);
  if (parts) return { parts, lines: span(from, to) };
  const field = storedField(expression);
  if (field) return { parts: [{ x: 1, field }], lines: span(from, to) };
  if (holdsJsx(expression)) {
    walkInto(expression, stack);
    return { parts: [], lines: [] };
  }
  return { parts: [SLOT], lines: [] };
}

function visitElement(node, stack) {
  const name = elementName(node);
  if (SKIP.has(name)) return;
  const own = traits(node, name);
  const next = [...stack, { ...own, user: name === USER }];
  visitAttributes(node, next);
  collect(node.children, name, next, name);
}

function collect(nodes, name, stack, parent) {
  let block = { parts: [], lines: [] };
  const cut = () => {
    emit("jsx", name, block.parts, block.lines, stack);
    block = { parts: [], lines: [] };
  };
  const gather = (list, owner) => {
    for (const child of list) {
      if (child.type === "JSXText") {
        const text = cleanText(child.value);
        if (text.trim()) {
          block.parts.push(text);
          const lead = child.value.length - child.value.trimStart().length;
          const tail = child.value.length - child.value.trimEnd().length;
          block.lines.push(...span(child.start + lead, child.end - tail));
        } else if (text) block.parts.push(text);
      } else if (child.type === "JSXExpressionContainer") {
        if (child.expression.type === "JSXEmptyExpression") continue;
        const found = expressionParts(child.expression, stack, child.start, child.end);
        block.parts.push(...found.parts);
        block.lines.push(...found.lines);
      } else if (child.type === "JSXFragment") gather(child.children, owner);
      else if (child.type === "JSXElement") {
        const childName = elementName(child);
        if (childName === "code" && SKIP.has("code")) block.parts.push(SLOT);
        else if (childName === "br" || SKIP.has(childName)) cut();
        else if (INLINE.has(childName) || (childName === "Text" && owner === "Text")) {
          const own = traits(child, childName);
          stack = [...stack, { ...own, user: childName === USER }];
          visitAttributes(child, stack);
          gather(child.children, childName);
          stack = stack.slice(0, -1);
        } else {
          cut();
          visitElement(child, stack);
        }
      }
    }
  };
  gather(nodes, parent);
  cut();
}

function constantParts(node) {
  node = unwrap(node);
  if (!node) return [];
  if (node.type === "ArrayExpression") {
    return node.elements.map((element) => ({ parts: stringOf(element), node: element })).filter((entry) => entry.parts);
  }
  const parts = stringOf(node);
  return parts ? [{ parts, node }] : [];
}

function skipsObject(node) {
  return node.properties.some((property) => property.type === "Property" && ["@context", "@type"].includes(keyName(property)));
}

function visit(node, stack) {
  if (node.type === "JSXElement") {
    visitElement(node, stack);
    return false;
  }
  if (node.type === "JSXFragment") {
    collect(node.children, "", stack, "");
    return false;
  }
  if (node.type === "ExportNamedDeclaration" && node.declaration) {
    const declaration = node.declaration;
    const id = declaration.type === "VariableDeclaration" ? declaration.declarations[0]?.id : declaration.id;
    if (id && (id.name === "metadata" || id.name === "generateMetadata")) return false;
  }
  if (node.type === "ObjectExpression" && skipsObject(node)) return false;
  if (node.type === "Property" && TEXT_PROPS.has(keyName(node))) {
    const parts = stringOf(node.value);
    if (parts) emit("key", keyName(node), parts, span(node.start, node.end), stack);
  }
  if (node.type === "VariableDeclarator" && node.id.type === "Identifier" && node.init) {
    for (const entry of constantParts(node.init)) {
      const text = entry.parts.filter((part) => typeof part === "string").join("");
      if (/\s/.test(text.trim())) emit("const", node.id.name, entry.parts, span(entry.node.start, entry.node.end), stack);
    }
  }
  return true;
}

function errorLine(error) {
  const label = error.labels && error.labels[0];
  return `line ${label ? lineOf(label.start) : 1}: ${error.message}`;
}

const files = [];
for (const file of request.files) {
  starts = [0];
  for (let index = 0; index < file.source.length; index++) if (file.source.charCodeAt(index) === 10) starts.push(index + 1);
  blocks = [];
  request.touched = file.touched ? new Set(file.touched) : null;
  const result = parseSync(file.path, file.source);
  const failure = result.errors.find((error) => error.severity === "Error");
  if (failure) {
    files.push({ path: file.path, error: errorLine(failure), blocks: [] });
    continue;
  }
  walkInto(result.program, []);
  files.push({ path: file.path, error: null, blocks });
}
process.stdout.write(JSON.stringify({ files }));
'''
