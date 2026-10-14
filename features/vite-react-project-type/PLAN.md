# New-project scaffolds, solution-style tsconfig fix and README rewrite

Status: Complete

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
Decisions: starter files live in `.agents/starters/<stack>/`: discovery skips `.agents` and setup installs only `.agents/skills`, so they never reach projects. Scaffold tools are pinned (create-vite 9.2.1, create-next-app 16.4.0, create-cloudflare 2.73.3 with the OpenNext template at a fixed commit) so stored starter files match their template. OpenNext keeps the template's `next` release, because newer releases build but return HTTP 500 on the Worker. OpenNext generates only Worker binding types (`--include-runtime=false`) with `@cloudflare/workers-types`, because Hard Eng's Bun shim makes the full `wrangler types` fetch a parked domain. OpenNext adds a `sharp >=0.35.5` floor until wrangler 4.149 clears the release-age window. Per-reference declaration, not flattening (the Vite configs differ in `module`, `lib` and `types`). The runner expands one `types` gate into one `tsc -p <config>` run per referenced config, so gate configs and `configure_typing_checks` stay unchanged and existing installs are fixed by update. A root whose `files` holds only the declaration is an earlier setup's breakage and is repaired to `[]`. oxlint removal and version pins happen inside `--new`; the setup message also states them for agents that scaffold by hand. `bun update --latest --exact` can cross major versions (for example `@types/node` 24 to 26); this matches "newest version the release-age rule allows".

## Acceptance + steps

- [x] Vite react-ts fixture: setup leaves the root solution `files` empty and adds the declaration to each referenced config → `test_fresh_vite_install_keeps_the_solution_tsconfig_buildable`, red before the fix.
- [x] Rerun on an earlier broken install repairs the root and fills the references → `test_update_repairs_a_solution_tsconfig_an_earlier_setup_broke`, red before.
- [x] `types` gate on a solution root validates each referenced config, requires the union of their files to cover the sources, and runs `tsc -p` once per config → `test_types_gate_checks_each_config_a_solution_tsconfig_references`, red before.
- [x] Next.js route types exist before `tsc` on a clean checkout (found by the Next.js research run) → `test_types_gate_writes_next_route_types_before_a_clean_check`, red before.
- [x] A Flutter app's performance gate runs without `package:test` (found by the Flutter research run) → `test_flutter_performance_suite_runs_without_package_test`, red before.
- [x] Empty repository message offers React + Vite, says when to suggest each web stack, and names `--new STACK` → `test_missing_project_manifest_fails`.
- [x] `--new` refuses a non-empty repository and changes nothing; argparse rejects an unknown stack → `test_new_project_refuses_a_repository_that_holds_files`.
- [x] `--new` applies starter files, removes the template's other linter, pins, and commits → `test_vite_starter_replaces_oxlint_and_pins_after_the_scaffold`, `test_opennext_keeps_the_scaffold_next_release_after_the_upgrade`, `test_flutter_pins_each_any_constraint_to_the_resolved_version`.
- [x] Real E2E per stack: `sh setup.sh <checkout> --new <stack>` in an empty repository, stand-in PRODUCT.md/DESIGN.md committed, then `python3 .hooks/hard-eng.py check` passes every gate → vite 15/15, nextjs 15/15, opennext 15/15, flutter 10/10.
- [x] Real run: the Vite project's types gate fails on a deliberate type error in `src/App.tsx` and in `tests/bundle.test.ts`, and passes once removed.
- [x] README describes `--new`, the web-stack choice and every stage in plain short sentences with simpler diagrams.
- [x] Follow-up (user: "fix all the problems"): Biome leaves `linguist-generated` files out, like the size and comment checks → `test_javascript_file_scope_keeps_application_tests_and_declarations` extended, red before; the OpenNext starter drops its Biome format step and still passes 15/15.
- [x] The Bun shim runs wrangler and miniflare on Node when Node is installed → `test_node_runs_on_bun_except_for_cloudflare_tools`, red before; real `wrangler types` through the shim wrote the full 16,248-line file instead of 73 lines of parked-domain HTML.
- [x] Solution detection uses effective file lists after `extends` → `test_a_root_is_a_solution_only_when_its_effective_file_lists_are_empty`, red before.
- [x] Fresh clones of the Vite (15/15), Next.js (15/15) and Flutter (10/10) starters pass the full check after install; the Flutter starter passes a real integration run on macOS desktop (0, then 1 after a tap).
- [x] Flutter starter without the placeholder `Crash` facade, on flutter_skill_lints ^0.13.4 (crash rule fires only with error reporting; `prefer_type_over_var` restored, user decision: ban `var`, keep inferred `final`) and the Flutter skill pinned at v5.12.2 → new project and fresh clone 10/10; a deliberate `var` failed types-lint with `prefer_type_over_var`.
- [x] A pushed branch whose old remote tip is not an ancestor (a merged `hard-eng/update` branch left on the remote) is diffed from its branch point, so `update-pr` passes as scaffold-only instead of demanding a plan → `test_push_base_ignores_a_merged_update_branch_left_on_the_remote`, red before (returned the stale tip); found by the lint-package run and reproduced end to end in a scratch project.
- [x] Full `python3 .hooks/hard-eng.py check` passes.

## Baseline + execution

Result: Passed
Evidence: `python3 .hooks/hard-eng.py check --plan-stage Draft` on a1ec36b5 with only this plan added: exit 0; the base commit had passed required CI, so only the secret scan ran and passed.
Execution: Four Opus research agents, one per stack, find the smallest starter-file set that makes every gate pass on a fresh scaffold; the coordinator implements `--new` from their reports, then runs the real E2E per stack; Codex adversarial review loop after all changes; then PR.

## Risks + recovery

A solution root whose references point at missing files: setup raises with the line to add. Upstream scaffolds change over time and can break `--new`; the command fails loudly and the stack's E2E run is the proof to repeat. Recovery is reverting this branch.

## ux_reference

N/A — installer message, documentation and type-check wiring only; no product appearance.

## Verification

Result: Passed
Evidence: Focused tests went red before each fix and green after. This repo's Draft check passed every gate (line coverage above 90 percent). After the final code change, `sh setup.sh <checkout> --new <stack>` plus a full `check` passed in fresh repositories: vite 15/15, nextjs 15/15, opennext 15/15 (also from a fresh clone, plus a local `wrangler dev` 200 on `/`), flutter 10/10. Real-compiler probes: a composite library that is not strict is rejected; strict composites build and check. Codex adversarial review (gpt-6-astra) ran 12 rounds, and every finding was addressed with a regression test. Two were first deferred, then fixed in a later round: the root to app to library reference chain (round 5), and an explicit `-p` project whose composite references were unchecked (round 10, by requiring strict, checkJs with allowJs, and no noCheck in every composite config the build compiles, and by failing the gate when `tsc -b` fails). A real `uv init` and `uv lock` repository installs with this setup.
E2E: Passed — `setup.sh --new` for all four stacks, then a full passing `check` in each; the Vite types gate failed on deliberate type errors in `src` and `tests`, then passed once removed.

Delivery target: Merge
Delivery: Pending — PR CI, merge and merged-main CI.
