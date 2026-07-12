import path from 'node:path';

const supportedPlatforms = new Set(['darwin', 'linux']);

export function inspectSetupEnvironment(home, env = process.env, platform = process.platform) {
  const defaultCodexHome = path.join(path.resolve(home), '.codex');
  const configuredCodexHome = env.CODEX_HOME
    ? path.resolve(env.CODEX_HOME)
    : defaultCodexHome;
  const platformSupported = supportedPlatforms.has(platform);
  const defaultCodexHomeSelected = configuredCodexHome === defaultCodexHome;
  return {
    status: platformSupported && defaultCodexHomeSelected ? 'PASS' : 'FAIL',
    platform,
    supported_platforms: [...supportedPlatforms],
    codex_home: defaultCodexHomeSelected ? 'default' : 'custom-unsupported',
    manual_action: !platformSupported
      ? 'Run setup only on a listed supported platform; no mutation was planned.'
      : !defaultCodexHomeSelected
        ? 'Unset CODEX_HOME or select the matching default ~/.codex owner; custom CODEX_HOME migration is not supported.'
        : null,
  };
}

export function assertSetupEnvironment(home, env = process.env, platform = process.platform) {
  const report = inspectSetupEnvironment(home, env, platform);
  if (!report.supported_platforms.includes(platform)) {
    throw new Error(`Setup platform ${platform} is not supported; supported platforms are ${report.supported_platforms.join(', ')}.`);
  }
  if (report.codex_home !== 'default') {
    throw new Error('CODEX_HOME must resolve to the selected home default ~/.codex before setup can mutate state.');
  }
  return report;
}
