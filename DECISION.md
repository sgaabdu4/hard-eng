# Decisions

This file holds the scaffold's purpose, its current status and the requirements that are still open. Each enforced rule is defined once in the [requirement registry](.agents/skills/he/references/requirements.md). Dated verification history lives in Git history and in the merged PRs.

## Scaffold purpose

- This repository is the Hard Eng scaffold, added to existing projects so they can follow Hard Eng principles. Setup affects only the target repository.
- The scaffold checks for Hard Eng changes at agent session start and updates its installed setup under the update rules below.
- The scaffold adds gates for the entire project based on its actual tech stack.
- The scaffold supports Claude and Codex with applicable service integrations. Context Mode and Codebase Memory MCP are retired (user instruction, 2026-09-28).
- The scaffold prepends its `AGENTS.md` instructions to the project's `AGENTS.md`. Updates replace the previously added Hard Eng section, keeping it once at the top and preserving the project's own content below. Shared project rules use `AGENTS.md`; redundant Claude instruction wrappers are retired after preserving unique scoped rules.

## Current status

- Branches: feature PRs merge into `develop` after the `hard-eng` CI check passes. A release from `develop` to `main` runs the release canary once. `main` requires the `hard-eng` check, including for administrators; force pushes and deletion stay disabled.
- Cloud sessions in this repository load the same hooks, skill links and attribution settings that setup writes into a project.
- Learning: session and supported failure checkpoints request HE Learn; terse decisions live in `docs/adr/`. Hooks prompt judgment and cannot guarantee that a failure never recurs.
- Plans: Draft, Ready and Complete checks validate structure and declarations. They do not authenticate approval, evidence truth or delivery order. Each acceptance line names a test, a requirement ID or `N/A — reason`.
- This repository skips Git-history secret scanning with `scan_git_history: false` (user-approved). Current-file scanning stays required, and project templates keep history scanning on.
- Mutation runs report surviving mutants and never block.
- Skill guidance and passing gates do not certify every behavior.

Remaining acceptance gaps:

- Broken-hook enforcement: native clients do not all fail closed when a hook crashes or times out.
- Scanner completeness: a clean scanner report does not prove that the scanner examined every file or image layer. OSV can omit a malformed lockfile inside a container image and still succeed.
- Proof in real consuming projects for UI and device journeys, service integrations, container scans, the update lifecycle, test selection and performance budgets.
- Cloud containers cannot install gitleaks, osv-scanner, shellcheck or actionlint; CI runs those gates.

## Open requirements

Each item is agreed but not yet fully implemented or proven. Tick work happens in a feature plan; when a rule is enforced, add it to the registry and remove it here.

- [ ] Scaffold setup: install instructions, skills, stack-appropriate gates and agent integrations, and turn on enforcement at agent completion, pre-push and CI.
- [ ] Integration scope: change only the repository where setup runs, with project-local Claude and Codex MCP and hook configuration and no user-wide plugin activation.
- [ ] Gate results: findings, crashes and incomplete scans fail; an unrun check is never reported as passed; each scanner's result is verified.
- [ ] Test quality: tests assert independently expected outcomes and relevant failures; a regression test catches the original defect. Coverage and mock-call checks alone do not prove behavior.
- [ ] Tool versions: gates use the latest tool on every run, updated independently of Hard Eng.
- [ ] Updates: check at every session start and install the newest `main` commit whose required checks passed.
- [ ] Secret scanning: Gitleaks scans current files and Git history in every language, fully redacts secrets and fails on findings or errors.
- [ ] Source security: Semgrep scans JavaScript, TypeScript, Python, Dart and Flutter with applicable rules and fails on findings or scan errors.
- [ ] Scanner exceptions: only narrow exceptions for proven false positives or intended patterns, with reason and evidence; the rule stays active elsewhere.
- [ ] Focused test selection: reject command-line or configuration filters that shrink the expected Python, JavaScript or Dart test suite; scanner scopes cover the tests.
- [ ] AI hook lifecycle: session start checks updates and gives MCP readiness guidance; completion runs code checks; Claude PreToolUse hooks only deny foreground polling and note real-app previews on Artifact calls. See [the learning decision](docs/adr/0001-learning-prevention-and-decisions.md).
- [ ] AI completion: failed gates need another repair attempt; a broken verification hook needs repair before completion is claimed; repeated Stop loops are prevented.
- [ ] Full checks: pre-push and CI run every required check under the check-scope rules; task completion runs quick static gates on the session's own change (user decision, 2026-10-15).
- [ ] JavaScript and TypeScript gates: Biome, type checks, tests, applicable build and Fallow; React adds React Doctor.
- [ ] Dart and Flutter gates: Dart format, analyzer with configured lint plugins, tests, applicable build and Dart Decimate.
- [ ] Shared gates: secret scanning, dependency vulnerability checks and applicable integration tests.
- [ ] Generated source: when generated output is committed, regenerate it with the existing generator and check that it matches.
- [ ] Changed UI: a small runtime journey test plus applicable automated accessibility checks, reusing existing browser or device tests.
- [ ] Retired integrations: remove Context Mode and Codebase Memory MCP registrations, launchers and generated state during authorized adoption.
- [ ] MCP readiness: register applicable service tools; real calls against the intended project prove readiness; no unrelated startup probes.
- [ ] Service MCP readiness: verify the intended Sentry or Appwrite project with a read-only call, only for integrations the project uses.
- [ ] Container dependencies: scan produced container images with OSV-Scanner in addition to source dependency files.
- [ ] Bulk and async flows: add only the missing batching, queue-bound, cancellation and request-count regression checks to existing suites.
- [ ] Hot paths: review time and space complexity and add a representative scaling or operation-count check; add latency or memory budgets only for a real requirement.
