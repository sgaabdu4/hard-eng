#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';

const args = process.argv.slice(2);
const rootIndex = args.indexOf('--root');
const nodeIndexes = args.flatMap((arg, index) => arg === '--node' ? [index] : []);
const nativeModules = args
  .flatMap((arg, index) => arg === '--native-module' ? [args[index + 1]] : [])
  .filter(Boolean);
const root = path.resolve(rootIndex === -1 ? process.cwd() : args[rootIndex + 1]);

function run(command, commandArgs, options = {}) {
  return spawnSync(command, commandArgs, {
    cwd: root,
    encoding: 'utf8',
    stdio: ['ignore', 'pipe', 'pipe'],
    ...options,
  });
}

function existingNodeCandidates() {
  const candidates = [
    ...nodeIndexes.map((index) => args[index + 1]).filter(Boolean),
    process.execPath,
    '/usr/local/bin/node',
    '/opt/homebrew/opt/node@24/bin/node',
    '/opt/homebrew/opt/node@22/bin/node',
    '/opt/homebrew/opt/node@20/bin/node',
    '/opt/homebrew/bin/node',
  ];
  return [...new Set(candidates.map((candidate) => path.resolve(candidate)))]
    .filter((candidate) => fs.existsSync(candidate));
}

function nodeInfo(nodePath) {
  const result = run(nodePath, ['-p', 'JSON.stringify({ execPath: process.execPath, version: process.version, modules: process.versions.modules, napi: process.versions.napi })']);
  if (result.status !== 0) {
    return {
      nodePath,
      status: 'failed',
      stderr: result.stderr.trim(),
    };
  }
  return {
    nodePath,
    status: 'ready',
    ...JSON.parse(result.stdout),
  };
}

function npmIgnoreScripts() {
  const npm = process.platform === 'win32' ? 'npm.cmd' : 'npm';
  const result = run(npm, ['config', 'get', 'ignore-scripts']);
  if (result.status !== 0) {
    return { status: 'unknown', stderr: result.stderr.trim() };
  }
  return { status: 'ready', value: result.stdout.trim() };
}

function moduleProbeScript(moduleName) {
  const escaped = JSON.stringify(moduleName);
  if (moduleName === 'better-sqlite3') {
    return `
      const Database = require(${escaped});
      const db = new Database(':memory:');
      const row = db.prepare('select 1 as ok').get();
      db.close();
      if (!row || row.ok !== 1) throw new Error('better-sqlite3 query failed');
      console.log(require.resolve(${escaped}));
    `;
  }
  return `console.log(require.resolve(${escaped}));`;
}

function probeNativeModule(nodePath, moduleName) {
  const result = run(nodePath, ['-e', moduleProbeScript(moduleName)]);
  if (result.status === 0) {
    return {
      moduleName,
      nodePath,
      status: 'ready',
      resolvedPath: result.stdout.trim(),
    };
  }
  return {
    moduleName,
    nodePath,
    status: /Cannot find module/.test(result.stderr) ? 'missing' : 'failed',
    stderr: result.stderr.trim().split('\n').slice(0, 6).join('\n'),
  };
}

const nodes = existingNodeCandidates().map(nodeInfo);
const npmConfig = npmIgnoreScripts();
const nativeModuleResults = nativeModules.map((moduleName) => {
  const attempts = nodes
    .filter((node) => node.status === 'ready')
    .map((node) => probeNativeModule(node.nodePath, moduleName));
  return {
    moduleName,
    status: attempts.some((attempt) => attempt.status === 'ready') ? 'ready' : 'failed',
    attempts,
  };
});

const failedModules = nativeModuleResults.filter((result) => result.status !== 'ready');
const output = {
  status: failedModules.length === 0 ? 'ready' : 'failed',
  root,
  npmIgnoreScripts: npmConfig,
  nodes,
  nativeModules: nativeModuleResults,
  recommendations: [
    npmConfig.value === 'true' ? 'Run repair commands with npm_config_ignore_scripts=false.' : null,
    failedModules.length > 0 ? 'Pin PATH or --node to a Node candidate whose native module probe is ready.' : null,
  ].filter(Boolean),
};

console.log(JSON.stringify(output, null, 2));
process.exit(output.status === 'ready' ? 0 : 1);
