# Offer React + Vite and fix solution-style tsconfig setup

Status: Draft

## Outcome + scope

Empty-repository setup offers React + Vite (Bun) beside Next.js, with guidance on which web type fits, and setup no longer breaks a solution-style `tsconfig.json`; the `types` gate checks every referenced config. Non-goals: setup does not run the scaffold, edit package.json or replace oxlint by code; no flattening of user configs. Issue: sgaabdu4/hard-eng#295.

## Repository context

Owners: `setup.py` `gate_config` (empty-repository message), [untrusted_input.py](../../.hooks/untrusted_input.py) `typescript_config` (adds the declaration), [hard-eng.py](../../.hooks/hard-eng.py) `validate_typescript` + [gitleaks_scan.py](../../.hooks/gitleaks_scan.py) `run_gate_command` (runs the `types` gate), README setup table. The setup message is the single owner of the web-type rule; HE Plan stays unchanged to add no always-loaded text.
Evidence: a fresh `bun create vite <dir> --template react-ts` scaffold plus this checkout's setup wrote `"files": [".hooks/untrusted-input.d.ts"]` into the root; `bun run build` then failed with TS6306 and TS6310 for both referenced configs, and `tsc --noEmit … --showConfig` listed only the declaration. `tsc -b` rejects `--strict` (TS5094), so the gate cannot use build mode. With Bun `minimumReleaseAge = 604800`, a `^8.3.4` Vite range failed `bun install`; `bun update --latest --exact` pinned every package to the newest allowed release and passed. `bun create vite . --template react-ts` works in a repository that holds only `.git`.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: The user asked for both fixes in one PR referencing the issue, with a Codex adversarial review loop (gpt-6-astra) before the PR. Commit, push and PR follow this repository's merge-when-green practice.
Decisions: per-reference declaration, not flattening (the Vite configs differ in `module`, `lib` and `types`). The runner expands one `types` gate into one `tsc -p <config>` run per referenced config, so gate configs and `configure_typing_checks` stay unchanged and existing installs are fixed by update. A root whose `files` holds only the declaration is an earlier setup's breakage and is repaired to `[]`. oxlint removal and version pins are scaffold instructions in the setup message. `bun update --latest --exact` can cross major versions (for example `@types/node` 24 to 26); this matches "newest version the release-age rule allows".

## Acceptance + steps

- [ ] Vite react-ts fixture: setup leaves the root solution `files` empty and adds the declaration to `tsconfig.app.json` and `tsconfig.node.json` → new test in `tests/test_untrusted_input.py`, red before the fix.
- [ ] Rerun on an earlier broken install (root `files` holds only the declaration) repairs the root and fills the references → same fixture test, red before.
- [ ] `types` gate on a solution root validates strictness and the declaration per referenced config, requires the union of their files to cover the sources, and runs `tsc -p` once per config → runner tests with a command-keyed fake, red before.
- [ ] Empty repository message names React + Vite, its scaffold, pin and oxlint steps and when to suggest each web type → `test_missing_project_manifest_fails` extended.
- [ ] README row matches the message → link/Markdown gates.
- [ ] Real run: fresh Vite scaffold plus this checkout's setup → `bun run build` passes; the `types` gate passes, then fails on a deliberate type error in `src/App.tsx`.
- [ ] Full `python3 .hooks/hard-eng.py check` passes.

## Baseline + execution

Result: Passed
Evidence: `python3 .hooks/hard-eng.py check --plan-stage Draft` on a1ec36b5 with only this plan added: exit 0; the base commit had passed required CI, so only the secret scan ran and passed.
Execution: Single builder in this worktree; Codex adversarial review loop after all changes; then PR.

## Risks + recovery

A solution root whose references point at missing files: setup raises with the line to add, as it does for other configs it cannot extend. Recovery is reverting this branch.

## ux_reference

N/A — installer message, documentation and type-check wiring only; no product appearance.

## Verification

Result: Pending
Evidence: Pending
E2E: Required — real run of this checkout's setup on a fresh Vite react-ts scaffold, then `bun run build` and the `types` gate (pass, then fail on a deliberate type error).

Delivery target: Merge
Delivery: Pending — PR CI, merge and merged-main CI.
