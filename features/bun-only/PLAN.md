# Switch Hard Eng from pnpm to Bun

Status: Complete

## Outcome + scope

Hard Eng requires Bun for JavaScript and TypeScript projects and uses Bun for its own JavaScript tools, CI bootstrap and MCP launches. Projects on pnpm, npm or yarn fail setup with one migration instruction. Node is no longer required. Non-goals: rewriting project lockfiles or settings, a dual pnpm mode, a migration guide.

## Repository context

Owners: `javascript_manager`, `workspace_members` and `package_script_invocation` in `.hooks/project_setup.py`; tool provisioning in `.hooks/tool_setup.py`; workflow generation and migration in `.hooks/ci_setup.py`; related tests and OSV checks in `.hooks/reports.py` and `.hooks/hard-eng.py`; the JavaScript template and `.github/workflows/hard-eng.yml`.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: The user asked to force-migrate Hard Eng to Bun, run the Codex adversarial review loop with GPT-6 Astra, open a PR and merge to main.

Hard Eng still never deletes or rewrites a project's lockfile; the project's agent follows the error. Hard Eng installs mise from its per-platform npm package, because the main package's install script needs npm. Tools with a `node` shebang run on Bun through a `node` link when Node is absent. A package that declares no dependencies needs no `bun.lock`, because Bun deletes empty lockfiles.

## Acceptance + steps

- [x] A Bun project passes every native gate with no Node on PATH.
- [x] A pnpm, npm or yarn project is rejected with the migration instruction.
- [x] A Bun workspace member inherits the root `bun.lock`; a dependency-free package needs none.
- [x] Pre-push runs `bun test --changed=<base>` and fails on a planted bug.
- [x] Stryker reports mutants on Bun with no Node.
- [x] The previous generated workflow migrates to the new template exactly.
- [x] Full gate passes.

## Baseline + execution

Result: Passed
Evidence: Main f31011db required pnpm and rejected `bun.lock`. Fixture projects in a temporary directory exercised each acceptance item.
Execution: One builder for source; one test-update agent; Codex adversarial review loop.

## Risks + recovery

Existing pnpm consumers fail setup until their agent migrates. Socket Firewall does not list Bun as supported. A pnpm-era mise launcher folder is replaced on first use. Recovery: revert the owning commits.

## ux_reference

N/A — hook and CI behaviour with no visual surface.

## Verification

Result: Passed
Evidence: Fixture runs recorded in `DECISION.md`; focused suites pass.
E2E: Temporary Bun project installed with `setup.py` and checked with `hard-eng.py check` on a Node-free PATH.

Delivery target: PR
Delivery: Pending — PR checks.
