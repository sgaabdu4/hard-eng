# Fast Design-System Look Checks, Local UI Proof Gate, and Tailwind Theme Token Validation

Status: Complete

## Outcome + scope

Harden Hard Eng's UI-design enforcement without adding noticeable latency to `check` or extra reviewer turns to `look`:
1. Pass `DESIGN.md` (and `UI-LIBRARY.md` when present, bounded to 24,000 UTF-8 bytes with 8,000 bytes reserved for `UI-LIBRARY.md`) directly into `look`'s existing single reviewer prompt, record the full-document `"design_doc"` SHA-256 in the look record and `- design:` in the `Look review:` PR block, refuse a not-applicable `Design system` verdict when `DESIGN.md` is present, and refuse records in `ui_proof` that did not judge against the current `DESIGN.md`.
2. Enforce fast local-only Complete-stage UI proof checks in `.hooks/local_ui_proof.py` (reusing `validate_rules`'s changed-file set so the non-UI fast path runs in <5 ms with zero extra git subprocesses, skipped in `GITHUB_ACTIONS`, `CI`, and `--quick`) during `check --plan-stage Complete` and `push_text_checks`: refuse non-unchanged not-applicable `ux_reference` entries on visible changes (supporting multi-plan sibling scopes without letting a visual sibling skip proof), verify Flutter `meetsGuideline` coverage, verify finding-free `.hard-eng/browser` captures across every changed route and width (including dirty unchanged-pair proofs with zero findings, staleness after reverting or deleting UI edits, quoted binary asset diffs, and `HARD_ENG_TOOL_OWNER` pre-push snapshots), and verify clean `look` records covering every changed route for the current `HEAD` and `DESIGN.md` (matching `ship_problem`'s unchanged-appearance contract, where unchanged-only branches verify equal finding-free base/head captures without requiring `look`).
3. Extend `HE-UI-SOURCE` in `.hooks/ui_rules.py` and `.hooks/comments.py` to flag undefined Tailwind v4 `@theme` colour utility classes (`text-`, `bg-`, `border-`, `ring-`, `fill-`, `stroke-`) on added UI lines inside packages whose tracked CSS defines `@theme` (scoping CSS strictly per package in `@import` cascade order including package-root CSS, respecting `--color-*: initial`, `--color-<name>: initial`, `--color-*`, `--text-*`, `--background-image-*`, `@utility`, project CSS classes, built-in utilities, JSX expression attributes, comparison strings, multiline `@apply`, multiline script class helpers and template literals, and skipping packages with `tailwind.config.*`, `@config`, or third-party colour `@plugin`).
4. Update `he-build/SKILL.md`, `he-plan/references/ux.md`, and `he/references/requirements.md` to forbid substituting scratch Playwright scripts for `browser capture` / `browser measure` and document the new checks.

Non-goals: adding extra agent turns, running a browser inside `check`, or enforcing undefined token checks on Tailwind v3 JS/TS configs.

## Sources + coverage

Sources: N/A — user explicitly approved implementing these fast UI-design enforcement additions in this session.
Deliverables: None

## Repository context

Owners:
- `.hooks/look.py` owns the fresh image reviewer prompt, full-doc `design_hash`, UTF-8 bounded `design_text`, look records, and `Look review:` PR block formatting/validation.
- `.hooks/ui_proof.py` owns visible-change detection and shared browser/look/unchanged record verification.
- `.hooks/local_ui_proof.py` owns fast local Complete-stage UI proof validation and `HARD_ENG_TOOL_OWNER` resolution.
- `.hooks/ui_rules.py` and `.hooks/comments.py` own `HE-UI-SOURCE` changed-line UI source rules and `validate_rules` orchestration.
- `.hooks/gate_runner.py` and `.hooks/push_text.py` invoke `validate_rules` and local push checks.
- `.agents/skills/he/references/requirements.md`, `.agents/skills/he-build/SKILL.md`, and `.agents/skills/he-plan/references/ux.md` own the `HE-UI-SOURCE` requirement definition and agent workflow guidance.

Same cause: Visual reviews previously omitted `DESIGN.md`, local Complete checks skipped `.hard-eng/browser` and `hard-eng/look` verification until `ship`, and Tailwind v4 silently dropped undefined semantic colour classes; all three gaps are closed at their owners together.
Single source: `.hooks/look.py`, `.hooks/ui_proof.py`, `.hooks/local_ui_proof.py`, `.hooks/ui_rules.py`, and `.agents/skills/he/references/requirements.md` (`HE-UI-SOURCE`).

## Decisions + authorization

Blockers: None
Handoff: None
Authority: User approved implementing all four fast UI-design checks in chat on 2026-11-22 with the constraint not to slow down Hard Eng.
Review declined: Live Claude CLI run for `look` :: Attempted a live `look.look_command` run with `--host codex` (invoking `claude`), which failed because local Claude CLI authentication has expired (`Failed to authenticate: this login reached its time limit and cannot be renewed`); this branch changes only the shared prompt text (`prompt_for`) and `judge` logic without changing Claude CLI flags or `claude_proof`, the live Codex CLI run verified the changed prompt and `DESIGN.md` judgment end-to-end, and Claude invocation/proof parsing remains verified by `tests/test_look.py`.

## Acceptance + steps

- [x] `look` passes `DESIGN.md` (and `UI-LIBRARY.md` when present, bounded in UTF-8 bytes with reserved space for `UI-LIBRARY.md`) in its existing single prompt, records full-file `design_doc` SHA-256 in the look record and `- design:` in the `Look review:` block, refuses a not-applicable `Design system` verdict when `DESIGN.md` exists, and `ui_proof` refuses records whose `design_doc` does not match the current `DESIGN.md` → `tests/test_look.py::test_look_includes_design_docs_in_prompt_record_and_block`, `tests/test_look.py::test_look_refuses_design_system_na_when_design_doc_exists`, and `tests/test_look.py::test_look_truncates_large_design_docs_in_utf8_bytes_and_preserves_ui_library`.
- [x] Local `check --plan-stage Complete` and `push_text_checks` (outside `GITHUB_ACTIONS`, `CI`, and `--quick`) refuse visible changes lacking clean measured browser captures (handling dirty-tree edits, deleted/reverted components, dirty finding-free unchanged-pair proofs with route matching, multi-plan sibling scopes with directory-prefix ownership and multi-route coverage, quoted binary asset diffs, staged plan edits after committed deletions, and `HARD_ENG_TOOL_OWNER` pre-push snapshots), Flutter `meetsGuideline` tests, valid `ux_reference`, or clean `look` records for `HEAD` and `DESIGN.md`, while taking the <5 ms zero-git fast path on non-UI diffs and never importing `local_ui_proof` in `--quick`/`stop`/`session` → `tests/test_local_ui_proof.py::test_local_complete_check_refuses_missing_browser_and_look_then_passes`, `tests/test_local_ui_proof.py::test_local_complete_check_refuses_na_ux_reference_on_visible_change`, `tests/test_local_ui_proof.py::test_local_complete_check_supports_dirty_build_and_rejects_stale_and_deleted_edits`, `tests/test_local_ui_proof.py::test_local_complete_check_rejects_discarded_dirty_capture_and_allows_staged_plan_after_committed_delete`, `tests/test_local_ui_proof.py::test_local_complete_check_reads_owner_evidence_inside_pre_push_snapshot`, `tests/test_local_ui_proof.py::test_local_complete_check_validates_unchanged_pair_when_dirty_and_skips_in_ci`, `tests/test_local_ui_proof.py::test_local_complete_check_handles_multi_plan_siblings_and_multiple_routes`, `tests/test_local_ui_proof.py::test_local_complete_check_detects_quoted_binary_ui_asset_diff`, `tests/test_local_ui_proof.py::test_local_complete_check_validates_native_flutter_guideline_and_look`, `tests/test_local_ui_proof.py::test_local_complete_check_fast_path_and_quick_import_isolation`, `tests/test_local_ui_proof.py::test_push_text_checks_refuses_missing_local_ui_proof`, and `tests/test_ui_quality.py::test_quick_check_runs_no_ui_proof`.
- [x] `HE-UI-SOURCE` flags undefined Tailwind v4 `@theme` colour utility classes on added UI lines (including multiline `@apply`, multiline `cn(...)` helpers, and class-context multiline template literals without flagging JSX display templates), honours CSS `@import` entrypoint cascade order, `--color-*: initial`, `--color-<name>: initial`, custom `@theme`/`@utility`/CSS classes, built-in utilities, single- and multi-line comparison strings, JSX expression non-class attributes, strict per-package CSS scoping including package-root CSS, and skips `tailwind.config.*` and unknown `@plugin` packages → `tests/test_ui_rules.py::test_undefined_tailwind_theme_token_is_refused`, `tests/test_ui_rules.py::test_multiline_apply_and_script_class_helper_refuse_undefined_tokens`, `tests/test_ui_rules.py::test_css_import_order_governs_color_reset_and_restore`, `tests/test_ui_rules.py::test_theme_with_color_reset_refuses_default_palette_colours`, `tests/test_ui_rules.py::test_defined_builtin_and_non_class_tailwind_tokens_pass`, `tests/test_ui_rules.py::test_packages_with_tailwind_config_or_unknown_plugin_are_skipped`, and `tests/test_ui_rules.py::test_monorepo_theme_is_scoped_to_its_own_package`.
- [x] Edited skill/reference prose in `.agents/skills/he-build/SKILL.md`, `.agents/skills/he-plan/references/ux.md`, and `.agents/skills/he/references/requirements.md` passed an independent Writing Great Skills Reader check with every quoted sentence reworded, and all skill links and requirement registry checks pass → `tests/test_requirements.py::test_proven_registry_passes` and `tests/test_skill_links.py::test_distributed_skill_links_resolve`.

## Baseline + execution

Result: Passed
Evidence: Clean worktree created from `origin/develop` (`74c8103d`) where baseline checks pass.
Execution: Implemented changes in `.hooks/look.py`, `.hooks/ui_proof.py`, `.hooks/local_ui_proof.py`, `.hooks/ui_rules.py`, `.hooks/comments.py`, `.hooks/gate_runner.py`, `.hooks/push_text.py`, `pyproject.toml`, and skill docs; ran an independent Writing Great Skills Reader check and reworded every quoted sentence across `he-build/SKILL.md`, `ux.md`, and `requirements.md`; ran a live `look` probe against `DESIGN.md`; added unit and integration tests; full `check --plan-stage Complete`, `challenge`, PR, CI, and merge to `develop` follow.

## Risks + recovery

An overly broad Tailwind token regex could false-positive on valid utilities or non-class strings; mitigated by restricting to Tailwind v4 `@theme` packages without `tailwind.config.*`/`@config`/unknown `@plugin`, checking only added lines in markup (with non-class attribute masking), script class-helper, and `@apply` contexts, allowing all built-in utilities and CSS property names, and testing against real Tailwind v4 class sets. Requiring local browser/look proof at Complete could block pre-push snapshots or CI runners if they lacked local evidence; mitigated by resolving `HARD_ENG_TOOL_OWNER` to the owner checkout and skipping in `GITHUB_ACTIONS`, `CI`, and `--quick`. Recovery: revert the merge commit on `develop`.

## ux_reference

N/A — Hard Eng is a CLI and hook toolkit with no visual application UI.

## Verification

Result: Passed
Evidence: Focused `pytest`, `ruff` (format, lint, complexity, annotations), `pyrefly`, `hot-paths`, and full `python3 .hooks/hard-eng.py check --base origin/develop --plan-stage Complete` plus independent `challenge` run on the final commit before push; an independent Writing Great Skills Reader check reviewed all three edited skill/reference passages and all quoted sentences were reworded.
E2E: N/A — Hard Eng CLI/hook changes are verified by real Git worktree, fixture browser capture, and subprocess integration tests in the pytest suite.
Real service: Passed — ran `look.look_command` (`--host agy`, invoking the live `codex` CLI) in a temporary Git repository with a real `DESIGN.md` (`#1B2A4A` navy button, `#FFFFFF` canvas, `#111827` ink) and a real `browser capture` screenshot (`after-1280.png`); verified `record["design_doc"] == look.design_hash(root)` and observed the real reviewer directly cite `DESIGN.md` in its `Design system: Fail` line (matching the navy button and white canvas against `DESIGN.md` and catching the `#374151` helper text colour mismatch against `#111827` ink). Attempted live `claude` CLI run (`--host codex`) was blocked by expired local Claude CLI auth (`Failed to authenticate: this login reached its time limit`); Claude CLI flags and stream parsing are unchanged and remain covered by `tests/test_look.py`.
Retro: None — preventative hardening from an observed UI review bypass.
Delivery target: Merge
Delivery: Pending — full check, independent challenge, PR to `develop`, CI, and merge.
