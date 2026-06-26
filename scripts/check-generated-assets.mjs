#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';

const root = path.resolve(process.argv[2] || process.cwd());
const blockers = [];
let configuredPairs = [];
let staticAssets = [];

function loadPairs() {
  const configPath = path.join(root, 'generated-assets.json');
  if (!fs.existsSync(configPath)) return [];
  let config;
  try {
    config = JSON.parse(fs.readFileSync(configPath, 'utf8'));
  } catch (error) {
    blockers.push(`generated-assets.json is invalid JSON: ${error.message}`);
    return [];
  }
  if (!Array.isArray(config.pairs)) {
    blockers.push('generated-assets.json must define pairs[]');
    return [];
  }
  if (config.static !== undefined && !Array.isArray(config.static)) {
    blockers.push('generated-assets.json static must be an array');
  }
  staticAssets = (config.static || []).map((asset, index) => {
    if (!asset || typeof asset.output !== 'string' || typeof asset.reason !== 'string' || !asset.reason.trim()) {
      blockers.push(`generated-assets.json static[${index}] must have output and reason`);
      return null;
    }
    return asset;
  }).filter(Boolean);
  configuredPairs = config.pairs.map((pair, index) => {
    if (!pair || typeof pair.source !== 'string' || typeof pair.output !== 'string') {
      blockers.push(`generated-assets.json pairs[${index}] must have source and output`);
      return null;
    }
    return [pair.source, pair.output];
  }).filter(Boolean);
  return configuredPairs;
}

for (const [source, output] of loadPairs()) {
  const sourcePath = path.join(root, source);
  const outputPath = path.join(root, output);
  if (!fs.existsSync(sourcePath)) {
    blockers.push(`${source} missing for ${output}`);
    continue;
  }
  if (!fs.existsSync(outputPath)) {
    blockers.push(`${output} missing for ${source}`);
    continue;
  }
  if (fs.statSync(outputPath).mtimeMs + 1000 < fs.statSync(sourcePath).mtimeMs) {
    blockers.push(`${output} is older than ${source}`);
  }
}

function walk(dir, out = []) {
  for (const entry of fs.readdirSync(path.join(root, dir), { withFileTypes: true })) {
    if (['.git', 'node_modules', 'vendor'].includes(entry.name)) continue;
    const rel = path.join(dir, entry.name).split(path.sep).join('/');
    if (entry.isDirectory()) walk(rel, out);
    else if (entry.isFile()) out.push(rel);
  }
  return out;
}

function trackedImages() {
  const result = spawnSync('git', ['ls-files', 'docs/images'], { cwd: root, encoding: 'utf8' });
  if (result.status !== 0) return [];
  return result.stdout.split('\n').filter((file) => /^docs\/images\/.+\.png$/.test(file));
}

function trackedMedia() {
  const result = spawnSync('git', ['ls-files', 'docs/media'], { cwd: root, encoding: 'utf8' });
  if (result.status !== 0) return [];
  return result.stdout.split('\n').filter((file) => /^docs\/media\/.+\.(mp4|mov|webm)$/i.test(file));
}

function referencedBy(file) {
  if (file === 'README.md') return 'referenced by README.md';
  return `referenced by ${file}`;
}

const registeredOutputs = new Set([
  ...configuredPairs.map(([, output]) => output),
  ...staticAssets.map((asset) => asset.output),
]);
for (const asset of staticAssets) {
  if (!fs.existsSync(path.join(root, asset.output))) blockers.push(`${asset.output} missing for static asset entry`);
}

for (const file of walk('').filter((item) => /\.(md|html)$/.test(item))) {
  const text = fs.readFileSync(path.join(root, file), 'utf8');
  const refs = [
    ...[...text.matchAll(/src="(docs\/images\/[^"]+\.png)"/g)].map((match) => match[1]),
    ...[...text.matchAll(/!\[[^\]]*\]\((docs\/images\/[^)\s]+\.png)(?:\s+"[^"]*")?\)/g)].map((match) => match[1]),
    ...[...text.matchAll(/href="(docs\/media\/[^"]+\.(?:mp4|mov|webm))"/gi)].map((match) => match[1]),
    ...[...text.matchAll(/\[[^\]]*\]\((docs\/media\/[^)\s]+\.(?:mp4|mov|webm))(?:\s+"[^"]*")?\)/gi)].map((match) => match[1]),
  ];
  for (const asset of refs) {
    if (!registeredOutputs.has(asset)) blockers.push(`${asset} is ${referencedBy(file)} but missing from generated-assets.json`);
    if (!fs.existsSync(path.join(root, asset))) blockers.push(`${asset} is ${referencedBy(file)} but missing`);
  }
}

for (const image of trackedImages()) {
  if (!registeredOutputs.has(image)) blockers.push(`${image} is tracked under docs/images but missing from generated-assets.json`);
}
for (const media of trackedMedia()) {
  if (!registeredOutputs.has(media)) blockers.push(`${media} is tracked under docs/media but missing from generated-assets.json`);
}

if (blockers.length) {
  console.error('generated-assets: fail');
  for (const blocker of blockers) console.error(`blocker: ${blocker}`);
  process.exit(1);
}

console.log('generated-assets: pass');
