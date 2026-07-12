import fs from 'node:fs';
import { spawnSync } from 'node:child_process';
import { sha256 } from './canonical.mjs';

function environment() {
  return Object.fromEntries(
    [
      'PATH', 'HOME', 'TMPDIR', 'TMP', 'TEMP', 'SHELL', 'LANG', 'LC_ALL', 'LC_CTYPE',
      'CBM_CACHE_DIR', 'CONTEXT_MODE_DIR', 'XDG_CACHE_HOME', 'XDG_CONFIG_HOME',
    ]
      .filter((key) => process.env[key] !== undefined)
      .map((key) => [key, process.env[key]]),
  );
}

function run(command, args, timeout = 30_000) {
  const result = spawnSync(command, args, {
    env: { ...environment(), NO_COLOR: '1' },
    encoding: 'utf8',
    timeout,
    maxBuffer: 8 * 1024 * 1024,
    shell: false,
  });
  return {
    ok: result.status === 0 && !result.error,
    stdout: result.stdout ?? '',
    stderr: result.stderr ?? '',
    evidence: sha256(`${result.stdout ?? ''}\0${result.stderr ?? ''}\0${result.status ?? 'null'}`),
  };
}

function parseProjects(output) {
  try {
    const value = JSON.parse(output);
    return Array.isArray(value.projects) ? value.projects : [];
  } catch {
    throw new Error('Codebase Memory list_projects returned invalid JSON.');
  }
}

function record(result, evidence) {
  evidence.push(result.evidence);
  return result;
}

function exactProject(repo, execute, evidence) {
  let listed = execute('codebase-memory-mcp', ['cli', 'list_projects']);
  record(listed, evidence);
  if (!listed.ok) return { ok: false, evidence: sha256(evidence.join('\0')) };
  let projects = parseProjects(listed.stdout);
  let project = projects.find((entry) => {
    try {
      return fs.realpathSync(entry.root_path) === fs.realpathSync(repo);
    } catch {
      return false;
    }
  });
  if (!project) {
    const indexed = execute('codebase-memory-mcp', ['cli', 'index_repository', JSON.stringify({ repo_path: repo })], 120_000);
    record(indexed, evidence);
    if (!indexed.ok) return { ok: false, evidence: sha256(evidence.join('\0')) };
    listed = execute('codebase-memory-mcp', ['cli', 'list_projects']);
    record(listed, evidence);
    if (!listed.ok) return { ok: false, evidence: sha256(evidence.join('\0')) };
    projects = parseProjects(listed.stdout);
    project = projects.find((entry) => {
      try {
        return fs.realpathSync(entry.root_path) === fs.realpathSync(repo);
      } catch {
        return false;
      }
    });
  }
  if (!project?.name) throw new Error('Codebase Memory did not bind the exact repository after indexing.');
  return { ok: true, project: project.name };
}

function parameterKeys(parameters, allowed, operation) {
  const value = parameters ?? {};
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error(`${operation} parameters must be a bounded object.`);
  for (const key of Object.keys(value)) if (!allowed.has(key)) throw new Error(`${operation} has unknown parameter ${key}.`);
  return value;
}

function graphArguments(operation, project, parameters) {
  if (operation === 'get_architecture') {
    parameterKeys(parameters, new Set(), operation);
    return { project };
  }
  if (operation === 'search_graph') {
    const value = parameterKeys(parameters, new Set(['name_pattern', 'label', 'file_pattern', 'limit']), operation);
    const bounded = (name, max) => value[name] === undefined
      || (typeof value[name] === 'string' && value[name].trim() && value[name].length <= max);
    if (!bounded('name_pattern', 160) || !bounded('label', 40) || !bounded('file_pattern', 160)) {
      throw new Error('search_graph string parameters must be non-empty and bounded.');
    }
    if (!value.name_pattern && !value.label && !value.file_pattern) throw new Error('search_graph requires one bounded selector.');
    const limit = value.limit ?? 20;
    if (!Number.isInteger(limit) || limit < 1 || limit > 50) throw new Error('search_graph limit must be between 1 and 50.');
    return { project, ...value, limit };
  }
  if (operation === 'trace_path') {
    const value = parameterKeys(parameters, new Set(['function_name', 'direction', 'depth', 'include_tests']), operation);
    if (typeof value.function_name !== 'string' || !value.function_name.trim() || value.function_name.length > 160) {
      throw new Error('trace_path requires a bounded function_name.');
    }
    if (!['inbound', 'outbound', 'both'].includes(value.direction)) throw new Error('trace_path direction is invalid.');
    const depth = value.depth ?? 3;
    if (!Number.isInteger(depth) || depth < 1 || depth > 5) throw new Error('trace_path depth must be between 1 and 5.');
    if (value.include_tests !== undefined && typeof value.include_tests !== 'boolean') {
      throw new Error('trace_path include_tests must be boolean.');
    }
    return { project, ...value, depth };
  }
  parameterKeys(parameters, new Set(), operation);
  return { project };
}

function validStructuredResult(result) {
  if (!result.ok) return false;
  try {
    const value = JSON.parse(result.stdout);
    return value !== null && typeof value === 'object';
  } catch {
    return false;
  }
}

function observeCodebaseMemory(repo, operation, execute, parameters) {
  const operations = new Set([
    'list_projects', 'index_repository', 'get_architecture', 'search_graph', 'trace_path', 'detect_changes',
  ]);
  if (!operations.has(operation)) throw new Error('Runtime-observed Codebase Memory operation is unsupported.');
  const evidence = [];
  if (operation === 'index_repository') {
    parameterKeys(parameters, new Set(), operation);
    const indexed = record(execute(
      'codebase-memory-mcp',
      ['cli', 'index_repository', JSON.stringify({ repo_path: repo })],
      120_000,
    ), evidence);
    return { ok: indexed.ok, evidence: sha256(evidence.join('\0')) };
  }
  if (operation === 'list_projects') {
    parameterKeys(parameters, new Set(), operation);
    const listed = record(execute('codebase-memory-mcp', ['cli', 'list_projects']), evidence);
    if (!listed.ok) return { ok: false, evidence: sha256(evidence.join('\0')) };
    parseProjects(listed.stdout);
    return { ok: true, evidence: sha256(evidence.join('\0')) };
  }
  const resolved = exactProject(repo, execute, evidence);
  if (!resolved.ok) return resolved;
  const args = graphArguments(operation, resolved.project, parameters);
  const queried = record(execute(
    'codebase-memory-mcp',
    ['cli', operation, JSON.stringify(args)],
    120_000,
  ), evidence);
  return { ok: validStructuredResult(queried), evidence: sha256(evidence.join('\0')) };
}

function observeContextMode(repo, operation, execute, parameters) {
  if (operation !== 'search') throw new Error('Runtime-observed Context Mode receipts require an indexed search operation.');
  const value = parameterKeys(parameters, new Set(['source', 'query', 'limit']), operation);
  if (typeof value.source !== 'string' || !/^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$/.test(value.source)) {
    throw new Error('Context Mode search requires a bounded source label.');
  }
  if (
    typeof value.query !== 'string'
    || !value.query.trim()
    || value.query.length > 160
    || /[\r\n\0]/.test(value.query)
  ) throw new Error('Context Mode search requires one bounded query.');
  const limit = value.limit ?? 10;
  if (!Number.isInteger(limit) || limit < 1 || limit > 10) throw new Error('Context Mode search limit must be between 1 and 10.');
  const result = execute('context-mode', [
    'search', value.query,
    '--source', value.source,
    '--project', repo,
    '--limit', String(limit),
  ]);
  const output = `${result.stdout}\n${result.stderr}`.trim();
  const sources = output.split(/\r?\n/)
    .map((line) => /^Source:\s*(.+?)\s*$/.exec(line)?.[1] ?? null)
    .filter(Boolean);
  const observed = result.ok
    && output.length > 0
    && !/\bno (?:matching )?results?\b/i.test(output)
    && sources.length > 0
    && sources.every((source) => source === value.source);
  return { ok: observed, evidence: result.evidence };
}

export function observeSupportReceipt(repo, request, { now = Date.now(), execute = run } = {}) {
  if (!request || !['codebase-memory', 'context-mode'].includes(request.tool)) throw new Error('Support-tool request is invalid.');
  const base = {
    tool: request.tool,
    operation: request.operation,
    runtime_observed: true,
    recorded_at: new Date(now).toISOString(),
  };
  if (request.status === 'not-applicable') {
    if (request.tool !== 'context-mode' || request.operation !== 'not-applicable' || request.reason_code !== 'no-large-output') {
      throw new Error('Only Context Mode may be server-classified not-applicable for no large output.');
    }
    return { ...base, status: 'not-applicable', reason_code: 'no-large-output' };
  }
  const observed = request.tool === 'codebase-memory'
    ? observeCodebaseMemory(repo, request.operation, execute, request.parameters)
    : observeContextMode(repo, request.operation, execute, request.parameters);
  if (request.status === 'fallback') {
    if (observed.ok) throw new Error('Support-tool fallback is forbidden while the required command is healthy.');
    if (typeof request.fallback_reason !== 'string' || !request.fallback_reason.trim() || request.fallback_reason.length > 240) {
      throw new Error('Support-tool fallback requires a bounded diagnosis.');
    }
    return {
      ...base,
      status: 'fallback',
      evidence_digest: observed.evidence,
      fallback_reason: request.fallback_reason,
    };
  }
  if (request.status !== 'pass' || !observed.ok) throw new Error(`${request.tool} runtime observation failed.`);
  return { ...base, status: 'pass', evidence_digest: observed.evidence };
}
