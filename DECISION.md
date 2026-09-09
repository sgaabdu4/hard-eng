# Decisions

## Scaffold purpose

- This repository is the Hard Eng scaffold, added to existing projects so they can follow Hard Eng principles. Setup affects only the target repository.
- The scaffold checks for Hard Eng changes at agent session start and updates its installed setup under the update rules below.
- The scaffold adds gates for the entire project based on its actual tech stack. Other flows will be defined later.
- The scaffold sets up codebase-memory-mcp and the Context Mode plugin for Claude, Codex and Copilot using each client's supported project-local configuration.
- The scaffold prepends its `AGENTS.md` instructions to the project's `AGENTS.md`. Updates replace the previously added Hard Eng section, keeping it once at the top and preserving the project's own content below.

## Implementation checklist

Unchecked boxes are agreed requirements awaiting implementation and meaningful verification. Tick a box only after its required behavior is implemented and verified in the applicable environment. Previous implementation claims and CI runs do not prove this rebuild works.

Implement one agreed change at a time, with approval before each change. This document does not authorize committing, pushing, global installation or modifying other projects during the rebuild. The automatic update-commit behavior below is a requirement for the installed scaffold.

- [ ] Scaffold setup = install instructions, skills, stack-appropriate gates and agent integrations; activate enforcement at agent completion, Git pre-push and CI as part of setup.
- [ ] Project coverage = inspect the entire target project and configure gates for its actual supported tech stacks; execution scope follows the check-scope rules below.
- [ ] Project instructions = prepend Hard Eng's instructions to the target AGENTS.md; on updates, replace that section once at the top and preserve the project's content below.
- [ ] Existing configuration = preserve project configuration and local scaffold edits; combine settings where they can safely coexist, and ask before resolving conflicts. Do not silently overwrite existing skills, MCP configuration, gates or hooks.
- [ ] YAGNI enforcement = review actual changes against the user's request at completion; identify unsupported additions and remove them; automated scope/quality checks support this review but cannot certify semantic necessity by themselves.
- [ ] Addition rule = name the current agreed requirement and why existing code/direct commands are insufficient before adding machinery; leave it out otherwise. Tests must prove a required outcome or meaningful failure; optional expansion needs an explicit request. No extra justification files or enforcement framework.
- [ ] Gates = repository-owned `hard-eng.gates.json` declares applicable check commands.
- [ ] Gate execution = findings, missing tools, crashes, timeouts and incomplete scans fail; never swallow failures or report an unrun check as passed.
- [ ] Test quality = assert independently expected observable outcomes and relevant failure cases; regression tests must catch the original defect; merely executing code or checking mock calls does not prove the required behavior; coverage alone does not certify test quality.
- [ ] Runtime validation = no separate Zod/schema-library gate or mandatory dependency; test relevant valid/invalid external inputs through the existing test gate using the project's validation code.
- [ ] Scanner policy = all findings must be resolved, including pre-existing findings; no existing-debt baseline exemption.
- [ ] Git pre-push = enforce full applicable gates against the actual commits being pushed; failed gates or broken checks block the push while ordinary editing remains available. An uncommitted fix must not make committed code appear to pass.
- [ ] Remote enforcement = setup adds the CI workflow; CI independently runs applicable gates under the check-scope rules below. Missing/skipped expected checks fail the aggregate gate.
- [ ] Branch protection = ask for separate approval before changing remote branch rules. When approved, require the `hard-eng` check on protected `main`, including for administrators, with force-push and deletion disabled.
- [ ] Simplicity = no custom hash checks, fingerprint inventories or gate-result caching framework; use normal Git operations and the tools' native behavior.
- [ ] Tool versions = latest on every gate run; tool updates occur independently of Hard Eng updates.
- [ ] Check scope = full checks for affected packages + dependents + shared checks; uncertain impact → all supported packages.
- [ ] Scaffold-only updates = when an installed update changes only Hard Eng scaffold files, run relevant scaffold checks without running the target project's application checks or application CI. Changes affecting project code or project configuration run applicable project checks; mixed changes do not receive the scaffold-only exemption.
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
- [ ] MCP failure = warn and continue with other available tools when session-start readiness fails; do not deny edits or commands. Report unavailable integrations honestly and do not claim readiness passed.
- [ ] MCP storage = commit setup/configuration; keep credentials, generated indexes, caches and session data untracked.
- [ ] JS/TS formatting + linting = enforce Biome.
- [ ] Updates = check at every LLM session start; automatically install the newest main commit whose required checks passed.
- [ ] Update failure = report a failed update and continue normal work using the existing installed scaffold and its gates. Gate requirements remain active; MCP readiness failures follow the warning-only rule above.
- [ ] Update commits = after a successful update, automatically create a separate commit containing only the Hard Eng update; preserve unrelated work and ask before resolving conflicting local edits. Apply the scaffold-only check scope where eligible; do not automatically push.
- [ ] Scanner exceptions = allow narrowly scoped exceptions for proven false positives/intentional supported patterns; record reason + evidence; keep the rule active elsewhere.
- [ ] File size = maximum 700 physical lines per handwritten source/test file; exclude generated/vendor files; longer files require a file-specific reason + evidence explaining why splitting would harm maintainability; no blanket exemption for existing oversized files.
- [ ] Hook architecture = keep Hard Eng hook scripts in `.hooks` as the single source of truth. Client registrations call those scripts; one shared gate runner owns check execution and results without duplicated gate logic. Add scripts when their updater or gate command exists; do not restore the old coupled implementation wholesale or register missing commands.
- [ ] Hook registration = use `.claude/settings.json` for Claude, `.codex/hooks.json` for Codex and `.github/hooks/hard-eng.json` for Copilot. Map native events to the same shared scripts and preserve existing registrations without adding duplicates. Git pre-push calls the shared implementation through the target repository's Git hook location.
- [ ] AI hook lifecycle = Hard Eng hooks run at session start and completion. Session start checks updates + MCP readiness and warns without blocking work on failure. Add no extra Hard Eng PreToolUse or PostToolUse hooks; leave tool-use integration to Context Mode and wait until completion for automatic code checks. The agent can still run relevant checks while working.
- [ ] AI completion = verify required gates when completing code-changing work. Failed gates require another repair attempt; a crashed, timed-out or otherwise broken verification hook requires repair before claiming completion. Questions, honest blocked reports and user interruptions remain possible; prevent repeated stop-hook loops and never label incomplete verification as passed.
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

## Integration and enforcement verification

- [ ] MCP integrations = include context-mode + codebase-memory-mcp in repository-local setup; expose their tools to the active agent.
- [ ] MCP readiness = setup + session-start checks; prove real MCP calls, required Context Mode routing, and correct repository/index state for Codebase Memory.
- [ ] Service MCP readiness = verify intended Sentry organization/project or Appwrite endpoint/project with a read-only call; apply only to integrations the project uses.
- [ ] Full checks = task completion + pre-push + CI; run required checks directly each time under the check-scope rules, including the scaffold-only exemption.
- [ ] Hook capability = verify supported events and blocking semantics for each agent/version; test findings, crashes, timeouts and invalid responses; explicitly report unsupported enforcement and never treat a notification-only or failed hook as a working blocker.
- [ ] Container dependencies = extend OSV-Scanner to produced container images when the project builds them; scan image packages in addition to source dependency files; existing scope/version/exception and result-reuse policies apply.

## Acceptance proof

- Verify setup and repeat updates in an existing project, preserving its instructions, configuration and unrelated work; prove AGENTS.md contains only one Hard Eng section.
- Prove session-start updates, failure fallback, conflict handling and isolated update commits. Prove scaffold-only updates avoid application checks while project and mixed changes receive applicable checks.
- Verify real MCP calls and instruction/configuration loading in fresh Claude, Codex and Copilot sessions. Verify each client's supported project-local integration and blocking behavior before claiming support; do not substitute global activation.
- Verify completion, pre-push and CI enforcement with passing and failing changes. Verify remote branch protection only after separate approval.
- Verify session-start update/MCP failures leave edits and commands available; completion failures request repair without endless loops, and failed or broken pre-push checks block pushes. Verify all client registrations call the shared `.hooks` scripts without duplicated execution.
- Verify conditional service readiness and deployment/container scans in applicable projects or representative fixtures; do not claim success from absent integrations or empty scans.
