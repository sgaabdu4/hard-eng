# New-project scaffolds, solution-style tsconfig fix and README rewrite

Status: Draft

## Outcome + scope

1. Setup no longer breaks a solution-style `tsconfig.json`, and the `types` gate checks every referenced config (issue sgaabdu4/hard-eng#295).
2. `setup.sh --new <stack>` (flutter, nextjs, opennext, vite) creates a complete greenfield project in an empty repository: official scaffold, Hard Eng starter files, exact pins, then normal setup, so every gate passes at once. PRODUCT.md and DESIGN.md stay for the agent to fill from the user's answers. The empty-repository message offers React + Vite and says when to suggest each web stack.
3. README rewritten in ~80% ASD-STE100 with clearer diagrams; confusing or stale text removed.
Non-goals: no flattening of user configs; no CI workflow or shipping budget for the new project; no new skill text.

## Repository context

Owners: `setup.py` `gate_config` (empty-repository message), [untrusted_input.py](../../.hooks/untrusted_input.py) `typescript_config` (adds the declaration), [hard-eng.py](../../.hooks/hard-eng.py) `validate_typescript` + [gitleaks_scan.py](../../.hooks/gitleaks_scan.py) `run_gate_command` (runs the `types` gate), README setup table. The setup message is the single owner of the web-type rule; HE Plan stays unchanged to add no always-loaded text.
Evidence: a fresh `bun create vite <dir> --template react-ts` scaffold plus this checkout's setup wrote `"files": [".hooks/untrusted-input.d.ts"]` into the root; `bun run build` then failed with TS6306 and TS6310 for both referenced configs, and `tsc --noEmit … --showConfig` listed only the declaration. `tsc -b` rejects `--strict` (TS5094), so the gate cannot use build mode. With Bun `minimumReleaseAge = 604800`, a `^8.3.4` Vite range failed `bun install`; `bun update --latest --exact` pinned every package to the newest allowed release and passed. `bun create vite . --template react-ts` works in a repository that holds only `.git`.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: The user asked for all three parts in one PR referencing the issue, with a Codex adversarial review loop (gpt-6-astra) before the PR. The user chose a setup option for the command and "every gate passes" as its scope (PRODUCT.md and DESIGN.md left to the agent). Commit, push and PR follow this repository's merge-when-green practice.
Decisions: per-reference declaration, not flattening (the Vite configs differ in `module`, `lib` and `types`). The runner expands one `types` gate into one `tsc -p <config>` run per referenced config, so gate configs and `configure_typing_checks` stay unchanged and existing installs are fixed by update. A root whose `files` holds only the declaration is an earlier setup's breakage and is repaired to `[]`. oxlint removal and version pins happen inside `--new`; the setup message also states them for agents that scaffold by hand. `bun update --latest --exact` can cross major versions (for example `@types/node` 24 to 26); this matches "newest version the release-age rule allows".

## Acceptance + steps

- [ ] Vite react-ts fixture: setup leaves the root solution `files` empty and adds the declaration to `tsconfig.app.json` and `tsconfig.node.json` → new test in `tests/test_untrusted_input.py`, red before the fix.
- [ ] Rerun on an earlier broken install (root `files` holds only the declaration) repairs the root and fills the references → same fixture test, red before.
- [ ] `types` gate on a solution root validates strictness and the declaration per referenced config, requires the union of their files to cover the sources, and runs `tsc -p` once per config → runner tests with a command-keyed fake, red before.
- [ ] Empty repository message names React + Vite, its scaffold, pin and oxlint steps and when to suggest each web type → `test_missing_project_manifest_fails` extended.
- [ ] README row matches the message → link/Markdown gates.
- [ ] Real run: fresh Vite scaffold plus this checkout's setup → `bun run build` passes; the `types` gate passes, then fails on a deliberate type error in `src/App.tsx`.
- [ ] `setup.sh --new <stack>` refuses a non-empty repository or an unknown stack and changes nothing → setup tests.
- [ ] `--new` applies the stack's starter files and pins on top of a scaffold → setup test with a stand-in scaffold command.
- [ ] Real E2E per stack (flutter, nextjs, opennext, vite): `setup.sh --new <stack>` in an empty repository, add stand-in PRODUCT.md/DESIGN.md, then `python3 .hooks/hard-eng.py check` passes every gate.
- [ ] README describes `--new`, the web-stack choice and every stage in plain short sentences; Markdown/link gates pass.
- [ ] Full `python3 .hooks/hard-eng.py check` passes.

## Baseline + execution

Result: Passed
Evidence: `python3 .hooks/hard-eng.py check --plan-stage Draft` on a1ec36b5 with only this plan added: exit 0; the base commit had passed required CI, so only the secret scan ran and passed.
Execution: Four Opus research agents, one per stack, find the smallest starter-file set that makes every gate pass on a fresh scaffold; the coordinator implements `--new` from their reports, then runs the real E2E per stack; Codex adversarial review loop after all changes; then PR.

## Risks + recovery

A solution root whose references point at missing files: setup raises with the line to add. Upstream scaffolds change over time and can break `--new`; the command fails loudly and the stack's E2E run is the proof to repeat. Recovery is reverting this branch.

## ux_reference

N/A — installer message, documentation and type-check wiring only; no product appearance.

## Verification

Result: Pending
Evidence: Pending
E2E: Required — real run of this checkout's setup on a fresh Vite react-ts scaffold, then `bun run build` and the `types` gate (pass, then fail on a deliberate type error); `setup.sh --new <stack>` for all four stacks, then a full passing `check` in each.

Delivery target: Merge
Delivery: Pending — PR CI, merge and merged-main CI.
