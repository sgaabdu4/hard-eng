<img src="assets/readme/hard-eng-hero.png" alt="Hard Eng" width="100%">

Repository-local engineering instructions, skills, checks, hooks and CI for Python, JavaScript/TypeScript and Dart/Flutter, including monorepos.

## Capabilities

- Detect supported packages; preserve project instructions and configuration; report conflicts.
- Require meaningful `PRODUCT.md` and `DESIGN.md`, baseline checks, nonempty tests, at least 70% executable-line coverage and a configured performance suite. Preserve stricter coverage requirements.
- Check task `PLAN.md` structure, reasoned N/A entries and declared readiness/completion evidence through the existing runner; see [plan checks](.agents/skills/he/references/gates.md#plan-checks). Evidence truth and user authorization still require review.
- Run full checks for affected packages, dependents and shared concerns; uncertain impact expands scope. Independent checks may run in parallel.
- Validate native exits and reports; reject findings and missing, stale or malformed evidence. Handwritten source/test files over 700 lines need a justified exception.
- Install pre-push checks for the actual pushed commits, GitHub Actions checks and agent session/prompt/tool/completion hooks. Remote branch protection requires separate approval.
- Prompt evidence-based learning throughout work: prefer existing deterministic prevention, use skills as a last resort, and capture lasting accepted decisions in terse `docs/adr/` records. Routine progress creates no learning artifact; hooks do not certify semantic judgment.
- Require a configured [shipping contract](.agents/skills/he-ship/references/checks.md) for pushes and completed delivery plans; verify GitHub PR/check identity, required UI attachments and deployment proof; guard merge and task-worktree cleanup. Direct base pushes and over-budget pre-push checks fail. Visual relevance and external authority still require judgment.
- Configure Context Mode and Codebase Memory; add Appwrite, Sentry, Dart and Marionette MCPs when applicable. Registration alone does not prove readiness.
- Provide CI-verified scaffold updates with conflict preservation and a separate local update commit; never automatically push. Completion and shipping check installed-version freshness without changing files. Scaffold-only updates avoid unrelated application checks.

## Checks

| Stack | Native tools |
|---|---|
| Python | Ruff, Pyrefly, pytest/coverage, Vulture, jscpd, Deptry, Import Linter |
| JavaScript/TypeScript | Biome, TypeScript, project tests/coverage, Fallow; React adds React Doctor |
| Dart/Flutter | Format, analyzer, tests/coverage, Dart Decimate |
| Shared / conditional | Gitleaks, OSV, Semgrep, Actionlint, Zizmor, ShellCheck and deployment checks |

Existing build, integration, UI and generator scripts participate where applicable. [Performance guidance](.agents/skills/he/references/gates.md) covers project-specific budgets and native reports; setup does not invent product benchmarks.

## Skills

- Work: [Hard Eng](.agents/skills/he/SKILL.md), [HE Plan](.agents/skills/he-plan/SKILL.md) (scaled planning, Wayfinder and repository-grounded UX references), [HE Build](.agents/skills/he-build/SKILL.md), [HE Ship](.agents/skills/he-ship/SKILL.md), [Research](.agents/skills/research/SKILL.md), [Code Review](.agents/skills/code-review/SKILL.md), [Codebase Design](.agents/skills/codebase-design/SKILL.md).
- Verification: [E2E](.agents/skills/e2e/SKILL.md), [Security Review](.agents/skills/security-review/SKILL.md), [Product Walkthrough Video](.agents/skills/product-walkthrough-video/SKILL.md).
- Stack guidance: [Appwrite Backend](.agents/skills/appwrite-backend/SKILL.md), [Building Flutter Apps](.agents/skills/building-flutter-apps/SKILL.md).
- Authoring: [Writing Great Skills](.agents/skills/writing-great-skills/SKILL.md). [Test quality](.agents/skills/he/references/testing.md) is shared by Hard Eng and Code Review.

[HE Learn](.agents/skills/he-learn/SKILL.md) routes repeated failures to prevention and lasting decisions to terse ADRs. Skills guide judgment; passing tools do not certify product behavior or test quality.

## Install

The same command installs a new project or uses the supported updater for a recorded installation. Updates select a CI-verified revision and create a local commit without pushing; conflicting local edits remain protected. Run it before editing, not concurrently in the background.

When an update changes project configuration, its isolated candidate runs the application gates without requiring a task plan to be completed first. This verifies the update only; normal completion, push and shipping checks still require their task evidence.

Codex requires separate trust for new or changed hooks, even in a trusted project. Review them with `/hooks`, then verify the startup result in a new session before claiming automatic updates or completion enforcement. The installer does not grant trust to its own hooks. See the [official hook trust instructions](https://learn.chatgpt.com/docs/hooks).

Run from your project's Git root, locally or in a cloud terminal:

```sh
curl -fsSL https://raw.githubusercontent.com/sgaabdu4/hard-eng/main/setup.sh | sh
```

No GitHub account or existing Hard Eng checkout needed. Requires Git, curl and Python 3.12+. Running gates also requires uv, pnpm and the project's SDKs; Dart Decimate requires Cargo. Existing configuration conflicts are reported for review.

Classifying omitted type-only TypeScript coverage uses Node 22.13+ [native type stripping](https://nodejs.org/api/module.html#modulestriptypescripttypescode-options). Executable or unsupported sources still require coverage records.

Omitted Dart declaration-only coverage uses the analyzer from the package's existing `.dart_tool/package_config.json`. The parser reads source as data; it does not execute it. Only proven directive/constant/type declarations are exempt. Missing or incompatible analyzer support leaves coverage required, as do runtime methods, getters, constructors and initializers.

## Check

```sh
python3 .hooks/hard-eng.py check
```

## Status

Native hook activation depends on client trust and behavior. Scanner completeness and application-specific UI/device, service, container and update-lifecycle acceptance remain open. See [current verification and remaining decisions](DECISION.md#current-status); local proof does not establish publication or deployment.

For the standard Husky `.husky/_/pre-push` forwarding shim, setup preserves the shim and Git configuration and manages `.husky/pre-push` with a shell-compatible launcher. Existing canonical Hard Eng launchers migrate; custom hooks remain protected conflicts.

The updater commits that launcher together with the scaffold and revision marker. If the installed updater itself is the failing component, invoke `update.update(target_root)` from a fetched, CI-verified source checkout's `.hooks/update.py` for the repair. This uses the same verified, isolated transaction; manually copying hooks or advancing the marker is not adoption proof.

For a new task branch, pre-push resolves the configured shipping base on `origin` and fetches that exact commit for comparison, while checking the exact pushed revision. An unavailable base blocks the push. Existing branches retain their advertised remote-tip comparison; direct base pushes remain blocked.
