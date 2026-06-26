#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';

const root = path.resolve(process.argv[2] || process.cwd());
const configPath = path.join(root, 'ssot-guardrails.json');
const blockers = [];
const ignoredDirs = new Set(['.git', 'node_modules', 'vendor']);
const textExtensions = new Set(['.css', '.html', '.js', '.json', '.md', '.mjs', '.sh', '.ts', '.tsx', '.txt', '.yml', '.yaml']);

function rel(file) {
  return path.relative(root, file).split(path.sep).join('/');
}

function readJson(file) {
  try {
    return JSON.parse(fs.readFileSync(file, 'utf8'));
  } catch (error) {
    blockers.push(`ssot-guardrails.json is invalid JSON: ${error.message}`);
    return null;
  }
}

function walk(dir, out = []) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    if (ignoredDirs.has(entry.name)) continue;
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      walk(fullPath, out);
    } else if (entry.isFile()) {
      out.push(fullPath);
    }
  }
  return out;
}

function globToRegExp(glob) {
  let source = '';
  for (let index = 0; index < glob.length; index += 1) {
    const char = glob[index];
    if (char === '*') {
      if (glob[index + 1] === '*') {
        if (glob[index + 2] === '/') {
          source += '(?:.*/)?';
          index += 2;
        } else {
          source += '.*';
          index += 1;
        }
      } else {
        source += '[^/]*';
      }
    } else {
      source += char.replace(/[|\\{}()[\]^$+?.]/g, '\\$&');
    }
  }
  return new RegExp(`^${source}$`);
}

function matchesAny(relativePath, patterns) {
  return patterns.some((pattern) => globToRegExp(pattern).test(relativePath));
}

function firstMatchLine(text, pattern) {
  const regex = new RegExp(pattern);
  const lines = text.split(/\n/);
  for (const [index, line] of lines.entries()) {
    if (regex.test(line)) return index + 1;
  }
  return 0;
}

const config = fs.existsSync(configPath) ? readJson(configPath) : null;
if (!config) {
  if (!fs.existsSync(configPath)) blockers.push('ssot-guardrails.json is missing');
} else {
  if (!Array.isArray(config.scannerRegistry)) {
    blockers.push('ssot-guardrails.json must define scannerRegistry[]');
  } else {
    const registered = new Set();
    for (const [index, entry] of config.scannerRegistry.entries()) {
      if (!entry || typeof entry.path !== 'string' || !entry.path.trim()) {
        blockers.push(`scannerRegistry[${index}].path is required`);
        continue;
      }
      registered.add(entry.path);
      if (!Array.isArray(entry.owners) || entry.owners.length === 0 || entry.owners.some((owner) => typeof owner !== 'string' || !owner.trim())) {
        blockers.push(`scannerRegistry[${index}].owners must be non-empty string[]`);
      }
      if (!fs.existsSync(path.join(root, entry.path))) blockers.push(`${entry.path} is registered but missing`);
      for (const owner of entry.owners || []) {
        if (!fs.existsSync(path.join(root, owner))) blockers.push(`${entry.path} owner ${owner} is missing`);
      }
    }
    const rootScripts = fs.existsSync(path.join(root, 'scripts')) ? walk(path.join(root, 'scripts')).map(rel) : [];
    for (const script of rootScripts.filter((file) => /^scripts\/check-.*\.mjs$/.test(file))) {
      if (!registered.has(script)) blockers.push(`${script} is a scanner but is not registered in ssot-guardrails.json`);
    }
  }

  if (!Array.isArray(config.patternRules)) {
    blockers.push('ssot-guardrails.json must define patternRules[]');
  } else {
    const files = walk(root).filter((file) => textExtensions.has(path.extname(file)));
    for (const [index, rule] of config.patternRules.entries()) {
      if (!rule || typeof rule.id !== 'string' || !rule.id.trim()) blockers.push(`patternRules[${index}].id is required`);
      if (typeof rule.pattern !== 'string' || !rule.pattern.trim()) blockers.push(`patternRules[${index}].pattern is required`);
      if (!Array.isArray(rule.include) || rule.include.length === 0) blockers.push(`patternRules[${index}].include must be non-empty string[]`);
      if (!Array.isArray(rule.owners) || rule.owners.length === 0) blockers.push(`patternRules[${index}].owners must be non-empty string[]`);
      if (typeof rule.pattern !== 'string' || !Array.isArray(rule.include)) continue;
      try {
        new RegExp(rule.pattern);
      } catch (error) {
        blockers.push(`patternRules[${index}].pattern is invalid: ${error.message}`);
        continue;
      }
      const allow = Array.isArray(rule.allow) ? rule.allow : [];
      for (const owner of rule.owners || []) {
        if (!fs.existsSync(path.join(root, owner))) blockers.push(`patternRules[${index}] owner ${owner} is missing`);
      }
      for (const file of files) {
        const relativePath = rel(file);
        if (!matchesAny(relativePath, rule.include)) continue;
        if (matchesAny(relativePath, allow)) continue;
        const text = fs.readFileSync(file, 'utf8');
        const line = firstMatchLine(text, rule.pattern);
        if (line) blockers.push(`${relativePath}:${line}: ${rule.message || `matches ${rule.id}`}`);
      }
    }
  }
}

if (blockers.length) {
  console.error('ssot-guardrails: fail');
  for (const blocker of blockers) console.error(`blocker: ${blocker}`);
  process.exit(1);
}

console.log('ssot-guardrails: pass');
