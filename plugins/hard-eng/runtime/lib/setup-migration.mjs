import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { sha256 } from './canonical.mjs';
import { attachMigrationPlan, inspectSetupTarget, safeSetupTarget } from './setup-transaction.mjs';

const legacyAgentHashes = new Map([
  ['Explore', '2890e4d59b452c509efced423a9bd9160df4579f1c59a4538b881aedd61e76ec'],
  ['Plan', '9a6134be0d5164d99a4c46d0b5cb366c5c13bb7deae15f81bec47cf750d01221'],
  ['api-designer', 'db6cda8a63112490f174c316a971b6323355a60dc8efcc7e6d5c7d7d0bb15e1a'],
  ['appwrite-auditor', '9f9e2c18b28c422e201e9d94dc6e72a5dc70aab5029555dafb663e50b4227ea8'],
  ['default', '940300fa393085751a03f8923446a1e5b98afb7bca145530637e50a524fbab8d'],
  ['devops-engineer', '693fcbeeed19d0f32d566b6f013223c22a0d169eb64e739d1704345c5c35fdd1'],
  ['e2e-flutter-runner', '26293ceb199b0b62f0b180a5fe8dee232ccb1e8d7a257ee5d2b8e4c8a871d348'],
  ['e2e-web-runner', 'd411037ffab387617d7bcb1638bad25397aacfba9dc070389b88aa1f811af537'],
  ['edge-case-hunter', '12520b69109f58a0a0f55594e55b2ada0a1bec6abbe902d2845aa01077c932a7'],
  ['explorer', '667f18783baffec68665d0fb55862d317e7691ba581f6db2420bc15d8b625472'],
  ['flutter-auditor', '044d77f979aba09e1296379b821a55affeb2303c473df519042bfbb50836ae8b'],
  ['general-purpose', '06458721a70154e45653475702d9438051649cd117f8e28cf859fefdd6081b80'],
  ['implementer', 'df571e3d7a54b4259e275f549c94590be40e389567485aef2d5bb124ce6a2959'],
  ['junior-dev', '02adb24f1eb921de3ee7b0e6df9d0737766b705fe3e95a1fbb4c37130004aeb0'],
  ['naive-tester', '6b00eb414a688632b6bfa40518c0308060f2535746434875f58f164ea873f4c9'],
  ['perf-engineer', 'ea9e4c2b244a164087c34c33e98cc5f35e6f04ade5b5f1966b99b3dea86f3ecc'],
  ['qa-engineer', '212932735843d2b2ec150dde75f644f90a559c75bb19d2417eb8dac1e11c070d'],
  ['react-ts-auditor', 'bdd47ba56333527a57dde60463de834a6dfda258bec106e4a6eeadea282bfc47'],
  ['reuse-auditor', '3142cf6a36f219e08e6dcc7af3c4bc22e1f4823188bc9e3cff7c350e48c4928e'],
  ['security-reviewer', 'e542b8f76c13b98d1be8f6d453df05d1c4ef02b4357f7850ee341a55b70b2b34'],
  ['staff-engineer', '6904aa7000c31ae4895c516b46d5a652e6cc6a4c2d0b6c7d1a1db3b52cf5ea0f'],
  ['user-flow-auditor', '8159635227ea5f753ad739d5cbda208735b357a05d0d3db2286efc49e2668797'],
  ['ux-reviewer', '261b0483e4640c3246f4393c8d903e975a3d4ba1a885441515f5a46bd75c27ea'],
  ['web-ui-auditor', 'b2d39b58de52376cffaa71c1c658dbb258292fac186ef28a22f0333617809d93'],
  ['worker', 'bf81beb45a57a180b4cbfe66c18cb300842652a05a8f3c9e74791df93a3b2e60'],
]);

function linkResolvesTo(home, relative, expected) {
  const target = safeSetupTarget(home, relative);
  let stat;
  try {
    stat = fs.lstatSync(target);
  } catch (error) {
    if (error.code === 'ENOENT') return false;
    throw error;
  }
  if (!stat.isSymbolicLink()) return false;
  return path.resolve(path.dirname(target), fs.readlinkSync(target)) === path.resolve(home, expected);
}

function candidate(home, relative, expectedType, liveCutover, classification) {
  const target = safeSetupTarget(home, relative);
  try {
    fs.lstatSync(target);
  } catch (error) {
    if (error.code === 'ENOENT') return null;
    throw error;
  }
  const current = inspectSetupTarget(target);
  if (current.type !== expectedType) {
    return { entry: { path: relative, action: 'retain', classification: 'unknown-or-modified-type' }, operation: null };
  }
  const action = liveCutover ? 'remove' : 'defer';
  return {
    entry: { path: relative, action, classification, expected_type: expectedType, current_hash: current.hash },
    operation: liveCutover ? {
      action: 'remove',
      expected_type: expectedType,
      path: relative,
      source_relative: null,
      generated: null,
      source_hash: null,
      current_hash: current.hash,
      mode: null,
      rollback_action: 'restore-current',
    } : null,
  };
}

function collectSkillLinks(home, liveCutover, output) {
  const directory = path.join(home, '.codex', 'skills');
  if (!fs.existsSync(directory)) return;
  for (const entry of fs.readdirSync(directory, { withFileTypes: true }).sort((a, b) => a.name.localeCompare(b.name))) {
    const relative = `.codex/skills/${entry.name}`;
    const target = path.join(directory, entry.name);
    if (!entry.isSymbolicLink()) continue;
    const resolved = path.resolve(path.dirname(target), fs.readlinkSync(target));
    if (!resolved.startsWith(`${path.join(home, '.agents', 'skills')}${path.sep}`)) continue;
    const value = candidate(home, relative, 'symlink', liveCutover, 'legacy-hard-eng-skill-link');
    if (value) output.push(value);
  }
}

function collectAgentProfiles(home, liveCutover, output) {
  for (const name of [...legacyAgentHashes.keys()].sort()) {
    const relative = `.codex/agents/${name}.toml`;
    const target = safeSetupTarget(home, relative);
    if (!fs.existsSync(target)) continue;
    const current = inspectSetupTarget(target);
    const markerOwned = current.type === 'file'
      && fs.statSync(target).size <= 16 * 1024
      && fs.readFileSync(target, 'utf8').startsWith('# hard-eng-managed-agent/v1\n');
    if (current.type !== 'file' || (current.hash !== legacyAgentHashes.get(name) && !markerOwned)) {
      output.push({
        entry: {
          path: relative, action: 'retain', classification: 'unknown-or-modified-agent-profile',
          expected_type: current.type, current_hash: current.hash,
        },
        operation: null,
      });
      continue;
    }
    const value = candidate(home, relative, 'file', liveCutover, 'legacy-hard-eng-agent-profile');
    if (value) output.push(value);
  }
}

function collectBackupLinks(home, liveCutover, output) {
  const directory = path.join(home, '.codex');
  if (!fs.existsSync(directory)) return;
  const owners = new Map([
    ['AGENTS.md', '.agents/AGENTS.md'],
    ['hooks.json', '.agents/codex/hooks.json'],
    ['mcp-config.json', '.agents/mcp-config.json'],
  ]);
  for (const entry of fs.readdirSync(directory, { withFileTypes: true }).sort((a, b) => a.name.localeCompare(b.name))) {
    const match = /^(AGENTS\.md|hooks\.json|mcp-config\.json)\.backup\.\d{8,}$/.exec(entry.name);
    if (!match || !entry.isSymbolicLink()) continue;
    const target = path.join(directory, entry.name);
    const resolved = path.resolve(path.dirname(target), fs.readlinkSync(target));
    if (resolved !== path.resolve(home, owners.get(match[1]))) continue;
    const value = candidate(home, `.codex/${entry.name}`, 'symlink', liveCutover, 'legacy-hard-eng-backup-link');
    if (value) output.push(value);
  }
}

const managedCodexBins = [
  'codex-cleanup',
  'codex-context-mode-health',
  'codex-health',
  'codex-update-stack',
  'codex-watchdog',
];

function addBlocker(output, code, summary) {
  if (!output.some((item) => item.code === code)) output.push({ code, summary });
}

function presentType(target) {
  try {
    const stat = fs.lstatSync(target);
    if (stat.isSymbolicLink()) return 'symlink';
    if (stat.isFile()) return 'file';
    if (stat.isDirectory()) return 'directory';
    return 'unsupported';
  } catch (error) {
    if (error.code === 'ENOENT') return null;
    throw error;
  }
}

function retained(relative, classification, expectedType = null, currentHash = null, action = 'retain') {
  return {
    entry: {
      path: relative,
      action,
      classification,
      ...(expectedType ? { expected_type: expectedType } : {}),
      ...(currentHash ? { current_hash: currentHash } : {}),
    },
    operation: null,
  };
}

function isManagedCodexBin(target) {
  const stat = fs.lstatSync(target);
  if (!stat.isFile() || stat.size > 1024 * 1024) return false;
  return fs.readFileSync(target, 'utf8').slice(0, 4096).includes('# Managed by hard-eng installer.');
}

function collectManagedCodexBins(home, liveCutover, output, blockers) {
  for (const name of managedCodexBins) {
    const relative = `.codex/bin/${name}`;
    const target = safeSetupTarget(home, relative);
    const type = presentType(target);
    if (!type) continue;
    if (type !== 'file' || !isManagedCodexBin(target)) {
      const current = type === 'file' || type === 'symlink' ? inspectSetupTarget(target) : null;
      output.push(retained(relative, 'unknown-or-modified-hard-eng-runtime', type, current?.hash));
      addBlocker(blockers, 'MODIFIED_LEGACY_SURFACE', 'A legacy runtime path is modified or has an unexpected type and was retained.');
      continue;
    }
    output.push(candidate(home, relative, 'file', liveCutover, 'legacy-hard-eng-runtime'));
  }
}

function isLegacySkillConfig(target) {
  const stat = fs.lstatSync(target);
  if (!stat.isFile() || stat.size > 64 * 1024) return false;
  try {
    const value = JSON.parse(fs.readFileSync(target, 'utf8'));
    if (!value || Array.isArray(value) || typeof value !== 'object') return false;
    const keys = Object.keys(value).sort();
    if (!keys.length || keys.some((key) => !['selection', 'skills'].includes(key))) return false;
    return (typeof value.selection === 'string' || value.selection === undefined)
      && (Array.isArray(value.skills) ? value.skills.every((item) => typeof item === 'string') : value.skills === undefined);
  } catch {
    return false;
  }
}

function collectSkillConfig(home, liveCutover, output, blockers) {
  const relative = '.config/hard-eng/skills.json';
  const target = safeSetupTarget(home, relative);
  const type = presentType(target);
  if (!type) return;
  if (type !== 'file' || !isLegacySkillConfig(target)) {
    const current = type === 'file' || type === 'symlink' ? inspectSetupTarget(target) : null;
    output.push(retained(relative, 'unknown-or-modified-hard-eng-skill-config', type, current?.hash));
    addBlocker(blockers, 'MODIFIED_LEGACY_SURFACE', 'A legacy runtime path is modified or has an unexpected type and was retained.');
    return;
  }
  output.push(candidate(home, relative, 'file', liveCutover, 'legacy-hard-eng-skill-config'));
}

function isOwnedPlaywrightCache(target) {
  if (presentType(target) !== 'directory') return false;
  const top = fs.readdirSync(target).sort();
  if (top.length !== 1 || top[0] !== 'e2e-playwright') return false;
  const root = path.join(target, 'e2e-playwright');
  if (presentType(root) !== 'directory') return false;
  const names = fs.readdirSync(root).sort();
  if (!names.includes('package.json') || !names.includes('package-lock.json')) return false;
  if (names.some((name) => !['node_modules', 'package-lock.json', 'package.json'].includes(name))) return false;
  try {
    const pkg = JSON.parse(fs.readFileSync(path.join(root, 'package.json'), 'utf8'));
    const lock = JSON.parse(fs.readFileSync(path.join(root, 'package-lock.json'), 'utf8'));
    return Object.keys(pkg).every((key) => key === 'dependencies')
      && typeof pkg.dependencies?.playwright === 'string'
      && Object.keys(pkg.dependencies).length === 1
      && lock.name === 'e2e-playwright'
      && Number.isInteger(lock.lockfileVersion);
  } catch {
    return false;
  }
}

function collectCache(home, liveCutover, output, blockers) {
  const relative = '.cache/hard-eng';
  const target = safeSetupTarget(home, relative);
  const type = presentType(target);
  if (!type) return;
  if (!isOwnedPlaywrightCache(target)) {
    output.push(retained(relative, 'unknown-or-modified-hard-eng-cache', type));
    addBlocker(blockers, 'MODIFIED_LEGACY_SURFACE', 'A legacy runtime path is modified or has an unexpected type and was retained.');
    return;
  }
  output.push(candidate(home, relative, 'directory', liveCutover, 'legacy-hard-eng-playwright-cache'));
}

function collectShellBlock(home, liveCutover, output, blockers) {
  const relative = '.zshenv';
  const target = safeSetupTarget(home, relative);
  if (presentType(target) !== 'file' || fs.statSync(target).size > 1024 * 1024) return;
  const text = fs.readFileSync(target, 'utf8');
  const begin = '# BEGIN hard-eng bootstrap path';
  const end = '# END hard-eng bootstrap path';
  const beginCount = text.split(begin).length - 1;
  const endCount = text.split(end).length - 1;
  if (beginCount === 0 && endCount === 0) return;
  const current = inspectSetupTarget(target);
  if (beginCount !== 1 || endCount !== 1 || text.indexOf(begin) > text.indexOf(end)) {
    output.push(retained(relative, 'malformed-hard-eng-shell-block', 'file', current.hash));
    addBlocker(blockers, 'MALFORMED_SHELL_BLOCK', 'The legacy shell block is malformed and was retained unchanged.');
    return;
  }
  const rewritten = text
    .replace(begin, '# BEGIN personal toolchain bootstrap')
    .replace(end, '# END personal toolchain bootstrap');
  output.push({
    entry: {
      path: relative,
      action: liveCutover ? 'rewrite' : 'defer',
      classification: 'legacy-hard-eng-shell-marker-with-support-paths-preserved',
      expected_type: 'file',
      current_hash: current.hash,
    },
    operation: liveCutover ? {
      action: 'write',
      expected_type: 'file',
      path: relative,
      source_relative: null,
      generated: rewritten,
      source_hash: sha256(rewritten),
      current_hash: current.hash,
      mode: current.mode,
      rollback_action: 'restore-current',
    } : null,
  });
}

function collectLaunchAgent(home, output, blockers) {
  const relative = 'Library/LaunchAgents/dev.hard-eng.codex-watchdog.plist';
  const target = safeSetupTarget(home, relative);
  const type = presentType(target);
  if (!type) return;
  let classification = 'unknown-or-modified-hard-eng-launch-agent';
  let currentHash = null;
  if (type === 'file' && fs.statSync(target).size <= 128 * 1024) {
    const text = fs.readFileSync(target, 'utf8');
    const current = inspectSetupTarget(target);
    currentHash = current.hash;
    if (text.includes('<string>dev.hard-eng.codex-watchdog</string>') && text.includes('/.codex/bin/codex-watchdog</string>')) {
      classification = 'legacy-hard-eng-launch-agent-requires-unload';
    }
  }
  output.push(retained(relative, classification, type, currentHash));
  addBlocker(blockers, 'BACKGROUND_JOB_REQUIRES_MANUAL_RETIREMENT', 'A legacy launchd or cron owner must be stopped through its native control plane before file cleanup.');
}

export function readCronTextForHome(home, env = process.env) {
  if (!env.HOME || path.resolve(home) !== path.resolve(env.HOME)) return null;
  const childEnv = Object.fromEntries(
    ['PATH', 'HOME', 'TMPDIR', 'TMP', 'TEMP', 'SHELL', 'LANG', 'LC_ALL', 'LC_CTYPE']
      .filter((key) => env[key] !== undefined)
      .map((key) => [key, env[key]]),
  );
  const result = spawnSync('crontab', ['-l'], {
    env: childEnv,
    encoding: 'utf8',
    timeout: 5_000,
    maxBuffer: 256 * 1024,
    shell: false,
  });
  if (result.error?.code === 'ENOENT') return null;
  if (result.status === 0) return result.stdout ?? '';
  if (result.status === 1 && /no crontab/i.test(result.stderr ?? '')) return '';
  throw new Error('Current crontab could not be inventoried safely.');
}

function collectCronOwners(cronText, output, blockers) {
  if (typeof cronText !== 'string') return;
  const owned = cronText.split(/\r?\n/).filter((line) => {
    const value = line.trim();
    if (!value || value.startsWith('#')) return false;
    return /(?:\.agents\/scripts\/auto-sync\.sh|\.codex\/bin\/codex-(?:watchdog|update-stack|health|cleanup)|dev\.hard-eng)/i.test(value);
  });
  if (!owned.length) return;
  output.push(retained(
    'native:crontab',
    'legacy-hard-eng-crontab-requires-native-retirement',
    'native-control-plane',
    sha256(owned.join('\n')),
    'defer',
  ));
  addBlocker(
    blockers,
    'BACKGROUND_JOB_REQUIRES_MANUAL_RETIREMENT',
    'A legacy launchd or cron owner must be stopped through its native control plane before file cleanup.',
  );
}

function collectExternalTools(home, output, blockers) {
  const noMistakes = safeSetupTarget(home, '.local/bin/no-mistakes');
  if (presentType(noMistakes)) {
    const current = presentType(noMistakes) === 'file' ? inspectSetupTarget(noMistakes) : null;
    output.push(retained('.local/bin/no-mistakes', 'external-no-mistakes-retirement-deferred', presentType(noMistakes), current?.hash, 'defer'));
    addBlocker(blockers, 'NO_MISTAKES_EXTERNAL_DEPENDENCIES', 'Global no-mistakes retirement is blocked until dependent repositories are migrated or breakage is explicitly accepted.');
  }
  if (presentType(safeSetupTarget(home, '.no-mistakes'))) {
    output.push(retained('.no-mistakes', 'external-no-mistakes-state-preserved', presentType(safeSetupTarget(home, '.no-mistakes')), null, 'defer'));
    addBlocker(blockers, 'NO_MISTAKES_EXTERNAL_DEPENDENCIES', 'Global no-mistakes retirement is blocked until dependent repositories are migrated or breakage is explicitly accepted.');
  }
  const treehouse = safeSetupTarget(home, '.local/bin/treehouse');
  if (presentType(treehouse)) {
    const current = presentType(treehouse) === 'file' ? inspectSetupTarget(treehouse) : null;
    output.push(retained('.local/bin/treehouse', 'external-treehouse-retirement-deferred', presentType(treehouse), current?.hash, 'defer'));
    addBlocker(blockers, 'TREEHOUSE_RETIREMENT_REQUIRES_SEPARATE_APPROVAL', 'Treehouse binary/state retirement requires a clean pool inventory and separate approval.');
  }
  if (presentType(safeSetupTarget(home, '.treehouse'))) {
    output.push(retained('.treehouse', 'external-treehouse-state-preserved', presentType(safeSetupTarget(home, '.treehouse')), null, 'defer'));
    addBlocker(blockers, 'TREEHOUSE_RETIREMENT_REQUIRES_SEPARATE_APPROVAL', 'Treehouse binary/state retirement requires a clean pool inventory and separate approval.');
  }
}

function collectRuntimeSurfaces(home, liveCutover, output, blockers, cronText) {
  collectManagedCodexBins(home, liveCutover, output, blockers);
  collectSkillConfig(home, liveCutover, output, blockers);
  collectCache(home, liveCutover, output, blockers);
  collectShellBlock(home, liveCutover, output, blockers);
  collectLaunchAgent(home, output, blockers);
  collectCronOwners(cronText, output, blockers);
  collectExternalTools(home, output, blockers);
}

export function inspectLegacySurfaces(home, { liveCutover = false, cronText = null } = {}) {
  const classified = [];
  const blockers = [];
  if (linkResolvesTo(home, '.codex/AGENTS.md', '.agents/AGENTS.md')) {
    classified.push({
      entry: { path: '.codex/AGENTS.md', action: 'retain', classification: 'canonical-agents-link' },
      operation: null,
    });
  }
  for (const [relative, expected] of [
    ['.codex/hooks.json', '.agents/codex/hooks.json'],
    ['.codex/mcp-config.json', '.agents/mcp-config.json'],
  ]) {
    if (!linkResolvesTo(home, relative, expected)) continue;
    const value = candidate(home, relative, 'symlink', liveCutover, 'legacy-hard-eng-global-link');
    if (value) classified.push(value);
  }
  collectSkillLinks(home, liveCutover, classified);
  collectAgentProfiles(home, liveCutover, classified);
  collectBackupLinks(home, liveCutover, classified);
  collectRuntimeSurfaces(home, liveCutover, classified, blockers, cronText);
  const legacy = classified.map((value) => value.entry).sort((left, right) => left.path.localeCompare(right.path));
  const operations = classified.map((value) => value.operation).filter(Boolean);
  return { legacy, operations, blockers };
}

export function buildMigrationPlan(basePlan, { home, liveCutover, cronText = null }) {
  const { legacy, operations, blockers } = inspectLegacySurfaces(home, { liveCutover, cronText });
  return attachMigrationPlan(basePlan, { legacy, operations, liveCutover, blockers });
}
