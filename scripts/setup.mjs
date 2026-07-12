#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import {
  buildSetupPlan,
  readInstallManifestRecord,
} from '../runtime/lib/setup-transaction.mjs';
import { applySetupPlan } from '../runtime/lib/setup-apply.mjs';
import { applyRollbackPlan, buildRollbackPlan } from '../runtime/lib/setup-rollback.mjs';
import { runSetupDoctor } from '../runtime/lib/setup-doctor.mjs';
import {
  attachStateMigration,
  attachStatePurge,
  describeStateMigrations,
  describeStateRoots,
  purgeStateRoots,
  validateStateMigrations,
} from '../runtime/lib/setup-state.mjs';
import { redactErrorMessage } from '../runtime/lib/redact.mjs';
import { createCodexWiringClient } from '../runtime/lib/codex-wiring.mjs';
import { createCodexCutoverClient } from '../runtime/lib/codex-cutover.mjs';
import { sha256 } from '../runtime/lib/canonical.mjs';
import {
  applySetupRecoveryPlan,
  beginSetupTransaction,
  buildSetupRecoveryPlan,
} from '../runtime/lib/setup-recovery.mjs';
import { assertSetupEnvironment } from '../runtime/lib/setup-environment.mjs';

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
    ...(Object.hasOwn(plan, 'existing_manifest_hash')
      ? { existing_manifest_hash: plan.existing_manifest_hash }
      : {}),
    ...(plan.source_checkout_adoption ? { source_checkout_adoption: plan.source_checkout_adoption } : {}),
    purge_state: plan.purge_state,
    codex_mcp_action: plan.codex_mcp_action,
    ...(plan.codex_mcp ? { codex_mcp: plan.codex_mcp } : {}),
    ...(plan.codex_cutover ? {
      live_cutover: true,
      codex_cutover: plan.codex_cutover,
    } : {}),
    ...(plan.backup_bundle_id ? { backup_bundle_id: plan.backup_bundle_id } : {}),
    ...(plan.previous_codex_mcp_status ? { previous_codex_mcp_status: plan.previous_codex_mcp_status } : {}),
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
    previous_codex_mcp_status: plan.previous_codex_mcp_status,
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
  cronText = undefined,
  wiringClient = createCodexWiringClient({ env }),
  cutoverClient = createCodexCutoverClient({ env, cronText }),
  crashAfter = null,
  platform = process.platform,
} = {}) {
  const options = parseArgs(argv);
  if (options.mode === 'doctor') return runSetupDoctor({
    home: options.home,
    sourceRoot: path.resolve(sourceRoot),
    env,
    wiringClient,
    platform,
    cronText,
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
    return applySetupRecoveryPlan(plan, { home: options.home, wiringClient });
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
      codex_mcp_action: 'none',
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
    const currentWiring = wiringClient.inspect(options.home);
    if (!['PASS', 'NOT_CONFIGURED'].includes(currentWiring.status)) throw new Error('Rollback requires the exact current native wiring state.');
    const currentCodexMcpConfigured = currentWiring.status === 'PASS';
    const currentManifestRecord = readInstallManifestRecord(options.home);
    if (!currentManifestRecord || currentManifestRecord.hash !== plan.current_manifest_hash) {
      throw new Error('Install manifest changed after rollback approval.');
    }
    const currentManifest = currentManifestRecord.bytes;
    const transactionContext = beginSetupTransaction({
      home: options.home,
      plan,
      previousManifest: currentManifest,
      previousCodexMcpConfigured: currentCodexMcpConfigured,
      previousCodexMcpStatus: currentWiring.status,
      now,
    });
    const restorePreviousWiring = () => {
      if (plan.previous_codex_mcp_status === 'MIGRATION_REQUIRED') {
        const observed = wiringClient.inspect(options.home);
        if (observed.status !== 'MIGRATION_REQUIRED') throw new Error('Rollback did not restore the installed Codex owner.');
        return { status: 'PASS', action: 'verify-restored', changed: false, evidence_digest: observed.evidence_digest };
      }
      return wiringClient.reconcile(options.home, plan.previous_codex_mcp_status === 'PASS');
    };
    const result = applyRollbackPlan(plan, {
      home: options.home,
      now,
      failAfter,
      finalize: restorePreviousWiring,
      onRollback: () => wiringClient.reconcile(options.home, currentCodexMcpConfigured),
      transactionContext,
      crashAfter,
    });
    result.codex_mcp = result.finalization;
    delete result.finalization;
    return result;
  }
  if (options.backup) throw new Error('--backup is valid only with rollback.');
  if (options.liveCutover && options.mode !== 'migrate') throw new Error('--live-cutover is valid only with migrate.');
  if (options.purgeState) throw new Error('--purge-state was replaced by the separate `purge-state` mode.');
  if (options.stateRoots.length > 0 && !['migrate', 'update'].includes(options.mode)) {
    throw new Error('--state-root is valid only with purge-state, migrate, or update.');
  }
  const previousWiring = wiringClient.inspect(options.home);
  if (previousWiring.status === 'FAIL') throw new Error('Codex MCP wiring inventory is unavailable.');
  if (previousWiring.status === 'CONFLICT') throw new Error('Unexpected hard_eng owner blocks setup.');
  if (
    previousWiring.codebase_memory_mcp_entries > 0
    && previousWiring.status !== 'MIGRATION_REQUIRED'
  ) {
    throw new Error('Codebase Memory MCP wiring requires the approved live cutover before setup may mutate files.');
  }
  const codexCutover = previousWiring.status === 'MIGRATION_REQUIRED'
    ? cutoverClient.preview(options.home, previousWiring)
    : null;
  const previousCodexMcpConfigured = previousWiring.status === 'PASS' && previousWiring.configured === true;
  let plan = buildSetupPlan({
    mode: options.mode,
    home: options.home,
    sourceRoot: path.resolve(sourceRoot),
    purgeState: options.purgeState,
    codexMcp: previousWiring,
    codexCutover,
    liveCutover: options.liveCutover,
  });
  if (options.stateRoots.length > 0) plan = attachStateMigration(plan, describeStateMigrations(options.stateRoots));
  if (options.dryRun) return publicPlan(plan, 'DRY_RUN');
  if (!options.confirm) return publicPlan(plan, 'APPROVAL_REQUIRED');
  if (options.confirm !== plan.plan_digest) throw new Error('Setup confirmation digest does not match the current plan.');
  if (plan.stateMigration) validateStateMigrations(plan.stateMigration);
  const desiredCodexMcpConfigured = plan.codex_mcp.desired_configured;
  const previousManifestRecord = readInstallManifestRecord(options.home);
  if ((previousManifestRecord?.hash ?? null) !== plan.existing_manifest_hash) {
    throw new Error('Install manifest changed after setup approval.');
  }
  const previousManifest = previousManifestRecord?.bytes ?? null;
  const transactionContext = beginSetupTransaction({
    home: options.home,
    plan,
    previousManifest,
    previousCodexMcpConfigured,
    previousCodexMcpStatus: previousWiring.status,
    now,
  });
  const finalize = plan.codex_cutover
    ? ({ transaction, transactionContext }) => {
        const result = cutoverClient.apply(options.home, plan.codex_cutover, { transaction, transactionContext });
        const after = wiringClient.inspect(options.home);
        if (after.status !== 'PASS' || after.codebase_memory_mcp_entries !== 0) {
          throw new Error('Native Codex MCP wiring or Codebase Memory CLI-only state was not observable after cutover.');
        }
        const { applied, ...publicResult } = result;
        return { result: publicResult, applied };
      }
    : () => ({
        result: wiringClient.reconcile(options.home, desiredCodexMcpConfigured),
        applied: [],
      });
  const result = applySetupPlan(plan, {
    home: options.home,
    sourceRoot: path.resolve(sourceRoot),
    now,
    failAfter,
    finalize,
    onRollback: () => {
      const observed = wiringClient.inspect(options.home);
      if (previousWiring.status === 'MIGRATION_REQUIRED') {
        if (observed.status !== 'MIGRATION_REQUIRED') throw new Error('Installed Codex owner was not restored.');
        return { status: 'PASS', action: 'verify-restored', changed: false, evidence_digest: observed.evidence_digest };
      }
      return wiringClient.reconcile(options.home, previousCodexMcpConfigured);
    },
    transactionContext,
    crashAfter,
  });
  result.codex_mcp = result.finalization;
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
