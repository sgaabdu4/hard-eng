#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { buildSetupPlan, manifestPath } from '../plugins/hard-eng/runtime/lib/setup-transaction.mjs';
import { applySetupPlan } from '../plugins/hard-eng/runtime/lib/setup-apply.mjs';
import { applyRollbackPlan, buildRollbackPlan } from '../plugins/hard-eng/runtime/lib/setup-rollback.mjs';
import { runSetupDoctor } from '../plugins/hard-eng/runtime/lib/setup-doctor.mjs';
import { buildMigrationPlan, readCronTextForHome } from '../plugins/hard-eng/runtime/lib/setup-migration.mjs';
import {
  attachStateMigration,
  attachStatePurge,
  describeStateMigrations,
  describeStateRoots,
  purgeStateRoots,
  validateStateMigrations,
} from '../plugins/hard-eng/runtime/lib/setup-state.mjs';
import { redactErrorMessage } from '../plugins/hard-eng/runtime/lib/redact.mjs';
import { createCodexPluginClient } from '../plugins/hard-eng/runtime/lib/codex-plugin.mjs';
import { sha256 } from '../plugins/hard-eng/runtime/lib/canonical.mjs';
import {
  applySetupRecoveryPlan,
  beginSetupTransaction,
  buildSetupRecoveryPlan,
} from '../plugins/hard-eng/runtime/lib/setup-recovery.mjs';
import { assertSetupEnvironment } from '../plugins/hard-eng/runtime/lib/setup-environment.mjs';

const setupModes = new Set(['install', 'update', 'migrate', 'uninstall', 'rollback', 'recover', 'purge-state']);

function parseArgs(argv) {
  const options = {
    mode: argv[0] ?? 'doctor',
    home: process.env.HOME,
    dryRun: false,
    confirm: null,
    purgeState: false,
    liveCutover: false,
    backup: null,
    stateRoots: [],
  };
  for (let index = 1; index < argv.length; index += 1) {
    const value = argv[index];
    if (value === '--home') options.home = path.resolve(argv[++index]);
    else if (value === '--dry-run') options.dryRun = true;
    else if (value === '--confirm') options.confirm = argv[++index];
    else if (value === '--purge-state') options.purgeState = true;
    else if (value === '--live-cutover') options.liveCutover = true;
    else if (value === '--backup') options.backup = argv[++index];
    else if (value === '--state-root') options.stateRoots.push(path.resolve(argv[++index]));
    else throw new Error(`Unknown setup option: ${value}.`);
  }
  if (!options.home) throw new Error('A target home is required.');
  return options;
}

function publicPlan(plan, status) {
  return {
    status,
    mode: plan.mode,
    plan_digest: plan.plan_digest,
    target_home_digest: plan.target_home_digest,
    source_digest: plan.source_digest,
    purge_state: plan.purge_state,
    codex_plugin_action: plan.codex_plugin_action,
    ...(plan.live_cutover !== undefined ? {
      live_cutover: plan.live_cutover,
      legacy: plan.legacy,
      migration_blockers: plan.migration_blockers,
    } : {}),
    ...(plan.backup_bundle_id ? { backup_bundle_id: plan.backup_bundle_id } : {}),
    ...(plan.state_purge ? { state_purge: plan.state_purge } : {}),
    ...(plan.state_migration ? { state_migration: plan.state_migration } : {}),
    operations: plan.operations.map((operation) => ({
      action: operation.action,
      path: operation.path,
      source_hash: operation.source_hash,
      current_hash: operation.current_hash,
      rollback_action: operation.rollback_action,
    })),
  };
}

function publicRecoveryPlan(plan, status) {
  return {
    status,
    mode: 'recover',
    plan_digest: plan.plan_digest,
    source_plan_digest: plan.source_plan_digest,
    target_home_digest: plan.target_home_digest,
    transaction_digest: plan.transaction_digest,
    previous_plugin_installed: plan.previous_plugin_installed,
    operations: plan.operations.map((entry) => ({
      action: entry.action,
      path: entry.path,
      before_hash: entry.before?.hash ?? null,
      after_hash: entry.after?.hash ?? null,
    })),
  };
}

export function runSetup(argv, {
  sourceRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..'),
  now = Date.now(),
  failAfter = null,
  env = process.env,
  pluginClient = createCodexPluginClient({ env }),
  cronText,
  crashAfter = null,
  platform = process.platform,
} = {}) {
  const options = parseArgs(argv);
  if (options.mode === 'doctor') return runSetupDoctor({
    home: options.home,
    sourceRoot: path.resolve(sourceRoot),
    env,
    pluginClient,
    cronText,
    platform,
  });
  if (!setupModes.has(options.mode)) throw new Error(`Unknown setup mode: ${options.mode}.`);
  assertSetupEnvironment(options.home, env, platform);
  if (options.mode === 'recover') {
    if (options.backup || options.purgeState || options.liveCutover || options.stateRoots.length > 0) {
      throw new Error('recover accepts only --dry-run and --confirm.');
    }
    const plan = buildSetupRecoveryPlan({ home: options.home });
    if (options.dryRun) return publicRecoveryPlan(plan, 'DRY_RUN');
    if (!options.confirm) return publicRecoveryPlan(plan, 'APPROVAL_REQUIRED');
    if (options.confirm !== plan.plan_digest) throw new Error('Setup confirmation digest does not match the current plan.');
    return applySetupRecoveryPlan(plan, { home: options.home, pluginClient });
  }
  if (options.mode === 'purge-state') {
    if (options.purgeState || options.liveCutover || options.backup) {
      throw new Error('purge-state accepts only --state-root, --dry-run, and --confirm.');
    }
    if (options.stateRoots.length !== 1) throw new Error('purge-state requires exactly one explicit --state-root.');
    const descriptors = describeStateRoots(options.stateRoots);
    const base = {
      schema: 'hard-eng/setup-plan/v1',
      mode: 'purge-state',
      purge_state: true,
      codex_plugin_action: 'none',
      target_home_digest: sha256(path.resolve(options.home)),
      source_digest: sha256('state-purge-only'),
      operations: [],
    };
    const plan = attachStatePurge(base, descriptors);
    if (options.dryRun) return publicPlan(plan, 'DRY_RUN');
    if (!options.confirm) return publicPlan(plan, 'APPROVAL_REQUIRED');
    if (options.confirm !== plan.plan_digest) throw new Error('Setup confirmation digest does not match the current plan.');
    return {
      status: 'PASS',
      mode: 'purge-state',
      plan_digest: plan.plan_digest,
      purged_state_roots: purgeStateRoots(plan.statePurge),
    };
  }
  if (options.mode === 'rollback') {
    if (!options.backup) throw new Error('rollback requires one exact --backup plan digest.');
    if (options.purgeState || options.liveCutover || options.stateRoots.length > 0) {
      throw new Error('rollback cannot be combined with purge, live-cutover, or state-root options.');
    }
    const plan = buildRollbackPlan({ home: options.home, backupPlanDigest: options.backup });
    if (options.dryRun) return publicPlan(plan, 'DRY_RUN');
    if (!options.confirm) return publicPlan(plan, 'APPROVAL_REQUIRED');
    if (options.confirm !== plan.plan_digest) throw new Error('Setup confirmation digest does not match the current plan.');
    const currentPlugin = pluginClient.inspect(options.home);
    const currentPluginInstalled = currentPlugin.core?.installed === true;
    const currentManifest = fs.readFileSync(manifestPath(options.home));
    const transactionContext = beginSetupTransaction({
      home: options.home,
      plan,
      previousManifest: currentManifest,
      previousPluginInstalled: currentPluginInstalled,
      now,
    });
    const result = applyRollbackPlan(plan, {
      home: options.home,
      now,
      failAfter,
      finalize: () => pluginClient.reconcile(options.home, plan.previous_plugin_installed),
      onRollback: () => pluginClient.reconcile(options.home, currentPluginInstalled),
      transactionContext,
      crashAfter,
    });
    result.codex_plugin = result.finalization;
    delete result.finalization;
    return result;
  }
  if (options.backup) throw new Error('--backup is valid only with rollback.');
  if (options.liveCutover && options.mode !== 'migrate') throw new Error('--live-cutover is valid only with migrate.');
  if (options.purgeState) throw new Error('--purge-state was replaced by the separate `purge-state` mode.');
  if (options.stateRoots.length > 0 && !['migrate', 'update'].includes(options.mode)) {
    throw new Error('--state-root is valid only with purge-state, migrate, or update.');
  }
  let plan = buildSetupPlan({
    mode: options.mode,
    home: options.home,
    sourceRoot: path.resolve(sourceRoot),
    purgeState: options.purgeState,
  });
  if (options.mode === 'migrate') plan = buildMigrationPlan(plan, {
    home: options.home,
    liveCutover: options.liveCutover,
    cronText: cronText === undefined ? readCronTextForHome(options.home, env) : cronText,
  });
  if (options.stateRoots.length > 0) plan = attachStateMigration(plan, describeStateMigrations(options.stateRoots));
  if (options.dryRun) return publicPlan(plan, 'DRY_RUN');
  if (!options.confirm) return publicPlan(plan, 'APPROVAL_REQUIRED');
  if (options.confirm !== plan.plan_digest) throw new Error('Setup confirmation digest does not match the current plan.');
  if (plan.live_cutover && plan.migration_blockers?.length) {
    throw new Error(`Live cutover is blocked by ${plan.migration_blockers.map((item) => item.code).join(', ')}.`);
  }
  if (plan.stateMigration) validateStateMigrations(plan.stateMigration);
  const previousPlugin = pluginClient.inspect(options.home);
  const previousPluginInstalled = previousPlugin.core?.installed === true;
  const desiredPluginInstalled = options.mode !== 'uninstall';
  const previousManifest = fs.existsSync(manifestPath(options.home))
    ? fs.readFileSync(manifestPath(options.home))
    : null;
  const transactionContext = beginSetupTransaction({
    home: options.home,
    plan,
    previousManifest,
    previousPluginInstalled,
    now,
  });
  const result = applySetupPlan(plan, {
    home: options.home,
    sourceRoot: path.resolve(sourceRoot),
    now,
    failAfter,
    finalize: () => pluginClient.reconcile(options.home, desiredPluginInstalled),
    onRollback: () => pluginClient.reconcile(options.home, previousPluginInstalled),
    transactionContext,
    crashAfter,
  });
  result.codex_plugin = result.finalization;
  delete result.finalization;
  if (plan.stateMigration) result.migrated_state_roots = validateStateMigrations(plan.stateMigration);
  return result;
}

function main() {
  try {
    const result = runSetup(process.argv.slice(2));
    process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
    if (result.status === 'APPROVAL_REQUIRED') process.exitCode = 3;
    else if (result.status === 'FAIL') process.exitCode = 2;
  } catch (error) {
    process.stderr.write(`${redactErrorMessage(error)}\n`);
    process.exitCode = 2;
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) main();
