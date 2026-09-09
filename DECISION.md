# Decisions

Ticks record locally implemented and verified work. Native agent enforcement, service authentication and remote delivery need the remaining proof listed below.

## Implemented and verified

- [ ] YAGNI enforcement = review actual changes against the user's request at completion; identify unsupported additions and remove them; automated scope/quality checks support this review but cannot certify semantic necessity by themselves.
- [ ] Addition rule = name the current agreed requirement and why existing code/direct commands are insufficient before adding machinery; leave it out otherwise. Tests must prove a required outcome or meaningful failure; optional expansion needs an explicit request. No extra justification files or enforcement framework.
- [ ] Gates = repository-owned `hard-eng.gates.json` declares applicable check commands.
- [ ] Gate execution = findings, missing tools, crashes, timeouts and incomplete scans fail; never swallow failures or report an unrun check as passed.
- [ ] Test quality = assert independently expected observable outcomes and relevant failure cases; regression tests must catch the original defect; merely executing code or checking mock calls does not prove the required behavior; coverage alone does not certify test quality.
- [ ] Runtime validation = no separate Zod/schema-library gate or mandatory dependency; test relevant valid/invalid external inputs through the existing test gate using the project's validation code.
- [ ] Scanner policy = all findings must be resolved, including pre-existing findings; no existing-debt baseline exemption.
- [ ] Git pre-push = enforce full applicable gates against the actual commits being pushed; an uncommitted fix must not make committed code appear to pass.
- [ ] Remote enforcement = CI independently runs the shared gates; protected `main` requires the `hard-eng` GitHub Actions check, including for administrators, with force-push and deletion disabled. Missing/skipped expected checks fail the aggregate gate. Published main run: [34312282272](https://github.com/sgaabdu4/hard-eng/actions/runs/34312282272).
- [ ] Simplicity = no custom hash checks, fingerprint inventories or gate-result caching framework; use normal Git operations and the tools' native behavior.
- [ ] Tool versions = latest on every gate run; tool updates occur independently of Hard Eng updates.
- [ ] Check scope = full checks for affected packages + dependents + shared checks; uncertain impact → all supported packages.
- [ ] Research skill = rebuild `skills/research` with codebase, comparison, external evidence, library/API and troubleshooting routes; derive coverage before recommendations; distinguish documented/tested/inferred/unknown claims; explain remaining gaps before claiming sufficiency; no old receipt scripts or mandatory paperwork.
- [ ] Python gates = Ruff format/lint/complexity + Pyrefly + pytest + Vulture + jscpd + deptry + conditional Import Linter; validate speed/compatibility on the first real repository.
- [ ] Python typing = enforce Pyrefly `preset = "strict"` + `check-unannotated-defs = true` across the applicable package scope; no broad ignores, disabled strict checks or Any substitutions to silence findings; existing narrow exception policy applies.
- [ ] Python complexity = explicitly enable Ruff C901 + PLR0912 + PLR0915; configure maximum complexity 10, branches 12 and statements 50 per function using Ruff's documented defaults; preserve stricter existing limits; existing narrow exception policy applies; preview-only nesting checks are not enabled by default.
- [ ] Python dependency declarations = deptry for supported dependency definitions; check missing/unused dependencies, direct use of transitive dependencies, production use of development-only dependencies and standard-library packages declared as dependencies; account narrowly for proven dynamic/plugin usage; missing or incomplete expected analysis fails.
- [ ] Python import structure = Import Linter for Python packages; check recursive sibling module/package cycles across the applicable scope; enforce layer/forbidden-import/independence contracts where the project defines those boundaries; do not invent a new architecture; missing or incomplete expected analysis fails; existing scope/version/exception policies apply.
- [ ] Secret scanning = Gitleaks for repository files + Git history across all languages; fully redact secrets in output; fail on findings/errors; existing scope/version/exception policies apply. User-approved exception: this Hard Eng repository skips Git-history scanning with `scan_git_history: false`; current-file scanning stays required and project templates keep history scanning enabled.
- [ ] Source security = Semgrep for JS/TS + Python + Dart/Flutter; applicable security rules; explicitly fail on findings and scan errors; existing scope/version/exception policies apply.
- [ ] Semgrep validation = prove applicable rules detect known unsafe examples and accept safe examples in each language; validate runtime on the first repository; Dart support is experimental and zero applicable rules is not a pass.
- [ ] Fresh implementation = no legacy adapters, migration machinery, historical exception lists or compatibility scaffolding. Keep only tests proving required behavior and meaningful failure cases.
- [ ] Product/design context = require root PRODUCT.md and DESIGN.md; if missing, study the repository and fill the bundled templates from evidence using product.md and Google's design.md convention, with Atomic Design for UI components. Missing/empty files and unfilled template prompts fail the gate; preserve existing documents.
- [ ] Installation = from the target project's root, run `curl -fsSL https://raw.githubusercontent.com/sgaabdu4/hard-eng/main/setup.sh | sh`; copy shared rules, skills and required gate code directly into that project. Canonical skills live in `.agents/skills`; Codex and Copilot discover them directly, only Claude needs links in `.claude/skills`. Preserve existing project files; no submodule, nested Git repository or global installation. The agent adapts missing gate configuration from repository evidence.
- [ ] Plugin scope = affect only the repository where setup runs. Claude uses its project-scoped Context Mode plugin; Codex uses project-local MCP and hook configuration because its plugin installer enables plugins user-wide. Codebase Memory uses each client's native MCP configuration. Native plugin caches are managed by the client; no user-wide plugin activation is added.
- [ ] Agent independence = Hard Eng is agent-agnostic; shared repository configuration, gate commands and results must not depend on a particular AI agent, provider or model; gates also run directly through the CLI and CI.
- [ ] YAGNI = ultra by default throughout Hard Eng; establish the requested behavior, reuse existing code, then prefer stdlib/native platform/existing dependencies before new code; no speculative features, abstractions, configuration or scaffolding; preserve explicit requirements, root-cause correctness and necessary verification.
- [ ] Languages = Dart/Flutter + Python + TypeScript/JavaScript/React only.
- [ ] Test execution = reject unexpectedly empty test runs and accidental focused tests; enforce through the existing test gate.
- [ ] Coverage = at least 70% executable-line coverage across each affected package's full production code; include files never executed by tests; use the existing test run; preserve stricter existing thresholds.
- [ ] Coverage integrity = exclude test/generated/vendor code, not handwritten production logic to inflate the result; missing, stale or incomplete coverage fails; report branch coverage separately where supported.
- [ ] Conditional MCPs = Sentry when the project uses Sentry; Appwrite when it uses Appwrite; detect actual integration from repository evidence.
- [ ] MCP failure = block normal project work; allow diagnosis + integration repair; resume only after readiness passes.
- [ ] MCP storage = commit setup/configuration; keep credentials, generated indexes, caches and session data untracked.
- [ ] JS/TS formatting + linting = enforce Biome.
- [ ] Updates = check at every LLM session start; automatically install the newest main commit whose required checks passed.
- [ ] Freshness = work cannot proceed until the required update succeeds.
- [ ] Update failure = allow diagnosis + scoped update/setup repair; block normal project changes until current.
- [ ] Update commits = separate automatic commit containing only the Hard Eng update; preserve unrelated work; stop on conflicting local edits.
- [ ] Scanner exceptions = allow narrowly scoped exceptions for proven false positives/intentional supported patterns; record reason + evidence; keep the rule active elsewhere.
- [ ] File size = maximum 700 physical lines per handwritten source/test file; exclude generated/vendor files; longer files require a file-specific reason + evidence explaining why splitting would harm maintainability; no blanket exemption for existing oversized files.
- [ ] Hook architecture = hooks belong to gate enforcement; one shared gate runner owns check execution and results; Git and agent-specific adapters invoke it without duplicating gate logic; map lifecycle responsibilities to each agent's supported events rather than requiring one agent's event names.
- [ ] AI hook lifecycle = session start checks updates + MCP readiness; before relevant actions enforce readiness/restrictions while allowing diagnosis/repair; after code changes invalidate affected results and optionally run quick checks; do not run full scans on every tool call.
- [ ] AI completion = verify required gate results when completing code-changing work; questions, honest blocked reports and user interruptions remain possible; prevent repeated stop-hook loops.
- [ ] Tool selection = prioritize fast execution while preserving required checks.
- [ ] JS/TS gates = Biome + type checks + tests + applicable build + Fallow; React adds React Doctor.
- [ ] Dart/Flutter gates = Dart format + analyzer/configured lint plugins + tests + applicable build + Dart Decimate.
- [ ] Duplication = Fallow for JS/TS, Dart Decimate for Dart, jscpd for Python; fail on reported duplicate-code findings/errors; no existing-debt baseline; exclude generated/vendor code and apply the existing narrow exception policy; do not silently skip large handwritten files.
- [ ] Shared gates = secret scanning + dependency vulnerability checks + applicable integration tests.
- [ ] Dependency vulnerability checks = OSV-Scanner for supported Dart/Flutter, JS/TS and Python dependency files; fail on findings/errors; no packages scanned is not a pass when dependencies are expected; existing scope/version/exception policies apply.
- [ ] GitHub Actions checks = Actionlint only in repositories using GitHub Actions; validate workflows as a shared gate; fail on findings/errors; existing scope/version/exception and result-reuse policies apply.
- [ ] CI security = Zizmor for GitHub Actions; check permissions, unsafe triggers and related security risks; use a mode that fails on findings/errors; narrowly account for the agreed automatic tool updates under the existing exception policy.
- [ ] Shell checks = ShellCheck when supported Bash/sh helper scripts exist; fail on findings/errors; existing scope/version/exception and result-reuse policies apply.
- [ ] Deployment configuration = Trivy configuration scanning when supported Dockerfiles/infrastructure configuration exists; explicitly fail on findings/errors; existing scope/version/exception and result-reuse policies apply.
- [ ] Lockfiles = validate declaration/lockfile consistency with the existing package manager during dependency changes + CI; no reinstall on every edit.
- [ ] Generated source = when committed, regenerate affected outputs with the existing generator and check consistency.
- [ ] Changed UI = small runtime journey test + applicable automated accessibility checks; reuse browser/device tests; no full-app crawl by default.
- [ ] Mutation testing = supported but optional; present scope + estimated runtime and obtain user acceptance before running.
- [ ] Mutation scope = complete changed production functions + relevant covering tests, including existing tests; explain when broader scope would help.

## Pending or partially implemented

- [ ] MCP integrations = include context-mode + codebase-memory-mcp in repository-local setup; expose their tools to the active agent.
- [ ] MCP readiness = setup + session-start checks; prove real MCP calls, required Context Mode routing, and correct repository/index state for Codebase Memory.
- [ ] Service MCP readiness = verify intended Sentry organization/project or Appwrite endpoint/project with a read-only call; apply only to integrations the project uses.
- [ ] Full checks = task completion + pre-push + CI; run required checks directly each time.
- [ ] Hook capability = verify supported events and blocking semantics for each agent/version; test findings, crashes, timeouts and invalid responses; explicitly report unsupported enforcement and never treat a notification-only or failed hook as a working blocker.
- [ ] Container dependencies = extend OSV-Scanner to produced container images when the project builds them; scan image packages in addition to source dependency files; existing scope/version/exception and result-reuse policies apply.

## Remaining proof

- MCP servers completed real tool calls, and native agent configuration plus lifecycle adapters pass local tests. Loading those configurations and proving enforcement in fresh Codex, Claude and Copilot sessions is still pending. Copilot hook timeouts fail open; Git and CI gates are required.
- Sentry/Appwrite detection and intended-project response checks are tested. This repository uses neither service, so authenticated service readiness needs an applicable project.
- The shared CI workflow passed on published main and the required `hard-eng` branch check is active. The deleted predecessor workflow is never accepted as proof for this rebuild.
- Produced-container scanning uses OSV's native image command and report validation; a real produced-image scan remains unverified because this repository produces no image. Trivy deployment scanning has passed safe/unsafe Dockerfile probes.
