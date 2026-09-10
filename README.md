<img src="assets/readme/hard-eng-hero.png" alt="Hard Eng" width="100%">

Repository-local engineering instructions, skills, checks, hooks and CI for Python, JavaScript/TypeScript and Dart/Flutter, including monorepos.

## Capabilities

- Detect supported packages; preserve project instructions and configuration; report conflicts.
- Require meaningful `PRODUCT.md` and `DESIGN.md`, baseline checks, nonempty tests, at least 70% executable-line coverage and a configured performance suite. Preserve stricter coverage requirements.
- Run full checks for affected packages, dependents and shared concerns; uncertain impact expands scope. Independent checks may run in parallel.
- Validate native exits and reports; reject findings and missing, stale or malformed evidence. Handwritten source/test files over 700 lines need a justified exception.
- Install pre-push checks for the actual pushed commits, GitHub Actions checks and agent session/completion hooks. Remote branch protection requires separate approval.
- Configure Context Mode and Codebase Memory; add Appwrite, Sentry, Dart and Marionette MCPs when applicable. Registration alone does not prove readiness.
- Provide CI-verified scaffold updates with conflict preservation and a separate local update commit; never automatically push. Scaffold-only updates avoid unrelated application checks.

## Checks

| Stack | Native tools |
|---|---|
| Python | Ruff, Pyrefly, pytest/coverage, Vulture, jscpd, Deptry, Import Linter |
| JavaScript/TypeScript | Biome, TypeScript, project tests/coverage, Fallow; React adds React Doctor |
| Dart/Flutter | Format, analyzer, tests/coverage, Dart Decimate |
| Shared / conditional | Gitleaks, OSV, Semgrep, Actionlint, Zizmor, ShellCheck and deployment checks |

Existing build, integration, UI and generator scripts participate where applicable. [Performance guidance](.agents/skills/he/references/gates.md) covers project-specific budgets and native reports; setup does not invent product benchmarks.

## Skills

- Work: [Hard Eng](.agents/skills/he/SKILL.md), [Research](.agents/skills/research/SKILL.md), [Code Review](.agents/skills/code-review/SKILL.md), [Codebase Design](.agents/skills/codebase-design/SKILL.md).
- Verification: [E2E](.agents/skills/e2e/SKILL.md), [Security Review](.agents/skills/security-review/SKILL.md), [Product Walkthrough Video](.agents/skills/product-walkthrough-video/SKILL.md).
- Stack guidance: [Appwrite Backend](.agents/skills/appwrite-backend/SKILL.md), [Building Flutter Apps](.agents/skills/building-flutter-apps/SKILL.md).
- Authoring: [Writing Great Skills](.agents/skills/writing-great-skills/SKILL.md). [Test quality](.agents/skills/he/references/testing.md) is shared by Hard Eng and Code Review.

Skills guide judgment; passing tools do not certify product behavior or test quality.

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

## Status

Native hook activation depends on client trust and behavior. Scanner completeness and application-specific UI/device, service, container and update-lifecycle acceptance remain open. See [current verification and remaining decisions](DECISION.md#current-status); local proof does not establish publication or deployment.
