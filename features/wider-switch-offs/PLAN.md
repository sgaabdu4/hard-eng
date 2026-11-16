# Close the wider off switches

Status: Ready

## Outcome + scope

Hard Eng refuses the wider off switches that still pass after plan 2: turning off the Git-history secret scan, Gitleaks ignore entries outside one narrow rule, Rust lint attributes, the Fallow `dead-code` subcommand and raised or ignored Fallow health settings, ruff ignore settings and a nested Dart settings file that drops the package's lints; refusals name the `linguist-generated` route; Hard Eng's own history scan goes back on in the same change. Non-goals: the project fix PRs (`features/strict-rollout/PLAN.md` runs them; Baseline lists which ids need more work), any exemption for flutter_skill_lints, ruff `exclude` lists and the `fallow architecture` command form (reported, not planned here).

## Sources + coverage

Sources: the coordinator's planning brief of 2026-11-16 with the owner's design calls 1 to 7 and rules, and its added case on Hard Eng's own `scan_git_history: false`, read in full.
Reviewer: N/A — one small source; the brief forbids subagents in this planning run, so the coordinator may start a second reader before the build.
Deliverables: None — Hard Eng code, tests and text only.

- Owner rule, no suppression, ignore comment, allowlist entry or raised limit: In scope — no raised limit is added anywhere in this change
- Owner rule, a finding that shows a rule can be dodged is never declined: In scope — Proposal row's dodge form is refused
- Design call 1, history scan off: In scope — `"scan_git_history": false` in `hard-eng.gates.json` is refused
- Design call 1, the narrow Gitleaks entry rule: In scope — entry passes only when today's scan finds it
- Design call 1, every other entry and every `.gitleaks.toml` allowlist stay refused: In scope — allowlist and every other entry stay refused
- Added case, Hard Eng's own history scan: In scope — Hard Eng's own `hard-eng.gates.json` drops the key
- Design call 2, Rust: In scope — Rust `#[allow(`, `#![allow(` and `#[expect(` are switch-offs
- Design call 3, Fallow subcommand: In scope — Fallow gate that runs the `dead-code` subcommand without health fails
- Design call 3, Fallow settings: In scope — Fallow settings file with a health limit above Fallow's default
- Design call 4, Python: In scope — `ignore`, `extend-ignore` and `per-file-ignores`
- Design call 5, Dart: In scope — nested `analysis_options.yaml` inside a package must reach the package's own `analysis_options.yaml`
- Design call 6, message: In scope — refusal names the `linguist-generated` route
- Design call 7, flutter_skill_lints: In scope — flutter_skill_lints gets no Hard Eng exemption
- Counts per id and the ids that need more work: In scope — each id that needs more work is named in Baseline
- Rust spellings of the same switch (`#![cfg_attr(…, allow(…))]`, a Cargo `[lints]` level `allow`, a `#[ignore]` test): Proposal — refuse them with design call 2; yes — user, chat 2026-11-15 ("HARD ENG IS HARD FOR A REASON!!!" on declined dodge findings) and AGENTS.md (the design of this codebase is the agent's call)
- Ruff spellings of the same switch (`extend-per-file-ignores`, and `--ignore`, `--extend-ignore`, `--per-file-ignores` or a `--config` with those keys in a gate command): Proposal — refuse them with design call 4; yes — user, chat 2026-11-15 ("HARD ENG IS HARD FOR A REASON!!!" on declined dodge findings) and AGENTS.md (the design of this codebase is the agent's call)
- Fallow spellings of the same switch (`fallow.toml`, `.fallow.toml`, a `thresholdOverrides` entry above a default, a `complexity-*` rule set to `warn` or `off` in `rules` or `overrides`, and `maxUnitSize` in the report check): Proposal — refuse them with design call 3; yes — user, chat 2026-11-15 ("HARD ENG IS HARD FOR A REASON!!!" on declined dodge findings) and AGENTS.md (the design of this codebase is the agent's call)
- Secret gate forms that turn the history scan off without the key (a `secrets-history` gate that is not `gitleaks git .` with `--log-opts=--all`; `-b`/`--baseline-path`, `-i`/`--gitleaks-ignore-path`, `--enable-rule`, `--max-target-megabytes` or a `-c`/`--config` other than `.gitleaks.toml` in either secret gate; a `.gitleaks.toml` without `[extend] useDefault = true`; `--exit-code`, `--pre-commit`, `--staged` and `--max-decode-depth` in either secret gate): Proposal — refuse them with design call 1; yes — user, chat 2026-11-15 ("HARD ENG IS HARD FOR A REASON!!!" on declined dodge findings) and AGENTS.md (the design of this codebase is the agent's call)

## Repository context

Owners:
- Secret settings: `.hooks/gate_config.py` reads `scan_git_history` (lines 94, 922-923, 952-955) and drops the `secrets-history` gate; `.hooks/tool_setup.py:152` makes that role optional; `.hooks/gitleaks_scan.py` runs both scans and owns `new_commits_command`; nothing checks the history gate's command form (searched `.hooks/` for `gitleaks git`, `--log-opts`, `--baseline-path`, `--gitleaks-ignore-path`).
- Gitleaks entries and allowlists: `.hooks/whole_project.py` `LINE_IGNORES`, `gitleaks_switch_offs` and `switch_offs`; `.hooks/comments.py` `SCAN_IGNORES` and `security_hits` refuse every non-comment line today, both in the full check and in added lines (`security_switch_offs`).
- Generated files: `.hooks/gate_config.py` `generated_sources` returns `linguist-generated` and `linguist-vendored` together; design call 1 names `linguist-generated` only.
- Switch-off patterns: `.hooks/comments.py` `switch_off_pattern` (no `.rs` case), `pattern_switch_offs`, `scoped_names` (a `.rs` pattern also brings Rust test files into the assertion balance; `is_test_path` marks `tests/*.rs` as tests and `src/*.rs` not), `SWITCH_OFF_HEADER` and `COMMENT_HEADER`.
- Fallow: `.hooks/fallow_report.py` `HEALTH_LIMITS` (cyclomatic 20, cognitive 15, CRAP 30; no unit size), `fallow_failure` (refuses `--only` without health, not a subcommand), `validate_complexity` (reads the report at run time); `.hooks/untrusted_input.py` `jsonc_config` reads `.fallowrc.json` and `.fallowrc.jsonc`.
- Fallow defaults: Fallow 3.29.0 `fallow config-schema`, `HealthConfig`: `maxCyclomatic` default 20, `maxCognitive` 15, `maxCrap` 30.0, `maxUnitSize` 60; `ignore` "Glob patterns to exclude from complexity analysis"; `fallow config --help`: settings files are `.fallowrc.json`, `.fallowrc.jsonc`, `fallow.toml`, `.fallow.toml` (no bare `.fallowrc`). The combined JSON report's `health.summary` carries `max_unit_size_threshold`.
- Ruff: no Hard Eng reader of ruff settings today; `.hooks/python_setup.py` reads Pyrefly settings the same way (`pyrefly_gap`).
- Dart: `.hooks/dart_boundaries.py` `validate_dart_typing` requires each nested file to hold its own strict `analyzer` and `linter` settings (`NESTED_STEP`) and never checks its include chain; `validate_dart_includes` follows includes. Case run: a nested `test/analysis_options.yaml` with only `include: ../analysis_options.yaml` is refused today ("Dart requires analyzer settings"), and a full copy of the strict settings with no include passes, so the lint set can drop today.
- Rule text: `.agents/skills/he/references/requirements.md` HE-NO-SWITCH-OFF; `DECISION.md:19` records the user-approved history skip for this repository.
Same cause: Plan 2 (`features/strict-refusals/PLAN.md`, PR 638) refused inline switch-offs and allowlist lines; it helped (403 real switch-offs found in the step 1 scan) but left the config-level routes open, so projects moved to wider switches (step 1 judgement, faults 5 and 6). Other places searched: the Gitleaks command flags, Cargo `[lints]`, Fallow `thresholdOverrides`, `rules` and `overrides`, ruff command flags, `.gitleaks.toml` `[extend]`; each found form is a Proposal row above. Found, not planned: ruff `exclude` and `extend-exclude` (one copy excludes a stubs folder), and the `fallow architecture` gate form (three copies); the coordinator decides those.
Single source: The Fallow limits live once in `HEALTH_LIMITS` (gains `max_unit_size_threshold: 60`); the settings check maps the camel-case keys to it, and `dart_boundaries.MAX_CRAP = 30` (a copy found by search of `.hooks/` for `30`) reads the CRAP limit from it. The generated check stays `generated_sources`, with a way to ask for `linguist-generated` alone; no second attribute reader. The switch-off headers stay the two constants in `.hooks/comments.py`, used by both checks. The Gitleaks entry judge is one function in `.hooks/gitleaks_scan.py`, called only by the whole-project pass. Searched `.hooks/`, `tests/`, `.agents/skills/he/` and the three templates; the `.agents/skill-sources/*/.hooks/gate_config.py` copies are other repositories' installed hooks, updated by their own Hard Eng update, not copies to merge here.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: Autonomous. The owner's design calls 1 to 7 and the added case in the planning brief of 2026-11-16; the standing approval of 2026-11-15 to open, check and merge PRs in all projects and owned packages for the strict-rules effort; the Proposal rows cite the owner's standing words. Hard Eng's own history skip in `DECISION.md:19` was user-approved; design call 1 and the added case replace it.

## Acceptance + steps

Design per item:
1. Secrets. `scan_git_history` is refused in any value but `true` (remove the key). The full check judges each line of the root `.gitleaksignore` (Gitleaks reads only that one): an entry passes only when a Gitleaks scan run now, with no ignore file, finds that exact fingerprint, and either (a) the entry names a commit (`<sha>:<path>:<rule>:<line>`) and the current-files scan finds no hit of that rule in that path, or (b) its path is marked `linguist-generated`. Gitleaks 8.30.1 reads a root `.gitleaksignore` even when `-i` names an empty folder, so the judge scans where no such file exists: the named commits only (`gitleaks git <bare shared clone> --log-opts=--no-walk <shas>`, the same fingerprints as a full scan) and one current-files snapshot with the file removed, reused for every entry. The judge runs in the full check after the tools are installed, and the history scan scope becomes `--log-opts=--remotes HEAD`. Each refused entry names its reason: stale, commit not in this clone (fetch it or remove the entry), still in the current tree, or not generated. Every other entry, a `.gitleaksignore` in another folder and every `.gitleaks.toml` allowlist stay refused.
2. Rust. `switch_off_pattern` gets a `.rs` pattern: `#[allow(`, `#![allow(`, `#[expect(`, `#![expect(`, `cfg_attr(…allow(` or `expect(`, and `#[ignore` (Proposal). The whole-project pass also refuses a Cargo `[lints]` or `[workspace.lints]` entry at level `allow` (Proposal).
3. Fallow. `fallow_failure` refuses a native Fallow command whose first analysis word is `dead-code`, `dupes`, `flags`, `security` or `similar-code` (the analysis subcommands of `fallow --help` 3.29.0 other than `health` and `audit`), the same first sentence as `--only`, naming the subcommand to drop. Another first word is a path for Fallow (`fallow architecture` fails with "PATH 'architecture' does not exist" in a folder without it), runs the combined scan with health, and is not judged by this item. The whole-project pass reads every `.fallowrc.json`, `.fallowrc.jsonc`, `fallow.toml` and `.fallow.toml` and refuses a `health` limit above `HEALTH_LIMITS`, a non-empty `health.ignore`, a `thresholdOverrides` entry above a limit, and a `complexity-*` rule not at `error`.
4. Python. The whole-project pass reads every `pyproject.toml` (`[tool.ruff]`, `[tool.ruff.lint]`), `ruff.toml` and `.ruff.toml` and refuses `ignore`, `extend-ignore`, `per-file-ignores` and `extend-per-file-ignores`, one hit per key line. A gate command that passes ruff those keys as flags or `--config` text fails at load. The template's `--config "lint.flake8-annotations.ignore-fully-untyped = false"` and the `banned-api` `--config` lines must pass: match the key name before `=`, never a substring.
5. Dart. A nested `analysis_options.yaml` (below the package root, outside a nested package with its own `pubspec.yaml`) must reach the package's own `analysis_options.yaml` through its relative `include` chain; the typing check then reads the merged settings, so it no longer asks for a copy. The existing refusals of `false` rules and `ignore` errors stay.
6. Message. `SWITCH_OFF_HEADER` and `COMMENT_HEADER` add: a file that a tool writes passes when `.gitattributes` marks it `linguist-generated`.
7. flutter_skill_lints. No Hard Eng change. The route below is for its fix PR.

- [ ] `"scan_git_history": false` in `hard-eng.gates.json` is refused, and the message names the entry route → `tests/test_runner.py::test_turning_off_the_history_scan_is_refused` (replaces `test_history_exception_keeps_current_file_scanning` and the `scan_git_history` branch of `test_removing_shared_security_fails`, which assert the old skip) + HE-NO-SWITCH-OFF
- [ ] A `.gitleaksignore` entry passes only when today's scan finds it and it names a past commit whose path and rule have no hit in the current tree → `tests/test_strict_refusals.py::test_a_gitleaks_entry_for_a_past_commit_passes`
- [ ] A stale entry fails, an entry whose finding is still in the current tree fails, and an entry with no commit fails unless its path is marked `linguist-generated` (a `linguist-vendored` path fails) → `tests/test_strict_refusals.py::test_a_stale_or_current_gitleaks_entry_fails` and `tests/test_strict_refusals.py::test_a_gitleaks_entry_in_a_generated_file_passes`
- [ ] Every `.gitleaks.toml` allowlist and every other entry stay refused; the quick check (Stop hook) runs no scan and leaves a root `.gitleaksignore` line to the full check's judge, while a line in any other `.gitleaksignore` stays refused there → `tests/test_strict_refusals.py::test_gitleaks_rules_pass_and_allowlists_fail` + `tests/test_strict_refusals.py::test_the_quick_check_leaves_root_gitleaks_entries_to_the_full_check`
- [ ] Secret gates that narrow or baseline the scan fail at load (the Proposal forms), and the three template forms pass → `tests/test_current_files_gitleaks.py::test_a_secret_scan_that_narrows_or_baselines_fails` + `tests/test_current_files_gitleaks.py::test_a_history_gate_must_scan_every_commit`
- [ ] The history scan covers HEAD and the remote branches, so a local-only tag or branch never adds a hit that CI lacks → `tests/test_current_files_gitleaks.py::test_the_history_scan_covers_the_commits_ci_sees`
- [ ] A `.gitleaks.toml` without `[extend] useDefault = true` fails, and the full check judges a root `.gitleaksignore` after the tools are installed → `tests/test_strict_refusals.py::test_a_gitleaks_config_that_drops_the_default_rules_fails` + `tests/test_strict_refusals.py::test_the_full_check_judges_root_gitleaks_entries`
- [ ] Hard Eng's own `hard-eng.gates.json` drops the key and gets the template `secrets-history` gate; its root `.gitleaksignore` holds one entry for each of the 9 history findings on origin (each checked by hand first: a live credential stops the build and goes to the user); `DECISION.md:19` is removed; Hard Eng's own full `check` runs secrets-history and passes → HE-NO-SWITCH-OFF, proof in Verification
- [ ] Rust `#[allow(`, `#![allow(` and `#[expect(` are switch-offs, with the Proposal spellings, and a Rust test file's removed `assert` lines count in the balance → `tests/test_strict_refusals.py::test_rust_lint_attributes_are_switch_offs` + rows in `tests/switch_off_forms.py` + `tests/test_strict_refusals.py::test_a_cargo_lint_at_allow_is_a_switch_off` + `tests/test_strict_refusals.py::test_a_rust_test_files_removed_assertions_count_in_the_balance`
- [ ] A Fallow gate that runs the `dead-code` subcommand without health fails like `--only dead-code` → `tests/test_gate_tools.py::test_a_fallow_subcommand_without_health_fails` (replaces the `fallow dead-code` row of `tests/test_setup.py::test_update_gives_an_older_scanner_gate_its_required_strict_flags`: an update cannot repair that form, so the project changes the gate)
- [ ] A Fallow settings file with a health limit above Fallow's default, a health ignore list, a raised override or a complexity rule below `error` fails, for all four file names → `tests/test_strict_refusals.py::test_raised_or_ignored_fallow_health_settings_fail`; the report check also refuses `max_unit_size_threshold` above 60 → `tests/test_gate_tools.py::test_a_fallow_audit_with_a_raised_health_limit_fails`
- [ ] Ruff `ignore`, `extend-ignore` and `per-file-ignores` (and `extend-per-file-ignores`) in `pyproject.toml` or `ruff.toml` are switch-offs, top level and under `lint` → `tests/test_strict_refusals.py::test_ruff_ignore_settings_are_switch_offs`; gate flags → `tests/test_python_setup.py::test_a_ruff_gate_that_ignores_rules_fails` (the template's `annotations` gate is its passing near-miss)
- [ ] A nested `analysis_options.yaml` inside a package must reach the package's own `analysis_options.yaml`; one with only that include passes → `tests/test_dart_config.py::test_a_nested_settings_file_must_include_the_package_settings` (replaces `test_a_nested_settings_file_that_lacks_the_settings_is_named_with_its_step`, whose copy step is the old rule)
- [ ] The refusal names the `linguist-generated` route for a file that a tool writes → `tests/test_strict_refusals.py::test_each_refusal_names_the_fix_at_the_cause` (gains the route assertion)
- [ ] HE-NO-SWITCH-OFF text names each new form and the entry rule; `DECISION.md` has no history skip → `tests/test_requirements.py` registry checks + HE-NO-SWITCH-OFF
- [ ] flutter_skill_lints gets no Hard Eng exemption; its fix PR takes the route in Baseline → N/A — no Hard Eng change; the proof is the recorded flutter_skill_lints run in Baseline
- [ ] Each Proposal row's dodge form is refused, each by the test named on its design-call line above → HE-NO-SWITCH-OFF
- [ ] Per-id counts of each closure match the Baseline counts when the builder reruns the new pass on the 34 sealed copies, and each id that needs more work is named in Baseline → N/A — a recount over sealed copies, recorded in Verification; the fix PRs belong to the rollout plan
- [ ] No allowlist and no raised limit is added anywhere in this change → N/A — a diff review item; the Complete gate's whole-project pass on this branch proves it

Steps (one commit each): 1 secrets (entry judge, gate forms, history scan scope); 2 Rust; 3 Fallow; 4 ruff; 5 Dart nested; 6 messages and rule text; 7 the key refusal (last of the code, because this repository's own config holds the key until step 8); 8 Hard Eng's own history (config, entries, `DECISION.md`), after the coordinator confirms it. Each starts with its failing test.

## Baseline + execution

Result: Passed
Evidence: 2026-11-16 11:03, `python3 .hooks/hard-eng.py check --plan-stage Draft` on the starting code (origin/develop 80756642, whose required CI checks passed) with only this plan added: no package reads a plan, so only the secret scan ran; no leaks found; exit 0.

Counts in the 34 sealed scan copies, read only, at the step 1 scan revision. Scripts and per-id output stay in the planner's session evidence folder (not in this repository). "New" means a hit the closure adds that today's rules pass.
- Item 1, key: no copy sets `scan_git_history`; Hard Eng itself does (1).
- Item 1, history (Gitleaks 8.30.1, default rules, no ignore file, allowlists removed; findings / only in past commits): P1 168 / 46, P18 31 / 16, P19 6 / 6, P22 28 / 28, P24 24 / 21, P26 3 / 0, P27 1 / 0, P7 3 / 3, dart-decimate 10 / 0; Hard Eng 9 / 9 in 4 commits on origin `main` and `develop`; the history scan covers HEAD and the remote branches (`--remotes HEAD`), the commits CI sees, and finds the same 9 / 9 locally and in CI. Local-only tags (69 here, none on origin) and local-only branches are outside it. Current files (owned, not generated): P1 32, P24 11, dart-decimate 10, P18 3, P26 3, P27 1. None of the current hits is in a `linguist-generated` file today.
- Item 1, existing entries: P1 3 (commits not in the copy), P2 21 (9 stale, 12 commits not in the copy), P11 3 stale, P26 11 stale. No entry in any copy passes the new rule today. Item 1 relaxes the entry refusal, so it adds no new refusal in a copy.
- Item 1, Proposal forms: 0 in every copy (every `.gitleaks.toml` keeps `useDefault = true`; P26's `--config .gitleaks.toml` passes).
- Item 2: dart-decimate 5 (2 `#[allow(`, 3 `#[expect(`); 0 `#[ignore`, 0 Cargo `allow`, 0 `cfg_attr`; every other copy 0.
- Item 3: `dead-code` subcommand gates P8 1, P12 1, P25 1; raised limit P25 1 (`maxCrap` 100, today refused only when the health report runs); `health.ignore` P26 3, P27 1, dart-decimate 1; overrides and rule severities 0.
- Item 4: P7 2 lines (6 codes), P10 2 lines (`lint.ignore` 12 codes, `per-file-ignores` 2 entries); gate flags 0; Hard Eng 0.
- Item 5: flutter_skill_lints 1 (`example/analysis_options.yaml` includes only the public lint set); every other copy 0.
- Item 6: 0 new; the 9 tool-written files of the judgement (P1, P22, P24, P26) get the route in the message.
- Item 7: flutter_skill_lints 129 lines (already refused by plan 2).

Ids that need more work in their fix PRs: P1, P18, P19, P22, P24, P26, P27, P7 and dart-decimate (move each history hit to an entry the rule accepts, fix or mark generated each current hit, remove the allowlists); P2, P11 and P26 (remove stale entries; P1 and P2 also prove their missing-commit entries on the real remote); P8, P12 and P25 (Fallow gate form); P25, P26, P27 and dart-decimate (Fallow settings); P7 and P10 (ruff); dart-decimate (Rust); flutter_skill_lints (items 5 and 7). Each fix PR must not use `scan_git_history: false`.

flutter_skill_lints route (item 7), run on a scratch clone of its copy: the `non_constant_identifier_names` lint has no `test_` allowance (a probe with `test_foo` and `test_fooBar` names: 6 hits). Route: each test method becomes a private lowerCamel method (`test_reportsX` to `_reportsX`), and `main()` wires it through one helper, `ruleTests<T>(T.new, {'test_reportsX': (test) => test._reportsX()})`, which runs `setUp`, the body and `tearDown` inside plain `group` and `test` calls with the old test names. Result: 129 files changed, the `test_reflective_loader` import and every `ignore_for_file: non_constant_identifier_names` gone; `dart analyze --fatal-infos .` reports no issues; `dart test` runs 2,790 tests before and 2,790 after, every name the same, all passed (1 skipped both times). A method left out of the map fails analysis (`unused_element`), and a broken body fails its test. No Hard Eng exemption is needed.

Execution: One Sonnet builder in a Hard Eng worktree from develop, steps 1 to 6 in order; step 1 first, because the entry judge and Hard Eng's own history scan carry the main risk. The builder runs the new whole-project pass over the 34 sealed copies (read only) and checks each per-id count above before the Complete gate. A fresh independent review through `hard-eng.py challenge` on the candidate commit, then the Complete gate once. The fix PRs per id stay with the rollout plan's builders.

## Risks + recovery

- An entry judge that runs Gitleaks makes the full check slower. Recovery: it runs only when a root `.gitleaksignore` has entries, scans only the named commits (P18: 17 commits in 2.9 s against 1,303 commits in 12.8 s) and reuses the current-files snapshot; the Stop hook does not run it.
- A history hit in Hard Eng or a project may be a live credential, which an entry would hide. Recovery: each entry is written only after the value is read locally; a live one stops the work and goes to the user to revoke. Hard Eng's hits look like digest values and test samples by their redacted context.
- A shallow clone or a fetch without tags cannot find an entry's commit, so a good entry reads as stale. Recovery: CI already fetches with `fetch-depth: 0`; the refusal names a missing commit apart from a stale one and says to fetch.
- A local history scan that reads local-only tags or branches finds hits that CI never sees, and an entry for them would be refused in CI as a missing commit. Recovery: the history scan covers HEAD and the remote branches only (`--remotes HEAD`), so a local check and CI agree; no tag is deleted or pushed and no entry is written for a local-only commit.
- Moving Dart nested files to an include chain could let a nested file override a strict setting. Recovery: the merged settings run through the same typing check, and `false` rules and `ignore` errors stay refused in every file of the chain.

## ux_reference

N/A — no product screen changes; the work adds checks and refusal text.

## Verification

Result: Pending
Evidence: Pending — the builder's focused tests, the challenge, the Complete gate and the per-id recount.
E2E: Required — the real `python3 .hooks/hard-eng.py check` on Hard Eng itself with the history gate on, and the new whole-project pass over the 34 sealed copies matching the Baseline counts.
Real service: N/A — the checks read local files and run local scanners; no outside service is called.
Retro: Pending — written at task end.

Delivery target: Merge
Delivery path: into develop, then the release PR from develop to main after the fix PRs listed in Baseline.
Delivery: Pending — required remote proof.
