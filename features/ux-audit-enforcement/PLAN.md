# Universal UX Audit Enforcement Guards

Status: Complete

## Outcome + scope

Close six universal UX regression gaps discovered in real web application audits while keeping non-UI checks under 5 ms and avoiding extra browser round-trips or `look` turns:
1. Fix `.hooks/ui_measure.py` `competing-buttons` so two or more filled buttons in the same button group fail even when they share the same brand fill colour (`filled.length > 1` instead of unique fill colours `fills.size > 1`), and add `duplicate-buttons` for identical visible button labels repeated inside one direct button group.
2. Add zero-extra-round-trip runtime browser checks in `.hooks/ui_measure.py` (`MEASURE_SCRIPT`) for inverted `heading-hierarchy`, `clipped-control` (`<select>` clipping its selected option and clipped single-line `<button>` text), `clipped-chrome` (fixed or sticky tall chrome pushing interactive controls below the viewport without scrolling), `fetch-waterfall` (> 3 sequential client fetch waves on load), and `layout-shift` (`CLS > 0.1` via buffered `PerformanceObserver`).
3. Extend `HE-UI-SOURCE` in `.hooks/ui_rules.py` and `.hooks/comments.py` with a pure-Python duplicate sibling React `key` static check on added `.tsx`/`.jsx` lines (ignoring mutually exclusive ternary branches and separate `.map` callbacks while catching fragment, element, conditional `&&`, and array siblings) and a `DESIGN.md` YAML front-matter `fontWeight` parity check against Tailwind v4 `@theme` `--text-*--font-weight` and loaded `@font-face` weight ranges.
4. Update `.agents/skills/he-plan/references/ux.md` (active/next step first above collapsed completed steps on multi-step screens; web compositor-only motion, hover media gating, `:active` press feedback, and reduced-motion opacity fades) and `.agents/skills/e2e/SKILL.md` (`A → B → C → A` master-detail/tab switching, realistic 20+ row list volume, and delayed async responses).

Non-goals: running extra browser navigations or extra `look` turns, adding external JS/CSS parser dependencies, or adding visual/CSS wording into `ux.md`'s `Standard patterns` table.

## Sources + coverage

Sources: User's direct instructions in chat on 2026-11-22 approving the universal UX audit upgrades and active-step ordering constraint (`yes pls if it doesn't make hard-eng slow`, `Shouldn't we go to the next step when the first step is done?`), read in full.
Reviewer: N/A — user directly authorized these universal Hard Eng UX enforcement additions in this session.
Deliverables: None

- User instruction, universal UX audit enforcement without slowing Hard Eng: In scope — fixes `competing-buttons` for same-colour filled buttons
- User instruction, active step first on multi-step screens: In scope — Updated `ux.md` and `e2e/SKILL.md` prose passes

## Repository context

Owners:
- `.hooks/ui_measure.py` owns `LIMITS` and `MEASURE_SCRIPT` evaluated once per capture in `.hooks/browser.py`.
- `.hooks/ui_rules.py`, `.hooks/ui_audit_rules.py`, and `.hooks/comments.py` own `HE-UI-SOURCE` static checks and fast-path candidate prefiltering.
- `.agents/skills/he-plan/references/ux.md` owns the `Hierarchy` and `Design system` usability rules.
- `.agents/skills/e2e/SKILL.md` owns E2E journey-testing requirements.

Same cause: `ui_measure.py` counted unique fill colours instead of filled buttons and did not check duplicate sibling buttons, heading hierarchy, clipped controls/sidebar chrome, sequential fetch waves, or `CLS`, while `ui_rules.py` did not check duplicate sibling React keys or `DESIGN.md` heading weight parity; all six gaps are closed together at their existing owners.
Single source: `.hooks/ui_measure.py` (`MEASURE_SCRIPT`), `.hooks/ui_rules.py` (`ui_findings`), `.hooks/comments.py` (`ui_candidate`), `.agents/skills/he-plan/references/ux.md`, and `.agents/skills/e2e/SKILL.md`.

## Decisions + authorization

Blockers: None
Handoff: None
Authority: User directly authorized implementing all six UX audit guards and active-step ordering in chat on 2026-11-22 with the requirement not to slow Hard Eng down.

## Acceptance + steps

- [x] `.hooks/ui_measure.py` fixes `competing-buttons` for same-colour filled buttons and detects `duplicate-buttons`, `heading-hierarchy`, `clipped-control` (`<select>` and `<button>`), `clipped-chrome`, `fetch-waterfall`, and `layout-shift` in real headless Chromium with zero layout misfires on saved public pages → `tests/test_ui_audit_guards.py::test_each_runtime_audit_guard_finds_one_fault`, `tests/test_ui_audit_guards.py::test_sequential_fetch_waterfall_and_layout_shift_are_measured`, and `tests/test_ui_pages.py::test_saved_public_pages_have_no_layout_misfires`.
- [x] `.hooks/ui_rules.py` and `.hooks/comments.py` refuse duplicate sibling React `key` attributes (catching fragment/element/conditional siblings without flagging ternaries or separate `.map` loops), verify `DESIGN.md` YAML `fontWeight` parity against `@theme` `--text-*--font-weight` and loaded `@font-face` ranges, and keep `ui_rules` un-imported on non-UI diffs → `tests/test_ui_rules.py::test_duplicate_sibling_react_keys_are_refused_without_flagging_ternaries_or_maps`, `tests/test_ui_rules.py::test_design_md_font_weight_parity_catches_missing_theme_weight_and_unloaded_font_face`, and `tests/test_ui_rules.py::test_a_change_with_no_ui_file_does_not_load_the_ui_rules`.
- [x] Updated `ux.md` and `e2e/SKILL.md` prose passes independent Writing Great Skills Reader review, `Standard patterns` behaviour-only checks, and skill link/size tests → `tests/test_ui_pages.py::test_standard_patterns_state_behaviour_and_placement_only`, `tests/test_skill_links.py::test_distributed_skill_links_resolve`, and `tests/test_skill_links.py::test_distributed_skills_fit_the_codex_skill_limit`.

## Baseline + execution

Result: Passed
Evidence: Clean worktree branched from `feat/look-design-system-and-ui-gates` (`af2cd8a5`); implemented all six runtime and static guards plus skill updates and verified in real headless Chromium and unit suites.
Execution: Updated `.hooks/ui_measure.py`, `.hooks/ui_rules.py`, `.hooks/ui_audit_rules.py`, `.hooks/comments.py`, `pyproject.toml`, `.agents/skills/he-plan/references/ux.md`, `.agents/skills/e2e/SKILL.md`, `tests/test_ui_audit_guards.py`, `tests/test_ui_pages.py`, and `tests/test_ui_rules.py`; ran independent Writing Great Skills Reader review and reworded every quoted phrase.

## Risks + recovery

New runtime browser checks could misfire on legitimate layouts or display typography; mitigated by scoping `heading-hierarchy` weight checks to compact non-display headings, omitting native arrow padding on `appearance: none` selects, restricting `clipped-chrome` to `fixed` chrome and `overflow: hidden`/`clip` sticky containers (skipping reachable scrolling sticky sidebars and nested scrollers), computing standard Web Vitals CLS session windows (1 s gap / 5 s max span), checking `duplicate-buttons` strictly within one direct button group, and verifying zero misfires on all saved public GOV.UK pages across 390, 768, and 1280 px. Note: `fetch-waterfall` counts non-overlapping load-time fetch/XHR waves from `PerformanceResourceTiming` because the browser does not expose JS call-stack causality across fetches. Static React `key` parsing could misfire on TypeScript generics or ternaries; mitigated by tag-matched stack popping, branch-isolated ternary slots, standalone array frames, multiline `key=` line tracking, and isolated arrow-function scopes. Recovery: revert the commits on `develop`.

## ux_reference

N/A — Hard Eng is a CLI and hook toolkit with no visual application UI.

## Verification

Result: Passed
Evidence: Verified headless Chromium tests in `tests/test_ui_audit_guards.py` and `tests/test_ui_pages.py` (every new runtime guard plus zero misfires on all saved GOV.UK pages), plus 193 tests across `tests/test_ui_rules.py`, `tests/test_skill_links.py`, `tests/performance/`, and `tests/test_updates.py`, `ruff`, `complexity`, `pyrefly`, and `hard-eng.py check --quick --plan-stage Complete`; an independent Writing Great Skills Reader reviewed all edited `ux.md` and `e2e/SKILL.md` sentences and every quoted phrase was reworded.
E2E: N/A — browser measurement rules are proven directly in headless Chromium via `tests/test_ui_audit_guards.py` and `tests/test_ui_pages.py`.
Real service: N/A — runs locally against headless Chromium and unit fixtures with no external service calls.
Retro: Escaped base-branch bug in `.hooks/ui_measure.py` (`competing-buttons` checked unique fill colours `fills.size > 1` instead of `filled.length > 1`) plus five UX audit gaps → `tests/test_ui_audit_guards.py::test_each_runtime_audit_guard_finds_one_fault` (`competing-same-colour`, `duplicate-buttons`, `heading-hierarchy`, `clipped-select`, `clipped-button`, `clipped-chrome`), `tests/test_ui_audit_guards.py::test_sequential_fetch_waterfall_and_layout_shift_are_measured`, and `tests/test_ui_rules.py::test_duplicate_sibling_react_keys_are_refused_without_flagging_ternaries_or_maps`.

Delivery target: Merge
Delivery: Pending — rebase onto `develop` after PR #697 merges, run challenge, PR, CI, merge, and release to `main`.
