import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { digestValue, sha256 } from './canonical.mjs';
import { fingerprintCandidate } from './candidate.mjs';

const packageChecks = [
  ['format-check', ['format:check', 'format-check', 'check:format']],
  ['lint', ['lint']],
  ['typecheck', ['typecheck', 'type-check', 'check:types']],
  ['test', ['test']],
  ['integration', ['test:integration', 'integration']],
  ['build', ['build']],
];
const prohibited = /(?:\bcodex\b|\bclaude\b|\bimagegen\b|\bno-mistakes\b|\btreehouse\b|\b(?:curl|wget)\b[^\n|]*\|\s*(?:ba|z|fi)?sh\b|(?:^|\s)--watch(?:\s|$)|\bdaemon\b)/i;
const scriptReference = /\b(?:npm\s+(?:run\s+)?|pnpm\s+(?:run\s+)?|yarn\s+|bun\s+run\s+)([a-zA-Z0-9:._-]+)/g;
const localRunner = /\b(?:node|bash|sh)\s+(?:--[a-zA-Z0-9-]+\s+)*(["']?[^\s;&|"']+\.(?:[cm]?js|ts|sh)["']?)/g;
const localImport = /(?:\bfrom\s*|\bimport\s*(?:\(\s*)?|\brequire\s*\()\s*["'](\.{1,2}\/[^"']+)["']/g;

function check({ id, owner, command, trigger, risk, timeoutMs = 120_000 }) {
  return {
    id,
    owner,
    command,
    trigger,
    risk,
    timeout_ms: timeoutMs,
    network_policy: 'project-owned-no-installer-pipes',
    mutability: 'candidate-mutation-detected',
    candidate_impact: 'proof',
    evidence_parser: 'exit-code-and-output-digest',
    rerun_rule: 'only-after-candidate-change-or-classified-flake',
  };
}

function readPackage(repo) {
  const file = path.join(repo, 'package.json');
  if (!fs.existsSync(file)) return null;
  const parsed = JSON.parse(fs.readFileSync(file, 'utf8'));
  return parsed && typeof parsed.scripts === 'object' && !Array.isArray(parsed.scripts) ? parsed : null;
}

function readSmallOwner(file, label) {
  const stat = fs.lstatSync(file);
  if (!stat.isFile() || stat.isSymbolicLink() || stat.size > 1024 * 1024) throw new Error(`${label} owner is unsafe or oversized.`);
  return fs.readFileSync(file, 'utf8');
}

function resolveLocalOwner(repo, importer, reference) {
  const base = path.resolve(path.dirname(importer), reference);
  const candidates = [base, `${base}.mjs`, `${base}.js`, `${base}.cjs`, `${base}.ts`, path.join(base, 'index.js')];
  const owner = candidates.find((candidate) => fs.existsSync(candidate));
  if (!owner || !owner.startsWith(`${path.resolve(repo)}${path.sep}`)) return null;
  return owner;
}

function assertSafeLocalOwner(repo, file, seen = new Set()) {
  const absolute = path.resolve(repo, file);
  if (!absolute.startsWith(`${path.resolve(repo)}${path.sep}`) || !fs.existsSync(absolute) || seen.has(absolute)) return;
  if (seen.size >= 100) throw new Error('Package check wrapper dependency graph exceeds 100 files.');
  seen.add(absolute);
  const text = readSmallOwner(absolute, 'Package check wrapper');
  if (prohibited.test(text)) throw new Error('Package check wrapper contains a prohibited model, daemon, legacy, or network-installer command.');
  for (const match of text.matchAll(localImport)) {
    const dependency = resolveLocalOwner(repo, absolute, match[1]);
    if (dependency) assertSafeLocalOwner(repo, dependency, seen);
  }
}

function assertSafeScript(repo, pkg, name, seen = new Set()) {
  if (seen.has(name)) return;
  seen.add(name);
  const command = pkg.scripts[name];
  if (typeof command !== 'string' || !command.trim()) throw new Error(`Package script ${name} is invalid.`);
  if (prohibited.test(command)) {
    throw new Error(`Package script ${name} contains a prohibited model, daemon, legacy, or network-installer command.`);
  }
  for (const lifecycle of [`pre${name}`, `post${name}`]) {
    if (Object.hasOwn(pkg.scripts, lifecycle)) assertSafeScript(repo, pkg, lifecycle, seen);
  }
  for (const match of command.matchAll(scriptReference)) {
    if (Object.hasOwn(pkg.scripts, match[1])) assertSafeScript(repo, pkg, match[1], seen);
  }
  for (const match of command.matchAll(localRunner)) {
    assertSafeLocalOwner(repo, match[1].replace(/^["']|["']$/g, ''));
  }
}

function regularFile(repo, relative) {
  const file = path.join(repo, relative);
  if (!fs.existsSync(file)) return null;
  const stat = fs.lstatSync(file);
  if (!stat.isFile() || stat.isSymbolicLink()) throw new Error(`Project owner ${relative} must be a regular file.`);
  return file;
}

function projectChecks(repo) {
  const checks = [];
  const pubspec = regularFile(repo, 'pubspec.yaml');
  if (pubspec) {
    const text = readSmallOwner(pubspec, 'pubspec.yaml');
    const flutter = /\bsdk\s*:\s*flutter\b|^\s*flutter\s*:/m.test(text);
    checks.push(check({
      id: flutter ? 'flutter.analyze' : 'dart.analyze',
      owner: 'pubspec.yaml',
      command: flutter ? ['flutter', 'analyze'] : ['dart', 'analyze'],
      trigger: 'pubspec.yaml',
      risk: 'Dart static-analysis regression',
    }));
    if (flutter || fs.existsSync(path.join(repo, 'test'))) checks.push(check({
      id: flutter ? 'flutter.test' : 'dart.test',
      owner: 'pubspec.yaml and test/',
      command: flutter ? ['flutter', 'test', '--no-pub'] : ['dart', 'test'],
      trigger: flutter ? 'Flutter project' : 'Dart test owner exists',
      risk: 'Dart behavior regression',
    }));
  }
  if (regularFile(repo, 'go.mod')) {
    checks.push(check({
      id: 'go.vet', owner: 'go.mod', command: ['go', 'vet', '-mod=readonly', './...'],
      trigger: 'go.mod', risk: 'Go static-analysis regression',
    }));
    checks.push(check({
      id: 'go.test', owner: 'go.mod', command: ['go', 'test', '-mod=readonly', './...'],
      trigger: 'go.mod', risk: 'Go behavior regression',
    }));
  }
  const pyproject = regularFile(repo, 'pyproject.toml');
  if (pyproject) {
    const text = readSmallOwner(pyproject, 'pyproject.toml');
    if (/\bpytest\b|\[tool\.pytest\./i.test(text) || fs.existsSync(path.join(repo, 'tests'))) checks.push(check({
      id: 'python.test', owner: 'pyproject.toml or tests/', command: ['python3', '-m', 'pytest'],
      trigger: 'Python test owner exists', risk: 'Python behavior regression',
    }));
    if (/\[tool\.ruff(?:\.|\])/i.test(text)) checks.push(check({
      id: 'python.ruff', owner: 'pyproject.toml#tool.ruff', command: ['python3', '-m', 'ruff', 'check', '.'],
      trigger: 'Ruff owner exists', risk: 'Python lint regression',
    }));
    if (/\[tool\.mypy(?:\.|\])/i.test(text)) checks.push(check({
      id: 'python.mypy', owner: 'pyproject.toml#tool.mypy', command: ['python3', '-m', 'mypy', '.'],
      trigger: 'mypy owner exists', risk: 'Python type regression',
    }));
  }
  if (regularFile(repo, 'Cargo.toml')) {
    checks.push(check({
      id: 'rust.test', owner: 'Cargo.toml', command: ['cargo', 'test', '--all-targets'],
      trigger: 'Cargo.toml', risk: 'Rust behavior regression',
    }));
  }
  return checks;
}

export function validateCheck(checkSpec) {
  const expected = [
    'id', 'owner', 'command', 'trigger', 'risk', 'timeout_ms', 'network_policy',
    'mutability', 'candidate_impact', 'evidence_parser', 'rerun_rule',
  ].sort();
  if (JSON.stringify(Object.keys(checkSpec).sort()) !== JSON.stringify(expected)) throw new Error('Check registry entry has an invalid shape.');
  if (!/^[a-z0-9][a-z0-9._-]{2,80}$/.test(checkSpec.id)) throw new Error('Check ID is invalid.');
  if (!Array.isArray(checkSpec.command) || !checkSpec.command.length || checkSpec.command.some((part) => typeof part !== 'string' || !part)) {
    throw new Error(`Check ${checkSpec.id} command is invalid.`);
  }
  if (!Number.isInteger(checkSpec.timeout_ms) || checkSpec.timeout_ms < 1_000 || checkSpec.timeout_ms > 15 * 60_000) {
    throw new Error(`Check ${checkSpec.id} timeout is invalid.`);
  }
  if (
    checkSpec.network_policy !== 'project-owned-no-installer-pipes'
    || checkSpec.mutability !== 'candidate-mutation-detected'
  ) {
    throw new Error(`Check ${checkSpec.id} violates ordinary-operation policy.`);
  }
  return true;
}

export function buildCheckRegistry(repo) {
  const registry = [check({
    id: 'git.diff-check',
    owner: 'Git built-in',
    command: ['git', 'diff', '--check'],
    trigger: 'always',
    risk: 'whitespace and conflict-marker defects',
    timeoutMs: 30_000,
  })];
  const pkg = readPackage(repo);
  if (pkg) {
    for (const [category, candidates] of packageChecks) {
      const name = candidates.find((candidate) => Object.hasOwn(pkg.scripts, candidate));
      if (!name) continue;
      assertSafeScript(repo, pkg, name);
      registry.push(check({
        id: `package.${category}`,
        owner: `package.json#scripts.${name}`,
        command: ['npm', 'run', '--silent', name],
        trigger: category === 'test' ? 'always' : `when ${category} owner exists`,
        risk: `repository-owned ${category} regression`,
      }));
    }
  }
  registry.push(...projectChecks(repo));
  const duplicates = registry.map((entry) => entry.id).filter((id, index, all) => all.indexOf(id) !== index);
  if (duplicates.length) throw new Error(`Check registry contains duplicate IDs: ${[...new Set(duplicates)].join(', ')}.`);
  if (registry.length === 1) {
    throw new Error('No deterministic project quality checks were discovered; Ship requires an owned check or explicit no-code disposition.');
  }
  registry.forEach(validateCheck);
  return registry;
}

function execute(repo, checkSpec) {
  const started = Date.now();
  const env = Object.fromEntries(
    ['PATH', 'HOME', 'TMPDIR', 'TMP', 'TEMP', 'SHELL', 'LANG', 'LC_ALL', 'TERM']
      .filter((key) => process.env[key] !== undefined)
      .map((key) => [key, process.env[key]]),
  );
  const worker = fileURLToPath(new URL('../check-worker.mjs', import.meta.url));
  const result = spawnSync(process.execPath, [worker, repo, String(checkSpec.timeout_ms), JSON.stringify(checkSpec.command)], {
    encoding: 'utf8',
    timeout: checkSpec.timeout_ms + 5_000,
    maxBuffer: 256 * 1024,
    env: { ...env, CI: '1', HARD_ENG_CHECK: '1' },
    shell: false,
  });
  let observed;
  try {
    observed = result.status === 0 ? JSON.parse(result.stdout) : null;
  } catch {
    observed = null;
  }
  return {
    id: checkSpec.id,
    status: observed?.status === 0 && !observed.error_code ? 'PASS' : 'FAIL',
    exit_code: Number.isInteger(observed?.status) ? observed.status : null,
    signal: observed?.signal ?? result.signal ?? null,
    timed_out: observed?.timed_out === true || result.error?.code === 'ETIMEDOUT',
    duration_ms: Date.now() - started,
    output_digest: /^[a-f0-9]{64}$/.test(observed?.output_digest ?? '')
      ? observed.output_digest
      : sha256(`${result.stdout ?? ''}\0${result.stderr ?? ''}`),
    rerun_command: checkSpec.command,
  };
}

export function runCheckRegistry(repo, registry, { allowedUntracked = [], onProgress = null } = {}) {
  registry.forEach(validateCheck);
  const before = fingerprintCandidate(repo, { allowedUntracked });
  const results = registry.map((checkSpec, index) => {
    if (onProgress) onProgress({ event: 'check-start', id: checkSpec.id, index: index + 1, total: registry.length });
    const result = execute(repo, checkSpec);
    if (onProgress) onProgress({ event: 'check-finish', id: checkSpec.id, status: result.status, index: index + 1, total: registry.length });
    return result;
  });
  const after = fingerprintCandidate(repo, { allowedUntracked });
  const findings = [];
  if (before.fingerprint !== after.fingerprint) {
    findings.push({
      id: 'candidate-mutated-during-checks',
      severity: 'critical',
      action: 'manual',
      summary: 'A read-only check mutated the candidate; return to Build and classify the owner.',
    });
  }
  for (const result of results.filter((entry) => entry.status === 'FAIL')) {
    findings.push({
      id: `check-failed-${result.id}`,
      severity: 'high',
      action: 'manual',
      summary: `Check ${result.id} failed once; diagnose before rerun.`,
      rerun_command: result.rerun_command,
    });
  }
  const deterministicResults = results.map(({ duration_ms: ignored, ...result }) => result);
  const status = findings.length ? 'FAIL' : 'PASS';
  return {
    schema: 'hard-eng/check-report/v1',
    status,
    registry_digest: digestValue(registry),
    results_digest: digestValue(deterministicResults),
    candidate: after,
    results,
    findings,
    attempts: results.length,
  };
}
