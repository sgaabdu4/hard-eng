<img src="assets/readme/hard-eng-hero.png" alt="Hard Eng: plan with one Feature Brief, build in an implement-verify loop, ship, and learn from evidence" width="100%">

Sets up project-specific gates, agent instructions, hooks and CI for Python, JavaScript/TypeScript and Dart/Flutter, including monorepos.

## Install

The rebuilt installer is not yet published. Once released, run from your project's Git root, locally or in a cloud terminal:

```sh
curl -fsSL https://raw.githubusercontent.com/sgaabdu4/hard-eng/main/setup.sh | sh
```

No GitHub account or existing Hard Eng checkout needed. Requires Git, curl and Python 3.12+. Running gates also requires uv, pnpm and the project's SDKs; Dart Decimate requires Cargo. Existing configuration conflicts are reported for review.

## Check

```sh
python3 .hooks/hard-eng.py check
```
