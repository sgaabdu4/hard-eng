# Decisions

Ticks record locally implemented and verified work. Native agent enforcement, service authentication and remote delivery need the remaining proof listed below.

## Implemented and verified

- [x] YAGNI enforcement = review actual changes against the user's request at completion; identify unsupported additions and remove them; automated scope/quality checks support this review but cannot certify semantic necessity by themselves.
- [x] Addition rule = name the current agreed requirement and why existing code/direct commands are insufficient before adding machinery; leave it out otherwise. Tests must prove a required outcome or meaningful failure; optional expansion needs an explicit request. No extra justification files or enforcement framework.
- [x] Gates = repository-owned `hard-eng.gates.json` declares applicable check commands.
- [x] Gate execution = findings, missing tools, crashes, timeouts and incomplete scans fail; never swallow failures or report an unrun check as passed.
- [x] Test quality = assert independently expected observable outcomes and relevant failure cases; regression tests must catch the original defect; merely executing code or checking mock calls does not prove the required behavior; coverage alone does not certify test quality.
- [x] Runtime validation = no separate Zod/schema-library gate or mandatory dependency; test relevant valid/invalid external inputs through the existing test gate using the project's validation code.
- [x] Scanner policy = all findings must be resolved, including pre-existing findings; no existing-debt baseline exemption.
- [x] Git pre-push = enforce full applicable gates against the actual commits being pushed; an uncommitted fix must not make committed code appear to pass.
- [x] Simplicity = no custom hash checks, fingerprint inventories or gate-result caching framework; use normal Git operations and the tools' native behavior.
- [x] Tool versions = latest on every gate run; tool updates occur independently of Hard Eng updates.
- [x] Check scope = full checks for affected packages + dependents + shared checks; uncertain impact → all supported packages.
- [x] Research skill = rebuild `skills/research` with codebase, comparison, external evidence, library/API and troubleshooting routes; derive coverage before recommendations; distinguish documented/tested/inferred/unknown claims; explain remaining gaps before claiming sufficiency; no old receipt scripts or mandatory paperwork.
- [x] Python gates = Ruff format/lint/complexity + Pyrefly + pytest + Vulture + jscpd + deptry + conditional Import Linter; validate speed/compatibility on the first real repository.
- [x] Python typing = enforce Pyrefly `preset = "strict"` + `check-unannotated-defs = true` across the applicable package scope; no broad ignores, disabled strict checks or Any substitutions to silence findings; existing narrow exception policy applies.
- [x] Python complexity = explicitly enable Ruff C901 + PLR0912 + PLR0915; configure maximum complexity 10, branches 12 and statements 50 per function using Ruff's documented defaults; preserve stricter existing limits; existing narrow exception policy applies; preview-only nesting checks are not enabled by default.
- [x] Python dependency declarations = deptry for supported dependency definitions; check missing/unused dependencies, direct use of transitive dependencies, production use of development-only dependencies and standard-library packages declared as dependencies; account narrowly for proven dynamic/plugin usage; missing or incomplete expected analysis fails.
- [x] Python import structure = Import Linter for Python packages; check recursive sibling module/package cycles across the applicable scope; enforce layer/forbidden-import/independence contracts where the project defines those boundaries; do not invent a new architecture; missing or incomplete expected analysis fails; existing scope/version/exception policies apply.
- [x] Secret scanning = Gitleaks for repository files + Git history across all languages; fully redact secrets in output; fail on findings/errors; existing scope/version/exception policies apply. User-approved exception: this Hard Eng repository skips Git-history scanning with `scan_git_history: false`; current-file scanning stays required and project templates keep history scanning enabled.
- [x] Source security = Semgrep for JS/TS + Python + Dart/Flutter; applicable security rules; explicitly fail on findings and scan errors; existing scope/version/exception policies apply.
- [x] Semgrep validation = prove applicable rules detect known unsafe examples and accept safe examples in each language; validate runtime on the first repository; Dart support is experimental and zero applicable rules is not a pass.
- [x] Fresh implementation = no legacy adapters, migration machinery, historical exception lists or compatibility scaffolding. Keep only tests proving required behavior and meaningful failure cases.
- [x] Product/design context = require root PRODUCT.md and DESIGN.md; if missing, study the repository and fill the bundled templates from evidence using product.md and Google's design.md convention, with Atomic Design for UI components. Missing/empty files and unfilled template prompts fail the gate; preserve existing documents.
- [x] Installation = run from the target project's root: `git submodule add https://github.com/sgaabdu4/hard-eng.git .hard-eng && ./.hard-eng/setup.sh --agent codex`; configure the wrapper inside that repository, commit it with the project, and let the agent adapt missing gate configuration from repository evidence; no global installation.
- [x] Agent independence = Hard Eng is agent-agnostic; shared repository configuration, gate commands and results must not depend on a particular AI agent, provider or model; gates also run directly through the CLI and CI.
- [x] YAGNI = ultra by default throughout Hard Eng; establish the requested behavior, reuse existing code, then prefer stdlib/native platform/existing dependencies before new code; no speculative features, abstractions, configuration or scaffolding; preserve explicit requirements, root-cause correctness and necessary verification.
- [x] Languages = Dart/Flutter + Python + TypeScript/JavaScript/React only.
- [x] Test execution = reject unexpectedly empty test runs and accidental focused tests; enforce through the existing test gate.
- [x] Coverage = at least 70% executable-line coverage across each affected package's full production code; include files never executed by tests; use the existing test run; preserve stricter existing thresholds.
- [x] Coverage integrity = exclude test/generated/vendor code, not handwritten production logic to inflate the result; missing, stale or incomplete coverage fails; report branch coverage separately where supported.
- [x] Conditional MCPs = Sentry when the project uses Sentry; Appwrite when it uses Appwrite; detect actual integration from repository evidence.
- [x] MCP failure = block normal project work; allow diagnosis + integration repair; resume only after readiness passes.
- [x] MCP storage = commit setup/configuration; keep credentials, generated indexes, caches and session data untracked.
- [x] JS/TS formatting + linting = enforce Biome.
- [x] Updates = check at every LLM session start; automatically install the newest main commit whose required checks passed.
- [x] Freshness = work cannot proceed until the required update succeeds.
- [x] Update failure = allow diagnosis + scoped update/setup repair; block normal project changes until current.
- [x] Update commits = separate automatic commit containing only the Hard Eng update; preserve unrelated work; stop on conflicting local edits.
- [x] Scanner exceptions = allow narrowly scoped exceptions for proven false positives/intentional supported patterns; record reason + evidence; keep the rule active elsewhere.
- [x] File size = maximum 700 physical lines per handwritten source/test file; exclude generated/vendor files; longer files require a file-specific reason + evidence explaining why splitting would harm maintainability; no blanket exemption for existing oversized files.
- [x] Hook architecture = hooks belong to gate enforcement; one shared gate runner owns check execution and results; Git and agent-specific adapters invoke it without duplicating gate logic; map lifecycle responsibilities to each agent's supported events rather than requiring one agent's event names.
- [x] AI hook lifecycle = session start checks updates + MCP readiness; before relevant actions enforce readiness/restrictions while allowing diagnosis/repair; after code changes invalidate affected results and optionally run quick checks; do not run full scans on every tool call.
- [x] AI completion = verify required gate results when completing code-changing work; questions, honest blocked reports and user interruptions remain possible; prevent repeated stop-hook loops.
- [x] Tool selection = prioritize fast execution while preserving required checks.
- [x] JS/TS gates = Biome + type checks + tests + applicable build + Fallow; React adds React Doctor.
- [x] Dart/Flutter gates = Dart format + analyzer/configured lint plugins + tests + applicable build + Dart Decimate.
- [x] Duplication = Fallow for JS/TS, Dart Decimate for Dart, jscpd for Python; fail on reported duplicate-code findings/errors; no existing-debt baseline; exclude generated/vendor code and apply the existing narrow exception policy; do not silently skip large handwritten files.
- [x] Shared gates = secret scanning + dependency vulnerability checks + applicable integration tests.
- [x] Dependency vulnerability checks = OSV-Scanner for supported Dart/Flutter, JS/TS and Python dependency files; fail on findings/errors; no packages scanned is not a pass when dependencies are expected; existing scope/version/exception policies apply.
- [x] GitHub Actions checks = Actionlint only in repositories using GitHub Actions; validate workflows as a shared gate; fail on findings/errors; existing scope/version/exception and result-reuse policies apply.
- [x] CI security = Zizmor for GitHub Actions; check permissions, unsafe triggers and related security risks; use a mode that fails on findings/errors; narrowly account for the agreed automatic tool updates under the existing exception policy.
- [x] Shell checks = ShellCheck when supported Bash/sh helper scripts exist; fail on findings/errors; existing scope/version/exception and result-reuse policies apply.
- [x] Deployment configuration = Trivy configuration scanning when supported Dockerfiles/infrastructure configuration exists; explicitly fail on findings/errors; existing scope/version/exception and result-reuse policies apply.
- [x] Lockfiles = validate declaration/lockfile consistency with the existing package manager during dependency changes + CI; no reinstall on every edit.
- [x] Generated source = when committed, regenerate affected outputs with the existing generator and check consistency.
- [x] Changed UI = small runtime journey test + applicable automated accessibility checks; reuse browser/device tests; no full-app crawl by default.
- [x] Mutation testing = supported but optional; present scope + estimated runtime and obtain user acceptance before running.
- [x] Mutation scope = complete changed production functions + relevant covering tests, including existing tests; explain when broader scope would help.

## Pending or partially implemented

- [ ] MCP integrations = include context-mode + codebase-memory-mcp in repository-local setup; expose their tools to the active agent.
- [ ] MCP readiness = setup + session-start checks; prove real MCP calls, required Context Mode routing, and correct repository/index state for Codebase Memory.
- [ ] Service MCP readiness = verify intended Sentry organization/project or Appwrite endpoint/project with a read-only call; apply only to integrations the project uses.
- [ ] Full checks = task completion + pre-push + CI; run required checks directly each time.
- [ ] Hook capability = verify supported events and blocking semantics for each agent/version; test findings, crashes, timeouts and invalid responses; explicitly report unsupported enforcement and never treat a notification-only or failed hook as a working blocker.
- [ ] Remote enforcement = local Git/AI hooks can be bypassed; CI independently runs the shared gates, with required checks on protected branches and deliberate bypass settings; missing/skipped expected checks must not produce a successful aggregate gate result.
- [ ] Container dependencies = extend OSV-Scanner to produced container images when the project builds them; scan image packages in addition to source dependency files; existing scope/version/exception and result-reuse policies apply.

## Remaining proof

- MCP servers completed real tool calls, and native agent configuration plus lifecycle adapters pass local tests. Loading those configurations and proving enforcement in fresh Codex, Claude and Copilot sessions is still pending. Copilot hook timeouts fail open; Git and CI gates are required.
- Sentry/Appwrite detection and intended-project response checks are tested. This repository uses neither service, so authenticated service readiness needs an applicable project.
- The shared CI workflow is implemented locally. Publish it, obtain a successful main run and configure the required `hard-eng` branch check before claiming remote enforcement or making this rebuild available to the updater. The deleted predecessor workflow is never accepted as proof for this rebuild.
- Produced-container scanning uses OSV's native image command and report validation; a real produced-image scan remains unverified because this repository produces no image. Trivy deployment scanning has passed safe/unsafe Dockerfile probes.
