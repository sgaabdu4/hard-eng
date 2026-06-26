#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';

const args = process.argv.slice(2);
let root = process.cwd();
let json = false;
let requireProduct = false;
let requireDesign = false;
let requireTokenOwner = false;
let requireProductUpdate = false;
let requireDesignUpdate = false;

for (const arg of args) {
  if (arg === '--json') json = true;
  else if (arg === '--require-all') {
    requireProduct = true;
    requireDesign = true;
    requireTokenOwner = true;
  } else if (arg === '--require-product') requireProduct = true;
  else if (arg === '--require-design') requireDesign = true;
  else if (arg === '--require-token-owner') requireTokenOwner = true;
  else if (arg === '--require-product-update') requireProductUpdate = true;
  else if (arg === '--require-design-update') requireDesignUpdate = true;
  else if (arg === '-h' || arg === '--help') {
    console.log(`Usage: check-project-context-gates.mjs [--require-all] [--require-product-update] [--require-design-update] [--json] [repo]`);
    process.exit(0);
  } else {
    root = path.resolve(arg);
  }
}

root = path.resolve(root);
const blockers = [];
const warnings = [];

function read(relativePath) {
  try {
    return fs.readFileSync(path.join(root, relativePath), 'utf8');
  } catch {
    return '';
  }
}

function exists(relativePath) {
  return fs.existsSync(path.join(root, relativePath));
}

function firstExisting(candidates) {
  return candidates.find((candidate) => exists(candidate)) || null;
}

function hasSubstance(text) {
  const stripped = text.replace(/<!--[\s\S]*?-->/g, '').trim();
  return stripped.length >= 40 && !/^\s*(todo|tbd|placeholder)\s*$/i.test(stripped);
}

function gitStatus(paths) {
  const result = spawnSync('git', ['status', '--short', '--', ...paths], {
    cwd: root,
    encoding: 'utf8',
  });
  return result.status === 0 ? result.stdout.trim() : '';
}

function extractOwnerPaths(text, labels) {
  const matches = [];
  for (const label of labels) {
    const escaped = label.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const pattern = new RegExp(`^\\s*(?:[-*]\\s*)?${escaped}\\s*:\\s*\`?([^\`\n]+)`, 'gim');
    for (const match of text.matchAll(pattern)) {
      matches.push(match[1].trim().replace(/[.,;]$/, ''));
    }
  }
  return matches;
}

function block(message) {
  blockers.push(message);
}

const productPath = firstExisting(['PRODUCT.md', 'docs/PRODUCT.md']);
const designPath = firstExisting(['DESIGN.md', 'docs/DESIGN.md']);
const productText = productPath ? read(productPath) : '';
const designText = designPath ? read(designPath) : '';
const tokenOwnerPaths = designPath ? extractOwnerPaths(designText, ['Token owner', 'Tokens']) : [];
const designSystemPaths = designPath ? extractOwnerPaths(designText, ['Design system', 'Component owner']) : [];
const ownerPaths = [...new Set([...tokenOwnerPaths, ...designSystemPaths])];

if (requireProduct && (!productPath || !hasSubstance(productText))) block('PRODUCT.md is required and must contain real product context');
if (requireDesign && (!designPath || !hasSubstance(designText))) block('DESIGN.md is required and must contain real design context');
if (requireTokenOwner) {
  if (!designPath) {
    block('DESIGN.md must name token/design-system owners');
  } else if (!tokenOwnerPaths.length) {
    block('DESIGN.md must include `Token owner: <path>` or `Tokens: <path>`');
  }
  for (const ownerPath of ownerPaths) {
    if (!exists(ownerPath)) block(`DESIGN.md owner path does not exist: ${ownerPath}`);
  }
}

if (requireDesign && designPath && !/##\s+(Overview|Tokens|Components|States)/i.test(designText)) {
  warnings.push('DESIGN.md should include overview/tokens/components/states sections');
}

if (requireProductUpdate && !gitStatus(['PRODUCT.md', 'docs/PRODUCT.md'])) block('product change requires PRODUCT.md update');
if (requireDesignUpdate && !gitStatus(['DESIGN.md', 'docs/DESIGN.md'])) block('design/UI/token change requires DESIGN.md update');

const result = {
  root,
  productPath,
  designPath,
  tokenOwnerPaths,
  designSystemPaths,
  blockers,
  warnings,
};

if (json) {
  console.log(`${JSON.stringify(result, null, 2)}\n`);
} else {
  console.log(`project-context-gates: ${blockers.length ? 'fail' : 'pass'}`);
  if (productPath) console.log(`product: ${productPath}`);
  if (designPath) console.log(`design: ${designPath}`);
  if (ownerPaths.length) console.log(`owners: ${ownerPaths.join(', ')}`);
  for (const warning of warnings) console.log(`warning: ${warning}`);
  for (const blocker of blockers) console.error(`blocker: ${blocker}`);
}

process.exit(blockers.length ? 1 : 0);
