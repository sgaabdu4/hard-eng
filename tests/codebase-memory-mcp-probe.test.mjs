#!/usr/bin/env node
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';

const probe = path.join(process.env.HOME, '.agents', 'scripts', 'probe-codebase-memory-mcp.mjs');
assert.ok(fs.existsSync(probe), `${probe} must exist`);

const result = spawnSync('node', [probe], {
  encoding: 'utf8',
  env: { ...process.env, CBM_MCP_PROBE_TIMEOUT_MS: '30000' },
});

assert.equal(result.status, 0, result.stderr || result.stdout);
assert.match(result.stdout, /codebase-memory-mcp probe ok:/);
for (const tool of ['index_repository', 'search_graph', 'trace_path', 'search_code']) {
  assert.ok(result.stdout.includes(tool), `probe output must include ${tool}`);
}

console.log('codebase-memory-mcp-probe: pass');
