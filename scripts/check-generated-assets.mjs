#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';

const root = path.resolve(process.argv[2] || process.cwd());
const blockers = [];
let configuredPairs = [];

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

const readmePath = path.join(root, 'README.md');
if (fs.existsSync(readmePath)) {
  const readme = fs.readFileSync(readmePath, 'utf8');
  const imageRefs = [...readme.matchAll(/src="(docs\/images\/[^"]+\.png)"/g)].map((match) => match[1]);
  const registeredOutputs = new Set(configuredPairs.map(([, output]) => output));
  const staticAllowlist = new Set(['docs/images/hard-eng-hero.png']);
  for (const image of imageRefs) {
    if (!registeredOutputs.has(image) && !staticAllowlist.has(image)) {
      blockers.push(`${image} is referenced by README.md but missing from generated-assets.json`);
    }
    if (!fs.existsSync(path.join(root, image))) blockers.push(`${image} is referenced by README.md but missing`);
  }
}

if (blockers.length) {
  console.error('generated-assets: fail');
  for (const blocker of blockers) console.error(`blocker: ${blocker}`);
  process.exit(1);
}

console.log('generated-assets: pass');
