<img src="assets/readme/hard-eng-hero.png" alt="Hard Eng: plan with one Feature Brief, build in an implement-verify loop, ship, and learn from evidence" width="100%">

Sets up project-specific gates, agent instructions, hooks and CI for Python, JavaScript/TypeScript and Dart/Flutter, including monorepos.

Missing baseline checks fail validation before tools run. Supported packages cannot disappear from the gate manifest; applicable workflow, shell, deployment, React and existing build/test scripts are checked too.

Every language package needs a performance suite with workload-specific assertions. Missing setup fails the gate. Native Lighthouse budgets, API thresholds and Python/Dart/Flutter test contracts are described in the [performance gate guidance](.agents/skills/he/references/gates.md). Setup recognizes existing Lighthouse configuration; other templates require the project's performance tests and budgets to be configured.

## Install

Run from your project's Git root, locally or in a cloud terminal:

```sh
curl -fsSL https://raw.githubusercontent.com/sgaabdu4/hard-eng/main/setup.sh | sh
```

No GitHub account or existing Hard Eng checkout needed. Requires Git, curl and Python 3.12+. Running gates also requires uv, pnpm and the project's SDKs; Dart Decimate requires Cargo. Existing configuration conflicts are reported for review.

## Check

```sh
python3 .hooks/hard-eng.py check
```
